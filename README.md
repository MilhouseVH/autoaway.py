autoaway.py
===========

Improved auto-away monitoring for Nest Thermostats.

A Python script to improve Nest auto-away capability by monitoring WiFi enabled mobile devices (not just smartphones) and responding to their presence within the local network. Devices will be detected using the ARP cache, and if not found in the ARP cache using PING.

Once it has been determined that all monitored devices are no longer present on the WiFi network, after a user-definable grace period (default: 15 minutes) the property will be considered to be vacant and a user-defined notification script will be executed that can enable auto-away on your Nest Thermostat.

When at least one monitored device has reappeared on the WiFi network (ie. returned home), the same notification script will be called immediately to disable auto-away. 

A parameter of "away" or "here" will be passed to the notification script as appropriate.

Any number of devices can be monitored, using either hostname, IPv4 address or MAC address. As long as one of the monitored devices is "seen" on the WiFi network, it will be assumed that the property is occupied and auto-away should remain disabled.

"Off-peak" hours can be specified during which time device monitoring will be disabled. For instance between the hours of 01:00 and 06:30 it could reasonably be assumed the occupants are asleep, and there is no need to actively monitor devices (potentially waking devices from "deep sleep" and unnecessarily consuming battery power). If however the property is not occupied during the off-peak period, monitoring will continue until at least one device has returned at which point a "home" notification will be issudd and further device monitoring disabled until the end of the off-peak period.

Independent occupancy and vacancy polling intervals can be specified (default: 15 minutes and 15 seconds respectively), the much shorter "vacancy" interval should help detect returning devices as quickly as possible.

Devices will be pinged in random order to minimise communication with any single device, or alternatively by specifying `--norandom` a strict left-to-right sequence can be used (ie. device order as they appear on the command line).

Increase the likelihood of devices being in the ARP cache by running DHCP/DNS (eg. dnsmasq) on the same PC that is running autoaway.py, eg. a Raspberry Pi.

If other methods of device detection can be suggested I'll happily consider adding them, provided the suggested method(s) are not hugely complicated (no additional third-party libraries/modules), work with ALL WiFi-enabled mobile devices not just specific makes of smartphone, and must be passive (since ping already handles non-passive device detection).

####Usage:
```
usage: autoaway.py [-h] [-d DEVICE [DEVICE ...]] [-g MINUTES] [-ops HH:MM] [-ope HH:MM]
                   [-ce MIUNUTES | -os SECONDS] [-vs SECONDS] [-n FILENAME] [-s SUBNET]
                   [-p {1,2,3,4,5}] [--noarp] [--noreverse] [--norandom]
                   [--nocheck | --version] [--update | --fupdate] [-v]

Manage auto-away status based on presence of mobile devices

optional arguments:
  -h, --help             show this help message and exit
  -d DEVICE [DEVICE ...], --devices DEVICE [DEVICE ...]
                         List of devices to be monitored (hostnames, IPv4 address or
                         colon-delimited MAC)
  -g MINUTES, --grace MINUTES
                         Grace period after last device seen, in minutes
  -ops HH:MM, --offpeakstart HH:MM
                         Off peak period start, eg. 01:00. Use 24-hour notation for HH:MM
  -ope HH:MM, --offpeakend HH:MM
                         Off peak period end, eg. 08:00. Device communication will be
                         disabled during the off peak period unless no devices are present
                         prior to off peak commencing. Use 24-hour notation for HH:MM.
                         Both a start and end time must be specified for off-peak to be
                         enabled.
  -ce MIUNUTES, --check-every MIUNUTES
                         Schedule device checks at regular MINUTES interval, eg. 5, or 10.
                         Range 1..60. Default is 15.
  -os SECONDS, --occupied-sleep SECONDS
                         Alternative sleep interval used when property is oocupied.
                         Specified in seconds. Less regular than --check-every.
  -vs SECONDS, --vacant-sleep SECONDS
                         Sleep interval to be used when property is vacant. Default is 15
                         seconds.
  -n FILENAME, --notify FILENAME
                         Execute FILENAME when change of occupancy occurs - passed "here"
                         or "away" as arg1, here/away period in seconds as arg2 and
                         here/away period in "d h:m:s" format as arg3
  -s SUBNET, --subnet SUBNET
                         If only MAC addresses are specified, ping flood the subnet to
                         resolve IP addresses. Default is to extract subnet from ARP
                         cache, but this option will override (eg. 192.168.1)
  -p {1,2,3,4,5}, --pings {1,2,3,4,5}
                         Number of ping requests - default: 1. Increase if poor WiFi
                         reception leads to false postive "away" detection.
  --noarp                Do not try to find devices in ARP cache. ARP cache will still be
                         used to resolve MAC addresses to IP, if MAC addresses are to be
                         monitored.
  --noreverse            No reverse lookup on device names
  --norandom             Do not randomise order in which devices are communicated with -
                         use strict left-to-right order devices appear on command line
  --nocheck              Do not automatically notify new version availability
  --version              Display current version and notify if a new version is available
  -v, --verbose          Display diagnostic output

Version upgrade:
  --update               Update to latest version (if required)
  --fupdate              Force update to latest version (irrespective of current version)
```

####Default values:
```
--grace           15  (minutes)
--check-every     15  (minutes)
--vacant-sleep    15  (seconds)
--pings           1
```

####Example usage:
```
./autoaway.py --devices n950 192.168.0.30 90:cf:15:1b:ce:19 --offpeakstart 01:00 --offpeakend 08:00 --notify ./notifynest.sh
````
where notifynest.sh could be:
```
#!/bin/sh

BIN=$(readlink -f $(dirname $0))

echo "Updating Nest with away status: $1"
$BIN/nest.py --user joe@user.com --password swordfish away $1
if [ "$1" = "here" ]; then
  echo "Property vacant for $3 ($2 seconds)"
else
  echo "Property occupied for $3 ($2 seconds)"
fi
```

Note that nest.py can be obtained from https://github.com/jsquyres/pynest
