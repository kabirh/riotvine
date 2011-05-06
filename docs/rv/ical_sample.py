import vobject
from django.http import HttpResponse

# ---------------------------------------------

cal = vobject.iCalendar()
cal.add('method').value = 'PUBLISH'  # IE/Outlook needs this
for event in event_list:
    vevent = cal.add('vevent')
    ... # add your event details
icalstream = cal.serialize()
response = HttpResponse(icalstream, mimetype='text/calendar')
response['Filename'] = 'filename.ics'  # IE needs this
response['Content-Disposition'] = 'attachment; filename=filename.ics'

'''
Outlook seems to require three datetime fields for each event: DTSTART, DTEND and DTSTAMP 
(even if you don’t have values for all of them). Other consumers of .ics files do not, and 
what works on Windows with Firefox and Outlook may not with IE and Outlook. But it does 
work if you follow the steps, and vObject makes it much easier.
'''

# ---------------------------------------------------

EVENT_ITEMS = (
    ('uid', 'uid'),
    ('dtstart', 'start'),
    ('dtend', 'end'),
    ('summary', 'summary'),
    ('location', 'location'),
    ('last_modified', 'last_modified'),
    ('created', 'created'),
)

class ICalendarFeed(object):

    def __call__(self, *args, **kwargs):

        cal = vobject.iCalendar()

        for item in self.items():

            event = cal.add('vevent')

            for vkey, key in EVENT_ITEMS:
                value = getattr(self, 'item_'   key)(item)
                if value:
                    event.add(vkey).value = value

        response = HttpResponse(cal.serialize())
        response['Content-Type'] = 'text/calendar'

        return response

    def items(self):
        return []

    def item_uid(self, item):
        pass

    def item_start(self, item):
        pass

    def item_end(self, item):
        pass

    def item_summary(self, item):
        return str(item)

    def item_location(self, item):
        pass

    def item_last_modified(self, item):
        pass

    def item_created(self, item):
        pass
