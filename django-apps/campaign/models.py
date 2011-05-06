from __future__ import absolute_import
import logging
import os.path
import random
import string
import textwrap
from time import time
from mimetypes import guess_type
from decimal import Decimal as D
from datetime import datetime, date, timedelta
import Image, ImageFont, ImageDraw

from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile, UploadedFile
from django.db import models
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _
from django.utils.safestring import mark_safe
from django.utils.text import truncate_words
from django.db.models import signals

from rdutils.url import admin_url
from rdutils.site import DISPLAY_SITE_URL
from rdutils.image import get_raw_png_image, resize_in_memory, get_perfect_fit_resize_crop, remove_model_image, close, get_raw_image, str_to_file
from rdutils.decorators import attribute_cache
from rdutils.text import slugify
from artist.models import ArtistProfile
from queue.models import ActionItem
from registration.models import Address
from photo.models import Photo
from event import badgegen
from oembed.models import ServiceProvider as OEmbedProvider
from campaign import signals as campaign_signals


_log = logging.getLogger('campaign.models')


_UI_MEDIA_ROOT = os.path.join(settings.MEDIA_ROOT, settings.UI_ROOT, 'internal')
_BADGE_BG_IMAGE_INTERNAL = os.path.join(_UI_MEDIA_ROOT, settings.CAMPAIGN_BADGE_BACKGROUND_IMAGE_INTERNAL)
_BADGE_BG_IMAGE_EXTERNAL = os.path.join(_UI_MEDIA_ROOT, settings.CAMPAIGN_BADGE_BACKGROUND_IMAGE_EXTERNAL)
_BADGE_CALLOUT_IMAGE = os.path.join(_UI_MEDIA_ROOT, settings.CAMPAIGN_BADGE_CALLOUT_IMAGE)


class CampaignManager(models.Manager):
    def active(self, **kwargs):
        """Return approved campaigns that have started but not yet ended."""
        now = date.today()
        return self.visible(is_approved=True, start_date__lte=now, end_date__gte=now, **kwargs)

    def visible(self, **kwargs):
        """Return campaigns that have not been marked as deleted."""
        return self.filter(is_deleted=False, **kwargs)

    def public(self, **kwargs):
        return self.visible(is_approved=True)


class VisibleCampaignManager(models.Manager):
    """A ``Manager`` that includes only those campaigns that have not been marked as deleted."""
    def get_query_set(self, *args, **kwargs):
        return super(VisibleCampaignManager, self).get_query_set(*args, **kwargs).filter(is_deleted=False)


# Custom image field
class CampaignImageField(models.ImageField):   
    def generate_filename(self, instance, filename):
        ext = os.path.splitext(filename)[1]
        if not ext:
            ext = '.jpg'
        filename = '%s-%s-%s%s' % (instance.artist.pk,
                                   instance.pk or int(time()),
                                   slugify(instance.title)[:10], ext)
        return super(CampaignImageField, self).generate_filename(instance, filename)

    def save_form_data(self, instance, data):
        """Override default field save action and create resized campaign images.

        `instance` is a campaign instance.

        """
        if data and isinstance(data, UploadedFile):
            # A new file is being uploaded. So delete the old one.
            remove_model_image(instance, 'image')
        super(CampaignImageField, self).save_form_data(instance, data)
        instance._create_resized_images(raw_field=data, save=False)


