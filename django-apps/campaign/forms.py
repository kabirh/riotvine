from __future__ import absolute_import
import logging
import os.path
from datetime import date, datetime
from decimal import Decimal as D

from django import forms
from django.db import models
from django.conf import settings
from django.utils.translation import ugettext as _
from django.utils.encoding import force_unicode
from django.utils.html import escape, strip_tags
from django.core.urlresolvers import reverse

from photo.utils import get_image_aspect, get_image_format
from rdutils.site import DISPLAY_SITE_URL
from rdutils.date import get_age
from rdutils.decorators import attribute_cache
from rdutils.text import sanitize_html
from common.forms import ValidatingModelForm
from queue.models import ActionItem
from payment import PaymentProcessor, Payment, TransactionData, PaymentError
from payment.fields import CreditCardField, CreditCardExpiryDateField, CreditCardCCVField
from registration.forms import UserProfileForm
from oembed import utils as oembed_utils
from campaign.exceptions import CampaignError, SoldOutError, OnlineContributionsMaxedOutError, FanContributionsMaxedOutError, FanAlreadyJoinedError
from campaign.utils import make_invoice_num, is_campaign_url_available
from campaign.models import Campaign, CampaignChange, Contribution, PendingContribution, Ticket


_log = logging.getLogger("campaign.forms")


class AdminCampaignForm(ValidatingModelForm):
    class Meta:
        model = Campaign

    def clean_is_approved(self):
        is_approved = self.cleaned_data.get('is_approved', False)
        if is_approved and self.instance.pk and not self.instance.is_submitted:
            raise forms.ValidationError(_(u"The artist hasn't yet submitted this campaign for approval."))
        return is_approved

    def clean_is_homepage_worthy(self):
        is_homepage_worthy = self.cleaned_data.get('is_homepage_worthy', False)
        if is_homepage_worthy and self.instance.pk and not self.instance.is_submitted:
            raise forms.ValidationError(_(u"The artist hasn't yet submitted this campaign for approval."))
        return is_homepage_worthy

    def clean(self):
        if not self.instance.pk:
            raise forms.ValidationError(_(u"A new campaign can't be created from the Admin area. Please use the campaign creation area on the public site instead."))
        return self.cleaned_data


class DeleteCampaignForm(forms.Form):
    delete = forms.BooleanField(label=_("Yes, I am sure I want to delete this campaign."))
    delete.widget.attrs.update({'class':'checkboxInput'})

    def clean_delete(self):
        f = self.cleaned_data.get('delete')
        if not bool(f):
            raise forms.ValidationError(_(u'Please check this box to confirm that you want to delete this campaign.'))
        return f


class RedeemTicketForm(forms.Form):
    """Redeem a campaign ticket based on ticket code."""
    code = forms.CharField(label=_('Ticket code'), max_length=16,
                           help_text=_('The ticket code you wish to redeem.'))
    code.widget.attrs.update({'class':'textInput'})

    def clean_code(self):
        code = self.cleaned_data['code'].strip()
        # A code may have dashes for improved readability.
        # The database stored code always has all its dashes removed.
        # Also, a code is case-insensitive.
        code = code.replace('-', '').upper()
        try:
            Ticket.objects.unredeemed().get(code=code)
        except Ticket.DoesNotExist:
            raise forms.ValidationError(_(u"This ticket code can not be redeemed."))
        return code

    def save(self, user=None, commit=True):
        code = self.cleaned_data['code']
        ticket = Ticket.objects.unredeemed().get(code=code)
        ticket.is_redeemed = True
        ticket.redeemed_on = datetime.now()
        if user:
            ticket.redeemed_by = user
        if commit:
            ticket.save()
        ticket.just_redeemed = True
        return ticket


class _AgeValidatorFormBase(object):
    def __init__(self, min_age):
        self.min_age = min_age

    def clean(self):
        birth_date = self.cleaned_data.get('birth_date', None)
        if birth_date:
            age = get_age(birth_date)
            if age < self.min_age:
                raise forms.ValidationError(_(u"We're sorry. Based on the information you have submitted to us, you are ineligible to participate in this campaign."))
        return self.cleaned_data


