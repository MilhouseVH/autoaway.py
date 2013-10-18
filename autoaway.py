#!/usr/bin/env python
# -*- coding: utf-8 -*-

################################################################################
#
#  Copyright (C) 2013 Neil MacLeod (autoaway@nmacleod.com)
#
#  This Program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2, or (at your option)
#  any later version.
#
#  This Program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
#  https://github.com/MilhouseVH/autoaway.py
#
################################################################################

from __future__ import print_function

import os
import sys
import platform
import subprocess
import socket
import time
import datetime
import argparse
import random
import hashlib
import re

if sys.version_info >= (3, 0):
  import urllib.request as urllib2
else:
  import urllib2

class AutoAway(object):
  def __init__( self, devices, use_arp=True, pings=1, grace_period=30, notify=None,
                    off_peak_start=None, off_peak_end=None,
                    occupied_sleep=15*60, check_every=None, vacant_sleep=15,
                    verbose=False, reverse=True, randomise=True):

    self.devices = devices
    self.use_arp = use_arp
    self.pings = int(pings)
    self.grace_period = int(grace_period)
    self.notify = notify
    self.off_peak_start = self.time_to_tuple(off_peak_start)
    self.off_peak_end = self.time_to_tuple(off_peak_end)
    self.grace_period_secs = self.grace_period * 60
    self.occupied_sleep = int(occupied_sleep) if occupied_sleep else occupied_sleep
    self.check_every = int(check_every) if check_every else check_every
    self.vacant_sleep = int(vacant_sleep)
    self.verbose = verbose
    self.reverse = reverse
    self.randomise = randomise

    self.static_list = [("", x) for x in self.devices if not self.isMAC(x)]
    self.dynamic_list = [(x, "") for x in self.devices if self.isMAC(x)]

    self.debug("Monitoring %d device%s: [%s]" % (len(self.devices), "s"[len(self.devices)==1:], ", ".join(self.devices)))
    self.debug("Using ARP: %s, Reverse Lookup: %s" % (self.use_arp, self.reverse))
    self.debug("Pings: %d, Grace Period: %d mins" % (self.pings, self.grace_period))
    if self.off_peak_start and self.off_peak_end:
      self.debug("Off Peak: %s -> %s" % (off_peak_start, off_peak_end))
    else:
      self.debug("Off Peak: Not set")
    if self.check_every:
      self.debug("Sleep interval when occupied: Every %d minutes" % self.check_every)
    else:
      self.debug("Sleep interval when occupied: %d secs" % self.occupied_sleep)
    self.debug("Sleep Interval when vacant:   %d secs" % self.vacant_sleep)
    self.debug("=" * 50)

    self.last_seen = 0
    self.first_seen = 0
    self.first_notseen = 0

    self.time_occupied = 0
    self.time_vacant = 0

  def PropertyIsOccupied(self):
    is_occupied = self.get_status()

    if is_occupied:
      self.debug("Occupancy Check: %s (one or more devices within property)" % is_occupied)
    else:
      if self.first_notseen > 0:
        gp_remaining = self.grace_period_secs - (time.time() - self.first_notseen)
      else:
        gp_remaining = self.grace_period_secs
      gp_msg = "elapsed" if gp_remaining <= 0 else self.secsToTime(gp_remaining, "%dm %02ds")
      self.debug("Occupancy Check: %s (no devices within property, grace period remaining: %s)" % (is_occupied, gp_msg))

    self.set_status(is_occupied)

    if self.first_notseen != 0 and (time.time() - self.first_notseen) >= self.grace_period_secs:
      return False
    else:
      return True

  def PropertyIsVacant(self):
    return not self.PropertyIsOccupied()

  def DevicesSeen(self):
    return (self.first_notseen == 0)

  def GetOccupiedPeriod(self):
    return self.secsToTime(self.time_occupied)

  def GetVacantPeriod(self):
    return self.secsToTime(self.time_vacant)

  def ExecuteNotification(self, isOccupied):
    if self.notify:
      value = "here" if isOccupied else "away"
      self.debug("Calling notify [%s] with value [%s]" % (self.notify, value))
      try:
        response = subprocess.check_output([self.notify, value],
                                           stderr=subprocess.STDOUT).decode("utf-8")
        if response:
          self.debug("** Start of response **")
          self.debug("%s" % response[:-(len(os.linesep))])
          self.debug("** End of response **")
      except subprocess.CalledProcessError as e:
        self.log("#### BEGIN EXCEPTION #####")
        self.log(str(e))
        self.log("Output from notify follows:\n%s" % e.output)
        self.log("#### END EXCEPTION #####")

  def Wait(self):
    offpeak = False

    if self.DevicesSeen():
      sleep_time = self.get_next_interval()

      # When the property is occupied during off peak hours, sleep for
      # longer to avoid unecessary device communication and battery drain.
      if self.off_peak_start and self.off_peak_end:
        t = datetime.datetime.now().timetuple()
        hms = (t[3], t[4], t[5])
        s = self.off_peak_start
        e = self.off_peak_end
        if e < s: e = (e[0]+24, e[1], e[2])
        hms24 = (hms[0]+24, hms[1], hms[2]) if hms[0] < s[0] else hms

        # If off peak is active, sleep until off peak ends
        if s <= hms24 < e:
          offpeak = True
          sleep_time = ((e[0] - hms24[0])*60*60) + ((e[1] - hms24[1])*60) + (e[2] - hms24[2])
        else:
          # If off-peak kicks in before the next default occupancy check, only
          # sleep long enough so that the last on-peak check occurs just as
          # off-peak begins.
          if hms[0] > s[0]: s = (s[0]+24, s[1], s[2])
          secs_to_offpeak = ((s[0] - hms[0])*60*60) + ((s[1] - hms[1])*60) + (s[2] - hms[2])
          if secs_to_offpeak < sleep_time: sleep_time = secs_to_offpeak
    else:
      sleep_time = self.vacant_sleep

    if self.verbose:
      self.debug("Sleeping for %d seconds (%s)%s" %
        (sleep_time, self.secsToTime(sleep_time, "%dh %02dm %02ds"),
        " [Off peak is active]" if offpeak else ""))

    time.sleep(sleep_time)

  def get_status(self):
    # If checking ARP, or trying to resolve MAC addresses, then get the ARP cache
    if self.use_arp or self.dynamic_list:
      arp = self.get_arp_cache()

      # If we have MAC addresses, learn their IP address
      self.learn_mac_hosts(arp)
    else:
      arp = []

    if self.use_arp and self.arp_check(arp):
      return True
    else:
      return self.ping_check()

  def set_status(self, isOccupied):
    if isOccupied:
      self.last_seen = time.time()

      if self.first_seen == 0:
        self.first_seen = self.last_seen

      if self.first_notseen != 0:
        self.time_vacant = self.first_seen - self.first_notseen
        self.first_notseen = self.last_notseen = 0
    else:
      self.last_notseen = time.time()
      if self.first_notseen == 0:
        self.first_notseen = self.last_notseen

      if self.first_seen != 0:
        self.time_occupied = self.first_notseen - self.first_seen
        self.first_seen = self.last_seen = 0

  def ping_check(self):
    self.debug("Pinging remote hosts...")

    dlist = [x for x in self.static_list + self.dynamic_list if x[1] != ""]
    if self.randomise:
      dlist = random.sample(dlist, len(dlist))

    for host in dlist:
      mac = host[0]
      ip = host[1]
      fqname, ipaddress = self.get_host_details(ip)
      if ipaddress:
        try:
          if sys.platform == "win32":
            response = subprocess.check_output(["ping", "-n", "%d" % self.pings, "-w", "1000", ipaddress],
                                               stderr=subprocess.STDOUT).decode("utf-8")
          else:
            response = subprocess.check_output(["ping", "-c","%d" % self.pings, "-W", "1", ipaddress],
                                               stderr=subprocess.STDOUT).decode("utf-8")
        except (subprocess.CalledProcessError) as e:
          response = e.output

        (sent, received, lost, errors, pctloss) = self.get_ping_stats(response)
        self.debug("* Ping stats for %s: %d sent, %d received, %d lost (%d%% loss), %d errors" %
          (fqname, sent, received, lost, pctloss, errors))

        if received != 0:
          self.debug("** Got Ping reply from: %s [%s]" % (fqname, ipaddress))
          return True
        else:
          self.debug("** No Ping reply from: %s [%s]" % (fqname, ipaddress))
      else:
        self.debug("** Invalid Device: %s (no ip address)" % fqname)
    else:
      return False

  def get_ping_stats(self, response):
    re_match = None
    re_group = None
    replies = 0
    for line in response.split("\n"):
      if not line: continue
      if re_match:
        re_group = re.search("^.*?(\d+).*?(\d+).*?(\d+) errors.*?(\d+)%.*$", line)
        if not re_group:
          re_group = re.search("^.*?(\d+).*?(\d+).*?(\d+)%.*$", line)
        break
      else:
        if re.match(".*from.* ttl=.*$", line, flags=re.IGNORECASE):
          replies += 1
        else:
          re_match = re.search("^.*?ping statistics.*", line, flags=re.IGNORECASE)

    # Sent/Received/Lost/Errors/% Loss
    r = [0, 0, 0, 0, 0]
    if re_group and len(re_group.groups()) != 0:
      r[0] = int(re_group.group(1)) # Sent
      r[1] = replies if sys.platform == "win32" else int(re_group.group(2))
      if len(re_group.groups()) == 4: # s/r/e/%
        r[3] = int(re_group.group(3)) # Errors

      # Calculate lost and % loss
      r[2] = r[0] - r[1]
      r[4] = int(100*(1-(float(r[1])/float(r[0]))))

    return(tuple(r))

  def get_arp_cache(self):
    self.debug("Loading ARP Cache...")

    arp = []

    if sys.platform == "win32":
      try:
        response = subprocess.check_output(["arp", "-a"],
                                           stderr=subprocess.STDOUT).decode("utf-8")
        pattern = re.compile(" *([0-9]*\.[0-9]*\.[0-9]*\.[0-9]*) *([^ ]*) *([^ ]*)")
        for line in response.split("\r\n"):
          if line:
            match = re.match(pattern, line)
            if match and match.group(3) != "invalid":
              arp.append({"mac": match.group(2).replace("-", ":"), "ip": match.group(1), "type": match.group(3)})
      except (OSError, subprocess.CalledProcessError) as e:
        pass
    else:
      try:
        response = subprocess.check_output(["arp", "-a"],
                                           stderr=subprocess.STDOUT).decode("utf-8")
        pattern = re.compile(".* \(([0-9]*\.[0-9]*\.[0-9]*\.[0-9]*)\) at (.*) on (.*)")
        for line in response.split("\n"):
          if line:
            match = re.match(pattern, line)
            if match and self.isMAC(match.group(2)): # Got a MAC address...
              arp.append({"mac": match.group(2).split(" ")[0], "ip": match.group(1), "type": match.group(3)})
      except (OSError, subprocess.CalledProcessError) as e:
        try:
          response = subprocess.check_output(["ip", "neighbor", "list"],
                                             stderr=subprocess.STDOUT).decode("utf-8")
          pattern = re.compile("^([0-9]*\.[0-9]*\.[0-9]*\.[0-9]*) .* .* (.*) (.*)$")
          for line in response.split("\n"):
            if line:
              match = re.match(pattern, line)
              if match and self.isMAC(match.group(2)): # Got a MAC address...
                arp.append({"mac": match.group(2), "ip": match.group(1), "type": match.group(3)})
        except (OSError, subprocess.CalledProcessError) as e:
          pass

    self.debug("* ARP Cache has %d entrie(s)" % len(arp))

    return arp

  def arp_check(self, arp):
    if not arp: return False

    for host in [x for x in self.static_list + self.dynamic_list if x[1] != ""]:
      mac = host[0]
      ip = host[1]
      fqname, ipaddress = self.get_host_details(ip)
      for nic in arp:
        if ipaddress == nic["ip"]:
          self.debug("** Found in ARP Cache: %s [%s]" % (fqname, ipaddress))
          return True
      else:
        self.debug("** Not in ARP Cache: %s [%s]" % (fqname, ipaddress))
    else:
      return False

  def learn_mac_hosts(self, arp_list):
    if not self.dynamic_list: return

    for index, host in enumerate(self.dynamic_list):
      mac = host[0]
      ip = host[1]
      for nic in arp_list:
        # Learn new IP address for this MAC
        if mac == nic["mac"]:
          if ip != nic["ip"]:
            self.dynamic_list[index] = (mac, nic["ip"])
            self.debug("* New IP address learned: %s -> %s" % (mac, nic["ip"]))
          break
        # Forget any learned IP addresses if now assigned to a different MAC
        elif mac != nic["mac"] and ip == nic["ip"]:
            self.dynamic_list[index] = (mac, "")
            self.debug("* Old IP address unlearned: %s (%s re-allocated to %s)" % (mac, nic["ip"], nic["mac"]))
            break

  def isMAC(self, possible_mac):
    return possible_mac.count(":") == 5

  def get_host_details(self, device):
    try:
      fqname = socket.getfqdn(device) if self.reverse else device
      ipaddress = socket.gethostbyname(device)
      return (fqname, ipaddress)
    except (socket.gaierror, socket.error):
      self.debug("Can't resolve hostname: %s" % device)
      return (device, None)

  # Return an interval that schedules the next sleep period
  # for either the default number of seconds (occupied_sleep)
  # or calculates when the next check_every should occur (eg.
  # every 5 minutes)
  def get_next_interval(self):
    if self.check_every:
      t = datetime.datetime.now().timetuple()
      hms = (t[3], t[4], t[5])
      next = (hms[0], hms[1] + self.check_every - (hms[1] % self.check_every), 0)
      if next[1] >= 60: next = (next[0]+1, next[1] - 60, next[2])
      return ((next[0] - hms[0])*60*60) + ((next[1] - hms[1])*60) + (next[2] - hms[2])
    else:
      return self.occupied_sleep

  def secsToTime(self, secs, format=None):
    (days, hours, mins, seconds) = (int(secs/86400), int(secs/3600) % 24, int(secs/60) % 60, secs % 60)

    if format:
      items = format.count("%") if format else 0
      if items == 4:
        return format % (days, hours, mins, seconds)
      elif items == 3:
        return format % (hours, mins, seconds)
      elif items == 2:
        return format % (mins, seconds)
    else:
      return "%dd %02d:%02d:%02d" % (days, hours, mins, seconds)

  def time_to_tuple(self, aTime):
    if not aTime:
      return None
    else:
      hour, min = aTime.split(":")
      return (int(hour), int(min), 0)

  def debug(self, msg):
    if self.verbose:
      self.log("[debug] %s" % msg)

  def log(self, msg):
    print("%s: %s" % (datetime.datetime.now(), msg))
    sys.stdout.flush()

