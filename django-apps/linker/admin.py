from django.contrib import admin
from django.conf import settings

from common.forms import get_model_form
from linker.models import WebLink


class WebLinkAdmin(admin.ModelAdmin):
    form = get_model_form(WebLink)
    list_display = ('url', 'category', 'email_count', 'web_count', 'total_count', 'updated_on', 'id')
    search_fields = ('url', 'redirect_to', 'category')
    list_filter = ('category',)
    ordering = ('-updated_on',)

admin.site.register(WebLink, WebLinkAdmin)

