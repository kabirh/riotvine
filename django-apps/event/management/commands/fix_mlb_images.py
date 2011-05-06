import logging
import logging.config
import os
import sys
import time
from optparse import make_option

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from rdutils import lock_socket


if not logging.getLogger().handlers:
    logging.config.fileConfig('./lastfm_logging.conf')
    _x_root = logging.getLogger()
    _x_root.setLevel(logging.DEBUG)

_x = logging.getLogger('event.management.commands.import_mlb')
_TASK_LOCK_PORT = getattr(settings, 'TASK_LOCK_PORT', {})


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--event_source', dest='event_source', default='mlb2010'),
        make_option('--geoloc', dest='geoloc', default='42.63699,-71.549835'),
    )
    help = """Fixes MLB event images based on home team name"""

    def handle(self, metapath, *args, **options):
        try:
            s = lock_socket(_TASK_LOCK_PORT.get("event.import", None))
            if not s:
                print "Another instance is running"
            print "Import started from", metapath
            from event.import_utils import fix_mlb_images as do_mlb_fix
            print options
            do_mlb_fix(metapath, **options)
            print "Import done"
        except (KeyboardInterrupt, SystemExit):
            pass
        except Exception, e:
            print >> sys.stderr, "ERROR: %s" % e
            _x.exception(e)

