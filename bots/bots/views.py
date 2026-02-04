"""
Bots Django views
"""
# pylint: disable=missing-class-docstring, missing-function-docstring, broad-exception-caught, consider-using-f-string
# pylint: disable=too-many-lines, too-many-branches, too-many-return-statements, too-many-statements

from base64 import b64encode
from datetime import datetime
import glob
from json.decoder import JSONDecodeError
import os
import socket
import subprocess
import time
import traceback

import django
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required, user_passes_test
from django.core.mail import mail_managers
from django.shortcuts import get_object_or_404, Http404
from django.utils.safestring import mark_safe
from django.views.decorators.csrf import requires_csrf_token
from lxml.etree import XMLSyntaxError

from . import (
    botsglobal,
    botslib,
    forms,
    grammar,
    job2queue,
    models,
    pluglib,
    py2html,
    viewlib,
)
from .botsconfig import (
    ERROR,
    EXTERNIN,
    EXTERNOUT,
    FILEIN,
    MERGED,
    NO_RETRY,
    OPEN,
    PROCESS,
    RESEND,
    SPLITUP,
    TRANSLATED,
)
from .bots_context import set_context
from .botslib import gettext as _
from .exceptions import BotsError, PluginError, txtexc


ERROR_500_TEMPLATE_NAME = '500.html'

IS_POPUP_VAR = 'popup'


@requires_csrf_token
def server_error(request, template_name=ERROR_500_TEMPLATE_NAME):
    """
    The 500 error handler.
    Templates: `500.html`
    Context: None
    """
    exc_info = traceback.format_exc(None)
    botsglobal.logger.error(_('Ran into server error: "%(error)s"'), {'error': exc_info})
    try:
        template = django.template.loader.get_template(template_name)
    except django.template.exceptions.TemplateDoesNotExist:
        if template_name != ERROR_500_TEMPLATE_NAME:
            # Reraise if it's a missing custom template.
            raise
        return django.http.HttpResponseServerError(
            '<h1>Server Error (500)</h1>', content_type='text/html')

    context = {}
    if botsglobal.ini.get('webserver', 'debug', False) == 'True':
        context['exc_info'] = exc_info
    context.update(set_context(request))
    return django.http.HttpResponseServerError(template.render(context))


def index(request):
    """
    when using eg http://localhost:8080
    index can be reached without being logged in.
    most of the time user is redirected to '/home'
    """
    return django.shortcuts.render(request, 'admin/base.html')


@login_required
def home(request):
    """Display bots environment infos"""
    return django.shortcuts.render(request, 'bots/about.html', {'botsinfo': botslib.botsinfo()})


@login_required
@permission_required('bots.view_report', login_url='/')
def reports(request):
    context = {
        'title': _('Reports'),
        'verbose_name': _('Report'),
        'verbose_name_plural': _('Reports'),
    }
    if request.method == 'GET':
        if IS_POPUP_VAR in request.GET:
            context['is_popup'] = True
        cleaned_data = viewlib.load_selection(request, forms.SelectReports)
        if cleaned_data:
            cleaned_data.update(request.GET.items())
            if cleaned_data.get(IS_POPUP_VAR):
                context['is_popup'] = True
            context['form'] = formin = forms.SelectReports(cleaned_data, request=request)
            if 'select' in request.GET or not formin.is_valid():
                return django.shortcuts.render(request, formin.template, context)
            cleaned_data = formin.cleaned_data

        elif 'select' in request.GET:
            # from menu:select->reports
            context['form'] = form = forms.SelectReports(request=request)
            if len(request.GET) > 1:
                form.initial.update(form.initials)
                form.initial.update(request.GET.items())
                context['form'] = form = forms.SelectReports(form.initial, request=request)
                form.is_valid()
            # go to the SelectReports form
            return django.shortcuts.render(request, form.template, context)

        else:
            # from menu:run->report
            context['form'] = form = forms.ViewReports(request=request)
            cleaned_data = form.initials
            if len(request.GET) > 0:
                form.initial.update(form.initials)
                form.initial.update(request.GET.items())
                context['form'] = formin = forms.ViewReports(form.initial, request=request)
                if not formin.is_valid():
                    return django.shortcuts.render(request, formin.template, context)
                cleaned_data = formin.cleaned_data
        # go to default report-query

    else:
        # request.method == 'POST'
        # is_popup
        if request.POST.get(IS_POPUP_VAR):
            context['is_popup'] = True

        # selection from selectform
        if request.POST.get('selection_name') \
                or 'saveselection' in request.POST \
                or 'deleteselection' in request.POST:
            # from SelectReports form
            context['form'] = formin = forms.SelectReports(request.POST, request=request)
            if not formin.is_valid():
                return django.shortcuts.render(request, formin.template, context)
            if 'deleteselection' in request.POST:
                # delete selection
                viewlib.delete_selection(formin)
            else:
                # Save selection
                viewlib.save_selection(formin)
            if "fromselect" not in request.POST:
                context['form'] = form = forms.SelectReports(formin.cleaned_data, request=request)
                return django.shortcuts.render(request, form.template, context)
        else:
            # from ViewReports form
            context['form'] = formin = forms.ViewReports(request.POST, request=request)

        if not formin.is_valid():
            return django.shortcuts.render(request, formin.template, context)

        if '2select' in request.POST:
            # from ViewReports form using button change selection
            context['form'] = form = forms.SelectReports(formin.cleaned_data, request=request)
            return django.shortcuts.render(request, form.template, context)
        if 'permlink' in request.POST:
            # Redirect to permanent url
            return django.shortcuts.redirect(viewlib.get_selection_url(formin))

        action, idtas = None, []
        if 'action' in request.POST and request.POST.get('actions'):
            action = request.POST.get('actions')
            idtas = [viewlib.safe_int(i) for i in request.POST.getlist('sel')]
        elif request.POST.get('delete'):
            action = 'delete'
            idtas = [viewlib.safe_int(request.POST['delete'])]

        if action == 'delete' and idtas:
            if request.user.has_perm('bots.delete_report'):
                for idta in idtas:
                    # delete report > filereports > tas
                    get_object_or_404(models.report, idta=idta).delete()
                txt = _('Reports deleted: %s') % idtas
                botsglobal.logger.info(txt)
                messages.add_message(request, messages.INFO, txt)
            else:
                warn = _('User %(user)s try to perform unauthorised request: %(request)s') % {
                    'user': request.user, 'request': request.POST}
                botsglobal.logger.warning(warn)

        # from ViewReports, next page etc
        viewlib.handlepagination(request.POST, formin)
        cleaned_data = formin.cleaned_data

    # normal report-query with parameters
    query = models.report.objects.all()
    context['queryset'] = viewlib.filterquery(query, cleaned_data, context=context)
    context['form'] = form = forms.ViewReports(initial=cleaned_data, request=request)
    return django.shortcuts.render(request, form.template, context)


