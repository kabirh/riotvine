"""
Helper class structures that hold payment related data.

"""
from django.conf import settings


class PaymentError(Exception):
    pass


def _get_payment_processor_class():
    """Return the default PaymentProcessor class."""
    cls = settings.PAYMENT_PROCESSOR_CLS
    mod, cls = cls.rsplit('.', 1)
    mod = __import__(mod, globals(), locals(), [''])
    cls = getattr(mod, cls)
    return cls

# The default payment processor gets exported here
PaymentProcessor = _get_payment_processor_class()


class Payment(object):
    """A common structure to hold payment information."""
    def __init__(self, invoice_num=None, total_amount=None, cc_num=None, expiration_date=None, ccv=None):
        self.invoice_num = invoice_num
        self.total_amount = total_amount
        self.cc_num = cc_num
        self.expiration_date = expiration_date
        self.ccv = ccv


class TransactionData(object):
    """A common structure to hold payment transaction data."""
    def __init__(self):
        self._user = None
        self.address = None
        self.payment = None
        #self.phone = None

    def set_user(self, user):
        self._user = user
        self.address = user.get_profile().address
        #self.phone = user.get_profile().phone_number

    def get_user(self):
        return self._user

    user = property(get_user, set_user)
