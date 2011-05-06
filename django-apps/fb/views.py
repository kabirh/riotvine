import logging
from uuid import uuid4
from datetime import datetime

from django.utils.http import urlencode
from django.utils.encoding import iri_to_uri
from django.utils import simplejson as json
from django.conf import settings
from django.http import HttpResponseRedirect, Http404, HttpResponse, HttpResponseForbidden, HttpResponseBadRequest, HttpResponseNotAllowed
from django.core.urlresolvers import reverse
from django.views.decorators.csrf import csrf_view_exempt
from django.db import transaction
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth import login, authenticate, logout, get_backends
from django.shortcuts import get_object_or_404
from django.utils.encoding import smart_str
from django.contrib.auth.models import User
from django.utils.translation import ugettext as _


from common.utils import add_message
from rdutils.render import render_view, paginate, render_to_string
from rdutils.query import get_or_none
from rdutils.cache import shorten_key, cache
from rdutils.text import slugify
from fb.utils import verify_sig, get_user_session, get_mobile_session, get_user_info, get_connected_friends, auto_friend
from registration.models import UserProfile, Friendship, PendingFriendship, FBInvitedUser, FBSuggestedFriends

_log = logging.getLogger('fb.views')


def xd_receiver(request, template='fb/xd_receiver.html'):
    return render_view(request, template, {})


def _logout_redirect(request, next):
    logout(request)
    request.delete_fb_cookies = True
    add_message(request, u"Ooops, your Facebook session has expired. Please sign-in again.")
    return HttpResponseRedirect(next)


def _get_connected_friends(api_key, secret, fb_session_key, fb_uid):
    key = shorten_key(u'fb_friends:%s' % fb_uid)
    all_fb_friends = cache.cache.get(key, None)
    if all_fb_friends is None:
        fb_connected_friends = set([unicode(id) for id in get_connected_friends(api_key, secret, fb_session_key, fb_uid)])
        all_fb_friends = set(UserProfile.objects.active().filter(fb_userid__in=list(fb_connected_friends)).values_list('fb_userid', flat=True))
        cache.cache.set(key, all_fb_friends, 120)
    return all_fb_friends


def get_fb_session(request):
    api_key, secret = settings.FB_API_KEY, settings.FB_SECRET_KEY    
    fb_session_key = request.session.get('fb_session_key', None)
    fb_uid = request.session.get('fb_uid', None)
    fb_session_secret = None
    auth_token = request.REQUEST.get('auth_token', None)
    if not auth_token:
        auth_token = request.session.pop('fb_auth_token', None)    
    if auth_token:
        # get mobile session from auth_token
        # http://wiki.developers.facebook.com/index.php/Authentication_and_Authorization_for_Facebook_for_Mobile_Applications
        fb_uid, fb_session_key, fb_session_secret = get_mobile_session(auth_token, api_key, secret)
    elif api_key in request.COOKIES: # no FB signature
        if not verify_sig(request.COOKIES, api_key, secret):
            return None, None, None
        fb_uid, fb_session_key, fb_session_secret = get_user_session(request.COOKIES, api_key)
        if not fb_uid or not fb_session_key or not fb_session_secret:
            return None, None, None
        dt = datetime.fromtimestamp(float(request.COOKIES[api_key+'_expires']))
        if dt.year > 2009:
            if dt < datetime.now():
                # FB session has expired
                return None, None, None
    return fb_uid, fb_session_key, fb_session_secret


def fb_login_mobile(request):
    """Redirect user to constant auth permission page"""
    from common.utils import hostname_port
    params = dict(
        api_key = settings.FB_API_KEY,
        next_url = reverse("fb_login")[1:], # remove first forward slash
        host = hostname_port(),
    )
    url = u'''http://www.facebook.com/connect/prompt_permissions.php?api_key=%(api_key)s&ext_perm=offline_access&next=http://%(host)s/%(next_url)s&cancel=http://%(host)s/%(next_url)s&display=wap''' %  params
    auth_token = request.REQUEST.get('auth_token', None)
    if auth_token:
        request.session['fb_auth_token'] = auth_token
    return HttpResponseRedirect(url)


