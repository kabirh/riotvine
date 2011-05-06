from django.contrib import admin

from common.forms import get_model_form
from queue.models import ActionItem


class ActionItemAdmin(admin.ModelAdmin):
    form = get_model_form(ActionItem)
    list_display = ('action', 'target_link', 'category', 'status', 'updated_on')
    list_per_page = 25
    list_filter = ('action', 'category', 'status')
    date_hierarchy = 'updated_on'
    ordering = ('-added_on',)
    save_on_top = True

admin.site.register(ActionItem, ActionItemAdmin)

