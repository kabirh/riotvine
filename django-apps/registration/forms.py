import logging
import os.path
from urllib2 import urlopen, Request, urlparse

from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import force_unicode
from django.utils.html import strip_tags
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.localflavor.us import forms as us_forms
from django.core.files.base import ContentFile
from django import forms

from photo.utils import get_image_aspect, get_image_format
from rdutils.date import get_age
from rdutils.url import POPUP
from rdutils.social import save_open_profile
from captcha import verify
from captcha.fields import CaptchaField
from registration.models import Address, UserProfile, AVATAR_HELP_TEXT
from registration.utils import copy_avatar_from_url_to_profile, is_sso_email, is_username_available


_log = logging.getLogger('registration.forms')

_ACCEPT_EULA_LABEL = _('''
    Accept <a href="/terms-of-use/?popup=y" %s>End User License Agreement&nbsp;&raquo;</a>
''' % POPUP)


class MobileAuthenticationForm(AuthenticationForm):
    def __init__(self, request=None, *args, **kwargs):
        super(MobileAuthenticationForm, self).__init__(request, *args, **kwargs)
        self.fields['username'].widget.input_type = 'email'
        self.fields['username'].widget.attrs.update(dict(autocorrect='off', autocapitalize='off'))

class ActivationForm(forms.Form):
    code = forms.CharField(label=_("Confirmation Code"))
    
    def clean_code(self):
        code = self.cleaned_data["code"]
        profile, message = UserProfile.objects.activate_user(code)
        if not profile:
            raise forms.ValidationError(message)
        self.user_profile = profile
        return code


class SignupStep1Form(forms.Form):
    email = forms.EmailField(label=_("Email address"))
    password1 = forms.CharField(label=_("Password"), widget=forms.PasswordInput, min_length=5)
    password2 = forms.CharField(label=_("Re-enter Password"), widget=forms.PasswordInput, min_length=5)
    has_opted_in = forms.BooleanField(label=_('Receive e-mails with news about %s.' % settings.UI_SETTINGS['UI_SITE_TITLE']), required=False, initial=True)
    
    def __init__(self, *args, **kwargs):
        is_mobile = kwargs.pop("is_mobile", False)
        super(SignupStep1Form, self).__init__(*args, **kwargs)
        if is_mobile:
            del self.fields['has_opted_in']
            self.fields['email'].widget.input_type = 'email'
            self.fields['email'].widget.attrs.update(dict(autocorrect='off', autocapitalize='off'))
    
    def clean_email(self):
        email = self.cleaned_data["email"]
        if email:
            email = email.strip().lower()
        try:
            User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return email
        raise forms.ValidationError(_("A user with that email address already exists."))
    
    def clean_password2(self):
        password1 = self.cleaned_data.get("password1", "")
        password2 = self.cleaned_data["password2"]
        if password1 != password2:
            raise forms.ValidationError(_("The two password fields didn't match."))
        return password2


class AvatarImageCleaner(object):    
    """DRY method to clean profile image field (i.e. avatar image)."""
    def clean_image(self):
        img = self.cleaned_data.get("image", None)
        if img and hasattr(img, 'name'):
            fname, ext = os.path.splitext(img.name)
            if not ext:
                raise forms.ValidationError(_(u'The file you have uploaded does not have an extension. Only JPEG and PNG images with the file extensions .jpeg, .jpg, or .png are accepted.'))
            if not (ext.lower() in ('.jpeg', '.png', '.jpg') and get_image_format(img) in ('JPEG', 'PNG')):
                raise forms.ValidationError(_(u'The file you have uploaded is not an acceptable image. Only JPEG and PNG images are accepted.'))
            if img.size > settings.AVATAR_IMAGE_MAX_SIZE_MB*1000000:
                sz = img.size / 1000000
                raise forms.ValidationError(_(u"The profile image file you have uploaded is too big. Please upload a file under %s MB.") % int(settings.AVATAR_IMAGE_MAX_SIZE_MB))
            if img.size == 0:
                raise forms.ValidationError(_(u"The uploaded profile image file seems to have been corrupted. Please try again."))
        return img


