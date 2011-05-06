#!/bin/bash

export HM=/home/web
export PY=$HM/site-packages
export PYTHONPATH=$PY/local:$PY/irock/irock:$PY/irock/django-apps:$PY/irock/rd-apps:$PY/irock/tp-apps:$PY/django-trunk
export DJANGO_SETTINGS_MODULE=settings
export PYTHON=/usr/bin/python

$HM/bin/stopamqp.sh

cd $PY/irock/irock

kill `cat $HM/var/run/rv.pid`
kill `cat $HM/var/run/rv2.pid`
kill `cat $HM/var/run/rv3.pid`
kill `cat $HM/var/run/rv4.pid`
kill `cat $HM/var/run/rv5.pid`
kill `cat $HM/var/run/rv6.pid`

echo "App servers stopped"
