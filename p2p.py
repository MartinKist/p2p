#!/usr/bin/env python3
# (c) 2021 Martin Kistler

import argparse
import sys

from twisted.logger import globalLogPublisher, ILogObserver, eventAsText
from zope.interface import provider
import requests

import defaults
from client import P2PClient

# argument parsing
parser = argparse.ArgumentParser()
parser.add_argument('--debug', help='set logging level to debug', action='store_true')
parser.add_argument('--port', help=f'the port to listen on for incoming connections (default is {defaults.PORT})',
                    type=int, default=defaults.PORT)
parser.add_argument('--out', help=f'the amount of outgoing connections to maintain (default is {defaults.OUTGOING})',
                    type=int, default=defaults.OUTGOING)
parser.add_argument('--ip', help=f'the IPv4 address your client is reachable under '
                                 f'(gets curled from "https://icanhazip.com" by default)', type=str, default=None)
args = parser.parse_args()


# set up logging
@provider(ILogObserver)
def simpleObserver(event):
    if event['log_level'].name == 'debug':
        if args.debug:
            print(eventAsText(event))
    else:
        print(eventAsText(event))


globalLogPublisher.addObserver(simpleObserver)

if args.ip is None:
    try:
        res = requests.get('https://icanhazip.com', timeout=5)
    except:
        print('Could\'nt get your IPv4 address from https://icanhazip.com.\n'
              'Set your IPv4 address manually by using the "--ip" flag.')
        sys.exit()

    ipv4_address = res.text.strip()
else:
    ipv4_address = args.ip


P2PClient(ipv4_address, args.port, args.out).run()
