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

_x = logging.getLogger('registration.management.commands.deactivate_accounts')
_TASK_LOCK_PORT = getattr(settings, 'TASK_LOCK_PORT', {})


class Command(BaseCommand):
    help = """Deactivates accounts that have not been confirmed for over X days"""

    def handle(self, *args, **options):
        try:
            s = lock_socket(_TASK_LOCK_PORT.get("registration.deactivate_accounts", None))
            if not s:
                print "Another instance is running"
            print "Account deactivation started"
            from registration.models import UserProfile
            num = UserProfile.objects.deactivate_accounts()
            print "Account deactivation done. Number of accounts deactivated:", num
        except (KeyboardInterrupt, SystemExit):
            pass
        except Exception, e:
            print >> sys.stderr, "ERROR: %s" % e
            _x.exception(e)

