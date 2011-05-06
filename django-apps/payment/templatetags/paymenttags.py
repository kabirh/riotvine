from datetime import date

from django import template
from django.conf import settings
from django.core.urlresolvers import reverse

from rdutils.site import site_url, secure_site_url


register = template.Library()


@register.simple_tag
def currency_default():
    return settings.CURRENCY_DEFAULT


@register.simple_tag
def paypal_submit_url(artist=None):
    return settings.PAYPAL_POST_URL


@register.simple_tag
def google_submit_url(artist):
    return settings.GOOGLE_POST_URL + artist.google_merchant_id


@register.simple_tag
def google_button_image_url(artist):
    return settings.GOOGLE_CHECKOUT_IMAGE_URL + artist.google_merchant_id


@register.simple_tag
def paypal_receiver_email(artist):
    """Return email address where artist receives PayPal payments.

    Return a preset development address when we are in development mode.
    """
    return settings.DEV_MODE and settings.PAYPAL_RECEIVER_EMAIL_ADDRESS or artist.paypal.paypal_email


@register.simple_tag
def paypal_notification_url():
    """Return the URL to which we want PayPal to post a payment notification (IPN)."""
    domain = settings.DEV_MODE and site_url() or secure_site_url()
    return u'%s%s' % (domain, reverse('paypal_notification'))

