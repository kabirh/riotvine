from __future__ import absolute_import
import logging
import os.path
from datetime import date, datetime
from datetime import time as dt_time
from decimal import Decimal as D
from uuid import uuid4

from django import forms
from django.contrib.localflavor.us.forms import USZipCodeField
from django.db import models
from django.conf import settings
from django.utils import simplejson as json
from django.utils.translation import ugettext as _
from django.utils.encoding import force_unicode
from django.core.files.base import ContentFile
from django.utils.html import escape, strip_tags
from django.core.urlresolvers import reverse

from photo.utils import get_image_aspect, get_image_format
from rdutils.site import DISPLAY_SITE_URL
from rdutils.date import get_age
from rdutils.decorators import attribute_cache
from rdutils.text import sanitize_html, xss_vulnerable_html, get_tags_and_attributes, slugify
from common.forms import ValidatingModelForm, CommentForm
from queue.models import ActionItem
from registration.forms import UserProfileForm
from oembed import utils as oembed_utils
from oembed.models import ServiceProvider as OEmbedProvider
from twitter.utils import get_background_url
from event.utils import is_event_url_available, copy_background_image_from_url_to_event
from event.exceptions import SoldOutError, FanAlreadyJoinedError
from event.models import Event, EventChange, Attendee, Venue, EventTweet
from event.amqp.tasks import event_created
from artist.models import ArtistProfile


_log = logging.getLogger("event.forms")


EMBED_VALID_TAGS, EMBED_VALID_ATTRS = get_tags_and_attributes(settings.MP3_ALLOWED_EMBED_CODE)


class AdminEventForm(ValidatingModelForm):
    class Meta:
        model = Event

    def clean_is_approved(self):
        is_approved = self.cleaned_data.get('is_approved', False)
        if is_approved and self.instance.pk and not self.instance.is_submitted:
            raise forms.ValidationError(_(u"The artist hasn't yet submitted this event for approval."))
        return is_approved

    def clean_is_homepage_worthy(self):
        is_homepage_worthy = self.cleaned_data.get('is_homepage_worthy', False)
        if is_homepage_worthy and self.instance.pk and not self.instance.is_submitted:
            raise forms.ValidationError(_(u"The artist hasn't yet submitted this event for approval."))
        return is_homepage_worthy

    def clean(self):
        # if not self.instance.pk:
        #    raise forms.ValidationError(_(u"A new event can't be created from the Admin area. Please use the event creation area on the public site instead."))
        return self.cleaned_data


class DeleteEventForm(forms.Form):
    delete = forms.BooleanField(label=_("Yes, I am sure I want to delete this event."))
    delete.widget.attrs.update({'class':'checkboxInput'})

    def clean_delete(self):
        f = self.cleaned_data.get('delete')
        if not bool(f):
            raise forms.ValidationError(_(u'Please check this box to confirm that you want to delete this event.'))
        return f


class _AgeValidatorFormBase(object):
    def __init__(self, min_age):
        self.min_age = min_age

    def clean(self):
        birth_date = self.cleaned_data.get('birth_date', None)
        if birth_date:
            age = get_age(birth_date)
            if age < self.min_age:
                raise forms.ValidationError(_(u"We're sorry. Based on the information you have submitted to us, you are ineligible to participate in this event."))
        return self.cleaned_data


class QualificationForm(UserProfileForm, _AgeValidatorFormBase):
    """Collect user profile data required by an event."""
    def __init__(self, event, user_profile, *args, **kwargs):
        self.event = event
        self.user_profile = user_profile
        show_fields = ['name'] # Name is always required
        if event.min_age:
            show_fields.append('birth_date')
        UserProfileForm.__init__(self, instance=user_profile, show_fields=show_fields, optional_fields=[], *args, **kwargs)
        _AgeValidatorFormBase.__init__(self, int(self.event.min_age))

    def clean(self):
        return _AgeValidatorFormBase.clean(self)


