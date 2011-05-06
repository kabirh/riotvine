from django.conf.urls.defaults import *


urlpatterns = patterns('event.views',
    # SEO views
    url(r'^(?P<artist_url>[_0-9a-zA-Z\-]+)/show/(?P<event_url>[_0-9a-zA-Z\-]+)/$', 'view_seo', name='view_event_seo'),
)


