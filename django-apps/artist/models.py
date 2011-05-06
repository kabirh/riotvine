from urlparse import urlparse

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.utils.safestring import mark_safe
from django.conf import settings

from rdutils.site import DISPLAY_SITE_URL, site_url
from rdutils.decorators import attribute_cache
from rdutils.url import admin_url

from registration.models import UserProfile


class Genre(models.Model):
    name = models.CharField(_('genre name'), max_length=75, db_index=True, unique=True)

    class Meta:
        ordering = ('name',)

    def __unicode__(self):
        return u'%s' % self.name


class ArtistProfile(models.Model):
    WEBSITE_HELP_TEXT = _("If you have an external website, enter its address here. For example: http://www.pinkfloyd.com")
    user_profile = models.OneToOneField(UserProfile, primary_key=True, related_name='artist_profile')
    name = models.CharField(_('artist/band name'), max_length=64, db_index=True)
    num_members = models.PositiveSmallIntegerField(_('number of band members'), editable=False)
    url = models.SlugField(_('IlliusRock URL'), max_length=25, db_index=True, unique=True,
                           help_text=_('If you enter "pink-floyd" as your url, your public homepage will be at "%s/pink-floyd". Only English letters, numbers, and dashes are allowed.' % DISPLAY_SITE_URL))
    website = models.URLField(_('artist/band website'), max_length=150, verify_exists=True,
        db_index=True, null=True, blank=True, help_text=WEBSITE_HELP_TEXT)
    genres = models.ManyToManyField(Genre)

    def __unicode__(self):
        return u'%s Band: %s' % (self.user_profile.username, self.name)

    def get_absolute_url(self):
        return u'%s/%s/' % (site_url(), self.url)

    def save(self, *args, **kwargs):
        if not self.num_members:
            self.num_members = 2
        super(ArtistProfile, self).save(*args, **kwargs)

    def admin_url_link(self):
        return mark_safe(u'<a href="%s">%s</a>' % (self.get_absolute_url(), self.url))
    admin_url_link.short_description = 'URL'
    admin_url_link.allow_tags = True
    admin_url_link.admin_order_field = 'url'

    def admin_user_profile_link(self):
        return admin_url(self.user_profile)
    admin_user_profile_link.short_description = 'profile'
    admin_user_profile_link.allow_tags = True

    @property
    def artist_or_band(self):
        return self.num_members > 1 and u'band' or u'artist'

    @property
    def is_band(self):
        return self.num_members > 1

    @property
    def is_solo(self):
        return self.num_members == 1

    @property
    @attribute_cache('short_name')
    def short_name(self):
        """Return the band's short name upto ``settings.ARTIST_SHORT_NAME_LENGTH`` characters long."""
        if len(self.name) > settings.ARTIST_SHORT_NAME_LENGTH:
            return mark_safe(u'%s&hellip;' % self.name[:settings.ARTIST_SHORT_NAME_LENGTH])
        else:
            return self.name

    @property
    @attribute_cache('short_name_plain_text')
    def short_name_plain_text(self):
        """Return the band's short name upto ``settings.ARTIST_SHORT_NAME_LENGTH`` characters long."""
        if len(self.name) > settings.ARTIST_SHORT_NAME_LENGTH:
            return u'%s...' % self.name[:settings.ARTIST_SHORT_NAME_LENGTH]
        else:
            return self.name

    @property
    @attribute_cache('short_name_for_twitter')
    def short_name_for_twitter(self):
        """Return (band's short name, mode).
        
        ``mode``
            0 - Short name
            1 - Long name
            2 - Truncated long name
        """
        n = len(self.name)
        if n <= settings.TWITTER_ARTIST_NAME_SHORT_LENGTH:
            return self.name, 0
        elif n <= settings.TWITTER_ARTIST_NAME_MAX_LENGTH:
            return self.name, 1
        else:
            return u"%s..." % self.name[:settings.TWITTER_ARTIST_NAME_MAX_LENGTH-3], 2

    @property
    @attribute_cache('website_hostname')
    def website_hostname(self):
        if self.website:
            p = urlparse(self.website)
            return p.hostname
        else:
            return u''

    @property
    @attribute_cache('paypal')
    def paypal(self):
        """Return the ``PaymentPaypal`` instance for this ArtistProfile."""
        try:
            return self.payment_paypal
        except PaymentPaypal.DoesNotExist:
            return None

    @property
    @attribute_cache('google')
    def google(self):
        """Return the ``PaymentGoogle`` instance for this ArtistProfile."""
        try:
            return self.payment_google
        except PaymentGoogle.DoesNotExist:
            return None

    @property
    @attribute_cache('has_payment_info')
    def has_payment_info(self):
        """Return True if this artist has at least one type of payment info (Paypal or Google)."""
        return self.paypal or self.google

    def get_merchant_account(self, account_type):
        """Return merchant account based on the account_type.

        ``account_type`` may be either 'paypal' or 'google'

        """
        return getattr(self, account_type, None)

    @property
    @attribute_cache('available_payment_modes')
    def available_payment_modes(self):
        modes = []
        if self.paypal:
            modes.append(self.paypal)
        if self.google:
            modes.append(self.google)
        return modes

    @property
    @attribute_cache('google_merchant_id')
    def google_merchant_id(self):
        if not self.google:
            return ''
        return settings.DEV_MODE and settings.GOOGLE_MERCHANT_ID or self.google.google_merchant_id


    @property
    @attribute_cache('google_merchant_key')
    def google_merchant_key(self):
        if not self.google:
            return ''
        return settings.DEV_MODE and settings.GOOGLE_MERCHANT_KEY or self.google.google_merchant_key


class PaymentPaypal(models.Model):
    artist_profile = models.OneToOneField(ArtistProfile, primary_key=True, related_name='payment_paypal')
    paypal_email = models.EmailField(_('PayPal e-mail address'), unique=True, db_index=True)

    @property
    def payment_mode(self):
        return 'paypal'

    @property
    def payment_mode_name(self):
        return 'PayPal'


class PaymentGoogle(models.Model):
    artist_profile = models.OneToOneField(ArtistProfile, primary_key=True, related_name='payment_google')
    google_merchant_id = models.CharField(_('Google Checkout Merchant ID'), unique=True, db_index=True, max_length=50)
    google_merchant_key = models.CharField(_('Google Checkout Merchant Key'), max_length=50)

    @property
    def payment_mode(self):
        return 'google'

    @property
    def payment_mode_name(self):
        return 'Google Checkout'

