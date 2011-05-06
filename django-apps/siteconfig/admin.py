from django.contrib import admin

from siteconfig.models import SiteConfig
from siteconfig.forms import SiteConfigForm


class SiteConfigAdmin(admin.ModelAdmin):
    form = SiteConfigForm
    search_fields = ('name',)
    list_display = ('name', 'value')
    ordering = ('name',)

admin.site.register(SiteConfig, SiteConfigAdmin)

