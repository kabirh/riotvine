from __future__ import absolute_import
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta, SU,MO, TU, WE, TH, FR, SA
import calendar as pycalendar
import vobject
import logging
import random
import csv
from time import time
from sys import exc_info
from traceback import format_exception
import os
import urllib2
from uuid import uuid4

from django.utils.http import urlencode
from django.utils.encoding import iri_to_uri
from django.utils import simplejson as json
from django.conf import settings
from django.http import HttpResponseRedirect, Http404, HttpResponse, HttpResponseForbidden, HttpResponseBadRequest, HttpResponseNotAllowed
from django.core.urlresolvers import reverse
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q, Count
from django.contrib.auth.decorators import login_required, permission_required
from django.utils.translation import ugettext as _
from django.shortcuts import get_object_or_404
from django.views.static import serve as serve_static
from django.views.decorators.cache import cache_control, never_cache
from django.utils.encoding import smart_str
from django.contrib.markup.templatetags.markup import markdown
from django.contrib.sites.models import Site
from django.contrib.flatpages.models import FlatPage

from common.utils import add_message
from rdutils.render import render_view, paginate, render_to_string
from rdutils.email import email_template
from rdutils.query import get_or_none
from rdutils.cache import key_suffix, short_key, clear_keys, cache, shorten_key
from rdutils.url import sanitize_url
from extensions import formwizard as wizard
from messages import forms as messageforms
from artist.decorators import artist_account_required
from queue.models import ActionItem
from payment.processor import paypal, google
from registration.models import UserProfile
from twitter.utils import post_to_twitter
from event.templatetags import eventtags
from event.exceptions import EventError
from artist.models import ArtistProfile
from linker.models import WebLink
from event.models import Event, Badge, Attendee, today_timedelta_by_location
from event import forms
from event.utils import get_friends_favorites_count


_log = logging.getLogger('event.views')

_SUBDOMAIN_PORT = getattr(settings, 'SUBDOMAIN_PORT', '')
if _SUBDOMAIN_PORT:
    _SUBDOMAIN_PORT = u":" + _SUBDOMAIN_PORT


@login_required
@transaction.commit_on_success
def edit(request, event_id=None, step=None, location=None, template='event/event_edit_form.html'):
    user_profile = request.user_profile
    max_steps = 3
    ctx = {}
    approved_event_edit = False
    if not event_id and not step:
        step = 1
    steps = None
    if step:
        step = int(step)
        steps = [step]
        next_step = step + 1
    FormClass = forms.get_event_form(request, steps, location)
    if event_id is not None:
        # We are in update mode. Get the event instance if it belongs to 
        # this user.
        event = get_object_or_404(Event.visible_objects,
            Q(artist__user_profile__user=request.user) | Q(creator__user=request.user),
            pk=event_id) #is_submitted=False
        mode = 'update'
        ctx['event'] = event
        if event.is_approved:
            # Approved events no longer use a different form to track changes
            # FormClass = forms.get_event_edit_form(event, request, steps)
            approved_event_edit = True
    else:
        event = None
        mode = 'add'
    if request.method == 'POST':
        form = FormClass(data=request.POST, files=request.FILES, instance=event)
        if form.is_valid():
            if approved_event_edit:
                event_change = form.save(commit=True)
                if not event_change.is_approved:
                    # ActionItem.objects.q_admin_action(event, 'approve-event-edit')
                    email_template('Event Edited: approval requested by %s' % request.user.username,
                               'event/email/request_approval_edit.txt',
                               {'event':event}, to_list=settings.EVENT_APPROVERS, fail_silently=False)
                    request.user.message_set.create(message=_("This is what your updated event page will look like once an admin approves your changes."))
                else:
                    request.user.message_set.create(message=_('The event has been updated.'))
            else:
                event = form.save(commit=True)
                submit_for_approval(event, request.user, auto_approve=True)
                if event.is_member_generated and not event.attendee_set.count():
                    # Make the event creating member an automatic attendee
                    event.attendee_set.create(attendee_profile=user_profile, qty=1, added_on=datetime.now())
                request.user.message_set.create(message=_('The event has been updated.'))
            if event_id is None:
                _log.info('Event created: (%s) %s', event.pk, event.short_title)
            else:
                _log.info('Event updated: (%s) %s', event.pk, event.short_title)
            if step and next_step <= max_steps:
                return HttpResponseRedirect(reverse("edit_event_step", kwargs={'event_id':event.pk, 'step':next_step}))
            return HttpResponseRedirect(event.get_absolute_url())
    else:
        form = FormClass(instance=event)
    allow_city_change = False # not event # allow city change if this event is being newly created
    if allow_city_change:
        city = form.location
        other_cities = sorted(settings.LOCATION_DATA.keys())
        other_cities.remove(city)
        ctx['allow_city_change'] = True
        ctx['city'] = settings.LOCATION_DATA[city][3]
        ctx['other_cities'] = [(loc, settings.LOCATION_DATA[loc][3]) for loc in other_cities]
        request.location = city
        request.location_name = ctx['city']
    ctx.update({'form':form, 'mode':mode, 'step':step, 'event':event})
    return render_view(request, template, ctx)


