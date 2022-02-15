# Converter of old-style relacs files to NIX

converts file-based relacs data files to nix files, does not convert repro-written special files such as stimspikes.dat, etc.

## TODO

* check if all required files can be found --> Done
* unzip raw files if needed  --> Done
* check if there is already a nix file... Don't do anything unless there is a --force  --> Done
* convert raw traces to DataArrays (relacs.data.sampled), find out their names, etc. --> Done
* read stimuli.dat for unit and sampling interval --> Done
* read info file and convert to nix sections and properties. Beware ... old and new style metadata in relacs files... --> Done
* convert event traces to DataArrays (relacs.data.event)
* read stimuli.dat and get the repros and when they were run