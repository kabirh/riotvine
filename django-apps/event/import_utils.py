import logging
import os.path
from urllib2 import urlopen, Request, urlparse
from cgi import parse_qs
from time import time, strptime
from datetime import date, datetime, timedelta
from itertools import chain
from collections import defaultdict
from uuid import uuid4

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.urlresolvers import resolve, Resolver404
from django.contrib.flatpages.models import FlatPage
from django.utils import simplejson as json
from django.utils.http import urlencode
from django.db.models import Count
from django.db import transaction, connection

from rdutils.email import email_template
from rdutils.url import download_url
from registration.models import Friendship, UserProfile
from rdutils.text import slugify


_log = logging.getLogger('event.import_utils')

_UI_MEDIA_ROOT = os.path.join(settings.MEDIA_ROOT, settings.UI_ROOT, 'internal')
_DEFAULT_IMAGE = os.path.join(_UI_MEDIA_ROOT, settings.EVENT_BADGE_DEFAULT_IMAGE)


'''
['Aces Lounge|||||03/17/2010|-- no Hyperlink --\n',
 '(222 E 6th St)\xc2\xa0(21+)|||||03/17/2010|-- no Hyperlink --\n',
 '|Camp Lo||Bronx NY|Hip-Hop/Rap|03/17/2010|http://my.sxsw.com/events/eid/6957\n',
 '|Big Sean||Detroit MI|Hip-Hop/Rap|03/17/2010|http://my.sxsw.com/events/eid/6931\n',
 '|Mike Posner||Southfield MI|Pop|03/17/2010|http://my.sxsw.com/events/eid/7199\n',
 '|PRGz||Huntsville AL|Hip-Hop/Rap|03/17/2010|http://my.sxsw.com/events/eid/7269\n',
 '|Shawn Chrystopher||Inglewood CA|Hip-Hop/Rap|03/17/2010|http://my.sxsw.com/events/eid/7315\n',
 '\xe2\x99\xaa|Freddie Gibbs||Gary IN|Hip-Hop/Rap|03/17/2010|http://my.sxsw.com/events/eid/8276\n',
 '|Wale||Washington DC|Hip-Hop/Rap|03/17/2010|http://my.sxsw.com/events/eid/10063\n',
 '|2AM Club||Hollywood CA|R&B|03/17/2010|http://my.sxsw.com/events/eid/8674\n',
 '|Kevin Jack||Austin TX|Hip-Hop/Rap|03/17/2010|http://my.sxsw.com/events/eid/8727\n',
 
 'The Ale House|||||03/17/2010|-- no Hyperlink --\n',
 '(310 E 6th St (Alley Entrance))\xc2\xa0(21+)|||||03/17/2010|-- no Hyperlink --\n',
 '\xe2\x99\xaa|Hilary York|7:00 p.m.|Austin TX|Singer-Songwriter|03/17/2010|http://my.sxsw.com/events/eid/10303\n',
 '\xe2\x99\xaa|Isaac Russell|8:00 p.m.|Provo UT|Singer-Songwriter|03/17/2010|http://my.sxsw.com/events/eid/9737\n',
 '|Nathaniel Rateliff|9:00 p.m.|Denver CO|Folk|03/17/2010|http://my.sxsw.com/events/eid/7218\n',
 '|Anais Mitchell|10:00 p.m.|Marshfield VT|Singer-Songwriter|03/17/2010|http://my.sxsw.com/events/eid/9513\n',
 '\xe2\x99\xaa|Alina Simone|11:00 p.m.|Brooklyn NY|Pop|03/17/2010|http://my.sxsw.com/events/eid/6899\n',
 '\xe2\x99\xaa|Melissa Ferrick|12:00 a.m.|Boston MA|Singer-Songwriter|03/17/2010|http://my.sxsw.com/events/eid/8401\n',
 '|Polly Mackey & the Pleasure Principle|1:00 a.m.|Wrexham UK-WALES|Rock|03/17/2010|http://my.sxsw.com/events/eid/7265\n']
'''    
def import_events(filepath, hashtag=u"#SXSWm #Showcase", location=u'austin', venue_city='Austin', venue_state='TX', venue_zip=u'', event_source='sxsw', geoloc="30.27,-97.74", **kwargs):
    from artist.models import ArtistProfile
    from event.models import Event, Venue
    from lastfm import get_artist
    from lastfm.fetch_events import get_raw_image
    _ARTIST = ArtistProfile.objects.get(url='riotvine-member')
    _DATE_FORMAT = "%m/%d/%Y" # format: 03/17/2010
    f = open(filepath, 'r')
    lines = f.readlines()
    max = len(lines)
    rnum = 0
    while True:
        if rnum >= max:
            break
        r = lines[rnum].strip().split('|')
        print rnum, r
        if r[1] == u'' and r[2] == u'' and r[3] == u'' and r[4] == u'':
            # venue row #1
            if rnum + 1 >= max:
                break
            r2 = lines[rnum+1].strip().split('|')
            if r2[1] == u'' and r2[2] == u'' and r2[3] == u'' and r2[4] == u'':
                # venue row #2
                venue = r[0]                
                venue_address = r2[0].split(')\xc2\xa0(')[0][1:].decode('utf-8')
                querystring = urlencode({'q':u'%s %s, %s %s' % (venue[:25], venue_address, venue_city, venue_state)})
                map_url = u'http://maps.google.com/?%s' % querystring
                vn, created = Venue.objects.get_or_create(
                    name=venue[:255],
                    geo_loc=geoloc,
                    defaults=dict(
                        source='user-entered',
                        address=venue_address[:255],
                        city=venue_city[:255],
                        state=venue_state,
                        zip_code=venue_zip[:12],
                        venue_url=u'',
                        map_url=map_url,
                    )
                )
                rnum += 1 # skip this row next time around
        else:
            # event row
            artist_name = r[1]
            artist_dictionary = get_artist(artist_name)
            bio = artist_dictionary.get('bio', {}).get('summary', u'')
            img = artist_dictionary.get('img', u'')
            event_date = r[5] # MM/DD/YYYY
            dt = strptime(event_date, _DATE_FORMAT)
            event_date = date(*dt[:3])
            event_time = r[2] # HH:MM zz"
            if ':' in event_time:
                if ' ' in event_time:
                    # convert to 24 hour time format
                    t, z = event_time.split(' ')
                    h, m = t.split(':')
                    if 'p' in z.lower() and not event_time.lower() == '12:00 p.m.':                        
                        h = (int(h) + 12) % 24
                        event_time = u"%s:%s" % (h, m)
                    elif event_time.lower() == '12:00 a.m.':
                        event_time = u"00:00"
                        event_date = event_date + timedelta(days=1)
                    else:
                        if int(h) <= 2 or int(h) == 12:
                            if int(h) == 12:
                                t = u"00:%s" % m
                            event_date = event_date + timedelta(days=1)
                        event_time = t
            else:
                event_time = None
            if not event_time:
                event_time = None
            artist_location = r[3]
            headliner = artist_name
            genre = r[4]
            external_url = r[6].strip()
            event_id = external_url.split('/')[-1]
            if 'no hyperlink' in external_url.lower():
                external_url = u''
            genre_tag = genre.replace('/', ' #')
            title = u"%s at %s %s #%s" % (artist_name.decode('utf-8'), vn.name.decode('utf-8'), hashtag, genre_tag)
            Event.objects.filter(ext_event_id=event_id, ext_event_source=event_source).delete()
            ex = Event(
                ext_event_id=event_id,
                ext_event_source=event_source,
                artist=_ARTIST,
                creator=_ARTIST.user_profile,
                description=bio,
                is_submitted=True,
                is_approved=True,
                title=title[:120],
                url=(u"%s-%s" % (slugify(title)[:30], uuid4().hex[::4]))[:35],
                venue=vn,
                event_date=event_date,
                event_start_time=event_time,
                event_timezone=u'',
                hashtag=u'"%s"' % headliner[:200].decode('utf-8') or u'',
                location=location,
                headliner=headliner[:200] or u'',
                artists=u'',
                has_image=bool(img),
            )
            image_content = ContentFile(get_raw_image(img))
            fname, ext = os.path.splitext("default.jpg")
            fname = u'%s%s' % (uuid4().hex[::2], ext)
            ex.image.save(fname, image_content, save=False)
            ex._create_resized_images(raw_field=None, save=False)
            ex.save()
            print ex, ex.ext_event_id        
        rnum += 1
        
