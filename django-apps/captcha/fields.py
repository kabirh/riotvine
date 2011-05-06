from django.forms.fields import CharField
from django.utils.translation import ugettext_lazy as _

from captcha.widgets import CaptchaInput


class CaptchaField(CharField):
    def __init__(self, label=_(u'Verification Code'), widget=CaptchaInput(attrs={'class':'required textInput captchaInput'}), max_length=50,
                 help_text=_(u'Enter the letters seen in the above image.'), *args, **kwargs):
        kwargs['label'], kwargs['widget'], kwargs['max_length'], kwargs['help_text'] = label, widget, max_length, help_text
        super(CaptchaField, self).__init__(*args, **kwargs)
