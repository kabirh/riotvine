from common.utils import get_messages


def messages(request):
    """Add app messages to context."""
    ctx = {}
    messages = get_messages(request)
    if messages:
        ctx['mesgs'] = messages
    return ctx

