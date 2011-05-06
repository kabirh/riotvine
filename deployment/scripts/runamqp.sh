#!/bin/bash

export HM=/home/web
export PY=$HM/site-packages
export PYTHONPATH=$PY/local:$PY/irock/irock:$PY/irock/django-apps:$PY/irock/rd-apps:$PY/irock/tp-apps:$PY/django-trunk
export DJANGO_SETTINGS_MODULE=settings
export PYTHON=/usr/bin/python

cd $PY/irock/irock

kill `cat $HM/var/run/getq.pid`
python manage.py q twitter.getq --daemonize=True --pidfile=$HM/var/run/getq.pid

kill `cat $HM/var/run/computeq1.pid`
kill `cat $HM/var/run/computeq2.pid`
python manage.py q twitter.computeq --daemonize=True --pidfile=$HM/var/run/computeq1.pid
python manage.py q twitter.computeq --daemonize=True --pidfile=$HM/var/run/computeq2.pid

kill `cat $HM/var/run/searchq.pid`
python manage.py q twitter.searchq --daemonize=True --pidfile=$HM/var/run/searchq.pid

kill `cat $HM/var/run/eventsq1.pid`
kill `cat $HM/var/run/eventsq2.pid`
python manage.py q event.eventsq --daemonize=True --pidfile=$HM/var/run/eventsq1.pid
python manage.py q event.eventsq --daemonize=True --pidfile=$HM/var/run/eventsq2.pid

echo "AMQP queues started"

ps x