@artist_account_required
def list_attendees_report(request, event_id, template='event/attendees_report.html'):
    ctx = {}
    event = get_object_or_404(Event.visible_objects, pk=event_id, artist__user_profile__user=request.user, is_approved=True)
    attendees = event.attendee_set.select_related('attendee', 'attendee_profile__user').order_by("attendee__username")
    if request.REQUEST.get('format', 'html') == 'csv':
        content_type = "text/csv; charset=%s" % settings.DEFAULT_CHARSET
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=event_%s_attendees.csv' % event.pk
        writer = csv.writer(response)
        r = writer.writerow
        r(['Event attendees'])
        r(['Event #%s' % event.pk, smart_str(event.title)])
        headers = ['User', 'First name', 'Last name', 'Qty', 'Registered on']
        r(headers)
        for c in attendees:
            u = c.attendee
            row = [u.username, u.first_name, u.last_name, c.qty, c.added_on]
            r(row)
        return response
    else:
        page = paginate(request, attendees, 100) # Show 100 attendees per page.
        ctx.update({'event':event, 'page':page})
        return render_view(request, template, ctx)


def list_attendees(request, event_id, template='event/attendees.html'):
    ctx = {}
    event = get_object_or_404(Event.visible_objects, pk=event_id)
    attendees = UserProfile.objects.select_related('user').filter(user__attendee__event__pk=event.pk).order_by("user__username")
    page = paginate(request, attendees, 100) # Show 100 attendees per page.
    ctx.update({'event':event, 'page':page})
    return render_view(request, template, ctx)


@artist_account_required
@transaction.commit_on_success
def message_attendees(request, event_id, form_class=messageforms.ComposeForm, template_name='messages/compose.html', success_url=None):
    """Send a message to all attendees of the given event."""
    event = get_object_or_404(Event.visible_objects, pk=event_id, artist__user_profile__user=request.user, is_approved=True)
    form = form_class()
    if request.method == "POST":
        form = form_class(request.POST)
        if form.is_valid():
            form.save(sender=request.user)
            request.user.message_set.create(
                message=_(u"Message successfully sent."))
            if success_url is None:
                success_url = reverse('view_event', kwargs={'event_id':event.pk})
            return HttpResponseRedirect(success_url)
    else:
        form = form_class()
        attendees = event.attendee_set.all().order_by("attendee__username")
        recipients = [c.attendee for c in attendees]
        form.fields['recipient'].initial = recipients
    return render_view(request, template_name, {'form':form})


@artist_account_required
def list_artist_events(request, category):
    """Show event summaries of logged in artist under the given category.

    Supported `category` values:
        unsubmitted
        pending-approval
        approved-upcoming
        active
        expired

    """
    # Sanity check
    if category not in ('unsubmitted', 'pending-approval', 'approved-upcoming', 'active', 'expired'):
        raise Http404
    artist = request.user.get_profile().artist
    category = category.replace('-', '_')
    # DRY: Call template tag for the given category.
    fn_name = 'events_%s' % category
    tag_fn = getattr(eventtags, fn_name)
    ctx = tag_fn(artist, limit=None)
    queryset = ctx.pop('events')
    ctx['is_owner'] = True
    # Reuse the `list_events` view.
    return list_events(request, queryset=queryset, extra_context=ctx)


