import os
import re
import odml
import logging
import numpy as np

from IPython import embed

only_number = re.compile("^([+-]?\\d+\\.?\\d*)$")
integer_number = re.compile("^[+-]?\\d+$")
number_and_unit = re.compile("^(^[+-]?\\d+\\.?\\d*)\\s?\\w+(/\\w+)?$")
repro = re.compile(".+RePro.*:{1}.+", re.IGNORECASE)

units = ["mV", "sec","ms", "min", "uS/cm", "C", "°C", "Hz", "kHz", "cm", "mm", "um", "mg/l", "ul" "MOhm", "g"]
unit_pattern = {}
for unit in units:
    unit_pattern[unit] = re.compile(f"^(^[+-]?\\d+\\.?\\d*)\\s?{unit}$", re.IGNORECASE|re.UNICODE)


class Column(object):

    def __init__(self, name:str, number:int, type_or_unit:str) -> None:
        self._name = name
        self._number = number
        self._type_or_unit = type_or_unit
        self._dtype = float
        self._data = []

    @property
    def name(self):
        return self._name

    @property
    def number(self):
        return self._number

    @property
    def type_or_unit(self):
        return self._type_or_unit

    @property
    def data(self):
        return np.array(self._data)

    def append_data(self, data):
        self._data.append(data)

    def __repr__(self) -> str:
        s = f"Column {self.number}: {self.name} type: {self.type_or_unit}"
        return s


class ColumnSubgroup(object):

    def __init__(self, name: str) -> None:
        self._name = name
        self._columns = []

    @property
    def name(self):
        return self._name

    @property
    def columns(self):
        return self._columns

    def add_column(self, col:Column):
        assert(isinstance(col, Column))
        self._columns.append(col)

    @property
    def column_numbers(self):
        return [c.number for c in self.columns]

    def column_names(self):
        return [c.name for c in self.columns]

    def column(self, key):
        if isinstance(key, int):
            if key in self.column_numbers:
                return self._columns[self.column_numbers.index(key)]
        elif isinstance(key, str):
            if key in self.column_names:
                return self._columns[self.column_names.index(key)]
        raise KeyError("Unknown column name or column number!")

    def __getitem__(self, key):
        self.column(key)

    def __repr__(self) -> str:
        s = f"Subgroup {self.name}: with {len(self.columns)} columns."
        return s


class ColumnGroup(object):

    def __init__(self, name:str) -> None:
        self._name = name
        self._subgroups = []

    @property
    def name(self):
        return self._name

    @property
    def subgroups(self):
        return self._subgroups

    def add_subgroup(self, subgroup:ColumnSubgroup):
        assert(isinstance(subgroup, ColumnSubgroup))
        self._subgroups.append(subgroup)

    @property
    def column_numbers(self):
        numbers = []
        for sg in self.subgroups:
            numbers.extend(sg.column_numbers)
        return numbers

    @property
    def column_count(self):
        return len(self.column_numbers)

    def find_column(self, number):
        for sg in self.subgroups:
            if number in sg.column_numbers:
                return sg.column(number)
        return None
    
    # def __contains__(self, key):
    #     pass
    
    def __repr__(self) -> str:
        s = f"ColumnGroup {self.name} with {len(self.subgroups)} subgroups and {self.column_count} columns."
        return s


