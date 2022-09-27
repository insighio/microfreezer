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

import json
import logging
from os import path


class Config():
    def __init__(self, config_file='config.json'):
        self.config_file_name = config_file
        self.app_config = {}
        self.loadConfiguration()

    def get(self, key, defaultValue=None):
        if key in self.app_config:
            return self.app_config[key]
        else:
            return defaultValue

    def loadConfiguration(self):
        # detect if the node is client or master
        filename = self.config_file_name

        with open(filename) as json_file:
            self.app_config = json.load(json_file)

    def setupLogging(is_verbose):
        logging_ready = False
        FORMATTER = "%(asctime)s: [%(levelname)s]: %(message)s"

        if is_verbose:
            logging.basicConfig(format=FORMATTER, level=logging.DEBUG)
            logging.debug("Debug logging: on")
        else:
            logging.basicConfig(
                format=FORMATTER, level=logging.INFO)
