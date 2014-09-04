#!/usr/bin/python


# TODO: 
#  - replace list of authorized phone numbers with a dictionary for replying by name
# GARAGE DOOR SMS BUTLER
# Written by Akira Fist, August 2014
# -Modified by Bruce Goheen August 2014
# -Will be running on a server rather than pi and utilizing WebIOPi to communicate with GPIO
#
# Features:
#
# - 100% secure operation, with access control lists. Only authorized family members can open.
# - Ability to interact with server with no open router ports
# - Ability to remotely stop or kill the process in case of malfunction or abuse
# - Cheap SMS solution (3/4 a cent per text), with no GSM card purchases or any cell contracts
# - Standard Linux code, easily setup on a new box, and quickly portable to other platforms like RPi, BeagleBone, or whatever 
#    future Linux technology arrives. Basically, I wanted the ability to restore this system on a fresh device within 30 minutes or less
#    
import logging
import logging.handlers
import MySQLdb as mdb
import MySQLdb.cursors
import datetime
import time
import os
import sys
from twilio.rest import TwilioRestClient
from contextlib import closing
import subprocess
import re

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
#                      LOGGING
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

log = logging.getLogger(__name__)
logging.basicConfig(filename="/var/log/smsbutler",level=logging.INFO)
formatter = logging.Formatter('%(module)s.%(funcName)s: %(message)s')

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
#                       VARIABLES
#           CHANGE THESE TO YOUR OWN SETTINGS!
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

# Insert your own account's SID and auth_token from Twilio's account page
twilio_account_sid = "FILLTHISIN"
twilio_auth_token = "FILLTHISIN"
# The phone number you purchased from Twilio
sTwilioNumber = "FILLTHISIN"

iNumOpenings = 0
iStatusEnabled = 1
iAuthorizedUser_Count = 0
iAdminUser_Count = 0
iSID_Count = 0

sLastCommand = "Startup sequence initiated at {0}.  No requests, yet".format(time.strftime("%x %X"))
sSid = ""
sSMSSender = ""


# Unfortunately, you can't delete SMS messages from Twilio's list.  
# So we store previously processed SIDs into the database.
lstSids = list()
admindict = {} # admin phone numbers, able to execute ALL commands
authdict = {} # authorized phone numbers, that can execute most commands

# Connect to local MySQL database
con = mdb.connect(host="localhost", user="smsbutler", passwd="smsbutlerpassword", db="SMSButler")
dictcon = mdb.connect(host="localhost", user="smsbutler", passwd="smsbutlerpassword", db="SMSButler", cursorclass=MySQLdb.cursors.DictCursor)
# Twilio client which will be fetching messages from their server
TwilioClient = TwilioRestClient(twilio_account_sid, twilio_auth_token)

# Various variables for mac addresses and such here
storedMacs = {
"jenny": "00:FF:00:FF:00:FF",
"johnny fever": "FF:00:FF:00:FF:00"
}

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
#                       FUNCTIONS
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

# This function sends an SMS message, wrapped in some error handling
def SendSMS(sMsg):
  try:
    sms = TwilioClient.sms.messages.create(body="{0}".format(sMsg),to="{0}".format(sSMSSender),from_="{0}".format(sTwilioNumber))
  except:
    log.warning('Error inside function SendSMS')
    pass

# Enable livingroom light GPIO
def EnableLight():
  try:
    subprocess.call(["/usr/share/smsbutler/lightrestcontrol.py", "1"])
  except:
    log.warning('Error inside function EnableLight')
    pass

# Disable livingroom light GPIO
def DisableLight():
  try:
    subprocess.call(["/usr/share/smsbutler/lightrestcontrol.py", "0"])
  except:
    log.warning('Error inside function DisableLight')
    pass

def LightStatus():
  try:
    return subprocess.check_output(["/usr/share/smsbutler/lightrestcheck.py"])
  except:
    log.warning('Error inside function LightStatus')
    pass