'''
["Friday, March 12|03/12/2010|Sapient's The Mix at Six|Six Lounge and The Tap Room||||Map it|Details|http://www.austin360.com/music/sxsw-2010sxsw-2010-side-parties-database-244202.html?appSession=425225488699985&RecordID=245&PageID=3&PrevPageID=2&cpipage=1&CPIsortType=&CPIorderBy=\n",
 'Friday, March 12|03/12/2010|Ning SXSW {RV}IP Lounge and Karaoke|TBA||||Map it|Details|http://www.austin360.com/music/sxsw-2010sxsw-2010-side-parties-database-244202.html?appSession=425225488699985&RecordID=246&PageID=3&PrevPageID=2&cpipage=1&CPIsortType=&CPIorderBy=\n',
 'Friday, March 12|03/12/2010|Hive Awards|Red 7||||Map it|Details|http://www.austin360.com/music/sxsw-2010sxsw-2010-side-parties-database-244202.html?appSession=425225488699985&RecordID=247&PageID=3&PrevPageID=2&cpipage=1&CPIsortType=&CPIorderBy=\n',
 'Friday, March 12|03/12/2010|Nokia SXSW Party Posse|Moonshine||Yes|Yes|Map it|Details|http://www.austin360.com/music/sxsw-2010sxsw-2010-side-parties-database-244202.html?appSession=425225488699985&RecordID=373&PageID=3&PrevPageID=2&cpipage=1&CPIsortType=&CPIorderBy=\n',
 'Friday, March 12|03/12/2010|Austinist / WOXY SXSW Day Party|Mohawk|Toro Y Moi, and more to come.|||Map it|Details|http://www.austin360.com/music/sxsw-2010sxsw-2010-side-parties-database-244202.html?appSession=425225488699985&RecordID=279&PageID=3&PrevPageID=2&cpipage=1&CPIsortType=&CPIorderBy=\n']
'''
def import_parties(filepath, hashtag, location=u'austin', venue_city='Austin', venue_state='TX', venue_zip=u'', event_source='sxsw-party', geoloc="30.27,-97.74", **kwargs):
    from artist.models import ArtistProfile
    from event.models import Event, Venue
    from lastfm import get_artist
    from lastfm.fetch_events import get_raw_image
    parent, filename = os.path.split(_DEFAULT_IMAGE)
    party_images = {
        '#SXSWi #Party'.lower():os.path.join(parent, "sxswi_party.jpg"),
        '#SXSWm #Party'.lower():os.path.join(parent, "sxswm_party.jpg"),
    }
    _ARTIST = ArtistProfile.objects.get(url='riotvine-member')
    _DATE_FORMAT = "%m/%d/%Y" # format: 03/17/2010
    f = open(filepath, 'r')
    f.readline() # skip first line -- Date|Actual Date|Event|Venue|Band|Free|Free Drinks|Map|Details|Link|
    lines = f.readlines()
    max = len(lines)
    rnum = 0
    img = party_images.get(hashtag.lower(), None)
    has_image = True
    if not img:
        has_image = False
        img = _DEFAULT_IMAGE
    f = open(img, "rb")
    raw_image_contents = f.read()
    f.close()
    while True:
        if rnum >= max:
            break
        r = lines[rnum].strip().split('|')
        print rnum, r       
        venue = r[3].strip().decode("utf-8").strip()         
        venue_address = u''
        querystring = urlencode({'q':u'"%s" %s, %s %s' % (venue[:25], venue_address, venue_city, venue_state)})
        map_url = u'http://maps.google.com/?%s' % querystring
        vn, created = Venue.objects.get_or_create(
            name=venue[:255],
            geo_loc=geoloc,
            defaults=dict(
                source='user-entered',
                address=venue_address[:255],
                city=venue_city[:255],
                state=venue_state,
                zip_code=venue_zip[:12],
                venue_url=u'',
                map_url=map_url,
            )
        )
        event_name = r[2]
        event_date = r[1] # MM/DD/YYYY
        if 'err' in event_date.lower():
            rnum += 1
            continue
        dt = strptime(event_date, _DATE_FORMAT)
        event_date = date(*dt[:3])
        event_time = None        
        headliner = u''
        is_free = r[5] and "y" in r[5].lower()
        free_drinks = r[6] and "y" in r[6].lower()
        band = r[4]
        description = u""
        if band and 'tba' not in band.lower():
            description = u'<p class="band party party-band">%s</p>' % band.decode("utf-8")
        if free_drinks:
            description = description + u"\n<p><strong>Free Drinks!</strong></p>\n"
        external_url = r[9].strip()
        if 'no hyperlink' in external_url.lower():
            external_url = u''
            event_id = u''
        else:            
            x = urlparse.urlsplit(external_url)
            qx = x.query
            qx_dict = parse_qs(qx)
            qx_dict.pop("appSession", None) # remove session id from URL to make it work
            event_id = qx_dict.get("RecordID")[0]
            new_dict = {}
            for k, v in qx_dict.iteritems():
                new_dict[k]=v[0]
            qx = urlencode(new_dict)
            external_url = urlparse.urlunsplit((x.scheme, x.netloc, x.path, qx, x.fragment))
            description = description + u'\n<p><a href="%s">More details&nbsp;&raquo;</a></p>\n' % external_url            
        title = u"%s at %s %s" % (event_name.decode('utf-8'), vn.name.decode('utf-8'), hashtag)        
        Event.objects.filter(ext_event_id=event_id, ext_event_source=event_source).delete()        
        ex = Event(
            ext_event_id=event_id,
            ext_event_source=event_source,
            artist=_ARTIST,
            creator=_ARTIST.user_profile,
            description=description,
            is_submitted=True,
            is_approved=True,
            is_free=is_free,
            title=title[:120],
            url=(u"%s-%s" % (slugify(title)[:30], uuid4().hex[::4]))[:35],
            venue=vn,
            event_date=event_date,
            event_start_time=event_time,
            event_timezone=u'',
            hashtag=u'',
            location=location,
            headliner=u'',
            artists=u'',
            has_image=has_image,
        )
        image_content = ContentFile(raw_image_contents)
        fname, ext = os.path.splitext("default.jpg")
        fname = u'%s%s' % (uuid4().hex[::2], ext)
        ex.image.save(fname, image_content, save=False)
        ex._create_resized_images(raw_field=None, save=False)
        ex.save()
        print ex, ex.ext_event_id        
        rnum += 1


