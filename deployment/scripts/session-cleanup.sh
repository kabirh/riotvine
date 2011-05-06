#!/bin/bash

export HM=/home/web
export PY=$HM/site-packages
export PYTHONPATH=$PY/local:$PY/irock/irock:$PY/irock/django-apps:$PY/irock/rd-apps:$PY/irock/tp-apps:$PY/django-trunk
export DJANGO_SETTINGS_MODULE=settings
export PYTHON=/usr/bin/python

cd $PY/irock/irock

$PYTHON manage.py q twitter.searchq purge

$PYTHON $PY/django-trunk/django/bin/daily_cleanup.py

echo "Cleanup done"