class Campaign(models.Model):
    # Constants --------------------------------------------
    END_DATE_ARRIVED = 'END_DATE_ARRIVED'
    NUM_CONTRIBUTIONS_RECEIVED = 'NUM_CONTRIBUTIONS_RECEIVED'
    TARGET_AMOUNT_RAISED = 'TARGET_AMOUNT_RAISED'
    NO_CONTRIBUTIONS_YET = 'NO_CONTRIBUTIONS_YET'
    ACTIVE = 'ACTIVE'
    NOT_ACTIVE = 'NOT_ACTIVE'
    TITLE_HELP = _("What are you trying to raise money for? 255 characters max. For example: Music Video, New Instruments, etc.")

    # DB field definitions ---------------------------------
    artist = models.ForeignKey(ArtistProfile)
    # Internal status fields
    edited_on = models.DateTimeField(_('edited on'), blank=True, null=True)
    is_submitted = models.BooleanField(_('is submitted'), default=False, db_index=True,
                    help_text=_('When this is checked, it means that the artist has submitted this campaign for approval.'))
    submitted_on = models.DateTimeField(_('submitted on'), blank=True, null=True)
    is_payout_requested = models.BooleanField(_('is payout requested'), default=False, db_index=True, editable=False,
                    help_text=_('When this is checked, it means that the artist has requested a payout for this campaign.'))
    payout_requested_on = models.DateTimeField(_('payout requested on'), blank=True, null=True, editable=False)
    is_event = models.BooleanField(_('is like show'), default=False, db_index=True,
                    help_text=_('Check this box to make this campaign behave like a show.'))
    is_approved = models.BooleanField(_('is approved'), default=False, db_index=True,
                    help_text=_('Check this box to approve and activate this campaign.'))
    approved_on = models.DateTimeField(_('approved on'), blank=True, null=True)
    is_homepage_worthy = models.BooleanField(_('is homepage worthy'), default=False, db_index=True,
                    help_text=_("Check this box if this campaign's badge may be picked up for special display on the homepage."))
    homepage_worthy_on = models.DateTimeField(_('homepage worthy on'), 
                    blank=True, null=True,
                    help_text=_("This date and time controls the order in which homepage worthy campaigns are displayed. Chronologically newer ones are displayed first."))
    # Artist entered fields
    title = models.CharField(_('campaign title'),
                                max_length=255,
                                help_text=TITLE_HELP)
    url = models.SlugField(_('URL'), max_length=35, db_index=True, unique=True, blank=True, null=True)
    max_contributions = models.PositiveIntegerField(_('maximum number of contributions'),
                                help_text=_("What's the maximum number of contributions allowed in this campaign?"))
    max_contributions_per_person = models.PositiveIntegerField(_('maximum number of allowed contributions per person'),
                                help_text=_("What's the maximum number of contributions allowed per contributor?"))
    contribution_amount = models.DecimalField(_('contribution amount ($)'),
                                max_digits=10,
                                decimal_places=2,
                                help_text=_('What is the fixed per-contribution amount (in US dollars)? Must be either zero for a free campaign or at least $%s for a paid campaign.' % settings.CAMPAIGN_CONTRIBUTION_AMOUNT_MIN_VALUE))
    offering = models.TextField(_('offering'),
                                help_text=_('What are you offering to your contributors?'))
    start_date = models.DateField(_('start date'), help_text=_('In the format M/D/YYYY or YYYY-M-D. For example, 7/21/2008 or 2008-7-21.'))
    end_date = models.DateField(_('end date'),
                                db_index=True,
                                help_text=_('When do you want this campaign to end? In the format M/D/YYYY or YYYY-M-D. For example, 8/21/2008 or 2008-8-21.'))
    # Eligibility criteria
    min_age = models.PositiveSmallIntegerField(_('contributor minimum age'),
                        blank=True,
                        help_text=_("Minimum age in years for a person to be eligible to contribute to this campaign. Leave empty if there's no age restriction."))
    phone_required = models.BooleanField(_('phone number required'),
                        default=False,
                        help_text=_('If a contributor must provide a phone number to be eligible in this campaign.'))
    address_required = models.BooleanField(_('address required'),
                        default=False,
                        help_text=_('If a contributor must provide an address to be eligible in this campaign.'))
    # Thank you note
    fan_note = models.TextField(_('Thank you note'), blank=True,
                                help_text=_('An optional plain-text message to be included in the email that is sent out to fans when they contribute to this campaign.'))
    # Badge source image
    image = CampaignImageField(_('badge image'),
                            upload_to='badges/original/%Y-%b',
                            max_length=250,
                            help_text=_("""We will resize this down to fit your campaign badge.
                                <ul>
                                    <li>The image format must be either JPEG or PNG.</li> 
                                    <li>The image must be in landscape format (width &gt; height).</li>
                                    <li>The file size must be under %s MB.</li>
                                </ul>""" % int(settings.CAMPAIGN_IMAGE_MAX_SIZE_MB)))
    embed_service = models.ForeignKey(OEmbedProvider, null=True, blank=True,
                    help_text=_('These are the embeddable video services we currently support. Select yours.'))
    embed_url = models.URLField(_('external video url'), max_length=255, null=True, blank=True,
                    help_text=_('''Now paste in the link to your video page and we will generate the 
                                   correct embed code for you. 
                                   For example: 
                                   <ul>
                                       <li>http://vimeo.com/339189</li>
                                       <li>http://www.youtube.com/watch?v=Apadq9iPNxA</li>
                                       <li>http://myspacetv.com/index.cfm?fuseaction=vids.individual&amp;videoid=27687089</li>
                                   </ul>'''))
    # Auto-generated image fields
    image_resized = models.ImageField(_('badge image resized'), upload_to='badges/resized/%Y-%b', max_length=250, editable=False)
    image_avatar = models.ImageField(_('avatar sized campaign image'), upload_to='badges/avatars/%Y-%b', max_length=250, editable=False)
    # Miscellaneous fields
    target_amount = models.DecimalField(_('target amount ($)'),
                                max_digits=10,
                                decimal_places=2,
                                editable=False,
                                help_text=_('How much are you trying to raise (in US dollars)? Enter 0 if this is a free campaign.'))
    num_tickets_total = models.PositiveIntegerField(default=0, blank=True, help_text=_('Number of tickets that were requested for this campaign by the artist.'))
    is_deleted = models.BooleanField(_('is hidden'), default=False, db_index=True,
                    help_text=_('When this is checked, this campaign will be visible only in the admin area and nowhere else.'))

    objects = CampaignManager()
    visible_objects = VisibleCampaignManager()

    class Meta:
        ordering = ('-start_date', '-end_date')
        permissions = (("can_manage_campaigns", "Can manage campaigns"),)

    def __unicode__(self):
        return u'%s: %s' % (self.artist.name, self.title)

    def get_absolute_url(self):
        if self.url:
            return reverse('view_campaign_seo', kwargs={'campaign_url':self.url, 'artist_url':self.artist.url})
        else:
            return reverse('view_campaign', kwargs={'campaign_id':self.pk})

    def save(self, **kwargs):
        just_approved, just_deleted = False, False
        is_update = self.pk is not None
        if is_update and (self.is_approved or self.is_deleted):
            # Check if this campaign was just approved/deleted
            # based on its status in the DB's old copy.
            db_copy = Campaign.objects.get(pk=self.pk)
            just_approved = self.is_approved and not db_copy.is_approved
            just_deleted = self.is_deleted and not db_copy.is_deleted
        if not self.min_age:
            self.min_age = 0
        if self.is_submitted and not self.submitted_on:
            self.submitted_on = datetime.now()
        if self.is_approved and not self.approved_on:
            self.approved_on = datetime.now()
        if self.is_homepage_worthy and not self.homepage_worthy_on:
            self.homepage_worthy_on = datetime.now()
        if self.max_contributions == 0:
            self.max_contributions = settings.CAMPAIGN_MAX_CONTRIBUTORS_MIN_VALUE
        if self.num_tickets_total is None:
            self.num_tickets_total = 0
        self.target_amount = self.contribution_amount * D(self.max_contributions)
        if not self.target_amount:
            # Allow only one contribution per person in a free campaign.
            self.max_contributions_per_person = 1
        if self.offering:
            self.offering = self.offering.replace('\r\n', '\n')
        if self.fan_note:
            self.fan_note = self.fan_note.replace('\r\n', '\n')
        super(Campaign, self).save(**kwargs)
        if not is_update: # When a campaign is first created, create an empty Stats child object for it.
            Stats.objects.get_or_create(campaign=self)
        ActionItem.objects.q_campaign_action(self, 'generate-badges')
        self.create_badges()
        ActionItem.objects.q_campaign_action_done(self, 'generate-badges')
        if just_approved:
            ActionItem.objects.q_admin_action_done(self, 'approve-campaign')
            ActionItem.objects.q_campaign_action(self, 'email-campaign-approval')
            campaign_signals.post_campaign_approval.send(sender=self.__class__, instance=self)
        if just_deleted:
            ActionItem.objects.q_admin_action_done(self, 'delete-campaign')
            campaign_signals.post_campaign_deletion.send(sender=self.__class__, instance=self)

    def delete(self):
        ActionItem.objects.q_admin_action_done(self, 'delete-campaign')
        super(Campaign, self).delete()

    def _create_resized_images(self, raw_field, save):
        """Generate scaled down images needed for campaign badges and avatars."""
        # Derive base filename (strip out the relative directory).
        filename = os.path.split(self.image.name)[-1]
        ctype = guess_type(filename)[0]

        # Generate resized copy of image.
        remove_model_image(self, 'image_resized')
        bb = self.is_event and settings.EVENT_RESIZED_IMAGE_BOUNDING_BOX or settings.CAMPAIGN_RESIZED_IMAGE_BOUNDING_BOX
        resize, crop, img = get_perfect_fit_resize_crop(bb, input_image=self.image.path)
        resized_contents = resize_in_memory(img, resize, crop=crop)
        resized_file = str_to_file(resized_contents)
        resized_field = InMemoryUploadedFile(resized_file, None, None, ctype, len(resized_contents), None)
        self.image_resized.save(name='resized-%s' % filename, content=resized_field, save=save)
        resized_file.close()

        # Generate avatar.
        remove_model_image(self, 'image_avatar')
        avatar_contents = resize_in_memory(self.image.path, settings.CAMPAIGN_AVATAR_IMAGE_CROP, crop=settings.CAMPAIGN_AVATAR_IMAGE_CROP, crop_before_resize=True)
        avatar_file = str_to_file(avatar_contents)
        avatar_field = InMemoryUploadedFile(avatar_file, None, None, ctype, len(avatar_contents), None)
        self.image_avatar.save(name='avatar-%s' % filename, content=avatar_field, save=save)
        avatar_file.close()

    def admin_artist_link(self):
        return admin_url(self.artist, verbose_name=self.artist.short_name)
    admin_artist_link.short_description = 'artist'
    admin_artist_link.allow_tags = True
    admin_artist_link.admin_order_field = 'artist'

    def admin_stats_link(self):
        return admin_url(self.stats, verbose_name=(self.target_amount or 'free!'))
    admin_stats_link.short_description = 'target'
    admin_stats_link.allow_tags = True
    admin_stats_link.admin_order_field = 'target_amount'

    def admin_contribution_amount(self):
        return self.contribution_amount
    admin_contribution_amount.short_description = 'per fan'
    admin_contribution_amount.admin_order_field = 'contribution_amount'

    def admin_num_tickets_total(self):
        return self.num_tickets_total
    admin_num_tickets_total.short_description = 'max tix'
    admin_num_tickets_total.admin_order_field = 'num_tickets_total'

    def admin_max_contributions(self):
        return self.max_contributions
    admin_max_contributions.short_description = 'max fans'
    admin_max_contributions.admin_order_field = 'max_contributions'

    def admin_status(self):
        if self.is_deleted:
            return u'Hidden'
        if self.is_submitted and not self.is_approved:
            return u'Submitted'
        if self.is_approved:
            if self.is_homepage_worthy:
                return u'Homepage worthy'
            else:
                return u'Approved'
        if self.is_payout_requested:
            return u'Payout requested'
    admin_status.short_description = 'status'

    @property
    def sort_date(self):
        """Date field used to merge campaigns and events together into a mixed feed."""
        return self.end_date

    @property
    @attribute_cache('owner')
    def owner(self):
        return self.artist.user_profile.user

    def is_user_qualified(self, user):
        """Return tuple (True/False, reason_list) based on whether user abides by all 
        campaign rules or not.

        Return True if user qualifies. False, otherwise. When False, return a list of 
        reasons for non-qualification.

        """
        reason_list = []
        qual = True
        p = user.get_profile()
        if not (user.first_name and user.last_name):
            qual = False
            reason_list.append('NO_NAME')
        if self.address_required:
            try:
                adr = p.address
            except Address.DoesNotExist:
                qual = False
                reason_list.append('NO_ADDRESS')
        if self.phone_required and not p.phone:
            qual = False
            reason_list.append('NO_PHONE')
        if self.min_age:
            if p.age is None:
                qual = False
                reason_list.append('NO_BIRTH_DATE')
            elif p.age < self.min_age:
                qual = False
                reason_list.append('NOT_OLD_ENOUGH')
        return (qual, reason_list)

    @property
    @attribute_cache('is_editable')
    def is_editable(self):
        if self.is_deleted or self.has_ended:
            return False
        if self.changed_version and self.changed_version.is_approved:
            # Allow queue processor to merge approved changes before permitting new edits.
            return False
        return True

    @property
    @attribute_cache('is_public')
    def is_public(self):
        return not self.is_deleted and self.is_approved

    @property
    @attribute_cache('is_active')
    def is_active(self):
        now = date.today()
        return not self.is_deleted and self.is_approved and self.start_date <= now and self.end_date >= now

    @property
    @attribute_cache('has_ended')
    def has_ended(self):
        return self.is_approved and self.end_date < date.today()

    @property
    @attribute_cache('has_photos')
    def has_photos(self):
        return Photo.objects.get_for_object(self).count()

    @property
    @attribute_cache('ticket_redeem_by_date')
    def ticket_redeem_by_date(self):
        return self.end_date + timedelta(days=settings.CAMPAIGN_TICKET_REDEEM_BY_GRACE_DAYS)

    @property
    @attribute_cache('is_deletable')
    def is_deletable(self):
        """Return true if this campaign has not been approved or has not yet started AND
        no contributions are associated with it.

        In all other cases, an admin needs to review the campaign before it may be deleted.

        """
        # Deletion functionality is currently under discussion.
        # For now, delete requests are emailed to the admin.
        return False
        #return (not self.is_approved or self.start_date > now) and (not self.amount_raised) and (not self.is_deleted)

    @property
    @attribute_cache('are_tickets_available')
    def are_tickets_available(self):
        """Return true if tickets may be requested for this campaign.

        True only if the campaign is active and at least some online
        contributions are left to be fulfilled. Tickets are allocated from
        the online contributions left unfulfilled.

        """
        return self.is_active and self.num_online_left > 0

    @property
    @attribute_cache('is_payout_available')
    def is_payout_available(self):
        """Return true only if the campaign has ended, payout has not yet been 
        requested and a non-zero amount was raised
        by this campaign online (i.e. excluding ticket sales.)

        """
        return False # Disabled because artist receives payout directly from fan
        # return self.has_ended and not self.is_payout_requested and self.amount_raised_online and not self.is_deleted

    def image_preview(self):
        """Return HTML fragment to display campaign image."""
        h = '<img src="%s" alt="%s"/>' % (self.image_resized_url, self.title)
        return mark_safe(h)
    image_preview.allow_tags = True
    image_preview.short_description = 'image'

    def avatar_preview(self):
        """Return HTML fragment to display campaign avatar."""
        h = '<img src="%s" alt="%s"/>' % (self.image_avatar_url, self.title)
        return mark_safe(h)
    avatar_preview.allow_tags = True
    avatar_preview.short_description = 'avatar'

    @property
    @attribute_cache('short_title')
    def short_title(self):
        """Return a short title for the campaign."""
        return truncate_words(self.title, settings.CAMPAIGN_SHORT_TITLE_WORDS)

    @property
    @attribute_cache('amount_raised')
    def amount_raised(self):
        """Return the total amount raised (online + tickets) to date by this campaign."""
        return self.stats.amount_raised

    @property
    @attribute_cache('amount_raised_online')
    def amount_raised_online(self):
        """Return the amount raised online to date by this campaign (excluding tickets)."""
        return self.stats.amount_raised_online

    @property
    @attribute_cache('amount_raised_by_tickets')
    def amount_raised_by_tickets(self):
        """Return the amount raised online to date by this campaign (excluding tickets)."""
        return self.stats.amount_raised_by_tickets

    @property
    @attribute_cache('is_complete')
    def is_complete(self):
        """Return (True/False, reason) if this campaign is complete, based on any of these rules:
          - End date has arrived
          - Total number of contributors has been met
          - Total amount has been raised (for non-free campaigns)
          See ``completion_status`` below.

        """
        completed, reason = self.completion_status
        return completed

    @property
    @attribute_cache('is_free')
    def is_free(self):
        return self.target_amount == D('0')

    @property
    @attribute_cache('action_name')
    def action_name(self):
        payment_action = self.is_event and 'purchase tickets' or 'contribute to campaign'
        return self.is_free and 'join campaign' or payment_action

    @property
    @attribute_cache('sponsor_or_attendee')
    def sponsor_or_attendee(self):
        return self.is_event and 'attendee' or 'sponsor'

    @property
    @attribute_cache('contributor_or_attendee')
    def contributor_or_attendee(self):
        return self.is_event and 'attendee' or 'contributor'

    @property
    @attribute_cache('contribution_or_ticket')
    def contribution_or_ticket(self):
        return self.is_event and 'ticket' or 'contribution'

    @property
    @attribute_cache('completion_status')
    def completion_status(self):
        """Return a tuple with campaign_completion_status and completion reason."""
        if self.end_date < date.today():
            return True, self.END_DATE_ARRIVED
        try:
            if self.stats.num_contributions == self.max_contributions:
                return True, self.NUM_CONTRIBUTIONS_RECEIVED
            if self.target_amount > D('0'): # Not a free campaign
                if self.stats.amount_raised >= self.target_amount:
                    return True, self.TARGET_AMOUNT_RAISED
        except Stats.DoesNotExist:
            return False, self.NO_CONTRIBUTIONS_YET
        return False, self.is_active and self.ACTIVE or self.NOT_ACTIVE

    @property
    @attribute_cache('is_sold_out')
    def is_sold_out(self):
        return self.stats.num_contributions == self.max_contributions

    @property
    @attribute_cache('stats')
    def stats(self):
        return self.stats_set.get()

    @property
    @attribute_cache('num_online_left')
    def num_online_left(self):
        """Return number of online contribution slots left."""
        return self._contributions_left[0]

    @property
    @attribute_cache('num_tickets_left')
    def num_tickets_left(self):
        """Return number of tickets left unredeemed."""
        return self._contributions_left[1]

    def num_online_left_for_user(self, user):
        """Return number of online contribution slots left for ``user``."""
        q = self.contribution_set.filter(contributor=user)
        num_user_contribs = sum([c.qty for c in q])
        remaining = self.max_contributions_per_person - num_user_contribs
        if remaining < 0:
            remaining = 0
        left = min(remaining, self.num_online_left)
        return left

    @property
    @attribute_cache('_slots_left')
    def _contributions_left(self):
        """Return tuple with number of online contributions left, unredeemed tickets left."""
        if self.is_complete:
            return 0, 0
        online_left = self.online_quota - self.stats.num_online_contributions
        if online_left < 0:
            online_left = 0
        tickets_left = self.num_tickets_total - self.stats.num_tickets_redeemed
        return (online_left, tickets_left)

    @property
    @attribute_cache('num_contributions')
    def num_contributions(self):
        """Return number of online and ticket contributions made to this campaign."""
        return self.stats.num_online_contributions + self.stats.num_tickets_redeemed

    @property
    @attribute_cache('num_attendees')
    def num_attendees(self):
        """Return number of attendee i.e. tickets purchased when this campaign behaves like an event."""
        n = sum([c.qty for c in self.contribution_set.all()])
        return n

    @property
    def event_date(self):
        """Return end date of the campaign; used when this campaign behaves like an event."""
        return self.end_date

    @property
    def special_badge_text(self):
        """Used by badge generation code when this campaign behaves like an event."""
        return None

    @property
    @attribute_cache('online_quota')
    def online_quota(self):
        """Return the number of online contributions accepted excluding tickets."""
        return self.max_contributions - self.num_tickets_total

    @property
    @attribute_cache('ticket_prefix')
    def ticket_prefix(self):
        url = self.artist.url[:3].replace('-', 'Z') # first 3 letters from artist's url
        pk = '%03d' % (self.pk % 1000) # last 3 digits of campaign.pk
        prefix = '%s%3s' % (url, pk)
        prefix = prefix.upper().replace(' ', 'Z').replace('O', 'Z').replace('0', random.choice('ABCXYZ'))
        return prefix

    @property
    @attribute_cache('short_title_chars')
    def short_title_chars(self):
        """Return the campaign's title upto ``settings.CAMPAIGN_SHORT_TITLE_LENGTH`` characters long."""
        if len(self.title) > settings.CAMPAIGN_SHORT_TITLE_LENGTH:
            return mark_safe(u'%s&hellip;' % self.title[:settings.CAMPAIGN_SHORT_TITLE_LENGTH])
        else:
            return self.title

    def _badge_chars_per_line(self, text, font, font_size):
        """Return characters per line computed to fit within a badge's available area."""
        xmin, y = settings.CAMPAIGN_BADGE_TITLE_POSITION
        xmax, y = settings.CAMPAIGN_BADGE_CALLOUT_POSITION
        width_available = xmax - xmin - settings.CAMPAIGN_BADGE_TITLE_CLEARANCE # clearance
        font = ImageFont.truetype(font, font_size, encoding='unic')
        w, h = font.getsize(text)
        pixels_per_char = float(w)/float(len(text))
        chars_per_line = int(width_available/pixels_per_char)
        # If chars_per_line is slightly off, adjust it
        one_line = text[:chars_per_line]
        w, h = font.getsize(one_line)
        dw = w - width_available
        if dw > 0:
            dchar = dw/pixels_per_char + 2
            chars_per_line -= dchar
        return chars_per_line

    @property
    @attribute_cache('artist_short_name_for_badge')
    def artist_short_name_for_badge(self):
        name = self.artist.name
        chars_per_line = self._badge_chars_per_line(self.artist.name, settings.CAMPAIGN_BADGE_ARTIST_FONT, settings.CAMPAIGN_BADGE_ARTIST_FONT_SIZE)
        if len(name) > chars_per_line:
            return u'%s...' % name[:chars_per_line]
        else:
            return name

    @property
    @attribute_cache('short_title_wrapped_for_badge')
    def short_title_wrapped_for_badge(self):
        """Return the campaign's title with wrapped lines to fit a badge.

        Each line is returned as a list element.

        """
        chars_per_line = self._badge_chars_per_line(self.title, settings.CAMPAIGN_BADGE_TITLE_FONT, settings.CAMPAIGN_BADGE_TITLE_FONT_SIZE)
        max_lines = settings.CAMPAIGN_BADGE_TITLE_MAX_LINES
        if len(self.title) > chars_per_line:
            wrapped = textwrap.wrap(self.title, chars_per_line)
            ellipsis_needed = len(wrapped) > max_lines
            wrapped = wrapped[:max_lines]
            if ellipsis_needed or (wrapped and (len(wrapped) == max_lines) and (len(wrapped[max_lines - 1]) > chars_per_line)):
                wrapped[max_lines - 1] = u'%s...' % wrapped[max_lines - 1][:-3]
            return wrapped
        else:
            return [self.title]

    def create_badges(self, badge_types=None):
        if badge_types is None:
            badge_types = map(lambda x:x[0], Badge.BADGE_TYPES)
        badge_maker = self.is_event and self.create_event_badge or self.create_badge
        for t in badge_types:
            try:
                badge = self.badge_set.get(badge_type=t)
            except Badge.DoesNotExist:
                badge = Badge(campaign=self, badge_type=t)
            badge_maker(badge)

    def create_event_badge(self, badge, special=None, num_attendees=None):
        badgegen.create_badge(event=self, badge=badge, special=special, num_attendees=num_attendees)

    def create_badge(self, badge):
        _log.debug('Creating campaign badge: %s' % badge.get_badge_type_display())
        bg, fg = None, None
        try:
            badge_type, badge_img = badge.badge_type, badge.bg_image_path
            bg = Image.open(badge_img)
            fg = Image.open(self.image_resized.path)
            bg.paste(fg, settings.CAMPAIGN_BADGE_IMAGE_POSITION)
            t = ImageDraw.Draw(bg)

            x, y = settings.CAMPAIGN_BADGE_ARTIST_POSITION

            # Artist name
            tx = self.artist_short_name_for_badge
            font = ImageFont.truetype(settings.CAMPAIGN_BADGE_ARTIST_FONT, settings.CAMPAIGN_BADGE_ARTIST_FONT_SIZE, encoding='unic')
            t.text((x, y), tx, font=font, fill='#333333')
            dx, dy = t.textsize(tx, font=font)
            y += dy + 2 # starting point for the next line

            px, py = settings.CAMPAIGN_BADGE_TITLE_POSITION
            x += px
            y += py # starting point for the next line

            # Campaign title
            lines = self.short_title_wrapped_for_badge
            font = ImageFont.truetype(settings.CAMPAIGN_BADGE_TITLE_FONT, settings.CAMPAIGN_BADGE_TITLE_FONT_SIZE, encoding='unic')
            for line in lines:
                t.text((x, y), line.strip(), font=font, fill='#b30000')
                dx, dy = t.textsize(line, font=font)
                y += dy + 2 # starting point for the next line

            mx, my = settings.CAMPAIGN_BADGE_TEXT_POSITION
            x += mx
            y += my # starting point for the next line

            # Amount raised
            # if False and self.amount_raised and not self.is_free: # THIS HAS BEEN DISABLED
            #    tx =  _('Raised to date: $%.2f') % self.amount_raised
            #    font = ImageFont.truetype(settings.CAMPAIGN_BADGE_TEXT_FONT, settings.CAMPAIGN_BADGE_TEXT_FONT_SIZE, encoding='unic')
            #    t.text((x, y), tx, font=font,  fill='#333333')

            # Free campaign
            # if False and self.is_free: # DISABLED
            #    tx =  _('Join us for free!')
            #    font = ImageFont.truetype(settings.CAMPAIGN_BADGE_TEXT_FONT, settings.CAMPAIGN_BADGE_TEXT_FONT_SIZE, encoding='unic')
            #    t.text((x, y), tx, font=font,  fill='#333333')

            # Callout box
            box = Image.open(_BADGE_CALLOUT_IMAGE)
            bg.paste(box, settings.CAMPAIGN_BADGE_CALLOUT_POSITION) # callout background

            # Save generated image
            raw_img = get_raw_image(bg, jpeg_quality=settings.CAMPAIGN_BADGE_JPEG_QUALITY)
            if raw_img:
                raw_file = str_to_file(raw_img)
                # file, field_name, name, content_type, size, charset
                raw_badge = InMemoryUploadedFile(raw_file, None, None, guess_type(".jpg")[0], len(raw_img), None)
                remove_model_image(badge, 'image') # remove previous resized copy
                badge.image.save(name='badge-%s-%s-%s.jpg' % (badge_type, self.pk, int(time())), content=raw_badge, save=False)
                badge.save()
                raw_file.close()
                _log.info('Badge (type: %s) created: %s - %s', badge_type, self.pk, self.title)
            else:
                _log.error('Badge (type: %s) creation failed: %s - %s', badge_type, self.pk, self.title)
        except Exception, e:
            _log.exception(e)
            raise
        finally:
            close(bg)
            close(fg)

    def recompute(self):
        """Recompute campaign statistics."""
        stats = Stats.objects.get(campaign=self)
        # Stats from regular (non-ticket) contributions:
        q = Contribution.objects.filter(campaign=self)
        stats.num_online_contributions = sum([c.qty for c in q])
        stats.amount_raised_online = sum([c.amount for c in q])
        # Stats from redeemed tickets:
        q2 = self.ticket_set.redeemed()
        count = q2.count()
        ticket_amt = sum([c.amount for c in q2])
        # Save stats
        stats.num_tickets_redeemed = count
        stats.num_tickets_total = self.ticket_set.count()
        stats.amount_raised_by_tickets = ticket_amt
        stats.num_contributions = stats.num_online_contributions + count
        stats.amount_raised = stats.amount_raised_online + stats.amount_raised_by_tickets
        stats.save()
        # queue up an action to generate/update badges
        ActionItem.objects.q_campaign_action(self, 'generate-badges')

    @property
    @attribute_cache('changed_version')
    def changed_version(self):
        """Return the latest unapproved changes for this campaign"""
        try:
            return CampaignChange.objects.get(campaign__pk=self.pk)
        except CampaignChange.DoesNotExist:
            return None

    def notify_contributors(self, message, exclude=None):
        exclude = exclude or []
        for a in self.contributor_set.select_related('contributor').all():
            if a.contributor.pk not in exclude:
                a.contributor.specialmessage_set.create(message=message)