class _AttendeeFormBase(QualificationForm):
    """Factor out common code."""
    
    def __init__(self, event, user_profile, *args, **kwargs):
        if event.is_sold_out:
            raise SoldOutError()
        QualificationForm.__init__(self, event, user_profile, *args, **kwargs)
        self.qty_shown = False
        num_left = event.num_left_for_user(user_profile.user)
        if event.max_attendees and num_left == 0:
            raise FanAlreadyJoinedError()

    @property
    @attribute_cache('qty')
    def qty(self):
        return 1


class DirectAttendeeForm(_AttendeeFormBase):
    """Collect user profile data required by an event."""

    post_to_tweeter = forms.BooleanField(label=u"Post to Twitter", required=False, initial=True)

    def __init__(self, event, user_profile, *args, **kwargs):
        _AttendeeFormBase.__init__(self, event, user_profile, *args, **kwargs)
        if user_profile.has_twitter_access_token:
            self.fields.keyOrder.remove('post_to_tweeter')
            self.fields.keyOrder.append('post_to_tweeter')
        else:
            del self.fields['post_to_tweeter']

    def save(self, commit=True):
        UserProfileForm.save(self, commit=commit)
        if self.event.attendee_set.filter(attendee_profile=self.user_profile).count():
            return None
        a = Attendee(event=self.event,
                     attendee_profile=self.user_profile,
                     qty=1,
                     added_on=datetime.now())
        a.already_registered = False
        if commit:
            a.save()
        return a


