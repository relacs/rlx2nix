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
import argparse

from IPython import embed

from rlx2nix.converter import Converter


def create_parser():
    """Create the command line parser

    Returns:
        argparse.ArgumentParser: the parser
    """
    parser = argparse.ArgumentParser(description="Converter tool for folder based relacs files to nix container-files.")
    parser.add_argument('folder', type=str, help="The name of the folder to convert. May be a pattern glob understands", nargs=1)
    parser.add_argument("-o", "--output", default=None, help="Defines the name of the output nix file. If may files are provided this argument is interpreted as a prefix. If not given, the output file will be named as the folder is.")
    parser.add_argument("-l", "--logger", type=str, default="WARN", help="Log level. One of {WARN, INFO, DEBUG, ERROR}, default: WARN")
    parser.add_argument("-f", "--force", action='store_true', help="Ignore all warnings and overwrite any existing nix files.")
    return parser


def find_folders(args):
    folder = sorted(glob.glob(args.folder[0]))
    return folder


def set_log_level(level_name):
    logging.basicConfig(level=logging._nameToLevel[level_name], force=True)


def main():
    parser = create_parser()
    args = parser.parse_args()
    set_log_level(args.logger)
    folder = find_folders(args)

    logging.debug(f"rlx2nix converter! Found {len(folder)} folders matching pattern {args.folder} to process, output name: {args.output}.")
    is_prefix = len(folder) > 1

    for f in folder:
        logging.info(f"Processing folder {f}")
        if not os.path.isdir(f):
            logging.warning(f"Skipping! {f} is no folder")
            continue
        dataset = os.path.split(f.rstrip(os.sep))[-1]
        if args.output is None:
            output_filename = os.path.join(f, dataset + ".nix")
        elif is_prefix:
            output_filename = os.path.join(f, args.output + "_" + os.path.split(f)[-1] + ".nix")
        else:
            output_filename = args.output

        Converter(f, output_filename, args.force).convert()


if __name__ == "__main__":
    main()