from django.contrib.sites.models import Site
from django.conf import settings


DISPLAY_SITE_URL = u'http://%s/' % settings.DISPLAY_SITE_DOMAIN
#_domain = Site.objects.get_current().domain

def site_url():
    return u'http://%s' % settings.DISPLAY_SITE_DOMAIN


def site_secure_url():
    return u'https://%s' % settings.DISPLAY_SITE_DOMAIN
secure_site_url = site_secure_url # just an alias

