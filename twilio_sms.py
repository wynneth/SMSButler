#!/usr/bin/python
import argparse
from twilio.rest import TwilioRestClient
__author__ = 'wynneth'
 
parser = argparse.ArgumentParser(description='Script to accept phonenumbers and messages to send SMS.')
parser.add_argument('-c','--contacts', help='PhoneNumbers to send SMS to', nargs='+', required=True)
parser.add_argument('-m','--message',help='Contents for SMS message', nargs='+', required=True)
args = parser.parse_args()

#Your Account Side and Auth Token from twilio.com/user/account
account_sid = "FILLTHISIN"
auth_token = "FILLTHISIN"
client = TwilioRestClient(account_sid, auth_token)
contacts = args.contacts
text = args.message

for i in contacts:
    message = client.messages.create(body=text,
        to=i,    # Replace with your phone number
        from_="+19998675309") # Replace with your Twilio number
    print message.sid
