"""

Populate default flat pages and some reference data for photo galleries.

"""
from django.db.models import signals
from django.contrib.flatpages import models as flatpage_models
from django.contrib.auth import models as auth_models
from photo import models as photo_models
from siteconfig import models as siteconfig_models
from oembed import models as oembed_models
from artist import models as artist_models
from linker import models as linker_models


FLATPAGES = (
#------------------------------------------------------------------------------
('/help/registration/step/1/', 'Artist Registration - Step 1',
u'''## Artist Registration - Step 1
'''),
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
('/help/registration/step/2/', 'Artist Registration - Step 2',
u'''## Artist Registration - Step 2
'''),
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
('/help/registration/step/3/', 'Artist Registration - Step 3',
u'''## Artist Registration - Step 3
'''),
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
('/help/artist/profile/update/main/', 'Artist Account',
u'''## Account Update
'''),
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
('/help/artist/profile/update/sidebar/', 'Artist Account',
u'''## Account Update
'''),
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
('/help/artist/gco/instructions/', 'Google Checkout Setup Instructions',
u'''## Google Checkout Setup Instructions

Once signed up, you'll need to configure your Google Checkout account and find your Merchant ID and Key:

1. On your Google Checkout account page, click on Settings. If you can't find Settings, look for "My Sales" at the top.
2. On the Settings page, select Preferences from the left.
3. Under Order Processing, change the setting to: "Automatically authorize and **charge** the buyer's credit card."
4. If "Email me each time I receive an order, cancellation, or other transaction" is checked, you'll be notified for every contribution. (Recommended)
5. Click on Integration on the left.
6. Uncheck "My company will only host digitally signed carts."
7. In the API callback URL field, enter: https://riotvine.com/campaign/google-notification/
8. Set the Callback method to HTML.
9. On the right side, you should see your Google Merchant ID and Key. Copy these values into the fields below.

'''),
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
('/help/campaign/redeem-ticket/', 'Redeem Ticket Sidebar',
u'''## What are campaign tickets?

We love going to live shows, and think they're a great venue for
artists to show you why you should contribute to their campaigns. If
an artist has an ongoing campaign on RiotVine.com, they can accept
your contributions at their live shows. In exchange for your
contribution, you'll receive a campaign ticket with a unique code that
you can enter above. Once entered, it will acknowledge your contribution to the 
artist's campaign and qualify you for the campaign offering.

Still have questions? E-mail us at help@riotvine.com
'''),
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
('/about/', 'About Us',
u'''## About Us
'''),
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
('/contact/', 'Contact Us',
u'''## Contact Us
'''),
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
('/terms-of-use/', 'Terms of Use',
u'''## Terms of Use
'''),
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
('/help/', 'Help',
u'''## Help
'''),
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
('/help/registration/', 'Artist Registration - Help',
u'''### Artist Registration - Help
'''),
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
('/help/artist/faq/', 'Artist FAQ',
u'''## What are campaign tickets?

We love going to shows. They're the perfect opportunity to promote your campaign and accept contributions, so we made it easy.

Campaigns tickets allow your fans to quickly contribute to your campaigns. In exchange for their contribution, they receive a ticket that directs them to RiotVine.com. Each ticket has a unique code on it that acknowledges them as a contributor to your campaign.

### I don't get it?

Here's a handy 3 step breakdown:

1. Request campaign tickets.
2. Accept contributions.
3. Hand out a campaign ticket for each contribution.

### What if the fan is not registered on Riot Vine? Can they still contribute?

Yes, they'll be asked to create an account after they enter their unique code on our website.

### Why is there a maximum on the amount of tickets I can request?

Your campaigns have a limited number of spots, so the maximum number of tickets you can request is limited to the maximum number of spots available in your campaign.

### How many campaign tickets should I request?

That's up to you, but we'd recommend enough to meet demand at live shows but still leave some left over for fans that want to contribute online.

### If I request the maximum number of tickets, what happens to my campaign?

The number of tickets you request will be automatically deducted from the total available campaign spots. This ensures that everyone that receives a ticket will have an open spot in your campaign. Unfortunately, anyone that goes to your campaign page will be told that online contributions are unavailable, and will be directed to contact you.

### I requested campaign tickets; what next?

You should receive campaign tickets 5-7 days after they are requested. They are mailed to the band address we have on file for you. Once received, you can immediately start accepting contributions in exchange for tickets.

**Still have questions? E-mail us: help@riotvine.com**

'''),
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
('/site/landingpage-intro/', 'Landing Page Intro',
u'''
<div style="width:100%;margin:0 auto;text-align:center;">

<h2 style='font-size:230%;font-family:"Georgia", "Times New Roman", serif;font-weight:bold;color:#555;'>
Get out and take your friends with you
</h2>

<p style='text-align:left;padding:0 0 0 60px;font-size:150%;font-family:"Lucida Grande", "Times New Roman", serif;font-style:italic;font-weight:normal;color:#555;'>
RiotVine is a social event guide; we make it easy to discover all<br/>
the
great events around you, and share them with your friends.<br/>
All it takes is a single click.
</p>

<h3 style='font-size:200%;font-family:Georgia, "Times New Roman", serif;color:#555;line-height:1.3;margin-top:1.25em'>
Get started by <a href="#" class="login_dialog">signing up</a>,<br/>
<a href="/lnk/tweet-us/">inviting</a> your friends and<br/>
<img src="/media/ui/images/star-25x25.png" width="25" height="25" border="0" alt="fav"/>'ing a few events.
</h3>

</div>

'''),
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
('/site/campaigns-intro/', 'Campaigns Intro',
u'''## What are campaigns?

### Current Campaigns
'''),
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
('/site/campaigns-sidebar/', 'Campaigns Sidebar',
u'''
'''),
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
('/artist/admin/tip/1/', 'Artist Admin',
u'''## Tip1 
'''),
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
('/artist/admin/tip/2/', 'Artist Admin',
u'''## Tip2
'''),
#------------------------------------------------------------------------------
)


