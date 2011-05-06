import logging
import csv
from uuid import uuid4
from itertools import chain

from django.conf import settings
from django.http import HttpResponseRedirect, HttpResponse
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.db import transaction
from django.utils import simplejson
from django.utils.translation import ugettext as _
from django.shortcuts import get_object_or_404
from django.contrib.sites.models import Site
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, authenticate, logout, get_backends
from django.contrib.auth.models import User

import captcha
from event.amqp.tasks import build_recommended_events
from common.utils import add_message
from rdutils.email import email_template
from rdutils.render import render_view
from twitter import TwitterAPI
from rdutils.social import save_open_profile
from registration import forms
from registration.utils import copy_avatar_from_url_to_profile, is_sso_email
from registration.models import UserProfile, Friendship, Follower


_log = logging.getLogger('registration.views')


@login_required
def account(request, template='registration/account.html'):
    """Render the admin page for a user account."""
    ctx = {'needs_fbml':True}
    # if request.user_profile.is_sso:
    #    template = 'registration/sso_account.html'
    return render_view(request, template, ctx)


@login_required
@transaction.commit_on_success
def do_friending(request, username):
    profile = get_object_or_404(UserProfile.objects.active(), user__username__iexact=username)
    action = request.POST.get('action', None)
    if request.method != 'POST' or not action:
        return HttpResponseRedirect(profile.get_absolute_url())
    if request.user_profile.pk == profile.pk:
        add_message(request, "Ummm, you just tried to friend yourself. You need to get out more often :)")
        return HttpResponseRedirect(profile.get_absolute_url())
    action = action.lower().strip()
    if action not in ('add to friends', 'remove from friends', 'follow', 'unfollow'):
        return HttpResponseRedirect(profile.get_absolute_url())
    rel_obj, viewer = profile.get_relationship(request.user_profile) # viewer can be 'friend', 'follower', 'followee'
    # rev_obj, rev_viewer = request.user_profile.get_relationship(profile) # reverse relationship
    if action == 'add to friends':
        if viewer == 'friend':
            add_message(request, "You and %s are already friends." % profile.username)
        elif viewer == 'follower':
            add_message(request, "You've already asked to be friends with %s. We are just waiting for %s to confirm your request." % (profile.username, profile.username))
        elif viewer == 'followee':
            Friendship.objects.make_friends(profile, request.user_profile, source='site')
            add_message(request, "You and %s are now friends!" % profile.username)
            _log.info("Friendship established: %s <-> %s", profile.username, request.user_profile.username)
            email_template('%s is your friend!' % request.user_profile.username.title(),
                               'registration/email/new-friend.html',
                               {'user':profile.user, 'user_profile':profile, 'profile2':request.user_profile},
                               to_list=[profile.user.email])
        elif not viewer: # no existing relationship
            Follower.objects.get_or_create(followee=profile, follower=request.user_profile)
            add_message(request, "We've just asked %s to confirm your friend request." % profile.username)
            _log.info("Follower established: %s is followed by %s", profile.username, request.user_profile.username)
            email_template('%s is now following you!' % request.user_profile.username.title(),
                               'registration/email/new-follower.html',
                               {'user':profile.user, 'user_profile':profile, 'profile2':request.user_profile, 'friendship_needed':True},
                               to_list=[profile.user.email])
    elif action == 'remove from friends':
        if viewer != 'friend':
            add_message(request, "You and %s are not friends." % profile.username)
        elif viewer == 'friend' and rel_obj.source == 'twitter':
            add_message(request, "Your friendship with %s was established through Twitter. You will have to unfollow %s on Twitter to unfriend them here." % (profile.username, profile.username))
        else:
            Friendship.objects.disconnect_friends(profile, request.user_profile)
            add_message(request, "You and %s are no longer friends." % profile.username)
    elif action == 'follow':
        if viewer in ('friend', 'follower'):
            add_message(request, "You are already following %s." % profile.username)
        elif viewer == 'followee':
            Friendship.objects.make_friends(profile, request.user_profile, source='site')
            add_message(request, "You and %s are now friends!" % profile.username)
            _log.info("Friendship established: %s <-> %s", profile.username, request.user_profile.username)
            email_template('%s is your friend!' % request.user_profile.username.title(),
                               'registration/email/new-friend.html',
                               {'user':profile.user, 'user_profile':profile, 'profile2':request.user_profile},
                               to_list=[profile.user.email])
        elif not viewer: # no existing relationship
            Follower.objects.get_or_create(followee=profile, follower=request.user_profile)
            add_message(request, "You are now following %s!" % profile.username)
            _log.info("Follower established: %s is followed by %s", profile.username, request.user_profile.username)
            email_template('%s is now following you!' % request.user_profile.username.title(),
                               'registration/email/new-follower.html',
                               {'user':profile.user, 'user_profile':profile, 'profile2':request.user_profile, 'friendship_needed':False},
                               to_list=[profile.user.email])
    elif action == 'unfollow':
        if viewer != 'follower':
            add_message(request, "You don't follow %s." % profile.username)
        else:
            Friendship.objects.disconnect_friends(profile, request.user_profile)
            add_message(request, "You no longer follow %s." % profile.username)    
    build_recommended_events(request.user_profile.pk)
    return HttpResponseRedirect(profile.get_absolute_url())