@login_required
@permission_required('bots.view_filereport', login_url='/')
def incoming(request):
    """
    Incoming view
    """
    context = {
        'title': _('Incoming'),
        'verbose_name': _('Incoming'),
        'verbose_name_plural': _('Incomings'),
    }
    if request.method == 'GET':
        if IS_POPUP_VAR in request.GET:
            context['is_popup'] = True
        cleaned_data = viewlib.load_selection(request, forms.SelectIncoming)
        if cleaned_data:
            cleaned_data.update(request.GET.items())
            if cleaned_data.get(IS_POPUP_VAR):
                context['is_popup'] = True
            context['form'] = formin = forms.SelectIncoming(cleaned_data, request=request)
            if 'select' in request.GET or not formin.is_valid():
                return django.shortcuts.render(request, formin.template, context)
            cleaned_data = formin.cleaned_data

        elif 'select' in request.GET:
            # from menu:select->incoming
            context['form'] = form = forms.SelectIncoming(request=request)
            if len(request.GET) > 1:
                form.initial.update(form.initials)
                form.initial.update(request.GET.items())
                context['form'] = form = forms.SelectIncoming(form.initial, request=request)
                form.is_valid()
            # go to the SelectIncoming form
            return django.shortcuts.render(request, form.template, context)

        else:
            # from menu:run->incoming
            context['form'] = form = forms.ViewIncoming(request=request)
            cleaned_data = form.initials
            if len(request.GET) > 0:
                form.initial.update(form.initials)
                form.initial.update(request.GET.items())
                context['form'] = formin = forms.ViewIncoming(form.initial, request=request)
                if not formin.is_valid():
                    return django.shortcuts.render(request, formin.template, context)
                cleaned_data = formin.cleaned_data
        # go to default incoming-query using these default parameters

    else:
        # request.method == 'POST'

        # is_popup
        if request.POST.get(IS_POPUP_VAR):
            context['is_popup'] = True

        # selection
        if request.POST.get('selection_name') \
                or 'saveselection' in request.POST \
                or 'deleteselection' in request.POST:
            # from SelectIncoming form
            context['form'] = formin = forms.SelectIncoming(request.POST, request=request)
            if not formin.is_valid():
                return django.shortcuts.render(request, formin.template, context)
            if 'deleteselection' in request.POST:
                # delete selection
                viewlib.delete_selection(formin)
            else:
                # Save selection
                viewlib.save_selection(formin)
            if "fromselect" not in request.POST:
                context['form'] = form = forms.SelectIncoming(formin.cleaned_data, request=request)
                return django.shortcuts.render(request, form.template, context)

        else:
            # from ViewIncoming form, check this form first
            context['form'] = formin = forms.ViewIncoming(request.POST, request=request)

        if not formin.is_valid():
            return django.shortcuts.render(request, formin.template, context)

        if '2select' in request.POST:
            # from ViewIncoming form using button change selection
            context['form'] = form = forms.SelectIncoming(formin.cleaned_data, request=request)
            return django.shortcuts.render(request, form.template, context)
        if '2outgoing' in request.POST:
            # from ViewIncoming form, using button 'outgoing (same selection)'
            request.POST = viewlib.changepostparameters(request.POST, soort='in2out')
            return outgoing(request)
        if '2process' in request.POST:
            # from ViewIncoming form, using button 'process errors (same selection)'
            request.POST = viewlib.changepostparameters(request.POST, soort='2process')
            return process(request)
        if '2confirm' in request.POST:
            # from ViewIncoming form, using button 'confirm (same selection)'
            request.POST = viewlib.changepostparameters(request.POST, soort='in2confirm')
            return confirm(request)
        if '2report' in request.POST:
            # from ViewIncoming form, using button 'reports (same selection)'
            request.POST = viewlib.changepostparameters(request.POST, soort='in2report')
            return reports(request)
        if 'permlink' in request.POST:
            # get selection permanent url
            return django.shortcuts.redirect(viewlib.get_selection_url(formin))

        action, idtas = None, []
        if 'action' in request.POST and request.POST.get('actions'):
            action = request.POST.get('actions')
            idtas = [viewlib.safe_int(i) for i in request.POST.getlist('sel')]
        elif request.POST.get('delete'):
            action = 'delete'
            idtas = [viewlib.safe_int(request.POST['delete'])]
        elif 'rereceive' in request.POST:
            action = 'rereceive'
            idtas = [viewlib.safe_int(request.POST['rereceive'])]

        if action == 'delete' and idtas:
            if request.user.has_perm('bots.delete_filereport'):
                for idta in idtas:
                    # delete filereport
                    get_object_or_404(models.filereport, idta=idta).delete()
                txt = _('Filereports deleted: %s') % idtas
                botsglobal.logger.info(txt)
                messages.add_message(request, messages.INFO, txt)
            else:
                warn = _('User %(user)s try to perform unauthorised request: %(request)s') % {
                    'user': request.user, 'request': request.POST}
                botsglobal.logger.warning(warn)

        elif action == 'rereceive':
            if request.user.has_perm('bots.change_mutex'):
                for idta in idtas:
                    filereport = get_object_or_404(models.filereport, idta=idta)
                    if filereport.fromchannel:
                        # for resend files fromchannel has no value.
                        # (do not rereceive resend items)
                        filereport.retransmit = not filereport.retransmit
                        filereport.save()
            else:
                notification = _('No rights for this operation.')
                botsglobal.logger.info(notification)
                messages.add_message(request, messages.ERROR, notification)

        elif 'rereceiveall' in request.POST:
            if request.user.has_perm('bots.change_mutex'):
                # from ViewIncoming form using button 'rereceive all'
                # select all objects with parameters and set retransmit
                query = models.filereport.objects.all()
                incomingfiles = viewlib.filterquery(query, formin.cleaned_data, paginate=False)
                # for resend files fromchannel has no value.
                # (do not rereceive resend items)
                for incomingfile in incomingfiles:
                    if incomingfile.fromchannel:
                        incomingfile.retransmit = not incomingfile.retransmit
                        incomingfile.save()
            else:
                warn = _('User %(user)s try to perform unauthorised request: %(request)s') % {
                    'user': request.user, 'request': request.POST}
                botsglobal.logger.warning(warn)

        # from ViewIncoming, next page etc
        viewlib.handlepagination(request.POST, formin)
        cleaned_data = formin.cleaned_data

    # normal incoming-query with parameters
    query = models.filereport.objects.all()
    context['queryset'] = viewlib.filterquery(query, cleaned_data, incoming=True, context=context)
    context['form'] = form = forms.ViewIncoming(initial=cleaned_data, request=request)
    if cleaned_data.get('lastrun'):
        context['title'] += ' - lastrun'
    return django.shortcuts.render(request, form.template, context)