def search_events(request, location=None):
    ctx = {'title':'Upcoming Events', 'searched':True, 'is_search':True, 'limit':None}
    ctx['rpp'] = int(request.REQUEST.get('rpp', 10))
    location = location or request.location
    request.location = location # stick user to this location going forward
    request.location_name = settings.LOCATION_DATA.get(location, settings.EMPTY_LOCATION_DATA)[3]
    today, td = today_timedelta_by_location(location)
    qx = Event.objects.active(attending_user=request.user_profile, today=today).order_by('event_date', 'event_start_time', 'pk')
    loc = request.REQUEST.get("location", None)
    any_loc = loc == 'any'
    if not any_loc:
        # qx = qx.exclude(ext_event_source='mlb2010', location='user-entered')
        qx = qx.exclude(location='user-entered') # don't show user entered events on city pages
    f = request.GET.get('filter', '').lower()
    sort_by = request.GET.get('sort', '').lower()
    by_date = request.GET.get('date', None)
    choices = request.GET.getlist('choices')    
    if 'free' in choices:
        qx = qx.filter(is_free=True)
    if 'checkins' in sort_by:
        # Checkins must automatically limit the view to today
        f = 'today'
    if f:
        if not request.user_profile and f in  ('favorites', 'my-calendar', 'recommended'):
            add_message(request, "You will need to sign in first.")
            return HttpResponseRedirect(u"%s?next=%s" % (reverse("signin"), request.get_full_path()))
        ctx['filter'] = f
        if f in ('favorites', 'my-calendar') and request.user_profile:
            ctx['title'] = "I'm In For:"
            qx = qx.filter(
               attendee__attendee_profile=request.user_profile
            ).distinct().order_by('event_date', 'event_start_time', 'pk')
            if settings.CALENDAR_FILTER_BY_LOCATION:
                qx = qx.filter(location__in=('destination', 'user-entered', location))
        elif f == 'recommended' and request.user_profile:
            ctx['title'] = "Friends' Events"
            qx = qx.filter(
               recommendedevent__user_profile=request.user_profile
            ).distinct().order_by('event_date', 'event_start_time', 'pk')
            if settings.RECOMMENDED_EVENTS_FILTER_BY_LOCATION:
                qx = qx.filter(location__in=('destination', 'user-entered', location))            
        elif f == 'most-popular':
            ctx['title'] = 'Most Popular Events'
            qx = qx.filter(location=location).order_by('-tweet_count', 'event_date', 'event_start_time', 'pk')
        elif f == 'our-picks':
            ctx['title'] = 'Our Picks'
            qx = qx.filter(location=location).filter(is_homepage_worthy=True).order_by('event_date', 'event_start_time', 'pk')
        elif f == 'destination':
            ctx['title'] = 'Destination Events'
            qx = qx.filter(location='destination').order_by('-destination_timestamp', 'event_date', 'event_start_time', 'pk')
        elif f == 'today':
            ctx['title'] = "Today's Events"
            qx = qx.filter(location=location).filter(
                event_date=today
            ).order_by('event_date', 'event_start_time', 'pk')
        elif f == 'date':
            # if date not specified, use today
            dt = by_date and datetime.strptime(by_date, "%m/%d/%Y") or date.today()
            ctx['title'] = "Events on %s" % dt.strftime("%A, %b %d, %Y")
            qx = qx.filter(location=location).filter(
                event_date=dt
            ).order_by('event_date', 'event_start_time', 'pk')
        elif f == 'tomorrow':
            ctx['title'] = "Tomorrow's Events"
            qx = qx.filter(location=location).filter(
                event_date=today + timedelta(days=1)
            ).order_by('event_date', 'event_start_time', 'pk')
        elif f == 'this-week':
            ctx['title'] = "This Week"
            start = today + relativedelta(weekday=MO(-1)) # greater than or equal to last Monday
            end = start + relativedelta(weekday=SU(+1)) # less than or equal to this Sunday
            qx = qx.filter(location=location).filter(
                event_date__gte=start,
                event_date__lte=end
            ).order_by('event_date', 'event_start_time', 'pk')
            ctx['start'] = start
            ctx['end'] = end
        elif f == 'this-weekend':
            ctx['title'] = "This Weekend"
            start = today + relativedelta(weekday=MO(-1)) + relativedelta(weekday=FR) # greater than or equal to this Friday
            end = start + relativedelta(weekday=SU(+1)) # less than or equal to this Sunday
            qx = qx.filter(location=location).filter(
                event_date__gte=start,
                event_date__lte=end
            ).order_by('event_date', 'event_start_time', 'pk')
            ctx['start'] = start
            ctx['end'] = end
        elif f == 'next-week':
            ctx['title'] = "Next Week"
            start = today + relativedelta(weekday=MO(-1), weeks=1) # greater than or equal to next Monday
            end = start + relativedelta(weekday=SU(+1)) # less than or equal to next Sunday
            qx = qx.filter(location=location).filter(
                event_date__gte=start,
                event_date__lte=end
            ).order_by('event_date', 'event_start_time', 'pk')
            ctx['start'] = start
            ctx['end'] = end
        elif f == 'next-weekend':
            ctx['title'] = "Next Weekend"
            start = today + relativedelta(weekday=MO(-1), weeks=1) + relativedelta(weekday=FR) # greater than or equal to next Friday
            end = start + relativedelta(weekday=SU(+1)) # less than or equal to next Sunday
            qx = qx.filter(location=location).filter(
                event_date__gte=start,
                event_date__lte=end
            ).order_by('event_date', 'event_start_time', 'pk')
            ctx['start'] = start
            ctx['end'] = end
    else: # no filter
        if not any_loc:
            qx = qx.filter(location__in=('destination', 'user-entered', location))
    q = request.GET.get('q', '')
    if q:
        if not f:
            ctx['title'] = 'Events matching "%s"' % q
        ctx['q'] = q
        qx = qx.filter(
            Q(title__icontains=q) | 
            Q(description__icontains=q) |
            Q(venue__name__icontains=q) |
            Q(hashtag__icontains=q)
        )
        if 'sxsw' in q.lower():
            if not request.mobile:
                ctx['rpp'] = 100
            ctx['limit'] = 30 # start with events starting in 30 minutes or more
        if request.GET.get('page', '1') == '1':
            prefix = request.mobile and '/mobile/search' or '/help/search'
            qflat = q.replace('#', '').replace('@', '').lower()
            for k,v in settings.EVENT_SEARCH_NORMALIZATION.iteritems():
                qflat = qflat.replace(k, v)
            try:
                flaturl = u"%s/%s/" % (prefix, qflat.replace(' ', '-'))
                fp = Site.objects.get_current().flatpage_set.get(url=flaturl.lower())
                ctx['flatcontent'] = markdown(fp.content)
            except FlatPage.DoesNotExist:
                # if this search phrase has multiple space-separated keywords, 
                # look for a flatpage for just the first word.
                if ' ' in qflat:
                    x = qflat.split(' ')
                    if x[0]:
                        try:
                            flaturl = u"%s/%s/" % (prefix, x[0])
                            fp = Site.objects.get_current().flatpage_set.get(url=flaturl.lower())
                            ctx['flatcontent'] = markdown(fp.content)
                        except FlatPage.DoesNotExist:
                            pass
    if sort_by and 'checkins' in sort_by:
        ctx['limit'] = 30
    limit = request.GET.get('limit', ctx.get('limit', None))
    if limit:
        minutes = int(limit)
        now = td and (datetime.now() - td) or datetime.now()
        threshold = now - timedelta(minutes=minutes)
        time_threshold = threshold.time()
        _log.debug("Excluding %s events started before %s (limit = %s minutes, td = %s)", today, time_threshold, limit, td)
        qx = qx.exclude(
            # event_start_time__isnull=False, # has start time
            event_date=today, # happened today
            event_start_time__lt=time_threshold # already happened
        )
    if sort_by and sort_by in ('date', 'tweets', 'interested', 'new', 'checkins', 'mf_checkins', 'fm_checkins'):
        if 'checkins' in sort_by:
            # only include events that have no start time or that have already started or that are starting in the next 1 hour
            now = td and (datetime.now() - td) or datetime.now()
            threshold = now + timedelta(minutes=settings.CHECKIN_THRESHOLD_MINUTES) # 80 mins from now
            time_threshold = threshold.time()
            qx = qx.filter(
                Q(event_start_time__isnull=True) |
                Q(event_start_time__lte=time_threshold)
            )
        if sort_by == 'date':
            qx = qx.order_by('event_date', 'event_start_time', 'pk')
        elif sort_by == 'tweets':
            qx = qx.order_by('-tweet_count', 'event_date', 'event_start_time', 'pk')
        elif sort_by == 'interested':
            qx = qx.order_by('-stats__num_attendees', 'event_date', 'event_start_time', 'pk')
        elif sort_by == 'new':
            qx = qx.order_by('-pk', 'event_date', 'event_start_time')
        elif sort_by == 'checkins':
            qx = qx.order_by('-venue__fsq_checkins', 'event_date', 'event_start_time', 'pk')
            ctx['title'] = "Checkins Today"
        elif request.user.is_authenticated():
            if sort_by == 'mf_checkins': # where the ladies are          
                qx = qx.filter(venue__fsq_checkins__gt=0, venue__fsq_f__gt=1).order_by('venue__fsq_mf', 'event_date', 'event_start_time', 'pk')
                ctx['title'] = "Checkins Today"
            elif sort_by == 'fm_checkins': # where the gents are
                qx = qx.filter(venue__fsq_checkins__gt=0, venue__fsq_m__gt=1).order_by('venue__fsq_fm', 'event_date', 'event_start_time', 'pk')
                ctx['title'] = "Checkins Today"
        ctx['sort_by'] = sort_by
    return list_events(request, location, queryset=qx, extra_context=ctx, hide_top3=True)


