SMSButler
===============

A fork of Garage SMS Butler for the Raspberry Pi, originally by AkiraFist and
located here: https://github.com/AkiraFist/GarageSMSButler

This project is designed to interface between SMS and various other systems.
As I have a very varied collection of services running at home, this project
makes it easy for members of my household to access these with no computing knowledge.

The original garage door controls have been removed for the time being.

As of the writing of this readme, the project currently allows for two user levels,
Admins and Authorized Users:

Admins have full access to all commands; Authorized Users have access to a
limited number of commands which excludes any system control commands (KILL, DISABLE, etc).

Currently, this project has commands to access a Raspberry Pi running on the same network
to check the status of a particular GPIO and change it's value. This is done utilizing the WebIOPi
REST framework on the RPi. I have a relay which controls lighting connected to this GPIO,
therefore the lighting can be queried/enabled/disabled via SMS.

This project utilizes a curl request to check for active wireless clients
on the local router. This accomplishes a very simplified process of checking if a
particular family member is home or being alerted when they arrive. (Utilizing
our reliance on the ever present smartphone.)

As this was written primarily for my own use, further configuration will rely on
a user who has a good grasp of the methods used.

The ddwrtauth file is intended to place your username (first line) and password (second line) to be used
when accessing a router to check wireless mac addresses.

If using a compatible distribution, utilize the included rc.smsbutler initscript to automatically
launch the system at boot.

GETTING STARTED:

Place all files in /usr/share/smsbutler (or modify the URI in each file).

You first need a Twilio account, go to www.twilio.com.
Install necessary libraries on your device:

sudo apt-get install -y python-pip mysql-server python-dev libmysqlclient-dev

sudo pip install MySQL-python twilio

Next, login to your new MySQL localhost server, and then add a user + set privs + create the database and tables needed:

mysql -pYourSQLPassword -u root -h localhost

create database SMSButler;

use SMSButler;

create table Butler(sSid CHAR(40), dDate INT);

create table Authorized(sPhone CHAR(20), sName CHAR(20));

create table Admins(sPhone CHAR(20), sName CHAR(20));

-- put your phone number, with a +1 before it if you're inside the USA

insert into Authorized (sPhone, sName) values ('+19998675309', 'Jenny');   #Repeat as needed for auth phone numbers

insert into Admins (sPhone, sName) valus ('+19995555555', 'Johnny Fever'); #Repeat as needed for admin phone numbers

CREATE USER 'smsbutler'@'localhost' IDENTIFIED BY 'smsbutlerpassword';

GRANT ALL PRIVILEGES ON * . * TO 'smsbutler'@'localhost';

FLUSH PRIVILEGES;

exit;