def CheckUptime():
  try:
    return subprocess.check_output(["uptime"])
  except:
    log.warning('Error inside function CheckUptime')
    pass

def WifiClients():
  try:
    with open('/usr/share/smsbutler/ddwrtauth', 'r') as f:
      wrtuser = f.readline().rstrip()
      wrtpw = f.readline().rstrip()
      ddwrturl = "http://"+wrtuser+":"+wrtpw+"@192.168.1.1/Status_Wireless.asp"
    return subprocess.check_output(["curl", "-s", ddwrturl])
  except:
    log.warning('Error inside function WifiClients')
    pass

def RunStalker(mac, who, name):
  try:
    subprocess.Popen(["python", "/usr/share/smsbutler/macstalker.py", mac, who, name])
  except:
    log.warning('Error inside function RunStalker')
    pass

try:
  # Store admin and authorized phone numbers in a dictionary, so we don't waste SQL resources repeatedly querying tables
  with closing(dictcon.cursor()) as auth_cursor:
    auth_cursor.execute("select sName, sPhone from Authorized")
    auth_set = auth_cursor.fetchall()
    for row in auth_set:
      authdict[(row["sPhone"])] = (row["sName"])
      iAuthorizedUser_Count = iAuthorizedUser_Count + 1

  with closing(dictcon.cursor()) as admin_cursor:
    admin_cursor.execute("select sName, sPhone from Admins")
    admin_set = admin_cursor.fetchall()
    for row in admin_set:
      admindict[(row["sPhone"])] = (row["sName"])
      iAdminUser_Count = iAdminUser_Count + 1

  # Store previous Twilio SMS SID ID's in a List, again, so we don't waste SQL resources repeatedly querying tables
  with closing(con.cursor()) as sid_cursor:
    sid_rows = sid_cursor.execute("select sSid from Butler")   
    sid_rows = sid_cursor.fetchall()
    for sid_row in sid_rows:
      for sid_col in sid_row:
        iSID_Count = iSID_Count + 1
        lstSids.append(sid_col)
        
  log.info('{0} Service loaded, found {1} admin users, {2} authorized users, {3} previous SMS messages'.format(time.strftime("%x %X"),iAdminUser_Count,iAuthorizedUser_Count,iSID_Count))
except Exception as e:
    exc_type, exc_obj, exc_tb = sys.exc_info()
    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
    log.warning('{0} Error while loading service, bailing!'.format(time.strftime("%x %X")))
    log.critical(exc_type, fname, exc_tb.tb_lineno)
    if con: con.close()
    exit(2)

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
#                       MAIN LOOP
#
#         Continuously scan Twilio's incoming SMS list
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