def list_events(request, location=None, template='event/list.html', queryset=None, extra_context=None, hide_top3=False):
    location = location or request.location
    request.location = location # stick user to this location going forward
    request.location_name = settings.LOCATION_DATA.get(location, settings.EMPTY_LOCATION_DATA)[3]
    if queryset is None:
        today, td = today_timedelta_by_location(location)
        queryset = Event.objects.active_by_location(location=location, attending_user=request.user_profile, today=today).order_by('event_date', 'event_start_time', 'pk')
        # queryset = queryset.exclude(ext_event_source='mlb2010', location='user-entered')
        queryset = queryset.exclude(location='user-entered') # don't show user entered events on city pages
    ctx = {
        'title':'Upcoming Events',
        'events':queryset,
        'location_name':Event.LOCATIONMAP.get(location, 'Boston, MA'),
    }
    if not hide_top3:
        userid = request.user.is_authenticated() and request.user.pk or 0
        key = shorten_key(u"popular-ourpick-destination:%s:%s" % (location, userid))
        px = cache.cache.get(key, None)
        if px is None:
            popular = Event.objects.active_by_location(
                location=location,
                attending_user=request.user_profile,
                event_date__lte=datetime.today() + timedelta(days=7),
            ).order_by('-tweet_count')[:1]
            ctx['popular'] = get_or_none(popular)
            ctx['ourpick'] = get_or_none(Event.objects.active_by_location(location=location, attending_user=request.user_profile, is_homepage_worthy=True).order_by('event_date', 'event_start_time', 'pk')[:1])
            ctx['destination'] = get_or_none(Event.objects.active_by_location(location='destination', attending_user=request.user_profile).order_by('-destination_timestamp')[:1])
            px = (ctx['popular'], ctx['ourpick'], ctx['destination'])
            cache.cache.set(key, px, 600)
        else:
            ctx['popular'], ctx['ourpick'], ctx['destination'] = px
    if extra_context:
        ctx.update(extra_context)
    other_cities = sorted(settings.LOCATION_DATA.keys())
    other_cities.remove(location)
    city_list_html = [
        ('<a href="http://%s.%s%s%s">%s</a>' % (settings.LOCATION_SUBDOMAIN_REVERSE_MAP[loc], settings.DISPLAY_SITE_DOMAIN,  _SUBDOMAIN_PORT, reverse("list_events"), settings.LOCATION_DATA.get(loc)[3])) for loc in other_cities
    ]
    ctx['other_cities'] = ', '.join(city_list_html)
    if request.mobile:
        template = 'mobile/event/city.html'
    if request.user.is_authenticated():
        # Get Friends' Favorites count
        ctx['num_ff'] = get_friends_favorites_count(request.user_profile, location)
    ctx['needs_fbml'] = True
    return render_view(request, template, ctx)


@login_required
@transaction.commit_on_success
def post_comment(request, event_id, template='event/comment_form.html'):
    event = get_object_or_404(Event.objects.public(), pk=event_id)
    if request.method == 'POST':
        form = forms.EventCommentForm(author=request.user, target_instance=event, data=request.POST)
        if form.is_valid():
            comment = form.save()
            request.user.message_set.create(message=_('Thank you for your <a href="#c%s">comment&nbsp;&raquo;</a>' % comment.pk))
            _log.debug('Event comment posted: (%s)', comment.get_as_text())
            cache_killer = "%s-%s"% (random.randint(0, 10000), time())
            return HttpResponseRedirect(event.get_absolute_url() + "?q=%s" % cache_killer)
    else:
        form = forms.EventCommentForm(author=request.user, target_instance=event)
    ctx = {'form':form, 'comment_form':form, 'event':event}
    return render_view(request, template, ctx)


