import random
from datetime import date

from django import template
from django.conf import settings
from django.contrib.auth.models import User

from artist.models import ArtistProfile
from photo.models import PhotoSize, PhotoVersion
from campaign import exceptions


register = template.Library()


@register.inclusion_tag("campaign/tags/photo_thumbnails.html")
def campaign_photo_thumbnails(campaign, aspect="thumbnail", title="Campaign photos", limit=None):
    size = PhotoSize.objects.get_thumbnail(cropped=aspect.lower()=='square')
    photos = PhotoVersion.objects.get_for_object(campaign, size=size).order_by("?")
    if limit:
        photos = photos[:int(limit)]
    return {'campaign':campaign, 'photos':photos, 'aspect':aspect.title(), 'title':title}


@register.simple_tag
def campaign_error_message(exception_class_name):
    """DRY: Return campaign error message from campaign.exceptions.*Error"""
    try:
        instance = getattr(exceptions, exception_class_name)()
        return instance.message
    except AttributeError, e:
        if settings.DEV_MODE:
            assert False
        return u''


@register.inclusion_tag("campaign/tags/summary.html", takes_context=True)
def campaign_summary(context, campaign, classes='', is_owner=False, is_admin=False, include_title=False, show_detail_link=False, separate_offering=False, changes=False):
    return {'campaign':campaign, 'classes':classes, 'is_owner':is_owner,
            'is_admin':is_admin, 'include_title':include_title,
            'show_detail_link':show_detail_link,
            'separate_offering':separate_offering,
            'changes':changes,
            'context':context}


def _campaign_badge(campaign, badge_type='i'):
    ctx = {'campaign':campaign}
    from campaign.models import Badge
    try:
        badge = campaign.badge_set.get(badge_type=badge_type)
        ctx['badge'] = badge
    except Badge.DoesNotExist:
        pass
    return ctx


@register.inclusion_tag("campaign/tags/badge_external_code.html")
def campaign_external_badge_code(campaign):
    if not campaign.is_public:
        return {}
    ctx = _campaign_badge(campaign, badge_type='e')
    return ctx


@register.inclusion_tag("campaign/tags/badge_internal.html")
def campaign_badge_internal(campaign, classes='', is_owner=False, is_admin=False):
    ctx = _campaign_badge(campaign, badge_type='i')
    ctx['classes'] = classes
    ctx['is_owner'] = is_owner
    if is_owner or is_admin:
        # Show uncached badge to admin or campaign owner
        ctx['query_string'] = "?q=%s" % random.randint(1000, 1000000)
    return ctx


@register.inclusion_tag("campaign/tags/badge_external.html")
def campaign_badge_external(campaign, classes='', show_code=False, title='', is_owner=False, is_admin=False):
    if not campaign.is_public:
        return {}
    ctx = _campaign_badge(campaign, badge_type='e')
    ctx['classes'] = classes
    ctx['show_code'] = show_code == 'show_code'
    ctx['title'] = title
    ctx['is_owner'] = is_owner
    if is_owner or is_admin:
        # Show uncached badge to admin or campaign owner
        ctx['query_string'] = "?q=%s" % random.randint(1000, 1000000)
    return ctx


@register.inclusion_tag("campaign/tags/blurb_list.html")
def campaign_blurbs_latest(max_num="10"):
    from campaign.models import Campaign
    max_num = int(max_num)
    campaigns = Campaign.objects.active().order_by('-approved_on', '-start_date')[:max_num]
    ctx = {'max_num':max_num, 'campaigns':campaigns}
    return ctx


@register.inclusion_tag("campaign/tags/contributor_list.html", takes_context=True)
def campaign_contributors_latest(context, max_num="10"):
    from campaign.models import Contribution, Ticket
    max_num = int(max_num)
    contribs = Contribution.objects.select_related('contributor', 'campaign').filter(amount__gt=0).order_by('-paid_on')[:max_num]
    tickets = Ticket.objects.select_related('redeemed_by', 'campaign').filter(is_redeemed=True).order_by('-redeemed_on')[:max_num]
    l1 = [(c.paid_on, c) for c in contribs]
    l2 = [(t.redeemed_on, t) for t in tickets]
    lx = l1 + l2
    lx.sort(reverse=True)
    contributors = [c[1] for c in lx[:max_num]]
    ctx = {'max_num':max_num, 'contributors':contributors, 'context':context}
    return ctx


