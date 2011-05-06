'''
from twitter import TwitterAPI as T
t = T()
x = t.get_unauthorised_request_token()
print x
t.close()
'''
import logging
import oauth
import httplib
from urlparse import urlparse
import time
import datetime
import os

from django.utils.encoding import smart_str
from django.conf import settings


_log = logging.getLogger('twitter.views')

PROTOCOL = (settings.DEV_MODE and os.name == 'nt') and 'http' or 'https'

SERVER = getattr(settings, 'TWITTER_OAUTH_SERVER', 'twitter.com')
REQUEST_TOKEN_URL = getattr(settings, 'TWITTER_OAUTH_REQUEST_TOKEN_URL', '%s://%s/oauth/request_token' % (PROTOCOL, SERVER))
ACCESS_TOKEN_URL = getattr(settings, 'TWITTER_OAUTH_ACCESS_TOKEN_URL', '%s://%s/oauth/access_token' % (PROTOCOL, SERVER))
AUTHORIZATION_URL = getattr(settings, 'TWITTER_OAUTH_AUTHORIZATION_URL', '%s://%s/oauth/authorize' % (PROTOCOL, SERVER))
CALLBACK_URL = getattr(settings, 'TWITTER_OAUTH_CALLBACK_URL', None)

CONSUMER_KEY = getattr(settings, 'TWITTER_CONSUMER_KEY', 'YOUR_CONSUMER_KEY')
CONSUMER_SECRET = getattr(settings, 'TWITTER_CONSUMER_SECRET', 'YOUR_CONSUMER_SECRET')

USER_PROFILE_URL = '%s://twitter.com/account/verify_credentials.json' % PROTOCOL
STATUS_POST_URL = '%s://twitter.com/statuses/update.json' % PROTOCOL

CONSUMER = oauth.OAuthConsumer(CONSUMER_KEY, CONSUMER_SECRET)
signature_method = oauth.OAuthSignatureMethod_HMAC_SHA1()
HEADERS = {
    'User-Agent':settings.USER_AGENT
}


class OAuthAPI(object):

    def __init__(self, server=None, callback_url=None, request_token_url=None, auth_url=None, access_token_url=None, consumer=None, user_profile_url=None, status_post_url=None, headers=None, ssl=True):
        self.server = server or SERVER
        _log.debug("OAuth connecting to %s", self.server)
        proxy = os.getenv('HTTP_PROXY', None)
        if proxy:
            p = urlparse(proxy)
            self.connection = httplib.HTTPConnection(p.hostname, p.port, strict=False)
        else:
            if ssl:
                self.connection = httplib.HTTPSConnection(self.server)
            else:
                self.connection = httplib.HTTPConnection(self.server)
        # self.connection.connect()
        self.callback_url = callback_url or CALLBACK_URL
        self.request_token_url = request_token_url or REQUEST_TOKEN_URL
        self.auth_url = auth_url or AUTHORIZATION_URL
        self.access_token_url = access_token_url or ACCESS_TOKEN_URL
        self.consumer = consumer or CONSUMER
        self.user_profile_url = user_profile_url or USER_PROFILE_URL
        self.status_post_url = status_post_url or STATUS_POST_URL
        self.headers = headers or HEADERS

    def close(self):
        self.connection.close()

    def __del__(self):
        self.connection.close()

    # Shortcut around oauth.OauthRequest
    def request(self, url, access_token, parameters=None, http_method='GET'):
        """
        usage: request( '/url/', your_access_token, parameters=dict() )
        Returns a OAuthRequest object
        """
        _log.debug("OAuth URL: %s", url)
        if not isinstance(access_token, oauth.OAuthToken):
            access_token = oauth.OAuthToken.from_string(access_token)
        oauth_request = oauth.OAuthRequest.from_consumer_and_token(
            self.consumer, token=access_token, http_method=http_method, http_url=url, parameters=parameters
        )
        oauth_request.sign_request(signature_method, self.consumer, access_token)
        return oauth_request

    def fetch_response(self, oauth_request):
        if oauth_request.http_method == 'POST':
            headers = {'Content-Type':'application/x-www-form-urlencoded'}
            headers.update(self.headers)
            self.connection.request(oauth_request.http_method, oauth_request.get_normalized_http_url(), body=oauth_request.to_postdata(), headers=headers)
        else:
            http_method, url = oauth_request.http_method, oauth_request.to_url()            
            _log.debug("Fetching OAuth response: %s > %s\n%s", http_method, url, self.headers)
            self.connection.request(http_method, url, headers=self.headers)
        response = self.connection.getresponse()
        s = response.read()
        return s

    def get_unauthorised_request_token(self):
        parameters = {}
        if self.callback_url:
            parameters['oauth_callback'] = self.callback_url
        _log.debug("Getting unauth token: %s", self.request_token_url)
        oauth_request = oauth.OAuthRequest.from_consumer_and_token(
            self.consumer, http_url=self.request_token_url, parameters=parameters
        )
        oauth_request.sign_request(signature_method, self.consumer, None)
        resp = self.fetch_response(oauth_request)
        token = oauth.OAuthToken.from_string(resp)
        return token

    def get_authorisation_url(self, token):
        parameters = {}
        # if CALLBACK_URL:
        #    parameters['oauth_callback'] = CALLBACK_URL
        oauth_request = oauth.OAuthRequest.from_consumer_and_token(
            self.consumer, token=token, http_url=self.auth_url, parameters=parameters
        )
        oauth_request.sign_request(signature_method, self.consumer, token)
        return oauth_request.to_url()

    def exchange_request_token_for_access_token(self, request_token, oauth_verifier=None):
        parameters = {}
        if oauth_verifier:
            parameters['oauth_verifier'] = oauth_verifier
        oauth_request = oauth.OAuthRequest.from_consumer_and_token(
            self.consumer, token=request_token, http_url=self.access_token_url, parameters=parameters
        )
        oauth_request.sign_request(signature_method, self.consumer, request_token)
        resp = self.fetch_response(oauth_request)
        return oauth.OAuthToken.from_string(resp)


class TwitterAPI(OAuthAPI):
    def get_url(self, access_token, url):
        oauth_request = self.request(url, access_token)
        response_str = self.fetch_response(oauth_request)
        return response_str

    def get_profile(self, access_token):
        oauth_request = self.request(self.user_profile_url, access_token)
        profile = self.fetch_response(oauth_request)
        return profile

    def post_status(self, access_token, status_text):
        """Post user's status to Twitter"""
        if not status_text:
            return None 
        status_text = smart_str(status_text[:140])
        oauth_request = self.request(self.status_post_url, access_token, {'status':status_text}, http_method='POST')
        status = self.fetch_response(oauth_request)
        return status

