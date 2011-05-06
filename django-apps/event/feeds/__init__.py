from datetime import date

from django.contrib.syndication.feeds import Feed, FeedDoesNotExist
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.utils.safestring import mark_safe

from event.utils import get_feed_signature
from event.models import Event, Attendee, RecommendedEvent
from registration.models import UserProfile


class FavoritesFeed(Feed):
    feed_sig_type = "favorites"
    title_template = "feeds/event-title.html"
    description_template = "feeds/event-description.html"
    
    def get_object(self, bits):
        if len(bits) != 2:
            raise ObjectDoesNotExist
        user_profile_id, signature = bits
        if signature != get_feed_signature(user_profile_id, self.feed_sig_type):
            raise ObjectDoesNotExist
        try:
            user_profile = get_object_or_404(UserProfile.objects.active(), pk=user_profile_id)     
        except ValueError:
            user_profile = get_object_or_404(UserProfile.objects.active(), user__username__iexact=user_profile_id) # backwards compatibility fix
        return user_profile

    def title(self, obj):
        return mark_safe(u"%s is in for these events on %s:" % (obj.username.title(), settings.UI_SETTINGS['UI_SITE_TITLE']))

    def link(self, obj):
        if not obj:
            raise FeedDoesNotExist
        return obj.get_absolute_url()

    def description(self, obj):
        return u""

    def items(self, obj):
        now = date.today()
        attendees = Attendee.objects.select_related("event__venue", "attendee_profile__user").filter(
            attendee_profile=obj,
            event__is_deleted=False,
            event__is_approved=True,
            event__event_date__gte=now
        ).order_by('-added_on')
        events = []
        for a in attendees:
            e = a.event
            e.added_on = a.added_on
            events.append(e)
        return events
       
    def item_pubdate(self, item):
        return item.added_on


class FriendsFavoritesFeed(FavoritesFeed):
    feed_sig_type = "friends-favorites"
    
    def title(self, obj):
        return mark_safe(u"%s's friends are in for these events on %s:" % (obj.username.title(), settings.UI_SETTINGS['UI_SITE_TITLE']))

    def items(self, obj):
        now = date.today()
        recommended = RecommendedEvent.objects.select_related("event__venue", "user_profile__user").filter(
            user_profile=obj,
            event__is_deleted=False,
            event__is_approved=True,
            event__event_date__gte=now
        ).order_by('-updated_on')
        events = []
        for a in recommended:
            e = a.event
            e.added_on = a.updated_on
            events.append(e)
        return events
