"""

Various signal hooks to extend the functionality of 
external applications (django.contrib.* and third party apps)

"""
import logging

from django.conf import settings
from django.db.models import signals
from django.core.cache import cache
from messages.models import Message
from messages.utils import new_message_email

from campaign.models import Campaign
from campaign import signals as campaign_signals


_log = logging.getLogger('extensions.signal_extensions')


def clear_inbox_cache(sender, instance, **kwargs):
    """
    When a ``Message`` object is saved, refresh the message count cache for 
    that message's sender and recipient.
    """
    for user in (instance.sender, instance.recipient):
        key = 'message-count-%s' % user.pk
        cache.delete(key)

signals.post_save.connect(clear_inbox_cache, sender=Message)


def expire_campaign_cache(sender, instance, **kwargs):
    """
    When a campaign is changed by an admin, expire the 
    cached keys for campaigns.
    """
    if isinstance(instance, Campaign):
        for key in (u'ir-top3-campaigns',
                    u'ir-tpl-hp-top3-campaigns',
                    u'ir-tpl-hp-newest-campaigns'):
            cache.delete(key)
        _log.debug("Cleared campaign cache.")

campaign_signals.post_campaign_admin_change.connect(expire_campaign_cache, sender=Campaign)


try:
    # Disconnect messaging notification
    if not getattr(settings, 'MESSAGE_EMAIL_NOTIFICATION_ENABLED', False):
        signals.post_save.disconnect(new_message_email, sender=Message)
except IndexError:
    # Caused by a Django bug
    pass

