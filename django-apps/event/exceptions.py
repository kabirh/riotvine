from django.utils.translation import ugettext as _


class EventError(Exception):
    """Base Exception class for the following custom Exceptions."""
    pass


class SoldOutError(EventError):
    def __init__(self, message=None):
        if message is None:
            message = _(u'This event has been sold out! There are no spots available.')
        super(SoldOutError, self).__init__(message)


class FanAlreadyJoinedError(EventError):
    def __init__(self, message=None):
        if message is None:
            message = _(u'You are already attending this event.')
        super(FanAlreadyJoinedError, self).__init__(message)

