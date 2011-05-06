import os

from django import forms
from django.conf import settings
from django.utils.translation import ugettext as _
from django.utils.encoding import force_unicode
from django.utils.html import strip_tags

from photo.utils import get_image_format

from common.forms import ValidatingModelForm
from photo.utils import create_photo_versions
from photo.models import Photo


class PhotoForm(forms.ModelForm):
    class Meta:
        model = Photo
        fields = ('image', 'caption')

    def clean_image(self):
        img = self.cleaned_data["image"]
        if img and hasattr(img, 'name'):
            fname, ext = os.path.splitext(img.name)
            if not ext:
                raise forms.ValidationError(_(u'The file you have uploaded does not have an extension. Only JPEG and PNG images with the file extensions .jpeg, .jpg, or .png are accepted.'))
            if not (ext.lower() in ('.jpeg', '.png', '.jpg') and get_image_format(img) in ('JPEG', 'PNG')):
                raise forms.ValidationError(_(u'The file you have uploaded is not an acceptable image. Only JPEG and PNG images are accepted.'))
            if img.size > settings.PHOTO_MAX_SIZE_MB*1000000:
                sz = img.size / 1000000
                raise forms.ValidationError(_(u"The image file you have uploaded is too big. Please upload a file under %s MB.") % int(settings.PHOTO_MAX_SIZE_MB))
            if img.size == 0:
                raise forms.ValidationError(_(u"The image file you have uploaded is empty. Please upload a real image."))
        return img

    def clean_caption(self):
        caption = self.cleaned_data.get('caption', '')
        if caption:
            caption = force_unicode(strip_tags(caption))
        return caption

    def save(self, commit=True, content_object=None, display_order=None, user=None):
        photo = super(PhotoForm, self).save(commit=False)
        if content_object:
            photo.content_object = content_object
        if display_order:
            photo.display_order = display_order
        if user:
            photo.user = user
        if commit:
            photo.save()
            create_photo_versions(self, photo)
        return photo


class PhotoEditForm(PhotoForm):
    def __init__(self, *args, **kwargs):
        super(PhotoEditForm, self).__init__(*args, **kwargs)

    class Meta(PhotoForm.Meta):
        fields = ('id', 'title', 'caption', 'display_order')

