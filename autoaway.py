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
                    occupied_sleep=15*60, vacant_sleep=15,
                    verbose=False, reverse=True, randomise=True):

    self.devices = devices
    self.use_arp = use_arp
    self.pings = int(pings)
    self.grace_period = int(grace_period)
    self.notify = notify
    self.off_peak_start = self.time_to_tuple(off_peak_start)
    self.off_peak_end = self.time_to_tuple(off_peak_end)
    self.grace_period_secs = self.grace_period * 60
    self.occupied_sleep = int(occupied_sleep)
    self.vacant_sleep = int(vacant_sleep)
    self.verbose = verbose
    self.reverse = reverse
    self.randomise = randomise

    self.debug("Monitoring %d device%s: [%s]" % (len(devices), "s"[len(devices)==1:], ", ".join(devices)))
    self.debug("Using ARP: %s, Reverse Lookup: %s" % (use_arp, reverse))
    self.debug("Pings: %d, Grace Period: %d mins" % (pings, grace_period))
    if self.off_peak_start and self.off_peak_end:
      self.debug("Off Peak: %s -> %s" % (off_peak_start, off_peak_end))
    else:
      self.debug("Off Peak: Not set")
    self.debug("Sleep interval when occupied: %d secs" % occupied_sleep)
    self.debug("Sleep Interval when vacant:   %d secs" % vacant_sleep)
    self.debug("=" * 50)

    self.last_seen = 0
    self.first_seen = 0
    self.first_notseen = 0

    self.time_occupied = 0
    self.time_vacant = 0

  def CheckForOccupancy(self):
    inARP = self.arp_check() if self.use_arp else False
    if inARP:
      result = True
    else:
      result = self.ping_check()

    if result:
      self.debug("Occupancy Check: %s (one or more devices within property)" % result)
    else:
      self.debug("Occupancy Check: %s (no devices within property)" % result)

    return result

  def ping_check(self):
    self.debug("Pinging remote hosts...")
    gotreply = False

    dlist = random.sample(self.devices, len(self.devices)) if self.randomise else self.devices

    for device in dlist:
      fqname, ipaddress = self.getHostDetails(device)
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

        (sent, received, lost, errors, pctloss) = self.extractPacketStats(response)
        self.debug("* Ping stats for %s: %d sent, %d received, %d lost (%d%% loss), %d errors" %
          (fqname, sent, received, lost, pctloss, errors))

        if received != 0:
          self.debug("** Got Ping reply from: %s [%s]" % (fqname, ipaddress))
          gotreply = True
          break
        else:
          self.debug("** No Ping reply from: %s [%s]" % (fqname, ipaddress))
      else:
        self.debug("** Invalid Device: %s (no ip address)" % fqname)
    return gotreply

  def extractPacketStats(self, response):
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

  def arp_check(self):
    self.debug("Checking ARP Cache...")

    arp = {}

    if sys.platform == "win32":
      try:
        response = subprocess.check_output(["arp", "-a"],
                                           stderr=subprocess.STDOUT).decode("utf-8")
        for line in response.split("\r\n"):
          if line:
            match = re.match(" *([0-9]*\.[0-9]*\.[0-9]*\.[0-9]*) *([^ ]*) *([^ ]*)", line)
            if match and match.group(3) != "invalid": arp[match.group(1)] = match.group(3)
      except (OSError, subprocess.CalledProcessError) as e:
        pass
    else:
      try:
        response = subprocess.check_output(["arp", "-a"],
                                           stderr=subprocess.STDOUT).decode("utf-8")
        for line in response.split("\n"):
          if line:
            match = re.match(".* \(([0-9]*\.[0-9]*\.[0-9]*\.[0-9]*)\).*", line)
            if match: arp[match.group(1)] = "OK"
      except (OSError, subprocess.CalledProcessError) as e:
        try:
          response = subprocess.check_output(["ip", "neighbor", "list"],
                                             stderr=subprocess.STDOUT).decode("utf-8")
          for line in response.split("\n"):
            if line:
              match = re.match("^([0-9]*\.[0-9]*\.[0-9]*\.[0-9]*).* (.*)$", line)
              if match and match.group(2) != "FAILED":
                arp[match.group(1)] = match.group(2)
        except (OSError, subprocess.CalledProcessError) as e:
          pass

    self.debug("* ARP Cache has %d entrie(s)" % len(arp))

    found = False
    for device in self.devices:
      fqname, ipaddress = self.getHostDetails(device)
      if ipaddress in arp:
        self.debug("** Found in ARP Cache: %s [%s]" % (fqname, ipaddress))
        found = True
        break
      else:
        self.debug("** Not in ARP Cache: %s [%s]" % (fqname, ipaddress))

    return found

  def getHostDetails(self, device):
    try:
      fqname = socket.getfqdn(device) if self.reverse else device
      ipaddress = socket.gethostbyname(device)
      return (fqname, ipaddress)
    except (socket.gaierror, socket.error):
      self.debug("Can't resolve hostname: %s" % device)
      return (device, None)

  def SetStatus(self, isOccupied):
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

  def PropertyIsOccupied(self):
    self.SetStatus(self.CheckForOccupancy())
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
    sleep_time = self.occupied_sleep

    if self.DevicesSeen():
      # When the property is occupied during off peak hours, sleep for
      # longer to avoid unecessary device communication and battery drain.
      if self.off_peak_start and self.off_peak_end:
        t = datetime.datetime.now().timetuple()
        hour_min = (t[3], t[4])

        s = self.off_peak_start
        e = self.off_peak_end
        if e < s: e = (e[0]+24, e[1])
        hour_min24 = (hour_min[0]+24, hour_min[1]) if hour_min[0] < s[0] else hour_min

        # If off peak is active, sleep until off peak ends
        if s <= hour_min24 < e:
          offpeak = True
          sleep_time = ((e[0] - hour_min24[0])*60*60) + ((e[1] - hour_min24[1])*60)
        else:
          # If off-peak kicks in before the next default occupancy check, only
          # sleep long enough so that the last on-peak check occurs just as
          # off-peak begins.
          if hour_min[0] > s[0]: s = (s[0]+24, s[1])
          secs_to_offpeak = ((s[0] - hour_min[0])*60*60) + ((s[1] - hour_min[1])*60)
          if secs_to_offpeak < sleep_time: sleep_time = secs_to_offpeak
    else:
      sleep_time = self.vacant_sleep

    if self.verbose:
      self.debug("Sleeping for %d seconds (%s)%s" %
        (sleep_time, self.secsToTime(sleep_time, "%dh %02dm %02ds"),
        " [Off peak is active]" if offpeak else ""))

    time.sleep(sleep_time)

  def secsToTime(self, secs, format=None):
    (days, hours, mins, seconds) = (int(secs/86400), int(secs/3600) % 24, int(secs/60) % 60, secs % 60)
    items = format.count("%") if format else 0

    if format and items == 4:
      return format % (days, hours, mins, seconds)
    elif format and items == 3:
      return format % (hours, mins, seconds)
    else:
      return "%dd %02d:%02d:%02d" % (days, hours, mins, seconds)

  def time_to_tuple(self, aTime):
    if not aTime:
      return None
    else:
      hour, min = aTime.split(":")
      return (int(hour), int(min))

  def debug(self, msg):
    if self.verbose:
      self.log("[debug] %s" % msg)

  def log(self, msg):
    print("%s: %s" % (datetime.datetime.now(), msg))
    sys.stdout.flush()

