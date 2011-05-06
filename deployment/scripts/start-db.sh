#!/bin/bash

export HM=/home/web
export PY=$HM/site-packages
export PYTHONPATH=$PY/local:$PY/irock/irock:$PY/irock/django-apps:$PY/irock/rd-apps:$PY/irock/tp-apps:$PY/django-trunk
export DJANGO_SETTINGS_MODULE=settings
export PYTHON=/usr/bin/python

echo "DB Server"

#$HM/bin/stopamqp.sh

$HM/bin/run_prio_q.sh
$HM/bin/runamqp.sh

echo "DB server started" 

ps x

