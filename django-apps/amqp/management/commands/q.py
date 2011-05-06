import logging
import logging.config
import os
import sys
import time
from optparse import make_option

from django.core.management.base import BaseCommand, CommandError


if not logging.getLogger().handlers:
    logging.config.fileConfig('./amqp_logging.conf')
    _x_root = logging.getLogger()
    _x_root.setLevel(logging.DEBUG)

_x = logging.getLogger('amqp.management.commands.q')


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--daemonize', dest='daemonize', default='False',
            help='True/False. Runs the process in the background. Defaults to False.'),
        make_option('--pidfile', dest='pidfile', default='',
            help='Specifies the file in which to write the PID.'),
    )
    help = """Starts, stops, or purges the named queue"""
    args = 'module.queue_name start/stop/purge'
    
    def handle(self, qname=None, start_stop='start', *args, **options):
        if args or start_stop not in ('start', 'stop', 'purge') or not qname:
            raise CommandError('Usage is %s' % self.args)
        mod, qname = qname.split('.')
        mod = '%s.amqp.queues' % mod
        queues = __import__(mod, globals(), locals(), [''])
        qclass = getattr(queues, qname)
        try:
            if start_stop == 'start':
                print "%s started" % qname
                daemonize = options.get('daemonize', False)
                daemonize = daemonize in (True, 1, 'TRUE', 'True', 'true', 'y', 'Y', 'yes', 'Yes', 'YES')
                if daemonize:
                    from django.utils.daemonize import become_daemon
                    workdir = options.get('workdir', '.')
                    become_daemon(our_home_dir=workdir)                
                if options.get("pidfile", False):
                    fp = open(options["pidfile"], "w")
                    fp.write("%d\n" % os.getpid())
                    fp.close()
                q = qclass().listen()
            elif start_stop == 'purge':
                q = qclass(bind_queue=False).purge()
                time.sleep(1) # give the message a chance to transmit
                print "Queue %s purged" % qname
            else:
                q = qclass(bind_queue=False).stop()
                time.sleep(1) # give the message a chance to transmit
                print "%s stop message sent" % qname
        except (KeyboardInterrupt, SystemExit):
            pass
        except Exception, e:
            print >> sys.stderr, "ERROR: %s" % e
            _x.exception(e)

