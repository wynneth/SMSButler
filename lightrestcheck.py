#!/usr/bin/python
import urllib2

url = 'http://rasppi:8000/GPIO/22/value'
response = urllib2.urlopen(url)
if response.read() == "1":
   print " The light is on."
else:
   print " The light is off."
