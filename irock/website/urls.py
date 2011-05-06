from django.conf.urls.defaults import *


urlpatterns = patterns('',
    url(r'^$', 'website.views.homepage', name='home'),
    url(r'^test/$', 'website.views.test', name='test'),
)

