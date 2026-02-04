"""
Bots plugmanager
"""

import atexit
import logging
import os
import sys

from . import botsinit
from . import botsglobal


def plugoutindex():
    """
    Bots plugoutindex
    Create usersys/index.json
    """
    # pylint: disable=import-outside-toplevel

    usage = """
    This is "%(name)s" version %(version)s, part of Bots open source edi translator (https://bots-edi.org).
    A utility to generate the index file of a plugin; this can be seen as a database dump of the configuration.
    This is eg useful for version control.
    Usage:
        %(name)s  -c<directory>
    Options:
        -c<directory>   directory for configuration files (default: config).

    """ % {
        'name': os.path.basename(sys.argv[0]),
        'version': botsglobal.version,
    }
    configdir = None
    for arg in sys.argv[1:]:
        if arg.startswith('-c'):
            configdir = arg[2:]
            if not configdir:
                print('Error: configuration directory indicated, but no directory name.')
                sys.exit(1)
        else:
            print(usage)
            sys.exit(0)
    # ***end handling command line arguments**************************

    # find locating of bots, configfiles, init paths etc.
    botsinit.generalinit(configdir)

    # import here, import at start of file gives error; first initialize.
    from . import pluglib

    filename = os.path.join(botsglobal.ini.get("directories", "usersysabs"), "index.json")
    pluglib.make_index(filename)


def index2json():
    """
    Convert an old bots index.py > index.json
    """
    # pylint: disable=import-outside-toplevel

    usage = """
    This is "%(name)s" version %(version)s, part of Bots open source edi translator (https://bots-edi.org).
    Convert bots index.py > index.json

    Usage:
        %(name)s -c<directory> <index.py> <index.json>

    Options:
        -c<directory>      directory for configuration files (default: config).
        infile: path to bots index.py
        outfile: path to bots index.json
    """ % {
        "name": os.path.basename(sys.argv[0]),
        "version": botsglobal.version,
    }
    infile = ""
    outfile = ""
    configdir = None
    for arg in sys.argv[1:]:
        if arg.startswith('-c'):
            configdir = arg[2:]
            if not configdir:
                print('Error: configuration directory indicated, but no directory name.')
                sys.exit(1)
        elif arg in ["?", "/?", "-h", "--help"] or arg.startswith("-"):
            print(usage)
            sys.exit(0)
        else:
            if not infile:
                infile = arg
            elif not outfile:
                outfile = arg
            else:
                print(usage)
                sys.exit(0)
    if not infile or not outfile:
        print(usage)
        print("Error: both input index.py and output index.json must be specified.")
        sys.exit(0)

    # find locating of bots, configfiles, init paths etc.
    botsinit.generalinit(configdir)
    botsglobal.logger = botsinit.initserverlogging(__name__)
    atexit.register(logging.shutdown)

    # import here, import at start of file gives error; first initialize.
    from . import pluglib

    print("Converting", infile, ">", outfile)
    converted = pluglib.convertindex2json(infile, outfile)
    print("Converted bots index to json:", converted)
