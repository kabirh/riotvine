import random

from django.forms.widgets import TextInput
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe


class CaptchaInput(TextInput):
    """Display a CAPTCHA image along with a text field that captures the user's
    CAPTCHA verification response.

    """
    def render(self, name, value, attrs=None):
        input_html = super(CaptchaInput, self).render(name, '', attrs=attrs)
        captcha_img_url = "%s?id=%s" % (reverse('captcha_image'),
                                    random.randint(0, 9999999))
        captcha = u'<img src="%s" alt="Captcha" class="captcha" />' % captcha_img_url
        return mark_safe(u'<div class="captcha-image">%s %s</div>' % (captcha, input_html))

