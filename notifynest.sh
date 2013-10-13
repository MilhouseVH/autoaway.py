#!/bin/sh
#
# Sample script to communicate latest away status to nest.com
#
# Uses nest.py from https://github.com/jsquyres/pynest
#
BIN=$(readlink -f $(dirname $0))

echo "Updating Nest with away status: $1"
$BIN/nest.py --user joe@user.com --password swordfish away $1
