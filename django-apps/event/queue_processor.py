"""

ActionItem processors for event and attendee related queued actions.

See further documentation of this API in `queue.ActionItemProcessorBase`.

"""

import logging

from django.conf import settings
from django.template.defaultfilters import date as date_filter
from django.template.defaultfilters import time as time_filter

from rdutils.email import email_template
from queue import ActionItemProcessorBase


_log = logging.getLogger('queue.models')


def get_event_email_data(event, email_type):
    e, v = event, event.venue
    d = dict(
        email_type=email_type,
        event_id=e.pk,
        event__title=e.title,
        event__event_url=e.get_absolute_url(force_hostname=True),
        event__tweet_count=e.tweet_count,
        event__short_url=e.get_short_url(),
        event__ticket_url=e.ticket_or_tm_url,
        event__event_date=e.event_date,
        event__event_start_time=e.event_start_time,
        event__event_timezone=e.event_timezone,
        event__venue__name=v.name,
        event__venue__address=v.address,
        event__venue__citystatezip=v.citystatezip,
        event__venue__map_url=v.map_url,
    )
    d['event__event_date'] = date_filter(d['event__event_date'], "l, N j, Y")
    if d['event__event_start_time']:
        d['event__event_start_time'] = time_filter(d['event__event_start_time'])
    if e.show_checkins:
        d['fsq_checkins'] =  v.fsq_checkins
        d['fsq_ratio'] = v.fsq_ratio_display
    return d


class EventProcessor(ActionItemProcessorBase):
    def recompute_event(self, event):
        if event:
            event.recompute()
        return True

    def generate_badges(self, event):
        if event:
             event.create_badges()
        return True

    def email_event_approval(self, event):
        if event and event.is_approved and not event.is_member_generated:
            user = event.artist.user_profile.user
            email_template('[%s] Your new event is live!' % settings.UI_SETTINGS['UI_SITE_TITLE'],
                           'event/email/event_approved.txt',
                           {'event':event, 'user':user},
                           to_list=[user.email])
        return True

    def merge_event_edits(self, event):
        if not event:
            return True
        if event.changed_version and event.changed_version.is_approved:
            ch = event.changed_version
            for fname in ch.MERGE_FIELDS:
                f = getattr(ch, fname)
                if f:
                    setattr(event, fname, f)
            for fname in ch.BOOLEAN_MERGE_FIELDS:
                f = getattr(ch, fname)
                setattr(event, fname, f) 
            event.edited_on = ch.edited_on
            event.save()
            ch.delete()
        return True


class AttendeeProcessor(ActionItemProcessorBase):
    def ack_attendee(self, attendee):
        """Send an email to the fan who registered for an event.

        Don't send email if the event owner belongs to the group 'Disable ack email'.

        """
        return True # Email acknowledgement disabled.
        if not attendee:
            return True
        event = attendee.event
        disable_ack_email = event.owner.groups.filter(name__iexact='disable ack email').count()
        if disable_ack_email:
            return True
        user = attendee.attendee
        if user:
            email_template('[%s] Thanks for registering!' % settings.UI_SETTINGS['UI_SITE_TITLE'],
                           'event/email/registration_thanks.txt',
                           {'event':event, 'user':user},
                           to_list=[user.email])
        return True
    
    def event_faved(self, attendee):
        """Email users when a friend favorites an event they've favorited.
        
        The email will basically say "%Username% is on board with you for %Event%!".

        """
        from event.templatetags.eventtags import event_friends
        from registration.models import Friendship
        if not attendee:
            return True
        event = attendee.event
        if not event.is_active:
            return True
        venue = event.venue
        user_profile = attendee.attendee_profile
        if not user_profile.user.is_active:
            return True
        friends = Friendship.objects.get_friendships(
            user_profile
        ).values_list('user_profile2_id', flat=True)
        friends = set(list(friends))
        attendees = event.attendee_set.select_related('attendee_profile__user').filter(
            pk__lt=attendee.pk, # people that faved this event before this user
            attendee_profile__send_favorites=True,
            attendee_profile__user__is_active=True
        )
        e, v = event, venue
        d = get_event_email_data(event, 'event-faved')
        for f in attendees:
            friend_profile = f.attendee_profile
            if friend_profile.pk in friends:
                num_fr = event_friends(event, friend_profile).lower().replace('|', '')
                if num_fr.endswith("friend"):
                    num_fr = num_fr + " is in for this event"
                elif num_fr.endswith("friends"):
                    num_fr = num_fr + " are in for this event"
                d['num_friends'] = num_fr
                subject = u'%s is on board with you for %s' % (user_profile.username.title(), event.title)
                email_template(subject,
                               'event/email/friend_is_on_board.html',
                               {'event':event, 'user_profile':friend_profile, 'friend_profile':user_profile, 'data':d},
                               to_list=[friend_profile.user.email])
        return True


class CheckinProcessor(ActionItemProcessorBase):
    def event_unlocked(self, eventcheckin):
        """Send an email to the user who has just unlocked a badge at an event"""
        from event.templatetags.eventtags import event_friends
        if not eventcheckin:
            return True        
        user_profile = eventcheckin.user_profile
        if not user_profile:
            return True
        event = eventcheckin.event
        if not event.has_unlock and not settings.FOURSQUARE_UNLOCK_BETA:
            return True
        user = user_profile.user
        if user:
            d = get_event_email_data(event, 'event-unlocked')
            num_fr = event_friends(event, user_profile).lower().replace('|', '')
            if num_fr.endswith("friend"):
                num_fr = num_fr + " is in for this event"
            elif num_fr.endswith("friends"):
                num_fr = num_fr + " are in for this event"
            d['num_friends'] = num_fr
            subject = event.unlock_subject or settings.FOURSQUARE_UNLOCK_SUBJECT
            body = event.unlock_body
            email_template(subject,
                           'event/email/event_unlocked.html',
                           {'event':event, 'user':user, 'user_profile':user_profile, 'data':d, 'subject':subject, 'body':body},
                           to_list=[user.email])
        return True