class Table(object):

    def __init__(self, name:str, lines, start_index) -> None:
        self._name = name
        self._column_groups = []
        self._start_index = start_index
        self._end_index = self.table_parser(lines, start_index)

    @property
    def name(self):
        return self._name

    def add_column_group(self, col_group:ColumnGroup):
        assert(isinstance(col_group, ColumnGroup))
        self._column_groups.append(col_group)

    @property
    def column_groups(self):
        return self._column_groups

    @property
    def column_count(self):
        total = 0
        for cg in self.column_groups:
            total += cg.column_count
        return total

    @property
    def keys(self):
        return [cg.name for cg in self.column_groups]

    def find_column(self, number):
        col = None
        for cg in self.column_groups:
            col = cg.find_column(number) 
            if col is not None:
                break
        return col

    def __contains__(self, key):
        return key in self.keys

    def __getitem__(self, key):
        if key in self:
            return self.column_groups[self.keys.index(key)]
        raise KeyError(f"Key {key} is unknown")

    def __repr__(self) -> str:
        s = f"Table {self.name} with {len(self.column_groups)} column groups and {self.column_count} total columns"
        return s

    def table_parser(self, lines, start_index=0):
        def find_header(lines, start_index=0):
            """
            Returns
            -------
            int:
                start index of the table header
            int:
                end index of the table header
            str: 
                the Repro name if found
            """
            start = start_index
            end = -1
            found_header = False
            repro_name = None
            for l in lines[start:]:
                l = l.strip()
                if repro.search(l) is not None:
                    repro_name = l.split(":")[-1].strip()

                if not l.startswith("#Key"):
                    start += 1
                    continue  # table key not found yet
                else:
                    found_header = True
                    break

            if not found_header:
                return -1, -1, repro_name

            end = start + 1
            l = lines[end]
            while l.startswith("#"):
                end += 1
                l = lines[end]
            return start, end - 1, repro_name

        def parse_columns(lines, index, start_pos, end_pos, subgroup):
            colname_line = lines[index]
            end_pos = end_pos if end_pos > 0 else len(colname_line) + 10

            colnames = re.split(r'\s{2,}', colname_line[1:].strip())
            colname_indices = []
            for i, name in enumerate(colnames):
                if i > 0:
                    colname_indices.append(colname_line.find(name, colname_indices[-1] + 1))
                else:
                    colname_indices.append(colname_line.find(name))
            coltype_line = lines[index+1]
            coltypes = re.split(r'\s{2,}', coltype_line[1:].strip())
            colnumber_line = lines[index+2]
            colnumbers = re.split(r'\s{2,}', colnumber_line[1:].strip())
            for i, (name, position) in enumerate(zip(colnames, colname_indices)):
                if position >= start_pos and position < end_pos:
                    logging.debug(f"subgroup {subgroup.name} ({start_pos} to {end_pos}) has column {name} @ {position}")
                    column = Column(name, int(colnumbers[i]), coltypes[i])
                    subgroup.add_column(column)

        def parse_subgroups(lines, index, start_pos, end_pos, col_group):
            line = lines[index]
            end_pos = end_pos if end_pos > -1 else len(line) + 10
            subgroup_names = re.split(r'\s{2,}', line[1:].strip())
            subgroup_indices = []
            for i, n in enumerate(subgroup_names):
                n = n + " " if i < (len(subgroup_names) - 1) else n
                name_index = line.find(n, (0 if len(subgroup_indices) == 0 else subgroup_indices[i-1]))
                subgroup_indices.append(name_index)

            for i, (name, position) in enumerate(zip(subgroup_names, subgroup_indices)):
                if position >= start_pos and position < end_pos:
                    logging.debug(f"column_group {col_group.name} ({start_pos} to {end_pos}) has subgroup {name} @ {position}")
                    sub = ColumnSubgroup(name)
                    col_group.add_subgroup(sub)
                    end_position = -1 if i >= len(subgroup_indices)-1 else subgroup_indices[i+1]-1
                    parse_columns(lines, index + 1, position, end_position, sub)

        def parse_column_groups(lines, index, t):
            line = lines[index]
            col_group_names = re.split(r'\s{2,}', line[1:].strip())
            col_group_indices = [line.find(sub) for sub in col_group_names]

            for i, (start_pos, name) in enumerate(zip(col_group_indices, col_group_names)):
                end_pos = -1 if i >= len(col_group_indices)-1 else col_group_indices[i+1]-1
                g = ColumnGroup(name)
                logging.debug(f"New column group: {g.name}...")
                parse_subgroups(lines, index+1, start_pos, end_pos, g)
                t.add_column_group(g)

        def parse_header(lines, start_index, end_index):
            assert(lines[start_index].startswith("#Key"))
            assert(end_index - start_index == 5)
            parse_column_groups(lines, start_index+1, self)

        def read_tabledata(lines, start_index):
            def convert_data(d, dt):
                if dt == int:
                    d = int(d)
                elif dt == float:
                    d = float(d)
                else:
                    d = str(d)
                return d

            def guess_column_dtype(d):
                if integer_number.match(d) or only_number.match(d):
                    return float
                else:
                    return str

            columns = [self.find_column(i+1) for i in range(self.column_count)]
            dtypes = [float for c in columns]
            end_index = start_index
            for line in lines[start_index:]:
                line = line.strip()

                if len(line) > 0:
                    data = re.split(r'\s{2,}', line)
                    for i, (c, dt) in enumerate(zip(columns, dtypes)):
                        if end_index == start_index:
                            dt = guess_column_dtype(data[i].strip())
                            dtypes[i] = dt
                        try:
                            d = convert_data(data[i].strip(), dt)
                        except:
                            d = str(d)
                        c.append_data(d)
                else:
                    break
                end_index += 1
            return end_index

        start, end, _ = find_header(lines, start_index)
        parse_header(lines, start, end)
        end_index = read_tabledata(lines, end+1)
        return end_index


