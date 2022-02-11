# -*- coding: utf-8 -*-
# Copyright © 2022, Neuroethology Lab Uni Tuebingen
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted under the terms of the BSD License. See
# LICENSE file in the root of the Project.
import os


class EventTrace(object):

    def __init__(self, dataset_folder) -> None:
        if not os.path.exists(dataset_folder):
            raise FileNotFoundError(f"Dataset does not exist at location {dataset_folder}!")
        self._name
        self._inputtrace
        self._settings
        self._folder = dataset_folder