#===================

def CheckVersion(args):
  global GITHUB, VERSION

  (remoteVersion, remoteHash) = get_latest_version()

  if args.version:
    print("Current Version: v%s" % VERSION)
    print("Latest  Version: %s" % ("v" + remoteVersion if remoteVersion else "Unknown"))
    print("")

  if remoteVersion and remoteVersion > VERSION:
    print("A new version of this script is available - use the \"update\" option to automatically apply update.")
    print("")

  if args.version:
    url = GITHUB.replace("//raw.","//").replace("/master","/blob/master")
    print("Full changelog: %s/CHANGELOG.md" % url)

def DownloadLatestVersion(args):
  global GITHUB, VERSION

  (remoteVersion, remoteHash) = get_latest_version()

  if not remoteVersion:
    print("FATAL: Unable to determine version of the latest file, check internet and github.com are available.")
    return

  if not args.fupdate and remoteVersion <= VERSION:
    print("Current version is already up to date - no update required.")
    return

  try:
    response = urllib2.urlopen("%s/%s" % (GITHUB, "autoaway.py"))
    data = response.read()
  except Exception as e:
    print("Exception in downloadLatestVersion(): %s" % e)
    print("FATAL: Unable to download latest version, check internet and github.com are available.")
    return

  digest = hashlib.md5()
  digest.update(data)

  if (digest.hexdigest() != remoteHash):
    print("FATAL: Checksum of new version is incorrect, possibly corrupt download - abandoning update.")
    return

  path = os.path.realpath(__file__)
  dir = os.path.dirname(path)

  if os.path.exists("%s%s.git" % (dir, os.sep)):
    print("FATAL: Might be updating version in git repository... Abandoning update!")
    return

  try:
    THISFILE = open(path, "wb")
    THISFILE.write(data)
    THISFILE.close()
  except:
    print("FATAL: Unable to update current file, check you have write access")
    return

  print("Successfully updated from v%s to v%s" % (VERSION, remoteVersion))

