from django.contrib import admin

from common.forms import get_model_form
from photo.models import PhotoSize, Photo, PhotoVersion


class PhotoSizeAdmin(admin.ModelAdmin):
    form = get_model_form(PhotoSize)
    list_display = ('name', 'max_width', 'max_height', 'do_crop')
    ordering = ('name',)

admin.site.register(PhotoSize, PhotoSizeAdmin)


class PhotoAdmin(admin.ModelAdmin):
    form = get_model_form(Photo)
    list_display = ('user', 'title', 'container', 'image_preview', 'added_on')
    search_fields = ('title', 'caption', 'user__user__username', 'user__user__email',)
    list_per_page = 25
    raw_id_fields = ('user',)
    ordering = ('-added_on',)
    date_hierarchy = 'added_on'

admin.site.register(Photo, PhotoAdmin)


