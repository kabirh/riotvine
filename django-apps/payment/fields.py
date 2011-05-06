from datetime import date

from django import forms
from django.utils.translation import ugettext_lazy as _


def is_cc_num_valid(cc):
    """Validate credit card number using the Luhn mod 10 checksum algorigthm.

    ``cc`` is the credit card number in string form with no spaces.

    Return ``True`` if the card number is valid. ``False``, otherwise.

    *******************
    This is only a validity check for the credit card digits.
    It DOES NOT verify that the number is a legitimate credit card that has 
    been issued.
    *******************

    Ref: http://en.wikipedia.org/wiki/Luhn_algorithm#Implementation

       1. Counting from rightmost digit (which is the check digit) and moving left, 
          double the value of every alternate digit. For any digits that thus 
          become 10 or more, take the two numbers and add them together. 
          For example, 1111 becomes 2121, while 8763 becomes 7733 
          (from 2x6=12 -> 1+2=3 and 2x8=16 -> 1+6=7).

       2. Add all these digits together. For example, if 1111 becomes 2121, 
          then 2+1+2+1 is 6; and 8763 becomes 7733, so 7+7+3+3 is 20.

       3. If the total ends in 0 (put another way, if the total modulus 10 
          is congruent to 0), then the number is valid according to the 
          Luhn formula; else it is not valid. So, 1111 is not valid 
          (as shown above, it comes out to 6), while 8763 is valid 
          (as shown above, it comes out to 20).

    """
    n = len(cc)
    if n < 13 or n > 16:
        return False
    k = map(int, cc[::-1]) # integer cc digits in reverse
    odd = k[::2] # alternate odd digits
    even = k[1::2] # alternate even digits
    even_doubled = map(lambda x:x*2, even)
    
    # If any numbers in even_doubled are > 10, sum their digits
    even_doubled = map(lambda x: x/10 + (x % 10), even_doubled)
    checksum = sum(odd + even_doubled)
    return checksum % 10 == 0


class CreditCardField(forms.CharField):
    """A form field to accept a valid credit card number."""
    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = kwargs.get('max_length', 20)
        super(CreditCardField, self).__init__(*args, **kwargs)
        self.widget.attrs.update({'class':'textInput ccNum'})

    def clean(self, value):
        """Validate credit card number."""
        cc = super(CreditCardField, self).clean(value)
        cc = cc.replace(' ', '').replace('-', '')
        if not is_cc_num_valid(cc):
            raise forms.ValidationError(_(u'The credit card number is not valid.'))
        return cc


class CreditCardExpiryDateField(forms.CharField):
    """A form field to accept a valid cc expiry date."""
    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = kwargs.get('max_length', 8)
        y = (date.today().year + 2) % 100
        kwargs['help_text'] = kwargs.get('help_text', _('In the format MM/YY. For example: 11/%02d' % y))
        super(CreditCardExpiryDateField, self).__init__(*args, **kwargs)
        self.widget.attrs.update({'class':'textInput ccExpDate'})

    def clean(self, value):
        """Verify that the date is in the format MM/YY and that it is in the future."""
        dt = value
        try:
            today = date.today().replace(day=1)
            century = date.today().year / 100 * 100
            m, y = dt.split('/')
            m = int(m)
            y = int(y)
            exp = date(century + y, m, 1)
            if y < 0 or y > 99 or (exp < today):
                raise ValueError
        except ValueError:
            raise forms.ValidationError(_(u'The expiration date must be a valid date in the format MM/YY.'))
        return dt


class CreditCardCCVField(forms.IntegerField):
    """A form field to accept a cc verification code."""
    def __init__(self, *args, **kwargs):
        kwargs['min_value'] = kwargs.get('min_value', 100)
        kwargs['max_value'] = kwargs.get('max_value', 9999)
        kwargs['help_text'] = kwargs.get('help_text', _('The three- or four-digit number on the back of a credit card (on the front for American Express.)'))
        super(CreditCardCCVField, self).__init__(*args, **kwargs)
        self.widget.attrs.update({'class':'textInput ccVerification'})

