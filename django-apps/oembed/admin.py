from django.contrib import admin

from common.forms import get_model_form
from oembed.models import ServiceProvider


class ServiceProviderAdmin(admin.ModelAdmin):
    form = get_model_form(ServiceProvider)
    list_display = ('host', 'service_type', 'max_width', 'json_endpoint', 'url_scheme')

admin.site.register(ServiceProvider, ServiceProviderAdmin)
