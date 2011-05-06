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

_x = logging.getLogger('event.management.commands.import_parties')
_TASK_LOCK_PORT = getattr(settings, 'TASK_LOCK_PORT', {})


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--location', dest='location', default='austin'),
        make_option('--venue_city', dest='venue_city', default='Austin'),
        make_option('--venue_state', dest='venue_state', default='TX'),
        make_option('--venue_zip', dest='venue_zip', default=''),
        make_option('--event_source', dest='event_source', default='sxsw-party'),
        make_option('--geoloc', dest='geoloc', default='30.27,-97.74'),
    )
    help = """Imports parties from a spreadsheet"""

    def handle(self, filepath, hashtag, *args, **options):
        try:
            s = lock_socket(_TASK_LOCK_PORT.get("event.import", None))
            if not s:
                print "Another instance is running"
            print "Import started from", filepath
            from event.import_utils import import_parties
            options['hashtag'] = hashtag
            print options
            import_parties(filepath, **options)
            print "Import done"
        except (KeyboardInterrupt, SystemExit):
            pass
        except Exception, e:
            print >> sys.stderr, "ERROR: %s" % e
            _x.exception(e)

