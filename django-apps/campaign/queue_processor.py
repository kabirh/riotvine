"""

ActionItem processors for campaign and contribution related queued actions.

See further documentation of this API in `queue.ActionItemProcessorBase`.

"""

import logging

from django.conf import settings

from rdutils.email import email_template
from queue import ActionItemProcessorBase


_log = logging.getLogger('queue.models')


class CampaignProcessor(ActionItemProcessorBase):
    def generate_tickets(self, campaign):
        if not campaign:
            return True

        from campaign.models import Ticket
        from queue.models import ActionItem

        num = Ticket.objects.generate_tickets_for_campaign(campaign)
        _log.debug("%s tickets generated for campaign (%s)", num, campaign.pk)
        if num > 0:
            # Create an admin action item to remind the administrator to print 
            # and snail-mail out the generated tickets.
            ActionItem.objects.q_admin_action(campaign, 'print-tickets')
            email_template('Campaign tickets requested by %s' % campaign.artist.user_profile.user.username,
                           'campaign/email/request_tickets.txt',
                           {'campaign':campaign, 'num_tickets':num},
                           to_list=settings.CAMPAIGN_APPROVERS)
        return True

    def recompute_campaign(self, campaign):
        if campaign:
            campaign.recompute()
        return True

    def generate_badges(self, campaign):
        if campaign:
             campaign.create_badges()
        return True

    def email_campaign_approval(self, campaign):
        if campaign and campaign.is_approved:
            user = campaign.artist.user_profile.user
            email_template('[%s] Your new campaign is live!' % settings.UI_SETTINGS['UI_SITE_TITLE'],
                           'campaign/email/campaign_approved.txt',
                           {'campaign':campaign, 'user':user},
                           to_list=[user.email])
        return True

    def merge_campaign_edits(self, campaign):
        if not campaign:
            return True
        if campaign.changed_version and campaign.changed_version.is_approved:
            ch = campaign.changed_version
            for fname in ch.MERGE_FIELDS:
                f = getattr(ch, fname)
                if f:
                    setattr(campaign, fname, f)
            for fname in ch.BOOLEAN_MERGE_FIELDS:
                f = getattr(ch, fname)
                setattr(campaign, fname, f) 
            campaign.edited_on = ch.edited_on
            campaign.save()
            ch.delete()
        return True


class ContributionProcessor(ActionItemProcessorBase):
    def ack_contribution(self, contribution_or_ticket):
        """Send an email to the fan who paid in a campaign or redeemed a ticket.

        Don't send email if the campaign owner belongs to the group 'Disable ack email'.

        """
        if not contribution_or_ticket:
            return True
        campaign = contribution_or_ticket.campaign
        disable_ack_email = campaign.owner.groups.filter(name__iexact='disable ack email').count()
        if disable_ack_email:
            return True
        if campaign.is_event:
            return True
        user = contribution_or_ticket.contributor
        if user:
            email_template(u'[%s] Thanks for contributing!' % settings.UI_SETTINGS['UI_SITE_TITLE'],
                           'campaign/email/contribution_thanks.txt',
                           {'campaign':campaign, 'user':user},
                           to_list=[user.email])
            email_template(u'Whoa! Someone just joined your campaign! - [%s]' % settings.UI_SETTINGS['UI_SITE_TITLE'],
                           'campaign/email/contrib_artist.txt',
                           {'campaign':campaign, 'user':user},
                           to_list=[campaign.owner.email])
        return True

