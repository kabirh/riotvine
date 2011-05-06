"""

FileField storage utilities

Usage:

from django.core.files.storage import FileSystemStorage
from django_storages.backends.s3boto import S3BotoStorage
from rdutils.storage import copyfile
from registration.models import UserProfile

frm = FileSystemStorage()
to = S3BotoStorage()

ux = UserProfile.objects.all()

for u in ux:
    copyfile(u.avatar_image, frm, to)
    copyfile(u.avatar, frm, to)
    copyfile(u.avatar_medium, frm, to)
    print "Converted", u.pk, u
    
    
from django.core.files.storage import FileSystemStorage
from django_storages.backends.s3boto import S3BotoStorage
from rdutils.storage import copyfile
from event.models import Event

frm = FileSystemStorage()
to = S3BotoStorage()


ex = Event.objects.all().order_by("pk")
for e in ex:
    copyfile(e.image, frm, to)
    copyfile(e.image_resized, frm, to)
    copyfile(e.image_square, frm, to)
    copyfile(e.image_square_medium, frm, to)
    copyfile(e.image_avatar, frm, to)
    
    print "------------------------------"
    print e.pk, e
    print "------------------------------"

"""
import logging

from django.conf import settings
from django.core.files.storage import default_storage


_log = logging.getLogger('rdutils.storage')


def copyfile(filefield, from_storage, to_storage):
    """Copy `filefield` from one storage to another.

    `from_storage` and `to_storage` are `django.core.files.Storage` instances.

    """
    if not filefield:
        _log.debug("Skipped empty field")
        return None
    if not from_storage:
        from_storage = default_storage
    name = filefield.name
    try:
        f = from_storage.open(name)
    except IOError:
        #_log.debug("Skipping %s", name)
        return None
    actual_name = to_storage.save(name, f)
    _log.debug("Copied %s -> %s (%s)", name, actual_name, to_storage.url(name))
    return actual_name