@register.inclusion_tag("campaign/tags/campaign_sponsors.html", takes_context=True)
def campaign_sponsors(context, campaign, max_num="8"):
    max_num = int(max_num)
    u1 = campaign.contribution_set.values_list('contributor_id', flat=True)
    u2 = campaign.ticket_set.filter(is_redeemed=True).values_list('redeemed_by', flat=True)
    ux = set(list(u1) + list(u2)) # Unique contributors across contributions and tickets
    n = len(ux) # Unique contributor count
    contribs = campaign.contribution_set.select_related('contributor').order_by('?')[:max_num]
    tickets = campaign.ticket_set.select_related('redeemed_by', 'campaign').filter(is_redeemed=True).order_by('-redeemed_on')[:max_num]
    # Merge contribs and tickets:
    l1 = [(c.paid_on, c) for c in contribs]
    l2 = [(t.redeemed_on, t) for t in tickets]
    lx = l1 + l2
    x = []
    contributors = []
    # Remove duplicates between contributors and ticket redeemers:
    for c in lx:
        if c[1].contributor.pk not in x:
            x.append(c[1].contributor.pk)
            contributors.append(c[1])
        if len(contributors) == max_num:
            break
    ctx = {'max_num':max_num, 'contributors':contributors, 'context':context, 'campaign':campaign, 'n':n}
    return ctx


def _get_artist(user):
    """Return an ``ArtistProfile`` instance for ``user``.

    ``user`` may be a ``User`` instance or a ``User.username``.

    """
    if not isinstance(user, ArtistProfile):
        if isinstance(user, User):
            artist = user.get_profile().artist
        else:
            artist = ArtistProfile.objects.get(user_profile__user__username=user)
    else:
        artist = user
    return artist


def _apply_limit(campaigns, limit):
    """Internal DRY helper"""
    total_count = campaigns.count()
    has_more = False
    if limit:
        limit = int(limit)
        campaigns = campaigns[:limit]
        has_more = total_count > limit
    return {'campaigns':campaigns, 'has_more':has_more, 'total_count':total_count}


@register.inclusion_tag("campaign/tags/admin_list.html")
def campaigns_active(artist, title='Active campaigns', limit="3"):
    """Render active campaigns; user may be a username, a User instance or an ArtistProfile instance."""
    artist = _get_artist(artist)
    campaigns = artist.campaign_set.active().order_by('start_date')
    ctx = {'title':title, 'campaign_type':'active'}
    ctx.update(_apply_limit(campaigns, limit))
    return ctx


@register.inclusion_tag("campaign/tags/admin_list.html")
def campaigns_approved_upcoming(artist, title='Upcoming campaigns', limit="3"):
    """Render approved campaigns that are starting in the future; user may be a username, a User instance or an ArtistProfile instance."""
    artist = _get_artist(artist)
    campaigns = artist.campaign_set.visible(is_approved=True, start_date__gt=date.today()).order_by('start_date')
    total_count = campaigns.count()
    ctx = {'title':title, 'campaign_type':'approved-upcoming'}
    ctx.update(_apply_limit(campaigns, limit))
    return ctx


@register.inclusion_tag("campaign/tags/admin_list.html")
def campaigns_unsubmitted(artist, title='Unsubmitted campaigns', limit="3"):
    """Render campaigns not yet submitted; user may be a username, a User instance or an ArtistProfile instance."""
    artist = _get_artist(artist)
    campaigns = artist.campaign_set.visible(is_submitted=False).order_by('start_date')
    ctx = {'title':title, 'campaign_type':'unsubmitted'}
    ctx.update(_apply_limit(campaigns, limit))
    return ctx


@register.inclusion_tag("campaign/tags/admin_list.html")
def campaigns_pending_approval(artist, title='Campaigns pending approval', limit="3"):
    """Render campaigns pending approval; user may be a username, a User instance or an ArtistProfile instance."""
    artist = _get_artist(artist)
    campaigns = artist.campaign_set.visible(is_approved=False, is_submitted=True).order_by('start_date')
    ctx = {'title':title, 'campaign_type':'pending-approval'}
    ctx.update(_apply_limit(campaigns, limit))
    return ctx


@register.inclusion_tag("campaign/tags/admin_list.html")
def campaigns_expired(artist, title='Past campaigns', limit="3"):
    """Render past campaigns; user may be a username, a User instance or an ArtistProfile instance."""
    artist = _get_artist(artist)
    campaigns = artist.campaign_set.visible(is_approved=True, end_date__lt=date.today()).order_by('-end_date')
    ctx = {'title':title, 'campaign_type':'expired'}
    ctx.update(_apply_limit(campaigns, limit))
    return ctx


