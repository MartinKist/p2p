#!/usr/bin/env python3
# (c) 2021 Martin Kistler

import argparse

from twisted.logger import globalLogPublisher, ILogObserver, eventAsText
from zope.interface import provider

import defaults
from client import P2PClient


parser = argparse.ArgumentParser()
parser.add_argument('--debug', help='set logging level to debug', action='store_true')
parser.add_argument('--port', help=f'the port to listen on for incoming connections (default is {defaults.PORT})',
                    type=int, default=defaults.PORT)
parser.add_argument('--out', help=f'the amount of outgoing connections to maintain (default is {defaults.OUTGOING})',
                    type=int, default=defaults.OUTGOING)

args = parser.parse_args()


# set up logging
@provider(ILogObserver)
def simpleObserver(event):
    print(eventAsText(event))


globalLogPublisher.addObserver(simpleObserver)

P2PClient(args.port, args.out).run()
