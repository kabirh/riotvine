'''
<script type='text/javascript'>
    var amzn_wdgt={widget:'MP3Clips'};
    amzn_wdgt.tag='riot06-20';
    amzn_wdgt.widgetType='ASINList';
    amzn_wdgt.ASIN='B0011Z0YR2,B00137W4P8,B0013G0PG4,B001AU8ZLK,B001AUCJZ8,B001AUEMDK,B001AU8YB6,B001AU8YBQ,B001AU8YCK,B001AUCK2U,B001AUEMFS,B001AUCK52,B001AU6XE6,B001AUEMH6';
    amzn_wdgt.title='What I\'ve been listening to lately...';
    amzn_wdgt.width='234';
    amzn_wdgt.height='60';
    amzn_wdgt.shuffleTracks='True';
    amzn_wdgt.marketPlace='US';
</script>
<script type='text/javascript' src='http://wms.assoc-amazon.com/20070822/US/js/swfobject_1_5.js'>
</script>


Examples:
==========

http://ecs.amazonaws.com/onca/xml?AWSAccessKeyId=113ANC87BN82Q5CTP3R2&IdType=ASIN&Keywords=Will%20Dailey&Operation=ItemSearch&ResponseGroup=ItemIds&SearchIndex=MP3Downloads&Service=AWSECommerceService&SignatureMethod=HmacSHA256&SignatureVersion=2&Sort=-releasedate&Timestamp=2009-11-16T15%3A17%3A51&Version=2008-08-19&Signature=kPkWM4RIcnCj4LBcg2oNO3WVp/yuw1/77wlVi6Qvfrg%3D

http://ecs.amazonaws.com/onca/xml?AWSAccessKeyId=AKIAJGA2X2R3N7QW7JXA&AssociateTag=riot06-20&IdType=ASIN&Keywords=%22Will%20Dailey%22&Operation=ItemSearch&ResponseGroup=ItemIds&SearchIndex=MP3Downloads&Service=AWSECommerceService&SignatureMethod=HmacSHA256&SignatureVersion=2&Sort=-releasedate&Timestamp=2009-11-16T16%3A35%3A19&Version=2008-08-19&Signature=gxD2N19QND8bvLBS9X7HyOTaryEKcKC7VsyZlvGsZsY%3D

'''
import time
import urllib
from boto.connection import AWSQueryConnection
import xml.etree.ElementTree as ET
from django.conf import settings


AWS_ACCESS_KEY_ID = settings.AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY = settings.AWS_SECRET_ACCESS_KEY
AWS_ASSOCIATE_TAG = settings.AWS_ASSOCIATE_TAG


aws_conn = AWSQueryConnection(
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY, is_secure=False,
    host='ecs.amazonaws.com')
aws_conn.SignatureVersion = '2'
params = dict(
    Service='AWSECommerceService',
    Version='2008-08-19',
    SignatureVersion=aws_conn.SignatureVersion,
    AWSAccessKeyId=AWS_ACCESS_KEY_ID,
    AssociateTag=AWS_ASSOCIATE_TAG,
    Operation='ItemSearch',
    IdType='ASIN',
    SearchIndex='MP3Downloads',
    Sort='-releasedate',
    Keywords='"Will Dailey"',
    ResponseGroup='ItemIds',
    Timestamp=time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()))
verb = 'GET'
path = '/onca/xml'
qs, signature = aws_conn.get_signature(params, verb, path)
qs = path + '?' + qs + '&Signature=' + urllib.quote(signature)
# print "verb:", verb, "qs:", qs
print "http://ecs.amazonaws.com" + qs
# response = aws_conn._mexe(verb, qs, None, headers={})
# print response.read()

# ---------------------------
# XML
# ---------------------------
import xml.etree.ElementTree as ET

tree = ET.parse(f)
ns = "http://webservices.amazon.com/AWSECommerceService/2008-08-19"
asins =  tree.findall("{%(ns)s}Items/{%s}Item/{%s}ASIN" % {'ns':ns})
if asins:
    asins = [a.text for a in asins]
f.close()