@transaction.commit_on_success
def fb_login(request):
    next = request.REQUEST.get("next", "/")
    if request.user.is_authenticated():
        return HttpResponseRedirect(next)
    # if user has an FB Connect session, create account and 
    # log the user in.
    api_key, secret = settings.FB_API_KEY, settings.FB_SECRET_KEY
    fb_uid, fb_session_key, fb_session_secret = get_fb_session(request)
    if not fb_uid:
        return _logout_redirect(request, next)
    # Create account if necessary
    new_signup = True
    try:
        profile = UserProfile.objects.active().filter(fb_userid=fb_uid)[:1].get()
        new_signup = False # account exists; log the user in
        user = profile.user
        if user.email.startswith("sso+fb_"):
            # get FB proxied email and save it under this user's record
            uinfo = get_user_info(api_key, secret, fb_session_key, fb_uid)
            if uinfo:
                name, email = uinfo['name'], uinfo['email']
                if email:
                    user.email = email
                    user.save()
                    profile.is_sso = False
                    profile.send_reminders = True
                    profile.send_favorites = True
                    profile.save()
    except UserProfile.DoesNotExist:
        # create new acount
        new_signup = True
        email = request.session.get("email", None)
        if not email:
            add_message(request, u"Create a new account below in two easy steps before signing in with Facebook.")
            return HttpResponseRedirect(reverse("signup") + "?next=" + next)
        uinfo = get_user_info(api_key, secret, fb_session_key, fb_uid)
        # screen_name, name, email = None, None, None
        screen_name, name = None, None
        if uinfo:
            # name, email = uinfo['name'], uinfo['email']
            name = uinfo['name']
            if name:
                # screen name is firstname followed by last initial; all lowercased
                screen_name = name.lower().strip()
                x = screen_name.split(' ')
                if len(x) > 1:
                    firstname, lastname = x[0], x[1]
                    if lastname:
                        screen_name = firstname + lastname[0]
                    else:
                        screen_name = firstname
                screen_name = slugify(screen_name)[:25]
                unames = list(User.objects.filter(username__istartswith=screen_name).values_list("username", flat=True).order_by("username"))
                unames = set([x.lower() for x in unames])
                if screen_name in unames:
                    # generate a unique screen_name by suffixing it with a number
                    for n in range(2, 1000):
                        s = u"%s%s" % (screen_name, n)
                        if s not in unames:
                            screen_name = s
                            break
        if not screen_name:
            # Use FB User ID as the screen name
            screen_name = fb_uid
        if User.objects.filter(username=screen_name).count():
            # screen name not available. Generate one with a random suffix
            screen_name = u''.join([screen_name.strip()[:25], u'-', uuid4().hex[::6]])
        # create user and profile
        user = User.objects.create(
            username=screen_name,
            first_name='',
            last_name='',
            email=email or u'sso+fb_%s@riotvine.com' % uuid4().hex[::5],
        )
        profile = user.get_profile()
        profile.fb_userid = fb_uid
        profile.is_sso = False
        profile.send_reminders = bool(email)
        profile.send_favorites = bool(email)
        profile.fb_suggested = 0
        profile.save()
    # annotate the user object with the path of the backend so that 
    # login() works without a password:
    backend = get_backends()[0] 
    user.backend = "%s.%s" % (backend.__module__, backend.__class__.__name__)    
    login(request, user)
    if new_signup:
        user.message_set.create(message=_(u'Thank you for signing-up with Facebook!'))
    _log.debug("FB user %s logged in" % profile.username)
    request.user_profile = profile
    request.session['fb_uid'] = fb_uid
    request.session['fb_session_key'] = fb_session_key
    # if this user was invited by any existing users, create a friendship
    inv = FBInvitedUser.objects.select_related('inviter_profile').filter(fb_userid=fb_uid)
    for u in inv:
        inviter = u.inviter_profile
        Friendship.objects.make_friends(inviter, request.user_profile, source='fb')
        u.delete()
    # calculate new suggested friends and add their count to session
    try:
        user_profile = profile
        all_fb_friends = _get_connected_friends(api_key, secret, fb_session_key, fb_uid)
        fb_users = UserProfile.objects.active().exclude(fb_userid=u'')
        app_friends = set(list(fb_users.filter(friends2__user_profile1__pk=user_profile.pk).values_list('fb_userid', flat=True)))
        pending_friends = set(list(fb_users.filter(pending_friends_inviter__invitee_profile__pk=user_profile.pk).values_list('fb_userid', flat=True)))
        invited_friends = set(list(fb_users.filter(pending_friends_invitee__inviter_profile__pk=user_profile.pk).values_list('fb_userid', flat=True)))
        recommended_friends = all_fb_friends.difference(app_friends).difference(pending_friends).difference(invited_friends)
        db_reco, created = FBSuggestedFriends.objects.get_or_create(user_profile=user_profile)
        db_recommended_friends = db_reco.friendset
        new_friends = recommended_friends.difference(db_recommended_friends)
        if new_friends:
            if new_signup and settings.FB_AUTO_FRIEND:
                num_auto_friended = auto_friend(profile, new_friends)
                _log.debug("Auto-friended %s friends of %s", num_auto_friended, profile)
            else:
                request.session['num_fb_new_friends'] = len(new_friends)
    except Exception, e:
        _log.exception(e)
    if request.mobile:
        return HttpResponseRedirect(u"%s?show_friends=y" % reverse("home"))
    if new_signup:
        return HttpResponseRedirect(reverse("fb_manage_friends") + "?auto=y&next=%s" % next)
    return HttpResponseRedirect(next)
 