def submit_for_approval(event, user, auto_approve=False):
    """Helper method to submit an event for admin approval."""
    event.is_submitted = True
    if auto_approve:
        event.is_approved = True
        subject = 'Event auto-approved for %s' % user.username
    else:
        subject = 'Event approval requested by %s' % user.username
    event.save()
    if not auto_approve:
        # ActionItem.objects.q_admin_action(event, 'approve-event')
        email_template(subject,
                       'event/email/request_approval.txt',
                       {'event':event}, to_list=settings.EVENT_APPROVERS, fail_silently=False)


@artist_account_required
@transaction.commit_on_success
def request_approval(request, event_id):
    if request.method == 'POST':
        event = get_object_or_404(Event.visible_objects, pk=event_id, artist__user_profile__user=request.user)
        if not event.is_submitted:
            submit_for_approval(event, request.user)
            request.user.message_set.create(message=_('Your event has just been submitted for approval. An admin will review it shortly.'))
            _log.info('Event approval requested: (%s) %s', event.pk, event.short_title)
        else:
            request.user.message_set.create(message=_('This event has already been submitted for approval. Please send an e-mail to %s if you have questions.' % settings.EVENT_APPROVERS[0][1]))
        return HttpResponseRedirect(reverse('view_event', kwargs={'event_id':event_id}))
    else:
        raise Http404


@login_required
@transaction.commit_on_success
def delete(request, event_id, template='event/event_deletion_form.html'):
    event = get_object_or_404(Event.visible_objects,
            Q(artist__user_profile__user=request.user) |
            Q(creator__user=request.user),
            pk=event_id) #is_submitted=False
    ctx = {'event':event, 'c':event}
    if request.method == 'POST':
        form = forms.DeleteEventForm(data=request.POST)
        if form.is_valid():
            if event.is_deletable:
                event.delete()
                request.user.message_set.create(message=_('Your event has been deleted.'))
                return HttpResponseRedirect(reverse('artist_admin'))
            else:
                # ActionItem.objects.q_admin_action(event, 'delete-event')
                request.user.message_set.create(message=_('Your event deletion request has been submitted. An admin will review it shortly.'))
                email_template('Event deletion requested by %s' % request.user.username,
                               'event/email/request_deletion.txt',
                               {'event':event}, to_list=settings.EVENT_APPROVERS)
                _log.info('Event deletion requested: (%s) %s', event.pk, event.short_title)
            return HttpResponseRedirect(reverse('view_event', kwargs={'event_id':event_id}))
    else:
        form = forms.DeleteEventForm()
    ctx['form'] = form
    return render_view(request, template, ctx)


@transaction.commit_on_success
def buy_tickets(request, event_id):
    from common.templatetags.commontags import referer_url
    event = get_object_or_404(Event.visible_objects.all(), pk=event_id)
    if not event.is_active:
        # can't buy tix for past events
        add_message(request, u"This event has expired.")
        return HttpResponseRedirect(event.get_absolute_url())
    if not event.ticket_or_tm_url:
        # event doesn't have a ticket URL
        add_message(request, u"Sorry. This event doesn't have a ticket purchase link.")
        return HttpResponseRedirect(event.get_absolute_url())
    redirect_to = sanitize_url(referer_url(event.ticket_or_tm_url))
    # record this URL redirection
    src_email = 'email' == request.REQUEST.get('src', 'web').lower()
    if src_email:
        n_web, n_email = 0, 1
    else:
        n_web, n_email = 1, 0
    lnk, created = WebLink.objects.get_or_create(
        url=u"buy-tix-%s" % event.pk,
        defaults=dict(redirect_to=redirect_to, category='Buy Tickets'),
    )
    lnk.redirect_to = redirect_to
    lnk.category = u'Buy Tickets'
    lnk.email_count += n_email
    lnk.web_count += n_web
    lnk.save()
    return HttpResponseRedirect(lnk.redirect_to)


@transaction.commit_on_success
def vcal(request, event_id):
    event = get_object_or_404(Event.visible_objects.all(), pk=event_id)
    if not event.uuid:
        event.uuid = uuid4().hex
        super(Event, event).save()
    cal = vobject.iCalendar()
    cal.add('method').value = 'PUBLISH'  # IE/Outlook needs this
    vevent = cal.add('vevent')
    vevent.add('uid').value = event.uuid
    vevent.add('summary').value = event.title # smart_str(event.title, errors='replace')
    surl = event.get_short_url()
    desc = u'More details at RiotVine: %s' % surl
    if event.venue.map_url:
        desc = desc + u'\r\n\r\nLocation Map: %s\r\n' % event.venue.map_url
    vevent.add('URL;VALUE=URI').value=surl # iCal can use this
    vevent.add('description').value = desc # smart_str(desc, errors='ignore')
    location = event.venue.name + u' - ' + event.venue.address +u' - ' + event.venue.citystatezip
    vevent.add('location').value = location # smart_str(location, errors='ignore')
    dtstart = vevent.add('dtstart')
    d, t = event.event_date, event.event_start_time
    if event.has_start_time:
        start = datetime(d.year, d.month, d.day, t.hour, t.minute)
    else:
        start = datetime(d.year, d.month, d.day)
    dtstart.value = start
    vevent.add('dtend').value = start # Outlook needs this
    vevent.add('dtstamp').value = datetime.now() # Outlook needs this
    icalstream = cal.serialize()
    response = HttpResponse(icalstream, mimetype='text/calendar')
    response['Filename'] = 'riotvine_event.ics'  # IE needs this
    response['Content-Disposition'] = 'attachment; filename=riotvine_event.ics'
    return response