@login_required
@permission_required('bots.view_filereport', login_url='/')
def outgoing(request):
    """
    Outgoing view
    """
    # pylint: disable=too-many-nested-blocks
    context = {
        'title': _('Outgoing'),
        'verbose_name': _('Outgoing'),
        'verbose_name_plural': _('Outgoings'),
    }
    if request.method == 'GET':
        if IS_POPUP_VAR in request.GET:
            context['is_popup'] = True
        cleaned_data = viewlib.load_selection(request, forms.SelectOutgoing)
        if cleaned_data:
            cleaned_data.update(request.GET.items())
            if cleaned_data.get(IS_POPUP_VAR):
                context['is_popup'] = True
            context['form'] = formin = forms.SelectOutgoing(cleaned_data, request=request)
            if 'select' in request.GET or not formin.is_valid():
                return django.shortcuts.render(request, formin.template, context)
            cleaned_data = formin.cleaned_data

        elif 'select' in request.GET:
            # from menu:select->outgoing
            context['form'] = form = forms.SelectOutgoing(request=request)
            if len(request.GET) > 1:
                form.initial.update(form.initials)
                form.initial.update(request.GET.items())
                context['form'] = form = forms.SelectOutgoing(form.initial, request=request)
                form.is_valid()
            return django.shortcuts.render(request, form.template, context)

        else:
            # from menu:run->outgoing
            context['form'] = form = forms.ViewOutgoing(request=request)
            cleaned_data = form.initials
            if len(request.GET) > 0:
                form.initial.update(form.initials)
                form.initial.update(request.GET.items())
                context['form'] = formin = forms.ViewOutgoing(form.initial, request=request)
                if not formin.is_valid():
                    return django.shortcuts.render(request, formin.template, context)
                cleaned_data = formin.cleaned_data
        # go to default outgoing-query using these default parameters

    else:
        # request.method == 'POST'

        # is_popup
        if request.POST.get(IS_POPUP_VAR):
            context['is_popup'] = True

        # selection
        if request.POST.get('selection_name') \
                or 'saveselection' in request.POST \
                or 'deleteselection' in request.POST:
            # from SelectOutgoing form
            context['form'] = formin = forms.SelectOutgoing(request.POST, request=request)
            if not formin.is_valid():
                return django.shortcuts.render(request, formin.template, context)
            if 'deleteselection' in request.POST:
                # delete selection
                viewlib.delete_selection(formin)
            else:
                # Save selection
                viewlib.save_selection(formin)
            if "fromselect" not in request.POST:
                context['form'] = form = forms.SelectOutgoing(formin.cleaned_data, request=request)
                return django.shortcuts.render(request, form.template, context)
        else:
            # from ViewOutgoing form, check this form first
            context['form'] = formin = forms.ViewOutgoing(request.POST, request=request)

        if not formin.is_valid():
            return django.shortcuts.render(request, formin.template, context)

        if '2select' in request.POST:
            # from ViewOutgoing form using button change selection
            context['form'] = form = forms.SelectOutgoing(formin.cleaned_data, request=request)
            return django.shortcuts.render(request, form.template, context)
        if '2incoming' in request.POST:
            # from ViewOutgoing form, using button 'incoming (same selection)'
            request.POST = viewlib.changepostparameters(request.POST, soort='out2in')
            return incoming(request)
        if '2process' in request.POST:
            # from ViewOutgoing form, using button 'process errors (same selection)'
            request.POST = viewlib.changepostparameters(request.POST, soort='2process')
            return process(request)
        if '2confirm' in request.POST:
            # from ViewOutgoing form, using button 'confirm (same selection)'
            request.POST = viewlib.changepostparameters(request.POST, soort='out2confirm')
            return confirm(request)
        if 'permlink' in request.POST:
            # Redirect to permanent url
            return django.shortcuts.redirect(viewlib.get_selection_url(formin))

        if request.user.has_perm('bots.change_mutex'):
            action, idtas = None, []
            if 'action' in request.POST and request.POST.get('actions'):
                action = request.POST.get('actions')
                idtas = [viewlib.safe_int(i) for i in request.POST.getlist('sel')]
            elif 'resend' in request.POST:
                action = 'resend'
                idtas = [viewlib.safe_int(request.POST['resend'])]
            elif 'noautomaticretry' in request.POST:
                action = 'noautomaticretry'
                idtas = [viewlib.safe_int(request.POST['noautomaticretry'])]
            if action and idtas:
                if action == 'resend':
                    for idta in idtas:
                        ta_object = get_object_or_404(models.ta, idta=idta)
                        if ta_object.statust != RESEND:
                            # can only resend last file
                            ta_object.retransmit = not ta_object.retransmit
                            ta_object.save()
                elif action == 'noautomaticretry':
                    for idta in idtas:
                        ta_object = get_object_or_404(models.ta, idta=idta)
                        if ta_object.statust == ERROR:
                            ta_object.statust = NO_RETRY
                            ta_object.save()

            elif 'resendall' in request.POST:
                # from ViewOutgoing form using button 'resend all'
                # select all objects with parameters and set retransmit
                query = models.ta.objects.filter(status=EXTERNOUT)
                outgoingfiles = viewlib.filterquery(query, formin.cleaned_data, paginate=False)
                for outgoingfile in outgoingfiles:
                    # can only resend last file
                    if outgoingfile.statust != RESEND:
                        outgoingfile.retransmit = not outgoingfile.retransmit
                        outgoingfile.save()

        # from ViewIncoming, next page etc
        viewlib.handlepagination(request.POST, formin)
        cleaned_data = formin.cleaned_data

    # normal outgoing-query with parameters
    query = models.ta.objects.filter(status=EXTERNOUT)
    context['queryset'] = viewlib.filterquery(query, cleaned_data, context=context)
    context['form'] = form = forms.ViewOutgoing(initial=cleaned_data, request=request)
    if cleaned_data.get('lastrun'):
        context['title'] += ' - lastrun'
    return django.shortcuts.render(request, form.template, context)


