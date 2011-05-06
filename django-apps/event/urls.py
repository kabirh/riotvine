from django.conf.urls.defaults import *


urlpatterns = patterns('event.views',
    # General views
    url(r'^list/(?P<category>[a-z\-]+)/$', 'list_artist_events', name='list_artist_events'),
    url(r'^list-by-loc/(?P<location>[a-z\-]+)/$', 'list_events', name='list_events_by_location'),
    url(r'^list/$', 'list_events', name='list_events'),
    url(r'^search/$', 'search_events', name='search_events'),
    url(r'^shared/(?P<event_id>[0-9]+)/(?P<sharer_id>[0-9]+)/$', 'view_shared_event', name='view_shared_event'),
    url(r'^view/(?P<event_id>[0-9]+)/$', 'view', name='view_event'),
    url(r'^post-comment/(?P<event_id>[0-9]+)/$', 'post_comment', name="post_event_comment"),
    url(r'^view-comments/(?P<event_id>[0-9]+)/$', 'comments', name='event_comments'), # AJAX
    url(r'^buy-tix/(?P<event_id>[0-9]+)/$', 'buy_tickets', name='event_buy_tickets'),
    url(r'^vcal/(?P<event_id>[0-9]+)/$', 'vcal', name='event_vcal'),

    # Event creation
    url(r'^add/$', 'edit', kwargs={'step':'1'}, name='create_event'),
    url(r'^member-add/$', 'edit', kwargs={'step':'1'}, name='create_member_event'),
    url(r'^member-add-by-loc/(?P<location>[a-z\-]+)/$', 'edit', kwargs={'step':'1'}, name='create_member_event_by_location'),
    url(r'^edit/(?P<event_id>[0-9]+)/$', 'edit', name='edit_event'),
    url(r'^edit/(?P<event_id>[0-9]+)/(?P<step>[1-3])/$', 'edit', name='edit_event_step'),
    url(r'^delete/(?P<event_id>[0-9]+)/$', 'delete', name='delete_event'),

    # Venue search
    url(r'^venue/search/$', 'venue_search', name='event_venue_search'),

    # Event workflow
    url(r'^request-approval/(?P<event_id>[0-9]+)/$', 'request_approval', name='request_event_approval'),

    # Dynamic Badges
    url(r'^badge/(?P<event_id>[0-9]+)/$', 'dynamic_badge', name='event_badge'),
    url(r'^badge/int/(?P<event_id>[0-9]+)/$', 'serve_badge', kwargs={'badge_type':'i'}, name='serve_event_badge_internal'),
    url(r'^badge/ext/(?P<event_id>[0-9]+)/$', 'serve_badge', kwargs={'badge_type':'e'}, name='serve_event_badge_external'),

    # Recommendations
    url(r'^recommended/$', 'recommended_events', name='event_recommended'), # AJAX

    # Attendees
    url(r'^calendar/$', 'calendar', name='event_calendar'), # AJAX
    url(r'^add-to-calendar/(?P<event_id>[0-9]+)/$', 'add_to_calendar', {'ssl':False}, name='event_add_to_calendar'), # AJAX
    url(r'^remove-from-calendar/(?P<event_id>[0-9]+)/$', 'add_to_calendar', {'ssl':False, 'remove':True}, name='event_remove_from_calendar'), # AJAX
    url(r'^attend/(?P<event_id>[0-9]+)/$', 'attend', {'ssl':False}, name='attend_event'),
    url(r'^qualify/(?P<event_id>[0-9]+)/$', 'qualify', {'ssl':False}, name='qualify_for_event'),
    url(r'^attendees-report/(?P<event_id>[0-9]+)/$', 'list_attendees_report', name='list_attendees_report'),
    url(r'^attendees/(?P<event_id>[0-9]+)/$', 'list_attendees', name='list_attendees'),
    url(r'^interested/(?P<event_id>[0-9]+)/$', 'interested', name='event_interested'), # AJAX
    url(r'^message-attendees/(?P<event_id>[0-9]+)/$', 'message_attendees', name='message_attendees'),
)


urlpatterns += patterns('',
    (r'^photo/', include('event.photo.urls')),
)