class QualificationForm(UserProfileForm, _AgeValidatorFormBase):
    """Collect user profile data required by a campaign."""
    def __init__(self, campaign, user_profile, *args, **kwargs):
        self.campaign = campaign
        self.user_profile = user_profile
        show_fields = ['name'] # Name is always required
        if campaign.min_age:
            show_fields.append('birth_date')
        if campaign.address_required:
            show_fields.append('address')
        if campaign.phone_required:
            show_fields.append('phone_number')
        UserProfileForm.__init__(self, instance=user_profile, show_fields=show_fields, optional_fields=[], *args, **kwargs)
        _AgeValidatorFormBase.__init__(self, int(self.campaign.min_age))
        if user_profile.user.first_name and user_profile.user.last_name:
            self.fields['first_name'].widget = forms.HiddenInput()
            self.fields['last_name'].widget = forms.HiddenInput()
        try:
            del self.fields['has_opted_in']
        except KeyError:
            pass

    def clean(self):
        return _AgeValidatorFormBase.clean(self)


class _ContributionFormBase(QualificationForm):
    """Factor out code that is common to all payment modes."""
    def __init__(self, payment_mode, campaign, user_profile, *args, **kwargs):
        self.payment_mode = payment_mode
        if campaign.is_sold_out:
            raise SoldOutError()
        if campaign.num_online_left == 0:
            raise OnlineContributionsMaxedOutError()
        QualificationForm.__init__(self, campaign, user_profile, *args, **kwargs)
        self.qty_shown = False
        num_left = campaign.num_online_left_for_user(user_profile.user)
        if not campaign.is_free:
            if campaign.max_contributions_per_person > 1:
                if num_left > 1:
                    # Show the ``num_contributions`` field since the user can 
                    # choose how many contributions she wants to make.
                    if campaign.is_event:
                        h = _('You can purchase up to %s tickets at $%.2f per ticket.' % (num_left, campaign.contribution_amount))
                    else:
                        h = _('You can make up to %s contributions at $%.2f per contribution.' % (num_left, campaign.contribution_amount))
                    self.fields['num_contributions'] = forms.IntegerField(label=_('Number of %ss' % campaign.contribution_or_ticket), 
                        min_value=1, max_value=num_left, initial=1,
                        help_text=h)
                    self.fields['num_contributions'].widget.attrs.update({'class':'textInput'})
                    self.qty_shown = True
                elif num_left == 0:
                    raise FanContributionsMaxedOutError()
        else: # free campaign
            if num_left == 0:
                raise FanAlreadyJoinedError()

    @property
    @attribute_cache('qty')
    def qty(self):
        return self.qty_shown and self.cleaned_data.get('num_contributions', 1) or 1

    def save(self, commit=True):
        """Leave contributions pending until we later receive notifications for them."""
        UserProfileForm.save(self, commit=commit)
        c = PendingContribution(campaign=self.campaign,
                         contributor=self.user_profile.user,
                         amount=self.campaign.contribution_amount * self.qty,
                         qty=self.qty,
                         paid_on=datetime.now(),
                         payment_mode=self.payment_mode)
        if (commit):
            c.save()
        return c


class PaypalContributionForm(_ContributionFormBase):
    """Collect payment data and user profile data required by a campaign.

    Payment mode is PayPal.

    """
    def __init__(self, campaign, user_profile, *args, **kwargs):
        _ContributionFormBase.__init__(self, 'paypal', campaign, user_profile, *args, **kwargs)


class GoogleContributionForm(_ContributionFormBase):
    """Collect payment data and user profile data required by a campaign.

    Payment mode is Google Checkout.

    """
    def __init__(self, campaign, user_profile, *args, **kwargs):
        _ContributionFormBase.__init__(self, 'google', campaign, user_profile, *args, **kwargs)