def create_flatpages(sender, verbosity, **kwargs):
    from django.contrib.sites.models import Site
    for url, title, content in FLATPAGES:
        fp, created = flatpage_models.FlatPage.objects.get_or_create(url=url, defaults=dict(title=title,
                                                              content=content,
                                                              enable_comments=False,
                                                              registration_required=False))
        if created:
            if verbosity >= 2:
                print "Flatpage created", url
            fp.sites = [Site.objects.get_current()]

signals.post_syncdb.connect(create_flatpages, sender=flatpage_models)


PHOTO_SIZES = (
    ('Thumbnail', 100, 100, False),
    ('Square Thumbnail', 50, 50, True),
    ('Medium', 400, 300, False),
)


def create_photo_sizes(sender, verbosity, **kwargs):
    for name, w, h, crop in PHOTO_SIZES:
        fp, created = photo_models.PhotoSize.objects.get_or_create(max_width=w, max_height=h, do_crop=crop, defaults={'name':name})
        if created and verbosity >= 2:
            print "PhotoSize created", fp

signals.post_syncdb.connect(create_photo_sizes, sender=photo_models)


SITECONFIG_PARAMS = {
    'description': u'''RiotVine is your best source for event networking.''',
    'keywords': u'events, tweetups, parties',
}


def create_siteconfig_params(sender, verbosity, **kwargs):
    for name, value in SITECONFIG_PARAMS.iteritems():
        siteconf, created = siteconfig_models.SiteConfig.objects.get_or_create(name=name, defaults={'value':value})
        if created:
            if verbosity >= 2:
                print "SiteConfig created", name

signals.post_syncdb.connect(create_siteconfig_params, sender=siteconfig_models)


OEMBED_PROVIDERS = (
    ('MySpace.com', 'video', 'http://*.myspace.com/*', 'http://oembed.riotvine.com/oembed/', True, 425, 'width, height, html'),
    ('YouTube.com', 'video', 'http://*.youtube.com/watch*', 'http://oembed.riotvine.com/oembed/', True, 425, 'width, height, html'),
    ('Vimeo.com', 'video', 'http://www.vimeo.com/*', 'http://www.vimeo.com/api/oembed.json', False, 425, 'width, height, html'),
    ('SoundCloud.com', 'rich', 'http://soundcloud.com/*', 'http://soundcloud.com/oembed', True, 425, 'width, height, html'),
    ('Qik.com', 'video', 'http://qik.com/*', 'http://qik.com/api/oembed.json', False, 425, 'width, height, html'),
)


def oembed_post_syncdb(sender, verbosity, **kwargs):
    for host, stype, scheme, endpoint, format_reqd, max_width, keys in OEMBED_PROVIDERS:
        sp, created = oembed_models.ServiceProvider.objects.get_or_create(host__iexact=host,
            defaults=dict(service_type=stype, host=host,
                          url_scheme=scheme, json_endpoint=endpoint,
                          format_parameter_required=format_reqd,
                          max_width=max_width, keys=keys))
        if verbosity >= 2:
            print "oEmbed ServiceProvider created", sp

signals.post_syncdb.connect(oembed_post_syncdb, sender=oembed_models)


GROUPS = ('Disable ack email',)

def create_groups(sender, verbosity, **kwargs):
    for name in GROUPS:
        g, created = auth_models.Group.objects.get_or_create(name=name)
        if created:
            if verbosity >= 2:
                print "Group created", g.name

signals.post_syncdb.connect(create_groups, sender=auth_models)


def create_default_accounts(sender, verbosity, **kwargs):
    a, created = auth_models.User.objects.get_or_create(
        username='riotvine_member',
        defaults = dict(
            first_name='Riot',
            last_name='Vine',
            email='riotvine@riotvine.com',
            is_staff=False,
            is_active=False
        ))
    user_profile = a.get_profile()
    if not user_profile.is_artist:
        user_profile.is_artist = True
        user_profile.save()
    ax, created = artist_models.ArtistProfile.objects.get_or_create(
        user_profile=user_profile,
        defaults = dict(
            name='RiotVine',
            num_members=1,
            url='riotvine-member'
        ))
    if created:
        print "Artist created", ax.name

    a, created = auth_models.User.objects.get_or_create(
        username='anonymous',
        defaults = dict(
            first_name='Anonymous',
            last_name='Riot Vine User',
            email='riotvine+anonymous@riotvine.com',
            is_staff=False,
            is_active=True
        ))
    user_profile = a.get_profile()
    if created:
        print "Anonymous user created", a.username

signals.post_syncdb.connect(create_default_accounts, sender=artist_models)


LINK_PARAMS = (
    ('tweet-us', 'http://twitter.com/home?status=I+just+signed+up+for+@RiotVine,+check+it+out+and+find+cool,+local+events!+http://riotvine.com', 'RiotVine Tweet'),
)


def create_weblinks(sender, verbosity, **kwargs):
    for url, redirect_to, category in LINK_PARAMS:
        o, created = linker_models.WebLink.objects.get_or_create(url=url, defaults={'redirect_to':redirect_to, 'category':category})
        if created:
            if verbosity >= 2:
                print "WebLink created", name

signals.post_syncdb.connect(create_weblinks, sender=linker_models)

