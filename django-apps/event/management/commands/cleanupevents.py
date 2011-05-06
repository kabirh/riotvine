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
    logging.config.fileConfig('./cleanup_logging.conf')
    _x_root = logging.getLogger()
    _x_root.setLevel(logging.DEBUG)

_x = logging.getLogger('event.management.commands.cleanupevents')
_TASK_LOCK_PORT = getattr(settings, 'TASK_LOCK_PORT', {})


class Command(BaseCommand):
    help = """Runs event cleanup tasks"""

    def handle(self, *args, **options):
        try:
            s = lock_socket(_TASK_LOCK_PORT.get("event.cleanup", None))
            if not s:
                print "Another instance is running"
            print "Clean up started"
            from event.utils import cleanup
            from queue.models import ActionItem
            cleanup()
            ActionItem.objects.filter(status='done').delete()
            print "Clean up done"
        except (KeyboardInterrupt, SystemExit):
            pass
        except Exception, e:
            print >> sys.stderr, "ERROR: %s" % e
            _x.exception(e)