class DirectContributionForm(_ContributionFormBase):
    """Collect payment data and user profile data required by a campaign.

    Payment mode is direct via credit card.

    """
    def __init__(self, campaign, user_profile, *args, **kwargs):
        _ContributionFormBase.__init__(self, 'direct', campaign, user_profile, *args, **kwargs)
        self.payment_processor = None
        self.fields['first_name'].help_text = _('First name')
        self.fields['last_name'].help_text = _('Last name. It may include middle initial and suffix. For example, if your name is John M. Smith Jr., the last name would be entered as "M. Smith Jr."')
        if campaign.address_required or not campaign.is_free:
            self.fields['address1'].help_text = _('The billing address for your credit card.')
        if not campaign.is_free:
            # Add payment fields
            self.fields['cc_num'] = CreditCardField(label=_('Credit Card #'),
                        help_text=_('All major credit cards are supported. To safeguard your privacy, we will discard your credit card information after this transaction has been completed.'))
            if not self.qty_shown:
                h = self.fields['cc_num'].help_text
                self.fields['cc_num'].help_text = ' '.join([h, _('Your credit card will be charged for $%.2f.' % campaign.contribution_amount)])
            self.fields['expiration_date'] = CreditCardExpiryDateField(label=_('Expiration Date'))
            self.fields['ccv'] = CreditCardCCVField(label=_('Verification Code'))

    def clean(self):
        super(DirectContributionForm, self).clean()
        if not self._errors and not self.campaign.is_free:
            #
            # ---- IMPORTANT -----
            #
            # Ideally, we would verify the CC here and post the transaction
            # later in save(). However, there isn't an efficient way to merely
            # verify a credit card without actually posting the CC transaction; 
            # All that the ``CreditCardField`` validates that the CC number 
            # abides by the Luhn-checksum but this could still not be a 
            # legitimately issued CC number.
            #
            # Therefore, post the transaction here and produce validation errors 
            # based on what the transaction processor returns.
            #
            # The end result is that if this method succeeds, the transaction has 
            # already been posted.
            #

            # Save ``UserProfile`` and ``User`` fields to the database
            # because ``TransactionData`` needs to extract the payer's
            # name and address from the user instance.
            UserProfileForm.save(self, commit=True)
            data = TransactionData()
            data.user = self.user_profile.user
            payment = Payment()
            data.payment = payment
            payment.invoice_num = make_invoice_num(self.campaign, data.user)
            payment.total_amount = '%s' % self.campaign.contribution_amount * self.qty
            payment.cc_num = self.cleaned_data['cc_num']
            payment.expiration_date = self.cleaned_data['expiration_date']
            payment.ccv = self.cleaned_data['ccv']
            self.payment_processor = PaymentProcessor()
            extra = dict(x_description=self.campaign.title)
            self.payment_processor.prepare_data(data, extra_dict=extra)
            is_success, code, text = self.payment_processor.process()
            if not is_success:
                raise forms.ValidationError(escape(text))
        return self.cleaned_data

    def save(self, commit=True):
        if not self.campaign.is_free:
            is_success, code, text = self.payment_processor.result
            if not is_success:
                raise PaymentError(_('There was a system error in processing your payment.'))
            amount = D(self.payment_processor.transaction_data.payment.total_amount)
        else:
            amount = 0
        UserProfileForm.save(self, commit=commit)
        if not self.campaign.is_free:
            tx_id = self.payment_processor.transaction_data.payment.invoice_num
        else:
            tx_id = make_invoice_num(self.campaign, self.user_profile.user)
        c = Contribution(campaign=self.campaign,
                         contributor=self.user_profile.user,
                         amount=amount,
                         qty=self.qty,
                         paid_on=datetime.now(),
                         payment_mode='direct',
                         transaction_id=tx_id)
        if commit:
            c.save()
        return c


class RequestTicketsForm(forms.Form):
    num_tickets = forms.IntegerField(label=_('Number of tickets'), min_value=1)
    num_tickets.widget.attrs.update({'class':'textInput'})

    def __init__(self, instance, *args, **kwargs):
        self.campaign_instance = instance
        self.base_fields['num_tickets'].help_text = _('You can request up to %s tickets in this campaign.' % instance.num_online_left)
        self.base_fields['num_tickets'].max_value = instance.num_online_left
        super(RequestTicketsForm, self).__init__(*args, **kwargs)

    def save(self):
        n = self.cleaned_data['num_tickets']
        self.campaign_instance.num_tickets_total += n
        self.campaign_instance.save()
        ActionItem.objects.q_campaign_action(self.campaign_instance, 'generate-tickets', name='%s Campaign tickets requested: ' % n)


