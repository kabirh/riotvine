from Captcha.Visual.Tests import PseudoGimpy

from django.http import HttpResponse

from captcha import save_answer


def serve_captcha(request):
    """Serve a random CAPTCHA image and remember the expected answer by
    storing it in the session.

    """
    g = PseudoGimpy()
    answer_plain_text = g.solutions[0]
    enc = save_answer(request, answer_plain_text)
    response = HttpResponse(mimetype="image/png")
    im = g.render()
    im.save(response, "PNG", optimize=True)
    return response

