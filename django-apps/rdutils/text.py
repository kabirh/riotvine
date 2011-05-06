import re
from BeautifulSoup import BeautifulSoup, Comment

from django.template.defaultfilters import slugify


def xss_vulnerable_html(html, allowed_tags=None, allowed_attrs=None):
    """Return False if html contains safe code. Otherwise, return True."""
    if "&#" in html:
        return True
    rx = []
    rx.append(re.compile(r'[\s]*(&#x.{1,7})?'.join(list('script')), re.IGNORECASE|re.MULTILINE))
    rx.append(re.compile(r'&#', re.IGNORECASE|re.MULTILINE))
    rx.append(re.compile(r'background:', re.IGNORECASE|re.MULTILINE))
    rx.append(re.compile(r'background-image:', re.IGNORECASE|re.MULTILINE))
    for r in rx:
        if bool(r.search(html)):
            return True
    if allowed_tags or allowed_attrs:
        tags, attrs = get_tags_and_attributes(html)
        if allowed_tags and not allowed_tags.issuperset(tags):
            return True
        if allowed_attrs and not allowed_attrs.issuperset(attrs):
            return True
    return False


def get_tags_and_attributes(html):
    """Return a tuple with sets of tags and attributes found in the given html."""
    soup = BeautifulSoup(html)
    for comment in soup.findAll(text=lambda text:isinstance(text, Comment)):
        comment.extract()
    tagset = set()
    attrset = set()
    for tag in soup.findAll(True):
        tagset.add(tag.name)
        for attr, val in tag.attrs:
            attrset.add(attr)
    return (tagset, attrset)


def sanitize_html(value):
    r = re.compile(r'[\s]*(&#x.{1,7})?'.join(list('javascript:')), re.IGNORECASE|re.MULTILINE)
    validTags = 'p span strong em u br a ul ol li blockquote'.split()
    validAttrs = 'href style'.split()
    validStyles = 'font-family font-size'.split()
    soup = BeautifulSoup(value)
    for comment in soup.findAll(text=lambda text:isinstance(text, Comment)):
        comment.extract()
    for tag in soup.findAll(True):
        if tag.name not in validTags:
            tag.hidden = True
        # tag.attrs = [(attr, r.sub('', val)) for attr, val in tag.attrs if attr in validAttrs]
        attrs = []
        for attr, val in tag.attrs:
            if attr in validAttrs:
                v = r.sub('', val)
                if attr == 'style':
                    try:
                        # Remove unsupported styles
                        vx = [x.strip() for x in v.strip().lower().split(';') if x.strip()]
                        for a in vx:
                            if a:
                                x, y = a.split(':')
                                if x.strip() not in validStyles:
                                    v = ''
                                    break
                    except:
                        v = ''
                        break
                attrs.append((attr, v))
        tag.attrs = attrs
    return soup.renderContents().decode('utf8')

