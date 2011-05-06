from __future__ import absolute_import
import logging
import random
import csv
from time import time
from sys import exc_info
from traceback import format_exception

from django.conf import settings
from django.http import HttpResponseRedirect, Http404, HttpResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.core.urlresolvers import reverse
from django.db import transaction
from django.db.models import Q, ObjectDoesNotExist
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, permission_required
from django.utils.translation import ugettext as _
from django.shortcuts import get_object_or_404
from django.views.static import serve as serve_static
from django.views.decorators.cache import cache_control
from django.utils.encoding import smart_str

from rdutils.render import render_view, paginate
from rdutils.email import email_template
from extensions import formwizard as wizard
from messages import forms as messageforms
from artist.decorators import artist_account_required
from queue.models import ActionItem
from payment.processor import paypal, google
from common.forms import CommentForm
from registration.models import UserProfile
from campaign.templatetags import campaigntags
from campaign.exceptions import CampaignError
from campaign.models import Campaign, Badge, Contribution, PendingContribution
from campaign import forms


_log = logging.getLogger('campaign.views')


class CampaignCreationFormWizard(wizard.FormWizard):
    """Wizard for creating campaigns."""
    def __init__(self, form_list=None, request=None):
        if form_list is None:
            form_list = [forms.get_campaign_form_main(request), forms.get_campaign_form_image(request)]
        super(CampaignCreationFormWizard, self).__init__(form_list)

    def get_template(self, step):
        return "campaign/campaign_creation_wizard.html"

    def __call__(self, request, *args, **kwargs):
        view_fn = artist_account_required(super(CampaignCreationFormWizard, self).__call__)
        return view_fn(request, *args, **kwargs)

    @transaction.commit_on_success
    def done(self, request, form_list):
        form_main, form_image = form_list
        campaign = form_main.save(commit=False)
        campaign.artist = request.user.get_profile().artist
        form_image.instance = campaign
        form_image.save(commit=False) # campaign.save_image_file(filename=None, raw_field=form_image.cleaned_data["image"], save=False)
        campaign.save()
        request.user.message_set.create(message=_("This is what your campaign page will look like. If you are happy with it, please submit it for approval."))
        _log.info('Campaign created: (%s) %s', campaign.pk, campaign.short_title)
        return HttpResponseRedirect(campaign.get_absolute_url())


@artist_account_required
@transaction.commit_on_success
def edit(request, campaign_id=None, template='campaign/campaign_edit_form.html'):
    ctx = {}
    approved_campaign_edit = False
    FormClass = forms.get_campaign_form(request)
    if campaign_id is not None:
        # We are in update mode. Get the campaign instance if it belongs to 
        # this user and it has not yet been submitted for admin approval.
        campaign = get_object_or_404(Campaign.visible_objects, pk=campaign_id, artist__user_profile__user=request.user) #is_submitted=False
        mode = 'update'
        ctx['campaign'] = campaign
        if campaign.is_approved:
            # Approved campaigns use a different form to track changes
            FormClass = forms.get_campaign_edit_form(campaign, request)
            approved_campaign_edit = True
    else:
        campaign = Campaign(artist=request.user.get_profile().artist)
        mode = 'create'
    if request.POST:
        form = FormClass(data=request.POST, files=request.FILES, instance=campaign)
        if form.is_valid():
            if approved_campaign_edit:
                campaign_change = form.save(commit=True)
                ActionItem.objects.q_admin_action(campaign, 'approve-campaign-edit')
                email_template('Campaign Edited: approval requested by %s' % request.user.username,
                           'campaign/email/request_approval_edit.txt',
                           {'campaign':campaign}, to_list=settings.CAMPAIGN_APPROVERS, fail_silently=False)
                request.user.message_set.create(message=_("This is what your updated campaign page will look like once an admin approves your changes."))
            else:
                campaign = form.save(commit=False)
                campaign.save()
                request.user.message_set.create(message=_("This is what your updated campaign page will look like. If you are happy with it, please submit it for approval."))
            if campaign_id is None:
                _log.info('Campaign created: (%s) %s', campaign.pk, campaign.short_title)
            else:
                _log.info('Campaign updated: (%s) %s', campaign.pk, campaign.short_title)
            return HttpResponseRedirect(campaign.get_absolute_url())
    else:
        form = FormClass(instance=campaign)
    ctx.update({'form':form, 'mode':mode})
    return render_view(request, template, ctx)