def profile_page(request, username, template='registration/profile.html'):
    from event.utils import get_feed_signature
    ctx = {'needs_fbml':True}
    ctx['current_site'] = Site.objects.get_current()
    profile = get_object_or_404(UserProfile.objects.active(), user__username__iexact=username)
    ctx['profile'] = profile
    viewer_desc_map = {
        'anonymous':u'',
        'self':u'',
        'logged-in':u"You and %s don't follow each other." % profile.username,
        'friend':u"You and %s are friends." % profile.username,
        'follower':u"You follow %s." % profile.username,
        'followee':u"%s follows you." % profile.username,
    }
    permission = profile.permission #  everyone, only-friends, only-riotvine-users
    rel_obj = None # relationship object i.e. Follower or Friendship
    if request.user.is_authenticated():
        # logged in user
        viewer = 'logged-in' # default to logged in non-friend
        if request.user_profile.pk == profile.pk:
            viewer = 'self'
        else:
            rel_obj, viewer = profile.get_relationship(request.user_profile) # viewer can be 'friend', 'follower', 'followee'
        if not viewer:
            viewer = 'logged-in'
    else:
        viewer = 'anonymous'
    if 'google' in request.META.get("HTTP_USER_AGENT", "").lower():
        ctx['googlebot'] = True
    ctx['restricted'] = False
    ctx['show_friend_action'] = False
    ctx['show_unfriend_action'] = False
    ctx['show_follow_action'] = False  
    ctx['show_unfollow_action'] = False
    if viewer == 'friend':
        if rel_obj.source != 'twitter': # if friendship was not gleaned from Twitter, allow unfriending
            ctx['show_unfriend_action'] = True
    elif viewer == 'follower':
        ctx['show_unfollow_action'] = True
    elif viewer == 'logged-in':
        if permission == 'only-friends':
            ctx['show_friend_action'] = True
        else:
            ctx['show_follow_action'] = True
    elif viewer == 'followee':
        ctx['show_friend_action'] = True
    if permission != 'everyone' and viewer != 'self':
        # restrict profile view based on permissions
        if permission == 'only-friends' and viewer != 'friend':
            ctx['restricted'] = True            
        elif permission == 'only-riotvine-users' and viewer not in ('logged-in', 'friend', 'follower'):
            ctx['restricted'] = True
    ctx['viewer'] = viewer
    ctx['friendships'] = Friendship.objects.get_friendships(profile)
    ctx['followers'] = Follower.objects.get_followers(profile)
    ctx['num_friends'], ctx['num_followers'] = profile.get_friend_follower_count()    
    if not ctx['restricted']:
        # if a viewer got this far, they see everything a friend can see
        from event.models import Event
        events = Event.objects.active().filter(
                Q(creator__pk=profile.pk) |
                Q(attendee__attendee_profile__pk=profile.pk)
        ).distinct().order_by('event_date', 'event_start_time', 'pk')
        if viewer != 'anonymous':
            events = Event.objects.add_is_attending(events, request.user_profile)
        ctx['favorites'] = events
        ctx['show_favorites_feed'] = True
    ctx['show_friends_favorites_feed'] = viewer == 'self'
    ctx["favorites_sig"] = get_feed_signature(profile.pk, "favorites")
    ctx["friends_favorites_sig"] = get_feed_signature(profile.pk, "friends-favorites")
    ctx['viewer_desc'] = viewer_desc_map[viewer]
    return render_view(request, template, ctx)


