from datetime import datetime

from django.db import models
from django.conf import settings
from django.utils.translation import ugettext_lazy as _


class SiteConfig(models.Model):
    name = models.SlugField(_('name'), unique=True, max_length=50,
                            help_text=_('Lowercase name of the configuration parameter. Letters, numbers, and dashes only.'))
    value = models.TextField(_('value'))

    class Meta:
        verbose_name_plural = _('site configuration')
        ordering = ('name',)

    def __unicode__(self):
        return self.name