@artist_account_required
def list_contributors(request, campaign_id, template='campaign/contributors.html'):
    ctx = {}
    campaign = get_object_or_404(Campaign.visible_objects, pk=campaign_id, artist__user_profile__user=request.user, is_approved=True)
    contribs = list(campaign.contribution_set.all().order_by("contributor__username"))
    tickets = list(campaign.ticket_set.filter(is_redeemed=True).order_by("redeemed_by__username"))
    contributions = contribs + tickets
    if request.REQUEST.get('format', 'html') == 'csv':
        content_type = "text/csv; charset=%s" % settings.DEFAULT_CHARSET
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=campaign_%s_contributors.csv' % campaign.pk
        writer = csv.writer(response)
        r = writer.writerow
        r(['Campaign contributors'])
        r(['Campaign #%s' % campaign.pk, smart_str(campaign.title)])
        headers = ['User', 'First name', 'Last name'] #, 'Email']
        if campaign.is_free:
            headers.append('Joined on')
            def amount_fn(row, contribution):
                row.append(contribution.paid_on)
        else:
            headers.extend(['Type', 'Amount', 'Qty', 'Paid on'])
            def amount_fn(row, contribution):
                row.extend([contribution.contrib_type, contribution.amount, contribution.qty, contribution.paid_on])
        if campaign.phone_required:
            headers.append('Phone')
            def phone_fn(row, contribution):
                row.append(contribution.contributor.get_profile().phone)
        else:
            def phone_fn(row, contribution):
                pass
        if campaign.address_required:
            headers.extend(['Address', 'Address 2', 'City', 'State Zip'])
            def address_fn(row, contribution):
                try:
                    adr = contribution.contributor.get_profile().address
                    row.extend([
                        smart_str(adr.address1),
                        adr.address2 and smart_str(adr.address2) or '',
                        adr.city,
                        adr.state + ' ' + adr.postal_code
                    ])
                except ObjectDoesNotExist:
                    row.extend(['', '', '', ''])
        else:
            def address_fn(row, contribution):
                pass
        r(headers)
        for c in contributions:
            u = c.contributor
            username = (u.is_active and u.username != 'anonymous') and u.username or ''
            row = [username, u.first_name, u.last_name] #, u.email]
            amount_fn(row, c)
            phone_fn(row, c)
            address_fn(row, c)
            r(row)
        return response
    else:
        page = paginate(request, contributions, 100) # Show 100 contributors per page.
        ctx.update({'campaign':campaign, 'page':page})
        return render_view(request, template, ctx)


def list_sponsors(request, campaign_id, template='campaign/sponsors.html'):
    ctx = {}
    campaign = get_object_or_404(Campaign.visible_objects, pk=campaign_id)
    contributors = UserProfile.objects.select_related('user').filter(
        Q(user__contribution__campaign__pk=campaign.pk) |
        Q(user__ticket__campaign__pk=campaign.pk)
    ).distinct().order_by("user__username")
    page = paginate(request, contributors, 100) # Show 100 contributors per page.
    ctx.update({'campaign':campaign, 'page':page})
    return render_view(request, template, ctx)


@artist_account_required
@transaction.commit_on_success
def message_contributors(request, campaign_id, form_class=messageforms.ComposeForm, template_name='messages/compose.html', success_url=None):
    """Send a message to all contributors of the given campaign."""
    campaign = get_object_or_404(Campaign.visible_objects, pk=campaign_id, artist__user_profile__user=request.user, is_approved=True)
    form = form_class()
    if request.method == "POST":
        form = form_class(request.POST)
        if form.is_valid():
            form.save(sender=request.user)
            request.user.message_set.create(
                message=_(u"Message successfully sent."))
            if success_url is None:
                success_url = reverse('view_campaign', kwargs={'campaign_id':campaign.pk})
            return HttpResponseRedirect(success_url)
    else:
        form = form_class()
        contributions = campaign.contribution_set.members().order_by("contributor__username")
        recipients = list(set([c.contributor for c in contributions]))
        form.fields['recipient'].initial = recipients
    return render_view(request, template_name, {'form':form})


