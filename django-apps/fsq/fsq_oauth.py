""" Foursquare OAuth API"""
import logging
import oauth
import httplib
from urlparse import urlparse
import time
import datetime
import os

from django.utils.encoding import smart_str
from django.conf import settings

from twitter import TwitterAPI


_log = logging.getLogger('fsq.oauth')


PROTOCOL = 'http'

SERVER = getattr(settings, 'FOURSQUARE_OAUTH_SERVER', 'foursquare.com')
REQUEST_TOKEN_URL = getattr(settings, 'FOURSQUARE_OAUTH_REQUEST_TOKEN_URL', '%s://%s/oauth/request_token' % (PROTOCOL, SERVER))
ACCESS_TOKEN_URL = getattr(settings, 'FOURSQUARE_OAUTH_ACCESS_TOKEN_URL', '%s://%s/oauth/access_token' % (PROTOCOL, SERVER))
AUTHORIZATION_URL = getattr(settings, 'FOURSQUARE_OAUTH_AUTHORIZATION_URL', '%s://%s/oauth/authorize' % (PROTOCOL, SERVER))
CALLBACK_URL = getattr(settings, 'FOURSQUARE_OAUTH_CALLBACK_URL', None)

CONSUMER_KEY = getattr(settings, 'FOURSQUARE_CONSUMER_KEY', 'YOUR_CONSUMER_KEY')
CONSUMER_SECRET = getattr(settings, 'FOURSQUARE_CONSUMER_SECRET', 'YOUR_CONSUMER_SECRET')

USER_PROFILE_URL = '%s://api.foursquare.com/v1/user.json' % PROTOCOL

CONSUMER = oauth.OAuthConsumer(CONSUMER_KEY, CONSUMER_SECRET)
HEADERS = {
    'User-Agent':settings.FOURSQUARE_USER_AGENT
}

class FoursquareOAuthAPI(TwitterAPI):

    def __init__(self, server=None, callback_url=None, request_token_url=None, auth_url=None, access_token_url=None, consumer=None, user_profile_url=None, status_post_url=None, headers=None):
        super(FoursquareOAuthAPI, self).__init__(
                server=server or SERVER,
                callback_url=callback_url or CALLBACK_URL,
                request_token_url=request_token_url or REQUEST_TOKEN_URL,
                auth_url=auth_url or AUTHORIZATION_URL,
                access_token_url=access_token_url or ACCESS_TOKEN_URL,
                consumer=consumer or CONSUMER,
                user_profile_url=user_profile_url or USER_PROFILE_URL,
                headers=headers or HEADERS,
                ssl=PROTOCOL == 'https',
        )        
    