def view_shared_event(request, event_id, sharer_id):
    """Store sharer profile into session and redirect user to the event."""
    event = get_object_or_404(Event.visible_objects.select_related('creator__user', 'artist__user_profile__user', 'venue'), pk=event_id)
    request.session['sharer_profile_%s' % event_id] = sharer_id
    return HttpResponseRedirect(event.get_absolute_url())

def view_seo(request, artist_url, event_url):
    event_url = event_url.lower()
    event = get_object_or_404(Event.visible_objects.select_related('creator__user', 'artist__user_profile__user', 'venue'), url=event_url, artist__url=artist_url)
    return view(request, event.pk, event)


def view(request, event_id, event=None, template='event/detail.html'):
    """Event detail view"""
    from event.templatetags.eventtags import gcal_url
    ctx = {}
    if not event:
        event = get_object_or_404(Event.visible_objects.select_related('creator__user', 'artist__user_profile__user', 'venue'), pk=event_id)
    sharer_id = request.session.get("sharer_profile_%s" % event.pk, None)
    if sharer_id:
        if settings.DEV_MODE or not request.user.is_authenticated() or (int(request.user.pk) != int(sharer_id)):
            sharer_profile = get_object_or_404(UserProfile.objects.active(), user__pk=sharer_id)
            ctx['sharer_profile'] = sharer_profile
    if event.location not in ('destination', 'user-entered'):
        location = event.location
        request.location = location # stick user to this location going forward
        request.location_name = settings.LOCATION_DATA.get(location, settings.EMPTY_LOCATION_DATA)[3]
        ctx['event_location_name'] = request.location_name
    ctx['is_owner'] = request.user.is_authenticated() and \
        ((event.creator and request.user.id == event.creator.user.id) or \
        (request.user.id == event.artist.user_profile.user.id))
    ctx['is_admin'] = request.user.has_perm('event.can_manage_events')
    # Event changes, if available, are shown only to the event owner and the admin.
    ctx['changes'] = False # (ctx['is_owner'] or ctx['is_admin']) and event.changed_version
    if not event.is_approved:
        # Only admins and event owners may see unapproved events.
        if not request.user.is_authenticated():
            return HttpResponseRedirect("%s?next=%s" % (reverse('login'), request.path))
        if not (ctx['is_owner'] or ctx['is_admin']):
            # We could return an HTTP forbidden response here but we don't want a malicious user
            # to know if a event even exists with this id.
            # So, we raise a 404 - Page Not Found instead.
            raise Http404
    if request.user.is_authenticated():
        event.is_attending = event.attendee_set.filter(attendee_profile=request.user_profile).count()
        share_url = event.get_short_url_for_sharer(request.user.pk)
        full_share_url = event.get_full_url_for_sharer(request.user.pk)
    else:
        share_url = event.get_short_url()
        full_share_url = event.get_absolute_url()
    ctx['full_share_url'] = full_share_url
    ctx['share_url'] = share_url
    ctx['share_url_or_none'] = len(share_url) < 25 and share_url or None
    ctx['e'] = event
    ctx['event'] = event
    if request.user.is_authenticated():
        ctx['comment_form'] = forms.EventCommentForm(author=request.user, target_instance=event)
    ctx['twitter_label'] = u'Tweet this show'
    ctx['twitter_status'] = settings.TWITTER_EVENT_STATUS_FORMAT % {'event_name':event.short_name_for_twitter, 'event_url':event.get_short_url()}
    ctx['interested_count'] = event.interested_count
    ctx['gcal_url'] = gcal_url(event)
    stats = event.stats
    if not ctx['is_owner']:
        stats.num_views = stats.num_views + 1
        stats.save()
    else:
        # set context if this is the event owner's first visit to this page
        stats.num_owner_views = stats.num_owner_views + 1
        stats.save()
    ctx['stats'] = stats
    ctx['is_owner_first_visit'] = (ctx['is_owner'] and stats.num_owner_views == 1)  # or settings.DEV_MODE
    ctx['needs_fbml'] = True
    ctx['interested'] = event.get_interested()
    return render_view(request, template, ctx)


@cache_control(must_revalidate=True, max_age=300)
def dynamic_badge(request, event_id, event=None, template='event/dynamic_badge.html'):
    """Event badge"""
    ctx = {}
    if not event:
        event = get_object_or_404(Event.visible_objects.select_related('creator__user', 'artist__user_profile__user', 'venue'), pk=event_id)
    ctx['e'] = event
    ctx['event'] = event
    return render_view(request, template, ctx)


@never_cache
def comments(request, event_id, template='event/tags/event_comments.html'):
    """Event comments AJAX view"""
    from event.templatetags.eventtags import event_comments as fill_event_comments
    event = get_object_or_404(Event.visible_objects, pk=event_id)
    ctx = {}
    fill_event_comments(ctx, event)
    ctx['is_owner'] = request.user.is_authenticated() and \
        (request.user.id == event.artist.user_profile.user.id) or \
        (event.creator and request.user.id == event.creator.user.id)
    ctx['is_admin'] = request.user.has_perm('event.can_manage_events')
    ctx['c'] = event
    ctx['event'] = event
    if request.user.is_authenticated():
        ctx['comment_form'] = forms.EventCommentForm(author=request.user, target_instance=event)
    ctx['twitter_label'] = u'Tweet this show'
    ctx['twitter_status'] = settings.TWITTER_EVENT_STATUS_FORMAT % {'event_name':event.short_name_for_twitter, 'event_url':event.get_short_url()}
    return render_view(request, template, ctx)