@login_required
@permission_required('bots.view_ta', login_url='/')
def document(request):
    context = {
        'title': _('Documents'),
        'verbose_name': _('Document'),
        'verbose_name_plural': _('Documents'),
    }
    if request.method == 'GET':
        if IS_POPUP_VAR in request.GET:
            context['is_popup'] = True
        cleaned_data = viewlib.load_selection(request, forms.SelectDocument)
        if cleaned_data:
            cleaned_data.update(request.GET.items())
            if cleaned_data.get(IS_POPUP_VAR):
                context['is_popup'] = True
            context['form'] = formin = forms.SelectDocument(cleaned_data, request=request)
            if 'select' in request.GET or not formin.is_valid():
                return django.shortcuts.render(request, formin.template, context)
            cleaned_data = formin.cleaned_data

        elif 'select' in request.GET:
            # from menu:select->document
            context['form'] = form = forms.SelectDocument(request=request)
            if len(request.GET) > 1:
                form.initial.update(form.initials)
                form.initial.update(request.GET.items())
                context['form'] = form = forms.SelectDocument(form.initial, request=request)
                form.is_valid()
            return django.shortcuts.render(request, form.template, context)

        else:
            context['form'] = form = forms.ViewDocument(request=request)
            cleaned_data = form.initials
            if len(request.GET) > 0:
                form.initial.update(form.initials)
                form.initial.update(request.GET.items())
                context['form'] = formin = forms.ViewDocument(form.initial, request=request)
                if not formin.is_valid():
                    return django.shortcuts.render(request, formin.template, context)
                cleaned_data = formin.cleaned_data
        # go to default document-query using these default parameters

    else:
        # request.method == 'POST'

        # is_popup
        if request.POST.get(IS_POPUP_VAR):
            context['is_popup'] = True

        # selection
        if request.POST.get('selection_name') \
                or 'saveselection' in request.POST \
                or 'deleteselection' in request.POST:
            # from SelectDocument form
            formin = forms.SelectDocument(request.POST, request=request)
            if not formin.is_valid():
                context['form'] = formin
                return django.shortcuts.render(request, formin.template, context)
            if 'deleteselection' in request.POST:
                # delete selection
                viewlib.delete_selection(formin)
            else:
                # Save selection
                viewlib.save_selection(formin)
            if "fromselect" not in request.POST:
                context['form'] = form = forms.SelectDocument(formin.cleaned_data, request=request)
                return django.shortcuts.render(request, form.template, context)

        else:
            # from ViewDocument form, check this form first
            context['form'] = formin = forms.ViewDocument(request.POST, request=request)

        if not formin.is_valid():
            return django.shortcuts.render(request, formin.template, context)

        if '2select' in request.POST:
            # coming from ViewDocument, change the selection criteria, go to select form
            context['form'] = form = forms.SelectDocument(formin.cleaned_data, request=request)
            return django.shortcuts.render(request, form.template, context)
        if 'permlink' in request.POST:
            # Redirect to permanent url
            return django.shortcuts.redirect(viewlib.get_selection_url(formin))

        if 'rereceive' in request.POST and request.user.has_perm('bots.change_mutex'):
            # coming from ViewDocument, no reportidta
            idta = request.POST['rereceive']
            rootta = viewlib.django_trace_origin(viewlib.safe_int(idta), {'status': EXTERNIN})
            if rootta:
                filereport = get_object_or_404(models.filereport, idta=rootta[0].idta)
                filereport.retransmit = not filereport.retransmit
                filereport.save()

        # coming from ViewDocument, next page etc
        viewlib.handlepagination(request.POST, formin)
        cleaned_data = formin.cleaned_data

    if cleaned_data.get('allstatus'):
        # All ta in query except PROCESS
        query = models.ta.objects.exclude(status=PROCESS)
    else:
        # normal document-query with parameters
        query = models.ta.objects.filter(
            django.db.models.Q(status=SPLITUP) | django.db.models.Q(status=TRANSLATED)
        )
    context['queryset'] = pquery = viewlib.filterquery(query, cleaned_data, context=context)
    viewlib.trace_document(pquery)
    context['form'] = form = forms.ViewDocument(initial=cleaned_data, request=request)
    if cleaned_data.get('status'):
        # pylint: disable=protected-access
        for choice in form.fields['status']._choices:
            if choice[0] == cleaned_data.get('status'):
                context['title'] = choice[1]
                break
    if cleaned_data.get('lastrun'):
        context['title'] += ' - lastrun'
    return django.shortcuts.render(request, form.template, context)


@login_required
@permission_required('bots.view_filereport', login_url='/')
def process(request):
    context = {
        'verbose_name': _('Process Errors'),
        'verbose_name_plural': _('Processes Errors'),
    }
    context['title'] = context['verbose_name']
    if request.method == 'GET':
        if IS_POPUP_VAR in request.GET:
            context['is_popup'] = True
        cleaned_data = viewlib.load_selection(request, forms.SelectProcess)
        if cleaned_data:
            cleaned_data.update(request.GET.items())
            if cleaned_data.get(IS_POPUP_VAR):
                context['is_popup'] = True
            context['form'] = formin = forms.SelectProcess(cleaned_data, request=request)
            if 'select' in request.GET or not formin.is_valid():
                return django.shortcuts.render(request, formin.template, context)
            cleaned_data = formin.cleaned_data

        elif 'select' in request.GET:
            # from menu:select->process
            context['form'] = form = forms.SelectProcess(request=request)
            if len(request.GET) > 1:
                form.initial.update(form.initials)
                form.initial.update(request.GET.items())
                context['form'] = form = forms.SelectProcess(form.initial, request=request)
                form.is_valid()
            return django.shortcuts.render(request, form.template, context)

        else:
            # from menu: process->Errors
            context['form'] = form = forms.ViewProcess(request=request)
            cleaned_data = form.initials
            if len(request.GET) > 0:
                form.initial.update(form.initials)
                form.initial.update(request.GET.items())
                context['form'] = formin = forms.ViewProcess(form.initial, request=request)
                if not formin.is_valid():
                    return django.shortcuts.render(request, formin.template, context)
                cleaned_data = formin.cleaned_data
        # go to default process-query using these default parameters

    else:
        # request.method == 'POST'

        # is_popup
        if request.POST.get(IS_POPUP_VAR):
            context['is_popup'] = True

        # selection
        if request.POST.get('selection_name') \
                or 'saveselection' in request.POST \
                or 'deleteselection' in request.POST:
            # from SelectProcess form
            context['form'] = formin = forms.SelectProcess(request.POST, request=request)
            if not formin.is_valid():
                return django.shortcuts.render(request, formin.template, context)
            if 'deleteselection' in request.POST:
                # delete selection
                viewlib.delete_selection(formin)
            else:
                # Save selection
                viewlib.save_selection(formin)
            if "fromselect" not in request.POST:
                context['form'] = form = forms.SelectProcess(formin.cleaned_data, request=request)
                return django.shortcuts.render(request, form.template, context)
        else:
            # from ViewProcess form, check this form first
            context['form'] = formin = forms.ViewProcess(request.POST, request=request)

        if not formin.is_valid():
            return django.shortcuts.render(request, formin.template, context)

        if '2select' in request.POST:
            # coming from ViewProcess, change the selection criteria, go to select form
            context['form'] = form = forms.SelectProcess(formin.cleaned_data, request=request)
            return django.shortcuts.render(request, form.template, context)
        if '2incoming' in request.POST:
            # coming from ViewProcess, go to incoming form using same criteria
            request.POST = viewlib.changepostparameters(request.POST, soort='fromprocess')
            return incoming(request)
        if '2outgoing' in request.POST:
            # coming from ViewProcess, go to outgoing form using same criteria
            request.POST = viewlib.changepostparameters(request.POST, soort='fromprocess')
            return outgoing(request)
        if 'permlink' in request.POST:
            # Redirect to permanent url
            return django.shortcuts.redirect(viewlib.get_selection_url(formin))

        # coming from ViewProcess
        viewlib.handlepagination(request.POST, formin)
        cleaned_data = formin.cleaned_data

    # normal process-query with parameters
    query = models.ta.objects.filter(status=PROCESS, statust=ERROR)
    context['queryset'] = viewlib.filterquery(query, cleaned_data, context=context)
    context['form'] = form = forms.ViewProcess(initial=cleaned_data, request=request)
    return django.shortcuts.render(request, form.template, context)


@login_required
@permission_required('bots.view_ta', login_url='/')
def detail(request):
    """
    in: the idta, either as parameter in or out.
    in: is idta of incoming file.
    out: idta of outgoing file, need to trace back for incoming file.
    return list of ta's for display in detail template.
    This list is formatted and ordered for display.
    first, get a tree (trace) starting with the incoming ta ;
    than make up the details for the trace
    """
    if request.method == 'GET':
        rootta = None
        if 'inidta' in request.GET:
            # from incoming screen
            rootta = get_object_or_404(
                models.ta.objects, idta=viewlib.safe_int(request.GET['inidta'])
            )
        elif request.GET.get('outidta'):
            # from outgoing screen: trace back to EXTERNIN first
            rootta = viewlib.django_trace_origin(
                viewlib.safe_int(request.GET['outidta']), {'status': EXTERNIN}
            )
            if rootta:
                rootta = rootta[0]
        if not rootta:
            raise Http404()
        viewlib.gettrace(rootta)
        detaillist = viewlib.trace2detail(rootta)
        channels = {ta.channel for ta in detaillist}
        channels_types = {
            channel.idchannel: channel.type
            for channel in models.channel.objects.filter(idchannel__in=channels)
        }
        context = {
            'detaillist': detaillist,
            'rootta': rootta,
            'title': _("Details") + f" {rootta.idta}",
            'partners': models.getactivepartners(),
            'inactive_partners': models.getinactivepartners(),
            'channels_types': channels_types,
        }
        if IS_POPUP_VAR in request.GET:
            context['is_popup'] = True
        if 'admlink' in request.GET:
            context['admlink'] = True
        return django.shortcuts.render(request, 'bots/detail.html', context)
    return django.shortcuts.redirect("bots:home")