def get_campaign_form(request):
    user_profile = request.user.is_authenticated() and request.user.get_profile() or None
    if user_profile and user_profile.is_artist:
        user_url = user_profile.artist.url
    else:
        user_url = 'riotvine-member'

    class CampaignForm(forms.ModelForm):
        def __init__(self, *args, **kwargs):
            super(CampaignForm, self).__init__(*args, **kwargs)
            if 'title' in self.fields:
                self.fields['title'] = forms.RegexField(label=_("Title"), max_length=255, regex=r"""^[a-zA-Z0-9 '.",!?:;\-\(\)]+$""",
                                                        help_text=Campaign.TITLE_HELP,
                                                        error_message=_("The title must consist of English letters, numbers, and punctuation only."))
                self.fields['title'].widget.attrs.update({'class':'textInput'})
                self.fields['url'] = forms.RegexField(label=_('URL'),
                          regex=r"""^[a-zA-Z0-9\-]+$""",
                          max_length=35,
                          help_text=_('''If you enter "pink-floyd" as your url, your campaign's public homepage will be at "%s%s/campaign/pink-floyd". Only English letters, numbers, and dashes are allowed.''' % (DISPLAY_SITE_URL, user_url)))
                self.fields['url'].field_top_html = 'http://illiusrock.com/%s/campaign/' % user_url
                self.fields['url'].widget.attrs.update({'class':'textInput'})
                self.fields['max_contributions'].min_value = settings.CAMPAIGN_MAX_CONTRIBUTORS_MIN_VALUE
                self.fields['max_contributions'].widget.attrs.update({'class':'textInput'})
                self.fields['max_contributions_per_person'].min_value = 1
                self.fields['max_contributions_per_person'].widget.attrs.update({'class':'textInput'})
                self.fields['contribution_amount'].min_value = 0
                self.fields['contribution_amount'].error_messages.update({'invalid':'Enter a number (without the dollar sign.)'})
                self.fields['contribution_amount'].widget.attrs.update({'class':'textInput'})
                self.fields['offering'].widget.attrs.update({'class':'textareaInput htmlEdit', 'rows':20})
                self.fields['start_date'].widget.attrs.update({'class':'textInput dateInput vDateField'})
                self.fields['end_date'].widget.attrs.update({'class':'textInput dateInput vDateField'})
                self.fields['min_age'].required = False
                self.fields['min_age'].min_value = 0
                self.fields['min_age'].max_value = settings.CAMPAIGN_MIN_AGE_RANGE[1]
                self.fields['min_age'].widget.attrs.update({'class':'textInput'})
                self.fields['phone_required'].widget.attrs.update({'class':'checkboxInput'})
                self.fields['address_required'].widget.attrs.update({'class':'checkboxInput'})
                self.fields['fan_note'].widget.attrs.update({'class':'textareaInput'})
            if 'image' in self.fields:
                self.fields['image'].widget.attrs.update({'class':'filebrowserInput'})
                if self.instance.image:
                    _help = unicode(self.fields['image'].help_text) or ''
                    self.fields['image'].help_text = ' '.join([_('Leave this empty if you would like us to use your last uploaded image.'), _help])
                self.fields['embed_service'].widget.attrs.update({'class':'dropdownList'})
                self.fields['embed_url'].widget.attrs.update({'class':'textInput'})
    
        class Meta(object):
            model = Campaign
            exclude = ('artist', 'is_approved', 'approved_on', 'is_deleted', 'is_event',
                       'edited_on', 'is_submitted', 'submitted_on',
                       'is_payout_requested', 'payout_requested_on',
                       'is_homepage_worthy', 'homepage_worthy_on', 
                       'target_amount', 'image_resized', 'image_avatar',
                       'num_tickets_total')
    
        def _media(self):
            _append = "?v=%s" % settings.UI_SETTINGS['UI_JS_VERSION']
            return forms.Media(js=(reverse('catalog_jsi18n') + _append,
                                  settings.ADMIN_MEDIA_PREFIX + 'js/core.js' + _append,
                                  settings.ADMIN_MEDIA_PREFIX + 'js/calendar.js' + _append,
                                  settings.ADMIN_MEDIA_PREFIX + 'js/admin/DateTimeShortcuts.js' + _append,
                                  settings.ADMIN_MEDIA_PREFIX + 'js/urlify.js' + _append,
                                  'ui/js/fckeditor/fckeditor.js' + _append,
                                  'ui/js/campaign.js' + _append))
        media = property(_media)
    
        def clean_url(self):
            url = self.cleaned_data['url'].lower()
            if not is_campaign_url_available(url, getattr(self, 'instance', None)):
                raise forms.ValidationError(_('That url is not available. Please try another.'))
            return url
    
        def clean_min_age(self):
            age = self.cleaned_data.get('min_age', 0)
            if age > 0 and age < settings.CAMPAIGN_MIN_AGE_RANGE[0]:
                raise forms.ValidationError(_(u'The minimum age must be at least %s years, if provided.' % settings.CAMPAIGN_MIN_AGE_RANGE[0]))
            return age
    
        def clean_contribution_amount(self):
            amount = self.cleaned_data['contribution_amount']
            if amount < 0:
                raise forms.ValidationError(_(u'The amount must not be a negative number.'))
            if not amount == 0 and amount < D(settings.CAMPAIGN_CONTRIBUTION_AMOUNT_MIN_VALUE):
                raise forms.ValidationError(_(u'The amount must be either zero for a free campaign or at least $%.2f for a paid campaign.' % settings.CAMPAIGN_CONTRIBUTION_AMOUNT_MIN_VALUE))
            return amount
    
        def clean_max_contributions_per_person(self):
            per_person = self.cleaned_data['max_contributions_per_person']
            total = self.cleaned_data.get('max_contributions', 0)
            if per_person > total:
                raise forms.ValidationError(_(u'This number must not be greater than the maximum number of contributions (%s) allowed in this campaign.' % total))
            return per_person
    
        def clean_image(self):
            img = self.cleaned_data["image"]
            if hasattr(img, 'name'):
                fname, ext = os.path.splitext(img.name)
                if not ext:
                    raise forms.ValidationError(_(u'The file you have uploaded does not have an extension. Only JPEG and PNG images with the file extensions .jpeg, .jpg, or .png are accepted.'))
                if not (ext.lower() in ('.jpeg', '.png', '.jpg') and get_image_format(img) in ('JPEG', 'PNG')):
                    raise forms.ValidationError(_(u'The file you have uploaded is not an acceptable image. Only JPEG and PNG images are accepted.'))
                if img.size > settings.CAMPAIGN_IMAGE_MAX_SIZE_MB*1000000:
                    sz = img.size / 1000000
                    raise forms.ValidationError(_(u"The image file you have uploaded is too big. Please upload a file under %s MB.") % int(settings.CAMPAIGN_IMAGE_MAX_SIZE_MB))
                aspect = get_image_aspect(img)
                if aspect != 'landscape':
                    raise forms.ValidationError(_(u"A %s format image like this one doesn't work well with campaign badges. Please upload a landscape format image (width &gt; height)." % aspect))
            return img
    
        def clean_start_date(self):
            dt = self.cleaned_data["start_date"]
            today = date.today()
            if dt < today:
                raise forms.ValidationError(_(u'The date may not be in the past.'))
            return dt
    
        def clean_end_date(self):
            dt_end = self.cleaned_data["end_date"]
            today = date.today()
            if dt_end < today:
                raise forms.ValidationError(_(u'The end date may not be in the past.'))
            dt_start = self.cleaned_data.get("start_date", None)
            if dt_start:
                if dt_end <= dt_start:
                    raise forms.ValidationError(_(u'The end date must be later than the start date.'))
            return dt_end
    
        def clean_offering(self):
            offering = self.cleaned_data.get("offering", None)
            if offering:
                if not offering.endswith('\n'):
                    offering += '\n'
                offering_stripped = force_unicode(sanitize_html(offering))
                offering = offering_stripped.replace('\r\n', '\n')
            return offering
    
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

    return CampaignForm


