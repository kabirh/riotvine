import logging

from django.conf import settings
from django.http import HttpResponseRedirect, Http404, HttpResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.core.urlresolvers import reverse
from django.db import transaction
from django.db.models import Q
from django.core.paginator import Paginator, InvalidPage
from django.contrib.auth.decorators import login_required, permission_required
from django.utils.translation import ugettext as _
from django.utils import simplejson
from django.shortcuts import get_object_or_404
from django.template import Context, loader
from django.forms.models import modelformset_factory

from rdutils.render import render_view
from artist.decorators import artist_account_required
from event.models import Event
from event.photo import forms
from photo.forms import PhotoForm, PhotoEditForm
from photo.models import PhotoSize, PhotoVersion, Photo


_log = logging.getLogger('event.photo.views')


@login_required
@transaction.commit_on_success
def upload(request, event_id, template='event/photo/upload_form.html'):
    event = get_object_or_404(Event.visible_objects,
            Q(artist__user_profile__user=request.user) |
            Q(creator__user=request.user),
            pk=event_id)
    user = request.user
    event_url = event.get_absolute_url()
    photo_url = reverse('list_event_photos', kwargs={'event_id':event.pk})
    if request.POST:
        form = PhotoForm(data=request.POST, files=request.FILES)
        if form.is_valid():
            photo = form.save(content_object=event)
            _log.info('Photo uploaded: (%s) %s', photo.pk, photo.title)
            special_mesg = _('''<a href="%s">New photos</a> have been added to one of <a href="%s">your shows.</a>''' % (photo_url, event_url))
            event.notify_attendees(special_mesg, exclude=[user.pk])
            if 'Another' in request.POST.get('submit', 'Add'):
                user.message_set.create(message=_("%s Photo uploaded. You can add another photo below.") % photo.image_preview('square_thumbnail'))
                return HttpResponseRedirect(reverse('upload_event_photo', kwargs={'event_id':event.pk}))
            else:
                user.message_set.create(message=_("Photo uploaded."))
                return HttpResponseRedirect(event_url)
    else:
        form = PhotoForm()
    ctx = {'event':event, 'form':form, 'allow_another':True}
    return render_view(request, template, ctx)


@login_required
@transaction.commit_on_success
def member_upload(request, event_id, template='event/photo/upload_form.html'):
    event = get_object_or_404(Event.objects.public().select_related('artist__user_profile__user'), pk=event_id)
    user = request.user
    if event.owner.pk == request.user.pk:
        return HttpResponseRedirect(reverse('upload_event_photo', kwargs={'event_id':event.pk}))
    # Ensure that this user can't upload more photos than the allowed limit.
    photo_count = Photo.objects.get_for_object(event, user=request.user).count()
    limit = settings.EVENT_MAX_PHOTOS_PER_MEMBER
    event_url = reverse('view_event', kwargs={'event_id':event.pk})
    photo_url = reverse('list_event_photos', kwargs={'event_id':event.pk})
    if photo_count >= limit:
        user.message_set.create(message=_("You can not upload more than %s photos to this event." % limit))
        return HttpResponseRedirect(reverse('view_event', kwargs={'event_id':event.pk}))
    if request.POST:
        form = forms.MemberPhotoForm(data=request.POST, files=request.FILES)
        if form.is_valid():
            if photo_count == limit:
                submit = 'Add'
            else:
                submit = request.POST.get('submit', 'Add')
            photo = form.save(content_object=event, display_order=9999999, user=request.user_profile)
            _log.info('Photo uploaded: (%s) %s', photo.pk, photo.title)
            special_mesg = _('''<a href="%s">New photos</a> have been added to one of <a href="%s">your shows.</a>''' % (photo_url, event_url))
            event.notify_attendees(special_mesg, exclude=[user.pk])
            if 'Another' in submit:
                user.message_set.create(message=_("%s Photo uploaded. You can add another photo below.") % photo.image_preview('square_thumbnail'))
                return HttpResponseRedirect(reverse('upload_event_photo_member', kwargs={'event_id':event.pk}))
            else:
                user.message_set.create(message=_("Photo uploaded."))
                return HttpResponseRedirect(reverse('view_event', kwargs={'event_id':event.pk}))
    else:
        form = forms.MemberPhotoForm()
    ctx = {'event':event, 'form':form, 'allow_another':photo_count < limit-1, 'member_mode':True}
    return render_view(request, template, ctx)