@login_required
@permission_required('bots.view_ta', login_url='/')
def confirm(request):
    """
    Confirmations view
    """
    # pylint: disable=too-many-nested-blocks
    context = {
        'title': _('Confirmations'),
        'verbose_name': _('Confirmation'),
        'verbose_name_plural': _('Confirmations'),
    }
    if request.method == 'GET':
        if IS_POPUP_VAR in request.GET:
            context['is_popup'] = True
        cleaned_data = viewlib.load_selection(request, forms.SelectConfirm)
        if cleaned_data:
            cleaned_data.update(request.GET.items())
            if cleaned_data.get(IS_POPUP_VAR):
                context['is_popup'] = True
            context['form'] = formin = forms.SelectConfirm(cleaned_data, request=request)
            if 'select' in request.GET or not formin.is_valid():
                return django.shortcuts.render(request, formin.template, context)
            cleaned_data = formin.cleaned_data

        elif 'select' in request.GET:
            # from menu:select->confirm
            context['form'] = form = forms.SelectConfirm(request=request)
            if len(request.GET) > 1:
                form.initial.update(form.initials)
                form.initial.update(request.GET.items())
                context['form'] = form = forms.SelectConfirm(form.initial, request=request)
                form.is_valid()
            return django.shortcuts.render(request, form.template, context)

        else:
            # from menu:run->confirm
            context['form'] = form = forms.ViewConfirm(request=request)
            cleaned_data = form.initials
            if len(request.GET) > 0:
                form.initial.update(form.initials)
                form.initial.update(request.GET.items())
                context['form'] = formin = forms.ViewConfirm(form.initial, request=request)
                if not formin.is_valid():
                    return django.shortcuts.render(request, formin.template, context)
                cleaned_data = formin.cleaned_data
                cleaned_data['confirmed'] = formin.cleaned_data['confirmed'] or ''
        # go to default confirm-query using these default parameters

    else:
        # request.method == 'POST'

        # is_popup
        if request.POST.get(IS_POPUP_VAR):
            context['is_popup'] = True

        # save/delete selection
        if request.POST.get('selection_name') \
                or 'saveselection' in request.POST \
                or 'deleteselection' in request.POST:
            # from SelectConfirm form
            context['form'] = formin = forms.SelectConfirm(request.POST, request=request)
            if not formin.is_valid():
                return django.shortcuts.render(request, formin.template, context)
            if 'deleteselection' in request.POST:
                # delete selection
                viewlib.delete_selection(formin)
            else:
                # Save selection
                viewlib.save_selection(formin)
            if "fromselect" not in request.POST:
                context['form'] = form = forms.SelectConfirm(formin.cleaned_data, request=request)
                return django.shortcuts.render(request, form.template, context)
        else:
            context['form'] = formin = forms.ViewConfirm(request.POST, request=request)

        # from ViewConfirm form, check this form first
        if not formin.is_valid():
            return django.shortcuts.render(request, formin.template, context)

        if '2select' in request.POST:
            # coming from ViewConfirm, change the selection criteria, go to select form
            context['form'] = form = forms.SelectConfirm(formin.cleaned_data, request=request)
            return django.shortcuts.render(request, form.template, context)
        if '2incoming' in request.POST:
            # coming from ViewConfirm, go to incoming form using same criteria
            request.POST = viewlib.changepostparameters(request.POST, soort='confirm2in')
            return incoming(request)
        if '2outgoing' in request.POST:
            # coming from ViewConfirm, go to outgoing form using same criteria
            request.POST = viewlib.changepostparameters(request.POST, soort='confirm2out')
            return outgoing(request)
        if 'permlink' in request.POST:
            # Redirect to permanent url
            return django.shortcuts.redirect(viewlib.get_selection_url(formin))

        action, idtas = None, []
        if 'action' in request.POST and request.POST.get('actions'):
            action = request.POST.get('actions')
            idtas = [viewlib.safe_int(i) for i in request.POST.getlist('sel')]
        elif 'confirm' in request.POST:
            action = 'confirm'
            idtas = [viewlib.safe_int(request.POST['confirm'])]
        if action == 'confirm':
            if request.user.has_perm('bots.change_ta'):
                confirmed = []
                impossible = []
                for idta in idtas:
                    ta_object = get_object_or_404(models.ta, idta=idta)
                    if not ta_object.confirmidta and ta_object.confirmtype.startswith('ask'):
                        ta_object.confirmed = True
                        # to indicate a manual confirmation
                        ta_object.confirmidta = '-1'
                        ta_object.save()
                        confirmed.append(idta)
                    else:
                        impossible.append(idta)
                if confirmed:
                    messages.add_message(
                        request, messages.INFO, _("Manual confirmed: %s") % str(confirmed)[1:-1])
                if impossible:
                    messages.add_message(
                        request,
                        messages.ERROR,
                        _("Manual confirm not possible: %s") % str(impossible)[1:-1],
                    )

        # coming from ViewConfirm, next page etc
        viewlib.handlepagination(request.POST, formin)
        cleaned_data = formin.cleaned_data

    # normal confirm-query with parameters
    query = models.ta.objects.filter(confirmasked=True)
    context['queryset'] = viewlib.filterquery(query, cleaned_data, context=context)
    context['form'] = form = forms.ViewConfirm(initial=cleaned_data, request=request)
    if cleaned_data.get('confirmidta') == -1:
        context['title'] += ' - %s' % _('Manual')
    elif cleaned_data.get('confirmidta'):
        context['title'] += ': %s' % cleaned_data.get('confirmidta')
    elif cleaned_data.get('confirmidta') == 0:
        context['title'] += ' - %s' % _('Pending ...')
    elif cleaned_data.get('confirmed') == '0':
        context['title'] += ' - %s' % _('Unconfirmed')
    elif cleaned_data.get('confirmed') == '1':
        context['title'] += ' - %s' % _('Confirmed')
    return django.shortcuts.render(request, form.template, context)


