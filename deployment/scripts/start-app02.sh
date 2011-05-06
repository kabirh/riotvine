#!/bin/bash

export HM=/home/web
export PY=$HM/site-packages
export PYTHONPATH=$PY/local:$PY/irock/irock:$PY/irock/django-apps:$PY/irock/rd-apps:$PY/irock/tp-apps:$PY/django-trunk
export DJANGO_SETTINGS_MODULE=settings
export PYTHON=/usr/bin/python

echo "Alt Web Server"

echo "Before restart"
/bin/netstat -tnv | wc -l
/bin/netstat -tnv
echo "----------------------------------"

#$HM/bin/stopamqp.sh

$HM/bin/run_prio_q.sh

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

kill `cat $HM/var/run/rv5.pid`
$PYTHON manage.py runhttp \
       --daemonize \
       --servername=riotvine.com \
       --pidfile=$HM/var/run/rv5.pid \
       127.0.0.1:9195

kill `cat $HM/var/run/rv6.pid`
$PYTHON manage.py runhttp \
       --daemonize \
       --servername=riotvine.com \
       --pidfile=$HM/var/run/rv6.pid \
       127.0.0.1:9196

kill `cat $HM/var/run/rv7.pid`
$PYTHON manage.py runhttp \
       --daemonize \
       --servername=riotvine.com \
       --pidfile=$HM/var/run/rv7.pid \
       127.0.0.1:9197

kill `cat $HM/var/run/rv8.pid`
$PYTHON manage.py runhttp \
       --daemonize \
       --servername=riotvine.com \
       --pidfile=$HM/var/run/rv8.pid \
       127.0.0.1:9198

echo "App servers started on alt server"

echo "After restart"
/bin/netstat -tnv | wc -l
/bin/netstat -tnv
echo "----------------------------------"

ps x

