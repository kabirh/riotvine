from django.conf import settings


def facebook(request):
    return {
        'FB_APP_ID':settings.FB_APP_ID,
        'FB_API_KEY':settings.FB_API_KEY
    }