class Metadata(object):
    def __init__(self, name, lines, start, end) -> None:
        self.start = start
        self.end = end
        self._root = odml.Section(name)
        self._parse(lines)

    def _parse(self, lines):

        def parse_value(value_str):
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

        def looks_like_property(line):
            result = ":" in line and len(line.strip().split(": ")) > 1 and line.strip()[0] != "*"
            return result

        def looks_like_section(line):
            return len(line) > 0 and not looks_like_property(line)

        section = self._root
        for l in lines[self.start:self.end]:
            if not l.startswith("#"):
                continue
            if looks_like_section(l):
                name = l.strip().lstrip("# ").split(":")[0]
                section = self._root.create_section(name)
            elif looks_like_property(l):
                parts = l.lstrip("#").strip().split(": ")
                value, unit = parse_value(parts[1].strip())
                p = section.create_property(parts[0].strip(), value)
                p.unit = unit


class ReproRun(object):
    def __init__(self, lines, start_index) -> None:
        self._start = start_index
        self._end = start_index
        self._table = None
        self._metadata = None
        self._scan_repro(lines)

    @property
    def name(self):
        if "repro" in self._metadata._root.sections[0].props:
            return self._metadata._root.sections[0].props["repro"].values[0]
        elif "RePro" in self._metadata._root.sections[0].props:
            return self._metadata._root.sections[0].props["RePro"].values[0]
        return None

    @property
    def start_index(self):
        return self._start

    @property
    def end_index(self):
        return self._end

    def _find_repro_settings(self, lines):
        start_index = self._start
        index = start_index
        line = lines[index].strip()
        while len(line) == 0:
            index += 1
            start_index = index
            line = lines[index].strip()

        while not line.startswith("#Key"):
            index += 1
            line = lines[index]

        return start_index, index

    def _scan_repro(self, lines):
        start, end = self._find_repro_settings(lines)
        self._metadata = Metadata("ReproSettings", lines, start, end)
        self._end = self._metadata.end
        self._table = Table(self.name, lines, end)
        self._end = self._table._end_index

    def __repr__(self):
        s = f"ReproRun: {self.name} (from {self.start_index} to {self.end_index})"
        return s


class StimuliDat(object):
    
    def __init__(self, filename, loglevel="ERROR") -> None:
        self._filename = filename
        self._repro_runs = []
        self._general_metadata = []
        logging.basicConfig(level=logging._nameToLevel[loglevel], force=True)
        if not os.path.exists(self._filename):
            logging.error(f"Stimuli.dat file {self._filename} does not exist!")
            return

        self.scan_file()

    def find_general_metadata(self, lines, start_index=0):
        index = start_index
        line = lines[index].strip()
        while not line.startswith("#"):
            start_index = index
            index += 1
            line = lines[index].strip()

        while line.startswith("#") and not line.startswith("#Key"):
            index += 1
            line = lines[index].strip()

        return start_index, index

    def scan_file(self):
        f = open(self._filename)
        lines = f.readlines()
        f.close()

        start, end = self.find_general_metadata(lines)
        self._general_metadata = Metadata("General settings", lines, start, end)
        while end < len(lines):
            repro_run = ReproRun(lines, end)
            end = repro_run.end_index
            self._repro_runs.append(repro_run)

if __name__ == "__main__":
    stimdat = StimuliDat("../2012-03-23-ae-invivo-1/stimuli.dat")
    stimdat = StimuliDat("/data/invivo/2021-08-20-ar-invivo-2/stimuli.dat")
    embed()
    # lines = f.readlines()
    # f.close()
    # logging.basicConfig(level=logging._nameToLevel["INFO"], force=True)
    # end_index = 0
    # count = 0
    # tables = []
    # while end_index < len(lines) and count < 100:
    #     table, end_index = table_parser(lines, start_index=end_index)
    #     tables.append(table)
    #     count += 1