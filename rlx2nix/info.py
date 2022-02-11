# -*- coding: utf-8 -*-
# Copyright © 2022, Neuroethology Lab Uni Tuebingen
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted under the terms of the BSD License. See
# LICENSE file in the root of the Project.
import os
import json

here = os.path.dirname(__file__)

with open(os.path.join(here, "info.json")) as infofile:
    infodict = json.load(infofile)

NAME = infodict["NAME"]
VERSION = infodict["VERSION"]
STATUS = infodict["STATUS"]
RELEASE = infodict["RELEASE"]
AUTHOR = infodict["AUTHOR"]
COPYRIGHT = infodict["COPYRIGHT"]
CONTACT = infodict["CONTACT"]
BRIEF = infodict["BRIEF"]
HOMEPAGE = infodict["HOMEPAGE"]