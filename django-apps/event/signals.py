"""

Custom signals related to events occuring on Campaigns

"""
from django.dispatch import Signal


post_event_approval = Signal()
post_event_deletion = Signal()
post_event_admin_change = Signal()

