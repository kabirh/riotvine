import logging

from django import forms
from django.utils.translation import ugettext as _
from django.contrib.localflavor.us import forms as us_forms
from django.utils.encoding import force_unicode
from django.utils.html import strip_tags
from django.conf import settings
from django.contrib.sites.models import Site
from django.contrib.flatpages.models import FlatPage

from payment.processor import paypal, google
from rdutils.site import DISPLAY_SITE_URL
from registration.forms import RegistrationForm, AvatarImageCleaner, AVATAR_HELP_TEXT
from registration.models import Address
from artist.models import Genre, ArtistProfile, PaymentPaypal, PaymentGoogle
from artist.utils import is_artist_url_available


_log = logging.getLogger('artist.forms')

_GOOGLE_MERCHANT_ID_HELP = _(u"Your Google Checkout Merchant ID if you'd like to receive fan contributions there.")
_GOOGLE_MERCHANT_ID_HELP_WITH_LINKS = _(u'''
%s
<ul>
   <li><a href="%s">Sign-up for a Google Checkout merchant account</a></li>
   <li class="gco-help view-hide">
    <div class="view-hide-cue"><a href="#"><span>View</span> Google Checkout setup instructions&nbsp;&raquo;</a></div>
    <div class="hidden-content flatpage" style="display:none;">%%s</div>
   </li>
</ul>''' % (_GOOGLE_MERCHANT_ID_HELP, settings.GOOGLE_REFERRAL_URL))

_PAYPAL_EMAIL_HELP = _("Your PayPal Business or Premier account email address if you'd like to receive fan contributions there.")
_PAYPAL_EMAIL_HELP_WITH_LINKS = _('''
%s
<ul>
    <li><a href="%s">Sign-up for a PayPal Business or Premier account</a></li>
    <li><a href="%s">Upgrade existing PayPal account to a Business or Premier account</a></li>
</ul>
''' % (_PAYPAL_EMAIL_HELP, settings.PAYPAL_REFERRAL_URL, settings.PAYPAL_REFERRAL_URL))


def get_gco_help(url='/help/artist/gco/instructions/'):
    from django.contrib.markup.templatetags.markup import markdown
    page = Site.objects.get_current().flatpage_set.get(url=url)
    return _GOOGLE_MERCHANT_ID_HELP_WITH_LINKS % unicode(markdown(page.content))


class PaymentValidatorBaseForm(forms.Form):
    """Base form to hold common payment validations."""

    def clean_paypal_email(self):
        email = self.cleaned_data.get('paypal_email', u'')
        if email:
            email = email.lower() # Normalize to lowercase
            # Verify that this paypal account is not already in use.
            p = getattr(self, 'user_profile_instance', None)
            q = PaymentPaypal.objects.filter(paypal_email=email)
            if p:
                q = q.exclude(artist_profile__user_profile=p) # exclude current artist
            if q.count() > 0:
                raise forms.ValidationError(_('This PayPal account is not valid.'))
        if email and not paypal.validate_merchant(email):
            raise forms.ValidationError(_('This is not a valid PayPal account email address.'))
        return email

    def clean_paypal_email2(self):
        email2 = self.cleaned_data.get('paypal_email2', u'')
        email = self.cleaned_data.get('paypal_email', u'')
        if email2 != email:
            raise forms.ValidationError(_('This email address does not match the one you entered above.'))
        return email2

    def clean_google_merchant_id(self):
        m_id = self.cleaned_data.get("google_merchant_id", u'')
        if m_id and len(m_id) < 5:
            raise forms.ValidationError(_('This Merchant ID is invalid.'))
        # Verify that this merchant id is not already in use.
        if m_id:
            p = getattr(self, 'user_profile_instance', None)
            q = PaymentGoogle.objects.filter(google_merchant_id=m_id)
            if p:
                q = q.exclude(artist_profile__user_profile=p) # exclude current artist
            if q.count() > 0:
                raise forms.ValidationError(_('This Google Checkout account is not valid.'))
        return m_id

    def clean_google_merchant_key(self):
        m_key = self.cleaned_data.get("google_merchant_key", u'')
        if m_key and len(m_key) < 5:
            raise forms.ValidationError(_('This Merchant Key is invalid.'))
        m_id = self.cleaned_data.get("google_merchant_id", u'')
        if m_id:
            # A Merchant ID has been provided.
            # Verify that the Merchant Key was also provided.
            if not m_key:
                raise forms.ValidationError(_('This field is required along with the Merchant ID you provided above.'))
        if m_key:
            # A Merchant Key has been provided.
            # Verify that the Merchant ID was also provided.
            if not m_id:
                raise forms.ValidationError(_('A Merchant ID is required above along with this Merchant Key.'))
        if m_id and m_key and not google.validate_merchant(m_id, m_key):
            raise forms.ValidationError(_('The Merchant ID, Merchant Key combination is not valid.'))
        return m_key


