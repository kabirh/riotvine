import socket


def lock_socket(port=None):
    """Return a socket listening to the port given by settings.setting_name"""
    if not port:
        return True # lock not needed
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('', port))
        s.listen(1)
        return s
    except socket.error, e:
        return None


def chunks(l, n):
    """ Yield successive n-sized chunks from l.
    """
    for i in xrange(0, len(l), n):
        yield l[i:i+n]
