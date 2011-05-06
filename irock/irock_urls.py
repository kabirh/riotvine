from django.conf.urls.defaults import *
from django.contrib import admin
from django.conf import settings


admin.autodiscover()

urlpatterns = patterns('',
    url(r'^%s/(.*)' % settings.ADMIN_BASE[1:], admin.site.root, {'ssl':True}),
    url(r'^r/', include('django.conf.urls.shortcut')),
    url(r'^comments/', include('django.contrib.comments.urls')),
)

if settings.DEV_MODE:
    urlpatterns += patterns('',
        (r'^media/ui/(?P<path>.*)$', 'django.views.static.serve', {'document_root':settings.MEDIA_ROOT + settings.UI_ROOT}),
        (r'^media/(?P<path>.*)$', 'django.views.static.serve', {'document_root':settings.MEDIA_ROOT}),
    )
    # Django servers Admin media
    # only when we use the built-in development server through ``manage.py runserver``.
    # In DEV_MODE, the CherryPy WSGI server invocation needs to ensure that 
    # Admin media is served. The following code ensures that this is done.
    if hasattr(settings, 'DEV_ADMIN_MEDIA_ROOT'):
        urlpatterns += patterns('',
            (r'^%s/(?P<path>.*)$' % settings.ADMIN_MEDIA_PREFIX[1:-1], 'django.views.static.serve', {'document_root':settings.DEV_ADMIN_MEDIA_ROOT}),
        )

urlpatterns += patterns('',
    (r'^', include('website.urls')),
    (r'^lnk/', include('linker.urls')),
    (r'^captcha/', include('captcha.urls')),
    (r'^accounts/', include('registration.urls')),
    (r'^artist/', include('artist.urls')),
    (r'^campaign/', include('campaign.urls')),
    (r'^event/', include('event.urls')),
    (r'^messages/', include('messages.urls')),
    (r'^fb/', include('fb.urls')),
    (r'^foursquare/', include('fsq.urls')),
#    (r'^campaign/', include('campaign.seo_urls')),
#    (r'^show/', include('event.seo_urls')),
)

if 'twitter' in settings.INSTALLED_APPS:
    urlpatterns += patterns('',
        (r'^twitter/', include('twitter.urls')),
    )

urlpatterns += patterns('django.views.i18n',
    url(r'^js/i18n/$', 'javascript_catalog', name='catalog_jsi18n'),
)

# Ensure that the artist URL pattern is the last one below
# so that the artist can never choose a URL that's registered by one of the above
# application.
urlpatterns += patterns('',
    url(r'^', include('campaign.seo_urls')),
    url(r'^', include('event.seo_urls')),
    url(r'^event-feeds/', include('event.feed_urls')),
    url(r'^(?P<username>[0-9a-zA-Z\-\_]+)/$', 'registration.views.profile_page', name='user_profile'),
)

