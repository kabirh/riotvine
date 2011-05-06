from django.conf.urls.defaults import *

from event.feeds import FavoritesFeed, FriendsFavoritesFeed

feeds = {
    'favorites': FavoritesFeed,
    'friends-favorites': FriendsFavoritesFeed,
}

urlpatterns = patterns('',
    (r'^(?P<url>.*)/$', 'django.contrib.syndication.views.feed', {'feed_dict': feeds}),
)
