import logging
import os.path
import random
import string
import textwrap
from uuid import uuid4
from time import time, sleep
from mimetypes import guess_type
from datetime import datetime, date, timedelta
import base64
try:
    import cPickle as pickle
except ImportError:
    import pickle

from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _
from django.utils.safestring import mark_safe
from django.db.models import signals
from django.core.urlresolvers import reverse
from django.core import cache
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import InMemoryUploadedFile, UploadedFile

from rdutils.image import resize_in_memory, get_perfect_fit_resize_crop, remove_model_image, close, get_raw_image, str_to_file
from rdutils.date import get_age
from rdutils.cache import key_suffix, short_key, clear_keys, cache
from rdutils.url import admin_url
from rdutils.decorators import attribute_cache
from rdutils.text import slugify
from registration.utils import is_sso_email


_log = logging.getLogger('registration.models')


'''
_s3_enabled = "S3" in default_storage._wrapped.__class__.__name__
if _s3_enabled:
    DEFAULT_AVATAR_URL = default_storage.url(settings.AVATAR_DEFAULT_URL)
    DEFAULT_MEDIUM_AVATAR_URL = default_storage.url(settings.AVATAR_MEDIUM_DEFAULT_URL)
else:
    DEFAULT_AVATAR_URL = u"%sui/%s" % (settings.MEDIA_URL, settings.AVATAR_DEFAULT_URL)
    DEFAULT_MEDIUM_AVATAR_URL = u"%sui/%s" % (settings.MEDIA_URL, settings.AVATAR_MEDIUM_DEFAULT_URL)
'''

DEFAULT_AVATAR_URL = u"%sui/%s" % (settings.MEDIA_URL, settings.AVATAR_DEFAULT_URL)
DEFAULT_MEDIUM_AVATAR_URL = u"%sui/%s" % (settings.MEDIA_URL, settings.AVATAR_MEDIUM_DEFAULT_URL)


AVATAR_HELP_TEXT = _("""<p>
                            If you've got a profile image, upload it. 
                            We will resize it down to the appropriate dimensions.
                        </p>
                        <ul>
                            <li>The image format must be either JPEG or PNG.</li> 
                            <li>The file size must be under %s MB.</li>
                        </ul>""" % int(settings.AVATAR_IMAGE_MAX_SIZE_MB))


# Custom image field
class AvatarImageField(models.ImageField):   
    def generate_filename(self, instance, filename):
        ext = os.path.splitext(filename)[1]
        if not ext:
            ext = '.jpg'
        filename = '%s-%s-%s-%s%s' % (instance.user.pk,
                                   instance.pk or uuid4().hex[::6],
                                   slugify(instance.username)[:10],
                                   uuid4().hex[::8],
                                   ext)
        return super(AvatarImageField, self).generate_filename(instance, filename)

    def save_form_data(self, instance, data):
        """Override default field save action and create resized campaign images.

        `instance` is a campaign instance.

        """
        if data and isinstance(data, UploadedFile):
            # A new file is being uploaded. So delete the old one.
            remove_model_image(instance, 'avatar_image')
        super(AvatarImageField, self).save_form_data(instance, data)
        # instance._create_resized_images(raw_field=data, save=False)


class UserProfileManager(models.Manager):
    def active(self, **kwargs):
        return self.select_related('user').filter(user__is_active=True, **kwargs)

    def local(self, **kwargs):
        """Return non-SSO users"""
        return self.active(kwargs).filter(is_sso=False)
    
    def activate_user(self, activation_code, commit=True):
        """Find an unverified user profile and activate it. Return tuple (UserProfile|None, failure reason)."""
        try:
            user_id, code = activation_code.upper().split('-')
            user_id = user_id.replace('X', '0').replace('Y', '1')
            up = self.active().get(user__pk=user_id, activation_code=activation_code)
            if up.is_verified:
                return None, 'That account has already been confirmed.'
            up.is_verified = True
            if commit:
                super(UserProfile, up).save()
                return up, "Activated"
        except UserProfile.DoesNotExist:
            return None, 'The activation code is invalid.'
        except ValueError:
            return None, 'The activation code is invalid.'
        
    def deactivate_accounts(self):
        """Remove accounts that have not been activated within X days."""
        if settings.ACCOUNT_EMAIL_VERIFICATION_DEFAULT:
            return # if verification is disabled, don't delete unverified users
        days = settings.REGISTRATION_DEACTIVATION_THRESHOLD_DAYS + 1
        threshold = datetime.now() - timedelta(days=days)
        users = User.objects.filter(
            is_active=True,
            is_staff=False,
            userprofile__is_verified=False,
            date_joined__lte=threshold
        ).distinct()
        num = users.count()
        if num:
            _log.warn("%s users deleted - %s", num, users)
        users.delete()
        return num


