"""

Middleware classes to support mobile devices.

"""
import logging
from datetime import datetime, timedelta

from django.conf import settings


_log = logging.getLogger('mobile.middleware')


class MobileMiddleware(object):
    """Detect supported mobile phone and set request attributes `mobile` and `mobile_type`."""
    
    def process_request(self, request):
        ua = request.META.get("HTTP_USER_AGENT", None)
        request.mobile = False
        request.mobile_type = None
        request.mobile_available  = False
        if request.REQUEST.get("mobile", '') == 'y':
            request.session['mobile'] = True
        elif request.REQUEST.get("mobile", '') == 'n':
            request.session['mobile'] = False
        if ua:
            ua2 = ua.lower()
            for s, mtype in settings.MOBILE_USER_AGENTS:
                if s in ua2:
                    request.mobile = True
                    request.mobile_available = True
                    request.mobile_type = mtype
                    break
        if not request.mobile:
            # domain name is m.riotvine.com, force mobile = True
            http_host = request.get_host()
            if http_host:
                cx = http_host.lower().split(".")
                if len(cx) > 2 and cx[0] == 'm':
                    request.mobile = True
                    request.mobile_type = 'unknown'
        if 'mobile' in request.session:
            # user has explicitly set a mobile preference; respect it.
            if request.session['mobile']:
                request.mobile = True
                if not request.mobile_type: # preserve auto-detected type, if available
                    request.mobile_type = 'unknown'
            else:
                request.mobile = False
                request.mobile_type = None

