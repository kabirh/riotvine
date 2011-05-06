#!/bin/bash

export HM=/home/web
export PY=$HM/site-packages
export PYTHONPATH=$PY/local:$PY/irock/irock:$PY/irock/django-apps:$PY/irock/rd-apps:$PY/irock/tp-apps:$PY/django-trunk
export DJANGO_SETTINGS_MODULE=settings
export PYTHON=/usr/bin/python

echo "Before restart"
/bin/netstat -tnv | wc -l
/bin/netstat -tnv
echo "----------------------------------"

# $HM/bin/stopamqp.sh

$HM/bin/runamqp.sh

cd $PY/irock/irock

kill `cat $HM/var/run/rv.pid`
$PYTHON manage.py runhttp \
        --daemonize \
        --servername=riotvine.com \
        --pidfile=$HM/var/run/rv.pid \
        127.0.0.1:9191
        
kill `cat $HM/var/run/rv2.pid`
$PYTHON manage.py runhttp \
       --daemonize \
       --servername=riotvine.com \
       --pidfile=$HM/var/run/rv2.pid \
       127.0.0.1:9192

kill `cat $HM/var/run/rv3.pid`
$PYTHON manage.py runhttp \
       --daemonize \
       --servername=riotvine.com \
       --pidfile=$HM/var/run/rv3.pid \
       127.0.0.1:9193

kill `cat $HM/var/run/rv4.pid`
$PYTHON manage.py runhttp \
       --daemonize \
       --servername=riotvine.com \
       --pidfile=$HM/var/run/rv4.pid \
       127.0.0.1:9194

echo "App servers started"

echo "After restart"
/bin/netstat -tnv | wc -l
/bin/netstat -tnv
echo "----------------------------------"

ps x