@login_required
@transaction.commit_on_success
def edit(request, event_id, template='event/photo/edit_form.html'):
    """Edit photos associated with a event."""
    event = get_object_or_404(Event.visible_objects,
            Q(artist__user_profile__user=request.user) |
            Q(creator__user=request.user),
            pk=event_id)
    photoset = Photo.objects.get_for_object(event)
    photo_dict = dict([(p.pk, p) for p in photoset])
    PhotoEditFormSet = modelformset_factory(Photo,
                                            form=PhotoEditForm,
                                            fields=PhotoEditForm._meta.fields,
                                            exclude=PhotoEditForm._meta.exclude,
                                            max_num=0,
                                            extra=0,
                                            can_delete=True)
    if request.POST:
        formset = PhotoEditFormSet(data=request.POST, files=request.FILES, queryset=photoset)
        if formset.is_valid():
            edited_photos = formset.save()
            _log.info(u'Photos updated for event: %s', event)
            request.user.message_set.create(message=_("Photos updated."))
            return HttpResponseRedirect(reverse('list_event_photos', kwargs={'event_id':event.pk}))
    else:
        formset = PhotoEditFormSet(queryset=photoset)
    ctx = {'event':event, 'formset':formset, 'photo_dict':photo_dict}
    return render_view(request, template, ctx)


def list_photos(request, event_id, cropped=False, template='event/photo/list.html'):
    try:
        event = get_object_or_404(Event.visible_objects, pk=event_id)
        is_owner = request.user.is_authenticated() and event.owner.pk == request.user.pk
        if not event.is_public:
            # Allow event owner to see photos of unreleased event.
            # Disallow everyone else.
            if not is_owner:
                raise Http404
        size = PhotoSize.objects.get_thumbnail(cropped=cropped)
        m_size = PhotoSize.objects.get_thumbnail(cropped=True)
        photos = PhotoVersion.objects.get_for_object(event, size=size, photo__user__pk=event.owner_profile.pk)[:50]
        member_photos = PhotoVersion.objects.get_for_object(event, size=m_size).exclude(
            photo__user__pk=event.owner_profile.pk
        ).order_by('photo__user__user__username', '-id')
        paginator = Paginator(member_photos, settings.PHOTO_THUMBNAILS_PER_PAGE, orphans=3)
        page = paginator.page(request.REQUEST.get('page', 1))
        ctx = {'event':event, 'photos':photos, 'cropped':cropped, 'page':page, 'paginator':paginator, 'is_owner':is_owner}
        return render_view(request, template, ctx)
    except InvalidPage:
        raise Http404


def view(request, thumbnail_id, template='event/photo/view.html'):
    try:
        photo_version = get_object_or_404(PhotoVersion, pk=thumbnail_id)
        event = photo_version.photo.content_object
        if not event.is_public:
            # Allow only event owner to see photos of unreleased event.
            if not (event.owner == request.user):
                raise Http404
        size = PhotoSize.objects.get_medium()
        photos = PhotoVersion.objects.get_for_object(event, size=size)
        paginator = Paginator(photos, 1, orphans=0) # Show one medium-sized photo per page
        page_num = request.REQUEST.get('page', 0)
        if not page_num:
            # Find the page on which this photo falls assuming there's one photo per page.
            page_num = 1 # default is page #1
            photo_values = photos.values('photo_id')
            for n, o in enumerate(photo_values):
                if o['photo_id'] == photo_version.photo.pk:
                    page_num = n + 1
                    break
        try:
            page = paginator.page(page_num)
        except InvalidPage:
            page = paginator.page(1)
        index_link = reverse('list_event_photos', kwargs={'event_id':event.pk})
        is_owner = request.user.is_authenticated() and request.user.pk == event.owner.pk
        ctx = {'event':event,
               'page':page,
               'paginator':paginator,
               'is_owner':event.owner == request.user,
               'index_link':index_link,
               'is_owner':is_owner}
        if request.is_ajax():
            for photo in page.object_list:
                ph = photo
                break
            ctx.update({'request':request, 'photo':ph})
            photo_html = loader.get_template("photo/tags/one-photo.html").render(Context(ctx))
            json = {
                'success':True,
                'photo_next_page':page.next_page_number(),
                'photo_pk':ph.pk,
                'photo_html':photo_html
            }
            return HttpResponse(simplejson.dumps(json), mimetype='application/json')
        return render_view(request, template, ctx)
    except InvalidPage:
        raise Http404


@login_required
@transaction.commit_on_success
def delete(request, event_id, template='event/photo/view.html'):
    if request.POST:
        photo_id = request.POST['photo_id']
        photo_version = get_object_or_404(PhotoVersion, pk=photo_id)
        event = photo_version.photo.content_object
        if event.pk == int(event_id) and (event.owner.pk == request.user.pk or request.user.is_staff):
            photo_version.photo.delete()
            photo_version.delete()
            request.user.message_set.create(message=_("That photo has been deleted."))
            list_url = reverse('list_event_photos', kwargs={'event_id':event_id})
            return HttpResponseRedirect(list_url)
    return HttpResponseForbidden()

