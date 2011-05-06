"""

Google Checkout related functions.

"""
import logging
from sys import exc_info
from traceback import format_exception
import base64
import urllib2
import cgi

from django.utils.http import urlencode
from django.conf import settings


_log = logging.getLogger('payment.processor.google')


def validate_merchant(google_merchant_id, google_merchant_key):
    """Send a `hello` post to Google to verify that the supplied id and key are valid.

    Return ``True`` if the Google handshake was successful. Return ``False``, otherwise.

    """
    try:
        url = settings.GOOGLE_VALIDATION_URL + google_merchant_id
        auth_key = base64.encodestring('%s:%s' % (google_merchant_id, google_merchant_key)).strip()
        req = urllib2.Request(url, urlencode({'_type':'hello'}))
        req.add_header("Authorization", "Basic %s" % auth_key)
        req.add_header("Content-type", "application/xml;charset=UTF-8")
        req.add_header("Accept", "application/xml;charset=UTF-8")
        resp = urllib2.urlopen(req)
        ret = resp.read()
        resp.close()
        ret_list = cgi.parse_qsl(ret)
        return ('_type', 'bye') in ret_list
    except urllib2.URLError, e:
        _log.exception(''.join(format_exception(*exc_info())))
        return False


def verify_ipn_request(request, google_merchant_id, google_merchant_key):
    """Verify that the IPN came genuinely from Google.

    ``request`` is the HTTP request that was issued to this site's IPN URL.

    """
    try:
        auth_header = request.META['HTTP_AUTHORIZATION']
        auth_type, auth_key = auth_header.split()
        if auth_type != 'Basic':
            return False
        computed_auth_key = base64.encodestring('%s:%s' % (google_merchant_id, google_merchant_key)).strip()
        if computed_auth_key != auth_key:
            _log.debug("Computed auth key (%s) did not match received auth key (%s)", computed_auth_key, auth_key) 
            return False
    except KeyError:
        return False
    except:
        _log.exception(''.join(format_exception(*exc_info())))
        return False
    return True