@cache_control(must_revalidate=True, max_age=120) #@never_cache #
def serve_badge(request, event_id, badge_type='i'):
    if badge_type == 'e':
        objects = Badge.objects.filter(event__is_approved=True)
    else:
        objects = Badge.objects
    badge = get_object_or_404(objects, event=event_id, event__is_deleted=False, badge_type=badge_type)
    #response = serve_static(request, path=badge.image.path.replace('\\', '/'), document_root='/')
    response = serve_static(request, path=badge.image.name, document_root=settings.MEDIA_ROOT)
    return response


@login_required
@transaction.commit_on_success
def attend(request, event_id, template='event/event_registration_form.html'):
    """Process event registration."""
    event = get_object_or_404(Event.objects.active(), pk=event_id)
    if event.attendee_set.filter(attendee=request.user).count():
        request.user.message_set.create(message=_('You have already added this show to your list.'))
        return HttpResponseRedirect(reverse('view_event', kwargs={'event_id':event.pk}))
    try:
        qualifies, reasons = event.is_user_qualified(request.user)
        user_profile=request.user.get_profile()
        data = None
        if qualifies and request.user.first_name and request.user.last_name:
            # Skip the form and directly register this event attendee.
            data = {'first_name':request.user.first_name, 
                    'last_name':request.user.last_name,
                    'birth_date':user_profile.birth_date,
                    'post_to_tweeter':request.REQUEST.get('post_to_tweeter', False)}
        if data or request.method == 'POST':
            if request.method == 'POST':
                data = request.POST
            form = forms.DirectAttendeeForm(data=data, event=event, user_profile=user_profile)
            if form.is_valid():
                attendee = form.save(commit=True)
                if not attendee:
                    return HttpResponseRedirect(reverse('view_event', kwargs={'event_id':event.pk}))
                if form.cleaned_data.get('post_to_tweeter', False):
                    # Post to Twitter
                    status = settings.TWITTER_EVENT_STATUS_FORMAT % {'event_name':event.short_name_for_twitter, 'event_url':event.get_short_url()}
                    post_to_twitter(request.user, status)
                _log.info('Attendee processed %s', attendee)
                if attendee.qty > 1:
                    request.user.message_set.create(message=_('This show has been added to your list.'))
                else:
                    request.user.message_set.create(message=_('This show has been added to your list.'))
                return HttpResponseRedirect(reverse('view_event', kwargs={'event_id':event_id}))
        else:
            form = forms.DirectAttendeeForm(event=event, user_profile=user_profile)
        ctx = {'event':event, 'c':event, 'form':form}
    except EventError, e:
        request.user.message_set.create(message=e.message)
        return HttpResponseRedirect(reverse('view_event', kwargs={'event_id':event.pk}))
    return render_view(request, template, ctx)


@login_required
@transaction.commit_on_success
def add_to_calendar(request, event_id, remove=False, force=False):
    """Add user to event attendees (or remove them)"""
    try:
        user_profile=request.user_profile
        event = get_object_or_404(Event.objects.active(), pk=event_id)
        retval = {'success':True, 'do_remove':False}
        is_ajax = request.is_ajax()
        if force or (is_ajax and request.method == 'POST') or request.method == 'GET':
            clear_keys('attendees', event.pk)
            attending = event.attendee_set.filter(attendee_profile=user_profile).all()
            for a in attending:
                ActionItem.objects.q_attendee_action_done(a, 'event-faved')
            if remove:                
                attending.delete()
                retval['message'] = is_ajax and _(u'done!') or _(u'Event removed from your favorites')
                retval['do_remove'] = True
                retval['link_type'] = 'add'
                retval['old_link'] = reverse("event_remove_from_calendar", kwargs={"event_id":event.pk})
                retval['reverse_link'] = reverse("event_add_to_calendar", kwargs={"event_id":event.pk})
            else:
                if attending.count():
                    retval['message'] = is_ajax and _(u'done!') or _(u'Event added to your favorites')
                else:
                    attendee = event.attendee_set.create(attendee_profile=user_profile)
                    retval['message'] = is_ajax and _(u'done!') or _(u'Event added to your favorites')
                retval['link_type'] = 'remove'
                retval['old_link'] = reverse("event_add_to_calendar", kwargs={"event_id":event.pk})
                retval['reverse_link'] = reverse("event_remove_from_calendar", kwargs={"event_id":event.pk})
            if is_ajax:
                return HttpResponse(json.dumps(retval), mimetype='application/json')
            if retval.get('message', None):
                request.user.message_set.create(message=retval['message'])
            next = request.REQUEST.get('next', event.get_absolute_url())
            return HttpResponseRedirect(next)
        return HttpResponseNotAllowed(permitted_methods=['POST', 'GET'])
    except Exception, e:
        _log.exception(e)
        raise


