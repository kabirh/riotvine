from django.conf.urls.defaults import *
from django.contrib.auth.forms import SetPasswordForm

from registration.forms import MobileAuthenticationForm


urlpatterns = patterns('',
    url(r'^signup-step1/$', 'registration.views.signup_step1', name='signup'),
    url(r'^signup-step2/$', 'registration.views.signup_step2', name='signup_step2'),
    url(r'^sign-in/$', 'registration.views.signup_step2', {'existing_user':True}, name='signin'),
    url(r'^account/$', 'registration.views.account', name='account'),
    url(r'^login/$', 'django.contrib.auth.views.login', name='login'),
    url(r'^mobile/login/$', 'django.contrib.auth.views.login', {'template_name':'mobile/registration/login.html', 'authentication_form':MobileAuthenticationForm}, name='mobile_login'),
    url(r'^logout/$', 'django.contrib.auth.views.logout', {'next_page':'/'}, name='logout'),
    url(r'^password-change/$', 'django.contrib.auth.views.password_change', {'password_change_form':SetPasswordForm}, name='change_password'),
    url(r'^password-change/done/$', 'django.contrib.auth.views.password_change_done', name='change_password_done'),
    url(r'^register/$', 'registration.views.register', name='register'),
    url(r'^registration-complete/$', 'registration.views.registration_complete', name='registration_complete'),
    url(r'^update-user-profile/$', 'registration.views.update_user_profile', name='update_user_profile'),
    url(r'^mailing-list/$', 'registration.views.mailing_list', {'ssl':True}, name='mailing_list'),
    url(r'^friends/$', 'registration.views.friends', name='friends'),
    url(r'^do_friending/(?P<username>[0-9a-zA-Z\-\_]+)/$', 'registration.views.do_friending', name='do_friending'),
)

urlpatterns += patterns('',
    url(r'^password_reset/$', 'django.contrib.auth.views.password_reset', name='reset_password'),
    url(r'^password_reset/done/$', 'django.contrib.auth.views.password_reset_done'),
    url(r'^reset/(?P<uidb36>[0-9A-Za-z]+)-(?P<token>.+)/$', 'django.contrib.auth.views.password_reset_confirm', name='reset_password_confirm'),
    url(r'^reset/done/$', 'django.contrib.auth.views.password_reset_complete'),
)

# Single Sign-On (SSO)
urlpatterns += patterns('',
    url(r'^sso_initiate/$', 'registration.views.sso_initiate', name='sso_initiate'),
    url(r'^sso_authorized/$', 'registration.views.sso_authorized', name='sso_authorized'),
)

# Account confirmation i.e. activation
urlpatterns += patterns('',
    url(r'^confirm/(?P<user_id>[2-9A-Za-z]+)-(?P<code>[2-9A-Za-z]+)/$', 'registration.views.confirm_account', name='confirm_account_link'),
    url(r'^confirm/$', 'registration.views.confirm_account', name='confirm_account_keyin'),
)

