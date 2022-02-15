# -*- coding: utf-8 -*-
# Copyright © 2022, Neuroethology Lab Uni Tuebingen
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted under the terms of the BSD License. See
# LICENSE file in the root of the Project.
import re
import os
import glob
import logging
import subprocess
import numpy as np
import nixio as nix

from .config import ConfigFile
from .traces import EventTrace, RawTrace

from IPython import embed

units = ["mV", "sec", "min", "uS/cm", "C", "°C", "Hz", "cm", "mm", "um", "mg/l", "ul" "MOhm", "g"]
unit_pattern = {}
for unit in units:
    unit_pattern[unit] = re.compile(f"{unit}$", re.IGNORECASE|re.UNICODE)
only_number = re.compile("^([+-]?\\d+\\.?\\d+)$")
integer_number = re.compile("^[+-]?\\d+$")
number_and_unit = re.compile("^(^[+-]?\\d+\\.?\\d+)\\s?\\w+(/\\w+)?$")

class Converter(object):

    def __init__(self, folder_name, output_name, force=False) -> None:
        if not os.path.exists(folder_name):
            logging.error(f"{folder_name} does not exist!")
            raise ValueError("File not found error!")
        self._folder = folder_name
        self._output = output_name
        self._event_traces = None
        self._raw_traces = None
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
            logging.warn(f"Output file name {self._output} already exists!")
            if self._force:
                logging.warn(f"... force flag is set {self._force}, going to overwrite!")
            else:
                logging.error(f"Force flag is not set ({self._force}), abort!")
                raise ValueError("Output file {self._output} already exists! If you want to overwrite it use the --force flag.")
        logging.debug(f"... ok!")

        return True

    def unzip(self, tracename):
        if os.path.exists(tracename):
            logging.debug(f"\tunzip: {tracename}")
            subprocess.check_call(["gunzip", tracename])

    def find_traces(self):
        event_traces = []
        raw_traces = []

        configuration = self.find_config_file()
        for et in self.find_event_traces():
            event_traces.append(EventTrace(et, configuration))

        for rt in self.find_raw_traces():
            raw_traces.append(RawTrace(rt, configuration))

        return raw_traces, event_traces

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

    def find_config_file(self):
        if not os.path.exists(os.path.join(self._folder, "relacs.cfg")):
            logging.error("Found no info file!")
            raise ValueError(f"No relacs.cfg file found in {self._folder}!")
        configuration = ConfigFile(os.path.join(self._folder, "relacs.cfg"))
        return configuration

    def find_info(self):
        filename = os.path.join(self._folder, "info.dat")
        if not os.path.exists(filename):
            logging.error("Found no info file!")
            raise ValueError(f"No info file found in {self._folder}!")
        return True

    def read_info_file(self):
        def looks_like_oldstyle(filename):
            with open(filename, 'r') as f:
                for l in f:
                    if "# Recording" in l:
                        oldtyle = not l.strip().endswith(":")
                        break
            return oldtyle

        filename = os.path.join(self._folder, "info.dat")
        oldstyle = looks_like_oldstyle(filename)
        info = {}
        logging.info("Reading info file....")
        try:
            with open(filename, 'r') as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            logging.debug("Replacing experimenter...")
            command = r"sudo sed -i '/Experimenter/c\#       Experimenter: Anna Stoeckl' %s" % filename
            subprocess.check_call(command, shell=True)
            with open(filename, 'r') as f:
                lines = f.readlines()
        for l in lines:
            if not l.startswith("#"):
                continue
            l = l.strip("#").strip()
            if len(l) == 0:
                continue
            if oldstyle:
                if not ":" in l:   # subsection
                    sec = {}
                    info[l[:-1] if l.endswith(":") else l] = sec
                else:
                    parts = l.split(':')
                    sec[parts[0].strip()] = parts[1].strip('"').strip() if len(parts) > 1 else ""
            else:
                if l.endswith(":"):  # subsection
                    sec = {}
                    info[l[:-1] if l.endswith(":") else l] = sec
                else:
                    parts = l.split(': ')
                    sec[parts[0].strip()] = parts[1].strip('"').strip() if len(parts) > 1 else ""
        return info

    def read_channel_config(self):
        ids = [f"identifier{i}" for i in range(1, len(self._raw_traces)+1)]
        units = [f"unit{i}" for i in range(1, len(self._raw_traces)+1)]
        sampling_intervals = [f"sample interval{i}" for i in range(1, len(self._raw_traces)+1)]
        sampling_rates = [f"sampling rate{i}" for i in range(1, len(self._raw_traces)+1)]

        channel_config = {}
        for i in range(1, len(self._raw_traces)+1):
            channel_config[i] = {}
        with open(os.path.join(self._folder, "stimuli.dat")) as f:
            for line in f:
                if "#" in line:
                    line = line[1:]
                prop = line.strip().split(":")[0].strip()
                value = line.strip().split(":")[-1].strip()
                if prop in ids:
                    index = int(prop[-1])
                    channel_config[index]["identifier"] = value
                if prop in units:
                    index = int(prop[-1])
                    channel_config[index]["unit"] = value
                if prop in sampling_intervals:
                    index = int(prop[-1])
                    channel_config[index]["sampling interval"] = value
                if prop in sampling_rates:
                    index = int(prop[-1])
                    channel_config[index]["sampling rates"] = value

                if "analog output traces" in line:  # end of channel configuration, we are done here
                    break
        return channel_config

    def find_stimulus_info(self):
        logging.debug("Scanning stimuli.dat file!")
        if not os.path.exists(os.path.join(self._folder, "stimuli.dat")):
            logging.error("Found no stimuli.dat file! Abort!")
            raise ValueError("No stimuli.dat file found!")

    def check_folder(self):
        logging.debug("Checking folder structure: ...")
        self._raw_traces, self._event_traces = self.find_traces()
        self.find_info()
        logging.debug("Found info file!")
        self.find_stimulus_info()
        logging.debug("Found stimulus information!")
        return True

    def parse_value(self, value_str):
        value = None
        unit = None
        # check number
        if only_number.search(value_str) is not None:
            if integer_number.match(value_str) is not None:
                value = int(value_str)
            else:
                value = float(value_str)
        elif number_and_unit.search(value_str):
            for u in unit_pattern.keys():
                if unit_pattern[u].search(value_str) is not None:
                    unit = u
                    value_str = value_str.split(u)[0]
                    if integer_number.match(value_str):
                        value = int(value_str)
                    else:
                        value = float(value_str)
                    break
        else:
            value = value_str
        return value, unit

    def convert_metadata(self, metadata, nixfile, parent_section=None):
        def split_list(value_str):
            results = None
            if len(value_str) == 0:
                return " "
            if "|" in value_str:
                results = list(map(str.strip, value_str.split("|")))
            elif value_str[0] == "[" and "]" in value_str:
                results = list(map(str.strip, value_str[1:value_str.index("]")].split(', ')))
            else: 
                results = value_str
            return results

        if parent_section is not None:
            for k in metadata.keys():
                if isinstance(metadata[k], dict):
                    sec = parent_section.create_section(k, k.lower())
                    self.convert_metadata(metadata[k], nixfile, sec)
                else:  # is property
                    value, unit = self.parse_value(metadata[k])
                    if value is None:
                        continue
                    if isinstance(value, str):
                        value = split_list(value)
                    p = parent_section.create_property(k, value)
                    if unit is not None:
                        p.unit = unit

    def open_nix_file(self):
        info = self.read_info_file()
        nf = nix.File.open(self._output, nix.FileMode.Overwrite)
        dataset_name = os.path.split(self._output)[-1].strip(".nix")

        block = nf.create_block(dataset_name, "relacs.recording")
        sec = nf.create_section(dataset_name, "relacs.recording")
        block.metadata = sec
        sec.create_property("relacs-nix version", 1.1)
        self.convert_metadata(info, nf, sec)

        return nf

    def convert_raw_traces(self, nix_file, channel_config):
        logging.info("Converting raw traces, this may take a little while...")
        block = nix_file.blocks[0]
        for rt in self._raw_traces:
            logging.info(f"... trace {rt._trace_no}: {rt.name}")
            data = np.fromfile(os.path.join(self._folder, rt.filename), dtype=np.float32)
            da = block.create_data_array(rt.name, "relacs.data.sampled", dtype=nix.DataType.Float, data=data)
            da.unit = channel_config[rt._trace_no]["unit"]
            si = float(channel_config[rt._trace_no]["sampling interval"][:-2]) / 1000.
            da.append_sampled_dimension(si, unit="s")

    def convert_event_traces(self, block):

        def read_event_data(filename):
            logging.info(f"Reading event times from file {filename}...")
            times = []
            with open(filename, 'r') as f:
                for l in f:
                    if len(l.strip()) == 0 or "#" in l:
                        continue
                    times.append(float(l.strip().split()[0].strip()))

            return np.array(times)

        logging.info("Converting event traces...")
        for et in self._event_traces:
            logging.info(f"... trace {et.name}")
            event_times = read_event_data(et._filename)
            da = block.create_data_array(et.name, "relacs.data.events", data=event_times)
            da.unit = "s"
            da.append_range_dimension_using_self()
            da.definition = f"Events detected in {et.inputtrace}"


    def convert(self):
        logging.info("Converting dataset {self._folder} to nix file {self._output}!")
        channel_config = self.read_channel_config()
        logging.debug("Got channel configuration!")
        channel_config = self.read_channel_config()
        nf = self.open_nix_file()
        self.convert_raw_traces(nf, channel_config)
        self.convert_event_traces(nf.blocks[0])
        embed()
        nf.close()
        exit()
        nf.close()
