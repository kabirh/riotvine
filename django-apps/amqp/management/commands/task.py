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

_x = logging.getLogger('amqp.management.commands.task')


_TASK_LOCK_PORT = getattr(settings, 'TASK_LOCK_PORT', {})


class Command(BaseCommand):
    help = """Runs an AMQP task"""
    args = 'module.task_name'

    def handle(self, task_name=None, *args, **options):
        try:
            if not task_name:
                raise CommandError('Usage is %s' % self.args)
            mod, task = task_name.split('.')
            mod = '%s.amqp.tasks' % mod
            tasks = __import__(mod, globals(), locals(), [''])
            s = lock_socket(_TASK_LOCK_PORT.get(task_name, None))
            if not s:
                print "Another instance is running"
            fn = getattr(tasks, task)
            fn()
            time.sleep(3) # give the task a chance to get flushed
            print "Task initiated"
        except (KeyboardInterrupt, SystemExit):
            pass
        except Exception, e:
            print >> sys.stderr, "ERROR: %s" % e
            _x.exception(e)

