#Changelog

##Version 0.0.4 (18/10/2013)
* Add support for MAC addresses, automatically learning IP from ARP cache
* Although `--noarp` will disable ARP checking, the ARP cache will still be retrieved if MAC addresses are being monitored

##Version 0.0.3 (16/10/2013)
* Add --check-every option to use a more regular check interval (eg. --check-every 15 would check at precise 00, 15, 30 and 45 minute intervals).
* Remove sys.exit() from init()

##Version 0.0.2 (14/10/2013)
* Add --pings option to increase number of ping requests, useful if WiFi reception is patchy
* Parse ping results for improved reliability on Windows (which tends to lie about availability of unreachable hosts)
* More robust arp checking - on Linux, use arp then ip. Use regex to parse results.

##Version 0.0.1 (13/10/2013)
* Initial commit