@transaction.commit_on_success
def signup_step1(request, template='registration/signup_step1.html'):
    """Get email address"""
    if request.user.is_authenticated():
        return HttpResponseRedirect(reverse("account"))
    next = request.REQUEST.get('next', '')
    if request.method == 'POST':
        form = forms.SignupStep1Form(data=request.POST, files=request.FILES, is_mobile=request.mobile)
        if form.is_valid():
            request.session['email'] = form.cleaned_data['email']
            request.session['has_opted_in'] = form.cleaned_data.get('has_opted_in', False)
            request.session['password'] = form.cleaned_data['password1']
            return HttpResponseRedirect("%s?next=%s" % (reverse('signup_step2'), next))
    else:
        form = forms.SignupStep1Form(is_mobile=request.mobile)
    ctx = {'form':form, 'next':next}
    if request.mobile:
        template = "mobile/registration/signup_step1.html"
    return render_view(request, template, ctx)


@transaction.commit_on_success
def signup_step2(request, existing_user=False, template='registration/signup_step2.html'):
    """Show unified signup screen"""
    if request.user.is_authenticated():
        return HttpResponseRedirect(reverse("account"))
    next = request.REQUEST.get('next', '')
    email = request.session.get("email", None)
    if not email and not existing_user:
        return HttpResponseRedirect(reverse("signup") + "?next=" + next)
    request.session.set_test_cookie()
    ctx = {'next':next, 'existing_user':existing_user}
    if request.mobile:
        ctx['next'] = next or u"%s?show_friends=y" % reverse("home")
        if existing_user:
            ctx['form'] = forms.MobileAuthenticationForm(request)
            template = "mobile/registration/login.html"
        else:
            template = "mobile/registration/signup_step2.html"
    return render_view(request, template, ctx)


@transaction.commit_on_success
def register(request, template='registration/registration_form.html', redirect_field_name='next'):
    if request.user.is_authenticated():
        prof = request.user_profile
        u = prof.user
        if prof.is_sso and prof.twitter_profile:
            # populate current open profile into session
            t = prof.twitter_profile
            # get profile image URL from Twitter
            profile_image = ''
            try:
                tw = TwitterAPI()
                twitter_profile = tw.get_profile(t.access_token)
                tw.close()
                if twitter_profile:
                    p = simplejson.loads(twitter_profile)
                    profile_image = p.get('profile_image_url', '')
                    if '/images/default_profile' in profile_image:
                        profile_image = ''
            except Exception, e:
                _log.exception(e)
                # continue without profile image
            open_profile = dict(
                profile_type=u'twitter',
                screen_name=t.screen_name,
                first_name=u.first_name,
                last_name=u.last_name,
                appuser_id=t.appuser_id,
                profile_image_url=profile_image,
                access_token=t.access_token
            )
            # logout(request)
            # request.user_profile = None
            request.session['OPEN_PROFILE'] = open_profile
        else:
            return HttpResponseRedirect(reverse('account'))
    redirect_to = request.REQUEST.get(redirect_field_name, '')
    open_profile = request.session.get('OPEN_PROFILE', None)
    if request.method == 'POST':
        captcha_answer = captcha.get_answer(request)
        form = forms.RegistrationForm(captcha_answer=captcha_answer, data=request.POST, files=request.FILES, open_profile=open_profile, session=request.session)
        if form.is_valid():
            user = form.save()
            try:
                if open_profile:
                    del request.session['OPEN_PROFILE']
            except KeyError:
                pass
            password=form.cleaned_data['password1']
            user = authenticate(username=user.username, password=password)
            user_profile = getattr(user, "_profile", UserProfile.objects.get(user=user))
            login(request, user)
            user.message_set.create(message=_(u'Thank you for signing-up!'))
            _log.info("User registered: %s", user.username)
            email_template('Welcome to %s!' % settings.UI_SETTINGS['UI_SITE_TITLE'],
                               'registration/email/welcome.html',
                               {'user':user, 'user_profile':user_profile, 'password':password},
                               to_list=[user.email])
            if request.session.test_cookie_worked():
                request.session.delete_test_cookie()
            if not redirect_to or '//' in redirect_to or ' ' in redirect_to:
                redirect_to = reverse('list_events')
            try:
                if 'email' in request.session:
                    del request.session['email']
                if 'has_opted_in' in request.session:
                    del request.session['has_opted_in']
            except KeyError:
                pass
            return HttpResponseRedirect(redirect_to)
    else:
        form = forms.RegistrationForm(open_profile=open_profile, session=request.session)
    request.session.set_test_cookie()
    ctx = {'form':form, redirect_field_name:redirect_to}
    return render_view(request, template, ctx)


