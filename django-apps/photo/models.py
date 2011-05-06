from datetime import datetime
from uuid import uuid4
import os.path

from django.db import models
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import UploadedFile
from django.contrib.contenttypes import generic
from django.utils.translation import ugettext_lazy as _
from django.utils.safestring import mark_safe

from rdutils.decorators import attribute_cache, function_cache
from photo.utils import create_photo_versions, remove_model_image
from registration.models import UserProfile


class PhotoSizeManager(models.Manager):
    @function_cache('photosize-thumb')
    def get_thumbnail(self, cropped=False):
        """Return the smallest size by height."""
        try:
            size = self.filter(do_crop=cropped).order_by('max_height')[:1].get()
        except PhotoSize.DoesNotExist:
            size = None
        return size

    def get_square_thumbnail(self):
        return self.get_thumbnail(cropped=True)

    @function_cache('photosize-medium')
    def get_medium(self, cropped=False):
        """Return the tallest size instance."""
        try:
            return self.filter(do_crop=cropped).order_by('-max_height')[:1].get()
        except PhotoSize.DoesNotExist:
            return None


class PhotoSize(models.Model):
    name = models.CharField(_('name'), max_length=255, help_text=_('A short name for this size. For example: Thumbnail, Medium, Large.'))
    max_width = models.PositiveIntegerField(_('max width'), db_index=True, help_text=_('In pixels.'))
    max_height = models.PositiveIntegerField(_('max height'), db_index=True, help_text=_('In pixels.'))
    do_crop = models.BooleanField(_('do crop'), default=False)

    objects = PhotoSizeManager()

    class Meta:
        unique_together = (('max_width', 'max_height', 'do_crop'),)

    def __unicode__(self):
        return u"%s" % self.name

    @property
    def bounding_box(self):
        return (self.max_width, self.max_height)


class PhotoManager(models.Manager):
    def get_for_object(self, content_object, **kwargs):
        """Return Photo instances whose `photo.content_object` matches the given `content_object`."""
        ctype = ContentType.objects.get_for_model(content_object)
        return self.filter(object_id=content_object.pk,
                           content_type__pk=ctype.pk,
                           **kwargs).order_by('display_order', '-id')



# Custom image field
class PhotoImageField(models.ImageField):   
    def generate_filename(self, instance, filename):
        ext = os.path.splitext(filename)[1]
        if not ext:
            ext = '.jpg'
        filename = 'ph-%s%s' % (uuid4().hex, ext)
        return super(PhotoImageField, self).generate_filename(instance, filename)

    def save_form_data(self, instance, data):
        """Override default field save action and create resized event images.

        `instance` is a event instance.

        """
        if data and isinstance(data, UploadedFile):
            # A new file is being uploaded. So delete the old one.
            remove_model_image(instance, 'image')
        super(PhotoImageField, self).save_form_data(instance, data)


