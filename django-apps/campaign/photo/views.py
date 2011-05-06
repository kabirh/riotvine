import logging

from django.conf import settings
from django.http import HttpResponseRedirect, Http404, HttpResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.core.urlresolvers import reverse
from django.db import transaction
from django.core.paginator import Paginator, InvalidPage
from django.contrib.auth.decorators import login_required, permission_required
from django.utils.translation import ugettext as _
from django.shortcuts import get_object_or_404
from django.forms.models import modelformset_factory

from rdutils.render import render_view
from artist.decorators import artist_account_required
from campaign.models import Campaign
from photo.forms import PhotoForm, PhotoEditForm
from photo.models import PhotoSize, PhotoVersion, Photo


_log = logging.getLogger('campaign.photo.views')


@artist_account_required
@transaction.commit_on_success
def upload(request, campaign_id, template='campaign/photo/upload_form.html'):
    campaign = get_object_or_404(Campaign.visible_objects, pk=campaign_id, artist__user_profile__user=request.user)
    user = request.user
    campaign_url = campaign.get_absolute_url()
    photo_url = reverse('list_campaign_photos', kwargs={'campaign_id':campaign.pk})
    if request.POST:
        form = PhotoForm(data=request.POST, files=request.FILES)
        if form.is_valid():
            photo = form.save(commit=False)
            photo.content_object = campaign
            photo.save()
            _log.info('Photo uploaded: (%s) %s', photo.pk, photo.title)
            special_mesg = _('''<a href="%s">New photos</a> have been added to one of <a href="%s">your campaigns.</a>''' % (photo_url, campaign_url))
            campaign.notify_contributors(special_mesg, exclude=[user.pk])
            if 'Another' in request.POST.get('submit', 'Add'):
                request.user.message_set.create(message=_("%s Photo uploaded. You can add another photo below.") % photo.image_preview('square_thumbnail'))
                return HttpResponseRedirect(reverse('upload_campaign_photo', kwargs={'campaign_id':campaign.pk}))
            else:
                request.user.message_set.create(message=_("Photo uploaded."))
                return HttpResponseRedirect(reverse('view_campaign', kwargs={'campaign_id':campaign.pk}))
    else:
        form = PhotoForm()
    ctx = {'campaign':campaign, 'form':form}
    return render_view(request, template, ctx)


@artist_account_required
@transaction.commit_on_success
def edit(request, campaign_id, template='campaign/photo/edit_form.html'):
    """Edit photos associated with a campaign."""
    campaign = get_object_or_404(Campaign.visible_objects, pk=campaign_id, artist__user_profile__user=request.user)
    photoset = Photo.objects.get_for_object(campaign)
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
            _log.info(u'Photos updated for campaign: %s', campaign)
            request.user.message_set.create(message=_("Photos updated."))
            return HttpResponseRedirect(reverse('list_campaign_photos', kwargs={'campaign_id':campaign.pk}))
    else:
        formset = PhotoEditFormSet(queryset=photoset)
    ctx = {'campaign':campaign, 'formset':formset, 'photo_dict':photo_dict}
    return render_view(request, template, ctx)


def list_photos(request, campaign_id, cropped=False, template='campaign/photo/list.html'):
    try:
        campaign = get_object_or_404(Campaign.visible_objects, pk=campaign_id)
        is_owner = request.user.is_authenticated() and campaign.owner.pk == request.user.pk
        if not campaign.is_public:
            # Allow campaign owner to see photos of unreleased campaign.
            # Disallow everyone else.
            if not is_owner:
                raise Http404
        size = PhotoSize.objects.get_thumbnail(cropped=cropped)
        photos = PhotoVersion.objects.get_for_object(campaign, size=size)
        paginator = Paginator(photos, settings.PHOTO_THUMBNAILS_PER_PAGE, orphans=3)
        page = paginator.page(request.REQUEST.get('page', 1))
        ctx = {'campaign':campaign, 'cropped':cropped, 'page':page, 'paginator':paginator, 'is_owner':is_owner}
        return render_view(request, template, ctx)
    except InvalidPage:
        raise Http404


def view(request, thumbnail_id, template='campaign/photo/view.html'):
    try:
        photo_version = get_object_or_404(PhotoVersion, pk=thumbnail_id)
        campaign = photo_version.photo.content_object
        if not campaign.is_public:
            # Allow only campaign owner to see photos of unreleased campaign.
            if not (campaign.owner == request.user):
                raise Http404
        size = PhotoSize.objects.get_medium()
        photos = PhotoVersion.objects.get_for_object(campaign, size=size)
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
        page = paginator.page(page_num)
        index_link = reverse('list_campaign_photos', kwargs={'campaign_id':campaign.pk})
        ctx = {'campaign':campaign,
               'page':page,
               'paginator':paginator,
               'is_owner':campaign.owner == request.user,
               'index_link':index_link}
        return render_view(request, template, ctx)
    except InvalidPage:
        raise Http404


