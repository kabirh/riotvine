from django import template
from django.core.cache import cache

from photo.models import Photo

register = template.Library()


@register.inclusion_tag('photo/tags/photo_prev_next.html')
def photo_prev_next(request, paginator, page, index_link=""):
    """Show square thumbnail of previous and next photo. 

    If `index_link` is provided, it should be the thumbnail page's URL.
    The paginator's objects per page is assumed to be 1.

    """
    current_page = page.number
    next_page = page.has_next() and page.next_page_number()
    previous_page = page.has_previous() and page.previous_page_number()
    photoversions = paginator.object_list
    previous_object, next_object = None, None
    photo_values = photoversions.values('id')[:current_page + 1]
    for n, o in enumerate(photo_values):
        pn = n + 1
        if pn == previous_page:
            previous_object = photoversions.get(pk=o['id']).photo
        if pn == next_page:
            next_object = photoversions.get(pk=o['id']).photo
    return dict(request=request,                
                paginator=paginator,
                page=page,
                index_link=index_link,
                previous_object=previous_object,
                next_object=next_object)

@register.simple_tag
def photo_thumbnail(photo_id, photo_dict=None, aspect='thumbnail'):
    """Return thumbnail version of photo.

    If `photo_dict` is given, look up the photo_id in it. Otherwise, use
    a DB query.

    """
    if not photo_dict:
        photo = Photo.objects.get(pk=photo_id)
    else:
        photo = photo_dict[photo_id]
    thumb = getattr(photo, aspect)
    if not thumb:
        return ''
    return '''<img src="%s" width="%s" height="%s"
                   alt="%s"/>''' % (thumb.image.url, thumb.width, thumb.height,
                                    thumb.alt_text)
