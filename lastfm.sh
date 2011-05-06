#!/bin/bash

export APP_ROOT=~/workspace/python/irock
export PYTHONPATH=$APP_ROOT/django-apps:$APP_ROOT/local:~/workspace/python/django-trunk:$APP_ROOT/irock:~/django-projects/tpl/django-messages:~/django-projects/tpl
export DJANGO_SETTINGS_MODULE=settings

echo -n $'\e]0;IlliusRock Test\a'

cd $APP_ROOT/irock
python ../django-apps/lastfm/fetch_events.py





