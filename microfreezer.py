#!/usr/bin/env python
#
# Copyright (c) 2021, insigh.io
#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

import logging
import os
from os import listdir
from os.path import isfile, join
from shutil import copyfile, rmtree
import binascii
import traceback
import hashlib
from functools import partial
from aux_files.config import Config

def mkdir(dirPath):
    try:
        logging.debug("Making directory: {}".format(dirPath))
        os.mkdir(dirPath)
    except Exception as e:
        logging.debug("directory {} already exists?".format(dirPath))


def readFromFile(source, open_binary=False):
    try:
        f = open(source, "rb" if open_binary else "r")
        contents = f.read()
        f.close()
        logging.debug("file [{}] read finished.".format(source))
        return contents
    except Exception as e:
        logging.debug("file [{}] read failed.".format(source))
        traceback.print_exc()
        return ""


def writeToFile(destination, content, open_binary=False):
    try:
        out_file = open(destination, "wb" if open_binary else "w")
        out_file.write(content)
        out_file.close()
        logging.debug("file [{}] write finished.".format(destination))
        return True
    except Exception as e:
        logging.debug("file [{}] write failed.".format(destination))
        traceback.print_exc()
    return False


def removeFile(directoryPath):
    try:
        os.remove(directoryPath)
        logging.debug("Removed file: {}".format(directoryPath))
    except OSError as e:
        logging.error("remove file {} failed".format(directoryPath))


# Create a single md5 sum for all files included in folders and subfolders of path
def md5folder(directoryPath, blocksize=65536):
    hash = hashlib.md5()
    logging.info("[md5sum]: Starting calculation of md5sum of folder: " + directoryPath)
    for (directory, _, files) in os.walk(directoryPath):
        for f in files:
            path = join(directory, f)
            with open(path, "rb") as tmpF:
                for block in iter(partial(tmpF.read, blocksize), b''):
                    hash.update(block)
    return hash.hexdigest()


def removeContents(directoryBaseDir, directoryContents):
    for file in directoryContents:
        path = join(directoryBaseDir, file)
        if isfile(path):
            removeFile(path)
        else:
            rmtree(path)


