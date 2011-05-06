from datetime import datetime, date, timedelta

from django.db import models
from django.utils import simplejson as json
from django.utils.translation import ugettext_lazy as _

from rdutils.cache import key_suffix, short_key, clear_keys, cache
from registration.models import UserProfile


class TwitterProfileManager(models.Manager):
    def active(self):
        return self.select_related('user_profile__user').filter(user_profile__user__is_active=True)


class TwitterProfile(models.Model):
    user_profile = models.ForeignKey(UserProfile, unique=True)
    screen_name = models.CharField(max_length=32, db_index=True)
    appuser_id = models.CharField(max_length=255, db_index=True)
    access_token = models.CharField(max_length=255, blank=True)
    screen_name_lower = models.CharField(max_length=32, db_index=True, editable=False, help_text=u'For internal use. Leave this alone.')
    added_on = models.DateTimeField(default=datetime.now)
    updated_on = models.DateTimeField(default=datetime.now)

    objects = TwitterProfileManager()

    def __unicode__(self):
        return self.screen_name

    def get_absolute_url(self):
        return u"http://twitter.com/%s" % self.screen_name

    def save(self, *args, **kwargs):
        if not self.added_on:
            self.added_on = datetime.now()
        self.updated_on = datetime.now()
        if self.screen_name:
            self.screen_name_lower = self.screen_name.lower()
        amqp_headers = kwargs.pop('amqp_headers', None)
        super(TwitterProfile, self).save(*args, **kwargs)
        clear_keys(u'twitter_profile', self.user_profile.user.pk)
        from twitter.amqp.tasks import refresh_friends
        refresh_friends(self.appuser_id, extra_headers=amqp_headers, access_token=self.access_token)

    @property
    def user(self):
        return self.user_profile.user


class TwitterFriend(models.Model):
    """A model to capture a Twitter user's friends (i.e. user A and user B follow each other)"""
    twitter_profile = models.ForeignKey(TwitterProfile)
    friend_id = models.CharField(max_length=255, db_index=True)

    class Meta:
        unique_together = (('twitter_profile', 'friend_id'),)
        ordering = ('twitter_profile',)

    def __unicode__(self):
        return self.friend_id


class BlackListManager(models.Manager):
    def blacklist_set(self):
        """Return a set of blacklisted screen names"""
        key = u"twitter-" + key_suffix("blacklist", 0, expire_time=3600*24*30)
        key = short_key(key)
        value = cache.cache.get(key, None)
        if value is None:
            value= set()
            for v in self.values_list('names', flat=True):
                for n in v.lower().split():
                    value.add(n.strip())
            cache.cache.set(key, value, 3600*24*30)
        return value


class BlackList(models.Model):
    names = models.TextField(help_text=u"Blacklisted Twitter screen names; one name per line")
    added_on = models.DateTimeField(default=datetime.now)
    updated_on = models.DateTimeField(default=datetime.now)

    objects = BlackListManager()

    def save(self, *args, **kwargs):
        if not self.added_on:
            self.added_on = datetime.now()
        self.updated_on = datetime.now()
        super(BlackList, self).save(*args, **kwargs)
        clear_keys(u'blacklist', 0)

