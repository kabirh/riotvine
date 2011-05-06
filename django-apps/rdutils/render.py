from django.shortcuts import render_to_response
from django.template import RequestContext, loader
from django.core.paginator import Paginator, InvalidPage, EmptyPage


def render_view(request, template_name, context=None):
    """Shortcut to include RequestContext into a view response."""
    return render_to_response(template_name, context, context_instance=RequestContext(request))


def render_to_string(request, template_name, context=None):
    """Shortcut to include RequestContext into a string response."""
    return loader.render_to_string(template_name, context, context_instance=RequestContext(request))


def paginate(request, query, per_page, **kwargs):
    """DRY method to paginate query sets."""
    paginator = Paginator(query, per_page, **kwargs)
    # Make sure page request is an int. If not, deliver first page.
    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1
    # If page request is out of range, deliver last page of results.
    try:
        page = paginator.page(page)
    except (EmptyPage, InvalidPage):
        page = paginator.page(paginator.num_pages)
    return page
