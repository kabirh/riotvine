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

_x = logging.getLogger('event.management.commands.build_autoprofiles')
_TASK_LOCK_PORT = getattr(settings, 'TASK_LOCK_PORT', {})


class Command(BaseCommand):
    help = """Turn last.fm events to auto-profile events"""

    def handle(self, *args, **options):
        try:
            s = lock_socket(_TASK_LOCK_PORT.get("event.autoprofiles", None))
            if not s:
                print "Another instance is running"
            print "Auto profile builder started"
            from event.import_utils import make_autoprofiles
            make_autoprofiles(**options)
            print "Auto profiles done"
        except (KeyboardInterrupt, SystemExit):
            pass
        except Exception, e:
            print >> sys.stderr, "ERROR: %s" % e
            _x.exception(e)

