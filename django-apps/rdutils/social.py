from django.conf import settings


def save_open_profile(user, open_profile, amqp_headers=None):
    from twitter.models import TwitterProfile
    from registration.utils import copy_avatar_from_url_to_profile, is_sso_email
    if not open_profile:
        return
    p_type = open_profile['profile_type']
    user_profile = user.get_profile()
    if p_type in settings.INSTALLED_APPS:
        if p_type == 'twitter':
            profile = user_profile.twitter_profile
            created = False
            if not profile:
                profile = TwitterProfile(user_profile=user_profile)
                created = True
            profile.created = created
            profile.screen_name = open_profile['screen_name']
            profile.appuser_id = unicode(open_profile['appuser_id'])
            profile.access_token = open_profile['access_token']
            profile.save(amqp_headers=amqp_headers)
            # If user doesn't have a first and last name, set them from the open_profile
            user_changed = False
            if not user.first_name:
                user.first_name = open_profile['first_name']
                user_changed = True
            if not user.last_name:
                user.last_name = open_profile['last_name']
                user_changed = True
            if user_changed:
                user.save()
            if not user_profile.avatar_medium and 'profile_image_url' in open_profile:
                # grab twitter profile image
                url = open_profile['profile_image_url']
                copy_avatar_from_url_to_profile(url, user_profile, commit=True)
            return profile
    return None
