"""

Queue handler script for ActionItems

This is a standalone Django script that periodically
goes over open ActionItems and calls processors that complete each task 
defined by an ActionItem.

Basic algorithm:

    Fetch 25 new non-admin ActionItems.
    For each action item:
        Dispatch to action handler based on ActionItem.action
        If action was handled successfully, mark ActionItem.status as done.

"""

import os
import threading
import logging, logging.config
import sys
import getopt
import time
import socket
from datetime import datetime, timedelta

if not os.environ.get('DJANGO_SETTINGS_MODULE', False):
    os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

from django.conf import settings


# Configure logging here before we import any of our other classes that make use
# of a logger. If this is not done, the default logging configuration defined by 
# the web application gets invoked first.
threading.currentThread().setName('QProcessor') # Used by the logger
if not logging.getLogger().handlers:
    logging.config.fileConfig('./q_logging.conf')
    _x_root = logging.getLogger()
    _x_root.setLevel(settings.LOG_DEBUG and logging.DEBUG or logging.INFO)

_x = logging.getLogger('queue.processor')


from queue import registry


_MAX_RUN_TIME =  timedelta(minutes=settings.QUEUE_SCRIPT_MAX_TIME_MINUTES)


def do_process():
    """Dispatch open ActionItems to their respective processors.

    For each invocation of this function, handle as many objects as are 
    returned by one call to `ActionItem.objects.pop` (by default 25 items.) If 
    settings.QUEUE_SCRIPT_MAX_TIME_MINUTES has elapsed before all these items 
    are processed, return immediately.

    """
    from queue.models import ActionItem
    socket = _check_instance_ok()
    if not socket:
        return
    now = datetime.now()
    ActionItem.objects.cleanup() # Unlock old unprocessed/aborted tasks.
    actions = ActionItem.objects.pop() # Fetch 25 open ActionItems.
    actions_processed = [] # Hold PKs of processed items.
    for a in actions:
        processor = registry.get_processor(a.category)
        if processor:
            try:
                _x.debug("Performing %s", a)
                success = processor.perform_action(a)
                if success:
                    actions_processed.append(a.pk)
                else:
                    a.status = 'cant-perform'
                    a.save()
                    _x.debug("Action %s can not be performed. No handler for task in %s", a, processor)
            except Exception, e:
                _x.exception(e)
        if _MAX_RUN_TIME < datetime.now() - now:
            _x.warn('Could not finish script in %s minutes. Skipping remaining actions.' % settings.QUEUE_SCRIPT_MAX_TIME_MINUTES)
            break
    # Mark processed actions as `done`.
    if actions_processed:
        ActionItem.objects.filter(pk__in=actions_processed).update(status='done')
    n = len(actions_processed)
    if n > 0:
        _x.info('Actions processed %s', n)
    return n


def do_process_loop():
    _x.info('Queue processor started. Hit Ctrl-C to exit.')
    try:
        while True:
            do_process()
            # time.sleep(15) # Run every 15 seconds
            break
    except KeyboardInterrupt, k:
        pass
    finally:
        _x.info("Queue processor stopped.")


def _check_instance_ok():
    """Return True if this instance of the script is OK to be executed.

    If multiple instances of this script are not allowed to be run, 
    settings.QUEUE_SCRIPT_LOCK_PORT must be defined to be a TCP/IP port number.

    This method binds to that port number. If the bind call is successful,
    it means that this instance is the first one to start. Subsequent instances
    would fail to bind to this port and thus know that they are not the first 
    instance.

    """
    if not hasattr(settings, 'QUEUE_SCRIPT_LOCK_PORT'):
        # Multiple instances are allowed
        return True
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('', settings.QUEUE_SCRIPT_LOCK_PORT))
        return s
    except socket.error, e:
        _x.warn('Another instance is running.')
        _x.error(e)
        return None


class Usage(Exception):
    def __init__(self, msg):
        self.msg = msg


def run_script(argv=None):
    """Queue Processor
-h, --help      This help
"""
    if argv is None:
        argv = sys.argv
    try:
        try:
            opts, args = getopt.getopt(argv[1:], "h:", ["help"])
        except getopt.GetoptError, msg:
            raise Usage(msg)
        for o, a in opts:
            if o in ("-h", "--help"):
                print __doc__
                return 0
        do_process_loop()
        return 0
    except Usage, err:
        print >> sys.stderr, err.msg
        print >> sys.stderr, "For help, use --help"
        return 2


if __name__ == "__main__":
    sys.exit(run_script())