while (True):
  
  # The TRY block is critical.  If we cannot connect to the database, then we could possibly execute our commands dozens of times.
  # If we can't contact Twilio, again, we could execute commands excessively.  Ideally, if any error at all occurs, we need
  # to completely bail, and ideally contact the home owner that this application stopped working.
  try:

    # Only process messages from today (Twilio uses UTC)
    messages = TwilioClient.messages.list(date_sent=datetime.datetime.utcnow())

    for p in messages:
      sSMSSender = p.from_

      # Only processed fully received messages, otherwise we get duplicates
      if p.status == "received":
        if p.sid not in lstSids: # Is it a unique SMS SID ID from Twilio's list?
          # Insert this new SID ID into database and List, to avoid double processing
          lstSids.append(p.sid)
          try:
            with closing(con.cursor()) as insert_sid_cursor:
              insert_sid_cursor = insert_sid_cursor.execute("insert into Butler(sSid) values('{0}')".format(p.sid))
              con.commit()
          except:
            log.warning('Error while inserting SID record to database')
            pass
          # strip punctuation from the message
          strippedsms = re.sub("[^A-Za-z0-9 ]", "", p.body.lower())
          # check first to see if user is in admin group then fallback to authorized only
          if sSMSSender in authdict or admindict:
            if strippedsms == "commands":
	      SendSMS("No list of commands available yet.")
     
            elif ("uptime") in strippedsms:
              if iStatusEnabled == 1:
                log.info('{0} Uptime requested from {1}, replied'.format(time.strftime("%x %X"), sSMSSender))
                SendSMS("Current system uptime is {0}".format(CheckUptime()))
		sLastCommand = "Uptime command issued by {0} on {1}".format(p.from_, time.strftime("%x %X"))
              else:
                log.info('{0} SERVICE DISABLED!  Uptime requested from {1}, replied'.format(time.strftime("%x %X"), sSMSSender))
                SendSMS("SERVICE DISABLED!  Uptime request cannot be processed: {0}".format(sLastCommand))
		sLastCommand = "Uptime command issued by {0} on {1}, but not processed.".format(p.from_, time.strftime("%x %X"))

	    elif re.search(r'\bturn (on|the|light)(?:\W+\w+){0,2}?\W+(on|the|light)(?:\W+\w+){0,2}?\W+(on|the|light)\b', strippedsms) is not None:
              if iStatusEnabled == 1:
                sLastCommand = "Living room light last toggled by {0} on {1}".format(p.from_, time.strftime("%x %X"))
                log.info('{0} Now enabling light for {1}'.format(time.strftime("%x %X"), sSMSSender))

                # Enable livingroom light here
                SendSMS("Ok, turning the livingroom light on.")
                log.info('{0} SMS response sent to authorized user {1}'.format(time.strftime("%x %X"), sSMSSender))
                EnableLight()
              else:
                log.info('{0} Toggle light request received from {1} but SERVICE IS DISABLED!'.format(time.strftime("%x %X"), sSMSSender))      
		sLastCommand = "EnableLight command issued by {0} on {1}, but not processed.".format(p.from_, time.strftime("%x %X"))

            elif re.search(r'\bturn (off|the|light)(?:\W+\w+){0,2}?\W+(off|the|light)(?:\W+\w+){0,2}?\W+(off|the|light)\b', strippedsms) is not None:
              if iStatusEnabled == 1:
                sLastCommand = "Living room light last toggled by {0} on {1}".format(p.from_, time.strftime("%x %X"))
                log.info('{0} Now disabling light for {1}'.format(time.strftime("%x %X"), sSMSSender))

                # Disable livingroom light here
                SendSMS("Ok, turning the livingroom light off.")
                log.info('{0} SMS response sent to authorized user {1}'.format(time.strftime("%x %X"), sSMSSender))
                DisableLight()
              else:
                log.info('{0} Toggle light request received from {1} but SERVICE IS DISABLED!'.format(time.strftime("%x %X"), sSMSSender))
		sLastCommand = "DisableLight command issued by {0} on {1}, but not processed.".format(p.from_, time.strftime("%x %X"))

            elif ("is the light on") in strippedsms:
              if iStatusEnabled == 1:
                sLastCommand = "Living room light status last checked by {0} on {1}".format(p.from_, time.strftime("%x %X"))
                log.info('{0} Now checking light status for {1}'.format(time.strftime("%x %X"), sSMSSender))

                # Check livingroom light status here
                SendSMS("The living room light? {0}".format(LightStatus()))
                log.info('{0} SMS response sent to authorized user {1}'.format(time.strftime("%x %X"), sSMSSender))
              else:
                log.info('{0} Light status request received from {1} but SERVICE IS DISABLED!'.format(time.strftime("%x %X"), sSMSSender))
                sLastCommand = "LightStatus command issued by {0} on {1}, but not processed.".format(p.from_, time.strftime("%x %X"))
             
            elif re.search(r'\bis\W+(?:\w+\W+){1,1}?home\b', strippedsms) is not None:
	      matchObj = re.search(r'\bis +(.\w+)', strippedsms)
	      sLastCommand = "{0} last checked if {2} was home on {1}".format(p.from_, time.strftime("%x %X"), matchObj.group(1))
	      log.info('{0} Now checking {2}\'s location for {1}'.format(time.strftime("%x %X"), sSMSSender, matchObj.group(1)))
	      if storedMacs[matchObj.group(1)] in WifiClients():
	        SendSMS("Ok, stalker! {0} (or at least their phone) is home.".format(matchObj.group(1)))
	      else:
	        SendSMS("Ok, stalker! {0} is not home or their phone is off.".format(matchObj.group(1)))

            elif re.search(r'\btell me when\W+(?:\w+\W+){1,1}?is home\b', strippedsms) is not None:
	      matchObj = re.search(r'\btell me when +(.\w+)', strippedsms)
	      sLastCommand = "{0} set stalker mode on {2} on {1}".format(p.from_, time.strftime("%x %X"), matchObj.group(1))
	      log.info('{0} Stalker mode set for {2} by {1}'.format(time.strftime("%x %X"), sSMSSender, matchObj.group(1)))
	      SendSMS("Stalker mode activated for {1} by {0}. I'll let you know when they return.".format(sSMSSender, matchObj.group(1)))
	      try: 
	        RunStalker(storedMacs[matchObj.group(1)],sSMSSender,matchObj.group(1))
	      except:
	        SendSMS("I'm not sure who you're looking for...")
		pass
	    
            if sSMSSender in admindict:
              if strippedsms == "kill":
                log.info('{0} Received KILL command from {1} - bailing now!'.format(time.strftime("%x %X"), admindict[sSMSSender]))
                SendSMS("KILL command received, {0}.  Bailing to terminal now!".format(admindict[sSMSSender]))
	        sLastCommand = "Kill command issued by {0} on {1}".format(admindict[sSMSSender], time.strftime("%x %X"))
                exit(3)
	    
              elif strippedsms == "disable":
                iStatusEnabled = 0
                log.info('{0} Received DISABLE command from {1}, now disabled.  Service is now disabled.'.format(time.strftime("%x %X"), sSMSSender))
                SendSMS("{0}, service is being disabled.  Send ENABLE to restart")
	        sLastCommand = "DISABLE command issued by {0} on {1}".format(admindict[sSMSSender], time.strftime("%x %X"))

              elif strippedsms == "enable":
                iStatusEnabled = 1
                log.info('{0} Received ENABLE command from {1}.  Service is now enabled'.format(time.strftime("%x %X"), admindict[sSMSSender]))
                SendSMS("{0}, service is now enabled".format(admindict[sSMSSender]))
	        sLastCommand = "ENABLE command issued by {0} on {1}".format(admindict[sSMSSender], time.strftime("%x %X"))

              elif strippedsms == "status":
                if iStatusEnabled == 1:
                  log.info('{0} Status requested from {1}, replied'.format(time.strftime("%x %X"), sSMSSender))
                  SendSMS("{0}, status is ENABLED: {1}".format(admindict[sSMSSender],sLastCommand))
                else:
                  log.info('{0} SERVICE DISABLED!  Status requested from {1}, replied'.format(time.strftime("%x %X"), sSMSSender))
                  SendSMS("{0}, status is SERVICE DISABLED: {1}".format(admindict[sSMSSender],sLastCommand))

            else:
              SendSMS("I'm sorry, I didn't quite catch that.")
    
          else: # This phone number is not authorized.  Report possible intrusion to home owner
            log.critical('{0} Unauthorized user tried to access system: {1}'.format(time.strftime("%x %X"), sSMSSender))
	    sLastCommand = "Unauthorized attempt by {0} on {1}".format(p.from_, time.strftime("%x %X"))

  except KeyboardInterrupt:  
    exit(4)
  
  except Exception as e:
    exc_type, exc_obj, exc_tb = sys.exc_info()
    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
    log.critical(exc_type, fname, exc_tb.tb_lineno)
    if con: con.close()
    exit(1)

