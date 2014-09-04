#!/usr/bin/python
import urllib
import urllib2
import sys

url = 'http://rasppi:8000/GPIO/22/value/'
url = url + sys.argv[1]
data = urllib.urlencode('')
req = urllib2.Request(url, data)
response = urllib2.urlopen(req)
#print " the light has been toggled."