def get_event_form(request, steps=None, location=None):
    if request:
        user_profile = request.user_profile
        allowed_locations = [loc for loc, name in settings.LOCATIONS if loc != 'destination']
        if location and location not in allowed_locations:
            location = None # end users aren't allowed to create destination events
        location = location or 'user-entered' # request.location
    else:
        user_profile = None
    if user_profile and user_profile.is_artist:
        user_url = user_profile.artist.url
        artist = user_profile.artist
    else:
        artist = ArtistProfile.objects.get(url='riotvine-member')
        user_url = 'riotvine-member'
    if user_profile and user_profile.twitter_profile:
        bg_image_url, bg_tile = get_background_url(user_profile.twitter_profile.appuser_id)
    else:
        bg_image_url, bg_tile = None, True
    if not steps:
        steps = [1, 2, 3]

    class EventForm(forms.ModelForm):
        def __init__(self, *args, **kwargs):
            super(EventForm, self).__init__(*args, **kwargs)
            inst = self.instance
            self.location = inst.pk and inst.location or location
            if 1 in steps:
                self.fields['event_date'].widget.attrs.update({'class':'date_field'})
                self.fields['venue_name'] = forms.CharField(
                    label=_('Venue'),
                    max_length=255,
                    help_text=_(u"<span class='error'>Type in the venue name and click search. Include the city and state for best results.</span>")
                )
                self.fields['venue_source'] = forms.CharField(widget=forms.HiddenInput(), initial='user-entered')
                self.fields['venue_params'] = forms.CharField(widget=forms.HiddenInput(), required=False)
                if inst.pk:
                    vn = inst.venue
                    self.fields['venue_name'].initial = vn.state and u", ".join([vn.name, vn.state]) or vn.name
                    self.fields['venue_source'].initial = vn.source
                    self.fields['venue_params'].initial = vn.params
                else:
                    # invite by email option is only available on event creation and not on event update
                    self.fields['invite_by_email'] = forms.BooleanField(label=u'Invite my friends to this event via email!', widget=forms.CheckboxInput(), initial=True, required=False)
            if 2 in steps:
                self.fields['image'].initial = None
                self.fields['image'].required = False
                if self.instance.image:
                    _help = unicode(self.fields['image'].help_text) or ''
                    self.fields['image'].help_text = ' '.join([_('Leave this empty if you would like us to use your last uploaded image.'), _help])
                self.fields['bg_image'].initial = None
                self.fields['bg_image'].label = "Background<br/>image"
                if self.instance.bg_image:
                    _help = unicode(self.fields['bg_image'].help_text) or ''
                    htext = [_('Leave this empty if you would like us to use your last uploaded image.'), _help]
                    self.fields['bg_image'].help_text = ' '.join(htext)
                if bg_image_url:
                    self.fields['bg_image_url'] = forms.CharField(widget=forms.HiddenInput(), initial=bg_image_url, required=False)
                    self.fields['bg_tile'] = forms.CharField(widget=forms.HiddenInput(), initial=bg_tile and "tile" or "", required=False)
                    self.fields['use_twitter_background'] = forms.BooleanField(label=u"Use my Twitter background image as this event's background image", required=False, initial=False)
            if 3 in steps:
                self.fields['event_start_time'].input_formats = ('%I:%M %p',)
                self.fields['event_start_time'].widget.attrs.update({'class':'time_field'})
                self.fields['event_start_time'].widget.format = "%I:%M %p"
                loc_data = settings.LOCATION_DATA.get(self.location, None)
                self.fields['event_timezone'].initial = loc_data and loc_data[4] or u''
                self.fields['event_timezone'].widget = forms.HiddenInput()
                f = self.fields['mp3_url']
                self.fields['mp3_url'] = forms.CharField(label=f.label, initial=f.initial, max_length=1000, required=f.required, 
                        help_text = f.help_text
                )
                self.fields['embed_service'].label = u'External video type'
                self.fields['embed_service'].queryset = OEmbedProvider.objects.filter(service_type='video')
            if 'use_twitter_background' in self.fields:
                keys = self.fields.keyOrder
                keys.remove('bg_image')
                keys.append('bg_image')

        class Meta(object):
            model = Event
            fields = []
            if 1 in steps:
                fields.extend(['title', 'event_date', 'description'])
            if 2 in steps:
                fields.extend(['image', 'bg_image'])
            if 3 in steps:
                fields.extend(['is_free', 'price_text', 'ticket_url', 'hashtag', 'event_start_time', 'event_timezone',
                               'mp3_url', 'embed_service', 'embed_url'])

        def _media(self):
            _append = "?v=%s" % settings.UI_SETTINGS['UI_JS_VERSION']
            return forms.Media(js=(
                'ui/js/jquery.timepicker.js' + _append,
                'ui/js/fckeditor/fckeditor.js' + _append,
                'ui/js/event.js' + _append
            ))
        media = property(_media)

        def clean_url(self):
            url = self.cleaned_data['url'].lower()
            if not is_event_url_available(url, getattr(self, 'instance', None)):
                raise forms.ValidationError(_('That url is not available. Please try another.'))
            return url

        def clean_min_age(self):
            age = self.cleaned_data.get('min_age', 0)
            if age > 0 and age < settings.EVENT_MIN_AGE_RANGE[0]:
                raise forms.ValidationError(_(u'The minimum age must be at least %s years, if provided.' % settings.EVENT_MIN_AGE_RANGE[0]))
            return age
    
        def clean_price(self):
            amount = self.cleaned_data['price']
            if amount < 0:
                raise forms.ValidationError(_(u'The amount must not be a negative number.'))
            return amount
    
        def clean_ticket_url(self):
            url = self.cleaned_data.get('ticket_url', None)
            if url and not url.startswith('http'):
                raise forms.ValidationError(_(u'Only <em>http</em> and <em>https</em> URLs are currently supported.'))
            return url

        def clean_image(self, fieldname="image", maxsizemb=settings.EVENT_IMAGE_MAX_SIZE_MB):
            img = self.cleaned_data.get(fieldname, None)
            if img:
                if hasattr(img, 'name'):
                    fname, ext = os.path.splitext(img.name)
                    if not ext:
                        raise forms.ValidationError(_(u'The file you have uploaded does not have an extension. Only JPEG and PNG images with the file extensions .jpeg, .jpg, or .png are accepted.'))
                    if not (ext.lower() in ('.jpeg', '.png', '.jpg') and get_image_format(img) in ('JPEG', 'PNG')):
                        raise forms.ValidationError(_(u'The file you have uploaded is not an acceptable image. Only JPEG and PNG images are accepted.'))
                    if img.size > maxsizemb*1000000:
                        sz = img.size/1000000
                        raise forms.ValidationError(_(u"The image file you have uploaded is too big. Please upload a file under %s MB.") % int(maxsizemb))
                    if img.size == 0:
                        raise forms.ValidationError(_(u"The image file you have uploaded is empty. Please upload a real image."))
            return img

        def clean_bg_image(self):
            return self.clean_image("bg_image", settings.EVENT_BG_IMAGE_MAX_SIZE_MB)

        def clean_event_date(self):
            dt = self.cleaned_data["event_date"]
            today = date.today()
            if dt < today:
                raise forms.ValidationError(_(u'The date may not be in the past.'))
            return dt

        def clean_event_end_time(self):
            event_end_time = self.cleaned_data["event_end_time"]
            if str(event_end_time) == "00:00:00":
                return event_end_time
            event_start_time = self.cleaned_data.get("event_start_time", None)
            if event_start_time and event_start_time > event_end_time:
                raise forms.ValidationError(_(u"The event end time must be later than the event start time."))
            return event_end_time

        def clean_event_timezone(self):
            tz = self.cleaned_data.get("event_timezone", "")
            if not tz:
                loc_data = settings.LOCATION_DATA.get(self.location, None)
                tz = loc_data and loc_data[4] or u''
            return tz

        def clean_description(self):
            description = self.cleaned_data.get("description", u'')
            if description:
                if not description.endswith('\n'):
                    description += '\n'
                description_stripped = force_unicode(sanitize_html(description))
                description = description_stripped.replace('\r\n', '\n')
            else:
                description = u''
            return description

        def clean_audio_player_embed(self):
            audio_player_embed = self.cleaned_data.get('audio_player_embed', None)
            if audio_player_embed:
                txt = audio_player_embed.lower()
                if len(audio_player_embed) > 2000 or xss_vulnerable_html(txt, EMBED_VALID_TAGS, EMBED_VALID_ATTRS):
                    raise forms.ValidationError(_(u"That embed code is invalid. Please try another embedded player."))
                found = False
                for phrase in settings.MP3_PLAYER_LIST:
                    if phrase in audio_player_embed:
                        found = True
                        break
                if not found:
                    raise forms.ValidationError(_(u"That embed code is not valid. Please try an embedded player from reverbnation.com or projectopus.com."))
            return audio_player_embed

        def clean_mp3_url(self):
            url = self.cleaned_data.get('mp3_url', None)
            if url:
                url = oembed_utils.get_soundcloud_param_value(url)
                if not url:
                    raise forms.ValidationError(_(u'Only SoundCloud.com URLs and embed codes are allowed here.'))
                url = url[:200]
                soundcloud_host = OEmbedProvider.objects.get(host__iexact='soundcloud.com', service_type='rich')
                if not oembed_utils.get_embed_code(soundcloud_host, url):
                    raise forms.ValidationError(_(u'That SoundCloud.com URL does not work.'))
            return url or None

        def clean_embed_url(self):
            url = self.cleaned_data.get('embed_url', None)
            host = self.cleaned_data.get('embed_service', None)
            if url:
                if not url.startswith('http'):
                    raise forms.ValidationError(_(u'Only <em>http</em> and <em>https</em> URLs are allowed here.'))
                if host:
                    resp_dict = oembed_utils.get_embed_code(host, url)
                    if not resp_dict:
                        raise forms.ValidationError(_(u'This embeddable  audio or video URL is not valid. Its embed code could not be generated.'))
                else:
                    raise forms.ValidationError(_(u'Please select your embeddable audio or video service from the above list.'))
            else:
                if host:
                    raise forms.ValidationError(_(u'An embeddable audio or video URL is required when you select an audio or video service above.'))
            return url

        def clean_fan_note(self):
            fan_note = self.cleaned_data.get("fan_note", None)
            if fan_note:
                if not fan_note.endswith('\n'):
                    fan_note += '\n'
                fan_note_stripped = force_unicode(strip_tags(fan_note)).replace('<', '').replace('>', '')
                if fan_note_stripped != fan_note:
                    raise forms.ValidationError(_(u'HTML tags < > are not allowed here.'))
                fan_note = fan_note.replace('\r\n', '\n')
            return fan_note

        def save(self, commit=True):
            event = super(EventForm, self).save(commit=False)
            inst = self.instance
            is_new = not inst.pk
            if not inst.pk:
                event.location = self.location
            event.is_member_generated = not user_profile.is_artist
            image_changed = False
            img = self.cleaned_data.get("image", None)
            if img:
                event.image.save("badge", img, save=False)
                image_changed = True
            bg_image = self.cleaned_data.get("bg_image", None)
            if not bg_image and self.cleaned_data.get("use_twitter_background", False):
                bg_image_url = self.cleaned_data.get("bg_image_url", None)
                if bg_image_url:
                    copy_background_image_from_url_to_event(bg_image_url, event, False)
                event.bg_tile = bool(self.cleaned_data.get("bg_tile", False))
            if bg_image:
                event.bg_image.save("badge-bg", bg_image, save=False)
            event.creator = user_profile
            if not inst.pk:
                event.artist = artist
                event.url = (u"%s-%s" % (slugify(event.title)[:30], uuid4().hex[::4]))[:35]
            if 1 in steps:
                venue_name = self.cleaned_data.get('venue_name', '').strip()
                venue_source = self.cleaned_data.get('venue_source', '').strip()
                venue_params = self.cleaned_data.get('venue_params', '').strip()
                if venue_params:
                    venue_params = json.loads(venue_params)
                venue = None
                inst = self.instance
                if inst.pk:
                    vn = inst.venue
                    # process venue update
                    if venue_name == vn.name:
                        if venue_params:
                            street = venue_params.get('streetAddress', u'')[:255]
                            city = venue_params.get('city', u'')[:255]
                            region = venue_params.get('region', u'')[:100]
                            uvn = (street, city, region)
                            dbvn = (vn.address, vn.city, vn.state)
                            if uvn == dbvn:
                                venue = vn # venue hasn't changed; retain it
                            else:
                                event._venue_changed = True
                        else:
                            # venue name hasn't changed
                            venue = vn # retain existing venue instance
                if not venue:
                    event._venue_changed = True
                    if venue_source == 'user-entered':
                        geo_loc = settings.VENUE_DEFAULT_GEO_LOC
                        venue, created = Venue.objects.get_or_create(
                            name=venue_name,
                            geo_loc=geo_loc,
                            defaults=dict(
                                source=venue_source,
                            )
                        )
                    else: # if venue_source == 'google-maps':
                        lat = venue_params['lat']
                        lng = venue_params['lng']
                        lat = str(round(float(lat), 3))
                        lng = str(round(float(lng), 3))
                        geo_loc = u"%s,%s" % (lat, lng)
                        title = venue_params['titleNoFormatting']
                        streetAddress = venue_params['streetAddress']
                        city = venue_params['city']
                        region = venue_params['region']
                        url = venue_params['url']
                        venue, created = Venue.objects.get_or_create(
                            name=title,
                            geo_loc=geo_loc,
                            defaults=dict(
                                source=venue_source,
                                address=streetAddress[:255],
                                city=city[:255],
                                state=region[:100],
                                map_url=url[:255],
                            )
                        )
                        if not created: # and venue.source != 'google-maps':
                            # Update empty fields
                            vn = venue
                            dirty = False
                            if not vn.address:
                                vn.address = streetAddress[:255]
                                dirty = True
                            if not vn.city:
                                vn.city = city[:255]
                                dirty = True
                            if not vn.state:
                                vn.state = region[:100]
                                dirty = True
                            if not vn.map_url:
                                vn.map_url = url[:255]
                                dirty = True
                            if dirty:
                                vn.save()
                event.venue = venue
            if not event.image:
                # Use default image
                _UI_MEDIA_ROOT = os.path.join(settings.MEDIA_ROOT, settings.UI_ROOT, 'internal')
                _DEFAULT_IMAGE = os.path.join(_UI_MEDIA_ROOT, settings.EVENT_BADGE_DEFAULT_IMAGE)
                f = open(_DEFAULT_IMAGE, "rb")
                img = f.read()
                f.close()
                event.image.save("badge", ContentFile(img), save=False)
                image_changed = True
            if commit:
                event.save()
                if is_new and self.cleaned_data.get('invite_by_email', False):
                    event_created(event)
                if image_changed or not event.image_resized:
                    try:
                        event._create_resized_images(raw_field=None, save=True)
                    except:
                        # retry once
                        try:
                            event._create_resized_images(raw_field=None, save=True)
                        except Exception, e:
                            _log.warn("Event image could not be resized. Event: %s - Image: %s", event.pk, event.image)
                            _log.exception(e)                            
            return event
    return EventForm


