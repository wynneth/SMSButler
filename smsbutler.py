#!/usr/bin/python


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
import MySQLdb as mdb #for MySQL to store/retrieve SIDs and contacts
import MySQLdb.cursors #for creating a dictionary of contacts
import datetime
import time
import os
import sys
from threading import Thread
from twilio.rest import TwilioRestClient
from contextlib import closing
import subprocess #for shell scripts and commands
import re #regex used throughout
import urllib #for raspberry pi webiopi rest access
import urllib2 #for raspberry pi webiopi rest access
from httplib import ResponseNotReady #attempt to handle exception cases
from httplib2 import ServerNotFoundError, HttpLib2Error
from ssl import SSLError

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
#                      LOGGING
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

log = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s:%(levelname)s:%(module)s.%(funcName)s.%(threadName)s:%(message)s', filename="/var/log/smsbutler",level=logging.INFO)

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
#                       VARIABLES
#           CHANGE THESE TO YOUR OWN SETTINGS!
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

# Insert your own account's SID and auth_token from Twilio's account page
twilio_account_sid = "FILLTHISIN"
twilio_auth_token = "FILLTHISIN"
# The phone number you purchased from Twilio
sTwilioNumber = "FILLTHISIN"
ownerphone = "FILLTHISIN"

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

# Usage dictionary
usagedict = {
"commands": "lists available commands",
"status": "provides status of SMS Butler",
"usage": "is the command you just issued...",
"kill": "will hardstop SMS Butler",
"enable": "will enable responses",
"disable": "will disable responses",
"uptime": "provides system uptime",
"is the light on": "provides status of living room light",
"turn on the light": "should be self-explanatory",
"turn off the light": "should be self-explanatory",
"is person home": "should be self-explanatory",
"tell me when person is home": "should be self-explanatory"
}

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
#                       FUNCTIONS
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

# This function sends an SMS message, wrapped in some error handling
def ReplySMS(sMsg):
  try:
    sms = TwilioClient.sms.messages.create(body="{0}".format(sMsg),to="{0}".format(sSMSSender),from_="{0}".format(sTwilioNumber))
  except:
    log.exception('Error inside function ReplySMS')

def SendSMS(sMsg, sRecip):
  try:
    sms = TwilioClient.sms.messages.create(body="{0}".format(sMsg),to="{0}".format(sRecip),from_="{0}".format(sTwilioNumber))
  except:
    log.exception('Error inside function SendSMS')

# Toggle livingroom light GPIO
def ToggleLight(value):
  try:
    url = 'http://rasppi:8000/GPIO/22/value/'
    url = url + value
    data = urllib.urlencode('')
    req = urllib2.Request(url, data)
    response = urllib2.urlopen(req)  
  except:
    log.exception('Error inside function ToggleLight')

def LightStatus():
  try:
    url = 'http://rasppi:8000/GPIO/22/value'
    response = urllib2.urlopen(url)
    if response.read() == "1":
      return " The light is on."
    else:
      return " The light is off."
  except:
    log.exception('Error inside function LightStatus')

def CheckUptime():
  try:
    return subprocess.check_output(["uptime"])
  except:
    log.exception('Error inside function CheckUptime')

def WifiClients():
  try:
    with open('/usr/share/smsbutler/ddwrtauth', 'r') as f:
      wrtuser = f.readline().rstrip()
      wrtpw = f.readline().rstrip()
      ddwrturl = "http://"+wrtuser+":"+wrtpw+"@192.168.1.1/Status_Wireless.asp"
    return subprocess.check_output(["curl", "-s", ddwrturl])
  except:
    log.exception('Error inside function WifiClients')

