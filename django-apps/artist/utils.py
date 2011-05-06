import logging
import time
import urllib
from boto.connection import AWSQueryConnection
import xml.etree.ElementTree as ET

from django.conf import settings
from django.core.urlresolvers import resolve, Resolver404
from django.contrib.flatpages.models import FlatPage

from rdutils.cache import shorten_key, cache


_log = logging.getLogger('artist.utils')
_AWS_ECS_NAMESPACE = getattr(settings, 'AWS_ECS_NAMESPACE', "http://webservices.amazon.com/AWSECommerceService/2008-08-19")


def is_artist_url_available(url, user_profile=None):
    """Check that ``url`` is not already in use.

    A ``url`` is in use if it's been taken by another artist or 
    it's being used internally by this web application.

    Furthermore, ``url`` must resolve to the artist homepage view.

    """
    from artist.models import ArtistProfile
    from artist.views import home
    # Check if this URL maps to internal site features.
    rel_url = '/%s/' % url.lower()
    f = FlatPage.objects.filter(url__iexact=rel_url).count()
    if f > 0: # URL maps to a flatpage.
        return False
    try:
        fn_tuple = resolve(rel_url)
        # Ensure that the url resolves to the artist home view.
        if fn_tuple[0] != home:
            return False
    except Resolver404:
        return False
    # Check if another artist has claimed this url.
    q = ArtistProfile.objects.filter(url=url)
    if user_profile:
        q = q.exclude(user_profile=user_profile)
    match = q.count()
    is_url_available = match == 0
    return is_url_available


def get_ecs_response(params):
    """Call Amazon ECS with the given parameters and return the raw XML response"""
    try:
        aws_conn = AWSQueryConnection(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            is_secure=False,
            host='ecs.amazonaws.com',
        )
        aws_conn.SignatureVersion = '2'
        base_params = dict(
            Service='AWSECommerceService',
            Version='2008-08-19',
            SignatureVersion=aws_conn.SignatureVersion,
            AWSAccessKeyId=settings.AWS_ACCESS_KEY_ID,
            AssociateTag=settings.AWS_ASSOCIATE_TAG,
            Operation='ItemSearch',
            IdType='ASIN',
            ResponseGroup='Small',
            Timestamp=time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
        )
        if params:
            base_params.update(params)
        verb = 'GET'
        path = '/onca/xml'
        qs, signature = aws_conn.get_signature(base_params, verb, path)
        qs = path + '?' + qs + '&Signature=' + urllib.quote(signature)
        time.sleep(0.5) # throttle
        response = aws_conn._mexe(verb, qs, None, headers={})
        resp = response.read()
        _log.debug("ECS Response: %s", resp)
        return resp
    except Exception, e:
        _log.debug("AWS ASIN call failed for params: %s", params)
        _log.debug(e)
        return u''


def get_asins_from_xml(xml, artist=None):
    """Parse ECS XML and return ASINS found. Return an empty list otherwise.

    Log the full XML response when list is empty.

    """
    try:
        tree = ET.XML(xml)
        nsmap = {'ns':_AWS_ECS_NAMESPACE}
        asins =  tree.findall("{%(ns)s}Items/{%(ns)s}Item/{%(ns)s}ASIN" % nsmap)
        if asins:
            if artist:
                # only include asins where artist is the MP3 creator
                asins = []
                for item in tree.findall("{%(ns)s}Items/{%(ns)s}Item" % nsmap):
                    c = item.findtext("{%(ns)s}ItemAttributes/{%(ns)s}Creator" % nsmap)
                    if c and c.lower() == artist.lower():
                        asin = item.findtext("{%(ns)s}ASIN" % nsmap)
                        asins.append(asin)
            else:
                asins = [a.text for a in asins]
        else:
            asins = []
        return asins
    except Exception, e:
        _log.debug("AWS ASIN return XML could not be parsed:\n%s\n", xml)
        _log.debug(e)
        return []


def get_asins(artist, force=False):
    """Get AWS ASIN ID list for artist name"""
    cache_key = shorten_key('artist:asin:%s' % artist)
    value = cache.cache.get(cache_key, None)
    if value is None or force:
        params = dict(
            SearchIndex='MP3Downloads',
            Sort='-releasedate',
            Keywords='"%s"' % artist,
        )
        xml = get_ecs_response(params)
        value = xml and get_asins_from_xml(xml, artist) or []
        cache.cache.set(cache_key, value, 24*3600) # cache for 24 hours
    return value

