#!/bin/bash

./stopamqp.sh

export APP_ROOT=~/workspace/python/irock
export PYTHONPATH=$APP_ROOT/django-apps:$APP_ROOT/local:~/workspace/python/django-trunk:$APP_ROOT/irock:~/django-projects/tpl/django-messages:~/django-projects/tpl
export DJANGO_SETTINGS_MODULE=settings

echo -n $'\e]0;RiotVine Test\a'

cd $APP_ROOT/irock


python manage.py q twitter.getq --daemonize=True --pidfile=/home/rajesh/temp/getq.pid

python manage.py q twitter.computeq --daemonize=True --pidfile=/home/rajesh/temp/computeq1.pid
python manage.py q twitter.computeq --daemonize=True --pidfile=/home/rajesh/temp/computeq2.pid
python manage.py q twitter.searchq --daemonize=True --pidfile=/home/rajesh/temp/searchq.pid
python manage.py q twitter.priosearchq --daemonize=True --pidfile=/home/rajesh/temp/priosearchq.pid

python manage.py q event.eventsq --daemonize=True --pidfile=/home/rajesh/temp/eventsq1.pid
python manage.py q event.eventsq --daemonize=True --pidfile=/home/rajesh/temp/eventsq2.pid

