from django.core.urlresolvers import resolve, Resolver404
from django.contrib.flatpages.models import FlatPage
from time import time


def make_invoice_num(campaign, user):
    return '%s-%s-%s' % (campaign.pk, user.pk, int(time()))


def is_campaign_url_available(url, campaign=None):
    """Check that ``url`` is not already in use.

    A ``url`` is in use if it's been taken by another campaign or 
    it's being used internally by this web application.

    Furthermore, ``url`` must resolve to the campaign public page view.

    """
    from campaign.models import Campaign
    from campaign.views import view_seo
    # Check if this URL maps to internal site features.
    rel_url = '/riotvine-member/campaign/%s/' % url.lower()
    f = FlatPage.objects.filter(url__endswith=url.lower()).count()
    if f > 0: # URL maps to a flatpage.
        return False
    try:
        fn_tuple = resolve(rel_url)
        # Ensure that the url resolves to the correct view.
        if fn_tuple[0] != view_seo:
            return False
    except Resolver404:
        return False
    # Check if another campaign has claimed this url.
    q = Campaign.objects.filter(url__iexact=url)
    if campaign and campaign.pk:
        q = q.exclude(pk=campaign.pk)
    match = q.count()
    is_url_available = match == 0
    return is_url_available