class UserProfile(models.Model):
    PERMISSION_CHOICES = (
        ('everyone', 'Everyone'),
        ('only-riotvine-users', 'Only RiotVine users'),
        ('only-friends', 'Only friends'),
    ) 
    PERMISSION_DEFAULT = 'only-riotvine-users'
    user = models.ForeignKey(User, unique=True)
    is_artist = models.BooleanField(_('is artist'), default=False)
    birth_date = models.DateField(_('birth date'), blank=True, null=True)
    phone_number = models.CharField(_('phone number'), blank=True, db_index=True,
                        max_length=25,
                        help_text=_('In the format: XXX-XXX-XXXX'))
    has_opted_in = models.BooleanField(_('has opted in'), default=False, db_index=True)
    is_sso = models.BooleanField(_('is single sign-on'), default=False, db_index=True)
    sso_username = models.CharField(max_length=32, blank=True, db_index=True, unique=True, help_text=u"Enter an 'x' here if you want to remove this field. Don't leave it blank.")
    fb_userid = models.CharField('FB', max_length=32, blank=True, db_index=True, unique=True, help_text=u"Enter an 'x' here if you want to remove this field. Don't leave it blank.")
    fsq_userid = models.CharField('FSQ', max_length=64, blank=True, db_index=True, unique=True, help_text=u"Enter an 'x' here if you want to remove this field. Don't leave it blank.")
    fb_session_key = models.CharField(max_length=250, blank=True, db_index=True)
    avatar_image = AvatarImageField(upload_to='avatars/original/%Y-%b',
                              max_length=250,
                              null=True,
                              blank=True,
                              help_text=AVATAR_HELP_TEXT)
    avatar = models.ImageField(_('profile image'),
                           upload_to='avatars/resized/%Y-%b',
                           # width_field='avatar_width',
                           # height_field='avatar_height',
                           null=True,
                           blank=True,
                           max_length=250,
                           editable=True)
    avatar_medium = models.ImageField(_('medium profile image '),
                           upload_to='avatars/resized-medium/%Y-%b',
                           # width_field='avatar_medium_width',
                           # height_field='avatar_medium_height',
                           null=True,
                           blank=True,
                           max_length=250,
                           editable=True)
    avatar_width = models.PositiveIntegerField(null=True, editable=False)
    avatar_height = models.PositiveIntegerField(null=True, editable=False)
    avatar_medium_width = models.PositiveIntegerField(null=True, editable=False)
    avatar_medium_height = models.PositiveIntegerField(null=True, editable=False)
    send_reminders = models.BooleanField(_('send reminder emails'), default=True)
    send_favorites = models.BooleanField(_("send friends' favorites emails"), default=True)
    is_verified = models.BooleanField(default=False)
    activation_code = models.CharField(max_length=40, db_index=True, blank=True)
    permission = models.CharField(_("Who can see my profile"), max_length=30, default=PERMISSION_DEFAULT, choices=PERMISSION_CHOICES)
    full_artistname = models.CharField(max_length=200, blank=True, db_index=True, unique=True, editable=False)

    objects = UserProfileManager()

    def __unicode__(self):
        return self.username

    @models.permalink
    def get_absolute_url(self):
        # tp = self.twitter_profile
        # return tp and tp.get_absolute_url() or u"/"
        return ("user_profile", (), {'username':self.user.username.lower()})

    def delete(self):
        if not self.user.is_superuser:
            super(UserProfile, self).delete()

    def save(self, *args, **kwargs):
        if self.sso_username:
            self.sso_username = self.sso_username.strip().lower()
        if self.is_sso and not self.has_email:
            self.send_reminders = False
            self.send_favorites = False
        if not self.is_verified:
            self.generate_activation_code(commit=False)
        if not self.sso_username or self.sso_username.lower() == 'x':
            self.sso_username = u''
        if not self.fb_userid or self.fb_userid.lower() == 'x':
            self.fb_userid = u''
        if self.fsq_userid:
            self.fsq_userid = self.fsq_userid.strip()
        if not self.fsq_userid or self.fsq_userid.lower() == 'x':
            self.fsq_userid = u''
        super(UserProfile, self).save(*args, **kwargs)

    def get_profile(self):
        return self

    @property
    def username(self):
        return self.is_sso and self.sso_username or self.user.username
    
    @property
    def firstname_or_username(self):
        return self.first_name and self.first_name.title() or self.username

    @property
    def is_fb(self):
        return bool(self.fb_userid)
    
    @property
    def first_name(self):
        return self.user.first_name
    
    @property
    def last_name(self):
        return self.user.last_name
    
    @property
    def email(self):
        return self.user.email
    
    @property
    def date_joined(self):
        return self.user.date_joined

    def admin_user_link(self):
        return admin_url(self.user)
    admin_user_link.short_description = 'user link'
    admin_user_link.allow_tags = True

    def admin_address_link(self):
        try:
            return admin_url(self.address)
        except Address.DoesNotExist:
            return ''
    admin_address_link.short_description = 'user link'
    admin_address_link.allow_tags = True

    def admin_address_text(self):
        try:
            adr = self.address
            a = '''<p>%s %s<br/>
            %s<br/>
            %s<br/>
            %s %s %s<br/>
            </p>
            ''' % (self.user.first_name, self.user.last_name,
                   adr.address1,
                   adr.address2,
                   adr.city, adr.state, adr.postal_code)
        except Address.DoesNotExist:
            return ''
    admin_address_text.short_description = 'address'
    admin_address_text.allow_tags = True

    def get_phone(self):
        return self.phone_number

    def set_phone(self, phone):
        self.phone_number = phone

    phone = property(get_phone, set_phone)

    @property
    def is_fan(self):
        return not self.is_artist

    @property
    @attribute_cache('age')
    def age(self):
        """Return age in complete years."""
        if self.birth_date:
            return get_age(self.birth_date)
        else:
            return None
        
    def generate_activation_code(self, commit=True):
        """Generate a new activation code and optionally save it to the DB.
        
        Activation code format:
            user_id-5_random_alpha_nums
        
        The code is always in uppercase.
        
        """
        if self.activation_code or self.is_verified:
            return # don't overwrite existing code
        uid = unicode(self.user.pk).replace('0', 'X').replace('1', 'Y')
        digits = u''.join(random.sample('23456789ABCDEFGHJKMNPQRSTUVWXYZ', 5))
        self.activation_code = u"%s-%s" % (uid, digits)
        if commit:
            super(UserProfile, self).save()
          
    @property
    @attribute_cache('activation_url')
    def activation_url(self):
        self.generate_activation_code()
        if not self.activation_code:
            return None
        user_id, code = self.activation_code.split('-')
        return reverse("confirm_account_link", kwargs=dict(user_id=user_id, code=code))

    @property
    @attribute_cache('friendset')
    def friendset(self):
        """Return a set of user_profile ids of this user's friends"""
        key = u"friendset:%s" % key_suffix('friends', self.pk)
        key = short_key(key)
        value = cache.cache.get(key, None)
        if value is None:
            value = set(Friendship.objects.get_friendships(user_profile=self).values_list('user_profile2_id', flat=True))
            cache.cache.set(key, value)
        return value

    @property
    @attribute_cache('artist')
    def artist(self):
        from artist.models import ArtistProfile
        try:
            return ArtistProfile.objects.get(user_profile=self) # Artist must have an artist profile
        except ArtistProfile.DoesNotExist:
            return None

    @property
    def is_artist_profile_complete(self):
        """Return ``True`` if this is an artist profile and all required 
        artist profile fields have been populated.

        To be deemed complete, an artist must have:
            - Phone number
            - First and last name
            - ``ArtistProfile``
            - Payment info (i.e. Paypal or Google merchant info)
        """
        if self.is_artist:
            from artist.models import ArtistProfile
            try:
                if not self.phone_number:
                    return False
                if not (self.user.first_name and self.user.last_name):
                    return False
                # adr = self.address # Address is no longer mandatory.
                artist_profile = ArtistProfile.objects.get(user_profile=self) # Artist must have an artist profile
                if not artist_profile.has_payment_info:
                    return False
                return True
            except ObjectDoesNotExist:
                return False
        return False

    def _create_resized_images(self, raw_field, save):
        """Generate scaled down images for avatars."""
        if not self.avatar_image:
            return None
        # Derive base filename (strip out the relative directory).
        filename = os.path.split(self.avatar_image.name)[-1]
        ctype = guess_type(filename)[0]
        ext = os.path.splitext(filename)[1]
        if not ext:
            ext = '.jpg'

        t = None
        try:
            try:
                pth = self.avatar_image.path
            except NotImplementedError:
                from django.core.files.temp import NamedTemporaryFile
                t = NamedTemporaryFile(suffix=ext)
                ix = self.avatar_image
                for d in ix.chunks(4000000):
                    t.write(d)
                t.flush()
                t.seek(0)
                pth = t

            # Generate avatar.
            remove_model_image(self, 'avatar')
            self.avatar = None
            avatar_contents = resize_in_memory(pth, settings.AVATAR_IMAGE_CROP, crop=settings.AVATAR_IMAGE_CROP, crop_before_resize=True)
            if avatar_contents:
                avatar_file = str_to_file(avatar_contents)
                avatar_field = InMemoryUploadedFile(avatar_file, None, None, ctype, len(avatar_contents), None)
                self.avatar.save(name='avatar-%s' % filename, content=avatar_field, save=save)
                avatar_file.close()

            # Generate medium-sized avatar.
            remove_model_image(self, 'avatar_medium')
            self.avatar_medium = None
            if t:
                t.seek(0)
            avatar_contents = resize_in_memory(pth, settings.AVATAR_MEDIUM_IMAGE_CROP, crop=settings.AVATAR_MEDIUM_IMAGE_CROP, crop_before_resize=True)
            if avatar_contents:
                avatar_file = str_to_file(avatar_contents)
                avatar_field = InMemoryUploadedFile(avatar_file, None, None, ctype, len(avatar_contents), None)
                self.avatar_medium.save(name='avatar-med-%s' % filename, content=avatar_field, save=save)
                avatar_file.close()

            if t:
                t.close()
            if save:
                super(UserProfile, self).save()
        except Exception:
            raise
        finally:
            if t:
                t.close()

    def avatar_preview(self, alt=None):
        """Return HTML fragment to display avatar if available."""
        if not alt:
            alt = self.username
        if self.avatar:
            h = '<img src="%s" alt="%s" width="%s" height="%s"/>' % (self.avatar.url,
                                                                     alt,
                                                                     self.avatar_width,
                                                                     self.avatar_height)
            return mark_safe(h)
        return u''
    avatar_preview.allow_tags = True
    avatar_preview.short_description = 'Avatar'

    def avatar_url(self):
        """Return avatar or default url"""
        from boto.exception import S3ResponseError
        if self.avatar:
            try:
                return self.avatar.url
            except S3ResponseError:
                try:
                    # try once again
                    sleep(.02) # 20 millisecond pause
                    return self.avatar.url
                except:
                    return DEFAULT_AVATAR_URL
        else:
            return DEFAULT_AVATAR_URL

    def avatar_w(self):
        """Return avatar width or default width"""
        if self.avatar_width:
            return self.avatar_width
        else:
            return settings.AVATAR_IMAGE_CROP[0]

    def avatar_h(self):
        """Return avatar_height or default height"""
        if self.avatar_height:
            return self.avatar_height
        else:
            return settings.AVATAR_IMAGE_CROP[1]

    def avatar_medium_url(self):
        """Return avatar_medium or default url"""
        if self.avatar_medium:
            return self.avatar_medium.url
        else:
            return DEFAULT_MEDIUM_AVATAR_URL

    def avatar_medium_w(self):
        """Return avatar width or default width"""
        if self.avatar_medium_width:
            return self.avatar_medium_width
        else:
            return settings.AVATAR_MEDIUM_IMAGE_CROP[0]

    def avatar_medium_h(self):
        """Return avatar_height or default height"""
        if self.avatar_medium_height:
            return self.avatar_medium_height
        else:
            return settings.AVATAR_MEDIUM_IMAGE_CROP[1]

    @property
    def use_fb_profile(self):
        """Return true if the profile image for this user should be loaded from Facebook"""
        if self.avatar:
            return False # User has a local profile image
        else:
            return self.fb_userid # User has an FB account

    @property
    @attribute_cache('twitter_profile')
    def twitter_profile(self):
        prof = self.twitterprofile_set.active()[:1]
        if prof:
            return prof[0]
        else:
            return None
        
    def admin_twitter_profile(self):
        return self.twitter_profile or u''
    admin_twitter_profile.short_description = u'Twitter Id'

    @property
    @attribute_cache('has_twitter_access_token')
    def has_twitter_access_token(self):
        prof = self.twitter_profile
        return bool(prof and prof.access_token)

    @property
    def has_email(self):
        return not is_sso_email(self.user.email)
       
    @property
    @attribute_cache('google_username')
    def google_username(self):
        """Return google username for this user"""
        email = self.user.email.lower()
        if email.endswith("@gmail.com"):
            u = email.split('@')[0]
            if '+' in u:
                u = u.split('+')[0]
            return u
        return None
    
    def get_relationship(self, user_profile2):
        """Return tuple with user_profile2's relationship with this user.
        
        Possible relationship_types are:
            follower -- user_profile2 follows self
            followee -- self follows user_profile2
            friend -- self and user_profile2 follow each other (they are friends)
        """                
        relationship_object, relationship_type = Follower.objects.get_follower_followee(self, user_profile2)
        if not relationship_object:
            relationship_object = Friendship.objects.get_friendship(self, user_profile2)
            if relationship_object:
                relationship_type = 'friend'
        return relationship_object, relationship_type
    
    @attribute_cache('get_friend_follower_count')
    def get_friend_follower_count(self):
        key = u"friend-follower-stats:%s" % key_suffix('friends', self.pk)
        key = short_key(key)
        value = cache.cache.get(key, None)
        if value is None:
            v1 = Friendship.objects.select_related('user_profile2__user').filter(user_profile1=self, user_profile2__user__is_active=True).count()
            v2 = Follower.objects.select_related('follower__user').filter(followee=self, follower__user__is_active=True).count()
            value = (v1, v2)
            cache.cache.set(key, value, 300)
        return value


