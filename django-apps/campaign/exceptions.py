from django.utils.translation import ugettext as _


class CampaignError(Exception):
    """Base Exception class for the following custom Exceptions."""
    pass


class SoldOutError(CampaignError):
    def __init__(self, message=None):
        if message is None:
            message = _(u'This campaign is closed. There are no spots available.')
        super(SoldOutError, self).__init__(message)


class OnlineContributionsMaxedOutError(CampaignError):
    def __init__(self, message=None):
        if message is None:
            message = _(u'''This campaign's online contribution spots have been sold out.
                            Don't lose heart! You might still be able to contribute to this campaign 
                            at a live show.''')
        super(OnlineContributionsMaxedOutError, self).__init__(message)


class FanContributionsMaxedOutError(CampaignError):
    def __init__(self, message=None):
        if message is None:
            message = _(u'''You have already made the maximum number of contributions 
                            that this campaign allows per person.''')
        super(FanContributionsMaxedOutError, self).__init__(message)


class FanAlreadyJoinedError(FanContributionsMaxedOutError):
    def __init__(self, message=None):
        if message is None:
            message = _(u'You have already joined this free campaign.')
        super(FanAlreadyJoinedError, self).__init__(message)

