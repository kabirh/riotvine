from django.contrib import admin

from common.forms import get_model_form
from twitter.models import TwitterProfile, TwitterFriend, BlackList


class TwitterProfileAdmin(admin.ModelAdmin):
    form = get_model_form(TwitterProfile)
    list_display = ('user_profile', 'screen_name', 'appuser_id', 'added_on', 'id')
    search_fields = ('user_profile__user__username', 'screen_name', 'appuser_id')
    raw_id_fields = ('user_profile',)
    ordering = ('-added_on',)
    date_hierarchy = 'added_on'

admin.site.register(TwitterProfile, TwitterProfileAdmin)


class TwitterFriendAdmin(admin.ModelAdmin):
    form = get_model_form(TwitterFriend)
    list_display = ('twitter_profile', 'friend_id', 'id')
    search_fields = ('twitter_profile__screen_name', 'twitter_profile__appuser_id', 'friend_id')
    raw_id_fields = ('twitter_profile',)

admin.site.register(TwitterFriend, TwitterFriendAdmin)


class BlackListAdmin(admin.ModelAdmin):
    form = get_model_form(BlackList)
    list_display = ('id', 'updated_on', 'names')
    list_display_links = ('id', 'updated_on')
    search_fields = ('names',)

admin.site.register(BlackList, BlackListAdmin)