class Address(models.Model):
    user_profile = models.OneToOneField(UserProfile, primary_key=True, related_name='address')
    address1 = models.CharField(_('address 1'), max_length=100)
    address2 = models.CharField(_('address 2'), blank=True, max_length=100)
    city = models.CharField(_('city'), max_length=100, db_index=True)
    state = models.CharField(_('state'), max_length=100, db_index=True)
    postal_code = models.CharField(_('zip code'), max_length=20, db_index=True)
    country = models.CharField(_('country'), max_length=75, db_index=True, default='US')

    def __unicode__(self):
        return u'%s' % self.address1


def create_user_profile(sender, instance, **kwargs):
    """
    Ensure that a ``UserProfile`` gets created whenever a new ``User`` is created.

    Hook this method call to the User ``post_save`` signal.
    """
    if isinstance(instance, User):
        p, created = UserProfile.objects.get_or_create(user=instance)
        if created:
            _log.debug("Profile created for user %s", instance.username)

signals.post_save.connect(create_user_profile, sender=User)


class FollowerManager(models.Manager):
    def get_follower_followee(self, user_profile1, user_profile2):
        """Return tuple with follower/followee relationship between the given users."""
        try:
            return (self.get(followee=user_profile1, follower=user_profile2), 'follower')
        except Follower.DoesNotExist:
            pass
        try:
            return (self.get(followee=user_profile2, follower=user_profile1), 'followee')
        except Follower.DoesNotExist:
            pass
        return (None, '')
    
    def get_followers(self, user_profile):
        """Return the given user's followers"""
        return self.select_related(
            'follower__user'
        ).filter(follower__user__is_active=True, followee=user_profile).distinct().order_by("-pk")
    

