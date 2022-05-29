#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Explanation:

This will walk the client through a set of questions to create a config file.

Usage:
    $ python  genconfig [ options ]

Style:
    Google Python Style Guide:
    http://google.github.io/styleguide/pyguide.html

    @name           genconfig
    @version        1.9.0
    @author-name    Wayne Schmidt
    @author-email   wschmidt@sumologic.com
    @license-name   GNU GPL
    @license-url    http://www.gnu.org/licenses/gpl.html
"""

__version__ = '1.9.0'
__author__ = "Wayne Schmidt (wschmidt@sumologic.com)"

import argparse
import configparser
import datetime
import os
import sys

sys.dont_write_bytecode = 1

PARSER = argparse.ArgumentParser(description="""
Generates a Sumo Logic/Recorded Future Integration Config File
""")

PARSER.add_argument('-c', metavar='<cfgfile>', dest='CONFIG', \
                    default='recorded_future.initial.cfg', help='specify a config file')

PARSER.add_argument("-i", "--initialize", action='store_true', default=False, \
                    dest='INITIALIZE', help="initialize config file")

ARGS = PARSER.parse_args(args=None if sys.argv[1:] else ['--help'])

DEFAULTMAP = []
DEFAULTMAP.append('ip')
MAPLIST = DEFAULTMAP
FUSION = {}

SRCTAG = 'sumologic-backup'

CURRENT = datetime.datetime.now()
DSTAMP = CURRENT.strftime("%Y%m%d")
TSTAMP = CURRENT.strftime("%H%M%S")

LSTAMP = DSTAMP + '.' + TSTAMP

if os.name == 'nt':
    VARTMPDIR = os.path.join ( "C:\\", "Windows", "Temp" )
else:
    VARTMPDIR = os.path.join ( "/", "var", "tmp" )

CACHED = os.path.join(VARTMPDIR, SRCTAG, DSTAMP)
SRCURL = 'UNSET'

def collect_config_info(config):
    """
    Collect information to populate the config file with
    """

    config.add_section('Default')

    sumo_uid_input = input ("Please enter your Sumo Logic API Key Name: \n")
    config.set('Default', 'SUMO_UID', sumo_uid_input )

    sumo_key_input = input ("Please enter your Sumo Logic API Key String: \n")
    config.set('Default', 'SUMO_KEY', sumo_key_input )

def persist_config_file(config):
    """
    This is a wrapper to persist the configutation files
    """

    starter_config = os.path.join( VARTMPDIR, SRCTAG + ".initial.cfg")

    with open(starter_config, 'w', encoding='utf8') as configfile:
        config.write(configfile)

    print(f'Written script config: {starter_config}')

def display_config_file():
    """
    This is a wrapper to display the configuration file
    """
    cfg_file = os.path.abspath(ARGS.CONFIG)
    if os.path.exists(cfg_file):
        my_config = configparser.ConfigParser()
        my_config.optionxform = str
        my_config.read(cfg_file)
        print(f'### Contents: {cfg_file} ###\n')
        for cfgitem in dict(my_config.items('Default')):
            cfgvalue = my_config.get('Default', cfgitem)
            print(f'{cfgitem} = {cfgvalue}')
    else:
        print(f'Unable to find: {cfg_file}')

def main():
    """
    This is a wrapper for the configuration file generation routine
    """

    if ARGS.INITIALIZE is False:

        display_config_file()

    else:

        config = configparser.RawConfigParser()

        config.optionxform = str

        collect_config_info(config)

        persist_config_file(config)

if __name__ == '__main__':
    main()
