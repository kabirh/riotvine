import logging
import new
from datetime import datetime, timedelta

from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.utils.safestring import mark_safe


_log = logging.getLogger('queue.models')
_TIMEOUT = settings.QUEUE_TIMEOUT_MINUTES
_PURGE_DAYS = settings.QUEUE_PURGE_TIME_DAYS


class ActionItemManager(models.Manager):
    def fetch_new_action_items(self, max_num=25):
        """Return up to ``max_num`` ActionItems that are in ``new`` status. 

        Any ActionItem returned is set to 'in-progress', so that future
        invocations won't retrieve it until after an expiration time.

        Items with category `admin` are not returned.

        """
        now = datetime.now()
        results = self.filter(status='new').exclude(category='admin').order_by('-id')[:max_num]
        actions = list(results)
        id_list = [a.pk for a in actions]
        if id_list:
            self.filter(pk__in=id_list).update(status='in-progress', updated_on=now)
        return actions
    # Some aliases to the above function:
    fetch_new_actions = fetch_new_action_items
    pop = fetch_new_action_items

    def cleanup(self, timeout=_TIMEOUT, purge_days=_PURGE_DAYS):
        """
        1. Look for old ``in-progress`` tasks and turn them to ``New``.
        2. Delete ``done`` tasks that were completed ``QUEUE_PURGE_TIME_DAYS`` ago.

        Old ``in-progress`` tasks are defined as ``ActionItem``s that 
        that have been in that status for longer than ``TIMEOUT_MINUTES``.

        """
        now = datetime.now()
        timeout_threshold = now - timedelta(minutes=timeout)
        self.filter(status='in-progress', updated_on__lt=timeout_threshold).update(status='new', updated_on=now)
        purge_threshold = now - timedelta(days=purge_days)
        self.filter(status='done', updated_on__lt=purge_threshold).delete()

    def q_category_action(self, category, target, action, name=''):
        """Conveniently queue up a category's action.

        If a ``new`` or ``in-progress`` instance of this action already exists
        on this target, don't create a new one.

        The return value is the action item instance that was created or found.

        """
        ctype = ContentType.objects.get_for_model(target)
        a = self.filter(status__in=['new', 'in-progress'], category=category, action=action, target_type__id=ctype.id, target_id=target.pk)
        if a:
            return a[0]
        return self.create(status='new', action=action, target=target, category=category, name=name)

    def q_action_done(self, target, action):
        """Conveniently mark an action as done.

        All ``new`` or ``in-progress`` matching actions on ``target`` are 
        marked as ``done``.

        """
        ctype = ContentType.objects.get_for_model(target)
        self.filter(status__in=['new', 'in-progress'],
                    action=action,
                    target_type__id=ctype.id,
                    target_id=target.pk).update(status='done', updated_on=datetime.now())


# Dynamically, add class methods of the form:
#   q_<category>_action and 
#   q_<category>_action_done
# to the ActionItemManager class
for category, category_name in settings.QUEUE_CATEGORY_CHOICES:
    method_name = 'q_%s_action' % category
    if not hasattr(ActionItemManager, method_name):
        class _Curry(object):
            def __init__(self, category_name):
                self.category = category_name
            def __call__(self, manager_instance, target, action, name=''):
                return ActionItemManager.q_category_action(manager_instance, category=self.category, target=target, action=action, name=name)
        class_method = new.instancemethod(_Curry(category), None, ActionItemManager)
        setattr(ActionItemManager, method_name, class_method)
        setattr(ActionItemManager, '%s_done' % method_name, ActionItemManager.q_action_done)


class ActionItem(models.Model):
    """An ActionItem is a queuing mechanism that allows parts of the online
    web application to schedule tasks that are meant to be run by 
    batch processing scripts.

    """
    STATUS_CHOICES = (('new', 'New'), ('in-progress', 'In progress'), ('done', 'Done'), ('cant-perform', "Can't perform"))

    name = models.CharField(max_length=100, blank=True, help_text=_('An optional name for this ActionItem.'))
    category = models.CharField(choices=settings.QUEUE_CATEGORY_CHOICES, max_length=25, db_index=True,
                                help_text=_("Items in category 'Admin' are not automatically processed."))
    action = models.CharField(choices=settings.QUEUE_ACTION_CHOICES, max_length=25, db_index=True,
                              help_text=_('The action to be performed.'))
    status = models.CharField(choices=STATUS_CHOICES, default='new', max_length=25, db_index=True)
    target_type = models.ForeignKey(ContentType, help_text=_('The type of object on which this action is performed.'))
    target_id = models.PositiveIntegerField(help_text=_('The id of the object on which this action is performed.'))
    target = generic.GenericForeignKey(ct_field="target_type", fk_field="target_id")
    notes = models.TextField(blank=True, help_text=_('For admin reference.'))
    added_on = models.DateTimeField(default=datetime.now)
    updated_on = models.DateTimeField(default=datetime.now)

    objects = ActionItemManager()

    class Meta:
        ordering = ('-added_on',)

    def __unicode__(self):
        return u'%s (%s)' % (self.action, self.get_category_display())

    def save(self, **kwargs):
        if not self.added_on:
            self.added_on = datetime.now()
        self.updated_on = datetime.now()
        super(ActionItem, self).save(**kwargs)

    def target_link(self):
        try:
            return mark_safe(u'<a href="%s">%s</a>' % (self.target.get_absolute_url(), self.target))
        except AttributeError, e:
            return ''
    target_link.allow_tags = True
    target_link.short_description = "target"

