from django.conf.urls.defaults import *


urlpatterns = patterns('linker.views',
    url(r'^(?P<url>[a-z\-]+)/$', 'link_redirect', name='lnk_redirect'),
)

