from django.db.models import ObjectDoesNotExist
from django.db import backend


def get_or_none(query, **kwargs):
    """Convenience method to return a model object or None."""
    try:
        return query.get(**kwargs)
    except ObjectDoesNotExist:
        return None


def quote_name(name):
    """Quote database field or table name."""
    return backend.DatabaseOperations().quote_name(name)