class CampaignChange(models.Model):
    """A model to hold unapproved edits to an active campaign."""
    MERGE_FIELDS = (
        'title',
        'max_contributions',
        'max_contributions_per_person', 
        'contribution_amount',
        'offering', 
        'start_date',
        'end_date', 
        'min_age',
        'fan_note', 
        'embed_service',
        'embed_url', 
    )
    BOOLEAN_MERGE_FIELDS = ('address_required', 'phone_required',)
    campaign = models.ForeignKey(Campaign, unique=True)
    title = models.CharField(_('campaign title'),
                                blank=True, null=True,
                                max_length=255,
                                help_text=Campaign.TITLE_HELP)
    max_contributions = models.PositiveIntegerField(_('maximum number of contributions'),
                                null=True, blank=True,
                                help_text=_("What's the maximum number of contributions allowed in this campaign?"))
    max_contributions_per_person = models.PositiveIntegerField(_('maximum number of allowed contributions per person'),
                                null=True, blank=True,
                                help_text=_("What's the maximum number of contributions allowed per contributor?"))
    contribution_amount = models.DecimalField(_('contribution amount ($)'),
                                null=True, blank=True,
                                max_digits=10,
                                decimal_places=2,
                                help_text=_('What is the fixed per-contribution amount (in US dollars)? Must be either zero for a free campaign or at least $%s for a paid campaign.' % settings.CAMPAIGN_CONTRIBUTION_AMOUNT_MIN_VALUE))
    offering = models.TextField(_('offering'),
                                blank=True, null=True,
                                help_text=_('What are you offering to your contributors?'))
    start_date = models.DateField(_('start date'), null=True, blank=True, help_text=_('In the format M/D/YYYY or YYYY-M-D. For example, 7/21/2008 or 2008-7-21.'))
    end_date = models.DateField(_('end date'),
                                null=True, blank=True,
                                db_index=True,
                                help_text=_('When do you want this campaign to end? In the format M/D/YYYY or YYYY-M-D. For example, 8/21/2008 or 2008-8-21.'))
    min_age = models.PositiveSmallIntegerField(_('contributor minimum age'),
                        blank=True, null=True,
                        help_text=_("Minimum age in years for a person to be eligible to contribute to this campaign. Leave empty if there's no age restriction."))
    phone_required = models.NullBooleanField(_('phone number required'),
                        default=False, null=True, blank=True,
                        help_text=_('If a contributor must provide a phone number to be eligible in this campaign.'))
    address_required = models.NullBooleanField(_('address required'),
                        default=False, null=True, blank=True,
                        help_text=_('If a contributor must provide an address to be eligible in this campaign.'))
    fan_note = models.TextField(_('Thank you note'), blank=True, null=True,
                                help_text=_('An optional plain-text message to be included in the email that is sent out to fans when they contribute to this campaign.'))
    embed_service = models.ForeignKey(OEmbedProvider, null=True, blank=True,
                    help_text=_('These are the embeddable video services we currently support. Select yours.'))
    embed_url = models.URLField(_('external video url'), max_length=255, null=True, blank=True,
                    help_text=_('''Now paste in the link to your video page and we will generate the 
                                   correct embed code for you. 
                                   For example: 
                                   <ul>
                                       <li>http://vimeo.com/339189</li>
                                       <li>http://www.youtube.com/watch?v=Apadq9iPNxA</li>
                                       <li>http://myspacetv.com/index.cfm?fuseaction=vids.individual&amp;videoid=27687089</li>
                                   </ul>'''))
    is_submitted = models.BooleanField(_('is submitted'), default=False, db_index=True, editable=False,
                    help_text=_('When this is checked, it means that the artist has submitted this change for approval.'))
    submitted_on = models.DateTimeField(_('submitted on'), blank=True, null=True, editable=False)
    added_on = models.DateTimeField(_('added on'), blank=True, null=True, db_index=True)
    edited_on = models.DateTimeField(_('last edited on'), blank=True, null=True)
    is_approved = models.BooleanField(_('is approved'), default=False, db_index=True,
                    help_text=_('Check this box to approve and activate this change. This action can not be undone.'))

    def __unicode__(self):
        return unicode(self.campaign)

    class Meta:
        ordering = ('-start_date', '-end_date')

    def save(self, *args, **kwargs):
        if not self.added_on:
            self.added_on = datetime.now()
        if not self.is_approved:
            self.edited_on = datetime.now()
            self.is_submitted = True
            self.submitted_on = datetime.now()
        just_approved = False
        is_update = self.pk is not None
        if self.offering:
            self.offering = self.offering.replace('\r\n', '\n')
        if self.fan_note:
            self.fan_note = self.fan_note.replace('\r\n', '\n')
        if is_update and self.is_approved:
            # Check if this change was just approved
            # based on its status in the DB's old copy.
            db_copy = CampaignChange.objects.get(pk=self.pk)
            just_approved = self.is_approved and not db_copy.is_approved
        # Clear out fields that were not changed
        n_changes = 0
        for fname in self.MERGE_FIELDS:
            ch = getattr(self, fname)
            if ch:
                if ch == getattr(self.campaign, fname):
                    setattr(self, fname, None)
                else:
                    n_changes += 1
        super(CampaignChange, self).save(*args, **kwargs)
        if just_approved:
            ActionItem.objects.q_admin_action_done(self.campaign, 'approve-campaign-edit')
            ActionItem.objects.q_campaign_action(self.campaign, 'merge-campaign-edits')

    def delete(self):
        ActionItem.objects.q_admin_action_done(self.campaign, 'approve-campaign-edit')
        ActionItem.objects.q_campaign_action_done(self.campaign, 'merge-campaign-edits')
        super(CampaignChange, self).delete()

    @property
    @attribute_cache('embed_service_latest')
    def embed_service_latest(self):
        """Return embed_service from this instance or from the campaign instance."""
        return self.embed_service and self.embed_service or self.campaign.embed_service


