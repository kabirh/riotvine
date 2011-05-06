"""
High performance Web server from the CherryPy project.

Uses the wsgiserver package from http://svn.cherrypy.org/trunk/cherrypy/

"""
import os
import sys
from optparse import make_option

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--numthreads', dest='numthreads', default='30',
            help='Specifies the number of worker threads to create. Defaults to 30 threads.'),
        make_option('--daemonize', dest='daemonize', action='store_true',
            help='Runs the Web server in the background.'),
        make_option('--workdir', dest='workdir', default='.',
            help='Work directory to change to before daemonizing. Defaults to the current directory.'),
        make_option('--pidfile', dest='pidfile', default='',
            help='Specifies the file in which to write the PID.'),
        make_option('--urlpath', dest='urlpath', default='/',
            help='Specifies the URL path prefix to which the Web server responds. Defaults to /'),
        make_option('--servername', dest='servername',
            help="The string to set for WSGI's SERVER_NAME environment variable."),
    )
    help = """Runs the Django application under CherryPy's production quality Web server.

Requires CherryPy WSGIServer.

WARNING: This DOES NOT serve static media files.
"""
    args = '[optional port number, or ipaddr:port (defaults to 127.0.0.1:8000)]'

    def handle(self, addrport='', *args, **options):
        import django
        from django.core.handlers.wsgi import WSGIHandler
        if args:
            raise CommandError('Usage is runhttp %s' % self.args)
        if not addrport:
            addr = ''
            port = '8000'
        else:
            try:
                addr, port = addrport.split(':')
            except ValueError:
                addr, port = '', addrport
        if not addr:
            addr = '127.0.0.1'

        if not port.isdigit():
            raise CommandError("%r is not a valid port number." % port)

        numthreads = options.get('numthreads', '30')
        if not numthreads.isdigit():
            raise CommandError("%r is not a valid value for numthreads." % numthreads)

        port = int(port)
        numthreads = int(numthreads)
        
        print "Starting %s threads" % numthreads

        try:
            from cherrypy.wsgiserver import CherryPyWSGIServer
            from cherrypy.wsgiserver import WSGIPathInfoDispatcher
        except ImportError:
            try:
                from wsgiserver import CherryPyWSGIServer
                from wsgiserver import WSGIPathInfoDispatcher
            except ImportError, e:
                print >> sys.stderr, "ERROR: %s" % e
                print >> sys.stderr, "  Unable to load the wsgiserver package.  In order to run django's"
                print >> sys.stderr, "  high-performance web server, you will need to get wsgiserver from"
                print >> sys.stderr, "  http://svn.cherrypy.org/trunk/cherrypy/"
                print >> sys.stderr, "  Only the wsgiserver directory and its contents are required."
                print >> sys.stderr, "  If you've already installed wsgiserver, "
                print >> sys.stderr, "  make sure it is in your PYTHONPATH."
                return False

        #print "Validating models..."
        self.validate(display_num_errors=False)

        wsgi_apps = WSGIPathInfoDispatcher([(options.get('urlpath', '/'), WSGIHandler())])
        server = CherryPyWSGIServer((addr, port),
                    wsgi_apps,
                    numthreads=numthreads,
                    server_name=options.get('servername', None))

        daemonize = options.get('daemonize', False)

        if daemonize:
            from django.utils.daemonize import become_daemon
            workdir = options.get('workdir', '.')
            become_daemon(our_home_dir=workdir)
        else:
            print "HTTP server started on %s:%s" % (addr, port)
            print "Press Ctrl-C to stop the server."

        if options.get("pidfile", False):
            fp = open(options["pidfile"], "w")
            fp.write("%d\n" % os.getpid())
            fp.close()

        try:
            server.start()
        except (KeyboardInterrupt, SystemExit):
            server.stop()