@login_required
@permission_required('bots.view_ta', login_url='/')
def filer(request):
    """
    handles bots file viewer.
    Only files in data dir of Bots are displayed.
    """
    # pylint: disable=too-many-nested-blocks, too-many-locals
    context = {
        'title': _('Bots Filer'),
    }
    if request.method == 'GET':
        currentta = get_object_or_404(models.ta, idta=request.GET.get('idta'))
        formin = forms.FilerForm(request=request)
        formin.initial.update(formin.initials)
        if len(request.GET) > 0:
            formin.initial.update(request.GET.items())
        context['form'] = formin = forms.FilerForm(formin.initial, ta=currentta, request=request)
    else:
        currentta = get_object_or_404(models.ta, idta=request.POST.get('idta'))
        context['form'] = formin = forms.FilerForm(request.POST, ta=currentta, request=request)

    if not formin.is_valid():
        return django.shortcuts.render(request, formin.template, context)

    cleaned_data = formin.cleaned_data

    try:
        # Download
        if cleaned_data['action'] == 'downl':
            ext = '.txt'
            if currentta.editype == 'edifact' or currentta.contenttype == 'application/edifact':
                ext = '.edi'
            elif currentta.editype == 'x12':
                ext = '.x12'
            elif currentta.editype in ['xml', 'xmlnocheck'] \
                    or currentta.contenttype in ['text/xml', 'application/xml']:
                ext = '.xml'
            elif currentta.editype in ['json', 'jsonnocheck'] \
                    or currentta.contenttype == 'application/json':
                ext = '.json'
            elif currentta.contenttype == 'text/html':
                ext = '.html'
            elif currentta.contenttype == 'application/pdf':
                ext = '.pdf'
            elif currentta.editype == 'csv':
                ext = '.csv'
            elif currentta.editype == 'idoc':
                ext = '.idoc'
            elif currentta.editype == 'excel':
                ext = '.xls'

            # filename
            filename = currentta.filename + ext
            if currentta.status == EXTERNIN:
                filename = os.path.basename(currentta.filename)
                # EXTERNIN has no file, so go to first FILEIN
                currentta = models.ta.objects.filter(parent=currentta.idta).first()
            elif currentta.status == FILEIN and currentta.divtext:
                # email attachment filename
                filename = currentta.divtext
            elif currentta.status == EXTERNOUT:
                filename = os.path.basename(currentta.filename)
                # EXTERNOUT has no file, so go to last FILEOUT
                currentta = models.ta.objects.filter(idta=currentta.parent).first()
            if currentta.contenttype in ["message/rfc822", "multipart/mixed"] and currentta.reference:
                # email (s)mime
                filename = f"{currentta.reference.strip('<>')}.eml"

            # botsglobal.logger.debug('Downloaded filename: %s', currentta.filename)
            response = django.http.HttpResponse(content_type=currentta.contenttype)
            dispositiontype = "attachment"
            response["Content-Disposition"] = f"{dispositiontype}; filename={filename}"
            # response["Content-Length"] = os.path.getsize(absfilename)
            response.write(botslib.readdata_bin(currentta.filename))
            return response

        if cleaned_data['action'] == 'previous':
            if currentta.parent:
                # has a explicit parent
                talijst = list(models.ta.objects.filter(idta=currentta.parent))
            else:
                # get list of ta's referring to this idta as child
                talijst = list(
                    models.ta.objects.filter(
                        idta__range=(currentta.script, currentta.idta), child=currentta.idta
                    )
                )
        elif cleaned_data['action'] == 'next':
            if currentta.child:
                # has a explicit child
                talijst = list(models.ta.objects.filter(idta=currentta.child))
            else:
                talijst = list(models.ta.objects.filter(parent=currentta.idta))
        else:  # elif cleaned_data['action'] == 'this':
            if currentta.status == EXTERNIN:
                # EXTERNIN can not be displayed, so go to first FILEIN
                talijst = list(models.ta.objects.filter(parent=currentta.idta))
            elif currentta.status == EXTERNOUT:
                # EXTERNOUT can not be displayed, so go to last FILEOUT
                talijst = list(models.ta.objects.filter(idta=currentta.parent))
            else:
                talijst = [currentta]
        channels = []
        charsets = set()
        for ta_object in talijst:
            # determine if file could be displayed
            cleaned_data = cleaned_data.copy()
            cleaned_data['idta'] = ta_object.idta
            cleaned_data['action'] = 'this'
            if ta_object.filename and ta_object.filename.isdigit():
                ta_object.has_file = True
                if ta_object.contenttype == 'application/pdf':
                    ta_object.content = str(b64encode(
                        botslib.readdata_bin(ta_object.filename)
                    ))[2:-1]
                else:
                    if not ta_object.charset:
                        # guess safe choice for charset.
                        # alt1: get charset by looking forward (until translation).
                        ta_object.charset = "us-ascii"
                        if ta_object.editype != "edifact" and hasattr(grammar, ta_object.editype):
                            # alt2: Lookup the default charset in grammar
                            # utf-8: csv, xml*, json*
                            ta_object.charset = getattr(
                                grammar,
                                ta_object.editype,
                            ).defaultsyntax.get("charset", "us-ascii")
                    ta_object.content = botslib.readdata(
                        ta_object.filename, charset=ta_object.charset, errors="ignore",
                    )
                # Indent
                if request.method == 'GET' or currentta.editype != ta_object.editype \
                        or currentta.contenttype != ta_object.contenttype:
                    cleaned_data["indent"] = ""
                    if ta_object.contenttype in forms.SKIP_INDENT_TYPES:
                        # Skip indent for specific output com content type
                        pass
                    elif ta_object.editype in forms.DEFAULT_INDENT:
                        cleaned_data['indent'] = forms.DEFAULT_INDENT[ta_object.editype]
                    elif ta_object.contenttype in forms.INDENT_TYPE:
                        cleaned_data["indent"] = forms.DEFAULT_INDENT[forms.INDENT_TYPE[ta_object.contenttype]]
                # Add FilerForm to ta_object
                ta_object.form = forms.FilerForm(cleaned_data, ta=ta_object, request=request)
                if ta_object.form.indent_type not in [None, 'html']:
                    indent_func = getattr(viewlib, "indent_" + ta_object.form.indent_type, None)
                    ta_object.indent = indent = cleaned_data.get('indent')
                    if ta_object.indent not in ['', None]:
                        try:
                            if indent_func is viewlib.indent_xml:
                                if indent == "0":
                                    indent = ""
                                ta_object.content, ta_object.charset = viewlib.indent_xml(
                                    ta_object.content,
                                    indent=indent,
                                    encoding=ta_object.charset,
                                )
                            else:
                                ta_object.content = indent_func(ta_object.content, indent=indent)
                        except (JSONDecodeError, XMLSyntaxError) as exc:
                            warn = _("Invalid %(syntax)s syntax: %(exc)s") % {
                                "syntax": ta_object.form.indent_type, "exc": exc}
                            messages.add_message(request, messages.WARNING, warn)

                charsets.add(ta_object.charset if ta_object.editype != "edifact" else "us-ascii")

            else:
                ta_object.has_file = False
                ta_object.content = _('No file available for display.')
                ta_object.form = formin

            # determine has previous:
            if ta_object.parent or ta_object.status == MERGED:
                ta_object.has_previous = True
            else:
                ta_object.has_previous = False

            # determine: has next:
            if ta_object.status == EXTERNOUT or ta_object.statust in [OPEN, ERROR]:
                ta_object.has_next = False
            else:
                ta_object.has_next = True
            channels = [ta_object.fromchannel, ta_object.tochannel]

        channels_types = models.get_channels_types(idchannel__in=channels) if channels else {}
        charsets = list(charsets)
        if len(charsets) > 1:
            warn = _(
                "Several files with differents charset detected %s, "
                "some chars may not be displayed or bad displayed !"
            ) % charsets
            messages.add_message(request, messages.WARNING, warn)
        context.update({
            'idtas': talijst,
            'partners': models.getactivepartners(),
            'inactive_partners': models.getinactivepartners(),
            'channels_types': channels_types,
            "charset": charsets[-1] if charsets else "",
        })
        return django.shortcuts.render(request, 'bots/filer.html', context)

    except Exception as exc:
        err = str(exc) if botsglobal.settings.DEBUG else _("No such file.")
        exc_info = traceback.format_exc(None)
        botsglobal.logger.error("Filer error: %s", exc_info)
        return django.shortcuts.render(request, "bots/filer.html", {"error_content": err})


