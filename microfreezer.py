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
import getopt, sys

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

def isAnySubstringInString(substring_list, string):
    for substr in substring_list:
        if substr in string:
            return True
    return False


class MicroFreezer:
    def __init__(self, config_obj=None):
        self.config = config_obj if config_obj is not None else Config()
        self.excludeList = self.config.get("excludeList", [])
        self.directoriesKeptInFrozen = self.config.get("directoriesKeptInFrozen", [])
        self.enableZlibCompression = self.config.get("enableZlibCompression", True)
        self.minify = self.config.get("minify", False)
        self.minifyExcludeFolderList = self.config.get("minifyExcludeFolderList", [])
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
    def minifyAndReplaceFile(self, sourceFile, destFile):
        import python_minifier

        with open(sourceFile) as f:
            contents = python_minifier.minify(f.read(),
                                                remove_annotations=True,
                                                remove_pass=False,
                                                remove_literal_statements=True,
                                                combine_imports=True,
                                                hoist_literals=True,
                                                rename_locals=True,
                                                preserve_locals=None,
                                                rename_globals=False,
                                                preserve_globals=None,
                                                remove_object_base=False,
                                                convert_posargs_to_args=False,
                                                preserve_shebang=True)
        with open(destFile,"w") as fp:
             fp.writelines(contents)

    def convertFileToBase64(self, sourceFile, destFile):
        logging.debug("  [C]: " + str(sourceFile))
        tmp_file = None
        if self.minify and sourceFile.endswith(".py") and '/templ/' not in sourceFile:
            import uuid
            tmp_file = '/tmp/' + str(uuid.uuid1()) + ".py"
            self.minifyAndReplaceFile(sourceFile, tmp_file)
            sourceFile = tmp_file

        bytes = readFromFile(sourceFile, True)

        if self.minify and tmp_file is not None:
            try:
                import os
                #os.remove(tmp_file)
            except Exception as e:
                logging.exception(e, "Error deleting file [{}]".format(tmp_file))

        if self.enableZlibCompression:
            import zlib
            bytes = zlib.compress(bytes, 4)
        newFileName = join(self.defrostFolderPath, "base64_" + str(self.convertedFileNumber) + ".py")
        self.convertedFileNumber += 1
        contents = 'PATH="{}"\nDATA={}'.format(join(self.flashRootFolder, destFile), binascii.b2a_base64(bytes))
        writeToFile(newFileName, contents)

    def processFiles(self, currentPath=""):
        absoluteCurrentPath = join(self.baseSourceDir, currentPath)

        try:
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
        except Exception as e:
            logging.exception(e, "processFiles: Error processing file")

    def copyRecursive(self, sourceDir, destDir, ignoreFrozenDirectories=False):
        try:
            for f in listdir(sourceDir):
                if f in self.excludeList:
                    logging.debug("ignoring file: {}".format(f))
                    continue

                absoluteSourceDir = join(sourceDir, f)
                absoluteDestDir = join(destDir, f)
                if isfile(absoluteSourceDir):
                    if self.minify and absoluteSourceDir.endswith(".py") and not isAnySubstringInString(self.minifyExcludeFolderList, absoluteSourceDir):
                        logging.debug("file [M]: " + str(absoluteSourceDir))
                        self.minifyAndReplaceFile(absoluteSourceDir, absoluteDestDir)
                    else:
                        logging.debug("file: " + str(absoluteSourceDir))
                        copyfile(absoluteSourceDir, absoluteDestDir)
                elif not ignoreFrozenDirectories or f not in self.directoriesKeptInFrozen:
                    logging.debug("dir:  " + str(absoluteSourceDir))
                    mkdir(absoluteDestDir)
                    self.copyRecursive(absoluteSourceDir, absoluteDestDir)
        except Exception as e:
            logging.exception(e, "copyRecursive: Error processing file")

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

def showHelp():
    message = """usage:
    python3 microfreezer.py <options> <path-to-project> <path-to-output-folder>
or
    python3 microfreezer.py <options> -s <path-to-project> -d <path-to-output-folder>

Options and arguments:
-h, --help          : print this help message
-v, --verbose       : enable verbose logging messages
-c, --config        : explicitly specify configuration file path, if omitted "./config.json" will be used
-s, --source        : the path to the source directory of the project
-d, --destination   : the path to the destination folder where all the generated files will be placed
--ota-package       : generate OTA package instead, if omitted it will generate the files needed for micropython freezing
"""
    logging.error(message)
    quit()

if __name__ == '__main__':
    from sys import argv

    argumentList = sys.argv[1:]
    options = "hvc:s:d:"
    long_options = ["help", "verbose", "config=", "ota-package", "source=", "destination="]
    config_file = None
    is_ota_package = False
    is_verbose = False
    sourceDir = None
    destDir = None

    try:
        arguments, values = getopt.getopt(argumentList, options, long_options)

        sourceDir = argv[-2]
        destDir = argv[-1]

        for currentArgument, currentValue in arguments:
            if currentArgument in ("-c", "--config"):
                config_file = str(currentValue)
            elif currentArgument == "--ota-package":
                is_ota_package = True
            elif currentArgument in ("-v", "--verbose"):
                is_verbose = True
            elif currentArgument in ("-s", "--source"):
                sourceDir = str(currentValue)
            elif currentArgument in ("-d", "--destination"):
                destDir = str(currentValue)
            elif currentArgument in ("-h", "--help"):
                showHelp()

            if (not sourceDir or not destDir) and len(argv) >= 3:
                sourceDir = argv[-2]
                destDir = argv[-1]
            elif len(argv) < 3:
                raise getopt.error("not enough arguments provided")

    except getopt.error as err:
        # output error, and return with an error code
        logging.error(str(err))
        showHelp()

    Config.setupLogging(is_verbose)
    logging.info("using config file:" + str(config_file) if config_file else "default")
    config_obj = Config(config_file) if config_file is not None else Config()

    logging.debug("source: {}, destination: {}".format(sourceDir, destDir))

    freezer = MicroFreezer(config_obj)

    if is_ota_package:
        freezer.run_package(sourceDir, destDir)
    else:
        freezer.run(sourceDir, destDir)
