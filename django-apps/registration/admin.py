from django.contrib import admin
from django.contrib.admin.sites import NotRegistered, AlreadyRegistered
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.conf import settings

from common.forms import get_model_form
from registration.models import UserProfile, Address, Friendship, FBInvitedUser, FBSuggestedFriends, Follower


ENABLE_AVATAR = getattr(settings, 'AVATAR_ENABLE', True)


class UserAdmin(DjangoUserAdmin):
    """Customization of the built-in user admin."""
    filter_horizontal = ('user_permissions', 'groups')
    date_hierarchy = 'date_joined'

try:
    admin.site.unregister(User)
    admin.site.register(User, UserAdmin)
except (NotRegistered, AlreadyRegistered):
    pass


class AddressAdmin(admin.StackedInline):
    form = get_model_form(Address)
    model = Address
    extra = 0


class UserProfileAdmin(admin.ModelAdmin):
    form = get_model_form(UserProfile)
    list_display = ['username', 'has_opted_in', 'admin_user_link', 'send_reminders', 'fb_userid', 'admin_twitter_profile', 'fsq_userid', 'id']
    if ENABLE_AVATAR:
        list_display.insert(1, 'avatar_preview')
    search_fields = ('user__username', 'user__email', 'phone_number', 'fb_userid')
    list_filter = ('is_sso', 'has_opted_in', 'send_reminders', 'send_favorites', 'is_artist', 'is_verified', 'permission')
    raw_id_fields = ('user',)
    inlines = [AddressAdmin]
    ordering = ('-id',)

admin.site.register(UserProfile, UserProfileAdmin)


class FriendshipAdmin(admin.ModelAdmin):
    form = get_model_form(Friendship)
    list_display = ('user_profile1', 'user_profile2', 'source')
    raw_id_fields = ('user_profile1', 'user_profile2')
    search_fields = ('user_profile1__user__username',)
    list_filter = ('source',)

admin.site.register(Friendship, FriendshipAdmin)


class FollowerAdmin(admin.ModelAdmin):
    form = get_model_form(Follower)
    list_display = ('followee', 'follower', 'added_on')
    raw_id_fields = ('followee', 'follower')
    search_fields = ('followee__user__username',)
    # list_filter = ('source',)

admin.site.register(Follower, FollowerAdmin)


class FBInvitedUserAdmin(admin.ModelAdmin):
    form = get_model_form(FBInvitedUser)
    list_display = ('inviter_profile', 'fb_userid', 'added_on')
    search_fields = ('inviter_profile__user__username', 'fb_userid')
    raw_id_fields = ('inviter_profile',)
    date_hierarchy = 'added_on'

admin.site.register(FBInvitedUser, FBInvitedUserAdmin)


class FBSuggestedFriendsAdmin(admin.ModelAdmin):
    form = get_model_form(FBSuggestedFriends)
    list_display = ('user_profile', 'friendset', 'added_on')
    search_fields = ('user_profile__user__username',)
    raw_id_fields = ('user_profile',)
    date_hierarchy = 'added_on'

admin.site.register(FBSuggestedFriends, FBSuggestedFriendsAdmin)