@login_required
@permission_required('bots.change_translate', login_url='/')
def srcfiler(request):
    """handles bots source file viewer. display grammar, mapping, userscript etc."""
    if request.method == 'GET':
        try:
            src = request.GET.get('src')
            if not src:
                raise Http404()
            srcfile = os.path.abspath(
                os.path.join(botsglobal.ini.get('directories', 'usersysabs'), src))
            # Get only python files in usersys !
            if not srcfile.startswith(botsglobal.ini.get('directories', 'usersysabs')):
                botsglobal.logger.error('Invalid source file requested: %s', src)
                raise Http404()
            if srcfile.endswith('.py') and os.path.isfile(srcfile):
                max_size = botsglobal.ini.getint('webserver', 'max_src_size', 5000000)
                if os.stat(srcfile).st_size > max_size:
                    err = _('File too big exceed %(max_size)s: %(src)s') % {
                        'max_size': max_size, 'src': src}
                    botsglobal.logger.error(err)
                    return django.shortcuts.render(
                        request, 'bots/srcfiler.html', {'error_content': err}
                    )
                with open(srcfile, "r", encoding="utf8") as srcfil:
                    source = srcfil.read()
                classified_text = py2html.analyze_python(source)
                html_source = py2html.html_highlight(classified_text)
                return django.shortcuts.render(
                    request, 'bots/srcfiler.html', {'src': src, 'html_source': html_source}
                )
            return django.shortcuts.render(
                request,
                'bots/srcfiler.html',
                {'error_content': _('File not found: %s') % src},
            )
        except Exception:
            return django.shortcuts.render(
                request, 'bots/srcfiler.html', {'error_content': _('No such file.')}
            )
    return django.shortcuts.redirect("bots:home")


@login_required
@permission_required('bots.view_report', login_url='/')
def logfiler(request):
    """handles bots log file viewer. display/download any file in logging directory."""
    if request.method == 'GET':
        logname = ''
        if 'engine' in request.GET:
            logname = 'engine'
        elif 'jobqueue' in request.GET:
            logname = 'jobqueue'
        elif 'dirmonitor' in request.GET:
            logname = 'dirmonitor'
        elif 'webserver' in request.GET:
            logname = 'webserver'
        context = {
            'logname': logname,
            'is_popup': True,
        }
        logdir = botsglobal.ini.get('directories', 'logging')
        if not logname:
            context['logfiles'] = sorted(os.listdir(logdir), key=lambda s: s.lower())
        else:
            logdata = ''
            logdir = botslib.join(logdir, logname)
            logfiles = glob.glob(os.path.join(logdir, '*'))
            logfiles.sort(key=os.path.getmtime, reverse=True)
            if logname == 'engine' and botsglobal.ini.get(
                    'settings', 'log_when', None) == 'report':
                logfiles = logfiles[:25]
            context["logfiles"] = [os.path.basename(log) for log in logfiles]
            log = request.GET.get(logname, '').split(os.sep)[-1]
            if not log:
                if logname == 'engine':
                    log = str(viewlib.get_reportidta(request.GET) or "")
                if not log and context['logfiles']:
                    log = context['logfiles'][0]
            if log:
                context['log'] = log
                logfile = botslib.join(logdir, log)
                if os.path.isfile(logfile):
                    try:
                        with open(logfile, "r", encoding="utf8") as logfil:
                            logdata = logfil.read()
                        context['logdata'] = logdata or _('Empty log file.')
                    except Exception as exc:
                        err = _("Error occured when reading log %(log)s: %(exc)s") % {"log": log, "exc": exc}
                        botsglobal.logger.error(err)
                        context['logdata'] = err
                else:
                    context['logdata'] = _('No such file.')
                    if botsglobal.settings.DEBUG:
                        context['logdata'] += ': %s' % logfile

            # Download log file
            if request.GET.get('action') == 'download' and logdata:
                if logname == 'engine':
                    filename = 'bots-%s_%s.log' % (logname, log)
                else:
                    filename = 'bots-%s' % log
                if filename.endswith('.log'):
                    sts = os.stat(logfile)
                    mdt = datetime.fromtimestamp(sts.st_mtime)
                    filename = '%s_%s.log' % (filename[:-4], mdt.strftime('%Y%m%d_%H%M'))
                else:
                    filename = '%s.log' % filename.replace('.log', '')
                response = django.http.HttpResponse(content_type='text/log')
                response['Content-Disposition'] = 'attachment; filename=%s' % filename
                response.write(logdata)
                return response

        return django.shortcuts.render(request, 'bots/logfiler.html', context)

    return django.shortcuts.redirect("bots:home")


@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='/')
def plugin(request):
    """Load bots plugin"""

    template = 'bots/plugin.html'

    if request.method == 'GET':
        form = forms.UploadFileForm()
        return django.shortcuts.render(request, template, {'form': form})

    if 'submit' in request.POST:
        formin = forms.UploadFileForm(request.POST, request.FILES)
        if not formin.is_valid():
            messages.add_message(request, messages.INFO, _('No plugin read.'))
            return django.shortcuts.render(request, template, {'form': formin})

        # write backup plugin first
        pluglib.plugout_backup_core(request)

        # read the plugin
        try:
            plugreport = pluglib.read_plugin(request.FILES["file"].temporary_file_path())
            bots_version = plugreport.get("bots_version", plugreport.get("version", "unknown"))
            messages.add_message(
                request,
                messages.INFO if bots_version >= "3.8" else messages.WARNING,
                f"Plugin Bots version: {bots_version}",
            )
            add_messages(request, plugreport)
            if plugreport.get("skipped"):
                messages.add_message(
                    request,
                    messages.WARNING,
                    mark_safe(_("Skipped plugin files:<br>%s") % "<br>".join(plugreport["skipped"])),
                )
            if plugreport.get("overwritten"):
                messages.add_message(
                    request,
                    messages.WARNING,
                    mark_safe(_("Overwritten files:<br>%s") % "<br>".join(plugreport["overwritten"])),
                )
            notification = _('Plugin "%s" successfully installed.') % request.FILES["file"].name
            botsglobal.logger.info(notification)
            messages.add_message(request, messages.INFO, notification)

        except Exception:
            txt = txtexc()
            notification = _('Error occured while reading plugin "%(name)s": %(exc)s') % {
                "name": request.FILES["file"].name, "exc": txt}
            botsglobal.logger.error(notification)
            messages.add_message(request, messages.ERROR, notification)

        return django.shortcuts.render(request, template, {'form': formin})

    return django.shortcuts.redirect('bots:home')