@transaction.commit_on_success
@login_required
def fb_connect(request):
    """Merge FB session with current profile"""
    next = request.REQUEST.get("next", "/")
    if request.user_profile.fb_userid:
        # User has already connected an FB account
        add_message(request, u"You've already connected a Facebook account.")
        return HttpResponseRedirect(next)
    api_key, secret = settings.FB_API_KEY, settings.FB_SECRET_KEY
    fb_uid, fb_session_key, fb_session_secret = get_fb_session(request)
    if not fb_uid:
        return _logout_redirect(request, next)
    try:
        profile = UserProfile.objects.active().filter(fb_userid=fb_uid)[:1].get()
        add_message(request, u"You've already connected this Facebook account with another RiotVine account.") 
        return HttpResponseRedirect(next)
    except UserProfile.DoesNotExist:
        # save fb id
        profile = request.user_profile
        profile.fb_userid = fb_uid
        profile.is_sso = False
        profile.fb_suggested = 0
        profile.save()    
    request.user_profile = profile
    request.session['fb_uid'] = fb_uid
    # if this user was invited by any existing users, create a friendship
    inv = FBInvitedUser.objects.select_related('inviter_profile').filter(fb_userid=fb_uid)
    for u in inv:
        inviter = u.inviter_profile
        Friendship.objects.make_friends(inviter, request.user_profile, source='fb')
        u.delete()
    # calculate new suggested friends and add their count to session
    try:
        user_profile = profile
        all_fb_friends = _get_connected_friends(api_key, secret, fb_session_key, fb_uid)
        fb_users = UserProfile.objects.active().exclude(fb_userid=u'')
        app_friends = set(list(fb_users.filter(friends2__user_profile1__pk=user_profile.pk).values_list('fb_userid', flat=True)))
        pending_friends = set(list(fb_users.filter(pending_friends_inviter__invitee_profile__pk=user_profile.pk).values_list('fb_userid', flat=True)))
        invited_friends = set(list(fb_users.filter(pending_friends_invitee__inviter_profile__pk=user_profile.pk).values_list('fb_userid', flat=True)))
        recommended_friends = all_fb_friends.difference(app_friends).difference(pending_friends).difference(invited_friends)
        db_reco, created = FBSuggestedFriends.objects.get_or_create(user_profile=user_profile)
        db_recommended_friends = db_reco.friendset
        new_friends = recommended_friends.difference(db_recommended_friends)
        if new_friends:
            if settings.FB_AUTO_FRIEND:
                num_auto_friended = auto_friend(profile, new_friends)
                _log.debug("Auto-friended %s friends of %s", num_auto_friended, profile)
            else:
                request.session['num_fb_new_friends'] = len(new_friends)
    except Exception, e:
        _log.exception(e)
    add_message(request, u"You've connected your Facebook account successfully.")
    return HttpResponseRedirect(next)