#===================

def checkVersion(args):
  global GITHUB, VERSION

  (remoteVersion, remoteHash) = getLatestVersion()

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

def downloadLatestVersion(args):
  global GITHUB, VERSION

  (remoteVersion, remoteHash) = getLatestVersion()

  if not remoteVersion:
    print("FATAL: Unable to determine version of the latest file, check internet and github.com are available.")
    sys.exit(2)

  if not args.fupdate and remoteVersion <= VERSION:
    print("Current version is already up to date - no update required.")
    sys.exit(2)

  try:
    response = urllib2.urlopen("%s/%s" % (GITHUB, "autoaway.py"))
    data = response.read()
  except Exception as e:
    print("Exception in downloadLatestVersion(): %s" % e)
    print("FATAL: Unable to download latest version, check internet and github.com are available.")
    sys.exit(2)

  digest = hashlib.md5()
  digest.update(data)

  if (digest.hexdigest() != remoteHash):
    print("FATAL: Checksum of new version is incorrect, possibly corrupt download - abandoning update.")
    sys.exit(2)

  path = os.path.realpath(__file__)
  dir = os.path.dirname(path)

  if os.path.exists("%s%s.git" % (dir, os.sep)):
    print("FATAL: Might be updating version in git repository... Abandoning update!")
    sys.exit(2)

  try:
    THISFILE = open(path, "wb")
    THISFILE.write(data)
    THISFILE.close()
  except:
    print("FATAL: Unable to update current file, check you have write access")
    sys.exit(2)

  print("Successfully updated from v%s to v%s" % (VERSION, remoteVersion))

def getLatestVersion():
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
  (remoteVersion, remoteHash) = getLatestVersion_ex(ANALYTICS, headers = HEADERS, checkerror = False)

  # If the Analytics call fails, go direct to github
  if remoteVersion == None or remoteHash == None:
    (remoteVersion, remoteHash) = getLatestVersion_ex("%s/%s" % (GITHUB, "VERSION"))

  return (remoteVersion, remoteHash)

def getLatestVersion_ex(url, headers=None, checkerror=True):
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
      if checkerror: print("Bogus data in getLatestVersion_ex(): url [%s], data [%s]" % (url, data))
  except Exception as e:
    if checkerror: print("Exception in getLatestVersion_ex(): url [%s], text [%s]" % (url, e))

  socket.setdefaulttimeout(GLOBAL_TIMEOUT)
  return ITEMS

#===================

def log(msg):
  print("%s: %s" % (datetime.datetime.now(), msg))
  sys.stdout.flush()

