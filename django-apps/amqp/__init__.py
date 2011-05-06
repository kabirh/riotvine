import amqplib.client_0_8 as aq

from django.conf import settings

from amqp.base import AbstractQueue
from amqp.data import DataStorage


def get_connection():
    return aq.Connection(settings.AMQP_HOST, userid=settings.AMQP_USERID, password=settings.AMQP_PASSWORD)

