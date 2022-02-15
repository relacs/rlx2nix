# -*- coding: utf-8 -*-
# Copyright © 2022, Neuroethology Lab Uni Tuebingen
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted under the terms of the BSD License. See
# LICENSE file in the root of the Project.
import os
from .config import ConfigFile

from IPython import embed


class EventTrace(object):

    def __init__(self, filename, configuration) -> None:
        self._filename = filename
        self._name = os.path.split(self._filename)[-1].split("-events.dat")[0]
        self._inputtrace = None
        self._settings = None

        self._find_configuration(configuration)

    def _find_configuration(self, configuration):
        s = configuration._root.find_related("FilterDetectors")
        for sub in s:
            if self._name in sub.properties["name"][0].lower():
                self._inputtrace = sub.properties["inputtrace"][0]
                self._settings = sub

    @property
    def inputtrace(self):
        return self._inputtrace
    
    @property
    def name(self):
        return self._name
    
    @property
    def settings(self):
        return self._settings

    def __str__(self) -> str:
        s = f"Event trace {self.name}, mapped to input trace {self.inputtrace}"
        return s


class RawTrace(object):

    def __init__(self, filename, configuration):
        self._filename = os.path.split(filename)[-1]
        self._name = None
        self._settings = None
        self._trace_no = int(self.filename.split("-")[-1].split(".raw")[0])

        self._find_configuration(configuration)

    def _find_configuration(self, configuration):
        sec = configuration.find_section("input data") 
        self._name = sec.properties["inputtraceid"].values[self._trace_no -1]
        self._scale = float(sec.properties["inputtracescale"].values[self._trace_no -1])

    @property
    def inputtrace(self):
        return self._inputtrace

    @property
    def name(self):
        return self._name

    @property
    def filename(self):
        return self._filename

    @property
    def settings(self):
        return self._settings

    def __str__(self) -> str:
        s = f"Raw trace {self.filename}, mapped to signal tace number {self._trace_no}: {self.name}"
        return s