class Badge(models.Model):
    """Model for internal/external badges for a campaign."""
    BADGE_TYPES = (('i', 'Internal'), ('e', 'External'))
    BADGE_BG_IMAGES = {'i':_BADGE_BG_IMAGE_INTERNAL, 'e':_BADGE_BG_IMAGE_EXTERNAL}

    campaign = models.ForeignKey(Campaign)
    badge_type = models.CharField(max_length=1, db_index=True, choices=BADGE_TYPES)
    updated_on = models.DateTimeField(blank=True)
    image = models.ImageField(upload_to='badges/generated/%Y-%b', max_length=250, editable=False)

    class Meta:
        unique_together = (('campaign', 'badge_type'),)

    def save(self, **kwargs):
        self.updated_on = datetime.now()
        super(Badge, self).save(**kwargs)

    def image_preview(self):
        """Return HTML fragment to display badge image."""
        h = '<img src="%s" alt="Campaign badge"/>' % self.image.url
        return mark_safe(h)
    image_preview.allow_tags = True
    image_preview.short_description = 'image'

    @property
    def bg_image_path(self):
        """Return path to the badge's background image."""
        from event.models import Badge as EventBadge
        if self.campaign.is_event:
            return EventBadge.BADGE_BG_IMAGES[self.badge_type]
        return self.BADGE_BG_IMAGES[self.badge_type]


