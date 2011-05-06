import logging

from django.core.mail import EmailMessage
from django.contrib.sites.models import Site
from django.conf import settings
from django.template import Context, loader


_log = logging.getLogger('rdutils.email')


def send_mail(subject, message, from_email, to_list, fail_silently=True, subtype="plain"):
    msg = EmailMessage(subject, message, from_email, to_list)
    msg.content_subtype = subtype # plain or html
    msg.send(fail_silently=fail_silently)


def email_template(subject, template, context, to_list=None, fail_silently=True):
    """Conveniently e-mail a Django template."""
    if getattr(settings, 'DISABLE_EMAILS', False):
        _log.debug("Skipped email transmission")
        return
    if not to_list:
        to_list = [t[1] for t in settings.MANAGERS]
    if isinstance(to_list, tuple):
        to_list = [t[1] for t in to_list]
    if not 'site' in context:
        context['site'] = Site.objects.get_current()
    context.update(settings.UI_SETTINGS)
    context.update(settings.EXTRA_CONTEXT_SETTINGS)
    context.update(settings.SOCIAL_CONTEXT_SETTINGS)
    if 'MEDIA_URL' not in context:
        context['MEDIA_URL'] = settings.MEDIA_URL
    context = Context(context)
    message = loader.get_template(template).render(context)
    subtype = template.endswith('.html') and 'html' or 'plain'
    _log.debug("Sending email '%s' to %s", subject, to_list)
    # subject = subject + ' ' + settings.EMAIL_SUBJECT_PREFIX
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, to_list, fail_silently=fail_silently, subtype=subtype)
    _log.debug("Sent email '%s' to %s", subject, to_list)
