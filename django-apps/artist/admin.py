from django.contrib import admin

from common.forms import get_model_form
from artist.models import Genre, ArtistProfile


class GenreAdmin(admin.ModelAdmin):
    form = get_model_form(Genre)
    list_display = ('name',)


class ArtistProfileAdmin(admin.ModelAdmin):
    form = get_model_form(ArtistProfile)
    list_display = ('name', 'admin_url_link', 'admin_user_profile_link')
    search_fields = ('name', 'url', 'user_profile__user__username', 'user_profile__user__email',)
    list_per_page = 25
    raw_id_fields = ('user_profile',)
    list_filter = ('genres',)
    ordering = ('name',)


admin.site.register(Genre, GenreAdmin)
admin.site.register(ArtistProfile, ArtistProfileAdmin)
