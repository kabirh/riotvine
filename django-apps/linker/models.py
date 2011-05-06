from datetime import datetime, date, timedelta

from django.db import models
from django.utils import simplejson as json
from django.utils.translation import ugettext_lazy as _


class WebLink(models.Model):
    url = models.CharField(max_length=200, db_index=True, unique=True, help_text="Only lowercase alphabets, numbers, and dashes are allowed.")
    redirect_to = models.TextField(blank=True, help_text=u"Where to redirect the above URL")
    category = models.CharField(max_length=100, db_index=True, help_text=u"The admin area uses this to group links of the same type.")
    email_count = models.IntegerField(default=0, db_index=True, help_text=u"Number of people who visited this link from emails")
    web_count = models.IntegerField(default=0, db_index=True, help_text=u"Number of people who visited this link from web pages")
    total_count = models.IntegerField(default=0, db_index=True, help_text=u"Number of people who visited this link from emails and web pages")
    updated_on = models.DateTimeField(default=datetime.now, db_index=True)

    def __unicode__(self):
        return self.url

    def save(self, *args, **kwargs):
        self.updated_on = datetime.now()
        self.url = self.url.lower()
        if not self.redirect_to:
            self.redirect_to = u''
        self.total_count = self.email_count + self.web_count
        super(WebLink, self).save(*args, **kwargs)

