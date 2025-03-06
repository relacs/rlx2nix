# -*- coding: utf-8 -*-
# Copyright © 2022, Neuroethology Lab Uni Tuebingen
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted under the terms of the BSD License. See
# LICENSE file in the root of the Project.
import glob
import pathlib
import logging
import argparse

from rlx2nix.converter import Converter

loglevels = {"critical": logging.CRITICAL,
             "error": logging.ERROR,
             "warning":logging.WARNING,
             "info":logging.INFO,
             "debug":logging.DEBUG}


def create_parser():
    """Create the command line parser

    Returns:
        argparse.ArgumentParser: the parser
    """
    parser = argparse.ArgumentParser(description="Converter tool for folder based relacs files to nix container-files.")
    parser.add_argument('folder', type=str, help="The name of the folder to convert. May be a pattern glob understands", nargs=1)
    parser.add_argument("-o", "--output", default=None, help="Defines the name of the output nix file. If may files are provided this argument is interpreted as a prefix. If not given, the output file will be named as the folder is.")
    parser.add_argument("-d", "--destination", default=None, help="Defines the destination folder for the nix files. If not given, the nix files will be stored in the same folder as the relacs files.")
    parser.add_argument("-l", "--loglevel", type=str, default="WARN", help="Log level. One of {WARN, INFO, DEBUG, ERROR}, default: WARN")
    parser.add_argument("-f", "--force", action='store_true', help="Ignore all warnings and overwrite any existing nix files.")
    return parser


def find_folders(args):
    folder = sorted(glob.glob(args.folder[0]))
    return folder


def set_log_level(loglevel):
    # logging.basicConfig(level=logging._nameToLevel[level_name], force=True)
    logging.basicConfig(level=loglevel, force=True)


def main():
    parser = create_parser()
    args = parser.parse_args()

    folders = find_folders(args)
    logging.debug("rlx2nix converter! Found %i folders matching pattern %s to process, output name: %s.",
                  len(folders), args.folder, args.output)
    is_prefix = len(folders) > 1
    args.loglevel = loglevels[args.loglevel.lower() if args.loglevel.lower() in loglevels else "info"]
    set_log_level(args.loglevel)

    for f in folders:
        logging.info("Processing folder %s", f)
        p = pathlib.Path(f)
        if not p.is_dir():
            logging.warning("Skipping! %s is not a valid folder", str(p))
            continue
        dataset = p.name

        if args.destination is not None:
            output_folder = pathlib.Path(args.destination).resolve()
        else:
            output_folder = p
        logging.debug("Output folder is  %s", output_folder)

        if args.output is None:
            output_filename = output_folder / pathlib.Path(dataset + ".nix")
        elif is_prefix:
            output_filename = p / pathlib.Path(args.output + "_" + dataset + ".nix")
        else:
            output_filename = output_folder / pathlib.Path(args.output)
        logging.debug("Output filename is %s", output_filename)
        Converter(p, output_filename, args.force).convert()


if __name__ == "__main__":
    main()