#!/bin/bash

export APP_ROOT=~/workspace/python/irock
export PYTHONPATH=$APP_ROOT/django-apps:$APP_ROOT/local:~/workspace/python/django-trunk:$APP_ROOT/irock:~/django-projects/tpl/django-messages:~/django-projects/tpl
export DJANGO_SETTINGS_MODULE=settings

echo -n $'\e]0;RiotVine Test\a'

cd $APP_ROOT/irock

kill `cat /home/rajesh/temp/getq.pid`

kill `cat /home/rajesh/temp/computeq1.pid`
kill `cat /home/rajesh/temp/computeq2.pid`
kill `cat /home/rajesh/temp/searchq.pid`
kill `cat /home/rajesh/temp/priosearchq.pid`

kill `cat /home/rajesh/temp/eventsq1.pid`
kill `cat /home/rajesh/temp/eventsq2.pid`

