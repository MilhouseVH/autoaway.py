autoaway.py
===========

Improved auto-away monitoring for Nest Thermostats

Simple script to improve Nest auto-away capability by monitoring WiFi enabled mobile devices and reacting to their presence within the home network. Devices will be detected using the ARP cache, and if not found in the ARP cache using PING.

Once it has been determined that all monitored devices are no longer present on the WiFi network, after a user-definable grace period (default: 15 minutes) a user-defined notification script will be executed that can enable auto-away on your Nest Thermostat. When at least one monitored device has reappeared (ie. returned home), the same notification script will be called immediately to disable auto-away. A parameter of "away" or "here" will be passed to the notification script as appropriate.

Any number of devices can be monitored, using either hostname or IPv4 address. As long as one of the monitored devices is "seen" on the WiFi network, it will be assumed that the property is occupied and auto-away should remain disabled.

Off-peak hours can be specified during which time device monitoring will be disabled, for instance between the hours of 01:00 and 08:00 it could be assumed the occupants are asleep, and there is no need to continue pinging devices. Of course if nobody is home during these hours, monitoring will continue until at least one device returns home, and then monitoring will be disabled until the end of the off-peak period.

Independent occupancy and vacancy frequencies can be specified, by default a short vacancy frequency will be used to detect returning devices as quickly as possible.

Devices will be pinged in random order to minimise communication with any single device, or a strict left-to-right sequence may be selected.

####Usage:
```
autoaway.py [-h] [-d DEVICE [DEVICE ...]] [-g MINUTES] [-ops HH:MM] [-ope HH:MM]
                   [-so SECONDS] [-sv SECONDS] [-n FILENAME] [--noarp] [--noreverse]
                   [--norandom] [--version | --nocheck] [--update | --fupdate] [-v]

Manage auto-away status based on presence of mobile devices

optional arguments:
  -h, --help             show this help message and exit
  -d DEVICE [DEVICE ...], --devices DEVICE [DEVICE ...]
                         List of devices to be monitored (hostnames or IPv4 address)
  -g MINUTES, --grace MINUTES
                         Grace period after last device seen, in minutes
  -ops HH:MM, --offpeakstart HH:MM
                         Off peak period start, eg. 01:00
  -ope HH:MM, --offpeakend HH:MM
                         Off peak period end, eg. 08:00
  -so SECONDS, --sleep-occupied SECONDS
                         Sleep interval while oocupied
  -sv SECONDS, --sleep-vacant SECONDS
                         Sleep interval while vacant
  -n FILENAME, --notify FILENAME
                         Execute FILENAME when change of occupancy occurs - passed "here"
                         or "away" as argument
  --noarp                Do not try to find devices in ARP cache
  --noreverse            No reverse lookup on device names
  --norandom             Do not randomise device pings - ping using left-to-right order
  --version              Check current version, and if a new version is available
  --nocheck              Do not check if a new version is available
  -v, --verbose          Display diagnostic output

Version upgrades:
  --update               Update to latest version (if required)
  --fupdate              Force update to latest version (irrespective of current version)
```


####Default values:
```
--grace           15  (minutes)
--sleep-occupied  900 (seconds)
--sleep-vacant    15  (seconds)
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