class ArtistPaymentSetupForm(PaymentValidatorBaseForm):
    # Payment fields
    paypal_email = forms.EmailField(label=_("PayPal email address"), required=False, help_text=_PAYPAL_EMAIL_HELP_WITH_LINKS)
    paypal_email.widget.attrs.update({'class':'textInput'})
    paypal_email2 = forms.EmailField(label=_("PayPal email address (again)"), required=False, help_text=_("So we can be sure you typed it in correctly."))
    paypal_email2.widget.attrs.update({'class':'textInput'})
    google_merchant_id = forms.CharField(label=_('Google Checkout Merchant ID'), max_length=50, required=False, help_text=u'') # get_gco_help()
    google_merchant_id.widget.attrs.update({'class':'textInput'})
    google_merchant_key = forms.CharField(label=_('Google Checkout Merchant Key'), max_length=50, required=False,
                               help_text=_('Your Google Checkout Merchant Key. Required if Merchant ID is being provided.'))
    google_merchant_key.widget.attrs.update({'class':'textInput'})

    def clean(self):
        """Ensure that either Paypal or Google Checkout info was filled in."""
        if self.cleaned_data.get("paypal_email", False):
            return self.cleaned_data
        if self.cleaned_data.get("google_merchant_id", False):
            return self.cleaned_data
        raise forms.ValidationError(_('Either your PayPal account email address or your Google Checkout merchant information must be provided.'))

    def save(self, artist_profile, commit=True):
        if 'paypal_email' in self.fields:
            paypal_email = self.cleaned_data.get('paypal_email', None)
            if paypal_email:
                payment_paypal = PaymentPaypal(artist_profile=artist_profile)
                payment_paypal.paypal_email = paypal_email
                if commit:
                    payment_paypal.save()
            elif commit and artist_profile.paypal:
                artist_profile.paypal.delete()

        if 'google_merchant_id' in self.fields:
            google_merchant_id = self.cleaned_data.get('google_merchant_id', None)
            google_merchant_key = self.cleaned_data.get('google_merchant_key', None)
            if google_merchant_id:
                payment_google = PaymentGoogle(artist_profile=artist_profile)
                payment_google.google_merchant_id = google_merchant_id
                payment_google.google_merchant_key = google_merchant_key
                if commit:
                    payment_google.save()
            elif commit and artist_profile.google:
                artist_profile.google.delete()
        return artist_profile


#_GENRE_CHOICES = list(Genre.objects.values_list('id', 'name').order_by('name'))
_GENRE_CHOICES = [('music', 'Music')]

