"""
Authorize.NET payment processing module.

This module may be executed directly for test purposes.

"""
import logging
from urllib import urlencode
import urllib2

from django.conf import settings


_x = logging.getLogger('payment.processor.authorizedotnet')


class PaymentProcessor(object):
    """Main payment processor class."""
    def __init__(self, url=None, config_dict=None):
        self.url = settings.AUTHORIZEDOTNET_URL
        self.configuration = {
                'x_login':settings.AUTHORIZEDOTNET_LOGIN,
                'x_tran_key':settings.AUTHORIZEDOTNET_TRAN_KEY,
                'x_version':'3.1',
                'x_relay_response':'FALSE',
                'x_test_request':'FALSE',
                'x_delim_data':'TRUE',
                'x_delim_char':'|',
                'x_type':'AUTH_CAPTURE',
                'x_method':'CC',
                'x_duplicate_window':'180'}
        if config_dict:
            self.configuration.update(config_dict)
        if url:
            self.url = url
        self.result, self.data, self.transaction_data, self.post_string = None, {}, None, None

    def reset(self):
        """Discard all per-user transaction data."""
        self.result, self.data, self.transaction_data, self.post_string = None, {}, None, None

    def prepare_data(self, transaction_data, extra_dict=None):
        self.reset()
        self.transaction_data = transaction_data
        d = transaction_data # A convenient alias
        customer = {'x_cust_id':d.user.username[:20],
                         #'x_phone':d.phone or '',
                         'x_email':d.user.email,
                         'x_first_name':d.user.first_name,
                         'x_last_name':d.user.last_name,
                         'x_address':d.address.address1,
                         'x_address2':d.address.address2,
                         'x_city':d.address.city,
                         'x_state':d.address.state,
                         'x_zip':d.address.postal_code,
                         'x_country':d.address.country,}
        payment = {'x_card_num':d.payment.cc_num,
                        'x_exp_date':d.payment.expiration_date,
                        'x_card_code':d.payment.ccv,
                        'x_amount':d.payment.total_amount,
                        'x_invoice_num':d.payment.invoice_num,}
        self.data.update(self.configuration)
        self.data.update(payment)
        self.data.update(customer)
        if extra_dict:
            self.data.update(extra_dict)
        self.post_string = urlencode(self.data)

    def process(self):
        """Execute the HTTPS POST to Authorize Net.

        Return the result tuple (response_success, reasons_code, response_text)
        where, ``response_success`` is a boolean.

        """
        _x.debug(self.url)
        #_x.debug(self.post_string.replace('&', '\n'))
        conn = urllib2.Request(url=self.url, data=self.post_string)
        f = urllib2.urlopen(conn)
        all_results = f.read()
        parsed_results = all_results.split(self.configuration['x_delim_char'])
        #_x.debug(parsed_results)
        code = parsed_results[0]
        reason = parsed_results[1]
        text = parsed_results[3]
        self.result = (code == '1', reason, text)
        _x.debug(self.result)
        return self.result


if __name__ == "__main__":
    if not settings.DEV_MODE:
        raise Exception("Payment testing must be run in DEV_MODE")

    # Configure logging.
    if not logging.getLogger().handlers:
        import threading
        import logging.config
        threading.currentThread().setName('Pay') # Used by the logger
        logging.config.fileConfig('./logging.conf')
        _x_root = logging.getLogger()
        _x_root.setLevel(settings.DEBUG and logging.DEBUG or logging.INFO)
        _x = logging.getLogger('payment.processor.authorizedotnet')

    from django.contrib.auth.models import User
    from payment import TransactionData, Payment
    data = TransactionData()
    data.user = User.objects.get(username='fan1')
    data.payment = Payment(
                      invoice_num='12345',
                      total_amount='0.01',
                      cc_num='4007000000027',
                      expiration_date='0509',
                      ccv='144')
    processor = PaymentProcessor()
    processor.prepare_data(data)
    results, reason_code, msg = processor.process()
    _x.info(results, "::", reason_code, "::", msg)

