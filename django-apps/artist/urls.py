from django.conf.urls.defaults import *
from artist.views import ArtistRegistrationFormWizard

urlpatterns = patterns('artist.views',
    url(r'^$', 'admin', name='artist_admin'),
    # url(r'^register/$', 'register', {'ssl':True}, name='register_artist'),
    url(r'^update-profile/$', 'update_profile', {'ssl':True}, name='update_artist_profile'),
)

urlpatterns += patterns('rdutils.url',
    url(r'^register/$', 'call_view_class', {'class':ArtistRegistrationFormWizard, 'ssl':True}, name='register_artist'),
)