@cache_control(must_revalidate=True, max_age=1)
def calendar(request, limit=10, template='event/tags/event_calendar.html'):
    """Render event calendar for the logged in user"""
    from event.templatetags.eventtags import gcal_url
    try:
        ctx = {}
        if not request.user.is_authenticated:
            if request.is_ajax():
                raise Http404
            return HttpResponseRedirect("%s?next=%s" % (reverse("login"), reverse("list_events")))
        ctx['next'] = request.META.get('HTTP_REFERER', reverse("list_events"))
        event_id = request.REQUEST.get("event_id", "");
        # If there's an event_id, we are on the event detail page
        event = event_id and get_or_none(Event.objects.active(), pk=event_id) or None
        events = Event.objects.active().filter(
            attendee__attendee_profile=request.user_profile
        ).distinct().order_by('event_date', 'event_start_time', 'pk')
        if settings.CALENDAR_FILTER_BY_LOCATION:
            events = events.filter(location__in=('destination', 'user-entered', request.location))
        ctx['calendar_count'] = events.count()
        if limit:
            events = events[:int(limit)]
        ctx['events'] = events
        if event:
            ctx['next'] = event.get_absolute_url()
            ctx['event'] = event
            ctx['gcal_url'] = gcal_url(event)
            if request.user_profile and request.user_profile.attendee_set.filter(event=event).count():
                ctx['show_remove_event'] =  True
            else:
                ctx['show_add_event'] =  True
            ctx['is_owner'] = request.user.is_authenticated() and \
                                        ((event.creator and request.user.id == event.creator.user.id) or \
                                        (request.user.id == event.artist.user_profile.user.id))
            ctx['is_admin'] = request.user.has_perm('event.can_manage_events')
        return render_view(request, template, ctx)
    except Exception, e:
        _log.exception(e)
        raise


@cache_control(must_revalidate=True, max_age=1)
def recommended_events(request, limit=10, template='event/tags/recommended_events.html'):
    """Render event calendar for the logged in user"""
    try:
        ctx = {}
        if not request.user.is_authenticated:
            if request.is_ajax():
                raise Http404
            return HttpResponseRedirect("%s?next=%s" % (reverse("login"), reverse("event_recommended")))
        events = Event.objects.active().filter(
            recommendedevent__user_profile=request.user_profile
        ).distinct().order_by('event_date', 'event_start_time', 'pk')
        if settings.RECOMMENDED_EVENTS_FILTER_BY_LOCATION:
            events = events.filter(location__in=('destination', request.location))
        n = events.count()
        if not n:
            # fallback to user-entered events
            events = events.filter(location__in=('user-entered', request.location))
            n = events.count()
        else:
            ctx['city'] = request.location_name
        ctx['recommended_count'] = n
        if limit:
            events = events[:int(limit)]
        ctx['events'] = events
        return render_view(request, template, ctx)
    except Exception, e:
        _log.exception(e)
        raise


@cache_control(must_revalidate=True, max_age=1)
def interested(request, event_id, limit=500, template='event/tags/who_is_interested.html'):
    """Render users interested in the given event.

    This view is pulled in through AJAX view.
    
    The view can also be called with `return_context` set to True. In that case, 
    it just returns the context dictionary which can be used by the caller to merge this data
    into another view.

    """    
    try:
        ctx = {}
        e = get_object_or_404(Event.objects.public(), pk=event_id)
        ctx['e'] = e
        ctx['event'] = e
        ctx['interested'] = e.get_interested(limit=limit)
        return render_view(request, template, ctx)
    except Exception, e:
        _log.exception(e)
        raise


@login_required
@transaction.commit_on_success
def qualify(request, event_id, template='event/event_qualification_form.html'):
    ticket_code = request.session.get('open_ticket_code', None)
    event = get_object_or_404(Event.objects.public(), pk=event_id)
    qualifies, reasons = event.is_user_qualified(request.user)
    if qualifies and ticket_code:
        return HttpResponseRedirect(reverse('redeem_ticket'))
    else:
        _log.debug("Qualification needed: %s", reasons)
    if request.POST:
        form = forms.QualificationForm(data=request.POST, event=event, user_profile=request.user.get_profile())
        if form.is_valid():
            user_profile = form.save(commit=True)
            request.user.message_set.create(message=_('Your profile has been updated.'))
            if ticket_code:
                return HttpResponseRedirect(reverse('redeem_ticket'))
            else:
                return HttpResponseRedirect(reverse('view_event', kwargs={'event_id':event_id}))
    else:
        form = forms.QualificationForm(event=event, user_profile=request.user.get_profile())
    ctx = {'event':event, 'c':event, 'form':form}
    return render_view(request, template, ctx)


def venue_search(request, template='event/venue_search.html'):
    results = []
    q = request.REQUEST.get('q', None)
    location = request.REQUEST.get('location', request.location)
    _log.debug("Venue search: %s, %s", location, q)
    try:
        if not q:
            return HttpResponseForbidden()
        _VENUE_SEARCH_URL = getattr(settings, 'GOOGLE_LOCAL_SEARCH_URL', 'http://ajax.googleapis.com/ajax/services/search/local?%s')
        loc = settings.LOCATION_DATA.get(location, '')
        if location in settings.LOCATION_DATA.keys():
            sll = u"%s,%s" % loc[:2]
        else:
            sll = settings.GOOGLE_LOCAL_CENTER
        params = urlencode(dict(
            q=q,
            v='1.0',
            mrt='localonly', # blended, kmlonly
            # start=0,
            sll=sll,
            rsz='large',
        ))
        url = _VENUE_SEARCH_URL % params
        _log.debug("Venue search: %s", url)
        req = urllib2.Request(url)
        req.add_header("Content-type", "application/x-www-form-urlencoded")
        req.add_header('User-Agent', settings.USER_AGENT)
        req.add_header('Referer', settings.GOOGLE_LOCAL_REFERER)
        resp = urllib2.urlopen(req)
        ret = resp.read()
        resp.close()
        j = json.loads(ret)
        if j['responseStatus'] == 200:
            results = j['responseData'].get('results', [])
    except Exception, e:
        _log.error(e)
    ctx = {'results':results[:8], 'q':q}
    return render_view(request, template, ctx)