class Stats(models.Model):
    """A model that maintains a campaign's salient statistics."""
    campaign = models.ForeignKey(Campaign, unique=True)
    amount_raised = models.DecimalField(max_digits=10, decimal_places=2, blank=True, help_text=_('This includes on-site contributions as well as redeemed tickets.'))
    amount_raised_online = models.DecimalField(max_digits=10, decimal_places=2, blank=True, help_text=_('This includes on-site contributions but excludes redeemed tickets.'))
    amount_raised_by_tickets = models.DecimalField(max_digits=10, decimal_places=2, blank=True, help_text=_('This includes redeemed tickets but excludes on-site contributions.'))
    num_contributions = models.PositiveIntegerField(default=0, blank=True, help_text=_('This includes on-site contributions as well as redeemed tickets.'))
    num_online_contributions = models.PositiveIntegerField(default=0, blank=True)
    num_tickets_redeemed = models.PositiveIntegerField(default=0, blank=True)
    num_views = models.PositiveIntegerField(default=0, blank=True, db_index=True)
    updated_on = models.DateTimeField(default=datetime.now, blank=True, db_index=True)

    class Meta:
        verbose_name_plural = 'stats'

    def save(self, **kwargs):
        self.updated_on = datetime.now()
        if not self.amount_raised:
            self.amount_raised = 0
        if not self.amount_raised_online:
            self.amount_raised_online = 0
        if not self.amount_raised_by_tickets:
            self.amount_raised_by_tickets = 0
        if not self.num_contributions:
            self.num_contributions = 0
        if not self.num_online_contributions:
            self.num_online_contributions = 0
        if not self.num_tickets_redeemed:
            self.num_tickets_redeemed = 0
        super(Stats, self).save(**kwargs)

    @property
    def views(self):
        return self.num_views


