import logging
import os.path
from urllib2 import urlopen, Request, urlparse

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.urlresolvers import resolve, Resolver404
from django.contrib.flatpages.models import FlatPage


_log = logging.getLogger('registration.utils')


def copy_avatar_from_url_to_profile(url, user_profile, commit=True):
    """Download Twitter profile image from URL and associate it with the given user_profile"""
    if url:
        if '_normal.' in url:
            urls = (url.replace('_normal.', '_bigger.'), url)
        else:
            urls = (url,)
        for url in urls:
            try:
                _log.debug("Downloading %s's profile pic from %s", user_profile.username, url)
                filename = os.path.basename(urlparse.urlparse(url).path)
                request = Request(url)
                request.add_header('User-Agent', settings.USER_AGENT)
                response = urlopen(request)
                image_content = ContentFile(response.read())
                response.close()
                user_profile.avatar_image.save("profile_img", image_content, save=commit)
                user_profile._create_resized_images(raw_field=image_content, save=commit)
                _log.debug("%s's profile pic successfully downloaded from %s", user_profile.username.title(), url)
                return True
            except Exception, e:
                _log.exception(e)
    return None


def copy_avatar_from_file_to_profile(filepath, user_profile, commit=True):
    """Read profile image from filepath and associate it with the given user_profile"""
    filename = os.path.basename(filepath)
    f = open(filepath, "rb")
    image_content = ContentFile(f.read())
    f.close()
    user_profile.avatar_image.save("profile_img", image_content, save=commit)
    user_profile._create_resized_images(raw_field=image_content, save=commit)
    _log.debug("%s's profile pic successfully saved", user_profile.username)


def is_sso_email(email):
    return email and email.lower().startswith("sso+") and email.lower().endswith("@riotvine.com")


def is_username_available(username, user_profile=None):
    """Check that ``username`` is not already in use.

    A ``username`` is in use if it's been taken by another user or 
    it's being used internally by this web application.

    Furthermore, ``username`` must resolve to the user's profile view.

    """
    from registration.views import profile_page
    from registration.models import UserProfile
    from twitter.models import TwitterProfile
    url = username
    # Check if this URL maps to internal site features.
    rel_url = '/%s/' % url.lower()
    f = FlatPage.objects.filter(url__iexact=rel_url).count()
    if f > 0: # URL maps to a flatpage.
        return False
    try:
        fn_tuple = resolve(rel_url)
        # Ensure that the url resolves to the user's profile page
        if fn_tuple[0] != profile_page:
            return False
    except Resolver404:
        return False
    # Check if another user has claimed this username.
    q = UserProfile.objects.filter(user__username__iexact=username)
    q2 = UserProfile.objects.filter(sso_username__iexact=username)
    q3 = UserProfile.objects.filter(fb_userid__iexact=username)
    q4 = UserProfile.objects.filter(twitterprofile__screen_name__iexact=username)
    if user_profile:
        q = q.exclude(pk=user_profile.pk)
        q2 = q2.exclude(pk=user_profile.pk)
        q3 = q3.exclude(pk=user_profile.pk)
        q4 = q4.exclude(pk=user_profile.pk)
    if q.count() or q2.count() or q3.count() or q4.count():
        return False
    return True