@artist_account_required
def list_artist_campaigns(request, category):
    """Show campaign summaries of logged in artist under the given category.

    Supported `category` values:
        unsubmitted
        pending-approval
        approved-upcoming
        active
        expired

    """
    # Sanity check
    if category not in ('unsubmitted', 'pending-approval', 'approved-upcoming', 'active', 'expired'):
        raise Http404
    artist = request.user.get_profile().artist
    category = category.replace('-', '_')
    # DRY: Call template tag for the given category.
    fn_name = 'campaigns_%s' % category
    tag_fn = getattr(campaigntags, fn_name)
    ctx = tag_fn(artist, limit=None)
    queryset = ctx.pop('campaigns')
    ctx["is_owner"] = True
    # Reuse the `list_campaigns` view.
    return list_campaigns(request, queryset=queryset, extra_context=ctx)


def list_campaigns(request, template='campaign/list.html', queryset=None, extra_context=None):
    if queryset is None:
        queryset = Campaign.objects.active().order_by('-end_date')
    page = paginate(request, queryset, settings.CAMPAIGNS_PER_PAGE, orphans=3)
    ctx = {'page':page, 'title':'Current campaigns'}
    if extra_context:
        ctx.update(extra_context)
    return render_view(request, template, ctx)


@login_required
@transaction.commit_on_success
def post_comment(request, campaign_id, template='campaign/comment_form.html'):
    campaign = get_object_or_404(Campaign.objects.public(), pk=campaign_id)
    if request.method == 'POST':
        form = CommentForm(author=request.user, target_instance=campaign, data=request.POST)
        if form.is_valid():
            comment = form.save()
            request.user.message_set.create(message=_('Thank you for your <a href="#c%s">comment&nbsp;&raquo;</a>' % comment.pk))
            _log.debug('Campaign comment posted: (%s)', comment.get_as_text())
            cache_killer = "%s-%s"% (random.randint(0, 10000), time())
            return HttpResponseRedirect(reverse('view_campaign', kwargs={'campaign_id':campaign.pk}) + "?q=%s&new_c=y" % cache_killer)
    else:
        form = CommentForm(author=request.user, target_instance=campaign)
    ctx = {'form':form, 'comment_form':form, 'campaign':campaign}
    return render_view(request, template, ctx)


@artist_account_required
@transaction.commit_on_success
def request_approval(request, campaign_id):
    if request.method == 'POST':
        campaign = get_object_or_404(Campaign.visible_objects, pk=campaign_id, artist__user_profile__user=request.user)
        if not campaign.is_submitted:
            campaign.is_submitted = True
            campaign.save()
            ActionItem.objects.q_admin_action(campaign, 'approve-campaign')
            request.user.message_set.create(message=_('Your campaign has just been submitted for approval. An administrator will review it shortly.'))
            email_template('Campaign approval requested by %s' % request.user.username,
                           'campaign/email/request_approval.txt',
                           {'campaign':campaign}, to_list=settings.CAMPAIGN_APPROVERS, fail_silently=False)
            _log.info('Campaign approval requested: (%s) %s', campaign.pk, campaign.short_title)
        else:
            request.user.message_set.create(message=_('This campaign has already been submitted for approval. Please send an e-mail to %s if you have questions.' % settings.CAMPAIGN_APPROVERS[0][1]))
        return HttpResponseRedirect(reverse('view_campaign', kwargs={'campaign_id':campaign_id}))
    else:
        raise Http404


@artist_account_required
@transaction.commit_on_success
def request_tickets(request, campaign_id, template='campaign/request_tickets_form.html'):
    campaign = get_object_or_404(Campaign.visible_objects, pk=campaign_id, artist__user_profile__user=request.user, is_approved=True)
    if not campaign.are_tickets_available:
        request.user.message_set.create(message=_('Tickets are not available for this campaign.'))
        return HttpResponseRedirect(reverse('view_campaign', kwargs={'campaign_id':campaign.pk}))
    if request.POST:
        form = forms.RequestTicketsForm(instance=campaign, data=request.POST)
        if form.is_valid():
            form.save()
            request.user.message_set.create(message=_("Your campaign ticket request has been sent to the admins. Your tickets will be mailed out shortly."))
            _log.info('Campaign tickets requested: (%s) %s', campaign.pk, campaign.short_title)
            return HttpResponseRedirect(reverse('view_campaign', kwargs={'campaign_id':campaign.pk}))
    else:
        form = forms.RequestTicketsForm(instance=campaign)
    ctx = {'form':form, 'campaign':campaign}
    return render_view(request, template, ctx)


