from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _


def get_and_delete_messages(user, limit=None):
    messages = []
    count = 0
    for m in user.specialmessage_set.all():
        if not limit or count < limit:
            messages.append(m.message)
        m.delete()
        count += 1
    return messages


class SpecialMessage(models.Model):
    user = models.ForeignKey(User)
    message = models.TextField(_('message'))

    def __unicode__(self):
        return self.message


class KeyValue(models.Model):
    key = models.CharField(max_length=250, db_index=True)
    value = models.CharField(max_length=250)
    category = models.CharField(max_length=25, db_index=True)

    class Meta:
        unique_together = (('key', 'category'),)

    def __unicode__(self):
        return self.key

