from django_storages.backends.s3 import S3Storage as SS
from event.models import Event

s = SS()
e = Event.objects.all()[:1].get()
i = e.image_avatar
ix = s.save(i.name, i)
f = s.open(ix)
s.url(ix)

