from django.conf import settings


def admin_media(request):
    return {'ADMIN_MEDIA_PREFIX':settings.ADMIN_MEDIA_PREFIX}


def ui_vars(request):
    """Add UI-related context variables to the context."""
    return settings.UI_SETTINGS


def hostname_port(request):
    from common.utils import hostname_port as hp
    return {
        'TRUE_HOSTNAME_AND_PORT': hp(),
        'COOKIE_DOMAIN': settings.SESSION_COOKIE_DOMAIN
    }

def extra(request):
    """Add extra context variables to the context."""
    return settings.EXTRA_CONTEXT_SETTINGS


def admin_base(request):
    return {'ADMIN_BASE':settings.ADMIN_BASE}

def user_profile(request):
    # middleware.UserProfileMiddleware sets request.user_profile;
    # just copy it to the context
    return {'user_profile':getattr(request, 'user_profile', None)}


def social(request):
    return settings.SOCIAL_CONTEXT_SETTINGS

def social_user_agent(request):
    ua = request.META.get('HTTP_USER_AGENT', None)
    if ua:
        for a in settings.SOCIAL_USER_AGENTS:
            if a in ua:
                return {'SOCIAL_USER_AGENT':True}
    return {'SOCIAL_USER_AGENT':False}
