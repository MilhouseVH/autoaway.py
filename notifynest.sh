#!/bin/sh
#
# Sample script to communicate latest away status to nest.com
#
# Uses nest.py from https://github.com/jsquyres/pynest
#
BIN=$(readlink -f $(dirname $0))

echo "Updating Nest with away status: $1"

if [ "$1" = "here" ]; then
  echo "Property vacant for $3 ($2 seconds)"
else
  echo "Property occupied for $3 ($2 seconds)"
fi

$BIN/nest.py --user joe@user.com --password swordfish away $1