def RunStalker(mac, who, name):
  try:
    if mac in WifiClients():
      ReplySMS("{0} is already home, silly.".format(name.title()))
    else:
      while mac not in WifiClients():
        time.sleep(120)
      ReplySMS("{0} has returned home as of {1}.".format(name.title(), time.strftime("%x %X")))
  except:
    log.exception('Error inside function RunStalker')

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
        
  log.info('Service loaded, found {1} admin users, {1} authorized users, {2} previous SMS messages'.format(iAdminUser_Count,iAuthorizedUser_Count,iSID_Count))
except:
    log.exception('Error while loading service, bailing!')
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
	      fixeddate = datetime.datetime.strptime(p.date_sent.split("+")[0], '%a, %d %b %Y %H:%M:%S ')
              insert_sid_cursor = insert_sid_cursor.execute("insert into Butler(sSid,dDate) values('{0}',UNIX_TIMESTAMP('{1}'))".format(p.sid,fixeddate))
              con.commit()
            with closing(con.cursor()) as delete_sid_cursor:
	      delete_sid_cursor = delete_sid_cursor.execute("delete from Butler where FROM_UNIXTIME(dDate, '%Y-%m-%d') < '{:%Y-%m-%d}'".format(datetime.datetime.utcnow() - datetime.timedelta(days=1)))
	      log.info("Attempting to delete old records")
	      con.commit()
	  except (AttributeError, MySQLdb.OperationalError):
	    con = mdb.connect(host="localhost", user="alfred", passwd="alfredpassword", db="SnarfButler")
	    with closing(con.cursor()) as insert_sid_cursor:
              insert_sid_cursor = insert_sid_cursor.execute("insert into Butler(sSid) values('{0}')".format(p.sid))
              con.commit()
	      log.warn('Error while inserting SID record, reset con / cursor')
          except:
            log.exception('Error while inserting SID record to database')
          # strip punctuation from the message
          strippedsms = re.sub("[^A-Za-z0-9 ]", "", p.body.lower())
	  # reply to STOP, STOPALL, UNSUBSCRIBE, CANCEL, END, QUIT, START, YES, HELP, and INFO - twilio automatically acts on these and we can't override
	  twilOverrides = [ "stop", "stopall", "unsubscribe", "cancel", "end", "quit", "start", "yes", "help", "info" ]
	  if strippedsms in twilOverrides:
	    log.info("Received keyword overriden by Twilio: {0} from {1}".format(strippedsms,sSMSSender))
	    ReplySMS("We apologize if this is an incorrect number. If you unintentionally selected to STOP msgs, reply START to receive them again.")
          # check first to see if user is in admin group then fallback to authorized only
          if sSMSSender in authdict or admindict:
	    
	    if authdict.has_key(sSMSSender):
	      contactname = authdict[sSMSSender]
	    elif admindict.has_key(sSMSSender):
	      contactname = admindict[sSMSSender]
	      
            if strippedsms == "commands":
	      ReplySMS("Available commands are:")
              cmdlist = [key for key in usagedict]
              iterations = (len(cmdlist)/6)+1
              start = 0
              count = 0
              while iterations >= count:
                count = count + 1
                if start < len(cmdlist):
                  ReplySMS(str(cmdlist[start:(start+6)]).replace("[","").replace("]",""))
                  start = start+6
	      log.debug('Commands requested from {0}, replied'.format(contactname))

            #inserting elif for Usage command here with regex...
	    elif re.search(r'\busage (\w+)+', strippedsms):
	      matchObj = re.search(r'\busage ((?:\w+\s*)*)', strippedsms)
	      # use a dictionary for the usage definitions
	      if matchObj.group(1):
	        if matchObj.group(1) in usagedict:
	          ReplySMS("{0}, {1} {2}".format(contactname,matchObj.group(1),usagedict[matchObj.group(1)]))
                else:
		  ReplySMS("{0}, I don't know that command.".format(contactname))
	      else:
	        ReplySMS("{0}, please provide a command name with the Usage command.".format(contactname))
	        
            elif ("uptime") in strippedsms:
              if iStatusEnabled == 1:
                log.info('Uptime requested from {0}, replied'.format(contactname))
                ReplySMS("{0}, the current system uptime is {1}".format(contactname, CheckUptime()))
		sLastCommand = "Uptime command issued by {0} on {1}".format(contactname, time.strftime("%x %X"))
              else:
                log.info('SERVICE DISABLED! Uptime requested from {0}, replied'.format(contactname))
                ReplySMS("SERVICE DISABLED! Uptime request cannot be processed: {0}".format(sLastCommand))
		sLastCommand = "Uptime command issued by {0} on {1}, but not processed.".format(contactname, time.strftime("%x %X"))

            elif re.search(r'\bturn (on|off|the|light)(?:\W+\w+){0,2}?\W+(on|off|the|light)(?:\W+\w+){0,2}?\W+(on|off|the|light)\b', strippedsms):
	      matchObj = re.search(r'\bturn (on|off|the|light)(?:\W+\w+){0,2}?\W+(on|off|the|light)(?:\W+\w+){0,2}?\W+(on|off|the|light)\b', strippedsms)
              if iStatusEnabled == 1:
                sLastCommand = "Living room light last toggled by {0} on {1}".format(contactname, time.strftime("%x %X"))
		if "on" in matchObj.group():
		  lighttoggle = "on"
                  ToggleLight("1")
                else:
		  lighttoggle = "off"
	          ToggleLight("0")
                # Toggle livingroom light here
                ReplySMS("Ok, turning the livingroom light {0}.".format(lighttoggle))
		log.info('Now turning living room light {0} for {1}'.format(lighttoggle,contactname))
                log.debug('SMS response sent to authorized user {0}'.format(contactname))
              else:
                log.info('Toggle light request received from {0} but SERVICE IS DISABLED!'.format(contactname))
		sLastCommand = "Disable Light command issued by {0} on {1}, but not processed.".format(contactname, time.strftime("%x %X"))

            elif ("is the light on") in strippedsms:
              if iStatusEnabled == 1:
                sLastCommand = "Living room light status last checked by {0} on {1}".format(contactname, time.strftime("%x %X"))
                log.info('{0} Now checking light status for {1}'.format(time.strftime("%x %X"), contactname))

                # Check livingroom light status here
                ReplySMS("The living room light? {0}".format(LightStatus()))
                log.debug('SMS response sent to authorized user {0}'.format(contactname))
              else:
                log.info('Light status request received from {0} but SERVICE IS DISABLED!'.format(contactname))
                sLastCommand = "LightStatus command issued by {0} on {1}, but not processed.".format(contactname, time.strftime("%x %X"))
		
	    elif ("deploy countermeasures") in strippedsms:
	      ReplySMS("{0}, countermeasures have been deployed. Stage 1 action recommended.".format(contactname))
             
            elif re.search(r'\bis\W+(?:\w+\W+){1,1}?home\b', strippedsms):
	      matchObj = re.search(r'\bis +(.\w+)', strippedsms)
	      sLastCommand = "{0} last checked if {2} was home on {1}".format(contactname, time.strftime("%x %X"), matchObj.group(1).title())
	      log.info('Now checking {1}\'s location for {0}'.format(contactname, matchObj.group(1).title()))
	      if storedMacs[matchObj.group(1)] in WifiClients():
	        ReplySMS("Ok, stalker! {0} (or at least their phone) is home.".format(matchObj.group(1).title()))
	      else:
	        ReplySMS("Ok, stalker! {0} is not home or their phone is off.".format(matchObj.group(1).title()))

            elif re.search(r'\btell me when\W+(?:\w+\W+){1,1}?is home\b', strippedsms):
	      matchObj = re.search(r'\btell me when +(.\w+)', strippedsms)
	      sLastCommand = "{0} set stalker mode on {2} on {1}".format(contactname, time.strftime("%x %X"), matchObj.group(1).title())
	      log.info('Stalker mode set for {1} by {0}'.format(contactname, matchObj.group(1).title()))
	      ReplySMS("Stalker mode activated for {1} by {0}. I'll let you know when they return.".format(contactname, matchObj.group(1).title()))
	      try: 
	        t = Thread(target=RunStalker, args=(storedMacs[matchObj.group(1)],sSMSSender,matchObj.group(1)))
		t.start()
	      except:
	        ReplySMS("I'm not sure who you're looking for...")
		
	    elif sSMSSender not in admindict:
	      ReplySMS("I'm sorry, I didn't quite catch that, {0}.".format(contactname))
	    
	    
            elif sSMSSender in admindict:
	      contactname = admindict[sSMSSender]
              if strippedsms == "kill":
                log.info('Received KILL command from {0} - bailing now!'.format(contactname))
                ReplySMS("KILL command received, {0}.  Bailing to terminal now!".format(contactname))
	        sLastCommand = "Kill command issued by {0} on {1}".format(contactname, time.strftime("%x %X"))
                exit(3)
	    
              elif strippedsms == "disable":
                iStatusEnabled = 0
                log.info('Received DISABLE command from {0}, now disabled.  Service is now disabled.'.format(contactname))
                ReplySMS("{0}, service is being disabled.  Send ENABLE to restart.".format(contactname))
	        sLastCommand = "DISABLE command issued by {0} on {1}".format(contactname, time.strftime("%x %X"))

              elif strippedsms == "enable":
                iStatusEnabled = 1
                log.info('Received ENABLE command from {0}.  Service is now enabled'.format(contactname))
                ReplySMS("{0}, service is now enabled".format(contactname))
	        sLastCommand = "ENABLE command issued by {0} on {1}".format(contactname, time.strftime("%x %X"))

              elif strippedsms == "status":
                if iStatusEnabled == 1:
                  log.info('Status requested from {0}, replied'.format(contactname))
                  ReplySMS("{0}, status is ENABLED: {1}".format(contactname,sLastCommand))
                else:
                  log.info('SERVICE DISABLED!  Status requested from {0}, replied'.format(contactname))
                  ReplySMS("{0}, status is SERVICE DISABLED: {1}".format(contactname,sLastCommand))

              elif re.search(r'send a text to ', strippedsms):
	        matchObj = re.search(r'\bsend a text to ?(\w+)? ?(\d{10}) ?(.*)', strippedsms)
 		if iStatusEnabled == 1:
                  log.info('Received TEXT command from {0}.'.format(contactname))
                  if matchObj.group(1):
		    SendSMS(matchObj.group(3), matchObj.group(2))
		    ReplySMS("{0}, I am sending your message to {1} at {2}.".format(contactname,matchObj.group(1),matchObj.group(2)))
		  else:
		    SendSMS(matchObj.group(2),matchObj.group(3))
	            ReplySMS("{0}, I am sending your message to {1}.".format(contactname,matchObj.group(2)))
		  sLastCommand = "TEXT command issued by {0} on {1}".format(contactname, time.strftime("%x %X"))

              else:
                ReplySMS("I'm sorry, I didn't quite catch that, {0}.".format(contactname))
    
          else: # This phone number is not authorized.  Report possible intrusion to home owner
            log.warn('Unauthorized user tried to access system: {0}'.format(sSMSSender))
	    sLastCommand = "Unauthorized attempt by {0} on {1}".format(p.from_, time.strftime("%x %X"))

  except KeyboardInterrupt:  
    if con: con.close()
    exit(4)
  
  except (ResponseNotReady, ServerNotFoundError, HttpLib2Error, SSLError):
    log.error("httplib or httplib2 threw an error, previous command may have failed", exc_info=True) #log httplib exception
    messages = TwilioClient.messages.list(date_sent=datetime.datetime.utcnow()) #retry retrieving message list
  
  except Exception:
    log.critical("Something broke the SMS Butler!", exc_info=True)
    SendSMS("SMSButler has crashed.", ownerphone)
    if con: con.close()
    exit(1)