def registration_complete(request, template='registration/registration_complete.html'):
    return render_view(request, template, {})


@login_required
@transaction.commit_on_success
def update_user_profile(request, template='registration/user_profile_form.html', next=None, redirect_field_name='next'):
    # if request.user_profile.is_sso:
    #    return HttpResponseRedirect(reverse('account'))
    if request.user_profile.is_artist:
        return HttpResponseRedirect(reverse('update_artist_profile'))
    if next is None:
        redirect_to = request.REQUEST.get(redirect_field_name, '')
        if redirect_to:
            next = redirect_to
        else:
            next = reverse('account')
    user_profile = request.user_profile
    fields = None
    optional_fields = None
    if request.POST:
        form = forms.UserProfileForm(data=request.POST, files=request.FILES, instance=user_profile, show_fields=fields, optional_fields=optional_fields)
        if form.is_valid():
            user_profile = form.save()
            request.user.message_set.create(message=_(u'The profile for <em>%s</em> has been updated.' % user_profile.username))
            return HttpResponseRedirect(next)
    else:
        form = forms.UserProfileForm(instance=user_profile, show_fields=fields, optional_fields=optional_fields)
    ctx = {'form':form, 'next':next}
    return render_view(request, template, ctx)


@permission_required('campaign.can_manage_campaigns')
def mailing_list(request):
    """Return CSV mailing list for admin use."""
    content_type = "text/csv; charset=%s" % settings.DEFAULT_CHARSET
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename=mailing_list.csv'
    writer = csv.writer(response)
    r = writer.writerow
    r(['Username', 'First name', 'Last name', 'Email', 'Foursquare', 'Has Opted In', 'Date Joined'])
    q = UserProfile.objects.active().exclude(user__email__istartswith="sso", user__email__iendswith="@riotvine.com")
    profiles = q.filter(has_opted_in=True).order_by('user__username')
    profiles2 = q.exclude(has_opted_in=True).exclude(fsq_userid=u'').order_by('user__username')
    for p in chain(profiles, profiles2):
        date_joined = p.date_joined.strftime("%m/%d/%Y")
        r([p.username.encode("utf-8"), p.first_name.encode("utf-8"), p.last_name.encode("utf-8"), 
            p.email.encode("utf-8"), p.fsq_userid or "", 
            p.has_opted_in and "Y" or "N", 
            date_joined])
    return response


def sso_initiate(request):
    """Initiate Single Sign-On (SSO).

    - Save the HTTP REFERER into user's session (if ``next`` query param is given, use it instead)
    - Redirect to Twitter OAuth with sso_authorized as the "next" parameter

    """
    next = request.REQUEST.get('next', request.META.get('HTTP_REFERER', '/'))
    if not request.user.is_authenticated():
        if not 'SSO_NEXT' in request.session:
            request.session['SSO_NEXT'] = next
        next = reverse("sso_authorized")
    return HttpResponseRedirect(u"%s?next=%s" % (reverse("twitter_authorize"), next))


