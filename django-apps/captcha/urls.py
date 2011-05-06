from django.conf.urls.defaults import *


urlpatterns = patterns('captcha.views',
    url(r'^serve/$', 'serve_captcha', name='captcha_image'),
)

