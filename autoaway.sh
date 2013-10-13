#!/bin/sh
#
# Sample script to start monitoring smart devices and
# notify nest.com when a change in occupancy occurs.
#
BIN=$(readlink -f $(dirname $0))

$BIN/autoaway.py --devices n950 --offpeakstart 01:00 --offpeakend 08:00 --notify $BIN/notifynest.sh --verbose
