import logging

from django.http import HttpResponseRedirect, HttpResponsePermanentRedirect
from django.conf import settings
from django.core.urlresolvers import reverse
from django.db import transaction
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _
from django.shortcuts import get_object_or_404

import captcha
from rdutils.render import render_view
from extensions import formwizard as wizard
from rdutils.email import email_template
from artist import forms, models
from artist.decorators import artist_account_required


_log = logging.getLogger('artist.views')
_ARTIST_REGISTRATION_NEXT = getattr(settings, '_ARTIST_REGISTRATION_NEXT', 'artist_admin')


class ArtistRegistrationFormWizard(wizard.FormWizard):
    """Wizard for artist registration."""

    redirect_field_name='next'
    captcha_answer = None
    captcha_step = 99 # Captcha is no longer used in artist registration
    # payment_step = 2 # Artist can now defer providing payment info

    def __init__(self, form_list=None, request=None):
        if form_list is None:
            form_list = [forms.WizardAccountSetupForm,
                         forms.WizardArtistSetupForm,
                         # forms.WizardPaypalPaymentSetupForm,
                         # forms.WizardGooglePaymentSetupForm,
                         forms.WizardAvatarImageForm]
        super(ArtistRegistrationFormWizard, self).__init__(form_list)

    def get_form(self, step, data=None, files=None):
        """Helper method that returns the Form instance for the given step."""
        form = super(ArtistRegistrationFormWizard, self).get_form(step, data=data, files=files)
        if step == self.captcha_step:
            form.captcha_answer = self.captcha_answer
        return form

    def process_step(self, request, form, step):
        if request.method == 'GET' and step == 0:
            request.session.set_test_cookie()
        redirect_to = request.REQUEST.get(self.redirect_field_name, '')
        self.extra_context.update({'auto_populate_url':True, self.redirect_field_name:redirect_to})
        return super(ArtistRegistrationFormWizard, self).process_step(request, form, step)

    def parse_params(self, request, *args, **kwargs):
        """
        Hook for setting some state, given the request object and whatever
        *args and **kwargs were passed to __call__(), sets some state.

        This is called at the beginning of __call__().
        """
        step = self.determine_step(request, *args, **kwargs)
        if request.method == 'POST' and step == self.captcha_step:
            self.captcha_answer = captcha.get_answer(request)
        return super(ArtistRegistrationFormWizard, self).parse_params(request, *args, **kwargs)

    def get_template(self, step):
        return "artist/artist_registration_wizard.html"

    def __call__(self, request, *args, **kwargs):
        if request.user.is_authenticated():
            return HttpResponseRedirect(reverse(_ARTIST_REGISTRATION_NEXT))
        return super(ArtistRegistrationFormWizard, self).__call__(request, *args, **kwargs)

    @transaction.commit_on_success
    def done(self, request, form_list):
        # account_form, artist_form, paypal_payment_form, google_payment_form, avatar_form = form_list
        account_form, artist_form, avatar_form = form_list

        # If at least one payment form is not filled out,
        # send user back to 1st payment form.
        '''# Payment info collection is now defered.
        if not (paypal_payment_form.cleaned_data.get("paypal_email", False) or \
                google_payment_form.cleaned_data.get("google_merchant_id", False)):
           paypal_payment_form.message = _(u'At least one payment method must be filled in.')
           return self.render(paypal_payment_form, request, self.payment_step)
       '''

        # Save each form.
        user = account_form.save(commit=True)
        artist_profile = artist_form.save(profile=user.get_profile(), commit=True)
        # paypal_payment_form.save(artist_profile=artist_profile, commit=True)
        # google_payment_form.save(artist_profile=artist_profile, commit=True)
        avatar_form.save(profile=user.get_profile(), commit=True)
        _log.info('Artist registered: %s', user.username)
        # Send welcome email.
        email_template('Welcome to %s!' % settings.UI_SETTINGS['UI_SITE_TITLE'], 'artist/email/welcome.txt', {'user':user}, to_list=[user.email])
        # Log user in.
        user = authenticate(username=user.username, password=account_form.cleaned_data['password1'])
        login(request, user)
        user.message_set.create(message=_(u'The account for <em>%s</em> has now been registered. Welcome!' % user.get_profile().artist.name))
        if request.session.test_cookie_worked():
            request.session.delete_test_cookie()
        # Redirect to wherever ``next`` points to or default artist screen.
        redirect_to = request.REQUEST.get(self.redirect_field_name, '')
        if not redirect_to or '//' in redirect_to or ' ' in redirect_to:
            redirect_to = reverse(_ARTIST_REGISTRATION_NEXT)
        return HttpResponseRedirect(redirect_to)


