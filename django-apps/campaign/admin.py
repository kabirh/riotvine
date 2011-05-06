from django.contrib import admin

from common.forms import get_model_form
from campaign import signals as campaign_signals
from campaign.forms import AdminCampaignForm
from campaign.models import Campaign, CampaignChange, Badge, Contribution, PendingContribution, Ticket, Stats


class CampaignAdmin(admin.ModelAdmin):
    form = AdminCampaignForm
    list_display = ('id', 'avatar_preview',
                    'title', 'admin_status', 'admin_contribution_amount', # 'image_preview',
                    'start_date', 'end_date', 'admin_artist_link', 'admin_stats_link',
                    'admin_max_contributions', 'admin_num_tickets_total',)
    search_fields = ('id', 'title', 'url', 'artist__name',
                      'artist__user_profile__user__username',
                      'artist__user_profile__user__email',)
    list_display_links = ('id', 'avatar_preview', 'title')
    list_per_page = 25
    raw_id_fields = ('artist',)
    list_filter = ('is_approved', 'is_payout_requested', 'is_submitted', 'is_homepage_worthy', 'is_deleted')
    save_on_top = True
    date_hierarchy = 'start_date'
    ordering = ('-id',)

    def log_change(self, request, object, message):
        super(CampaignAdmin, self).log_change(request, object, message)
        campaign_signals.post_campaign_admin_change.send(sender=Campaign, instance=object)

admin.site.register(Campaign, CampaignAdmin)


class CampaignChangeAdmin(admin.ModelAdmin):
    form = get_model_form(CampaignChange)
    list_display = ('campaign', 'title', 'start_date', 'end_date', 'is_approved', 'submitted_on')
    search_fields = ('title', 'url', 'campaign__artist__name',
                      'campaign__artist__user_profile__user__username',
                      'campaign__artist__user_profile__user__email',)
    list_display_links = ('campaign', 'title')
    list_per_page = 25
    raw_id_fields = ('campaign',)
    list_filter = ('is_approved',)
    save_on_top = True
    date_hierarchy = 'start_date'
    ordering = ('-id',)

admin.site.register(CampaignChange, CampaignChangeAdmin)


class BadgeAdmin(admin.ModelAdmin):
    form = get_model_form(Badge)
    list_display = ('campaign', 'badge_type', 'image_preview', 'updated_on')
    search_fields = ('campaign__title', 'campaign__url', 'campaign__artist__name')
    list_per_page = 25
    raw_id_fields = ('campaign',)
    list_filter = ('badge_type',)
    date_hierarchy = 'updated_on'
    ordering = ('-updated_on',)

admin.site.register(Badge, BadgeAdmin)


class ContributionAdmin(admin.ModelAdmin):
    form = get_model_form(Contribution)
    list_display = ('campaign', 'contributor', 'amount', 'qty', 'paid_on', 'transaction_id', 'payment_mode')
    list_display_links = ('campaign', 'amount')
    list_per_page = 25
    search_fields = ('campaign__title', 'campaign__url', 'campaign__artist__name')
    raw_id_fields = ('campaign', 'contributor')
    date_hierarchy = 'paid_on'
    list_filter = ('payment_mode',)
    ordering = ('-paid_on',)

admin.site.register(Contribution, ContributionAdmin)


class PendingContributionAdmin(admin.ModelAdmin):
    form = get_model_form(PendingContribution)
    list_display = ('campaign', 'contributor', 'amount', 'qty', 'paid_on', 'id', 'payment_mode')
    list_display_links = ('campaign', 'amount')
    list_per_page = 25
    search_fields = ('campaign__title', 'campaign__url', 'campaign__artist__name')
    raw_id_fields = ('campaign', 'contributor')
    date_hierarchy = 'paid_on'
    list_filter = ('payment_mode',)
    ordering = ('-paid_on',)

admin.site.register(PendingContribution, PendingContributionAdmin)


class TicketAdmin(admin.ModelAdmin):
    form = get_model_form(Ticket)
    list_display = ('campaign', 'admin_code_display', 'is_printed', 'redeemed_by', 'redeemed_on', 'amount',)
    list_display_links = ('campaign', 'admin_code_display')
    list_filter = ('is_printed', 'is_redeemed')
    list_per_page = 25
    search_fields = ('code', 'campaign__title', 'campaign__url', 'campaign__artist__name', 'code')
    raw_id_fields = ('campaign', 'redeemed_by')
    date_hierarchy = 'updated_on'
    ordering = ('-redeemed_on',)

admin.site.register(Ticket, TicketAdmin)


class StatsAdmin(admin.ModelAdmin):
    form = get_model_form(Stats)
    list_display = ('campaign', 'amount_raised', 'num_contributions', 'num_online_contributions', 'num_tickets_redeemed', 'updated_on')
    list_display_links = ('campaign', 'amount_raised')
    search_fields = ('campaign__title', 'campaign__url', 'campaign__artist__name', 'code')
    list_per_page = 25
    raw_id_fields = ('campaign',)
    date_hierarchy = 'updated_on'
    ordering = ('-updated_on',)

admin.site.register(Stats, StatsAdmin)