class ArtistProfileUpdateForm(ArtistPaymentSetupForm, AvatarImageCleaner):
    """Build an artist profile update form.

    Artist profile requires contact information and 
    band related information. It also requires 
    payment setup information.

    """
    # Artist/Band fields
    name = forms.CharField(label=_('Artist / Band name'), max_length=64)
    name.widget.attrs.update({'class':'textInput'})
    # num_members = forms.IntegerField(label=_('Number of band members'), min_value=1)
    # num_members.widget.attrs.update({'class':'textInput'})
    url = forms.RegexField(label=_('IlliusRock URL'),
                      regex=r"""^[a-zA-Z0-9\-]+$""",
                      max_length=25,
                      help_text=_('If you enter "pink-floyd" as your url, your public homepage will be at "%spink-floyd". Only English letters, numbers, and dashes are allowed.' % DISPLAY_SITE_URL))
    url.widget.attrs.update({'class':'textInput'})
    website = forms.URLField(label=_('Artist / Band website'), required=False,
                      verify_exists=True, max_length=150, help_text=ArtistProfile.WEBSITE_HELP_TEXT)
    website.widget.attrs.update({'class':'textInput'})
    genres = forms.MultipleChoiceField(label=_('Genres'),
        choices=_GENRE_CHOICES,
        help_text=_('Ctrl-click or Option-click if you wish to select multiple genres.'))
    genres.widget.attrs.update({'class':'multiselectInput'})

    # Name and contact fields
    phone_number = us_forms.USPhoneNumberField(label=_('Phone number'), help_text=_('In the format: XXX-XXX-XXXX.'))
    phone_number.widget.attrs.update({'class':'textInput'})
    phone_number.pre_html = _('Please provide contact info for yourself or your band:')
    first_name = forms.CharField(label=_('First name'), max_length=30)
    first_name.widget.attrs.update({'class':'textInput'})
    last_name = forms.CharField(label=_('Last name'), max_length=30)
    last_name.widget.attrs.update({'class':'textInput'})
    address1 = forms.CharField(label=_('Address 1'), required=False)
    address1.widget.attrs.update({'class':'textInput'})
    address2 = forms.CharField(label=_('Address 2'), required=False)
    address2.widget.attrs.update({'class':'textInput'})
    city = forms.CharField(label=_('City'), max_length=100, required=False)
    city.widget.attrs.update({'class':'textInput'})
    state = us_forms.USStateField(label=_('State'), widget=us_forms.USStateSelect(), required=False)
    state.widget.attrs.update({'class':'textInput selectWider'})
    postal_code = us_forms.USZipCodeField(label=_('ZIP code'), required=False,
                    help_text=_('U.S. zip code in the format XXXXX or XXXXX-XXXX.'))
    postal_code.widget.attrs.update({'class':'textInput'})
    image = forms.ImageField(label=_("Profile image"), required=False, help_text=AVATAR_HELP_TEXT)
    image.widget.attrs.update({'class':'filebrowserInput'})
    has_opted_in = forms.BooleanField(label=_('Receive e-mails about upcoming campaigns and news about %s.' % settings.UI_SETTINGS['UI_SITE_TITLE']), required=False)
    has_opted_in.widget.attrs.update({'class':'checkboxInput'})

    class Media:
        _append = "?v=%s" % settings.UI_SETTINGS['UI_JS_VERSION']
        js=(settings.ADMIN_MEDIA_PREFIX + 'js/urlify.js' + _append,)

    def __init__(self, *args, **kwargs):
        user_profile_instance = kwargs.pop('user_profile_instance', None)
        self.user_profile_instance = user_profile_instance
        if not user_profile_instance:
            super(ArtistProfileUpdateForm, self).__init__(*args, **kwargs)
        else:
            # Gather initial values based on existing data.
            artist_profile = self.user_profile_instance.artist
            if artist_profile:
                if artist_profile:
                    initial_genres = [g.id for g in artist_profile.genres.all()]
                else:
                    artist_profile = ArtistProfile()
                    initial_genres = []
            else:
                artist_profile = ArtistProfile()
                initial_genres = []
            try:
                adr = self.user_profile_instance.address
            except Address.DoesNotExist:
                adr = Address()
            # Populate initial values.
            initial = {}      
            initial.update(self.user_profile_instance.user.__dict__)
            initial.update(self.user_profile_instance.__dict__)
            initial.update(adr.__dict__)
            initial.update(artist_profile.__dict__)
            initial['genres'] = initial_genres
            if artist_profile.paypal:
                initial.update(artist_profile.paypal.__dict__)
                initial.update({'paypal_email2':artist_profile.paypal.paypal_email})
            if artist_profile.google:
                initial.update(artist_profile.google.__dict__)
            initial.update(kwargs.pop('initial', {}))
            super(ArtistProfileUpdateForm, self).__init__(initial=initial, *args, **kwargs)
            if artist_profile.paypal:
                self.fields['paypal_email'].help_text = _PAYPAL_EMAIL_HELP_WITH_LINKS
            if artist_profile.google:
                self.fields['google_merchant_id'].help_text = get_gco_help()

    def clean_name(self):
        return force_unicode(strip_tags(self.cleaned_data['name']))

    def clean_first_name(self):
        return force_unicode(strip_tags(self.cleaned_data['first_name']))

    def clean_last_name(self):
        return force_unicode(strip_tags(self.cleaned_data['last_name']))

    def clean_url(self):
        url = self.cleaned_data['url'].lower()
        if not is_artist_url_available(url, getattr(self, 'user_profile_instance', None)):
            raise forms.ValidationError(_('That url is not available. Please try another.'))
        return url

    def save(self, profile=None, commit=True):
        if not profile:
            profile = self.user_profile_instance
        avatar_img = self.cleaned_data.get('image', None)
        if avatar_img:
            avatar_img_field = profile._meta.get_field('avatar_image')
            avatar_img_field.save_form_data(profile, avatar_img)
        artist_profile = self.save_artist_profile(profile, commit=commit)
        ArtistPaymentSetupForm.save(self, artist_profile=artist_profile, commit=commit)
        if avatar_img:
            profile._create_resized_images(raw_field=None, save=commit)
        return artist_profile

    def save_artist_profile(self, profile, commit=True):
        """`profile` is an instance of UserProfile"""
        user = profile.user
        profile.is_artist = True
        profile.phone_number = self.cleaned_data['phone_number']
        if 'has_opted_in' in self.fields:
            profile.has_opted_in = self.cleaned_data.get('has_opted_in', False)
        if commit:
            profile.save()
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
        adr1 = self.cleaned_data.get('address1', '')
        city = self.cleaned_data.get('city', '')
        state = self.cleaned_data.get('state', '')
        postal_code = self.cleaned_data.get('postal_code', '')
        if adr1 and city and state and postal_code:
            adr = Address(user_profile=profile)
            adr.address1 = adr1
            adr.address2 = self.cleaned_data.get('address2', '')
            adr.city = city
            adr.state = state
            adr.postal_code = postal_code
            if commit:
                adr.save()
        artist_profile = ArtistProfile(user_profile=profile)
        artist_profile.name = self.cleaned_data['name']
        artist_profile.num_members = self.cleaned_data.get('num_members', 2)
        artist_profile.url = self.cleaned_data['url']
        artist_profile.website = self.cleaned_data.get('website', None)
        if commit:
            artist_profile.save()
            artist_profile.genres = list(Genre.objects.filter(id__in=self.cleaned_data['genres']))
        return artist_profile