class TicketManager(models.Manager):
    def redeemed(self, **kwargs):
        kwargs.pop('is_redeemed', False)
        return self.filter(is_redeemed=True, **kwargs)

    def unredeemed(self, **kwargs):
        kwargs.pop('is_redeemed', False)
        return self.filter(is_redeemed=False, **kwargs)

    def generate_tickets_for_campaign(self, campaign):
        """Generate tickets for a campaign.

        Take into account tickets that may have already been generated.

        """
        tickets = campaign.ticket_set.all()
        # Create a dictionary of this campaign's existing ticket codes.
        # These codes are the likeliest ones to clash with the ones we
        # are about to generate because their 6 character prefix will be 
        # the same.
        codes = [t.code for t in tickets]
        code_dict = dict(zip(codes, codes))
        target_num = campaign.num_tickets_total - len(tickets)
        generated = []
        prefix = campaign.ticket_prefix
        for i in range(target_num):
            code = make_ticket_code(prefix, code_dict)
            code_dict['code'] = code
            generated.append(code)
        # Now that we have generated codes that are unique within this 
        # campaign's namespace, ensure that the codes are unique within the 
        # entire database.
        while (True): # do until all codes are unique
            # verify that none of the generated codes are already taken
            tickets = self.filter(code__in=generated)
            if tickets: # some codes are already in use
                for t in tickets:
                    generated.remove(t.code) # discard duplicate code
                    code = make_ticket_code(prefix, code_dict) # create a new code
                    generated.append(code)
            else:
                break # done: all codes are unique
        assert target_num == len(generated)
        for code in generated[:target_num]: # create tickets
            ticket = self.create(campaign=campaign,
                                 code=code,
                                 amount=campaign.contribution_amount)
        return target_num


