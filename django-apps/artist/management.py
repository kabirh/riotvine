"""
Populate the ``Genre`` data model with iTunes genre names.

"""
from django.db.models import signals
from artist import models


# We keep the genres in a line separated string as that makes it easy to
# copy and paste a different reference list from the web.
genres = """
Alternative & Punk
Blues
Classical
Country
Electronica/Dance
Folk
Hip Hop/Rap
Industrial
Jazz
Latin
Metal
New Age
Pop
Reggae
R&B
Rock
"""


# Only create genres if there are none in the database.
# That way, if a user deletes some of these genres, they won't resurface
# after a ``syncdb``.
def post_syncdb(sender, verbosity, **kwargs):
    if models.Genre.objects.count() == 0:
        for g in genres.split('\n'):
            if g:
                genre, created = models.Genre.objects.get_or_create(name=g.strip())
                if verbosity >= 2:
                    print "Genre created", g

signals.post_syncdb.connect(post_syncdb, sender=models)

