from django.contrib import admin

from common.forms import get_model_form
from event import signals as event_signals
from event.forms import AdminEventForm
from event.models import Event, EventChange, EventCheckin, Badge, Attendee, Stats, Venue, RecommendedEvent, EventTweet, EventCreatedSignal, FoursquareTrend


class EventAdmin(admin.ModelAdmin):
    form = AdminEventForm
    list_display = ('id', 'avatar_preview',
                    'title', 'venue', 'admin_status', 
                    'event_date', 'location', 'tweet_count', 'hashtag', 'headliner')
    search_fields = ('id', 'title', 'url', 'hashtag',
                     'venue__name', 'venue__address', 'venue__alias',
                     'creator__user__username',
                     'creator__user__email', 'headliner')
    list_display_links = ('id', 'avatar_preview', 'title')
    list_per_page = 25
    raw_id_fields = ('artist', 'venue', 'creator',)
    list_filter = ('is_homepage_worthy', 'location', 'is_deleted', 'is_approved', 'is_submitted', 'has_unlock')
    save_on_top = True
    date_hierarchy = 'event_date'
    ordering = ('-id',)

    def log_change(self, request, object, message):
        super(EventAdmin, self).log_change(request, object, message)
        event_signals.post_event_admin_change.send(sender=Event, instance=object)

    def save_model(self, request, obj, form, change):
        super(EventAdmin, self).save_model(request, obj, form, change)
        if form.cleaned_data.get("image", None) or not obj.image_resized:
            # if image was changed, regenerate its scaled-down versions
            obj._create_resized_images(raw_field=None, save=True)

admin.site.register(Event, EventAdmin)


class EventCheckinAdmin(admin.ModelAdmin):
    list_display = ('event', 'user_profile', 'fsq_userid', 'checkin_time', 'unlocked', 'updated_on')
    raw_id_fields = ('event', 'user_profile')
    date_hierarchy = 'checkin_time'
    list_filter = ('unlocked',)

admin.site.register(EventCheckin, EventCheckinAdmin)


class EventChangeAdmin(admin.ModelAdmin):
    form = get_model_form(EventChange)
    list_display = ('event', 'title', 'event_date', 'event_start_time', 'is_approved', 'submitted_on')
    search_fields = ('title', 'url', 'event__artist__name',
                      'event__artist__user_profile__user__username',
                      'event__artist__user_profile__user__email',)
    list_display_links = ('event', 'title')
    list_per_page = 25
    raw_id_fields = ('event',)
    list_filter = ('is_approved',)
    save_on_top = True
    date_hierarchy = 'event_date'
    ordering = ('-id',)

admin.site.register(EventChange, EventChangeAdmin)


class BadgeAdmin(admin.ModelAdmin):
    form = get_model_form(Badge)
    list_display = ('event', 'badge_type', 'image_preview', 'updated_on')
    search_fields = ('event__title', 'event__url', 'event__artist__name')
    list_per_page = 25
    raw_id_fields = ('event',)
    list_filter = ('badge_type',)
    date_hierarchy = 'updated_on'
    ordering = ('-updated_on',)

admin.site.register(Badge, BadgeAdmin)


class AttendeeAdmin(admin.ModelAdmin):
    form = get_model_form(Attendee)
    list_display = ('event', 'attendee', 'qty', 'added_on')
    list_display_links = ('event', 'attendee')
    list_per_page = 25
    search_fields = ('event__title', 'event__url', 'event__artist__name')
    raw_id_fields = ('event', 'attendee', 'attendee_profile')
    date_hierarchy = 'added_on'
    ordering = ('-added_on',)

admin.site.register(Attendee, AttendeeAdmin)


class RecommendedEventAdmin(admin.ModelAdmin):
    form = get_model_form(RecommendedEvent)
    list_display = ('event', 'user_profile', 'num_friends', 'updated_on')
    search_fields = ('event__title', 'event__url', 'user_profile__user__username')
    list_per_page = 25
    raw_id_fields = ('user_profile', 'event')
    date_hierarchy = 'updated_on'
    ordering = ('-updated_on',)

admin.site.register(RecommendedEvent, RecommendedEventAdmin)


class StatsAdmin(admin.ModelAdmin):
    form = get_model_form(Stats)
    list_display = ('event', 'num_attendees', 'updated_on')
    list_display_links = ('event', 'num_attendees')
    search_fields = ('event__title', 'event__url', 'event__artist__name')
    list_per_page = 25
    raw_id_fields = ('event',)
    date_hierarchy = 'updated_on'
    ordering = ('-updated_on',)

admin.site.register(Stats, StatsAdmin)

class VenueAdmin(admin.ModelAdmin):
    form = get_model_form(Venue)
    list_display = ('id', 'name', 'alias', 'source', 'address', 'city', 'state', 'fsq_id', 'fsq_checkins', 'fsq_ratio', 'fsq_m', 'fsq_f', 'fsq_mf', 'fsq_fm', 'added_on')
    list_display_links = ('id', 'name')
    search_fields = ('name', 'alias', 'source', 'address', 'city', 'state', 'zip_code', 'fsq_id')
    list_per_page = 25
    list_filter = ('source',)
    date_hierarchy = 'updated_on'
    ordering = ('-id',)

admin.site.register(Venue, VenueAdmin)

class EventTweetAdmin(admin.ModelAdmin):
    form = get_model_form(EventTweet)
    list_display = ('id', 'tweet_id', 'from_user', 'text', 'is_retweet', 'is_onsite', 'event', 'added_on')
    search_fields = ('tweet_id', 'from_user', 'event__id',)
    list_display_links = ('id', 'tweet_id', 'from_user')
    list_per_page = 100
    raw_id_fields = ('event',)
    list_filter = ('is_retweet', 'is_onsite',)
    save_on_top = True
    date_hierarchy = 'added_on'

admin.site.register(EventTweet, EventTweetAdmin)

class EventCreatedSignalAdmin(admin.ModelAdmin):
    list_display = ('id', 'event', 'added_on')
    list_display_links = ('id', 'event', 'added_on')
    search_fields = ('event__title',)
    raw_id_fields = ('event',)
    list_per_page = 50
    date_hierarchy = 'added_on'
    
admin.site.register(EventCreatedSignal, EventCreatedSignalAdmin)

class FoursquareTrendAdmin(admin.ModelAdmin):
    list_display = ('id', 'venue', 'fsq_id', 'fsq_checkins', 'fsq_ratio', 'fsq_m', 'fsq_f', 'fsq_mf', 'fsq_fm', 'updated_on')
    list_display_links = ('id', 'venue', 'fsq_id')
    search_fields = ('venue__name',)
    raw_id_fields = ('venue',)
    list_per_page = 50
    date_hierarchy = 'updated_on'
    
admin.site.register(FoursquareTrend, FoursquareTrendAdmin)

