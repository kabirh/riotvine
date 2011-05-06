from django.conf.urls.defaults import *


urlpatterns = patterns('fsq.views',
    url(r'^$', 'fsq_home', name='fsq_home'),
 )

# OAuth
urlpatterns += patterns('fsq.views',
    url(r'^oauth_authorize/$', 'oauth_authorize', name='fsq_authorize'),
    url(r'^oauth_callback/$', 'oauth_callback', name='fsq_callback'),
)