@transaction.commit_on_success
def sso_authorized(request):
    """Process Single Sign-On (SSO) authorization from Twitter.

    If authorized:
        If account doesn't already exist:
        - Create dummy user account with disabled password ()
        - Create user profile with sso (including avatar image)
        - Save Twitter profile
    - Initiate AMQP tasks for user
    - Log the user in
    - Redirect to saved HTTP_REFERER or ``next`` value from sso_initiate

    """
    from event.amqp.tasks import build_recommended_events
    next = request.session.get('SSO_NEXT', '/')
    if request.user.is_authenticated():
        return HttpResponseRedirect(next)
    if 'OPEN_PROFILE' not in request.session:
        _log.debug("Lost session data during SSO authorization. Retrying.")
        return sso_initiate(request)
    oprofile = request.session['OPEN_PROFILE']
    screen_name = oprofile['screen_name'].lower()
    new_signup = False
    try:
        # Use already created SSO account if one exists
        prof = UserProfile.objects.select_related('user').get(sso_username__iexact=screen_name)
        user = prof.user
    except UserProfile.DoesNotExist:
        try:
            # Use latest existing account if one linked to this twitter screen name exists
            prof = UserProfile.objects.select_related('user').filter(
                twitterprofile__screen_name__iexact=screen_name,
                twitterprofile__pk__isnull=False
            ).order_by("-pk")[:1].get()
            user = prof.user
        except UserProfile.DoesNotExist:
            # Create a new SSO account
            # If screenname is available, use it as username.
            # If not, suffix it with a number and use that.
            new_signup = True
            email = request.session.get("email", None)
            if not email:
                add_message(request, u"Create a new account below in two easy steps before signing in with Twitter.")
                return HttpResponseRedirect(reverse("signup") + "?next=" + next)
            screen_name = screen_name.strip()[:32]
            user = None
            if User.objects.filter(username=screen_name).count():
                screen_name = screen_name[:27] # make room for suffixed digits
                for x in range(2, 100):
                    uname = u"%s%s" % (screen_name, x)
                    if not User.objects.filter(username=uname).count():
                        user = User.objects.create(
                            username=uname,
                            first_name=oprofile['first_name'],
                            last_name=oprofile['last_name'],
                            email=email,
                        )
                        break
            else:
                user = User.objects.create(
                    username=screen_name,
                    first_name=oprofile['first_name'],
                    last_name=oprofile['last_name'],
                    email=email,
                )
            if not user:
                # use a randomly suffixed username
                user = User.objects.create(
                    username=u''.join([screen_name[:25], u'-', uuid4().hex[::6]]),
                    first_name=oprofile['first_name'],
                    last_name=oprofile['last_name'],
                    email=email,
                )
            prof = user.get_profile()
            prof.is_sso = True
            prof.sso_username = screen_name
            prof.send_reminders = False
            prof.send_favorites = False
            prof.save()
    # build AMQP headers so that recommended events are built right after 
    # this user's friendships have been computed
    amqp_headers = {
        'final_reply_to':'signal/signal.events.build_recommended_events',
        'user_profile_id':prof.pk
    }
    save_open_profile(user, oprofile, amqp_headers) # this will also initiate the friendship builder AMQP task
    if not prof.avatar_image:
        url = oprofile.get('profile_image_url', None)
        copy_avatar_from_url_to_profile(url, prof, commit=True)
    # annotate the user object with the path of the backend so that 
    # login() works without a password:
    backend = get_backends()[0] 
    user.backend = "%s.%s" % (backend.__module__, backend.__class__.__name__)
    login(request, user)
    if new_signup:
        user.message_set.create(message=_(u'Thank you for signing-up with Twitter!'))
    _log.debug("SSO user %s logged in" % prof.username)
    return HttpResponseRedirect(next)


@login_required
def friends(request, template='registration/friends.html'):
    """Render a list of this user's friends."""
    ctx = {'needs_fbml':True}
    ctx['friends'] = Friendship.objects.get_friendships(request.user_profile)
    return render_view(request, template, ctx)


@transaction.commit_on_success
def confirm_account(request, user_id=None, code=None, template='registration/confirm_account_form.html'):
    ctx = {}
    next = request.REQUEST.get("next", reverse("list_events"))
    if user_id and code: # user visited the direct confirmation link
        activation_code = u"%s-%s" % (user_id, code)
        profile, mesg = UserProfile.objects.activate_user(activation_code)
        if profile:
            add_message(request, u"Thank you for confirming your email address.")
            if not request.user.is_authenticated():
                user = profile.user
                backend = get_backends()[0] 
                user.backend = "%s.%s" % (backend.__module__, backend.__class__.__name__)
                login(request, user)
            return HttpResponseRedirect(next)
        else:
            add_message(request, mesg)
    if request.method == 'POST': # user has typed in the confirmation code manually
        form = forms.ActivationForm(data=request.POST, files=request.FILES)
        if form.is_valid():
            add_message(request, u"Thank you for confirming your email address.")
            if not request.user.is_authenticated():
                user = form.user_profile.user
                backend = get_backends()[0]
                user.backend = "%s.%s" % (backend.__module__, backend.__class__.__name__)
                login(request, user)
            return HttpResponseRedirect(next)
    else:
        form = forms.ActivationForm()        
    ctx['form'] = form
    ctx['next'] = next
    return render_view(request, template, ctx)

