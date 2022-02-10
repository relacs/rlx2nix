# Converter of old-style relacs files to NIX

converts file-based relacs data files to nix files, does not convert repro-written special files such as stimspikes.dat, etc.

## TODO

* check if there is already a nix file... Don't do anything unless there is a --force
* check the raw traces, they are not there, we will have a hard time
* convert them to dataArrays, find out their names, etc.
* read info file and convert to nix sections and properties. Beware ... old and new style metadata in relacs files...