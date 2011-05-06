#!/bin/bash

export HM=/home/illiusrock
export PY=$HM/site-packages
export PATH=/opt/manual/sbin:/opt/manual/bin:/opt/local/bin:/opt/local/sbin:/usr/xpg4/bin:/usr/bin:/usr/sbin:/usr/sfw/bin:/usr/openwin/bin:/opt/SUNWspro/bin:/usr/ccs/bin
export PYTHONPATH=$PY/local:$PY/irock/irock:$PY/irock/django-apps:$PY/django-svn:$PY/tpl
export DJANGO_SETTINGS_MODULE=settings
export PYTHON=/opt/manual/bin/python

cd $PY/irock/irock
pwd
$PYTHON ../django-apps/lastfm/fetch_events.pyc

/usr/xpg4/bin/tail -n 10 /tmp/irock_lastfm.log
echo "last.fm data loaded"