def get_event_form_main(request):
    EventForm = get_event_form(request)

    class EventFormMain(EventForm):
        """This is used by the ``event.views.EventFormWizard``.
    
        Show all event fields except for the image.
    
        """
        class Meta(EventForm.Meta):
            exclude = EventForm.Meta.exclude + ('image', 'mp3_url', 'audio_player_embed', 'embed_service', 'embed_url', 'hashtag')

    return EventFormMain


def get_event_form_image(request):
    EventForm = get_event_form(request)
    
    class EventFormImage(EventForm):
        """This is used by the ``EventFormWizard``.
    
        Show only the event image field.
    
        """
        class Meta(EventForm.Meta):
            fields = ('image', 'audio_player_embed', 'mp3_url', 'embed_service', 'embed_url', 'hashtag')
    
        def _media(self):
            return ''
        media = property(_media)

    return EventFormImage


def get_event_edit_form(event, request, steps=None):
    """Return a custom event edit form class based on the status of this event.

    If the event has already been approved, return a form with stricter validations 
    and a limited number of updatable fields. Otherwise, return the standard `EventForm`
    """
    return get_event_form(request, steps)

    # EventChangeForm is no longer used

    class EventChangeForm(forms.ModelForm):
        def __init__(self, *args, **kwargs):
            if not event.changed_version:
                changed_version = EventChange(event=event)
            else:
                changed_version = event.changed_version
            kwargs['instance'] = changed_version
            initial = {}
            # Set initial values from changed version or from event
            for fname in EventChange.MERGE_FIELDS:
                value = getattr(changed_version, fname) or getattr(event, fname)
                if isinstance(value, models.Model):
                    value = value.pk
                initial[fname] = value
            for fname in EventChange.BOOLEAN_MERGE_FIELDS:
                changed = getattr(changed_version, fname)
                orig = getattr(event, fname)
                initial[fname] = (changed_version.pk and [changed] or [orig])[0]
            kwargs['initial'] = initial
            super(EventChangeForm, self).__init__(*args, **kwargs)
            self.fields['title'] = forms.RegexField(label=_("Title"), max_length=255, regex=r"""^[a-zA-Z0-9 '.",!?:;\-\(\)]+$""",
                                                    help_text=Event.TITLE_HELP, required=False,
                                                    error_message=_("The title must consist of English letters, numbers, and punctuation only."))
            self.fields['title'].widget.attrs.update({'class':'textInput'})
            self.fields['max_attendees'].min_value = 0
            self.fields['max_attendees'].widget.attrs.update({'class':'textInput'})
            self.fields['price'].min_value = 0
            self.fields['price'].error_messages.update({'invalid':'Enter a number (without the dollar sign.)'})
            self.fields['price'].widget.attrs.update({'class':'textInput'})
            self.fields['description'].widget.attrs.update({'class':'textareaInput htmlEdit', 'rows':20})
            self.fields['venue'].widget.attrs.update({'class':'textInput'})
            self.fields['zip_code'] = USZipCodeField(label=_("Zip Code"), help_text=Event.ZIPCODE_HELP, required=False)
            self.fields['zip_code'].widget.attrs.update({'class':'textInput'})
            self.fields['event_date'].widget.attrs.update({'class':'textInput dateInput vDateField'})
            self.fields['event_start_time'].widget.attrs.update({'class':'textInput timeInput vTimeField'})
            # self.fields['event_end_time'].widget.attrs.update({'class':'textInput timeInput vTimeField'})
            self.fields['event_timezone'].widget.attrs.update({'class':'textInput'})
            self.fields['min_age'].required = False
            self.fields['min_age'].min_value = 0
            self.fields['min_age'].max_value = settings.EVENT_MIN_AGE_RANGE[1]
            self.fields['min_age'].widget.attrs.update({'class':'textInput'})
            self.fields['audio_player_embed'].widget.attrs.update({'class':'textareaInput'})
            self.fields['mp3_url'].widget.attrs.update({'class':'textInput'})
            self.fields['embed_service'].widget.attrs.update({'class':'dropdownList'})
            self.fields['embed_url'].widget.attrs.update({'class':'textInput'})
            # Disallow editing of inapplicable fields
            if event.is_sold_out or event.is_complete: 
                # Don't allow attendee related changes
                del self.fields['max_attendees']
                del self.fields['price']
            # Remove date fields if dates have passed
            now = date.today()
            if event.event_date < now:
                del self.fields['event_date']
                del self.fields['event_start_time']
                # del self.fields['event_end_time']

        class Meta(object):
            model = EventChange
            exclude = ('is_approved', 'is_submitted', 'submitted_on', 'event', 
                       'added_on', 'edited_on', 'event_end_time')

        def _media(self):
            _append = "?v=%s" % settings.UI_SETTINGS['UI_JS_VERSION']
            return forms.Media(js=(reverse('catalog_jsi18n') + _append,
                                  settings.ADMIN_MEDIA_PREFIX + 'js/core.js' + _append,
                                  settings.ADMIN_MEDIA_PREFIX + 'js/calendar.js' + _append,
                                  'ui/js/event/DateTimeShortcuts.js' + _append,
                                  'ui/js/fckeditor/fckeditor.js' + _append,
                                  'ui/js/event.js' + _append))
        media = property(_media)

        def clean_min_age(self):
            age = self.cleaned_data.get('min_age', 0)
            if age > 0 and age < settings.EVENT_MIN_AGE_RANGE[0]:
                raise forms.ValidationError(_(u'The minimum age must be at least %s years, if provided.' % settings.EVENT_MIN_AGE_RANGE[0]))
            return age

        def clean_price(self):
            amount = self.cleaned_data['price']
            if amount < 0:
                raise forms.ValidationError(_(u'The amount must not be a negative number.'))
            current = event.num_attendees
            if amount and current and amount > event.price:
                if current == 1:
                    t = "person has"
                else:
                    t = "people have"
                raise forms.ValidationError(_(u"%s %s already registered to attend this event. The event price may not be increased." % (current, t)))
            return amount

        def clean_max_attendees(self):
            max_attendees = self.cleaned_data.get('max_attendees', 0)
            current = event.num_attendees
            if max_attendees and current and max_attendees < current:
                if current == 1:
                    t = "person has"
                else:
                    t = "people have"
                raise forms.ValidationError(_(u"%s %s already registered to attend this event. This field must be left empty or be at least %s" % (current, t, current)))
            return max_attendees

        def clean_event_date(self):
            dt = self.cleaned_data["event_date"]
            today = date.today()
            if dt < today:
                raise forms.ValidationError(_(u'The date may not be in the past.'))
            return dt

        def clean_event_end_time(self):
            event_end_time = self.cleaned_data["event_end_time"]
            if str(event_end_time) == "00:00:00":
                return event_end_time
            event_start_time = self.cleaned_data.get("event_start_time", None)
            if event_start_time and event_start_time > event_end_time:
                raise forms.ValidationError(_(u"The event end time must be later than the event start time."))
            return event_end_time

        def clean_description(self):
            description = self.cleaned_data.get("description", None)
            if description:
                if not description.endswith('\n'):
                    description += '\n'
                description_stripped = force_unicode(sanitize_html(description))
                description = description_stripped.replace('\r\n', '\n')
            return description

        def clean_audio_player_embed(self):
            audio_player_embed = self.cleaned_data.get('audio_player_embed', None)
            if audio_player_embed:
                txt = audio_player_embed.lower()
                if len(audio_player_embed) > 2000 or xss_vulnerable_html(txt, EMBED_VALID_TAGS, EMBED_VALID_ATTRS):
                    raise forms.ValidationError(_(u"That embed code is invalid. Please try another embedded player."))
                found = False
                for phrase in settings.MP3_PLAYER_LIST:
                    if phrase in audio_player_embed:
                        found = True
                        break
                if not found:
                    raise forms.ValidationError(_(u"That embed code is not valid. Please try an embedded player from reverbnation.com or projectopus.com."))
            return audio_player_embed

        def clean_mp3_url(self):
            url = self.cleaned_data.get('mp3_url', None)
            audio_player_embed = self.cleaned_data.get('audio_player_embed', None)
            if url and audio_player_embed:
                raise forms.ValidationError(_(u'Please remove the above audio player embed code if you want us to use this direct MP3 URL instead.'))
            if url and not url.startswith('http'):
                raise forms.ValidationError(_(u'Only <em>http</em> and <em>https</em> URLs are currently supported.'))
            return url

        def clean_embed_url(self):
            url = self.cleaned_data.get('embed_url', None)
            host = self.cleaned_data.get('embed_service', None)
            if url:
                if not url.startswith('http'):
                    raise forms.ValidationError(_(u'Only <em>http</em> and <em>https</em> URLs are currently supported.'))
                if host:
                    resp_dict = oembed_utils.get_embed_code(host, url)
                    if not resp_dict:
                        raise forms.ValidationError(_(u'This embeddable video URL is not valid. Its embed code could not be generated.'))
                else:
                    raise forms.ValidationError(_(u'Please select your embeddable video service from the above list.'))
            else:
                if host:
                    raise forms.ValidationError(_(u'An embeddable video URL is required when you select a video service above.'))
            return url

        def clean_fan_note(self):
            fan_note = self.cleaned_data.get("fan_note", None)
            if fan_note:
                if not fan_note.endswith('\n'):
                    fan_note += '\n'
                fan_note_stripped = force_unicode(strip_tags(fan_note)).replace('<', '').replace('>', '')
                if fan_note_stripped != fan_note:
                    raise forms.ValidationError(_(u'HTML tags < > are not allowed here.'))
                fan_note = fan_note.replace('\r\n', '\n')
            return fan_note

        def save(self, commit=True):
            event_change = super(EventChangeForm, self).save(commit=False)
            event_change.is_approved = True
            if commit:
                event_change.save()
                # ActionItem.objects.q_event_action(event_change.event, 'merge-event-edits')
            return event_change

    return EventChangeForm # return dynamically defined form class


class EventCommentForm(CommentForm):
    def tweet_posted(self, comment, tweet):
        """When a comment is tweeted, save the tweet_id to prevent display of dupes"""
        if isinstance(comment.content_object, Event):
            tweetdict = json.loads(tweet)
            tid = unicode(tweetdict['id'])
            event = comment.content_object
            if event.eventtweet_set.filter(tweet_id=tid, source='twitter').count():
                return # skip duplicates of the same tweet
            et = EventTweet(
                event=event,
                is_onsite=True,
                source=u'twitter',
            )            
            et.set_tweet(tweetdict, do_save=True)            