@artist_account_required
@transaction.commit_on_success
def request_payout(request, campaign_id):
    if request.method == 'POST':
        campaign = get_object_or_404(Campaign.visible_objects, pk=campaign_id, artist__user_profile__user__id=request.user.id)
        if not campaign.has_ended:
            request.user.message_set.create(message=_("Payout may not be requested until after this campaign ends on %s." % campaign.end_date.strftime(settings.STRF_DATE_FORMAT)))
        elif not campaign.is_payout_requested:
            campaign.is_payout_requested = True
            campaign.save()
            ActionItem.objects.q_admin_action(campaign, 'payout-campaign')
            request.user.message_set.create(message=_('Your campaign payout request has been submitted. An administrator will review it shortly.'))
            email_template('Campaign payout requested by %s' % request.user.username,
                           'campaign/email/request_payout.txt',
                           {'campaign':campaign}, to_list=settings.CAMPAIGN_APPROVERS)
            _log.info('Campaign payout requested: (%s) %s', campaign.pk, campaign.short_title)
        else:
            request.user.message_set.create(message=_("That campaign's payout request has already been submitted. Please send an e-mail to %s if you have questions." % settings.CAMPAIGN_APPROVERS[0][1]))
        return HttpResponseRedirect(reverse('view_campaign', kwargs={'campaign_id':campaign_id}))
    else:
        raise Http404


@artist_account_required
@transaction.commit_on_success
def delete(request, campaign_id, template='campaign/campaign_deletion_form.html'):
    campaign = get_object_or_404(Campaign.visible_objects, pk=campaign_id, artist__user_profile__user=request.user)
    ctx = {'campaign':campaign, 'c':campaign}
    if request.method == 'POST':
        form = forms.DeleteCampaignForm(data=request.POST)
        if form.is_valid():
            if campaign.is_deletable:
                campaign.delete()
                request.user.message_set.create(message=_('Your campaign has been deleted.'))
                return HttpResponseRedirect(reverse('artist_admin'))
            else:
                ActionItem.objects.q_admin_action(campaign, 'delete-campaign')
                request.user.message_set.create(message=_('Your campaign deletion request has been submitted. An administrator will review it shortly.'))
                email_template('Campaign deletion requested by %s' % request.user.username,
                               'campaign/email/request_deletion.txt',
                               {'campaign':campaign}, to_list=settings.CAMPAIGN_APPROVERS)
                _log.info('Campaign deletion requested: (%s) %s', campaign.pk, campaign.short_title)
            return HttpResponseRedirect(reverse('view_campaign', kwargs={'campaign_id':campaign_id}))
    else:
        form = forms.DeleteCampaignForm()
    ctx['form'] = form
    return render_view(request, template, ctx)


@permission_required('campaign.can_manage_campaigns')
def print_tickets(request, campaign_id, template='campaign/print-tickets.html'):
    ctx = {}
    campaign = get_object_or_404(Campaign.visible_objects, pk=campaign_id)
    ctx['c'] = campaign
    ctx['unprinted'] = campaign.ticket_set.unredeemed(is_printed=False)
    ctx['printed'] = campaign.ticket_set.unredeemed(is_printed=True)
    ctx['redeemed'] = campaign.ticket_set.redeemed()
    if request.method == 'POST':
        # Printing completed. Mark tickets and action items as done.
        ActionItem.objects.q_admin_action_done(campaign, 'print-tickets')
        ctx['unprinted'].update(is_printed=True) #printed_on=datetime.now())
    return render_view(request, template, ctx)


def view_seo(request, artist_url, campaign_url):
    campaign_url = campaign_url.lower()
    campaign = get_object_or_404(Campaign, url=campaign_url, artist__url=artist_url)
    return view(request, campaign.pk)


