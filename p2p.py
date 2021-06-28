#!/usr/bin/env python3
# (c) 2021 Martin Kistler

import argparse
import sys

import yaml
from twisted.logger import Logger, globalLogPublisher, ILogObserver, eventAsText
from zope.interface import provider

from client import P2PClient


# TODO: Arguemnt parsing -> docker
parser = argparse.ArgumentParser()
parser.add_argument('--debug', help='set logging level to debug', action='store_true')
args = parser.parse_args()


# set up logging
@provider(ILogObserver)
def simpleObserver(event):
    print(eventAsText(event))

log = Logger()
globalLogPublisher.addObserver(simpleObserver)


# load config file
try:
    with open('config.yml', 'r') as file:
        # TODO: validate config?
        config = yaml.load(file, Loader=yaml.Loader)
except FileNotFoundError:
    log.critical('No configuration file found')
    sys.exit()


P2PClient(config).run()
