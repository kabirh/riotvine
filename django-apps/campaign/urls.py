from django.conf.urls.defaults import *
from campaign.views import CampaignCreationFormWizard


urlpatterns = patterns('rdutils.url',
    # Multi-step campaign creation
    url(r'^create/$', 'call_view_class', {'class':CampaignCreationFormWizard}, name='create_campaign'),
)

urlpatterns += patterns('campaign.views',
    # General views
    url(r'^list/(?P<category>[a-z\-]+)/$', 'list_artist_campaigns', name='list_artist_campaigns'),
    url(r'^list/$', 'list_campaigns', name='list_campaigns'),
    url(r'^view/(?P<campaign_id>[0-9]+)/$', 'view', name='view_campaign'),
    url(r'^post-comment/(?P<campaign_id>[0-9]+)/$', 'post_comment', name="post_campaign_comment"),

    # Campaign creation
    url(r'^edit/(?P<campaign_id>[0-9]+)/$', 'edit', name='edit_campaign'),
    url(r'^delete/(?P<campaign_id>[0-9]+)/$', 'delete', name='delete_campaign'),

    # Campaign workflow
    url(r'^request-approval/(?P<campaign_id>[0-9]+)/$', 'request_approval', name='request_approval'),
    url(r'^request-payout/(?P<campaign_id>[0-9]+)/$', 'request_payout', name='request_campaign_payout'),
    url(r'^request-tickets/(?P<campaign_id>[0-9]+)/$', 'request_tickets', name='request_campaign_tickets'),

    # Admin
    url(r'^print-tickets/(?P<campaign_id>[0-9]+)/$', 'print_tickets', name='print_campaign_tickets'),

    # Dynamic Badges
    url(r'^badge/int/(?P<campaign_id>[0-9]+)/$', 'serve_badge', kwargs={'badge_type':'i'}, name='serve_badge_internal'),
    url(r'^badge/ext/(?P<campaign_id>[0-9]+)/$', 'serve_badge', kwargs={'badge_type':'e'}, name='serve_badge_external'),

    # Contributions
    url(r'^contribute/(?P<campaign_id>[0-9]+)/$', 'contribute', {'ssl':True}, name='contribute_to_campaign'),
    url(r'^contribute/(?P<campaign_id>[0-9]+)/(?P<payment_mode>[0-9a-zA-Z\-]+)/$', 'contribute_by_payment_mode', {'ssl':True}, name='contribute_to_campaign_by_payment_mode'),
    url(r'^anon-contribute/(?P<campaign_id>[0-9]+)/(?P<payment_mode>[0-9a-zA-Z\-]+)/$', 'anon_contribute_by_payment_mode', {'ssl':True}, name='anon_contribute_to_campaign_by_payment_mode'),
    url(r'^redeem-ticket/$', 'redeem_ticket', {'ssl':True}, name='redeem_ticket'),
    url(r'^qualify/(?P<campaign_id>[0-9]+)/$', 'qualify', {'ssl':True}, name='qualify_for_campaign'),
    url(r'^contributors/(?P<campaign_id>[0-9]+)/$', 'list_contributors', name='list_contributors'),
    url(r'^message-contributors/(?P<campaign_id>[0-9]+)/$', 'message_contributors', name='message_contributors'),
    url(r'^sponsors/(?P<campaign_id>[0-9]+)/$', 'list_sponsors', name='list_sponsors'),

    # Payment service callbacks
    url(r'^paypal-notification/$', 'paypal_notification', {'ssl':True}, name='paypal_notification'),
    url(r'^google-notification/$', 'google_notification', {'ssl':True}, name='google_notification'),
    url(r'^payment-return/(?P<campaign_id>[0-9]+)/(?P<inv_id>[0-9]+)/(?P<success_code>[01])/(?P<payment_mode>[0-9a-zA-Z\-]+)/$', 'payment_return', name='payment_return'),
)


urlpatterns += patterns('',
    (r'^photo/', include('campaign.photo.urls')),
)