class Photo(models.Model):
    """A photo that may be associated with any generic object."""
    user = models.ForeignKey(UserProfile)
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField(_('object ID'), db_index=True)
    content_object = generic.GenericForeignKey()
    image = PhotoImageField(upload_to='photos/%Y-%b',
                              max_length=250,
                              width_field='width',
                              height_field='height',
                              help_text=_("""
                                <ul>
                                    <li>The image format must be either JPEG or PNG.</li> 
                                    <li>The file size must be under %s MB.</li>
                                </ul>""" % int(settings.PHOTO_MAX_SIZE_MB)))
    width = models.PositiveIntegerField(_('width'), db_index=True, editable=False)
    height = models.PositiveIntegerField(_('height'), db_index=True, editable=False)
    title = models.CharField(_('title'), max_length=255, blank=True, help_text=_('A short title for the photo.'))
    caption = models.TextField(_('caption'), max_length=3000, blank=True, help_text=_('A caption for the photo in plain-text.'))
    display_order = models.PositiveIntegerField(_('display order'), default=10, db_index=True,
                                                help_text=_('Lower numbered photos will appear before higher numbered ones.'))
    added_on = models.DateTimeField(blank=True, editable=False, db_index=True)

    objects = PhotoManager()

    class Meta:
        ordering = ('display_order', '-id')

    def save(self, **kwargs):
        if not self.pk:
            self.added_on = datetime.now()
        try:
            self.user
        except ObjectDoesNotExist:
            # If the content object has an owner_profile or owner attribute, treat that as the 
            # `user` of this photo.
            user = getattr(self.content_object, 'owner_profile', None)
            if user:
                self.user = user
            else:
                user = getattr(self.content_object, 'owner', None)
                if user:
                    self.user = user.get_profile()
        super(Photo, self).save(**kwargs)

    def container(self):
        return self.content_object

    @property
    @attribute_cache('alt_text')
    def alt_text(self):
        if self.title:
            return self.title
        else:
            return u"%s's photo (%s)" % (self.user.username, self.content_object)

    @property
    @attribute_cache('square_thumbnail')
    def square_thumbnail(self):
        thumb_size = PhotoSize.objects.get_thumbnail(cropped=True)
        if thumb_size:
            thumbnail = self.photoversion_set.filter(size=thumb_size)[:1]
            if thumbnail:
                return thumbnail[0]
        return None

    @property
    @attribute_cache('thumbnail')
    def thumbnail(self):
        thumb_size = PhotoSize.objects.get_thumbnail(cropped=False)
        if thumb_size:
            thumbnail = self.photoversion_set.filter(size=thumb_size)[:1]
            if thumbnail:
                return thumbnail[0]
        return None

    def image_preview(self, thumb_type='thumbnail', alt=None):
        """Return HTML fragment to display image thumbnail if available."""
        thumb = getattr(self, thumb_type, None)
        if not alt:
            alt = self.alt_text
        if thumb:
            h = '<img src="%s" alt="%s" width="%s" height="%s"/>' % (thumb.image.url,
                                                                     alt,
                                                                     thumb.width,
                                                                     thumb.height)
            return mark_safe(h)
        return u''
    image_preview.allow_tags = True
    image_preview.short_description = 'thumbnail'

#
# Instead of using signals, we explicitly call the photo version creation routine 
# through photo upload forms
# models.signals.post_save.connect(create_photo_versions, sender=Photo)
#

class PhotoVersionManager(models.Manager):
    def get_for_object(self, content_object, **kwargs):
        """Return PhotoVersion instances whose `photo.content_object` matches the given `content_object`."""
        ctype = ContentType.objects.get_for_model(content_object)
        return self.select_related('photo__user__user').filter(photo__object_id=content_object.pk,
                                   photo__content_type__pk=ctype.pk,
                                   **kwargs).order_by('photo__display_order', 'photo__user__user__username', '-id')


class PhotoVersion(models.Model):
    """A resized version of a Photo scaled down or cropped to fit the bounding box defined by `size`."""
    photo = models.ForeignKey(Photo)
    size = models.ForeignKey(PhotoSize)
    image = models.ImageField(upload_to='photos/versions/%Y-%b', max_length=250, width_field='width', height_field='height')
    width = models.PositiveIntegerField(_('width'), db_index=True)
    height = models.PositiveIntegerField(_('height'), db_index=True)
    updated_on = models.DateTimeField(blank=True, editable=False, db_index=True)

    objects = PhotoVersionManager()

    class Meta:
        unique_together = (('photo', 'size'),)

    def save(self, **kwargs):
        self.updated_on = datetime.now()
        super(PhotoVersion, self).save(**kwargs)

    @property
    @attribute_cache('owner')
    def owner(self):
        return self.photo.user

    @property
    @attribute_cache('owner_username')
    def owner_username(self):
        return self.photo.user.username

    @property
    @attribute_cache('title')
    def title(self):
        return self.photo.title

    @property
    @attribute_cache('caption')
    def caption(self):
        return self.photo.caption

    @property
    @attribute_cache('display_order')
    def display_order(self):
        return self.photo.display_order

    @property
    @attribute_cache('alt_text')
    def alt_text(self):
        return self.photo.alt_text

