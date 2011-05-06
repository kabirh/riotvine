#!/bin/bash

# Load average ALERT value.
max_loadavg=7.5

loadavg=$(cat /proc/loadavg | awk '{print $1}')


# Comment the line below if you do not want to log the load average in a file.
# echo "Load Average:$loadavg on `date`" >> ~/var/log/load.log

# Email subject
SUBJECT="ALERT! High Load $loadavg (>$max_loadavg) [`hostname`]"

# Email To?
EMAIL="rajesh.dhawan@gmail.com"

# Email text/message
EMAILMESSAGE="Load Average: $loadavg on `date`"

if [ $(echo "$loadavg >= $max_loadavg"|bc) -eq 1 ]
then

# Send an Email using /bin/mail
echo $EMAILMESSAGE | mail -s "$SUBJECT" "$EMAIL"

/usr/bin/killall python
sleep 3
/home/web/bin/start-app.sh

echo "`ps x`" | mail -s "Web app restarted [`hostname`]" "$EMAIL"

fi

exit