def get_latest_version():
  global GITHUB, ANALYTICS, VERSION

  # Need user agent etc. for analytics
  BITS = "64" if platform.architecture()[0] == "64bit" else "32"
  ARCH = "ARM" if platform.machine().lower().startswith("arm") else "x86"
  PLATFORM = platform.system()
  if PLATFORM.lower() == "darwin": PLATFORM = "Mac OSX"
  if PLATFORM.lower() == "linux": PLATFORM = "%s %s" % (PLATFORM, ARCH)

  user_agent = "Mozilla/5.0 (%s; %s_%s; rv:%s) Gecko/20100101 Py-v%d.%d.%d.%d/1.0" % \
      (PLATFORM, ARCH, BITS, VERSION,
       sys.version_info[0], sys.version_info[1], sys.version_info[2], sys.version_info[4])

  # Construct "referer" to indicate usage:
  USAGE = "autoaway.py"

  HEADERS = []
  HEADERS.append(('User-agent', user_agent))
  HEADERS.append(('Referer', "http://www.%s" % USAGE))

  # Try checking version via Analytics URL
  (remoteVersion, remoteHash) = get_latest_version_ex(ANALYTICS, headers = HEADERS, checkerror = False)

  # If the Analytics call fails, go direct to github
  if remoteVersion == None or remoteHash == None:
    (remoteVersion, remoteHash) = get_latest_version_ex("%s/%s" % (GITHUB, "VERSION"))

  return (remoteVersion, remoteHash)