@transaction.commit_on_success
@login_required
def manage_friends(request, template='fb/manage_friends.html'):
    """Show current FB friends with checkboxes allowing user to connect/disconnect with their friends.

    The view is divided into these parts:

        * Friends you're sharing events with
        * Suggested Friends
        
    The old view (now defunt) was divided into more granular parts:
        * Users who've shared a friendship with this user (ordered by sharing recency) and are awaiting this user's confirmation (actions: confirm, reject)
        * Users that are friends of this user on FB but not on our site (actions: friend)
        * Users who are already friends of this user (actions: unfriend)
        * Users whom this user has already invited to be friends (actions: cancel invitation)

    """
    next = request.REQUEST.get('next', reverse("fb_manage_friends"))
    user_profile = request.user_profile
    user = user_profile.user
    api_key, secret = settings.FB_API_KEY, settings.FB_SECRET_KEY
    fb_uid, fb_session_key, fb_session_secret = get_fb_session(request)
    if not fb_uid:
        return _logout_redirect(request, next)
    all_fb_friends = _get_connected_friends(api_key, secret, fb_session_key, fb_uid)
    fb_users = UserProfile.objects.active().exclude(fb_userid=u'')
    app_friends = set(list(fb_users.filter(friends2__user_profile1__pk=user_profile.pk).values_list('fb_userid', flat=True)))
    pending_friends = set(list(fb_users.filter(pending_friends_inviter__invitee_profile__pk=user_profile.pk).values_list('fb_userid', flat=True)))
    invited_friends = set(list(fb_users.filter(pending_friends_invitee__inviter_profile__pk=user_profile.pk).values_list('fb_userid', flat=True)))
    recommended_friends = all_fb_friends.difference(app_friends).difference(pending_friends).difference(invited_friends)
    if request.method == 'GET' and request.REQUEST.get("auto", False):
        # if there are no recommended friends, redirect to invite friends
        if not recommended_friends:
            return HttpResponseRedirect(reverse("fb_invite_friends") + "?next=%s" % next)
    db_reco, created = FBSuggestedFriends.objects.get_or_create(user_profile=user_profile)
    db_reco.friendset = recommended_friends
    db_reco.save()
    request.session['num_fb_new_friends']  = 0 # user has seen these friends
    ctx = {
        'needs_fbml':True,
        'next':next,
        # 'pending_friends':pending_friends,
        'recommended_friends':recommended_friends,
        'app_friends':app_friends,
        # 'invited_friends':invited_friends,
    }
    if request.method == 'POST':
        # process form submission
        data = request.POST
        # pends = set(data.getlist('pending'))
        # invs = set(data.getlist('invited'))
        curs = set(data.getlist('current'))
        recos = data.getlist('recommended')
        # Current
        for f in Friendship.objects.select_related('user_profile2').filter(user_profile1__pk=user_profile.pk):
            fb_uid = f.user_profile2.fb_userid
            if not fb_uid:
                continue
            if fb_uid not in app_friends:
                continue
            if fb_uid not in curs: # friendship was unchecked
                Friendship.objects.disconnect_friends(f.user_profile2, user_profile)
        # Recommended
        n = 0
        for profile in UserProfile.objects.active().filter(fb_userid__in=recos):
            fb_uid = profile.fb_userid
            if fb_uid not in recommended_friends:
                continue
            # establish bi-directional friendship immediately
            Friendship.objects.make_friends(user_profile, profile, source='fb')
            n += 1
        if n:
            if n == 1:
                add_message(request, u"You're sharing events with one new friend now.")
            else:
                add_message(request, u"You're sharing events with %s new friends now." % n)
        return HttpResponseRedirect(next)
    return render_view(request, template, ctx)


@login_required
def invite_friends(request, template='fb/invite_friends.html'):
    next = request.REQUEST.get('next', reverse("account"))
    user_profile = request.user_profile
    user = user_profile.user
    api_key, secret = settings.FB_API_KEY, settings.FB_SECRET_KEY
    fb_uid, fb_session_key, fb_session_secret = get_fb_session(request)
    if not fb_uid:
        return _logout_redirect(request, next)
    all_fb_friends = _get_connected_friends(api_key, secret, fb_session_key, fb_uid)
    fr_list = list(all_fb_friends)
    previous = list(user_profile.fbinviteduser_set.values_list("fb_userid", flat=True))
    fr_list.extend(previous)
    exclude_ids = u",".join(fr_list)
    ctx = {
        'next':next,
        'needs_fbml':True,
        'exclude_ids':exclude_ids
    }
    return render_view(request, template, ctx)


@transaction.commit_on_success
@login_required
@csrf_view_exempt
def invited_friends(request):
    """Facebook posts the IDs of invited friends here"""
    next = request.REQUEST.get('next', reverse("account"))
    user_profile = request.user_profile
    if request.method == 'POST':
        data = request.POST
        fr_list = data.getlist("ids[]")
        if fr_list:
            for fb_uid in fr_list:
                FBInvitedUser.objects.get_or_create(
                    inviter_profile=user_profile,
                    fb_userid=unicode(fb_uid)
                )
            n = len(fr_list)
            if n == 1:
                add_message(request, u"You've invited a friend to join %s!" % settings.UI_SETTINGS['UI_SITE_TITLE'])
            else:
                add_message(request, u"You've invited %s friends to join %s!" % (n, settings.UI_SETTINGS['UI_SITE_TITLE']))
    return HttpResponseRedirect(next)