class Follower(models.Model):
    SOURCES = (
        ('site', 'Site'),
    )
    DEFAULT_SOURCE = 'site'
    followee = models.ForeignKey(UserProfile, related_name='followees')
    follower = models.ForeignKey(UserProfile, related_name='followers')
    source = models.CharField(max_length=25, db_index=True, choices=SOURCES, default=DEFAULT_SOURCE)
    added_on = models.DateTimeField(db_index=True, editable=False, default=datetime.now)

    objects = FollowerManager()

    class Meta:
        unique_together = (('followee', 'follower'),)

    def __unicode__(self):
        return u'%s is followed by %s' % (self.user_profile1, self.user_profile2)
    
    def save(self, **kwargs):
        if not self.added_on:
            self.added_on = datetime.now()
        super(Follower, self).save(**kwargs)
        clear_keys('friends', self.user_profile1.pk)
        clear_keys('friends', self.user_profile2.pk)
        
    @property
    def user_profile1(self):
        return self.followee    

    @property
    def user_profile2(self):
        return self.follower
       

class FriendshipManager(models.Manager):
    def get_friendships(self, user_profile):
        """Return the given user's friends"""
        return user_profile.friends1.select_related(
            'user_profile2__user'
        ).filter(user_profile2__user__is_active=True).distinct().order_by("-pk")

    def make_friends(self, user_profile1, user_profile2, source=None):
        """Save (p1, p2) and (p2, p1) as two complimentary friendships"""
        if source is None:
            source = Friendship.DEFAULT_SOURCE
        friendship1, created = Friendship.objects.get_or_create(
            user_profile1=user_profile2,
            user_profile2=user_profile1,
            defaults={'source':source}
        )
        friendship2, created = Friendship.objects.get_or_create(
            user_profile1=user_profile1,
            user_profile2=user_profile2,
            defaults={'source':source}
        )
        clear_keys('friends', user_profile1.pk)
        clear_keys('friends', user_profile2.pk)
        try:
           PendingFriendship.objects.get(inviter_profile=user_profile1, invitee_profile=user_profile2).delete()
        except PendingFriendship.DoesNotExist:
            pass
        try:
           PendingFriendship.objects.get(inviter_profile=user_profile2, invitee_profile=user_profile1).delete()
        except PendingFriendship.DoesNotExist:
            pass
        try:
           Follower.objects.get(followee=user_profile1, follower=user_profile2).delete()
        except Follower.DoesNotExist:
            pass
        try:
           Follower.objects.get(follower=user_profile1, followee=user_profile2).delete()
        except Follower.DoesNotExist:
            pass
        return friendship2

    def get_friendship(self, user_profile1, user_profile2):
        try:
            return Friendship.objects.get(user_profile1=user_profile1, user_profile2=user_profile2)
        except Friendship.DoesNotExist:
            return None

    def disconnect_friends(self, user_profile1, user_profile2):
        """Delete (p1, p2) and (p2, p1)"""
        try:
           self.get(user_profile1=user_profile1, user_profile2=user_profile2).delete()
        except Friendship.DoesNotExist:
            pass
        try:
           self.get(user_profile1=user_profile2, user_profile2=user_profile1).delete()
        except Friendship.DoesNotExist:
            pass
        try:
           Follower.objects.get(followee=user_profile1, follower=user_profile2).delete()
        except Follower.DoesNotExist:
            pass
        try:
           Follower.objects.get(follower=user_profile1, followee=user_profile2).delete()
        except Follower.DoesNotExist:
            pass