def get_latest_version_ex(url, headers=None, checkerror=True):
  GLOBAL_TIMEOUT = socket.getdefaulttimeout()
  ITEMS = (None, None)

  try:
    socket.setdefaulttimeout(5.0)

    if headers:
      opener = urllib2.build_opener()
      opener.addheaders = headers
      response = opener.open(url)
    else:
      response = urllib2.urlopen(url)

    if sys.version_info >= (3, 0):
      data = response.read().decode("utf-8")
    else:
      data = response.read()

    items = data.replace("\n","").split(" ")

    if len(items) == 2:
      ITEMS = items
    else:
      if checkerror: print("Bogus data in get_latest_version_ex(): url [%s], data [%s]" % (url, data))
  except Exception as e:
    if checkerror: print("Exception in get_latest_version_ex(): url [%s], text [%s]" % (url, e))

  socket.setdefaulttimeout(GLOBAL_TIMEOUT)
  return ITEMS

#===================

def init():
  global GITHUB, ANALYTICS, VERSION

  GITHUB = "https://raw.github.com/MilhouseVH/autoaway.py/master/"
  ANALYTICS = "http://goo.gl/ZTe1mN"
  VERSION = "0.0.4"

  parser = argparse.ArgumentParser(description="Manage auto-away status based on presence of mobile devices",
                    formatter_class=lambda prog: argparse.HelpFormatter(prog,max_help_position=25,width=90))

  parser.add_argument("-d", "--devices", metavar="DEVICE", nargs="+", \
                      help="List of devices to be monitored (hostnames, IPv4 address or colon-delimited MAC)")

  parser.add_argument("-g", "--grace", metavar="MINUTES", type=int, default=15, \
                      help="Grace period after last device seen, in minutes")

  parser.add_argument("-ops", "--offpeakstart", metavar="HH:MM", \
                      help="Off peak period start, eg. 01:00. Use 24-hour notation for HH:MM")
  parser.add_argument("-ope", "--offpeakend", metavar="HH:MM", \
                      help="Off peak period end, eg. 08:00. Device communication will \
                            be disabled during the off peak period unless no devices are \
                            present prior to off peak commencing..Use 24-hour notation for HH:MM. \
                            Both a start and end time must be specified for off-peak to be enabled.")

  group = parser.add_mutually_exclusive_group()
  group.add_argument("-ce", "--check-every", metavar="MIUNUTES", type=int, choices=range(1,61), \
                      help="Schedule device checks at regular MINUTES intervals, eg. 5, or 10. Range 1..60. Default is 15.")
  group.add_argument("-os", "--occupied-sleep", metavar="SECONDS", type=int, \
                      help="Alternative sleep interval used when property is oocupied. Specified in seconds. \
                            Less regular than --check-every.")
  parser.add_argument("-vs", "--vacant-sleep", metavar="SECONDS", type=int, default=15, \
                      help="Sleep interval to be used when property is vacant. Default is 15 seconds.")

  parser.add_argument("-n", "--notify", metavar="FILENAME", \
                      help="Execute FILENAME when change of occupancy occurs - passed \
                      \"here\" or \"away\" as argument")

  parser.add_argument("-p", "--pings", type=int, choices=range(1, 6), default=1, \
                      help="Number of ping requests - default: 1. Increase if poor WiFi reception \
                            leads to false postive \"away\" detection.")
  parser.add_argument("--noarp", action="store_true", \
                      help="Do not try to find devices in ARP cache. ARP cache will still be used \
                            to resolve MAC addresses to IP, if MAC addresses are to be monitored.")
  parser.add_argument("--noreverse", action="store_true", \
                      help="No reverse lookup on device names")
  parser.add_argument("--norandom", action="store_true", \
                      help="Do not randomise order in which devices are communicated with - \
                            use strict left-to-right order devices appear on command line")

  group = parser.add_mutually_exclusive_group()
  group.add_argument("--nocheck", action="store_true", \
                      help="Do not automatically notify new version availability")
  group.add_argument("--version", action="store_true", \
                      help="Display current version and notify if a new version is available")

  group = parser.add_argument_group('Version upgrade').add_mutually_exclusive_group()
  group.add_argument("--update", action="store_true", \
                      help="Update to latest version (if required)")
  group.add_argument("--fupdate", action="store_true", \
                      help="Force update to latest version (irrespective of current version)")

  parser.add_argument("-v", "--verbose", action="store_true", \
                      help="Display diagnostic output")

  args = parser.parse_args()

  if not (args.check_every or args.occupied_sleep): args.check_every = 15

  if args.version or args.update or args.fupdate:
    if args.version:
      CheckVersion(args)
    else:
      DownloadLatestVersion(args)
    sys.exit(1)

  if args.notify and not os.path.exists(args.notify):
    parser.error("--notify file %s does not exist!" % args.notify)

  if args.devices == None:
    parser.error("argument -d/--devices is required")

  if not args.nocheck: CheckVersion(args)

  return args

