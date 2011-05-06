from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.conf import settings


class ServiceProvider(models.Model):
    host = models.CharField(_('host'), max_length=64, unique=True, db_index=True, help_text=_('For example, youtube.com.'))
    service_type = models.CharField(_('service type'), max_length=15, db_index=True, default='video', choices=settings.OEMBED_SUPPORTED_SERVICES)
    url_scheme = models.CharField(_('URL scheme'), max_length=255, db_index=True)
    json_endpoint = models.CharField(_('JSON endpoint'), max_length=255, db_index=True)
    max_width = models.PositiveIntegerField(_('max width'), default=350)
    keys = models.CharField(_('response keys'), max_length=255, default='width, height, html')
    format_parameter_required = models.BooleanField(_('Format parameter required'), default=True, help_text=_('Whether the format parameter is required in the query string.'))

    class Meta:
        ordering = ('host',)

    def __unicode__(self):
        return self.host