class RegistrationForm(UserCreationForm, AvatarImageCleaner):
    captcha = CaptchaField(label=_('Verification code'))
    email = forms.EmailField(label=_("Email address"))
    image = forms.ImageField(label=_("Profile image"), required=False, help_text=AVATAR_HELP_TEXT)
    has_opted_in = forms.BooleanField(label=_('Receive e-mails with news about %s.' % settings.UI_SETTINGS['UI_SITE_TITLE']), required=False)
    # over13 = forms.BooleanField(label=_("Check this box to certify that you are at least 13 years old."),
    #                error_messages={'required':'You must be at least 13 years old to register at %s.' % settings.UI_SETTINGS['UI_SITE_TITLE']})
    accept_eula = forms.BooleanField(label=_ACCEPT_EULA_LABEL,
                    error_messages={'required':'You must check the box below to accept our End User License Agreement.'})

    def __init__(self, *args, **kwargs):
        self.captcha_answer = kwargs.pop('captcha_answer', None)
        self.open_profile = kwargs.pop('open_profile', None)
        self.sso_profile = None
        session = kwargs.pop("session", None)
        initial = {}
        if self.open_profile:
            # grab initial values from open profile            
            initial['username'] = self.open_profile['screen_name']
            initial['first_name'] = self.open_profile['first_name']
            initial['last_name'] = self.open_profile['last_name']
        if session:
            initial['email'] = session.get('email', u'')
            initial['has_opted_in'] = session.get('has_opted_in', False)                
        kwargs['initial'] = initial
        super(RegistrationForm, self).__init__(*args, **kwargs)
        if self.open_profile:
            del self.fields['captcha'] # no need for a CAPTCHA on OAuthed users
            pimg = self.open_profile.get('profile_image_url', '')
            if pimg:
                pimg = pimg.replace('_normal', '_bigger')
                self.fields['image'].help_text += u'''
                    <p class="twitter_img">
                        <img class="twitter_profile_img" src="%s" width="73" height="73"/>
                        Leave the <em>Profile image</em> field empty
                        to use your profile image from Twitter&nbsp;&mdash;&raquo;
                    </p>
                ''' % pimg
            try:
                self.sso_profile = UserProfile.objects.select_related(
                    'user'
                ).get(is_sso=True, sso_username__iexact=self.open_profile['screen_name'])
            except UserProfile.DoesNotExist:
                self.sso_profile = None

    class Meta(UserCreationForm.Meta):
        fields = ("username", "email")

    def clean_username(self):
        username = self.cleaned_data["username"].strip().lower()
        if not is_username_available(username, user_profile=self.sso_profile):
            raise forms.ValidationError(_("This username is not available."))
        return username

    def clean_email(self):
        email = self.cleaned_data["email"]
        if email:
            email = email.strip().lower()
        try:
            User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return email
        raise forms.ValidationError(_("A user with that email address already exists."))

    def clean_captcha(self):
        raw_answer = self.cleaned_data['captcha']
        if not verify(raw_answer, self.captcha_answer):
            raise forms.ValidationError(_(u'That verification code is incorrect. Please try again.'))
        return ''

    def save(self, commit=True):
        if self.sso_profile:
            self.instance = self.sso_profile.user
        user = super(RegistrationForm, self).save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save() # This generates a default UserProfile instance
            user_profile = UserProfile.objects.get(user=user)
            user_profile.has_opted_in = self.cleaned_data.get('has_opted_in', False)
            user_profile.is_sso = False
            user_profile.is_verified = settings.ACCOUNT_EMAIL_VERIFICATION_DEFAULT
            self.save_profile_image(user_profile, commit=True)
            if self.open_profile:
                save_open_profile(user, self.open_profile)
            user._profile = user_profile
        return user

    def save_profile_image(self, user_profile, commit=True):
        """Save avatar image if one was uploaded.

        If `commit` is True, save the profile instance.

        Return the given user_profile instance.

        """
        avatar_img = self.cleaned_data.get('image', None)
        img_updated = False
        if avatar_img:
            avatar_img_field = user_profile._meta.get_field('avatar_image')
            avatar_img_field.save_form_data(user_profile, avatar_img)
            img_updated = True
        elif self.open_profile and self.open_profile['profile_image_url']:
            # Download and use Twitter profile image
            url = self.open_profile.get('profile_image_url', None)
            copy_avatar_from_url_to_profile(url, user_profile, commit=commit)
            img_updated = True
        if commit:
            user_profile.save()
            if img_updated:
                try:
                    user_profile._create_resized_images(raw_field=None, save=commit)
                except:
                    # retry once
                    try:
                        user_profile._create_resized_images(raw_field=None, save=commit)
                    except Exception, e:
                        _log.warn("User id %s's profile image could not be resized. Removing image.", user_profile.user.username)
                        _log.exception(e)
                        user_profile.avatar_image = None
                        user_profile.avatar = None
                        user_profile.avatar_medium = None
                        super(UserProfile, user_profile).save()
        return user_profile


