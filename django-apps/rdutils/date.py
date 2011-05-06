from datetime import date, datetime


def get_age(birth_date):
    """Return age in complete years based on birth date."""
    today = date.today()
    bday = birth_date
    return (today.year - bday.year) - ((today.month, today.day) < (bday.month, bday.day))

