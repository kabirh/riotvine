from django.conf.urls.defaults import *


urlpatterns = patterns('fb.views',
    url(r'^xd-receiver/$', 'xd_receiver', name='fb_xd_receiver'),
    url(r'^fb-login/$', 'fb_login', name='fb_login'),
    url(r'^fb-login-mobile/$', 'fb_login_mobile', name='fb_login_mobile'),
    url(r'^fb-connect/$', 'fb_connect', name='fb_connect'),
    url(r'^manage-friends/$', 'manage_friends', name='fb_manage_friends'),
    url(r'^invite-friends/$', 'invite_friends', name='fb_invite_friends'),
    url(r'^invited-friends/$', 'invited_friends', name='fb_invited_friends'),
)

