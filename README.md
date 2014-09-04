SMSButler
===============

A fork of Garage SMS Butler for the Raspberry Pi, originally by AkiraFist (github)

This project is designed to interface between SMS and various other systems.
As I have a very varied collection of services running at home, this project
makes it easy for members of my household to access this with no computing knowledge.

The original garage door controls have been removed for the time being; until such
time as I run wiring to utilize these functions. The same is true for the camera portion
related to it.

As of the writing of this readme, the project currently allows for two user levels:
Admins and Authorized Users

Admins have full access to all commands; Authorized Users have access to a
limited number of commands which excludes any system control commands (KILL, DISABLE, etc).

Currently, this project has commands to access a Raspberry Pi running on the same network
to check the status of a particular GPIO and change it's value. This is done utilizing the WebIOPo
REST framework on the RPi. I have a relay which controls lighting connected to this GPIO,
therefore the lighting can be queried/enabled/disabled via SMS.

This project utilizes a simple curl request to check for active wireless clients
on the local router. This accomplishes a very simplified process of checking if a
particular family member is home or being alerted when they arrive. (Utilizing
our reliance on the ever present smartphone.)

GETTING STARTED:

You first need a Twilio account, go to www.twilio.com.
Install necessary libraries on your device:

sudo apt-get install -y python-pip mysql-server python-dev libmysqlclient-dev

sudo pip install MySQL-python twilio

Next, login to your new MySQL localhost server, and then add a user + set privs + create the database and tables needed:

mysql -pYourSQLPassword -u root -h localhost

create database SMSButler;

use SMSButler;

create table Butler(sSid CHAR(40));

create table Authorized(sPhone CHAR(20), sName CHAR(20));

create table Admins(sPhone CHAR(20), sName CHAR(20));

create table Log(sPhone CHAR(20), sAction CHAR(10), dDate datetime);

-- put your phone number, with a +1 before it if you're inside the USA

insert into Authorized (sPhone, sName) values ('+19998675309', 'Jenny');   #Repeat as needed for authorized phone numbers
insert into Admins (sPhone, sName) valus ('+19995555555', 'Johnny Fever');

CREATE USER 'smsbutler'@'localhost' IDENTIFIED BY 'smsbutlerpassword';

GRANT ALL PRIVILEGES ON * . * TO 'smsbutler'@'localhost';

FLUSH PRIVILEGES;

exit;

The ddwrtauth file is intended to place your username (first line) and password (second line) to be used
when accessing a router to check wireless mac addresses.

Other included files run various commands, please be sure to update variables in each.

If using a compatible distribution, utilize the included rc.smsbutler initscript to automatically
launch the system at boot.