_BaseMetaClassR = type(RegistrationForm)
_BaseMetaClassA = type(ArtistProfileUpdateForm)

class CombinedMetaClass(_BaseMetaClassR, _BaseMetaClassA):
    def __new__(cls, name, bases, attrs):
        return _BaseMetaClassA.__new__(cls, name, bases, attrs)


class ArtistRegistrationForm(RegistrationForm, ArtistProfileUpdateForm):
    """Build a form for artist registration.

    Artist registration requires basic user registration as well as 
    artist profile information.

    =============================================================
    THIS HAS BEEN PHASED OUT IN FAVOR OF THE Wizard* FORMS BELOW.
    =============================================================

    """
    __metaclass__ = CombinedMetaClass

    def __init__(self, *args, **kwargs):
        user_profile_instance = kwargs.pop('user_profile_instance', None)
        captcha_answer = kwargs.pop('captcha_answer', None)
        RegistrationForm.__init__(self, captcha_answer=captcha_answer, *args, **kwargs)
        ArtistProfileUpdateForm.__init__(self, user_profile_instance=user_profile_instance, *args, **kwargs)
        # Move CAPTCHA and EULA fields to the end
        self.fields.keyOrder.remove('captcha')
        self.fields.keyOrder.remove('over13')
        self.fields.keyOrder.remove('accept_eula')
        self.fields.keyOrder.extend(['captcha', 'over13', 'accept_eula'])

    def save(self, commit=True):
        user = RegistrationForm.save(self, commit=commit)
        profile = user.get_profile()
        artist_profile = ArtistProfileUpdateForm.save(self, profile, commit=commit)
        return user


