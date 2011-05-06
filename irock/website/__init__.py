import logging, logging.config, logging.handlers

from django.conf import settings

# Configure logging first
if not logging.getLogger().handlers:
    logging.config.fileConfig('./logging.conf')
    _log = logging.getLogger()
    _log.setLevel(settings.LOG_DEBUG and logging.DEBUG or logging.INFO)

# Add commonly used templatetags to the builtins space so that we don't have
# to keep issuing {% load %} calls in every template.
from django.template import add_to_builtins

add_to_builtins('django.templatetags.cache')
add_to_builtins('django.templatetags.i18n')
add_to_builtins('common.templatetags.commontags')
add_to_builtins('siteconfig.templatetags.siteconfigtags')
add_to_builtins('campaign.templatetags.campaigntags')
add_to_builtins('event.templatetags.eventtags')
add_to_builtins('payment.templatetags.paymenttags')
add_to_builtins('photo.templatetags.phototags')
add_to_builtins('twitter.templatetags.twittertags')

# Invoke customizations to django.contrib apps and third-party apps.
import extensions.extend

import socket
socket.setdefaulttimeout(20)