def get_campaign_form_main(request):
    CampaignForm = get_campaign_form(request)

    class CampaignFormMain(CampaignForm):
        """This is used by the ``campaign.views.CampaignFormWizard``.
    
        Show all campaign fields except for the image.
    
        """
        class Meta(CampaignForm.Meta):
            exclude = CampaignForm.Meta.exclude + ('image', 'embed_service', 'embed_url')
    return CampaignFormMain


def get_campaign_form_image(request):
    CampaignForm = get_campaign_form(request)

    class CampaignFormImage(CampaignForm):
        """This is used by the ``CampaignFormWizard``.
    
        Show only the campaign image field.
    
        """
        class Meta(CampaignForm.Meta):
            fields = ('image', 'embed_service', 'embed_url')
    
        def _media(self):
            return ''
        media = property(_media)
        
    return CampaignFormImage


def get_campaign_edit_form(campaign, request):
    """Return a custom campaign edit form class based on the status of this campaign.

    If the campaign has already been approved, return a form with stricter validations 
    and a limited number of updatable fields. Otherwise, return the standard `CampaignForm`
    """
    if not campaign.is_approved:
        return get_campaign_form(request)

    class CampaignChangeForm(forms.ModelForm):
        def __init__(self, *args, **kwargs):
            if not campaign.changed_version:
                changed_version = CampaignChange(campaign=campaign)
            else:
                changed_version = campaign.changed_version
            kwargs['instance'] = changed_version
            initial = {}
            # Set initial values from changed version or from campaign
            for fname in CampaignChange.MERGE_FIELDS:
                value = getattr(changed_version, fname) or getattr(campaign, fname)
                if isinstance(value, models.Model):
                    value = value.pk
                initial[fname] = value
            for fname in CampaignChange.BOOLEAN_MERGE_FIELDS:
                changed = getattr(changed_version, fname)
                orig = getattr(campaign, fname)
                initial[fname] = (changed_version.pk and [changed] or [orig])[0]
            kwargs['initial'] = initial
            super(CampaignChangeForm, self).__init__(*args, **kwargs)
            self.fields['title'] = forms.RegexField(label=_("Title"), max_length=255, regex=r"""^[a-zA-Z0-9 '.",!?:;\-\(\)]+$""",
                                                    help_text=Campaign.TITLE_HELP, required=False,
                                                    error_message=_("The title must consist of English letters, numbers, and punctuation only."))
            self.fields['title'].widget.attrs.update({'class':'textInput'})
            self.fields['max_contributions'].min_value = campaign.num_contributions or settings.CAMPAIGN_MAX_CONTRIBUTORS_MIN_VALUE
            self.fields['max_contributions'].widget.attrs.update({'class':'textInput'})
            self.fields['max_contributions_per_person'].min_value = 1
            self.fields['max_contributions_per_person'].widget.attrs.update({'class':'textInput'})
            self.fields['contribution_amount'].min_value = 0
            self.fields['contribution_amount'].error_messages.update({'invalid':'Enter a number (without the dollar sign.)'})
            self.fields['contribution_amount'].widget.attrs.update({'class':'textInput'})
            self.fields['offering'].widget.attrs.update({'class':'textareaInput htmlEdit', 'rows':20})
            self.fields['start_date'].widget.attrs.update({'class':'textInput dateInput vDateField'})
            self.fields['end_date'].widget.attrs.update({'class':'textInput dateInput vDateField'})
            self.fields['min_age'].required = False
            self.fields['min_age'].min_value = 0
            self.fields['min_age'].max_value = settings.CAMPAIGN_MIN_AGE_RANGE[1]
            self.fields['min_age'].widget.attrs.update({'class':'textInput'})
            self.fields['phone_required'].widget.attrs.update({'class':'checkboxInput'})
            self.fields['address_required'].widget.attrs.update({'class':'checkboxInput'})
            self.fields['fan_note'].widget.attrs.update({'class':'textareaInput'})
            self.fields['embed_service'].widget.attrs.update({'class':'dropdownList'})
            self.fields['embed_url'].widget.attrs.update({'class':'textInput'})
            # Disallow editing of inapplicable fields
            if campaign.is_sold_out or campaign.is_complete: 
                # Don't allow contribution related changes
                del self.fields['max_contributions']
                del self.fields['max_contributions_per_person']
                del self.fields['contribution_amount']
            if campaign.amount_raised:
                try:
                    # Disallow contribution amount change
                    del self.fields['contribution_amount']
                except KeyError:
                    pass
            # Remove date fields if dates have passed
            now = date.today()
            if campaign.start_date < now:
                del self.fields['start_date']
            if campaign.end_date < now:
                del self.fields['end_date']
            if not campaign.address_required:
                # Do not allow changing address_required from N to Y
                del self.fields['address_required']
            if not campaign.phone_required:
                # Do not allow changing phone_required from N to Y
                del self.fields['phone_required']

        class Meta(object):
            model = CampaignChange
            exclude = ('is_approved', 'is_submitted', 'submitted_on', 'campaign', 'added_on', 'edited_on')

        def _media(self):
            _append = "?v=%s" % settings.UI_SETTINGS['UI_JS_VERSION']
            return forms.Media(js=(reverse('catalog_jsi18n') + _append,
                                  settings.ADMIN_MEDIA_PREFIX + 'js/core.js' + _append,
                                  settings.ADMIN_MEDIA_PREFIX + 'js/calendar.js' + _append,
                                  settings.ADMIN_MEDIA_PREFIX + 'js/admin/DateTimeShortcuts.js' + _append,
                                  'ui/js/fckeditor/fckeditor.js' + _append,
                                  'ui/js/campaign.js' + _append))
        media = property(_media)

        def clean_min_age(self):
            age = self.cleaned_data.get('min_age', 0)
            if age > 0 and age < settings.CAMPAIGN_MIN_AGE_RANGE[0]:
                raise forms.ValidationError(_(u'The minimum age must be at least %s years, if provided.' % settings.CAMPAIGN_MIN_AGE_RANGE[0]))
            return age

        def clean_contribution_amount(self):
            amount = self.cleaned_data['contribution_amount']
            if amount < 0:
                raise forms.ValidationError(_(u'The amount must not be a negative number.'))
            if not amount == 0 and amount < D(settings.CAMPAIGN_CONTRIBUTION_AMOUNT_MIN_VALUE):
                raise forms.ValidationError(_(u'The amount must be either zero for a free campaign or at least $%.2f for a paid campaign.' % settings.CAMPAIGN_CONTRIBUTION_AMOUNT_MIN_VALUE))
            return amount

        def clean_max_contributions_per_person(self):
            per_person = self.cleaned_data['max_contributions_per_person']
            total = campaign.max_contributions
            if per_person > total:
                raise forms.ValidationError(_(u'This number must not be greater than the maximum number of contributions (%s) allowed in this campaign.' % total))
            return per_person

        def clean_start_date(self):
            dt = self.cleaned_data["start_date"]
            today = date.today()
            if dt < today:
                raise forms.ValidationError(_(u'The date may not be in the past.'))
            return dt

        def clean_end_date(self):
            dt_end = self.cleaned_data["end_date"]
            today = date.today()
            if dt_end < today:
                raise forms.ValidationError(_(u'The end date may not be in the past.'))
            dt_start = self.cleaned_data.get("start_date", None)
            if dt_start:
                if dt_end <= dt_start:
                    raise forms.ValidationError(_(u'The end date must be later than the start date.'))
            return dt_end

        def clean_offering(self):
            offering = self.cleaned_data.get("offering", None)
            if offering:
                if not offering.endswith('\n'):
                    offering += '\n'
                offering_stripped = force_unicode(sanitize_html(offering))
                offering = offering_stripped.replace('\r\n', '\n')
            return offering

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

    return CampaignChangeForm # return dynamically defined form class

