from django import template

from siteconfig.models import SiteConfig


register = template.Library()


@register.simple_tag
def site_config(param):
    """Return configuration parameter value."""
    try:
        c = SiteConfig.objects.get(name=param)
        return c.value
    except SiteConfig.DoesNotExist:
        return ''