@login_required
def admin(request, template='artist/admin.html'):
    user_profile = request.user.get_profile()
    artist = user_profile.artist
    if not artist:
        return HttpResponseRedirect("/")
    return render_view(request, template, {'artist':artist})


@transaction.commit_on_success
def register(request, template='artist/registration_form.html', redirect_field_name='next'):
    """THIS ARTIST REGISTRATION VIEW IS NO LONGER USED.

    It's been superceded by ArtistRegistrationFormWizard instead.

    """
    if request.user.is_authenticated():
        return HttpResponseRedirect(reverse(_ARTIST_REGISTRATION_NEXT))
    redirect_to = request.REQUEST.get(redirect_field_name, '')
    if request.POST:
        captcha_answer = captcha.get_answer(request)
        form = forms.ArtistRegistrationForm(captcha_answer=captcha_answer, data=request.POST, files=request.FILES)
        if form.is_valid():
            user = form.save()
            user = authenticate(username=user.username, password=form.cleaned_data['password1'])
            login(request, user)
            user.message_set.create(message=_(u'The account for <em>%s</em> has now been registered. Welcome!' % user.get_profile().artist.name))
            _log.info('Artist registered: %s', user.username)
            email_template('Welcome to %s!' % settings.UI_SETTINGS['UI_SITE_TITLE'],
                               'artist/email/welcome.txt',
                               {'user':user}, to_list=[user.email])
            if request.session.test_cookie_worked():
                request.session.delete_test_cookie()
            if not redirect_to or '//' in redirect_to or ' ' in redirect_to:
                redirect_to = reverse(_ARTIST_REGISTRATION_NEXT)
            return HttpResponseRedirect(redirect_to)
    else:
        form = forms.ArtistRegistrationForm()
    request.session.set_test_cookie()
    ctx = {'form':form, 'auto_populate_url':True, redirect_field_name:redirect_to}
    return render_view(request, template, ctx)


@login_required
@transaction.commit_on_success
def update_profile(request, template='artist/profile_form.html', next=None):
    user_profile = request.user.get_profile()
    was_artist = user_profile.is_artist
    ctx = {}
    if request.POST:
        form = forms.ArtistProfileUpdateForm(data=request.POST, files=request.FILES, user_profile_instance=user_profile)
        if form.is_valid():
            artist_profile = form.save()
            request.user.message_set.create(message=_(u'The profile for <em>%s</em> has been updated.' % artist_profile.name))
            if next is None:
                if not was_artist:
                    # This fan account just got converted to an artist account.
                    next = reverse(_ARTIST_REGISTRATION_NEXT)
                else:
                    next = reverse('artist_admin')
            return HttpResponseRedirect(next)
    else:
        form = forms.ArtistProfileUpdateForm(user_profile_instance=user_profile)
    if not user_profile.artist:
        # This fan account is being converted to an artist account.
        # Allow auto population of the URL field
        ctx['auto_populate_url'] = True
    ctx['form'] = form
    return render_view(request, template, ctx)


def home(request, artist_url, template='artist/home.html'):
    url = artist_url.lower() # Artist URLs are case-insensitive
    if url != artist_url:
        return HttpResponsePermanentRedirect('/%s/' % url) # Redirect to normalized lowercased url
    ap = get_object_or_404(models.ArtistProfile, url=url)
    return render_view(request, template, {'artist':ap})

