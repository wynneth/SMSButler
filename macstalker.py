#!/usr/bin/python
# Script to check ddwrt active wireless clients for a specific mac and notify via sms when present
import sys
from time import sleep
import subprocess

def WifiClients():
  try:
    with open('/usr/share/wynscripts/ddwrtauth', 'r') as f:
      wrtuser = f.readline().rstrip()
      wrtpw = f.readline().rstrip()
      ddwrturl = "http://"+wrtuser+":"+wrtpw+"@10.1.1.1:81/Status_Wireless.asp"
    return subprocess.check_output(["curl", "-s", ddwrturl])
  except:
    pass

mac = sys.argv[1]
contact = sys.argv[2]
message = sys.argv[3] + " has returned home."
dummy = sys.argv[3] + " is already home, silly."

if mac in WifiClients():
  subprocess.Popen(["/usr/share/wynscripts/twilio_sms.py", "-c", contact, "-m", dummy])
else:
  while mac not in WifiClients():
    sleep(.5)
  subprocess.Popen(["/usr/share/wynscripts/twilio_sms.py", "-c", contact, "-m", message])
