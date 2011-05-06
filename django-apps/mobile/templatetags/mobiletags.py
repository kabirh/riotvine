from django import template

register = template.Library()

@register.filter
def mobilize_map_url(value, args=None):
    """Return m.google.com version of maps URL"""
    url = value
    # url = value.replace("maps.google.com", 'm.google.com')
    return url # + "&source=mobilesearchapp"