def log(msg):
  print("%s: %s" % (datetime.datetime.now(), msg))
  sys.stdout.flush()

def OccupancyChange(autoaway, isOccupied):
  if isOccupied:
    log("Property is occupied - vacant for %s" % autoaway.GetVacantPeriod())
  else:
    log("Property is vacant - occupied for %s" % autoaway.GetOccupiedPeriod())

  autoaway.ExecuteNotification(isOccupied)

#===================

def main(args):
  autoaway = AutoAway(args.devices, not args.noarp, args.pings, args.grace,
                      args.notify, args.offpeakstart, args.offpeakend,
                      args.occupied_sleep, args.check_every, args.vacant_sleep,
                      verbose=args.verbose, reverse=not args.noreverse,
                      randomise=not args.norandom)

  prev_occupied = autoaway.PropertyIsOccupied()
  prev_seen= autoaway.DevicesSeen()

  log("Startup status: %s" % ("Occupied" if prev_occupied else "Vacant"))

  while True:
    autoaway.Wait()

    now_occupied = autoaway.PropertyIsOccupied()
    now_seen = autoaway.DevicesSeen()

    if prev_occupied and now_occupied:
      if prev_seen and not now_seen:
        log("No device(s) present, property vacated? %d minute grace period commencing..." % args.grace)
      elif not prev_seen and now_seen:
        log("Device(s) now present - property re-occupied during grace period")

    if now_occupied != prev_occupied:
      OccupancyChange(autoaway, now_occupied)

    prev_occupied = now_occupied
    prev_seen = now_seen

def xx():
  lines = ["n950.local (192.168.0.47) at <incomplete> on eth0",
           "raspberrypi.local (192.168.0.4) at b8:27:eb:13:ed:b6 [ether] on eth0"]


  lines = ["192.168.0.47 dev eth0  FAILED",
           "192.168.0.4 dev eth0 lladdr b8:27:eb:13:ed:b6 REACHABLE"]

#  pattern = re.compile("^([0-9]*\.[0-9]*\.[0-9]*\.[0-9]*).* (.*)$")
  pattern = re.compile("^([0-9]*\.[0-9]*\.[0-9]*\.[0-9]*) .* .* (.*) (.*)$")

  for line in lines:
    match = re.match(pattern, line)
    if match: print(match.groups())
  sys.exit(2)

try:
#  xx()
  main(init())
except (KeyboardInterrupt, SystemExit) as e:
  if type(e) == SystemExit: sys.exit(int(str(e)))