class WizardAccountSetupForm(RegistrationForm):
    """Used by the artist registration wizard (1st step)."""
    title = _("Login Information")

    def __init__(self, *args, **kwargs):
        super(WizardAccountSetupForm, self).__init__(*args, **kwargs)
        del self.fields['captcha']
        del self.fields['image']


class WizardArtistSetupForm(ArtistProfileUpdateForm):
    """Used by the artist registration wizard (2nd step)."""
    title = _("Artist Information")

    def __init__(self, *args, **kwargs):
        super(WizardArtistSetupForm, self).__init__(*args, **kwargs)
        for f in ('address1', 'address2', 'city', 'state', 'postal_code'):
            del self.fields[f]
        del self.fields['paypal_email']
        del self.fields['paypal_email2']
        del self.fields['google_merchant_id']
        del self.fields['google_merchant_key']
        del self.fields['image']
        del self.fields['has_opted_in']

    def clean(self):
        return self.cleaned_data

    def save(self, profile=None, commit=True):
        # `profile` is an instance of registration.UserProfile.
        return self.save_artist_profile(profile, commit=commit)


class WizardPaymentSetupForm(ArtistPaymentSetupForm):
    """Used by the artist registration wizard.

    This form is currently not used.

    """
    title = _("Payment Receiving Options")


class WizardPaypalPaymentSetupForm(ArtistPaymentSetupForm):
    """Used by the artist registration wizard (3rd step)."""
    title = _("Payment Receiving Option: PayPal")

    def __init__(self, *args, **kwargs):
        super(WizardPaypalPaymentSetupForm, self).__init__(*args, **kwargs)
        del self.fields['google_merchant_id']
        del self.fields['google_merchant_key']

    def clean(self):
        return self.cleaned_data


class WizardGooglePaymentSetupForm(ArtistPaymentSetupForm):
    """Used by the artist registration wizard (4th step)."""
    title = _("Payment Receiving Option: Google Checkout")

    def __init__(self, *args, **kwargs):
        super(WizardGooglePaymentSetupForm, self).__init__(*args, **kwargs)
        del self.fields['paypal_email']
        del self.fields['paypal_email2']

    def clean(self):
        return self.cleaned_data


class WizardAvatarImageForm(RegistrationForm):
    """Used by the artist registration wizard (5th step)."""
    title = _("Profile Image")

    def __init__(self, *args, **kwargs):
        super(WizardAvatarImageForm, self).__init__(*args, **kwargs)
        # Delete all but the image fields from the base registration form.
        for k in self.fields.keys():
            if k != 'image':
                del self.fields[k]

    def clean(self):
        return self.cleaned_data

    def save(self, profile, commit=True):
        """Bypass default save method, saving just the image instead.

        `profile` is an instance of `registration.UserProfile`.

        """
        return super(WizardAvatarImageForm, self).save_profile_image(profile, commit)

