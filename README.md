autoaway.py
===========

Improved auto-away monitoring for Nest Thermostats.

A Python script to improve Nest auto-away capability by monitoring WiFi enabled mobile devices (not just smartphones) and responding to their presence within the local network. Devices will be detected using the ARP cache, and if not found in the ARP cache using PING.

Once it has been determined that all monitored devices are no longer present on the WiFi network, after a user-definable grace period (default: 15 minutes) the property will be considered to be vacant and a user-defined notification script will be executed that can enable auto-away on your Nest Thermostat.

When at least one monitored device has reappeared on the WiFi network (ie. returned home), the same notification script will be called immediately to disable auto-away. 

A parameter of "away" or "here" will be passed to the notification script as appropriate.

Any number of devices can be monitored, using either hostname or IPv4 address. As long as one of the monitored devices is "seen" on the WiFi network, it will be assumed that the property is occupied and auto-away should remain disabled.

Off-peak hours can be specified during which time device monitoring will be disabled. For instance between the hours of 01:00 and 06:30 it could reasonably be assumed the occupants are asleep, and there is no need to actively monitor devices (potentially waking devices from "deep sleep" and unnecessarily consuming battery power). If however the property is not occupied during the off-peak period, monitoring will continue until at least one device has returned at which point monitoring will be disabled until the end of the off-peak period.

Independent occupancy and vacancy polling intervals can be specified (default: 15 minutes and 15 seconds, respectively) - the much shorter interval when the property is vacant should help detect returning devices as quickly as possible.

Devices will be pinged in random order to minimise communication with any single device, or a strict left-to-right sequence (ie. order devices specified on the command line) may be selected.

Increase the likelihood of devices being in the ARP cache by running DHCP/DNS (eg. dnsmasq) on the same PC that is running autoaway.py, eg. a Raspberry Pi.

####Usage:
```
usage: autoaway.py [-h] [-d DEVICE [DEVICE ...]] [-g MINUTES] [-ops HH:MM] [-ope HH:MM]
                   [-os SECONDS] [-vs SECONDS] [-n FILENAME] [-p {1,2,3,4,5}] [--noarp]
                   [--noreverse] [--norandom] [--version | --nocheck]
                   [--update | --fupdate] [-v]

Manage auto-away status based on presence of mobile devices

optional arguments:
  -h, --help             show this help message and exit
  -d DEVICE [DEVICE ...], --devices DEVICE [DEVICE ...]
                         List of devices to be monitored (hostnames or IPv4 address)
  -g MINUTES, --grace MINUTES
                         Grace period after last device seen, in minutes
  -ops HH:MM, --offpeakstart HH:MM
                         Off peak period start, eg. 01:00. Use 24-hour notation for HH:MM
  -ope HH:MM, --offpeakend HH:MM
                         Off peak period end, eg. 08:00. Device communication will be
                         disabled during the off peak period unless no devices are present
                         prior to off peak commencing..Use 24-hour notation for HH:MM.
                         Both a start and end time must be specified for off-peak to be
                         enabled.
  -os SECONDS, --occupied-sleep SECONDS
                         Sleep interval to be used when property is oocupied
  -vs SECONDS, --vacant-sleep SECONDS
                         Sleep interval to be used when property is vacant
  -n FILENAME, --notify FILENAME
                         Execute FILENAME when change of occupancy occurs - passed "here"
                         or "away" as argument
  -p {1,2,3,4,5}, --pings {1,2,3,4,5}
                         Number of ping requests - default: 1. Increase if poor WiFi
                         reception leads to false "away" detection.
  --noarp                Do not try to find devices in ARP cache
  --noreverse            No reverse lookup on device names
  --norandom             Do not randomise order devices are communicated with - use strict
                         left-to-right order devices appear on command line
  --version              Display current version and notify if a new version is available
  --nocheck              Do not automatically notify new version availability
  -v, --verbose          Display diagnostic output

Version upgrade:
  --update               Update to latest version (if required)
  --fupdate              Force update to latest version (irrespective of current version)
```

####Default values:
```
--grace           15  (minutes)
--occupied-sleep  900 (seconds)
--vacant-sleep    15  (seconds)
--pings           1
```

####Example usage:
```
./autoaway.py --devices n950 192.168.0.30 --offpeakstart 01:00 --offpeakend 08:00 --notify ./notifynest.sh
````
where notifynest.sh could be:
```
#!/bin/sh

BIN=$(readlink -f $(dirname $0))

echo "Updating Nest with away status: $1"
$BIN/nest.py --user joe@user.com --password swordfish away $1
```

Note that nest.py can be obtained from https://github.com/jsquyres/pynest
