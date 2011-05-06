#!/bin/bash

echo "-----------------------"
echo "UTC date: `/bin/date`"
echo "-----------------------"
/usr/bin/curl --user-agent "RiotVine v/1.0" http://twitter.com/account/rate_limit_status.xml

