"""

Custom signals related to events occuring on Campaigns

"""
from django.dispatch import Signal


post_campaign_approval = Signal()
post_campaign_deletion = Signal()
post_campaign_admin_change = Signal()