# Make a list of all alphabets and numbers. Excludes zero and the letter O.
# Add each element twice to the list.
_CHAR_LIST = list(string.ascii_uppercase + string.digits)

# Don't use zero, one, and the letters O, I, L as they can be 
# confused for other letters or numbers.
_CHAR_LIST.remove('0')
_CHAR_LIST.remove('1')
_CHAR_LIST.remove('O')
_CHAR_LIST.remove('I') 
_CHAR_LIST.remove('L')
_CHAR_LIST *= 2


def make_ticket_code(prefix, code_dict):
    """Create a ticket code that is not in the provided code dictionary."""
    while (True): # continue until we find a unique code
        letters = random.sample(_CHAR_LIST, 4) # generate 4 random letters
        code = prefix + ''.join(letters) # turn letters to string
        if not code_dict.has_key(code): # code is unique
            return code


class Ticket(models.Model):
    campaign = models.ForeignKey(Campaign)
    code = models.CharField(max_length=12, unique=True, db_index=True)
    amount = models.DecimalField(_('amount'), max_digits=10, decimal_places=2)
    redeemed_by = models.ForeignKey(User, null=True, blank=True)
    redeemed_on = models.DateTimeField(null=True, blank=True)
    is_redeemed = models.BooleanField(blank=True, default=False)
    is_printed = models.BooleanField(blank=True, default=False)
    updated_on = models.DateTimeField(blank=True, default=datetime.now)

    objects = TicketManager()

    def __unicode__(self):
        return u'%s = %.2f - redeemed: %s' % (self.code, self.amount, self.is_redeemed)

    class Meta:
        ordering = ('-redeemed_on', 'campaign')

    def save(self, **kwargs):
        self.updated_on = datetime.now()
        if self.redeemed_by:
            self.is_redeemed = True
        if self.is_redeemed:
            self.is_printed = True
            if not self.redeemed_on:
                self.redeemed_on = datetime.now()
        super(Ticket, self).save(**kwargs)
        if getattr(self, 'just_redeemed', False):
            ActionItem.objects.q_contribution_action(self, 'ack-contribution')

    @property
    @attribute_cache('code_display')
    def code_display(self):
        """Return a user-friendly version of the ticket code in the format AAA-BBB-CCCC."""
        return u'%s-%s-%s' % (self.code[:3], self.code[3:6], self.code[6:])

    def admin_code_display(self):
        return self.code_display
    admin_code_display.short_description = "code"

    @property
    def contributor(self):
        return self.redeemed_by
    
    @property
    def paid_on(self):
        return self.redeemed_on
    
    @property
    def qty(self):
        return 1
    
    @property
    def contrib_type(self):
        return u'Ticket'