def fix_mlb_images(metapath, event_source='mlb2010', geo_loc="42.63699,-71.549835", limit=100000, rename_users=True, **kwargs):
    import csv
    import Image, ImageFont, ImageDraw
    from django.contrib.auth.models import User
    from django.db.models import signals
    from artist.models import ArtistProfile
    from event.models import Event, Venue, Attendee, Stats, recompute_event_stats
    from rdutils.image import get_raw_png_image, resize_in_memory, get_perfect_fit_resize_crop, remove_model_image, close, get_raw_image, str_to_file
    from registration.utils import copy_avatar_from_file_to_profile
    
    signals.post_save.disconnect(recompute_event_stats, sender=Attendee)
    signals.post_delete.disconnect(recompute_event_stats, sender=Attendee)
       
    parent, filename = os.path.split(_DEFAULT_IMAGE)
    eventimgpath = os.path.join(parent, "baseball/")
    
    if rename_users:
        # load team meta info    
        reader = csv.reader(open(metapath, "rb"))    
        for row in reader:
            print row
            username = row[6].strip().replace(' ', '')
            team_name = row[0].strip()
            hashtags = ", ".join(row[5].strip().split("~"))
            tz = row[7].strip()        
            # create user
            try:
                a = User.objects.get(username=username)
                a.password = 'NOPASSWORD'
                a.username = team_name.lower().replace(' ', '')
                a.save()
                print "Renamed %s to %s" % (username, a.username)        
            except User.DoesNotExist:
                print "User not renamed: %s" % username

    description = u'''
        <p class="mlb2010">
            <a href="/sports/baseball/2010/">Baseball 2010&nbsp;&raquo;</a>
        </p>
    '''
    games = Event.objects.select_related("creator__user").filter(ext_event_source=event_source).order_by("event_date")
    num = 0
    for ex in games:
        num += 1
        print "%s. Saving badge for event %s, %s" % (num, ex.pk, ex)
        hometeam = ex.creator.user.username.lower()
        img = os.path.join(eventimgpath, hometeam + ".jpg")
        f = open(img, "rb")        
        raw_image_contents = f.read()
        f.close()
        image_content = ContentFile(raw_image_contents)
        fname, ext = os.path.splitext("default.jpg")
        fname = u'%s%s' % (uuid4().hex[::2], ext)
        ex.description = description
        ex.image.save(fname, image_content, save=False)
        ex._create_resized_images(raw_field=None, save=False)
        ex.save()
        print "\t%s. Saved badge for event %s, %s" % (num, ex.pk, ex)