class MicroFreezer:
    def __init__(self):
        self.config = Config()
        self.excludeList = self.config.get("excludeList", [])
        self.directoriesKeptInFrozen = self.config.get("directoriesKeptInFrozen", [])
        self.enableZlibCompression = self.config.get("enableZlibCompression", True)
        self.removeComments = self.config.get("removeComments", False)
        self.targetESP32 = self.config.get("targetESP32", False)
        self.targetPycom = self.config.get("targetPycom", True)
        self.flashRootFolder = "/flash/" if self.targetPycom else "/"
        self.flashRootFolder = os.path.normpath(self.flashRootFolder)
        logging.info("Selected flash root folder: " + self.flashRootFolder)

    def run(self, sourceDir, destDir):
        self.convertedFileNumber = 0
        self.baseSourceDir = sourceDir
        self.baseDestDir = destDir
        if self.targetESP32:
            self.baseDestDirCustom = destDir
            self.baseDestDirBase = destDir
        elif self.targetPycom:
            self.baseDestDirCustom = join(destDir, "Custom")
            self.baseDestDirBase = join(destDir, "Base")
        self.defrostFolderPath = join(self.baseDestDirCustom, "_todefrost")

        logging.info("deleting old files from {}".format(self.baseDestDir))
        mkdir(self.baseDestDir)
        removeContents(self.baseDestDir, listdir(self.baseDestDir))
        mkdir(self.baseDestDirCustom)
        mkdir(self.baseDestDirBase)
        mkdir(self.defrostFolderPath)

        logging.info("Copying new files to {}".format(self.baseDestDir))
        self.processFiles()
        logging.info("Finalizing...")
        self.finalize()
        logging.info("Operation completed successfully.")

    def run_package(self, sourceDir, destDir):
        self.baseSourceDir = sourceDir
        self.baseDestDir = destDir

        logging.info("deleting old files from {}".format(self.baseDestDir))
        mkdir(self.baseDestDir)
        removeContents(self.baseDestDir, listdir(self.baseDestDir))

        logging.info("Copying new files to {}".format(self.baseDestDir))
        self.copyRecursive(self.baseSourceDir, self.baseDestDir, True)

        logging.info("Finalizing...")
        self.finalize_package()
        logging.info("Operation completed successfully.")

    # https://www.codingconception.com/python-examples/write-a-program-to-delete-comment-lines-from-a-file-in-python/
    def removeCommentsAndReplaceFile(self, sourceFile, destFile):
        # reading the file
        with open(sourceFile) as fp:
            contents=fp.readlines()

        # initialize two counter to check mismatch between "(" and ")"
        open_bracket_counter=0
        close_bracket_counter=0

        # whenever an element deleted from the list length of the list will be decreased
        decreasing_counter=0

        logging.debug("  #file: {}, lines: {}".format(sourceFile, len(contents)))

        for number in range(len(contents)):

            # checking if the line contains "#" or not
            if "#" in contents[number-decreasing_counter]:

                # delete the line if startswith "#"
                if contents[number-decreasing_counter].startswith("#"):
                    contents.remove(contents[number-decreasing_counter])
                    decreasing_counter+=1

                # delete the character after the "#"
                else:
                    newline=""
                    for character in contents[number-decreasing_counter]:
                        if character=="(":
                            open_bracket_counter+=1
                            newline+=character
                        elif character==")":
                            close_bracket_counter+=1
                            newline+=character
                        elif character=="#" and open_bracket_counter==close_bracket_counter:
                            break
                        else:
                            newline+=character
                    contents.remove(contents[number-decreasing_counter])
                    contents.insert(number-decreasing_counter,newline)


        # writing into a new file
        with open(destFile,"w") as fp:
            fp.writelines(contents)

    def convertFileToBase64(self, sourceFile, destFile):
        logging.debug("  [C]: " + str(sourceFile))
        tmp_file = None
        if self.removeComments and sourceFile.endswith(".py"):
            import uuid
            tmp_file = '/tmp/' + str(uuid.uuid1()) + ".py"
            self.removeCommentsAndReplaceFile(sourceFile, tmp_file)
            sourceFile = tmp_file

        bytes = readFromFile(sourceFile, True)

        if self.enableZlibCompression:
            import zlib
            bytes = zlib.compress(bytes, 4)
        newFileName = join(self.defrostFolderPath, "base64_" + str(self.convertedFileNumber) + ".py")
        self.convertedFileNumber += 1
        contents = 'PATH="{}"\nDATA={}'.format(join(self.flashRootFolder, destFile), binascii.b2a_base64(bytes))
        writeToFile(newFileName, contents)

        if self.removeComments and tmp_file is not None:
            try:
                import os
                os.remove(tmp_file)
            except Exception as e:
                logging.exception(e, "Error deleting file [{}]".format(tmp_file))

    def processFiles(self, currentPath=""):
        absoluteCurrentPath = join(self.baseSourceDir, currentPath)

        for f in listdir(absoluteCurrentPath):
            if f in self.excludeList:
                logging.debug("ignoring file: {}".format(f))
                continue
            absoluteSourceDir = join(absoluteCurrentPath, f)

            if isfile(absoluteSourceDir):
                logging.debug("File: " + str(absoluteSourceDir))
                self.convertFileToBase64(absoluteSourceDir, join(currentPath, f))
            else:
                logging.debug("Dir:  " + str(absoluteSourceDir))

                if f in self.directoriesKeptInFrozen:
                    self.copyRecursive(absoluteSourceDir, self.baseDestDirCustom)
                else:
                    self.processFiles(join(currentPath, f))

    def copyRecursive(self, sourceDir, destDir, ignoreFrozenDirectories=False):
        for f in listdir(sourceDir):
            if f in self.excludeList:
                logging.debug("ignoring file: {}".format(f))
                continue

            absoluteSourceDir = join(sourceDir, f)
            absoluteDestDir = join(destDir, f)
            if isfile(absoluteSourceDir):
                logging.debug("file: " + str(absoluteSourceDir))
                copyfile(absoluteSourceDir, absoluteDestDir)
            elif not ignoreFrozenDirectories or f not in self.directoriesKeptInFrozen:
                logging.debug("dir:  " + str(absoluteSourceDir))
                mkdir(absoluteDestDir)
                self.copyRecursive(absoluteSourceDir, absoluteDestDir)

    def finalize(self):
        # create md5sum file for package identification
        folderMd5 = md5folder(self.defrostFolderPath)
        contents = 'md5sum="{}"'.format(folderMd5)
        writeToFile(join(self.defrostFolderPath, "package_md5sum.py"), contents)

        # add microwave code responsible to defrost appropriate code upon pycom's first run after update
        microwave_file = "microwave.py"
        target_file = join(self.defrostFolderPath, microwave_file)
        fileContents = readFromFile(join("aux_files", microwave_file))
        fileContents = fileContents.replace('/flash/package.md5', join(self.flashRootFolder, 'package.md5'))

        # default: zlib enabled
        if not self.enableZlibCompression:
            fileContents = fileContents.replace('enableZlibCompression = True', 'enableZlibCompression = False')

        writeToFile(target_file, fileContents)

        # add call to _main that detects package changes and calls defrosting after
        # a firmware flash
        main_file = "_append_to_boot.py"
        target_file = join(self.baseDestDir, main_file)
        fileContents = readFromFile(join("aux_files", main_file))
        fileContents = fileContents.replace('/flash/package.md5', join(self.flashRootFolder, 'package.md5'))
        writeToFile(target_file, fileContents)

    def finalize_package(self):
        # create md5sum file for package identification
        folderMd5 = md5folder(self.baseDestDir)
        contents = 'md5sum="{}"'.format(folderMd5)
        writeToFile(join(self.baseDestDir, "package_md5sum.py"), contents)

        self.createTarFile(folderMd5, self.baseDestDir)

        main_file = "_apply_package.py"
        target_file = join(self.baseDestDir, main_file)
        fileContents = readFromFile(join("aux_files", main_file))
        fileContents = fileContents.replace('flashRootFolder = "/flash"', 'flashRootFolder="' + self.flashRootFolder + '"')
        writeToFile(target_file, fileContents)

    def createTarFile(self, file_name, path):
        import tarfile
        cwd = os.getcwd()
        os.chdir(path)
        tar_file_name = "{}.tar".format(file_name)
        files_to_include_in_tar = listdir(path)
        tar = tarfile.open(tar_file_name, "w")
        to_delete = []
        for f in files_to_include_in_tar:
            tar.add(f)
            to_delete.append(f)
        tar.close()

        removeContents(path, to_delete)

        if self.enableZlibCompression:
            try:
                # try to compress file
                import zlib
                logging.debug("compressing file...")
                bytes = zlib.compress(readFromFile(tar_file_name, True), 4)
                crc = zlib.crc32(bytes) & 0xffffffff
                # zlib 8 header bytes + data + crc 4 bytes
                bytes = b'\x1f\x8b\x08\x00\x00\x00\x00\x00' + bytes + crc.to_bytes(length=4, byteorder='big')
                if writeToFile("{}.gz".format(tar_file_name), bytes, True):
                    removeFile(tar_file_name)
            except Exception as e:
                logging.debug("Error comressing tar file {}.".format(tar_file_name))
                traceback.print_exc()
        os.chdir(cwd)

if __name__ == '__main__':
    from sys import argv

    Config.setupLogging(argv)

    if len(argv) < 3 or "-h" in argv or "--help" in argv:
        logging.error("Aborting: no proper args")
        logging.error("    python3 microfreezer.py <path-to-project> <path-to-output-folder>")
        quit()

    sourceDir = argv[-2]
    destDir = argv[-1]

    logging.debug("source: {}, destination: {}".format(sourceDir, destDir))

    freezer = MicroFreezer()

    if "--ota-package" in argv:
        freezer.run_package(sourceDir, destDir)
    else:
        freezer.run(sourceDir, destDir)