def view(request, campaign_id, template='campaign/detail.html'):    
    """Campaign detail view"""
    ctx = {}
    campaign = get_object_or_404(Campaign.visible_objects, pk=campaign_id)
    ctx['is_owner'] = request.user.is_authenticated() and request.user.id == campaign.artist.user_profile.user.id
    ctx['is_admin'] = request.user.has_perm('campaign.can_manage_campaigns')
    # Campaign changes, if available, are shown only to the campaign owner and the admin.
    ctx['changes'] = (ctx['is_owner'] or ctx['is_admin']) and campaign.changed_version
    if not campaign.is_approved:
        # Only admins and campaign owners may see unapproved campaigns.
        if not request.user.is_authenticated():
            return HttpResponseRedirect("%s?next=%s" % (reverse('login'), request.path))
        if not (ctx['is_owner'] or ctx['is_admin']):
            # We could return an HTTP forbidden response here but we don't want a malicious user
            # to know if a campaign even exists with this id.
            # So, we raise a 404 - Page Not Found instead.
            raise Http404
    ctx['c'] = campaign
    ctx['campaign'] = campaign
    if request.user.is_authenticated():
        ctx['comment_form'] = CommentForm(author=request.user, target_instance=campaign)
    if not ctx['is_owner']:
        stats = campaign.stats
        stats.num_views = stats.num_views + 1
        stats.save()
    return render_view(request, template, ctx)


@cache_control(must_revalidate=True, max_age=120) #@never_cache #
def serve_badge(request, campaign_id, badge_type='i'):
    if badge_type == 'e':
        objects = Badge.objects.filter(campaign__is_approved=True)
    else:
        objects = Badge.objects
    badge = get_object_or_404(objects, campaign=campaign_id, campaign__is_deleted=False, badge_type=badge_type)
    #response = serve_static(request, path=badge.image.path.replace('\\', '/'), document_root='/')
    response = serve_static(request, path=badge.image.name, document_root=settings.MEDIA_ROOT)
    return response


@login_required
@transaction.commit_on_success
def contribute(request, campaign_id, template='campaign/campaign_contribution_form.html'):
    """Process free campaign registration."""
    campaign = get_object_or_404(Campaign.objects.active(), pk=campaign_id)
    if not campaign.is_free:
        # Disable direct credit card based contribution
        request.user.message_set.create(message=_('That payment option is not available for this campaign.'))
        return HttpResponseRedirect(reverse('view_campaign', kwargs={'campaign_id':campaign_id}))
    err_msg = None
    try:
        qualifies, reasons = campaign.is_user_qualified(request.user)
        user_profile=request.user.get_profile()
        data = None
        if qualifies and request.user.first_name and request.user.last_name:
            # Skip the form and directly register this event attendee.
            data = {'first_name':request.user.first_name, 
                    'last_name':request.user.last_name,
                    'birth_date':user_profile.birth_date}
        if data or request.method == 'POST':
            if request.method == 'POST':
                data = request.POST
            form = forms.DirectContributionForm(data=data, campaign=campaign, user_profile=user_profile)
            if form.is_valid():
                contribution = form.save(commit=True)
                _log.info('Contribution processed %s', contribution)
                if contribution.qty > 1:
                    request.user.message_set.create(message=_('Your %s contributions totalling $.2f have been processed. Thank you.' % (contribution.qty, contribution.amount)))
                elif not campaign.is_free:
                    request.user.message_set.create(message=_('Your contribution of $.2f has been processed. Thank you.' % contribution.amount))
                else:
                    request.user.message_set.create(message=_('You have successfully joined this free campaign. Thank you.'))
                return HttpResponseRedirect(reverse('view_campaign', kwargs={'campaign_id':campaign_id}))
        else:
            form = forms.DirectContributionForm(campaign=campaign, user_profile=user_profile)
        ctx = {'campaign':campaign, 'c':campaign, 'form':form}
    except CampaignError, e:
        request.user.message_set.create(message=e.message)
        return HttpResponseRedirect(reverse('view_campaign', kwargs={'campaign_id':campaign.pk}))
    return render_view(request, template, ctx)


