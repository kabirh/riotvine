from urllib2 import *
from urllib import urlencode

x = {u'buyer-billing-address.region': u'NY', u'buyer-shipping-address.company-name': u'', u'buyer-billing-address.company-name': u'', u'buyer-shipping-address.fax': u'', u'shopping-cart.items.item-1.quantity': u'5', u'buyer-shipping-address.phone': u'', u'shopping-cart.items': u'shopping-cart.items.item-1', u'serial-number': u'466345432082631-00001-7\\r\\n', u'buyer-shipping-address.postal-code': u'11570', u'buyer-billing-address.city': u'Rockville Centre', u'google-order-number': u'466345432082631', u'order-adjustment.total-tax.currency': u'USD', u'buyer-billing-address.contact-name': u'Lawrence B Oakner', u'buyer-billing-address.email': u'larryoakner@aol.com', u'order-total': u'50.0', u'shopping-cart.items.item-1.item-name': u'You Can Be A Wesley: Pre-Order Pre-Party!', u'buyer-billing-address.fax': u'', u'order-adjustment.adjustment-total': u'0.0', u'buyer-shipping-address.contact-name': u'Lawrence B Oakner', u'financial-order-state': u'REVIEWING', u'buyer-shipping-address.city': u'Rockville Centre', u'buyer-id': u'132820792235584', u'shopping-cart.items.item-1.unit-price.currency': u'USD', u'buyer-billing-address.country-code': u'US', u'_type': u'new-order-notification', u'buyer-shipping-address.address1': u'49 Fonda Road', u'buyer-shipping-address.address2': u'', u'timestamp': u'2009-05-26T14:34:02.420Z', u'order-adjustment.total-tax': u'0.0', u'order-adjustment.adjustment-total.currency': u'USD', u'buyer-billing-address.phone': u'', u'buyer-billing-address.postal-code': u'11570', u'buyer-billing-address.address1': u'49 Fonda Road', u'buyer-billing-address.address2': u'', u'buyer-marketing-preferences.email-allowed': u'true', u'buyer-shipping-address.country-code': u'US', u'shopping-cart.items.item-1.unit-price': u'10.0', u'buyer-shipping-address.email': u'larryoakner@aol.com', u'order-total.currency': u'USD', u'fulfillment-order-state': u'NEW', u'shopping-cart.items.item-1.item-description': u'Illius Rock campaign: You Can Be A Wesley: Pre-Order Pre-Party!', u'buyer-shipping-address.region': u'NY'}
x.update({
    u'shopping-cart.merchant-private-data':u'0~anonymous~0',
    u'shopping-cart.items.item-1.merchant-item-id': u'8',
})

p = urlencode(x)
u = 'http://127.0.0.1:8000/campaign/google-notification/'
req = Request(u, p)
req.add_header("Content-type", "application/x-www-form-urlencoded")
req.add_header('User-Agent', 'GG')
resp = urlopen(req)
ret = resp.read()
resp.close()

print ret

