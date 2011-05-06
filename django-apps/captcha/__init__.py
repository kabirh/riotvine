from hashlib import sha1 as sha

from django.conf import settings


_CAPTCHA_KEY = '_captcha_key'


def encrypt(text):
    """Encrypt text."""
    salt = settings.SECRET_KEY[:20]
    enc = sha(salt+text.strip()).hexdigest()
    return enc


def verify(raw_text, hashed_text):
    """Verify that raw_text equals hashed_text."""
    return encrypt(raw_text) == hashed_text


def get_answer(request, clear=True):
    """Return the encrypted captcha response stored in the session.
    
    By default, also clear the response from the session.
    
    """
    answer = request.session.get(_CAPTCHA_KEY, None)
    if clear:
        try:
            del request.session[_CAPTCHA_KEY]
        except KeyError:
            pass
    return answer


def save_answer(request, answer_plain_text):
    """Store encrypted version of the answer text into the session."""
    encrypted = encrypt(answer_plain_text)
    request.session[_CAPTCHA_KEY] = encrypted
    return encrypted

