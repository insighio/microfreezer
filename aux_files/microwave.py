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

import sys
import uzlib
import uos
import uerrno
import ubinascii


enableZlibCompression = True


def writeToFile(destination, content):
    try:
        out_file = open(destination, "w")
        out_file.write(content)
        out_file.close()
        print("file [{}] write finished.".format(destination))
    except Exception as e:
        print("file [{}] write failed.".format(destination))
        sys.print_exception(e)


def recursiveMkdir(absolutePath):
    pathParts = absolutePath.split("/")
    pathParts.pop()
    path = ""
    for i in range(1, len(pathParts)):
        path += "/" + pathParts[i]
        mkdir(path)


def mkdir(directoryPath):
    try:
        uos.mkdir(directoryPath)
        print("Made directory: {}".format(directoryPath))
    except OSError as e:
        if e.args[0] != uerrno.EEXIST:
            print("directory {} failed".format(directoryPath))
            sys.print_exception(e)


def remove(directoryPath):
    try:
        uos.remove(directoryPath)
        print("Removed file: {}".format(directoryPath))
    except OSError as e:
        print("remove file {} failed".format(directoryPath))


def defrost(defrost_module_name="_todefrost", delete_file_after_operation=False):
    file_index = 0
    module_found = True
    print("Starting defrosting...")
    while module_found:
        name = defrost_module_name + ".base64_" + str(file_index)
        file_name = "{}/base64_{}.py".format(defrost_module_name, str(file_index))
        print("Processing file: " + name)
        try:
            x = __import__(name, globals(), locals(), ['PATH', 'DATA'])
            recursiveMkdir(x.PATH)
            ascii_data = ubinascii.a2b_base64(x.DATA)
            if enableZlibCompression:
                ascii_data = uzlib.decompress(ascii_data)
            writeToFile(x.PATH, ascii_data)
            del x
            sys.modules.pop(name)
            print("    File: " + name + ", success")
            if delete_file_after_operation:
                remove(file_name)
            file_index += 1
        except Exception as e:
            sys.print_exception(e)
            module_found = False

    # in case any file gets properly defrosted, the file_index will increase,
    # so it is used as a quick way of assuming operation success
    if file_index > 0:
        from _todefrost import package_md5sum
        writeToFile("/flash/package.md5", package_md5sum.md5sum)

    print("Defrosting finished")
