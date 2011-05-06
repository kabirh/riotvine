import logging

from django.conf import settings
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.db import transaction

from rdutils.url import sanitize_url
from linker.models import WebLink


_log = logging.getLogger('linker.views')


@transaction.commit_on_success
def link_redirect(request, url):
    src_email = 'email' == request.REQUEST.get('src', 'web').lower()
    if src_email:
        n_web, n_email = 0, 1
    else:
        n_web, n_email = 1, 0
    lnk = get_object_or_404(WebLink.objects.exclude(redirect_to=u''), url=url.lower())
    lnk.email_count += n_email
    lnk.web_count += n_web
    lnk.save()
    r = sanitize_url(lnk.redirect_to)
    return HttpResponseRedirect(r)

