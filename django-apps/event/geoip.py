"""

Dependencies:
    http://code.google.com/p/pygeoip/
    http://code.google.com/p/geolocator/source/checkout

"""
import logging

import pygeoip
from geolocator import gislib

from django.conf import settings


_log = logging.getLogger('event.geoip')

"""
from event.geoip import *
r = RiotVineGeoIP()
p1 = '174.129.12.4'
p2 = '207.7.108.211'
p3 = '75.101.150.1'
p4 = '8.12.33.140'
p5 = '209.242.23.73'
p6 = '140.241.251.240'
n = r.nearest_location
n(p1)
n(p2)
n(p3)
n(p4)
n(p5)
n(p6)

# EC2: 174.129.12.4 
# EC2: 
# San Diego, CA: 207.7.108.211

>>> x.record_by_addr(ip)
{'city': 'Livonia', 'region_name': 'MI', 'area_code': 734, 'longitude': -83.3731
99999999997, 'country_code3': 'USA', 'latitude': 42.396800000000013, 'postal_cod
e': None, 'dma_code': 505, 'country_code': 'US', 'country_name': 'United States'}
"""
class RiotVineGeoIP(object):
    def nearest_location(self, ip_addr):
        """Return nearest supported location for this IP Address"""
        try:
            _log.debug("Geo IP mapping %s", ip_addr)
            if ',' in ip_addr:
                ip_addr = ip_addr.split(',')[:1][0]
            dist, loc = 10000, settings.LOCATION_DEFAULT
            gi = pygeoip.GeoIP(settings.LOCATION_GEOIP_PATH, pygeoip.MEMORY_CACHE)
            rec = gi.record_by_addr(ip_addr)
            if not rec:
                return loc
            cn = rec.get('country_code', '')
            if cn == 'US':
                # Find nearest supported city by lat, lng
                lat, lng = rec['latitude'], rec['longitude']                
                for lc, params in settings.LOCATION_DATA.iteritems():
                    llat, llng = params[:2]
                    d = gislib.getDistance((lat, lng), (llat, llng))
                    # print ">>>", lc, d
                    if d < dist:
                        dist, loc = d, lc
                # print "Nearest:", loc, dist
            return loc
        except Exception, e:
            _log.error("GeoIP error on %s", ip_addr)
            _log.exception(e)
            return settings.LOCATION_DEFAULT

