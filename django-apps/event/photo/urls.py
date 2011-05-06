from django.conf.urls.defaults import *


urlpatterns = patterns('event.photo.views',
    url(r'^(?P<event_id>[0-9]+)/$', 'list_photos', name='list_event_photos'),
    url(r'^(?P<event_id>[0-9]+)/upload/$', 'upload', name='upload_event_photo'),
    url(r'^(?P<event_id>[0-9]+)/member-upload/$', 'member_upload', name='upload_event_photo_member'),
    url(r'^(?P<event_id>[0-9]+)/edit/$', 'edit', name='edit_event_photos'),
    url(r'^(?P<event_id>[0-9]+)/delete/$', 'delete', name='delete_event_photo'),
    url(r'^(?P<thumbnail_id>[0-9]+)/view/$', 'view', name='view_event_photo'),
)

