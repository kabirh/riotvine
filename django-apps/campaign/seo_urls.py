from django.conf.urls.defaults import *


urlpatterns = patterns('campaign.views',
    # SEO views
    url(r'^(?P<artist_url>[0-9a-zA-Z\-]+)/campaign/(?P<campaign_url>[0-9a-zA-Z\-]+)/$', 'view_seo', name='view_campaign_seo'),
)