@login_required
@transaction.commit_on_success
def contribute_by_payment_mode(request, campaign_id, payment_mode, template='campaign/campaign_contribution_form_%s.html'):
    """Process a PayPal or Google Checkout based contribution."""
    campaign = get_object_or_404(Campaign.objects.active(), pk=campaign_id)
    payment_option = campaign.artist.get_merchant_account(payment_mode)
    if not payment_option:
        raise Http404
    template = template % payment_option.payment_mode
    ContribForm = getattr(forms, '%sContributionForm' % payment_option.payment_mode.title())
    ctx = {'campaign':campaign, 'c':campaign, 'payment_option':payment_option}
    proceed_to_pay = False
    if campaign.is_free:
        return HttpResponseRedirect(reverse('contribute_to_campaign', kwargs={'campaign_id':campaign_id}))
    try:
        if request.POST:
            form = ContribForm(campaign=campaign, user_profile=request.user.get_profile(), data=request.POST)
            if form.is_valid():
                pending_contrib = form.save(commit=True)
                _log.info('Pending %s contribution recorded: %s', payment_option.payment_mode_name, pending_contrib)
                proceed_to_pay = True
                str_list = [str(k) for k in (campaign.pk, int(time()), pending_contrib.pk, request.user.pk)]
                pending_contrib.invoice_num = ''.join(str_list)
                ctx['contrib'] = pending_contrib
        else:
            form = ContribForm(campaign=campaign, user_profile=request.user.get_profile())
        ctx.update({'form':form, 'proceed_to_pay':proceed_to_pay})
    except CampaignError, e:
        request.user.message_set.create(message=e.message)
        return HttpResponseRedirect(reverse('view_campaign', kwargs={'campaign_id':campaign.pk}))
    return render_view(request, template, ctx)


def anon_contribute_by_payment_mode(request, campaign_id, payment_mode, template='campaign/campaign_contribution_form_%s_anon.html'):
    """Process a PayPal or Google Checkout based anonymous contribution."""
    campaign = get_object_or_404(Campaign.objects.active(), pk=campaign_id)
    payment_option = campaign.artist.get_merchant_account(payment_mode)
    if not payment_option:
        raise Http404
    template = template % payment_option.payment_mode
    ctx = {'campaign':campaign, 'c':campaign, 'payment_option':payment_option, 'is_anon':True, 'proceed_to_pay':True}
    if campaign.is_free:
        return HttpResponseRedirect(reverse('contribute_to_campaign', kwargs={'campaign_id':campaign_id}))
    return render_view(request, template, ctx)


@login_required
@transaction.commit_on_success
def qualify(request, campaign_id, template='campaign/campaign_qualification_form.html'):
    ticket_code = request.session.get('open_ticket_code', None)
    campaign = get_object_or_404(Campaign.objects.public(), pk=campaign_id)
    qualifies, reasons = campaign.is_user_qualified(request.user)
    if qualifies and ticket_code:
        return HttpResponseRedirect(reverse('redeem_ticket'))
    else:
        _log.debug("Qualification needed: %s", reasons)
    if request.POST:
        form = forms.QualificationForm(data=request.POST, campaign=campaign, user_profile=request.user.get_profile())
        if form.is_valid():
            user_profile = form.save(commit=True)
            request.user.message_set.create(message=_('Your profile has been updated.'))
            if ticket_code:
                return HttpResponseRedirect(reverse('redeem_ticket'))
            else:
                return HttpResponseRedirect(reverse('view_campaign', kwargs={'campaign_id':campaign_id}))
    else:
        form = forms.QualificationForm(campaign=campaign, user_profile=request.user.get_profile())
    ctx = {'campaign':campaign, 'c':campaign, 'form':form}
    return render_view(request, template, ctx)


@transaction.commit_on_success
def redeem_ticket(request, template='campaign/redeem_ticket.html'):
    """Redeem a campaign ticket.

    Kabir: The way I see it working is:
    Once they type in the redemption code, it will ask them to login or create an account. 
    New users create an account. The system checks to see what information it needs for the 
    redemption code they typed in and asks them to fill in the additional needed information.
    Then it redeems the ticket.

    """
    ticket_code = request.session.get('open_ticket_code', None)
    try:
        del request.session['open_ticket_code']
    except KeyError:
        pass
    if request.POST or ticket_code:
        data = request.POST.copy()
        if ticket_code:
            data[u'code'] = ticket_code
        form = forms.RedeemTicketForm(data=data)
        if form.is_valid():
            if request.user.is_authenticated():
                ticket = form.save(commit=False, user=request.user)
                qualifies, reasons = ticket.campaign.is_user_qualified(request.user)
                if qualifies:
                    ticket.save()
                    _log.info('Ticket redeemed %s', ticket)
                    if ticket.amount:
                        request.user.message_set.create(message=_('Your $%.2f ticket has been redeemed. Thank you.' % ticket.amount))
                    else:
                        request.user.message_set.create(message=_('Your ticket has been redeemed. Thank you.'))
                    return HttpResponseRedirect(reverse('view_campaign', kwargs={'campaign_id':ticket.campaign.pk}))
                else:
                    # The logged-in user does not have all qualifying fields for
                    # the campaign whose ticket is being redeemed.
                    # Therefore, store the ticket code into the session and
                    # give the user a chance to fill out the qualifying fields.
                    request.session['open_ticket_code'] = form.cleaned_data['code']
                    return HttpResponseRedirect(reverse('qualify_for_campaign', kwargs={'campaign_id':ticket.campaign.pk}))
            else: # user not logged in
                request.session['open_ticket_code'] = form.cleaned_data['code']
                return HttpResponseRedirect("%s?next=%s" % (reverse('login'), reverse('redeem_ticket')))
    else:
        form = forms.RedeemTicketForm()
    ctx = {'form':form}
    return render_view(request, template, ctx)


