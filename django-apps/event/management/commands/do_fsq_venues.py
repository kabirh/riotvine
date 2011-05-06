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
    logging.config.fileConfig('./amqp_logging.conf')
    _x_root = logging.getLogger()
    _x_root.setLevel(logging.DEBUG)

_x = logging.getLogger('event.management.commands.event.do_fsq_venues')
_TASK_LOCK_PORT = getattr(settings, 'TASK_LOCK_PORT', {})


class Command(BaseCommand):
    help = """Runs event cleanup tasks"""

    def handle(self, *args, **options):
        try:
            s = lock_socket(_TASK_LOCK_PORT.get("event.do_fsq_venues", None))
            if not s:
                print "Another instance of event.do_fsq_venues is running"
                return
            from event.utils import do_foursquare_venues
            num, err = do_foursquare_venues()
            if num or err:
                print "Processed %s fsq venues with %s errors" % (num, err)
        except (KeyboardInterrupt, SystemExit):
            pass
        except Exception, e:
            print >> sys.stderr, "ERROR: %s" % e
            _x.exception(e)

