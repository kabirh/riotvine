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
    logging.config.fileConfig('./4sq_logging.conf')
    _x_root = logging.getLogger()
    _x_root.setLevel(logging.DEBUG)

_x = logging.getLogger('event.management.commands.connect_4sq')
_TASK_LOCK_PORT = getattr(settings, 'TASK_LOCK_PORT', {})


class Command(BaseCommand):
    help = """Connect user profiles with their foursquare user ids"""

    def handle(self, *args, **options):
        try:
            s = lock_socket(_TASK_LOCK_PORT.get("foursquare.connect", None))
            if not s:
                print "Another instance is running"
            from fsq.utils import connect_uids
            connect_uids(**options)
        except (KeyboardInterrupt, SystemExit):
            pass
        except Exception, e:
            print >> sys.stderr, "ERROR: %s" % e
            _x.exception(e)

