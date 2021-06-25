#!/usr/bin/env python3
# (c) 2021 Martin Kistler

import argparse
import logging

import yaml
from twisted.internet import reactor
from twisted.internet.endpoints import TCP4ServerEndpoint

from main import P2PFactory

parser = argparse.ArgumentParser()
parser.add_argument('--debug', help='set logging level to debug', action='store_true')
args = parser.parse_args()


# set up logging
if args.debug:
    loglvl = logging.DEBUG
else:
    loglvl = logging.WARNING

logging.basicConfig(format='%(levelname)s:%(message)s', level=loglvl)   # TODO: log timestamps


# load config file
try:
    with open('config.yml', 'r') as file:
        # TODO: validate config?
        config = yaml.load(file, Loader=yaml.Loader)
except FileNotFoundError:
    logging.warning('No configuration file found')


endpoint = TCP4ServerEndpoint(reactor, 8007)
endpoint.listen(P2PFactory(config))
reactor.run()