class UserProfileForm(forms.Form, AvatarImageCleaner):
    """A profile change form"""
    def __init__(self, instance, show_fields=None, optional_fields=None, *args, **kwargs):
        self.instance = instance # an instance of UserProfile
        if show_fields is None:
            show_fields = ['email', 'name', 'phone_number', 'birth_date', 'image'] # 'phone_number', 
        if optional_fields is None:
            optional_fields = ['email', 'name', 'phone_number', 'birth_date', 'image'] # 'phone_number', 
        self.show_fields = show_fields
        self.optional_fields = optional_fields
        super(UserProfileForm, self).__init__(*args, **kwargs)
        
        email = self.instance.user.email.lower()
        is_fb_email = email.endswith('facebook.com')
        default_username = self.instance.user.username
        
        if is_sso_email(email) or is_fb_email:
            default_email = u''
        else:
            default_email = email
            
        if self.instance.is_sso:
            default_username = self.instance.sso_username
        
        if True: # default_email or is_fb_email:
            self.fields['permission'] = forms.CharField(label=_('Who can see my profile'), 
                initial=self.instance.permission,
                widget=forms.Select(choices=UserProfile.PERMISSION_CHOICES),
            )
            self.fields['send_reminders'] = forms.BooleanField(
                    initial=self.instance.send_reminders,
                    label=_("Email me daily reminders of upcoming events I am in for"), required=False)
            self.fields['send_favorites'] = forms.BooleanField(
                    initial=self.instance.send_favorites,
                    label=_("Email me daily reminders of upcoming events my friends are in for"), required=False)
            
        if 'email' in show_fields:
            self.fields['email'] = forms.EmailField(label=_('Email'),
                                                        initial=default_email,
                                                        required='email' not in optional_fields)
            if not self.instance.is_sso and is_fb_email and (self.instance.send_reminders or self.instance.send_favorites):
                self.fields['email'].help_text = u'''Event reminder emails are being sent to your Facebook account.<br/> 
                                                                       Add a different email address above or leave it empty to continue 
                                                                       using your Facebook account.'''
            
        if 'name' in show_fields:
            self.fields['username'] = forms.RegexField(label=_("Username"), max_length=30, regex=r'^\w+$', initial=default_username,
                                            error_message = _("This value must contain only letters, numbers and underscores."), 
                                            min_length=4,
                                            help_text=_(u'Between 4 and 30 alphanumeric characters (letters, digits and underscores).'))

            self.fields['first_name'] = forms.CharField(label=_('First name'), max_length=30,
                                                        initial=self.instance.user.first_name,
                                                        required='name' not in optional_fields)
            self.fields['last_name'] = forms.CharField(label=_('Last name'), max_length=30,
                                                        initial=self.instance.user.last_name,
                                                        required='name' not in optional_fields)

        if 'birth_date' in show_fields:
            self.fields['birth_date'] = forms.DateField(label=_('Date of birth'),
                                                        input_formats=['%m/%d/%Y'],
                                                        error_messages={'invalid':_('Enter a valid date in this format: MM/DD/YYYY.')},
                                                        help_text=_('In the format M/D/YYYY. For example, 8/21/1985.'),
                                                        initial=self.instance.birth_date and self.instance.birth_date.strftime('%m/%d/%Y') or None,
                                                        required='birth_date' not in optional_fields)

        if 'phone_number' in show_fields:
            self.fields['phone_number'] = us_forms.USPhoneNumberField(label=_('Phone number'),
                                                          initial=self.instance.phone_number,
                                                          help_text=_('In the format: xxx-xxx-xxxx.'),
                                                          required='phone_number' not in optional_fields)

        if 'address' in show_fields:
            try:
                adr = self.instance.address
            except Address.DoesNotExist:
                adr = Address()
            self.fields['address1'] = forms.CharField(label=_('Address 1'), initial=adr.address1)
            self.fields['address2'] = forms.CharField(label=_('Address 2'), required=False, initial=adr.address2)
            self.fields['city'] = forms.CharField(label=_('City'), max_length=100, initial=adr.city)
            self.fields['state'] = us_forms.USStateField(label=_('State'),
                                initial=adr.state,
                                widget=us_forms.USStateSelect())
            self.fields['postal_code'] = us_forms.USZipCodeField(label=_('ZIP code'),
                            initial=adr.postal_code,
                            help_text=_('U.S. zip code in the format XXXXX or XXXXX-XXXX.'))
            #self.fields['country'] = forms.CharField(label=_('Country'), max_length=75, initial=adr.country)
            #self.fields['country'].widget.attrs.update({'class':'textInput'})

        if 'image' in show_fields:
            self.fields['image'] = forms.ImageField(label=_("Profile image"), required=False, help_text=AVATAR_HELP_TEXT)
        if 'name' in show_fields:
            self.fields['has_opted_in'] = forms.BooleanField(
                initial=self.instance.has_opted_in,
                label=_('Receive e-mail with news about %s.' % settings.UI_SETTINGS['UI_SITE_TITLE']), required=False)
            
    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if not is_username_available(username.lower(), user_profile=self.instance):
            raise forms.ValidationError(_("This username is not available."))
        return username

    def clean_email(self):
        email = force_unicode(strip_tags(self.cleaned_data['email']))
        if email:
            if User.objects.exclude(pk=self.instance.user.pk).filter(email__iexact=email).count():
                raise forms.ValidationError(_(u"This email address is being used by someone else."))
        return email
    
    def clean_first_name(self):
        return force_unicode(strip_tags(self.cleaned_data['first_name']))

    def clean_last_name(self):
        return force_unicode(strip_tags(self.cleaned_data['last_name']))

    def clean(self):
        dob = self.cleaned_data.get('birth_date', None)
        if dob and get_age(dob) < settings.CAMPAIGN_MIN_AGE_RANGE[0]:
            raise forms.ValidationError(_(u'''We're sorry. Based on the information you have submitted to us, you are ineligible to participate on this site. 
            Please send an email to help@riotvine.com to cancel your account.'''))
        return self.cleaned_data

    def save(self, commit=True):
        show_fields = self.show_fields
        if self.instance.is_sso:
            self.instance.send_reminders = False
            self.instance.send_favorites = False
        else:
            self.instance.send_reminders = self.cleaned_data.get('send_reminders', False)
            self.instance.send_favorites = self.cleaned_data.get('send_favorites', False)
        user_dirty = False
        if 'email' in show_fields:
            email = self.cleaned_data.get('email', '').lower()
            if email:
                self.instance.user.email = email
                self.instance.is_sso = False
                user_dirty = True
        if 'name' in show_fields:
            self.instance.user.username = self.cleaned_data['username']
            self.instance.user.first_name = self.cleaned_data['first_name']
            self.instance.user.last_name = self.cleaned_data['last_name']
            if self.cleaned_data.get('has_opted_in', None) is not None:
                self.instance.has_opted_in = self.cleaned_data.get('has_opted_in', False)
            self.instance.permission = self.cleaned_data['permission']
            user_dirty = True
        if user_dirty and commit:
            self.instance.user.save()
        if 'birth_date' in show_fields:
            self.instance.birth_date = self.cleaned_data['birth_date']
        if 'phone_number' in show_fields:
            self.instance.phone_number = self.cleaned_data['phone_number']
        if 'image' in show_fields:
            avatar_img = self.cleaned_data.get('image', None)
            if avatar_img:
                avatar_img_field = self.instance._meta.get_field('avatar_image')
                avatar_img_field.save_form_data(self.instance, avatar_img)
        if commit:
            self.instance.save()
            if 'image' in show_fields:
                self.instance._create_resized_images(raw_field=None, save=True)
        if 'address' in show_fields:
            adr = Address(user_profile=self.instance)
            adr.address1 = self.cleaned_data['address1']
            adr.address2 = self.cleaned_data.get('address2', '')
            adr.city = self.cleaned_data['city']
            adr.state = self.cleaned_data['state']
            adr.postal_code = self.cleaned_data['postal_code']
            #adr.country = self.cleaned_data['country']
            if commit:
                adr.save()
        return self.instance

