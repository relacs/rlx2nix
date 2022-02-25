from multiprocessing.sharedctypes import Value
import os
import odml

from .config import ConfigFormat
from .util import parse_value


def looks_like_section(line, format):
    line = line.strip()
    if format == ConfigFormat.old:
        return line.split(":")[0] == "Stimulus"
    else:
        return len(line.split(":")[-1].strip()) == 0


def looks_like_oldstyle(filename):
    with open(filename, "r") as f:
        for l in f:
            if len(l.strip()) == 0:
                continue 
            if looks_like_section(l, ConfigFormat.new):
                return ConfigFormat.new
            elif looks_like_section(l, ConfigFormat.old):
                return ConfigFormat.old
    raise ValueError("Cannot guess the format!")


def parse_section(line, format):
    if not looks_like_section(line, format):
            raise ValueError("Line {line} does not not look like a section definition for format {format}!")
    name = ""
    type = "n.s."
    if format == ConfigFormat.old:
        name = line.split(": ")[-1].strip()
    else:
        name = line.split(":")[0].strip()
        if "(" in name and ")" in name:
            parts = name.split("(")
            name = parts[0].strip()
            if name.startswith("\"") and name.endswith("\""):
                name = name[1:-1]
            type = parts[-1].replace(")", "").strip()
            if "/" in type:
                type = type.replace("/", ".")
    return name, type


def parse_property(line):
    line = line.strip()
    parts = line.split(":")
    name = parts[0].strip()
    value_str = parts[-1].strip()
    value, unit = parse_value(value_str)

    return name, value, unit


def parse_stimulus_description(filename):
    if not os.path.exists(filename):
        return
    root = odml.Section("root")
    format = looks_like_oldstyle(filename)
    section = None
    with open(filename, "r") as f:
        for l in f:
            l = l.strip()
            if len(l) == 0:
                continue
            if looks_like_section(l, format):
                name, type = parse_section(l, format)
                section = root.create_section(name, type)
            else:
                n, v, u = parse_property(l)
                p = section.create_property(n, v)
                if len(u) > 0:
                    p.unit = u

    return root

