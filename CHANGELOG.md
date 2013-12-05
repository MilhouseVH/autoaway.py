#Changelog

##Version 0.1.0 (05/12/2013)
* Chg: Elapsed time while occupied shouldn't be reset by away detection that doesn't exceed grace period (ie. home for 5 hours, detected as away for 5 minutes during a 15 minute grace period, then away after another 2 hours is 7h05m occupied, not 2h00m).

##Version 0.0.9 (19/11/2013)
* Add: Extra arguments on call to --notify script, now pass arg1: status (away/here), arg2: here/away period in seconds, arg3: here/away period in "d h:m:s" format.

##Version 0.0.8 (18/11/2013)
* Restrict "ip" based arp cache to reachable devices only
* Add auto-update facility, will automatically update to latest version of script unless disabled with `--nocheck`. Manually update with `--update` option. Check current version with `--version` option.

##Version 0.0.7 (27/10/2013)
* Cast time.time() to int to avoid stray fractional seconds

##Version 0.0.6 (23/10/2013)
* Add extra detection checks when transitioning from seen to not seen to avoid false negative

##Version 0.0.5 (18/10/2013)
* Ping flood the subnet at startup to resolve unknown MAC addresses.
* Add `--subnet` option to specify subnet if it is incorrectly guessed from ARP cache (eg. `--subnet 192.168.0`)

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