@login_required
@transaction.commit_on_success
def payment_return(request, campaign_id, inv_id, success_code, payment_mode):
    """Process a return from PayPal's or Google's payment screen and redirect to the 
    campaign's detail view.

   ``inv_id`` is the id of a``PendingContribution``.
   ``success_code`` is 1 or 0 for successful or cancelled payments respectively.

    """
    campaign = get_object_or_404(Campaign, pk=campaign_id)
    if int(success_code) == 1:
        request.user.message_set.create(message=_('Thank you for your contribution.'))
    else:
        # User cancelled payment.
        request.user.message_set.create(message=_('Your payment has been cancelled.'))
        try:
            # Find ``PendingContribution`` and delete it.
            pc = PendingContribution.objects.get(pk=inv_id, campaign=campaign_id, contributor=request.user, payment_mode=payment_mode)
            pc.delete()
            _log.debug('Payment by %s was cancelled for %s', request.user.username, campaign)
        except PendingContribution.DoesNotExist:
            pass
    return HttpResponseRedirect(reverse('view_campaign', kwargs={'campaign_id':campaign.pk}))


def paypal_notification(request, payment_mode='paypal'):
    """Receive PayPal IPN (Instant Payment Notification.)"""
    try:
        data = request.POST
        _log.debug("PayPal IPN data: %s", repr(data))

        if not paypal.verify_ipn_request(request):
            return HttpResponse()

        if data.get('payment_status', None) != "Completed":
            # Do not insert payments whose status is not "Completed".
            _log.debug("Ignored IPN data for incomplete payment.")
            return HttpResponse()

        currency = data.get('mc_currency', settings.CURRENCY_DEFAULT)
        if currency.upper() not in settings.CURRENCIES_SUPPORTED:
            # We do not support anything other than USD.
            _log.debug("Ignored IPN data for unsupported currency %s", currency)
            return HttpResponse()

        pending_contribution_id, username = data['custom'].split('~') # pending_contrib_id~buyer's_username
        is_anon = username == 'anonymous'
        transaction_id = data['txn_id']
        qty = data['quantity']
        artist_email = data['receiver_email']
        campaign_id = data['item_number']
        amount = data['mc_gross']
        is_test = data.get('test_ipn', 0) == 1

        contribs = Contribution.objects.filter(transaction_id=transaction_id, payment_mode=payment_mode).count()
        if not contribs:
            # This transaction hasn't already been processed.
            # Process it and update the ``memo`` field if it has been provided by the buyer.
            if is_anon:
                _log.debug("Processing anonymous contribution")
                contributor = User.objects.get(username='anonymous')
                campaign = Campaign.objects.get(pk=campaign_id)
                contrib = campaign.contribution_set.create(
                    contributor=contributor,
                    amount=amount,
                    qty=qty,
                    payment_mode=payment_mode,
                    transaction_id=transaction_id,
                    memo=data.get('memo', '')
                )
                _log.info("PayPal (tx: %s) anonymous contribution recorded: %s", transaction_id, contrib)
            else:
                pending_contrib = PendingContribution.objects.get(pk=pending_contribution_id,
                                                contributor__username=username,
                                                campaign=campaign_id,
                                                amount=amount,
                                                qty=qty,
                                                payment_mode=payment_mode)
                if pending_contrib:
                    contrib = pending_contrib.process_payment_notification(transaction_id, data.get('memo', ''))
                    _log.info("PayPal transaction %s resolved. Contribution recorded: %s", transaction_id, contrib)
                else:
                    _log.error("PayPal transaction %s could not be resolved.", transaction_id)
    except:
        _log.exception(''.join(format_exception(*exc_info())))
    return HttpResponse()