class ContributionManager(models.Manager):
    def members(self):
        """Return all contributions made by IR members excluding anonymous contributions."""
        return self.exclude(contributor__username=u'anonymous')


class Contribution(models.Model):
    """Model for an online campaign contribution."""
    PAYMENT_MODE_CHOICES = (('direct', 'Direct'),
                            ('paypal', 'PayPal'),
                            ('google', 'Google Checkout'))
    campaign = models.ForeignKey(Campaign)
    contributor = models.ForeignKey(User)
    amount = models.DecimalField(_('amount'), max_digits=10, decimal_places=2, help_text="This is the net total amount i.e. quantity x per-contribution amount.")
    qty = models.PositiveIntegerField('quantity')
    paid_on = models.DateTimeField(blank=True, default=datetime.now, db_index=True)
    payment_mode = models.CharField(max_length=15, db_index=True, choices=PAYMENT_MODE_CHOICES)
    transaction_id = models.CharField(max_length=100, db_index=True)
    memo = models.CharField(max_length=2000, blank=True)

    objects = ContributionManager()
    
    def __unicode__(self):
        return u'%s, %s, %s' % (self.campaign.pk, self.contributor.username, self.amount)

    class Meta:
        ordering = ('-paid_on',)
        unique_together = (('payment_mode', 'transaction_id'),)

    def save(self, **kwargs):
        if not self.paid_on:
            self.paid_on = datetime.now()
        is_new = not self.pk
        super(Contribution, self).save(**kwargs)
        if is_new:
            ActionItem.objects.q_contribution_action(self, 'ack-contribution')

    @property
    def contrib_type(self):
        return self.get_payment_mode_display()


class PendingContribution(models.Model):
    """Model for a pending online campaign contribution.

    A contribution is pending if an Instant Payment Notification (IPN) has 
    not been received from the payment processor (i.e. PayPal, Google, ...)

    """
    campaign = models.ForeignKey(Campaign)
    contributor = models.ForeignKey(User)
    amount = models.DecimalField(_('amount'), max_digits=10, decimal_places=2)
    qty = models.PositiveIntegerField('quantity')
    paid_on = models.DateTimeField(blank=True, default=datetime.now, db_index=True)
    payment_mode = models.CharField(max_length=15, db_index=True, choices=Contribution.PAYMENT_MODE_CHOICES)

    def __unicode__(self):
        return u'%s, %s, %s' % (self.campaign.pk, self.contributor.username, self.amount)

    class Meta:
        ordering = ('-paid_on',)

    def save(self, **kwargs):
        if not self.paid_on:
            self.paid_on = datetime.now()
        super(PendingContribution, self).save(**kwargs)

    def process_payment_notification(self, transaction_id, memo=''):
        """Move this pending contribution to a paid contribution."""
        contribution = Contribution.objects.create(campaign=self.campaign,
                                                  contributor=self.contributor,
                                                  amount=self.amount,
                                                  qty=self.qty,
                                                  paid_on=self.paid_on,
                                                  payment_mode=self.payment_mode,
                                                  transaction_id=transaction_id,
                                                  memo=memo)
        self.delete()
        return contribution


def recompute_campaign_stats(sender, instance, **kwargs):
    """When a ``Contribution`` or ``Ticket`` object is saved, schedule a recomputation
    of the campaign's statistics.

    """
    if isinstance(instance, (Contribution, Ticket)):
        ActionItem.objects.q_campaign_action(instance.campaign, 'recompute-campaign')

signals.post_save.connect(recompute_campaign_stats, sender=Contribution)
signals.post_save.connect(recompute_campaign_stats, sender=Ticket)


