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
from shutil import copyfile
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


def readFromFile(source):
    try:
        f = open(source, "rb")
        contents = f.read()
        f.close()
        logging.debug("file [{}] read finished.".format(source))
        return contents
    except Exception as e:
        logging.debug("file [{}] read failed.".format(source))
        traceback.print_exc()
        return ""


def writeToFileBytes(destination, content):
    try:
        out_file = open(destination, "wb")
        out_file.write(content)
        out_file.close()
        logging.debug("file [{}] write finished.".format(destination))
        return True
    except Exception as e:
        logging.debug("file [{}] write failed.".format(destination))
        traceback.print_exc()
    return False


def writeToFile(destination, content):
    try:
        out_file = open(destination, "w")
        out_file.write(content)
        out_file.close()
        logging.debug("file [{}] write finished.".format(destination))
    except Exception as e:
        logging.debug("file [{}] write failed.".format(destination))
        traceback.print_exc()


def removeFile(directoryPath):
    try:
        os.remove(directoryPath)
        print("Removed file: {}".format(directoryPath))
    except OSError as e:
        print("remove file {} failed".format(directoryPath))


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


class MicroFreezer:
    def __init__(self, do_package):
        self.do_package = do_package
        self.config = Config()
        self.excludeList = self.config.get("excludeList", [])
        self.directoriesKeptInFrozen = self.config.get("directoriesKeptInFrozen", [])
        self.enableZlibCompression = self.config.get("enableZlibCompression", True)
        self.flashRootFolder = self.config.get("flashRootFolder", "/flash")

    def run(self, sourceDir, destDir):
        self.convertedFileNumber = 0
        self.baseSourceDir = sourceDir
        self.baseDestDir = destDir

        if self.do_package:
            self.baseDestDirCustom = destDir
            self.baseDestDirBase = destDir
            self.defrostFolderPath = join(destDir, "_todefrost_pack")
        else:
            self.baseDestDirCustom = join(destDir, "Custom")
            self.baseDestDirBase = join(destDir, "Base")
            self.defrostFolderPath = join(self.baseDestDirCustom, "_todefrost")
        mkdir(self.baseDestDir)
        mkdir(self.defrostFolderPath)
        mkdir(self.baseDestDirCustom)
        mkdir(self.baseDestDirBase)
        mkdir(self.defrostFolderPath)

        self.processFiles()
        self.finalize()

    def convertFileToBase64(self, sourceFile, destFile):
        logging.debug("  [C]: " + str(sourceFile))
        bytes = readFromFile(sourceFile)
        if self.enableZlibCompression:
            import zlib
            bytes = zlib.compress(bytes, 4)
        newFileName = join(self.defrostFolderPath, "base64_" + str(self.convertedFileNumber) + ".py")
        self.convertedFileNumber += 1
        contents = 'PATH="{}"\nDATA={}'.format(join(self.flashRootFolder, destFile), binascii.b2a_base64(bytes))
        writeToFile(newFileName, contents)

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
                    # Frozen folders are ignored during OTA package creation
                    if not self.do_package:
                        self.copyRecursive(absoluteSourceDir, self.baseDestDirCustom)
                else:
                    self.processFiles(join(currentPath, f))

    def copyRecursive(self, sourceDir, destDir):
        for f in listdir(sourceDir):
            if f in self.excludeList:
                logging.debug("ignoring file: {}".format(f))
                continue

            absoluteSourceDir = join(sourceDir, f)
            absoluteDestDir = join(destDir, f)
            if isfile(absoluteSourceDir):
                logging.debug("file: " + str(absoluteSourceDir))
                copyfile(absoluteSourceDir, absoluteDestDir)
            else:
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
        copyfile(join("aux_files", microwave_file), join(self.defrostFolderPath, microwave_file))

        # add call to _main that detects package changes and calls defrosting after
        # a firmware flash
        main_file = "_main.py"
        if self.do_package:
            main_file = "_apply_package.py"

        copyfile(join("aux_files", main_file), join(self.baseDestDirBase, main_file))

        if self.do_package:
            self.createTarFile(folderMd5)

    def createTarFile(self, md5):
        import tarfile
        os.chdir(self.baseDestDir)
        tar_file_name = "{}.tar".format(md5)
        tar = tarfile.open(tar_file_name, "w")
        tar.add("_todefrost_pack")
        tar.close()
        import shutil
        try:
            shutil.rmtree(self.defrostFolderPath)
        except OSError as e:
            print("Error: %s : %s" % (dir_path, e.strerror))

        try:
            # try to compress file
            import zlib
            print("compressing file...")
            bytes = zlib.compress(readFromFile(tar_file_name), 4)
            # zlib 8 header bytes
            bytes = b'\x1f\x8b\x08\x00\x00\x00\x00\x00' + bytes
            if writeToFileBytes("{}.gz".format(tar_file_name), bytes):
                removeFile(tar_file_name)
        except Exception as e:
            logging.debug("Error comressing tar file {}.".format(tar_file_name))
            traceback.print_exc()


if __name__ == '__main__':
    from sys import argv

    Config.setupLogging(argv)

    if len(argv) < 3 or "-h" in argv or "--help" in argv:
        logging.error("Aborting: no proper args")
        logging.error("    python3 microfreezer.py <path-to-project> <path-to-output-folder>")
        quit()

    do_package = False
    if "--ota-package" in argv:
        do_package = True

    sourceDir = argv[-2]
    destDir = argv[-1]

    logging.debug("source: {}, destination: {}".format(sourceDir, destDir))

    freezer = MicroFreezer(do_package)
    freezer.run(sourceDir, destDir)
