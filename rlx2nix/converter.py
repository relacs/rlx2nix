# -*- coding: utf-8 -*-
# Copyright © 2022, Neuroethology Lab Uni Tuebingen
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted under the terms of the BSD License. See
# LICENSE file in the root of the Project.

import os
import glob
import logging
import nixio as nix
import subprocess

from IPython import embed


class Converter(object):

    def __init__(self, folder_name, output_name, force=False) -> None:
        if not os.path.exists(folder_name):
            logging.error(f"{folder_name} does not exist!")
            raise ValueError("File not found error!")
        self._folder = folder_name
        self._output = output_name
        self._force = force
        self.preflight()

    def preflight(self):
        logging.debug(f"Pre-checking folder {self._folder}!")
        self.check_output()
        self.check_folder()
        logging.debug("Pre-checking done.")

    def check_output(self):
        logging.debug(f"Checking output name: {self._output}!")
        if os.path.exists(self._output):
            logging.debug(f"Output file name {self._output} already exists!")
            if self._force:
                logging.debug(f"... force flag is set {self._force}, going to overwrite!")
            else:
                logging.error(f"Force flag is not set ({self._force}), abort!")
                raise ValueError("Output file {self._output} already exists! If you want to overwrite it use the --force flag.")
        logging.debug(f"... ok!")

        return True

    def unzip(self, tracename):
        if os.path.exists(tracename):
            logging.debug(f"\tunzip: {tracename}")
            subprocess.check_call(["gunzip", tracename])

    def find_raw_traces(self):
        logging.debug(f"Checking for raw traces!")
        traces = sorted(glob.glob(os.path.join(self._folder, "trace-*.raw*")))
        for rt in traces:
            if rt.endswith(".gz") and rt.split(".gz")[0] not in traces:
                self.unzip(os.path.split(rt)[-1])
        
        traces = sorted(glob.glob(os.path.join(self._folder, "trace-*.raw")))
        logging.debug(f"Found {len(traces)} raw traces. {[os.path.split(t)[-1] for t in traces]}")

        return traces

    def find_event_traces(self):
        logging.debug("Discovering event traces!")
        traces = sorted(glob.glob(os.path.join(self._folder, "*-events.dat")))
        logging.debug(f"Found {len(traces)} event traces. {[os.path.split(t)[-1] for t in traces]}")
        return traces

    def find_info(self):
        info = None
        if not os.path.exists(os.path.join(self._folder, "info.dat")):
            logging.error("Found no info file!")
            raise ValueError(f"No info file found in {self._folder}!")
        else:
            # read_info_file(os.path.join(self._folder, "info.dat"))
            pass

        return info

    def find_stimulus_info(self):
        stimuli = None
        logging.debug("Scanning stimuli.dat file!")
        if not os.path.exists(os.path.join(self._folder, "stimuli.dat")):
            logging.error("Found no stimuli.dat file! Abort!")
            raise ValueError("No stimuli.dat file found!")

        return stimuli

    def check_folder(self):
        logging.debug("Checking folder structure: ...")
        raw_traces = self.find_raw_traces()
        event_traces = self.find_event_traces()
        info = self.find_info()
        logging.debug("Found info file!")
        stim_info = self.find_stimulus_info()
        logging.debug("Found stimulus information!")

    def convert(self):
        print("Convert!", self._folder)
