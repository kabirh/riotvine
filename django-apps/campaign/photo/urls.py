from django.conf.urls.defaults import *


urlpatterns = patterns('campaign.photo.views',
    url(r'^(?P<campaign_id>[0-9]+)/$', 'list_photos', name='list_campaign_photos'),
    url(r'^(?P<campaign_id>[0-9]+)/upload/$', 'upload', name='upload_campaign_photo'),
    url(r'^(?P<campaign_id>[0-9]+)/edit/$', 'edit', name='edit_campaign_photos'),
    url(r'^(?P<thumbnail_id>[0-9]+)/view/$', 'view', name='view_photo'),
)

