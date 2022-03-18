import re
import enum
import nixio as nix


class ValueType(enum.Enum):
    floating = 1
    integer = 2
    number_and_unit = 3
    string = 4


only_number = re.compile("^([+-]?\\d+\\.?\\d*)$")
integer_number = re.compile("^[+-]?\\d+$")
number_and_unit = re.compile("^(^[+-]?\\d*\\.?\\d*)\\s?\\w+%?(/\\w+)?$")

units = ["mV", "mV/cm", "sec","ms", "min", "uS/cm", "C", "°C", "Hz", "kHz", "cm", "mm", "um", "mg/l", "ul" "MOhm", "g", "%"]
unit_pattern = {}
for unit in units:
    unit_pattern[unit] = re.compile(f"^(^[+-]?\\d+\\.?\\d*)\\s?{unit}$", re.IGNORECASE|re.UNICODE)


def guess_value_type(value_str):
    if only_number.search(value_str) is not None:
        if integer_number.search(value_str) is not None:
            return ValueType.integer
        else:
            return ValueType.floating
    elif number_and_unit.search(value_str) is not None:
        return ValueType.number_and_unit
    else:
        return ValueType.string


def convert_value(val, val_type):
    if val_type == ValueType.integer:
        val = int(val)
    elif val_type == ValueType.floating:
        val = float(val)
    return val


def parse_value(value_str):
    value = value_str
    unit = ""
    vt = guess_value_type(value_str)
    if vt == ValueType.integer or vt == ValueType.floating:
        value = convert_value(value_str, vt)
    elif vt == ValueType.number_and_unit:
        for u in unit_pattern.keys():
            if unit_pattern[u].search(value_str) is not None:
                unit = u
                value_str = value_str.split(u)[0]
                vt = guess_value_type(value_str)
                value = convert_value(value_str, vt)
                break
    return value, unit


def odml2nix(odml_section, nix_section):
    for op in odml_section.props:
        values = op.values
        if len(values) > 0:
            nixp = nix_section.create_property(op.name, op.values)
        else:
            nixp = nix_section.create_property(op.name, nix.DataType.String)
        if op.unit is not None:
            nixp.unit = op.unit

    for osec in odml_section.sections:
        name = osec.name
        if "/" in osec.name:
            name = name.replace("/", "_")
        nsec = nix_section.create_section(name, osec.type)
        odml2nix(osec, nsec)