'''
Team Meta info format:
Team    City/Area    Stadium    Primary color    Secondary color    Twitter hashtag    Username    TZ
Orioles    Baltimore, MD    Oriole Park at Camden Yards     Orange    Black        BaltimoreBaseball   ET
Red Sox    Boston, MA     Fenway Park     Red    Navy        BostonBaseball  ET
Yankees    New York City, NY    Yankee Stadium     Navy    White        NewYorkBaseball  ET

Schedule:
START DATE    SUBJECT    LOCATION    START TIME (PT)    START TIME (MT)    START TIME (CT)    START TIME (ET)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    
04/04/10    Yankees at Red Sox    Fenway Park    05:05:00 PM    06:05:00 PM    07:05:00 PM    08:05:00 PM                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    
04/05/10    Blue Jays at Rangers    Rangers Ballpark in Arlington    11:05:00 AM    12:05:00 PM    01:05:00 PM    02:05:00 PM                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    
04/05/10    Cardinals at Reds    Great American Ball Park    10:10:00 AM    11:10:00 AM    12:10:00 PM    01:10:00 PM                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    


'''
def import_mlb(filepath, metapath, event_source='mlb2010', geo_loc="42.63699,-71.549835", limit=100000, **kwargs):
    import csv
    import Image, ImageFont, ImageDraw
    from django.contrib.auth.models import User
    from django.db.models import signals
    from artist.models import ArtistProfile
    from event.models import Event, Venue, Attendee, Stats, recompute_event_stats
    from rdutils.image import get_raw_png_image, resize_in_memory, get_perfect_fit_resize_crop, remove_model_image, close, get_raw_image, str_to_file
    from registration.utils import copy_avatar_from_file_to_profile
    
    print "Script has been disabled to prevent accidental execution :)"
    return False
    
    signals.post_save.disconnect(recompute_event_stats, sender=Attendee)
    signals.post_delete.disconnect(recompute_event_stats, sender=Attendee)
    
    # clear old data first
    '''
    print "Deleting stats"
    Stats.objects.filter(event__ext_event_source=event_source).delete() # delete existing stats
    Stats.objects.filter(event__ext_event_source=event_source).delete()
    print "Deleting events"
    Event.objects.filter(ext_event_source=event_source).delete() # delete existing events first
    print "Deleting users"
    User.objects.filter(first_name='MLB', last_name='Team', email__endswith='@riotvine.com').delete() # delete existing users
    '''
    
    colormap = {
        # 'navy':'#2E2EFE',
        'red': '#DD0000',
    }
    
    secondary_colormap = {}
    
    _ARTIST = ArtistProfile.objects.get(url='riotvine-member')
    _DATE_FORMAT = "%m/%d/%y" # format: 03/17/10
    _TIME_FORMAT = "%H:%M:%S %p"# format: 11:05:00 AM
    
    parent, filename = os.path.split(_DEFAULT_IMAGE)
    profilepath = os.path.join(parent, "baseball.jpg")
    eventbgpath = os.path.join(parent, "baseball_background.png")
    
    # load team meta info    
    team = {}
    reader = csv.reader(open(metapath, "rb"))    
    for row in reader:
        print row
        username = row[6].replace(' ', '')
        team_name = row[0].strip()
        hashtags = ", ".join(row[5].strip().split("~"))
        tz = row[7].strip()
        # create venue
        venue = row[2].decode("utf-8").strip()   
        venue_address = u''
        venue_city, venue_state = row[1].decode("utf-8").strip().split(",")
        venue_city, venue_state = venue_city.strip(), venue_state.strip()
        querystring = urlencode({'q':u'"%s" %s, %s %s' % (venue[:25], venue_address, venue_city, venue_state)})
        map_url = u'http://maps.google.com/?%s' % querystring
        vn, created = Venue.objects.get_or_create(
            name=venue[:255],
            geo_loc=geo_loc,
            source='mlb',
            defaults=dict(
                source='mlb',
                address=venue_address[:255],
                city=venue_city[:255],
                state=venue_state,
                zip_code=u'',
                venue_url=u'',
                map_url=map_url,
            )
        )
        # create user
        a, created = User.objects.get_or_create(
            username=username,
            defaults = dict(
                first_name='MLB',
                last_name='Team',
                email='riotvine-mlb-%s@riotvine.com' % username.lower(),
                is_staff=False,
                is_active=True
            )
        )
        user_profile = a.get_profile()
        user_profile.send_reminders = False
        user_profile.send_favorites = False
        is_verified = True
        user_profile.save()
        copy_avatar_from_file_to_profile(profilepath, user_profile)
        team[team_name.lower()] = {
            'name':team_name,
            'venue':vn,
            'pri-color':colormap.get(row[3].lower(), row[3]),
            'sec-color':secondary_colormap.get(row[4].lower(), row[4]),
            'user':user_profile,
            'tz':tz,
            'hashtags':hashtags,
        }    
    
    print "Loading schedule"
    # load schedule    
    description = u'''
        <p class="mlb">
            <a href="/sports/baseball/2010/">Baseball 2010&nbsp;&raquo;</a>
        </p>
    '''
    reader = csv.reader(open(filepath, "rb"))    
    num = 0
    for row in reader:
        num += 1
        print num, row
        dt, title, loc, ptime, mtime, ctime, etime = row
        
        # get road and home
        road, home = title.split(' at ')
        road, home = road.strip(), home.strip()
        roadvars = team[road.lower()]
        homevars = team[home.lower()]
        roaduser, homeuser = roadvars['user'], homevars['user']
        roadcolors = roadvars['pri-color'], roadvars['sec-color']
        homecolors = homevars['pri-color'], homevars['sec-color']
        
        hashtags = homevars['hashtags']
        
        # generate 211x211 badge
        raw_image_contents = None
        bg = Image.new("RGB", (211, 211), homecolors[1]) # background is the sec color of home team
        bgimg = Image.open(eventbgpath)
        bg.paste(bgimg, (0, 0))
        t = ImageDraw.Draw(bg)
        # Road team name
        x, y = settings.SPORTS_TEAM_TEXT_START
        font = ImageFont.truetype(settings.SPORTS_TEAM_TEXT_FONT, settings.SPORTS_TEAM_TEXT_FONT_SIZE, encoding='unic')
        tx = roadvars['name']
        w,h = t.textsize(tx, font=font)
        x = (211 - w)/2 # center align
        col = roadcolors[0] # (homecolors[1] == roadcolors[0]) and roadcolors[1] or roadcolors[0]
        t.text((x, y), tx, font=font, fill=col)
        
        # Text = at
        x, y = x, y + settings.SPORTS_TEAM_TEXT_FONT_SIZE + 10
        font = ImageFont.truetype(settings.SPORTS_TEAM_TEXT_FONT, settings.SPORTS_TEAM_TEXT_SMALL_FONT_SIZE, encoding='unic')
        tx = 'at'
        w,h = t.textsize(tx, font=font)
        x = (211 - w)/2 # center align
        t.text((x, y), tx, font=font, fill='#333333')
        
        # Home team name
        x, y = x, y + settings.SPORTS_TEAM_TEXT_SMALL_FONT_SIZE + 10
        font = ImageFont.truetype(settings.SPORTS_TEAM_TEXT_FONT, settings.SPORTS_TEAM_TEXT_FONT_SIZE, encoding='unic')
        tx = homevars['name']
        w,h = t.textsize(tx, font=font)
        x = (211 - w)/2 # center align
        t.text((x, y), tx, font=font, fill=homecolors[0])
        
        raw_image_contents = get_raw_png_image(bg)        
        
        # get venue
        vn = homevars['venue']
        location = settings.STATE_TO_LOCATION_MAP.get(vn.state.lower(), 'user-entered')
        city_state = u'%s|%s' % (vn.city, vn.state)
        location = settings.CITY_STATE_TO_LOCATION_MAP.get(city_state.lower(), location)
        # special cases for locations
        if vn.state == 'NJ':
            location = 'user-defined'
        
        dt = strptime(dt, _DATE_FORMAT)
        event_date = date(*dt[:3])
        
        tz = homevars['tz']
        if tz == 'ET':
            xtime = etime
        elif tz == 'CT':
            xtime = ctime
        elif tz == 'MT':
            xtime = mtime
        elif tz == 'PT':
            xtime = ptime
        else:
            xtime = etime # default timezone is ET
        
        tt = strptime(xtime.strip(), _TIME_FORMAT)
        h, m = tt.tm_hour, tt.tm_min
        if 'PM' in etime.upper() and h < 12:
            h = h + 12
        event_time = u"%s:%s" % (h, m)
        
        title = u"%s! %s" % (title, event_date.strftime("%m/%d"))
        # save event
        ex = Event(
            ext_event_id="999",
            ext_event_source=event_source,
            artist=_ARTIST,
            creator=homeuser,
            description=description,
            is_submitted=True,
            is_approved=True,
            is_free=False,
            title=title[:120],
            url=(u"%s-%s" % (slugify(title)[:30], uuid4().hex[::4]))[:35],
            venue=vn,
            event_date=event_date,
            event_start_time=event_time,
            event_timezone=tz,
            hashtag=hashtags,
            location=location,
            headliner=u'',
            artists=u'',
            has_image=True,
        )
        image_content = ContentFile(raw_image_contents)
        fname, ext = os.path.splitext("default.jpg")
        fname = u'%s%s' % (uuid4().hex[::2], ext)
        ex.image.save(fname, image_content, save=False)
        ex._create_resized_images(raw_field=None, save=False)
        ex.save()
        # favorite event for home users
        ex.attendee_set.get_or_create(attendee_profile=homeuser)
        # ex.attendee_set.get_or_create(attendee_profile=roaduser)        
        if num > limit:
            return


def make_autoprofiles(*args, **kwargs):
    from event.models import Event
    from artist.models import ArtistProfile
    from lastfm.fetch_events import get_artist_user_profile
    
    artist = ArtistProfile.objects.get(url='riotvine-member')
    artist_profile = artist.user_profile
        
    ex = Event.objects.active(ext_event_source='last.fm', creator=artist_profile)
    for e in ex:
        if e.headliner:
            user_profile = get_artist_user_profile(e.headliner)
            if user_profile:
                e.creator = user_profile
                super(Event, e).save()
                e.attendee_set.get_or_create(attendee_profile=user_profile)
                _log.debug("Auto-profiled %s -> %s", e.creator, e)