class Friendship(models.Model):
    SOURCES = (
        ('twitter', 'Twitter'),
        ('site', 'Site'),
        ('fb', 'Facebook'),
    )
    DEFAULT_SOURCE = 'twitter'
    user_profile1 = models.ForeignKey(UserProfile, related_name='friends1')
    user_profile2 = models.ForeignKey(UserProfile, related_name='friends2')
    source = models.CharField(max_length=25, db_index=True, choices=SOURCES, default=DEFAULT_SOURCE)    

    objects = FriendshipManager()

    class Meta:
        unique_together = (('user_profile1', 'user_profile2'),)

    def __unicode__(self):
        return u'%s <-> %s' % (self.user_profile1, self.user_profile2)


class PendingFriendshipManager(models.Manager):
    def disconnect_friends(self, user_profile1, user_profile2):
        """Delete (p1, p2) and (p2, p1)"""
        try:
           self.get(inviter_profile=user_profile1, invitee_profile=user_profile2).delete()
        except PendingFriendship.DoesNotExist:
            pass
        try:
           self.get(inviter_profile=user_profile2, invitee_profile=user_profile1).delete()
        except PendingFriendship.DoesNotExist:
            pass


class PendingFriendship(models.Model):
    SOURCES = (
        ('twitter', 'Twitter'),
        ('site', 'Site'),
        ('fb', 'Facebook'),
    )
    DEFAULT_SOURCE = 'fb'
    inviter_profile = models.ForeignKey(UserProfile, related_name='pending_friends_inviter')
    invitee_profile = models.ForeignKey(UserProfile, related_name='pending_friends_invitee')
    source = models.CharField(max_length=25, db_index=True, choices=SOURCES, default=DEFAULT_SOURCE)
    added_on = models.DateTimeField(db_index=True, editable=False, default=datetime.now)

    objects = PendingFriendshipManager()

    class Meta:
        unique_together = (('inviter_profile', 'invitee_profile'),)

    def __unicode__(self):
        return u'%s <-> %s' % (self.inviter_profile, self.invitee_profile)

    def save(self, **kwargs):
        if not self.added_on:
            self.added_on = datetime.now()
        super(PendingFriendship, self).save(**kwargs)