def google_notification(request, payment_mode='google'):
    """Receive notification of a campaign payment completed via Google Checkout."""
    # ack_xml = '''<notification-acknowledgment xmlns="http://checkout.google.com/schema/2" serial-number="%s"/>\n\n'''
    ack_html = '''_type=notification-acknowledgment&serial-number=%s\n\n'''
    processed_response = None
    try:
        data = request.POST
        _log.debug("Google Checkout IPN Headers: %s", repr(request.META))
        _log.debug("Google Checkout IPN data: %s", repr(data))

        serial_number = data[u'serial-number'].strip()
        ack_html = ack_html % serial_number
        processed_response = HttpResponse(ack_html, content_type="text/plain")

        ipn_type = data[u'_type']
        if ipn_type not in [u'new-order-notification']:
            _log.debug("Ignored unsupported IPN type %s.", ipn_type)
            return processed_response

        order_state = data[u'fulfillment-order-state']
        if order_state.upper() not in [u'NEW']:
            _log.debug("Ignored unsupported order state %s", order_state)
            return processed_response

        currency = data.get(u'order-total.currency', settings.CURRENCY_DEFAULT)
        if currency.upper() not in settings.CURRENCIES_SUPPORTED:
            # We do not support any currency other than USD.
            _log.debug("Ignored unsupported currency %s", currency)
            return processed_response

        required_keys = (
            'shopping-cart.items.item-1.merchant-item-id',
            'shopping-cart.items.item-1.quantity',
            'shopping-cart.merchant-private-data',
            'order-total',
            'google-order-number',
        )
        for key in required_keys:
            if key not in data:
                # We do not support this type of a response
                _log.debug("Unsupported IPN. No %s", key)
                return processed_response

        try:
            pending_contribution_id, username, invoice_num = data[u'shopping-cart.merchant-private-data'].split('~')
        except ValueError:
            # This IPN is not meant for our application
            _log.debug("Unsupported IPN. No proper shopping-cart.merchant-private-data")
            return processed_response

        is_anon = username == 'anonymous'
        campaign_id = data[u'shopping-cart.items.item-1.merchant-item-id']
        qty = data[u'shopping-cart.items.item-1.quantity']
        amount = data[u'order-total']
        transaction_id = data[u'google-order-number']

        if not is_anon:
            try:
                pending_contrib = PendingContribution.objects.get(
                                            pk=pending_contribution_id,
                                            contributor__username=username,
                                            campaign=campaign_id,
                                            qty=qty,
                                            payment_mode=payment_mode)
            except PendingContribution.DoesNotExist:
                # We don't need to keep receiving this notification any more.
                _log.debug("Pending contribution not found. Locals: %s" % locals())
                return processed_response

        campaign = Campaign.objects.get(pk=campaign_id)

        if is_anon:
            artist = campaign.artist
        else:
            artist = pending_contrib.campaign.artist

        google_merchant_id, google_merchant_key = artist.google_merchant_id, artist.google_merchant_key

        if not (google_merchant_id or google_merchant_key):
            # This artist does not support Google Checkout payments
            _log.debug("Artist %s does not accept Google Checkout payments", artist)
            return processed_response

        if not google.verify_ipn_request(request, google_merchant_id, google_merchant_key):
            raise Http404

        contribs = Contribution.objects.filter(transaction_id=transaction_id, payment_mode=payment_mode).count()
        if contribs:
            # This payment was already processed. Just acknowledge the notification.
            _log.debug("Payment was already processed.")
            return processed_response

        # Process it and update the ``memo`` field if it has been provided by the buyer.
        if is_anon:
            # Anonymous contribution
            contributor = User.objects.get(username='anonymous')
            contrib = campaign.contribution_set.create(
                contributor=contributor,
                amount=amount,
                qty=qty,
                payment_mode=payment_mode,
                transaction_id=transaction_id,
                memo=data.get('memo', '')
            )
            _log.info("Google (tx: %s) anonymous contribution recorded: %s", transaction_id, contrib)
        else:
            # Member contribution
            contrib = pending_contrib.process_payment_notification(transaction_id, data.get('memo', ''))
            _log.info("Google transaction %s resolved. Contribution recorded: %s", transaction_id, contrib)
    except:
        _log.exception(''.join(format_exception(*exc_info())))
        raise Http404
    return processed_response

