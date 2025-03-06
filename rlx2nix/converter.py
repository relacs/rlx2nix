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
import odml
import logging
import pathlib
import subprocess
import numpy as np
import nixio as nix

from .config import ConfigFile
from .traces import EventTrace, RawTrace
from .stimuli import StimuliDat
from .util import parse_value, odml2nix, only_number
from .stimdescription import parse_stimulus_description

from IPython import embed


class Converter(object):

    def __init__(self, folder:pathlib.Path, output:pathlib.Path, force=False) -> None:
        if not folder.exists():
            logging.error("%s does not exist!", str(folder))
            raise ValueError("File not found error!")
        self._folder = folder
        self._output = output
        self._event_traces = None
        self._raw_traces = None
        self._raw_data_arrays = {}
        self._event_data_arrays = {}
        self._stimuli_dat = None
        self._force = force
        self._nixfile = None
        self._block = None
        self._repro_tags = {}
        self._stimulus_mtags = {}
        self.preflight()

    def preflight(self):
        logging.debug("Pre-checking folder %s!", str(self._folder))
        self.check_output()
        self.check_folder()
        logging.debug("Pre-checking done.")

    def check_output(self):
        logging.debug("Checking output name: %s!", str(self._output))
        if self._output.exists():
            logging.warning("Output file name %s already exists!", str(self._output))
            if self._force:
                logging.warning("... force flag is set %s, going to overwrite!", str(self._force))
            else:
                logging.error("Force flag is not set (%s), abort!", str(self._force))
                raise ValueError(f"Output file {self._output} already exists! If you want to overwrite it use the --force flag.")
        logging.debug("... ok!")

        return True

    def unzip(self, tracename):
        if os.path.exists(tracename):
            logging.debug("... unzipping: %s", str(tracename))
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
        logging.debug("Checking for raw traces!")
        raw_traces = sorted(self._folder.glob("trace-*.raw*"))
        for rt in raw_traces:
            if ".gz" in rt.suffix and rt.with_suffix(".raw") not in raw_traces:
                self.unzip(rt)

        raw_traces = sorted(self._folder.glob("trace*.raw"))
        logging.debug("Found %i raw traces. %s", len(raw_traces), str([t.name for t in raw_traces]))
        return raw_traces

    def find_event_traces(self):
        logging.debug("Discovering event traces!")
        traces = sorted(self._folder.glob("*-events.dat"))
        logging.debug("Found %i event traces. %s", len(traces), str(t.name for t in traces))
        return traces

    def find_config_file(self):
        config = self._folder / pathlib.Path("relacs.cfg")
        if not config.exists():
            logging.error("Config file not found! %s", str(config))
            raise ValueError(f"No relacs.cfg file found in {self._folder}!")
        configuration = ConfigFile(config)
        return configuration

    def find_info(self):
        infofile = self._folder / pathlib.Path("info.dat")
        if not infofile.exists():
            logging.error("Info file not found! %s", str(infofile))
            raise ValueError(f"No info file found in {self._folder}!")
        return True

    def read_info_file(self):
        def looks_like_oldstyle(filename):
            recording_found = False
            with open(filename, 'r') as f:
                for l in f:
                    if "# Recording" in l:
                        recording_found = True
                        oldtyle = not l.strip().endswith(":")
                        break
            if not recording_found:
                logging.error(f"Conversion failed due to broken info file! {filename}")
                raise ValueError("Recording section not found in info file {filename}.")
            return oldtyle

        filename = os.path.join(self._folder, "info.dat")
        oldstyle = looks_like_oldstyle(filename)
        info = {}
        logging.info("Reading info file....")
        try:
            with open(filename, 'r') as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            print("UnicodeDecodeError, Replacing experimenter...")
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
        logging.info("Reading channel configuration ...")
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
        logging.debug("Scanning for stimuli.dat file!")
        stimfile = self._folder / pathlib.Path("stimuli.dat")
        if not stimfile.exists():
            logging.error("Stimuli.dat file not found! Abort!")
            raise ValueError("No stimuli.dat file found!")

    def find_stimulus_descriptions(self):
        logging.debug("Scanning for stimulus-descriptions.dat!")
        filename = self._folder / pathlib.Path("stimulus-descriptions.dat")
        if not filename.exists():
            logging.warning("Stimulus descriptions file %s does not exist!", filename.name)
            return False
        return True

    def check_folder(self):
        logging.debug("Checking folder structure: ...")
        self._raw_traces, self._event_traces = self.find_traces()
        self.find_info()
        logging.debug("Found info file!")
        self.find_stimulus_info()
        logging.debug("Found stimulus information!")
        stim_descriptions_found = self.find_stimulus_descriptions()
        if stim_descriptions_found:
            logging.debug("Found stimulus descriptions!")
        else:
            logging.debug("Did not find stimulus descriptions!")
        return True

    def convert_dataset_info(self, metadata, parent_section=None):
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
                    self.convert_dataset_info(metadata[k], sec)
                else:  # is property
                    value, unit = parse_value(metadata[k])
                    if value is None:
                        continue
                    if isinstance(value, str):
                        value = split_list(value)
                    p = parent_section.create_property(k, value)
                    if unit is not None:
                        p.unit = unit

    def open_nix_file(self):
        info = self.read_info_file()
        logging.info(f"Creating output file {self._output} ...")
        self._nixfile = nix.File.open(self._output, nix.FileMode.Overwrite)
        dataset_name = os.path.split(self._output)[-1].strip(".nix")

        self._block = self._nixfile.create_block(dataset_name, "relacs.recording")
        sec = self._nixfile.create_section(dataset_name, "relacs.recording")
        self._block.metadata = sec
        sec.create_property("relacs-nix version", 1.1)
        self.convert_dataset_info(info, sec)

    def convert_raw_traces(self, channel_config):
        logging.info("Converting raw traces, this may take a little while...")

        for rt in self._raw_traces:
            logging.info(f"... trace {rt._trace_no}: {rt.name}")
            data = np.fromfile(self._folder / pathlib.Path(rt.filename), dtype=np.float32)
            da = self._block.create_data_array(rt.name, f"relacs.data.sampled.{rt.name}", dtype=nix.DataType.Float, data=data)
            da.unit = channel_config[rt._trace_no]["unit"]
            si = float(channel_config[rt._trace_no]["sampling interval"][:-2]) / 1000.
            da.append_sampled_dimension(si, unit="s")
            self._raw_data_arrays[rt] = da

    def convert_event_traces(self):

        def read_event_data(filename):
            logging.info(f"... reading event times from file {filename}...")
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
            da = self._block.create_data_array(et.name, f"relacs.data.events.{et.name}", data=event_times)
            da.unit = "s"
            da.append_range_dimension_using_self()
            da.definition = f"Events detected in {et.inputtrace}"
            self._event_data_arrays[et] = da

    def convert_stimuli(self):
        def stimulus_descriptions(repro_name, reprorun, sampleinterval): 
            def skip_first_index(signals):
                skip = True
                for s in signals:
                    skip = skip and s.data[0].strip() == "-"
                return skip

            def find_active_signal(signals, stimulus_no):
                for i, s in enumerate(signals):
                    if s.data[stimulus_no].strip() != "-":
                        return i

            def parse_parameter(parameter_str):
                props = []
                if parameter_str.strip().startswith("\""):
                    parameter_str = parameter_str[1:-1]
                parts = parameter_str.split(",")
                for p in parts:
                    name = p.split(":")[0].strip()
                    value_str = p.split(":")[-1].strip()
                    value, unit = parse_value(value_str)
                    props.append(odml.Property(name=name, value=value, unit=unit))
                return props

            stimuli = []
            stimulus_columns = reprorun.table["stimulus"]
            signals = stimulus_columns.columns_by_name("signal")
            skip_first  = skip_first_index(signals)
            index_col = reprorun.table.find_column(1)
            abstimes = stimulus_columns.columns_by_name("time")[0]
            delays = stimulus_columns.columns_by_name("delay")[0]
            durations = stimulus_columns.columns_by_name("duration")
            amplitudes = stimulus_columns.columns_by_name("amplitude")
            if len(amplitudes) == 0: # this is an attempt for very old pre 2011 files.
                amplitudes = stimulus_columns.columns_by_name("%6.3f")
                
            parameters = stimulus_columns.columns_by_name("parameter")
            for i in range(0 if not skip_first else 1, len(index_col)):
                start_time = index_col[i] * sampleinterval
                active = find_active_signal(signals, i)
                characteristics = odml.Section(f"{repro_name}_{i}")
                characteristics.create_property("signal", signals[active].data[i])
                p = characteristics.create_property("start_time", start_time)
                p.unit = "s"
                dur = float(durations[active].data[i]) / (1000 if durations[active].type_or_unit == "ms" else 1)
                p = characteristics.create_property("duration", dur)
                p.unit = "s"
                p = characteristics.create_property("amplitude", float(amplitudes[active].data[i]))
                p.unit = amplitudes[active].type_or_unit
                d = float(delays.data[i]) / (1000 if delays.type_or_unit == "ms" else 1)
                p = characteristics.create_property("delay", d)
                p.unit = "s"
                at = float(abstimes.data[i]) / (1000 if abstimes.type_or_unit == "ms" else 1)
                p = characteristics.create_property("abs_time", at)
                p.unit = "s"
                characteristics.create_property("repro_tag_id", self._repro_tags[repro_name].id)
                if len(parameters) > 0:
                    params = parse_parameter(parameters[active].data[i])
                    for p in params:
                        characteristics.append(p)
                stimuli.append(characteristics)
            return stimuli

        def stimuli(sampleinterval):
            stims = {}
            counter = {}
            stim_metadata = parse_stimulus_description(os.path.join(self._folder, "stimulus-descriptions.dat"))
            for rr in self._stimuli_dat.repro_runs:
                if rr is None or rr.name is None:
                    print(rr)
                    continue
                if rr.name in counter:
                    counter[rr.name] += 1
                else:
                    counter[rr.name] = 1
                if not rr.valid:
                    continue
                if "BaselineActivity" in rr.name:
                    continue  # there are no stimulus presented during baseline
                repro_name = f"{rr.name}_{counter[rr.name]}"
                stims[repro_name] = stimulus_descriptions(repro_name, rr, sampleinterval)
                
            return stims, stim_metadata

        def store_stimuli(stims, stim_metadata):
            def store_features(signal, features):
                excluded_feats = ["start_time", "duration", "signal"]
                fixed_feats = ["abs_time", "amplitude", "repro_tag_id"]
                feats = {}
                for i, feat in enumerate(features):
                    for p in feat:
                        if p.name in excluded_feats:
                            continue
                        if p.name not in feats:
                            if p.dtype == "string":
                                feats[p.name] = np.empty(len(features), dtype=object)
                                feats[p.name][i] = p.values[0]
                            else:
                                feats[p.name] = np.empty(len(features))
                        else:
                            feats[p.name][i] = p.values[0]
                for key in feats.keys():
                    feat_name = f"{signal}_{key}"
                    feat_type = f"relacs.feature.{key if key in fixed_feats else 'mutable'}"
                    mtag = self._stimulus_mtags[signal]
                    shape = (len(feats[key]), 1)
                    data = np.reshape(feats[key], shape)
                    dtype = nix.DataType.String if data.dtype == object else nix.DataType.Float
                    feature_da = self._block.create_data_array(feat_name, feat_type, 
                                                                shape= shape, dtype=dtype,
                                                                data=data)
                    feature_da.append_set_dimension()
                    mtag.create_feature(feature_da, nix.LinkType.Indexed)
                return None

            unique_signals = []
            signal_counts = {}
            signal_starts = {}
            signal_durations = {}
            signal_features = {}
            for repro_run in stims:
                for stim in stims[repro_run]:
                    signal = stim.props["signal"].values[0]
                    if signal not in unique_signals:
                        unique_signals.append(signal)
                        signal_counts[signal] = 1
                        signal_starts[signal] = [stim.props["start_time"].values[0]]
                        signal_durations[signal] = [stim.props["duration"].values[0]]
                        signal_features[signal] = [stim]
                    else:
                        signal_starts[signal].append(stim.props["start_time"].values[0])
                        signal_durations[signal].append(stim.props["duration"].values[0])
                        signal_counts[signal] += 1
                        signal_features[signal].append(stim)

            excluded_refs = ["restart", "recording", "stimulus"]
            for signal in unique_signals:
                positions = self._block.create_data_array(f"{signal}_onset_times", "relacs.stimulus.onset",
                                                          data=np.atleast_2d(signal_starts[signal]).T)
                positions.append_set_dimension()

                extents = self._block.create_data_array(f"{signal}_durations", "relacs.stimulus.duration",
                                                          data=np.atleast_2d(signal_durations[signal]).T)
                extents.append_set_dimension()

                mtag = self._block.create_multi_tag(signal, "relacs.stimulus.segment", positions=positions, 
                                                    extents=extents)
                self._stimulus_mtags[signal] = mtag
                for et in self._event_data_arrays:
                    if et not in excluded_refs:
                        mtag.references.append(self._event_data_arrays[et])
                for rt in self._raw_data_arrays:
                    mtag.references.append(self._raw_data_arrays[rt])

                if stim_metadata is not None and signal in stim_metadata.sections:
                    metadata = stim_metadata[signal]
                    mtag.metadata = self._nixfile.create_section(mtag.name, "relacs.stimulus")
                    odml2nix(metadata, mtag.metadata)
                store_features(signal, signal_features[signal])

            return None

        logging.info("Converting stimuli...")
        sampleinterval = self._stimuli_dat.input_settings.props["sample interval1"].values[0] /1000
        stims, metadata = stimuli(sampleinterval)
        store_stimuli(stims, metadata)

        return

    def convert_repro_runs(self):
        def repro_times(reprorun, sampleinterval):
            if reprorun.name is None:
                return None, None
            if not reprorun.valid:
                return None, None
            index_col = reprorun.table.find_column(1)
            if len(index_col) == 0:
                return None, None

            stimulus_grp = reprorun.table["stimulus"]
            signals = stimulus_grp.columns_by_name("signal")
            is_init = np.any(np.array([s[0] for s in signals], dtype=object) == "init")
            delay_cols = stimulus_grp.columns_by_name("delay")
            delay = 0.0 if (len(delay_cols) == 0 or is_init) else delay_cols[0][0]
            start_time = index_col[0] * sampleinterval - delay / 1000.

            duration_cols = stimulus_grp.columns_by_name("duration")
            duration = 0.0
            if "BaselineActivity" in reprorun.name:
                duration = 0.0
                end_time = start_time
            else:
                for d in duration_cols:
                    dur = d[-1]
                    if isinstance(dur, (int, float)):
                        duration = dur / 1000
                        break
                    elif isinstance(dur, str) and only_number.search(dur) is not None:
                        duration = float(dur) / 1000
                        break
                end_time = index_col[-1] * sampleinterval + duration
            logging.debug("Repro %s from %.3f to %.3fs", reprorun.name, start_time, end_time)
            return start_time, end_time

        def repro_runs():
            repro_names = []
            repro_starts = []
            repro_ends = []
            repro_durations = []
            repro_metadata = []
            sample_interval = self._stimuli_dat.input_settings.props["sample interval1"].values[0] / 1000
            counter = {}
            for i, rr in enumerate(self._stimuli_dat.repro_runs):
                if rr.name in counter:
                    counter[rr.name] += 1
                else:
                    counter[rr.name] = 1
                if not rr.valid:
                    start, end = None, None
                    if "baselineactivity" in rr.name.lower():
                        logging.info("BaselineActivity run (Repro No %i) is incomplete/invalid, trying to rescue..", i)
                        if i == 0:
                            start = 0.0
                        else:
                            _, start = repro_times(self._stimuli_dat.repro_runs[i-1], sample_interval)

                        if i < len(self._stimuli_dat.repro_runs)-1:
                            end, _ = repro_times(self._stimuli_dat.repro_runs[i+1], sample_interval)
                        if start is None or end is None:
                            logging.warning("Rescue of BaselineActivity (Repro No %i) failed, estimated start or end time are invalid!", i)
                            continue
                        start += 1.0
                        end -= 1.0
                        if start >= end:
                            logging.warning("Rescue of BaselineActivity  (Repro No %i) failed, estimated interval is too short/invalid!", i)
                            continue
                        logging.info("BaselineActivity run (Repro No %i) succeeded! Estimated interval: %.3f --> %.3f s.",
                                     i, start, end)
                    else:
                        continue
                else:
                    start, end = repro_times(rr, sample_interval)
                if start is None:
                    logging.error("RePro run: %s has no start/stop entries! It is ignored!", rr.name)
                    continue

                repro_names.append(f"{rr.name}_{counter[rr.name]}")

                repro_starts.append(start)
                repro_durations.append(end - start)
                repro_ends.append(end)
                repro_metadata.append(rr.metadata)

            for i, (start, end , duration) in enumerate(zip(repro_starts, repro_ends, repro_durations)):
                logging.debug("Duration %.3f for repro %s and %i < %i",
                              duration, repro_names[i], i, len(repro_starts)-1) 
                if duration < sample_interval and i < len(repro_starts) -1:
                    repro_durations[i] = repro_starts[i+1] - start
                    logging.debug("... new duration: %.3f", repro_durations[i])
                    repro_ends[i] = repro_starts[i+1]

            return repro_names, repro_metadata, repro_starts, repro_durations

        def store_repro_runs(repro_names, repro_metadata, start_times, durations):
            excluded_refs = ["restart", "recording", "stimulus"]
            for name, metadata, start, duration in zip(repro_names, repro_metadata, start_times, durations):
                logging.debug("... storing %s which ran from %.3f to %.3fs.", name, start, start+ duration)
                tag = self._block.create_tag(name, "relacs.repro_run", position=[start])
                tag.extent = [duration]
                for et in self._event_data_arrays:
                    if et not in excluded_refs:
                        tag.references.append(self._event_data_arrays[et])
                for rt in self._raw_data_arrays:
                    tag.references.append(self._raw_data_arrays[rt])
                tag.metadata = self._nixfile.create_section(name, "relacs.repro")
                odml2nix(metadata, tag.metadata)
                self._repro_tags[name] = tag

        logging.info("Converting RePro runs...")
        names, metadata, starts, durations = repro_runs()
        store_repro_runs(names, metadata, starts, durations)

    def convert(self):
        logging.info("Converting dataset %s to nix file %s!", self._folder, self._output)

        channel_config = self.read_channel_config()
        self.open_nix_file()
        self.convert_raw_traces(channel_config)
        self.convert_event_traces()
        self._stimuli_dat = StimuliDat(os.path.join(self._folder, "stimuli.dat"))
        self.convert_repro_runs()
        self.convert_stimuli()
        self._nixfile.close()
        logging.info("Conversion of dataset %s to nix file %s finished!", self._folder, self._output)
