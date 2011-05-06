"""

Common forms and form utilities

"""
import logging
from datetime import datetime

from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import force_unicode
from django.utils.html import escape, strip_tags
from django.db.models import SlugField
from django.contrib.sites.models import Site
from django.contrib.comments.models import Comment
from django.contrib.contenttypes.models import ContentType
from django.utils.functional import curry
from django import forms
from django.forms import fields

from twitter import TwitterAPI


_log = logging.getLogger("common.forms")


class _ValidatingModelFormMetaclass(type(forms.ModelForm)):
    """Extend built-in ModelForm metaclass to add custom db field cleaners."""
    def __new__(cls, name, bases, attrs):
        new_class = super(_ValidatingModelFormMetaclass, cls).__new__(cls, name, bases, attrs)
        if new_class._meta.model:
            # Extract unique fields.
            for f in new_class._meta.model._meta.fields:
                if not f.primary_key and f.unique and f.editable:
                    cleaner = 'clean_%s' % f.name
                    existing_cleaner = getattr(new_class, cleaner, None)
                    setattr(new_class, cleaner, curry(new_class._db_validating_field_cleaner, field=f, existing_cleaner=existing_cleaner))
        return new_class


class ValidatingModelForm(forms.ModelForm):
    """Add DB model validations."""
    __metaclass__ = _ValidatingModelFormMetaclass

    def _db_validating_field_cleaner(self, field, existing_cleaner=None):
        field_name = field.name
        # If the field has a clean_FIELD method defined, call it first.
        cleaner = 'clean_%s' % field_name
        if existing_cleaner:
            value = existing_cleaner(self)
        else:
            value = self.cleaned_data.get(field_name, None)
        if value:
            if isinstance(field, SlugField):
                value = value.lower() # Check a SlugField case-insensitively.
            # Verify that field's value is unique
            q = self._meta.model._default_manager.filter(**{field_name:value})
            pk = self.instance.pk
            if self.instance.pk:
                q = q.exclude(pk=self.instance.pk)
            if q.count():
                raise forms.ValidationError(_("This value already exists."))
        return value


def get_model_form(model_class):
    class ModelForm(ValidatingModelForm):
        class Meta:
            model = model_class
    return ModelForm


class CommentForm(forms.ModelForm):
    """Newforms compatible form for ``django.contrib.comments``.

    Only supports registered users' comments (not freecomments)

    """
    def __init__(self, author, target_instance, *args, **kwargs):
        """
        Parameters:
            ``author`` - the comment author's User instance
            ``target_instance`` - the object on which this comment is being made
        """
        self.user = author
        self.content_type = ContentType.objects.get_for_model(target_instance)
        self.object_pk = target_instance.pk
        self.is_public = kwargs.pop('is_public', True)
        self.site = kwargs.pop('site', Site.objects.get_current())
        super(CommentForm, self).__init__(*args, **kwargs)
        self.fields['comment'].help_text = _('Plain text only.')
        # If comment tweeting is enabled and the user has a twitter profile,
        # add a tweet option to the form.
        if getattr(settings, 'ENABLE_COMMENT_TWEET', True):
            if self.user.get_profile().has_twitter_access_token:
                self.fields['do_tweet'] = forms.BooleanField(label=_(u"Tweet this message?"), required=False, initial=True)

    class Meta:
        model = Comment
        fields = ('comment',)

    def clean_comment(self):
        comment = self.cleaned_data.get("comment", None)
        if comment:
            comment = force_unicode(strip_tags(comment))
        return comment
    
    def tweet_posted(self, comment, tweet):
        # Subclasses can override this
        pass

    def save(self, commit=True):
        comment = super(CommentForm, self).save(commit=False)
        comment.user = self.user
        comment.content_type = self.content_type
        comment.object_pk = self.object_pk
        comment.is_public = self.is_public
        comment.submit_date = datetime.now()
        comment.site = self.site
        comment.save()
        try:
            if self.cleaned_data.get("do_tweet", False) and getattr(settings, 'ENABLE_COMMENT_TWEET', True):
                tw_prof = self.user.get_profile().twitter_profile
                if tw_prof and tw_prof.access_token:
                    tw = TwitterAPI()
                    tweet = tw.post_status(tw_prof.access_token, comment.comment)
                    tw.close()
                    self.tweet_posted(comment, tweet)                
        except Exception, e:
            _log.exception(e)
        return comment

