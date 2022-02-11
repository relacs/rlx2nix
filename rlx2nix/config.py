# -*- coding: utf-8 -*-
# Copyright © 2022, Neuroethology Lab Uni Tuebingen
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted under the terms of the BSD License. See
# LICENSE file in the root of the Project.

from http.client import LineTooLong
from optparse import Values
import os
from selectors import EpollSelector
import odml
import numpy as np
import enum

from collections import OrderedDict
from IPython import embed


class ConfigFormat(enum.Enum):
    old = 0
    new = 1


class ConfigFile(object):
    """Handling of configuration parameter.
    Configuration parameter have a name (key), a value, a unit and a
    description. New parameter can be added with the add() function.
    Configuration parameter can be further structured in the
    configuration file by inserting section titles via add_section().
    The triple value, unit, description can be retrieved via the name
    of a parameter using the [] operator.
    The value of a configuration parameter is retrieved by value()
    and set by set().
    Values of several configuration parameter can be mapped to
    new names with the map() function. The resulting dictionary can be
    passed as key-word arguments to a function.
    The configuration parameter can be written to a configuration file
    with dump() and loaded from a file with load() and load_files().
    """

    def __init__(self, orig=None):
        self._root = odml.Section(name="Root")
        self.cfg = OrderedDict()
        self.sections = dict()
        self.new_section = None
        if not orig is None:
            for k, v in orig.cfg.items():
                self.cfg[k] = list(v)
            for k, v in orig.sections.items():
                self.sections[k] = v
            self.new_section = None

            
    def __eq__(self, other):
        """Check whether the parameter and their values are the same.
        """
        return self.cfg == other.cfg

    def add(self, key, value, unit, description):
        """Add a new parameter to the configuration.
        The description of the parameter is a single string. Newline
        characters are intepreted as new paragraphs.
        Parameters
        ----------
        key: string
            Key of the parameter.
        value: any type
            Value of the parameter.
        unit: string
            Unit of the parameter value.
        description: string
            Textual description of the parameter.
        """
        # add a pending section:
        if self.new_section is not None:
            self.sections[key] = self.new_section
            self.new_section = None
        # add configuration parameter (4th element is default value):
        self.cfg[key] = [value, unit, description, value]

    def add_section(self, description):
        """Add a new section to the configuration.
        Parameters
        ----------
        description: string
            Textual description of the section
        """
        self.new_section = description

    def __contains__(self, key):
        """Check for existence of a configuration parameter.
        Parameters
        ----------
        key: string
            The name of the configuration parameter to be checked for.
        Returns
        -------
        contains: bool
            True if `key` specifies an existing configuration parameter.
        """
        return key in self.cfg

    def __getitem__(self, key):
        """Returns the list [value, unit, description]
        of the configuration parameter key.
        Parameters
        ----------
        key: string
            Key of the configuration parameter.
        Returns
        -------
        value: any type
            Value of the configuraion parameter.
        unit: string
            Unit of the configuraion parameter.
        description: string
            Description of the configuraion parameter.
        """
        return self.cfg[key]

    def value(self, key):
        """Returns the value of the configuration parameter defined by key.
        Parameters
        ----------
        key: string
            Key of the configuration parameter.
        Returns
        -------
        value: any type
            Value of the configuraion parameter.
        """
        return self.cfg[key][0]

    def set(self, key, value):
        """Set the value of the configuration parameter defined by key.
        Parameters
        ----------
        key: string
            Key of the configuration parameter.
        value: any type
            The new value.
        Raises
        ------
        IndexError:
            If key does not exist.
        """
        if not key in self.cfg:
            raise IndexError('Key %s does not exist' % key)
        self.cfg[key][0] = value

    def __delitem__(self, key):
        """Remove an entry from the configuration.
        Parameters
        ----------
        key: string
            Key of the configuration parameter to be removed.
        """
        if key in self.sections:
            sec = self.sections.pop(key)
            keys = list(self.cfg.keys())
            inx = keys.index(key)+1
            if inx < len(keys):
                next_key = keys[inx]
                if not next_key in self.sections:
                    self.sections[next_key] = sec
        del self.cfg[key]

    def map(self, mapping):
        """Map the values of the configuration onto new names.
        Use this function to generate key-word arguments
        that can be passed on to functions.
        Parameters
        ----------
        mapping: dict
            Dictionary with its keys being the new names
            and its values being the parameter names of the configuration.
        Returns
        -------
        a: dict
            A dictionary with the keys of mapping
            and the corresponding values retrieved from the configuration
            using the values from mapping.
        """
        a = {}
        for dest, src in mapping.items():
            if src in self.cfg:
                a[dest] = self.value(src)
        return a

    def write(self, stream, header=None, diff_only=False, maxline=60, comments=True):
        """Pretty print configuration into stream.
        The description of a configuration parameter is printed out
        right before its key-value pair with an initial comment
        character ('#').  
        Section titles get two comment characters prependend ('##').
        Lines are folded if the character count of parameter
        descriptions or section title exceeds maxline.
        
        A header can be printed initially. This is a simple string that is
        formatted like the section titles.
        Parameters
        ----------
        stream:
            Stream for writing the configuration.
        header: string
            A string that is written as an introductory comment into the file.
        diff_only: bool
            If true write out only those parameters whose value differs from their default.
        maxline: int
            Maximum number of characters that fit into a line.
        comments: boolean
            Print out descriptions as comments if True.
        """

        def write_comment(stream, comment, maxline, cs):
            # format comment:
            if len(comment) > 0:
                for line in comment.split('\n'):
                    stream.write(cs + ' ')
                    cc = len(cs) + 1  # character count
                    for w in line.strip().split(' '):
                        # line too long?
                        if cc + len(w) > maxline:
                            stream.write('\n' + cs + ' ')
                            cc = len(cs) + 1
                        stream.write(w + ' ')
                        cc += len(w) + 1
                    stream.write('\n')

        # write header:
        First = True
        if comments and not header is None:
            write_comment(stream, header, maxline, '##')
            First = False
        # get length of longest key:
        maxkey = 0
        for key in self.cfg.keys():
            if maxkey < len(key):
                maxkey = len(key)
        # write out parameter:
        section = ''
        for key, v in self.cfg.items():
            # possible section entry:
            if comments and key in self.sections:
                section = self.sections[key]

            # get value, unit, and comment from v:
            val = None
            unit = ''
            comment = ''
            differs = False
            if hasattr(v, '__len__') and (not isinstance(v, str)):
                val = v[0]
                if len(v) > 1 and len(v[1]) > 0:
                    unit = ' ' + v[1]
                if len(v) > 2:
                    comment = v[2]
                if len(v) > 3:
                    differs = (val != v[3])
            else:
                val = v

            # only write parameter whose value differs:
            if diff_only and not differs:
                continue

            # write out section
            if len(section) > 0:
                if not First:
                    stream.write('\n\n')
                write_comment(stream, section, maxline, '##')
                section = ''
                First = False
            
            # write key-value pair:
            if comments :
                stream.write('\n')
                write_comment(stream, comment, maxline, '#')
            stream.write('{key:<{width}s}: {val}{unit:s}\n'.format(
                key=key, width=maxkey, val=val, unit=unit))
            First = False

    def dump(self, filename, header=None, diff_only=False, maxline=60, comments=True):
        """Pretty print configuration into file.
        See write() for more details.
        Parameters
        ----------
        filename: string
            Name of the file for writing the configuration.
        """
        with open(filename, 'w') as f:
            self.write(f, header, diff_only, maxline, comments)

    def empty_or_comment(self, line):
        return len(line.strip()) == 0 or line[0] == '#'

    def looks_like_property(self, line, style=ConfigFormat.old):
        if style == ConfigFormat.old:
            result = ":" in line
        else:
            result = ":" in line and len(line.strip().split(": ")) > 1
        return result

    def looks_like_section(self, line, style=ConfigFormat.old):
        return not self.empty_or_comment(line) and not self.looks_like_property(line, style)

    def guess_indentation(self, filename, style=ConfigFormat.old):
        indentations = set()
        with open(filename, 'r') as f:
            for line in f:
                if self.looks_like_section(line, style):
                    indentations.add(len(line) - len(line.lstrip(" ")))
        indentations = sorted(list(indentations))
        if len(indentations) > 2:
            indent = np.unique(np.diff(np.array(indentations)))
            if len(indent) > 1:
                raise ValueError(f"Indentation levels inconsistent! {indent}")
        elif len(indentations) == 2:
            indent = indentations[-1] - indentations[0]
        else:
            indent = 1

        return indent

    def guess_file_format(self, filename):
        with open(filename, 'r') as f:
            for line in f:
                if self.empty_or_comment(line):
                    continue
                if '*' not in line and ':' not in line:
                    return ConfigFormat.old
        return ConfigFormat.new

    def parse_value(self, line, style=ConfigFormat.old):
        values = []
        unit = ""  # FIXME This can/should be improved, if needed!
        if style == ConfigFormat.old:
            list_sep = "|"
            if list_sep in line:
                values = line.strip().split(list_sep)
            else:
                values = line.strip()
        else:
            list_sep = ","
            if line.startswith("[") and "]" in line:
                values = line[1:line.index("]")].split(list_sep)
            else:
                values = line.strip()

        return values, unit

    def parse_property(self, line, style=ConfigFormat.old):
        key, val = line.split(': ', 1)
        key = key.strip()
        val = val.strip()
        values, unit = self.parse_value(val, style)
        return key, values, unit

    def read_config_file(self, filename, indent=2, format=ConfigFormat.old):
        current_section = self._root
        current_level = 0
        with open(filename, 'r') as f:
            for line in f:
                # do not process empty lines and comments:
                if self.empty_or_comment(line):
                    continue

                if self.looks_like_section(line, format):  # this line starts a section
                    if "-" * 8 in line:
                        line = line.replace("-","").strip()
                    new_level = (len(line) - len(line.lstrip(" "))) // indent + 1
                    line = line.strip().strip("*")
                    line = line.strip(":")
                    if new_level == current_level and new_level > 0:
                        current_section = current_section.parent
                    elif new_level < current_level:
                        level_diff = current_level - new_level + 1
                        while level_diff > 0:
                            current_section = current_section.parent
                            level_diff -= 1
                    print(f"new section {line} in {current_section.name}")
                    current_section = current_section.create_section(name=line)
                    current_level = new_level
                    continue

                if self.looks_like_property(line, format):
                    key, values, unit = self.parse_property(line, format)
                    print(f"\tadd {key} to section {current_section.name}!")
                    p = current_section.create_property(name=key, values=values)
                    if unit is not None and len(unit) > 0:
                        p.unit = unit

    def load(self, filename):
        if not os.path.exists(filename):
            raise ValueError(f"File {filename} does not exist!")

        format = self.guess_file_format(filename)
        indentation = self.guess_indentation(filename, format)
        self.read_config_file(filename, indentation, format)


if __name__ == "__main__":
    
    print("Checking configfile module ...")
    print('')

    # cfg = ConfigFile()
    # cfg.add_section('Power spectrum:')
    # cfg.add('nfft', 256, '', 'Number of data poinst for fourier transform.')
    # cfg.add('windows', 4, '', 'Number of windows on which power spectra are computed.')
    # cfg.add_section('Peaks:')
    # cfg.add('threshold', 20.0, 'dB', 'Threshold for peak detection.')
    # cfg.add('deltaf', 10.0, 'Hz', 'Minimum distance between peaks.')
    # cfg.write(sys.stdout)
    # print('')

    # del cfg['nfft']
    # del cfg['windows']
    # cfg.write(sys.stdout)
    cfg = ConfigFile()
    cfg.load("/data/invivo/2021-05-14-ac-invivo-2/relacs.cfg")
    #cfg.load("../2012-03-23-ae-invivo-1/relacs.cfg")
    embed()
