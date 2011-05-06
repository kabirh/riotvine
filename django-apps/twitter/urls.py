from django.conf.urls.defaults import *


urlpatterns = patterns('twitter.views',
    url(r'^authorize/$', 'authorize', name='twitter_authorize'),
    url(r'^callback/$', 'callback', name='twitter_callback'),
    url(r'^post-status/$', 'post_status', name='twitter_post_status'),
)