def PresenceChanged(isOccupied, autoaway):
  if isOccupied:
    log("Property is occupied - vacant for %s" % autoaway.GetVacantPeriod())
  else:
    log("Property is vacant - occupied for %s" % autoaway.GetOccupiedPeriod())

  autoaway.ExecuteNotification(isOccupied)

def init():
  global GITHUB, ANALYTICS, VERSION

  GITHUB = "https://raw.github.com/MilhouseVH/autoaway.py/master/"
  ANALYTICS = "http://goo.gl/ZTe1mN"
  VERSION = "0.0.2"

  parser = argparse.ArgumentParser(description="Manage auto-away status based on presence of mobile devices",
                    formatter_class=lambda prog: argparse.HelpFormatter(prog,max_help_position=25,width=90))

  parser.add_argument("-d", "--devices", metavar="DEVICE", nargs="+", \
                      help="List of devices to be monitored (hostnames or IPv4 address)")

  parser.add_argument("-g", "--grace", metavar="MINUTES", type=int, default=15, \
                      help="Grace period after last device seen, in minutes")

  parser.add_argument("-ops", "--offpeakstart", metavar="HH:MM", \
                      help="Off peak period start, eg. 01:00. Use 24-hour notation for HH:MM")
  parser.add_argument("-ope", "--offpeakend", metavar="HH:MM", \
                      help="Off peak period end, eg. 08:00. Device communication will \
                            be disabled during the off peak period unless no devices are \
                            present prior to off peak commencing..Use 24-hour notation for HH:MM. \
                            Both a start and end time must be specified for off-peak to be enabled.")

  parser.add_argument("-os", "--occupied-sleep", metavar="SECONDS", type=int, default=15*60, \
                      help="Sleep interval to be used when property is oocupied")
  parser.add_argument("-vs", "--vacant-sleep", metavar="SECONDS", type=int, default=15, \
                      help="Sleep interval to be used when property is vacant")

  parser.add_argument("-n", "--notify", metavar="FILENAME", \
                      help="Execute FILENAME when change of occupancy occurs - passed \
                      \"here\" or \"away\" as argument")

  parser.add_argument("-p", "--pings", type=int, choices=range(1, 6), default=1, \
                      help="Number of ping requests - default: 1. Increase if poor WiFi reception \
                            leads to false \"away\" detection.")
  parser.add_argument("--noarp", action="store_true", \
                      help="Do not try to find devices in ARP cache")
  parser.add_argument("--noreverse", action="store_true", \
                      help="No reverse lookup on device names")
  parser.add_argument("--norandom", action="store_true", \
                      help="Do not randomise order devices are communicated with - \
                            use strict left-to-right order devices appear on command line")

  group = parser.add_mutually_exclusive_group()
  group.add_argument("--version", action="store_true", \
                      help="Display current version and notify if a new version is available")
  group.add_argument("--nocheck", action="store_true", \
                      help="Do not automatically notify new version availability")

  group = parser.add_argument_group('Version upgrade').add_mutually_exclusive_group()
  group.add_argument("--update", action="store_true", \
                      help="Update to latest version (if required)")
  group.add_argument("--fupdate", action="store_true", \
                      help="Force update to latest version (irrespective of current version)")

  parser.add_argument("-v", "--verbose", action="store_true", \
                      help="Display diagnostic output")

  args = parser.parse_args()

  if args.version or args.update or args.fupdate:
    if args.version:
      checkVersion(args)
    elif args.update or args.fupdate:
      downloadLatestVersion(args)
    sys.exit(1)

  if args.notify and not os.path.exists(args.notify):
    parser.error("--notify file %s does not exist!" % args.notify)
    sys.exit(1)

  if args.devices == None:
    parser.error("argument -d/--devices is required")
    sys.exit(1)

  if not args.nocheck: checkVersion(args)

  return args

#===================

def main(args):
  autoaway = AutoAway(args.devices, not args.noarp, args.pings, args.grace,
                      args.notify, args.offpeakstart, args.offpeakend,
                      args.occupied_sleep, args.vacant_sleep,
                      verbose=args.verbose, reverse=not args.noreverse,
                      randomise=not args.norandom)

  occupied_prev = autoaway.PropertyIsOccupied()
  devices_seen = autoaway.DevicesSeen()

  log("Startup status: %s" % ("Occupied" if occupied_prev else "Vacant"))

  while True:
    autoaway.Wait()

    occupied_now = autoaway.PropertyIsOccupied()

    if devices_seen and not autoaway.DevicesSeen():
      log("Property appears to have been vacated - %d minute grace period commencing..." % args.grace)
    elif not devices_seen and autoaway.DevicesSeen():
      log("Property now re-occupied")
    devices_seen = autoaway.DevicesSeen()

    if occupied_now != occupied_prev:
      PresenceChanged(occupied_now, autoaway)
      occupied_prev = occupied_now

try:
  main(init())
except (KeyboardInterrupt, SystemExit) as e:
  if type(e) == SystemExit: sys.exit(int(str(e)))