def add_messages(request, msgs: dict[str, list]):
    """
    Add messages to user request

    :param request: django.request
    :param msgs: dict
    """
    for info in msgs.get("info", []):
        messages.add_message(request, messages.INFO, mark_safe(info.replace("\n", "<br>")))
    for warn in msgs.get("warning", []):
        messages.add_message(request, messages.WARNING, mark_safe(warn.replace("\n", "<br>")))


@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='/')
def plugin_index(request):
    """Import config entries in usersys/index.json"""
    if request.method == 'GET':
        return django.shortcuts.render(request, 'bots/plugin_index.html')

    if 'submit' in request.POST:
        # write backup plugin first
        pluglib.plugout_backup_core(request)
        try:
            # read the plugin
            plugreport = pluglib.read_index()
            add_messages(request, plugreport)

        except Exception as exc:
            notification = _('Error occured while reading configuration index file: "%s".') % str(exc)
            botsglobal.logger.error(notification)
            messages.add_message(request, messages.ERROR, notification)

    return django.shortcuts.redirect('bots:home')


@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='/')
def plugout_index(request):
    """Write bots database config entries in usersys/index.json"""
    if request.method == 'GET':
        try:
            plugreport = pluglib.make_index(
                os.path.join(botsglobal.ini.get("directories", "usersysabs"), "index.json"))
            add_messages(request, plugreport)

        except Exception as exc:
            notification = _('Error writing configuration index file: "%s".') % str(exc)
            botsglobal.logger.error(notification)
            messages.add_message(request, messages.ERROR, notification)

    return django.shortcuts.redirect("bots:home")


@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='/')
def plugout_backup(request):
    if request.method == 'GET':
        pluglib.plugout_backup_core(request)
    return django.shortcuts.redirect('bots:home')


@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='/')
def plugout(request):
    """Create bots plugins."""
    context = {}
    if request.method == 'GET':
        context['form'] = form = forms.PlugoutForm()
        return django.shortcuts.render(request, form.template, context)

    if 'submit' in request.POST:
        formin = forms.PlugoutForm(request.POST)
        if formin.is_valid():
            filename = 'bots_plugin_%s.zip' % time.strftime('%Y%m%d%H%M%S')
            filename = botslib.join(botsglobal.ini.get('directories', 'botssys'), filename)
            botsglobal.logger.info(_('Start writing plugin "%(file)s".'), {'file': filename})
            try:
                pluglib.make_plugin(formin.cleaned_data, filename)
                botsglobal.logger.info(
                    _('Plugin "%(file)s" created successful.'), {'file': filename}
                )
                with open(filename, "rb") as zipfile:
                    response = django.http.HttpResponse(zipfile.read(), content_type="application/zip")
                # response['Content-Length'] = os.path.getsize(filename)
                response['Content-Disposition'] = 'attachment; filename=%s'
                response['Content-Disposition'] %= os.path.basename(filename)
                os.remove(filename)
                return response

            except PluginError as exc:
                botsglobal.logger.error(exc)
                messages.add_message(request, messages.ERROR, exc)

    return django.shortcuts.redirect('bots:home')


@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='/')
def delete(request):
    """Bots delete view"""

    if request.method == 'GET':
        form = forms.DeleteForm()
        return django.shortcuts.render(request, 'bots/delete.html', {'form': form})

    if 'submit' in request.POST:
        form = forms.DeleteForm(request.POST)
        if form.is_valid():
            pluglib.delete(request=request, **form.cleaned_data)
    return django.shortcuts.redirect('bots:home')


@login_required
@permission_required('bots.change_mutex', login_url='/')
def runengine(request):
    """
    Start bots-engine from request parameters

    cmd arguments:
        1. bots-engine
        2. environment (config).
        3. commandstorun (eg --new) and routes.
    """
    if request.method == 'GET':
        environment = '-c' + botsglobal.ini.get('directories', 'config_org')
        lijst = ['bots-engine', environment]
        # get 3. commandstorun (eg --new) and routes via request
        if request.GET.get('clparameter'):
            lijst.append(request.GET['clparameter'])

        # either bots-engine is run directly or via jobqueue-server
        if botsglobal.ini.getboolean('jobqueue', 'enabled', False):
            # run bots-engine via jobqueue-server; reports back if job is queued
            terug = job2queue.send_job_to_jobqueue(lijst)
            txt = '%s: %s' % (job2queue.JOBQUEUEMESSAGE2TXT[terug], lijst[-1])
            if terug == 0:
                messages.add_message(request, messages.INFO, txt)
                botsglobal.logger.info(txt)
            elif terug == 1:
                messages.add_message(request, messages.ERROR, txt)
                botsglobal.logger.error(txt)
            else:
                messages.add_message(request, messages.WARNING, txt)
                botsglobal.logger.warning(txt)
        else:
            # run bots-engine direct.
            # reports back if bots-engine is started succesful.
            # **not reported: problems with running.
            botsglobal.logger.info(
                _('Run bots-engine with parameters: "%(parameters)s"'),
                {"parameters": str(lijst)},
            )

            # first check if another instance of bots-engine is running/if port is free
            try:
                engine_socket = botslib.check_if_other_engine_is_running()
            except socket.error:
                notification = _(
                    'Trying to run "bots-engine",'
                    ' but another instance of "bots-engine" is running.'
                    ' Please try again later.'
                )
                messages.add_message(request, messages.ERROR, notification)
                botsglobal.logger.error(notification)
                return django.shortcuts.redirect('bots:home')

            # Close the socket
            engine_socket.close()

            # run engine
            try:
                with subprocess.Popen(lijst) as proc:
                    terug = proc.pid
            except Exception as exc:
                notification = _('Errors while trying to run bots-engine: "%s".') % exc
                messages.add_message(request, messages.ERROR, notification)
                botsglobal.logger.error(notification)
            else:
                messages.add_message(request, messages.INFO, _('Bots-engine is started.'))

        if request.user.has_perm('bots.view_report'):
            return django.shortcuts.redirect('bots:reports')

    return django.shortcuts.redirect('bots:home')


@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='/')
def sendtestmailmanagers(request):
    try:
        sendornot = botsglobal.ini.getboolean('settings', 'sendreportiferror', False)
    except BotsError:
        sendornot = False
    if not sendornot:
        notification = _(
            'Trying to send test mail, but in bots.ini, section [settings], '
            '"sendreportiferror" is not "True".'
        )
        botsglobal.logger.info(notification)
        messages.add_message(request, messages.ERROR, notification)
        return django.shortcuts.redirect('bots:home')

    try:
        mail_managers(_('testsubject'), _('test content of report'))
    except Exception:
        txt = txtexc()
        messages.add_message(request, messages.ERROR, _('Sending test mail failed.'))
        botsglobal.logger.info(_('Sending test mail failed, error:\n%(txt)s'), {'txt': txt})
        return django.shortcuts.redirect('bots:home')

    notification = _('Sending test mail succeeded.')
    messages.add_message(request, messages.INFO, notification)
    botsglobal.logger.info(notification)
    return django.shortcuts.redirect('bots:home')