class FBInvitedUser(models.Model):
    inviter_profile = models.ForeignKey(UserProfile)
    fb_userid = models.CharField(max_length=32, db_index=True)
    added_on = models.DateTimeField(db_index=True, editable=False, default=datetime.now)

    class Meta:
        ordering = ('-added_on',)
        unique_together = (('inviter_profile', 'fb_userid'),)

    def __unicode__(self):
        return u'%s <-> %s' % (self.inviter_profile, self.fb_userid)

    def save(self, **kwargs):
        if not self.added_on:
            self.added_on = datetime.now()
        super(FBInvitedUser, self).save(**kwargs)


class FBSuggestedFriends(models.Model):
    user_profile = models.ForeignKey(UserProfile, unique=True)
    friends = models.TextField()
    added_on = models.DateTimeField(db_index=True, editable=False, default=datetime.now)
    
    class Meta:
        ordering = ('-added_on',)
        verbose_name_plural = 'FB suggested friends'

    def __unicode__(self):
        return u'%s' % self.user_profile

    def save(self, **kwargs):
        if not self.added_on:
            self.added_on = datetime.now()
        if not self.friends:
            self.set_friends()
        super(FBSuggestedFriends, self).save(**kwargs)
        
    def set_friends(self, friends=None):
        if not friends:
            friends = set()
        self.friends = base64.encodestring(pickle.dumps(friends, 2)).strip()
        
    def get_friends(self):
        if self.friends:
            return pickle.loads(base64.decodestring(self.friends))
        else:
            return set()

    friendset = property(get_friends, set_friends)
