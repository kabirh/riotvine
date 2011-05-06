"""

PayPal related functions.

"""
import logging
import urllib2

from django.utils.http import urlencode
from django.conf import settings


_log = logging.getLogger('payment.processor.paypal')


def validate_merchant(paypal_email):
    return True # Not implemented yet


def verify_ipn_request(request):
    """Verify that the IPN came genuinely from PayPal.

    ``request`` is the HTTP request that was issued to this site's IPN URL.

    """
    data = request.POST
    newparams = {}
    for key in data.keys():
        newparams[key] = data[key]
    newparams['cmd'] = "_notify-validate"
    params = urlencode(newparams)
    # Post back to PayPal and receive the response string "VERIFIED" to 
    # confirm the authenticity of the IPN.
    req = urllib2.Request(settings.PAYPAL_IPN_POST_URL, params)
    req.add_header("Content-type", "application/x-www-form-urlencoded")
    resp = urllib2.urlopen(req)
    ret = resp.read()
    resp.close()
    if ret == "VERIFIED":
        _log.debug("PayPal IPN data verification was successful.")
    else:
        _log.error("PayPal IPN data verification failed %s, %s", ret, params)
        return False
    return True

