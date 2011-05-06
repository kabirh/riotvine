from __future__ import absolute_import
import logging
import os.path
from time import time
from mimetypes import guess_type
from datetime import datetime, date, timedelta
import Image, ImageFont, ImageDraw

from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile, UploadedFile
from django.utils.translation import ugettext as _

from rdutils.image import get_raw_png_image, resize_in_memory, get_perfect_fit_resize_crop, remove_model_image, close, get_raw_image, str_to_file


_log = logging.getLogger('event.badgegen')


def create_badge(event, badge, special=None, num_attendees=None):
    """Event badge creation routine. Refactored so that it may be reused by a campaign 
    that behaves like an event."""
    _log.debug('Creating badge: %s' % badge.get_badge_type_display())
    special = special or event.special_badge_text
    num_attendees = num_attendees or event.num_attendees
    bg, fg = None, None
    try:
        badge_type, badge_img = badge.badge_type, badge.bg_image_path
        bg = Image.open(badge_img)
        fg = Image.open(event.image_resized.path)
        bg.paste(fg, settings.EVENT_BADGE_IMAGE_POSITION)
        t = ImageDraw.Draw(bg)

        x, y = settings.EVENT_BADGE_SPECIAL_POSITION

        if special and event.is_approved:
            # Special text
            tx = special
            font = ImageFont.truetype(settings.EVENT_BADGE_SPECIAL_FONT, settings.EVENT_BADGE_SPECIAL_FONT_SIZE, encoding='unic')
            t.text((x, y), tx, font=font, fill='#dddddd')

        # Event date
        x, y = settings.EVENT_BADGE_DATE_POSITION
        tx = event.event_date.strftime("%m/%d/%y")
        font = ImageFont.truetype(settings.EVENT_BADGE_DATE_FONT, settings.EVENT_BADGE_DATE_FONT_SIZE, encoding='unic')
        t.text((x, y), tx, font=font, fill='#666666')

        x, y = settings.EVENT_BADGE_ATTENDEE_POSITION

        # Attendees
        if num_attendees:
            tx =  "%s" % num_attendees
            # Pick font size based on the number of attendees.
            idx = 0
            dx = 0
            if num_attendees > 999:
                idx = 2
            elif num_attendees > 99:
                idx = 1
            else:
                if num_attendees < 10:
                    dx = 15
                idx = 0
            font = ImageFont.truetype(settings.EVENT_BADGE_ATTENDEE_FONT, settings.EVENT_BADGE_ATTENDEE_FONT_SIZES[idx], encoding='unic')
            y -= settings.EVENT_BADGE_ATTENDEE_FONT_SIZES[idx] - 1
            t.text((x+dx, y), tx, font=font,  fill='#eeeeee')

            # Attending
            x, y = settings.EVENT_BADGE_TEXT_POSITION
            tx = "Attending"
            font = ImageFont.truetype(settings.EVENT_BADGE_TEXT_FONT, settings.EVENT_BADGE_TEXT_FONT_SIZE, encoding='unic')
            t.text((x, y), tx, font=font, fill='#c60104')

        # Save generated image
        raw_img = get_raw_png_image(bg)
        if raw_img:
            raw_file = str_to_file(raw_img)
            # file, field_name, name, content_type, size, charset
            raw_badge = InMemoryUploadedFile(raw_file, None, None, guess_type(".jpg")[0], len(raw_img), None)
            remove_model_image(badge, 'image') # remove previous resized copy
            badge.image.save(name='badge-%s-%s-%s.png' % (badge_type, event.pk, int(time())), content=raw_badge, save=False)
            badge.save()
            raw_file.close()
            _log.info('Badge (type: %s) created: %s - %s', badge_type, event.pk, event.title)
        else:
            _log.error('Badge (type: %s) creation failed: %s - %s', badge_type, event.pk, event.title)
    except Exception, e:
        _log.exception(e)
        raise
    finally:
        close(bg)
        close(fg)

