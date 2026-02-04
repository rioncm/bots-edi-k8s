"""
Bots configuration for django's admin site.
"""
# pylint: disable=missing-class-docstring, missing-function-docstring, protected-access, unused-argument, too-few-public-methods, duplicate-code, too-many-lines
# flake8: noqa:E501

import copy
import json
import os
import time

from django import forms
from django.contrib import admin
import django.contrib.auth
from django.contrib.auth.admin import UserAdmin
from django.contrib import messages
from django.core.exceptions import ValidationError
import django.forms.utils
from django.utils.safestring import mark_safe

# bots-modules
from . import botsglobal
from . import botslib
from . import models
from . import pluglib
from .botslib import gettext as _
from .exceptions import PluginError
from .models import reverse_lazy, get_grammars, get_mappings, BOTS_DOCS_URL

User = django.contrib.auth.get_user_model()


def get_admin_url(obj, action='change'):
    return reverse_lazy(f"admin:{obj._meta.app_label}_{obj._meta.model_name}_{action}", args=[obj.pk])


def admin_link(obj, **kwargs):
    cssclass = kwargs.get('cssclass', 'button nowrap')
    if kwargs.get('cssicon'):
        cssclass += f" {kwargs.get('cssicon')}"
    popup_args = ''
    if isinstance(obj, models.channel):
        popup_args = ", '55%', '90%'"
    elif isinstance(obj, models.partner):
        popup_args = ", '60%', '80%'"
    return mark_safe(
        f"""<a class="{cssclass}" href="{get_admin_url(obj)}?_popup=1" """
        f"""target="{obj._meta.app_label}_{obj._meta.model_name}_{obj.pk}" """
        f"""onclick="return popup(this{popup_args})" """
        f"""title="{_('View')} {obj._meta.model_name} {obj}">{obj}</a>"""
        )


@mark_safe
def script_icon(script):
    if script and os.path.isfile(script):
        title = script.split(botsglobal.ini.get("directories", "usersysabs"))[1].lstrip(os.path.sep)
        return f"""<span class="icon-yes" title="{title}"></span>"""
    return models.ICON_NO


def make_plugin(cls, request, queryset, cleaned_data=None):
    """Make a Bots plugin with selected entries."""
    obj = queryset.first()
    name = obj._meta.model_name
    if len(queryset) == 1:
        name += "_" + str(obj).replace(" ", "_")
    filename = f"{obj._meta.app_label}_plugin_{name}_{time.strftime('%Y%m%d%H%M%S')}.zip"
    filename = botslib.join(botsglobal.ini.get('directories', 'botssys'), filename)
    botsglobal.logger.info(_('Start writing plugin "%(file)s".'), {'file': filename})
    if not isinstance(cleaned_data, dict):
        cleaned_data = {}
    cleaned_data['queryset'] = queryset
    try:
        pluglib.make_plugin(cleaned_data, filename)
    except PluginError as exc:
        if os.path.exists(filename):
            os.remove(filename)
        botsglobal.logger.error(exc)
        messages.add_message(request, messages.ERROR, exc)
        return False
    botsglobal.logger.info(_('Plugin "%(file)s" created successful.'), {"file": filename})
    with open(filename, "rb") as zipfile:
        response = django.http.HttpResponse(zipfile.read(), content_type="application/zip")
    # response["Content-Length"] = os.path.getsize(filename)
    response["Content-Disposition"] = f"attachment; filename={os.path.basename(filename)}"
    os.remove(filename)
    return response


make_plugin.short_description = _('Make bots plugin with selected entries')
make_plugin.allowed_permissions = ('make_plugin',)


def make_plugin_notranslate(cls, request, queryset):
    """Make a Bots plugin with selected entries without translate entries, mappings and grammars"""
    return make_plugin(cls, request, queryset, {'notranslate': True})


make_plugin_notranslate.short_description = _("Make bots plugin, skip translate (grammars, mappings)")
make_plugin_notranslate.allowed_permissions = ('make_plugin',)


def make_grammar_plugin(cls, request, queryset):
    """Make a Bots grammars plugin with selected translate(s), skip entries and mappings"""
    return make_plugin(cls, request, queryset, {'grammaronly': True})


make_grammar_plugin.short_description = _("Make grammar plugin (grammars only)")
make_grammar_plugin.allowed_permissions = ('make_plugin',)


def make_plugin_nogrammar(cls, request, queryset):
    """Make a Bots translate plugin with mapping(s), without grammars files."""
    return make_plugin(cls, request, queryset, {'nogrammar': True})


make_plugin_nogrammar.short_description = _("Make translate plugin (mapping(s) without grammars)")
make_plugin_nogrammar.allowed_permissions = ('make_plugin',)


class BotsAdmin(admin.ModelAdmin):
    """Bots admin class"""
    list_per_page = 30
    if hasattr(botsglobal.ini, 'getint'):
        list_per_page = botsglobal.ini.getint(
            'settings', 'adminlimit', botsglobal.ini.getint('settings', 'limit', list_per_page)
        )
    save_as = True
    save_on_top = True

    def activate(self, cls, request, queryset, *args, **kwargs):
        """handles the admin 'activate' action."""
        # much faster: queryset.update(active=not F('active'))
        # but negation of F() object is not yet supported in django (20140307)
        for obj in queryset:
            obj.active = not obj.active
            obj.save()
            admin.ModelAdmin.log_change(None, request, obj, f"Changed active: {obj.active}")

    activate.short_description = _('activate/de-activate')
    activate.allowed_permissions = ('change',)

    def has_make_plugin_permission(self, request):
        return request.user.is_superuser

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'active' in self.list_display and self.has_change_permission(request):
            actions['activate'] = (self.activate, 'activate', self.activate.short_description)
        if request.user.is_superuser:
            if "domein" not in self.list_display:
                actions['make_plugin'] = (make_plugin, 'make_plugin', make_plugin.short_description)
        return actions

    def changelist_view(self, request, extra_context=None):
        """Set title with bots model._meta.verbose_name_plural"""
        extra_context = extra_context or {}
        extra_context.setdefault("title", f"Bots {self.model._meta.verbose_name_plural.title()}")
        return super().changelist_view(request, extra_context=extra_context)

    def get_form(self, request, obj=None, change=False, **kwargs):
        """over-ride form text field widths to better fit their actual size"""
        form = super().get_form(request, obj, change, **kwargs)
        for field in form.base_fields:
            if form.base_fields[field].widget.attrs.get('class') == 'vTextField':
                width = min(70, int(form.base_fields[field].widget.attrs["maxlength"]))
                form.base_fields[field].widget.attrs["style"] = f"width: {width}ch;"
        return form


# *************************************************************************************************
@admin.register(models.ccodetrigger)
class CcodetriggerAdmin(BotsAdmin):
    """Bots ccodetrigger admin"""
    save_on_top = False
    list_display = ('ccodeid', 'ccodeid_desc')
    list_display_links = ('ccodeid',)
    ordering = ('ccodeid',)
    search_fields = ('ccodeid', 'ccodeid_desc')


@admin.register(models.ccode)
class CcodeAdmin(BotsAdmin):
    """Bots ccode admin"""

    def get_queryset(self, request):
        if not request.user.is_superuser:
            # usershortcuts = self.model.objects.all(ccodeid='shortcut', attr8=request.user.id)
            otherusers = [u.id for u in User.objects.exclude(id=request.user.id)]
            return self.model.objects.exclude(ccodeid='shortcut', attr8__in=otherusers + [''])
        return self.model.objects.all()

    list_display = (
        'ccodeid',
        'leftcode',
        'rightcode',
        'attr1',
        'attr2',
        'attr3',
        'attr4',
        'attr5',
        'attr6',
        'attr7',
        'attr8',
    )
    list_display_links = ('ccodeid',)
    list_filter = (
        'ccodeid',
        'attr1',
        'attr2',
        'attr3',
        'attr4',
        'attr5',
        'attr6',
        'attr7',
        'attr8',
    )
    ordering = ('ccodeid', 'leftcode')
    search_fields = (
        'ccodeid__ccodeid',
        'leftcode',
        'rightcode',
        'attr1',
        'attr2',
        'attr3',
        'attr4',
        'attr5',
        'attr6',
        'attr7',
        'attr8',
    )
    fieldsets = (
        (None, {
            'fields': (
                'ccodeid',
                'leftcode',
                'rightcode',
                'attr1',
                'attr2',
                'attr3',
                'attr4',
                'attr5',
                'attr6',
                'attr7',
                'attr8',
            ),
            'description': (
                _("For description of user code lists and usage in mapping: see ") +
                f'<a target="_blank" href="{BOTS_DOCS_URL}/configuration/mapping-scripts/code-conversion.html">wiki</a>'
            ),
        }),
    )

    def lookup_allowed(self, lookup, *args, **kwargs):
        if lookup.startswith('ccodeid'):
            return True
        return super().lookup_allowed(lookup, *args, **kwargs)


class ChannelAdminForm(forms.ModelForm):

    class Meta:
        model = models.channel
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'inorout' in self.fields:
            self.fields["inorout"].widget.attrs["onchange"] = "onchange_inorout()"
            self.fields["type"].widget.attrs["onchange"] = "onchange_inorout()"

    def clean_host(self):
        # If http auth is set and credentials are missing raise error
        if not self.cleaned_data.get('type') in ['file', 'mimefile', 'trash', 'communicationscript']:
            if not self.cleaned_data.get('host'):
                raise ValidationError(
                    _('HOST field is mandatory for %s channel') % self.cleaned_data.get('type'))
        return self.cleaned_data.get('host')


@admin.register(models.channel)
class ChannelAdmin(BotsAdmin):
    """Bots channel admin"""

    def secret_(self, obj):
        return ('*' * len(obj.secret))[:8] if obj.secret else ''

    secret_.short_description = _('Password')

    @mark_safe
    def idchannel_(self, obj):
        return f'<span class="ico-{obj.inorout}channel">{obj.idchannel}</span>'

    idchannel_.admin_order_field = 'idchannel'
    idchannel_.short_description = _('Idchannel')

    @mark_safe
    def inorout_(self, obj):
        return f'<span class="ico-{obj.inorout}channel">{obj.get_inorout_display()}</span>'

    inorout_.admin_order_field = 'inorout'
    inorout_.short_description = _('in/out')

    form = ChannelAdminForm
    list_display = [
        'idchannel_',
        'inorout_',
        'type',
        'comscript_',
        'remove',
        'host',
        'port',
        'username',
        'secret_',
        'path',
        'filename',
        'mdnchannel',
        'testpath',
        'archivepath',
        'rsrv3',
        'rsrv2',
        'rsrv1',
        'syslock',
        'parameters',
        'starttls',
        'apop',
        'askmdn',
        'sendmdn',
        'ftpactive',
        'ftpbinary',
        'debug',
    ]

    def get_list_display(self, request, **kwargs):
        list_display = self.list_display[:]
        if request.user.has_perm('bots.change_translate'):
            list_display[list_display.index('comscript_')] = 'comscript_link'
        if request.user.has_perm('bots.view_routes'):
            list_display.insert(list_display.index('remove') + 1, 'routes_link')
        return list_display

    list_filter = ('inorout', 'type', 'debug')
    ordering = ('idchannel',)
    readonly_fields = ('comscript_', 'comscript_link',)
    search_fields = (
        'idchannel',
        'inorout',
        'type',
        'host',
        'username',
        'path',
        'filename',
        'archivepath',
        'desc',
    )
    fieldsets = (
        (None, {
            'fields': [
                'idchannel',
                ('inorout', 'type'),
                'remove',
                'comscript_',
                ('host', 'port'),
                ('username', 'secret'),
                ('path', 'filename'),
                ('archivepath', 'rsrv3'),
                'desc',
            ],
        }),
        (_('Email specific'), {
            'fields': ('starttls', 'apop', 'askmdn', 'sendmdn'),
            'classes': ('collapse',),
        }),
        (_('FTP specific'), {
            'fields': ('ftpactive', 'ftpbinary', 'ftpaccount'),
            'classes': ('collapse',),
        }),
        (_('Safe writing & file locking'), {
            'fields': ('mdnchannel', 'syslock', 'lockname'),
            "description": (
                _("For more info see ") +
                f'<a target="_blank" href="{BOTS_DOCS_URL}/configuration/channel/file-locking.html">wiki</a><br>'
            ),
            'classes': ('collapse',),
        }),
        (_('Other'), {
            'fields': ('testpath', 'keyfile', 'certfile', 'rsrv2', 'rsrv1', 'debug', 'parameters'),
            'classes': ('collapse',),
        }),
    )

    def get_fieldsets(self, request, obj=None):
        if request.user.has_perm('bots.change_translate'):
            fieldsets = copy.deepcopy(self.fieldsets)
            fieldsets[0][1]['fields'][fieldsets[0][1]['fields'].index('comscript_')] = 'comscript_link'
            return fieldsets
        return self.fieldsets

    def comscript_(self, obj):
        return script_icon(obj.communicationscript)

    comscript_.admin_order_field = 'idchannel'
    comscript_.short_description = _('Script')

    def changelist_view(self, request, extra_context=None):
        """Set title with bots model._meta.verbose_name_plural"""
        extra_context = extra_context or {}
        extra_context['title'] = f"Bots {self.model._meta.verbose_name_plural.title()}"
        inorout = request.GET.get('inorout__exact')
        if inorout:
            extra_context["title"] += f": {_(inorout)}"
        channel_type = request.GET.get('type__exact')
        if channel_type:
            extra_context["title"] += f": {channel_type}"
        return super().changelist_view(request, extra_context=extra_context)


class ConfirmruleAdminForm(forms.ModelForm):
    """customs form for route for additional checks"""

    class Meta:
        model = models.confirmrule
        widgets = {'idroute': forms.Select()}
        fields = ['idroute']

    class Media:
        js = ('admin/js/bots.js',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.fields:
            self.fields['ruletype'].widget.attrs['onchange'] = "onchange_confirmruletype(event)"

    def clean(self):
        super().clean()
        ruletype = self.cleaned_data.get('ruletype')
        if ruletype == 'confirmasked':
            if self.cleaned_data.get('confirmtype') not in ['send-x12-997']:
                err = _('Confirm asked ruletype work only with "send-x12-997" confirmtype.')
                self.add_error('ruletype', err)
                raise ValidationError(err)
        elif ruletype == 'route':
            if not self.cleaned_data.get('idroute'):
                err = _('For ruletype "route" it is required to indicate a route.')
                self.add_error('idroute', err)
                raise ValidationError(err)
        elif ruletype == 'channel':
            if not self.cleaned_data.get('idchannel'):
                err = _('For ruletype "channel" it is required to indicate a channel.')
                self.add_error('idchannel', err)
                raise ValidationError(err)
        elif ruletype == 'frompartner':
            if not self.cleaned_data.get('frompartner'):
                err = _('For ruletype "frompartner" it is required to indicate a frompartner.')
                self.add_error('frompartner', err)
                raise ValidationError(err)
        elif ruletype == 'topartner':
            if not self.cleaned_data.get('topartner'):
                err = _('For ruletype "topartner" it is required to indicate a topartner.')
                self.add_error('topartner', err)
                raise ValidationError(err)
        elif ruletype == 'messagetype':
            if not self.cleaned_data.get('messagetype'):
                err = _('For ruletype "messagetype" it is required to indicate a messagetype.')
                self.add_error('messagetype', err)
                raise ValidationError(err)
        return self.cleaned_data


@admin.register(models.confirmrule)
class ConfirmruleAdmin(BotsAdmin):
    """Bots confirmrule admin"""
    save_on_top = False
    form = ConfirmruleAdminForm
    list_display = (
        'active',
        'negativerule',
        'confirmtype',
        'ruletype',
        'frompartner',
        'topartner',
        'idroute',
        'idchannel',
        'messagetype',
    )
    list_display_links = ('confirmtype',)
    list_filter = ('active', 'confirmtype', 'ruletype')
    search_fields = (
        'confirmtype',
        'ruletype',
        'frompartner__idpartner',
        'topartner__idpartner',
        'idroute',
        'idchannel__idchannel',
        'messagetype',
    )
    ordering = ('confirmtype', 'ruletype')
    fieldsets = (
        (None, {
            'fields': (
                'active',
                'negativerule',
                'confirmtype',
                'ruletype',
                'frompartner',
                'topartner',
                'idroute',
                'idchannel',
                'messagetype',
            ),
        }),
    )

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        """make dynamic choice list for field idroute. not a foreign key, gave to much trouble."""
        if db_field.name == 'idroute':
            kwargs['widget'].choices = models.getroutelist()
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['RULETYPES'] = json.dumps([rt[0] for rt in models.RULETYPE])
        return super().add_view(request, form_url, extra_context=extra_context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['RULETYPES'] = json.dumps([rt[0] for rt in models.RULETYPE])
        return super().change_view(request, object_id, form_url, extra_context=extra_context)


class MailInline(admin.TabularInline):
    model = models.chanpar
    fields = ('idchannel', 'mail', 'cc')
    extra = 1


@admin.register(models.partner)
class PartnerAdmin(BotsAdmin):
    """Bots partner admin"""
    filter_horizontal = ('group',)
    inlines = (MailInline,)
    list_display = (
        'active',
        'idpartner',
        'name',
        'mail',
        'cc',
        'address1',
        'city',
        'countrysubdivision',
        'countrycode',
        'postalcode',
        'startdate',
        'enddate',
        'phone1',
        'phone2',
        'attr1',
        'attr2',
        'attr3',
        'attr4',
        'attr5',
    )
    list_display_links = ('idpartner',)
    list_filter = ('active', 'group')
    ordering = ('idpartner',)
    search_fields = (
        'idpartner',
        'name',
        'mail',
        'cc',
        'address1',
        'city',
        'countrysubdivision',
        'countrycode',
        'postalcode',
        'attr1',
        'attr2',
        'attr3',
        'attr4',
        'attr5',
        'name1',
        'name2',
        'name3',
        'desc',
    )
    fieldsets = (
        (None, {
            'fields': (
                'active',
                ('idpartner', 'name'),
                ('mail', 'cc'),
                'desc',
                ('startdate', 'enddate'),
            ),
        }),
        (_('Address'), {
            'fields': (
                'name1',
                'name2',
                'name3',
                'address1',
                'address2',
                'address3',
                ('postalcode', 'city'),
                ('countrycode', 'countrysubdivision'),
                ('phone1', 'phone2'),
            ),
            'classes': ('collapse',),
        }),
        (_('Is in groups'), {
            'fields': ('group',),
            'classes': ('collapse',)
        }),
        (_('User defined'), {
            'fields': ('attr1', 'attr2', 'attr3', 'attr4', 'attr5'),
            'classes': ('collapse',),
        }),
    )

    def get_queryset(self, request):
        return self.model.objects.filter(isgroup=False)

# class PartnerInline(admin.TabularInline):
#     model = models.partner.group.through
#     fields = ('idpartner','name')
#     extra = 1
#     fk_name = 'from_partner_id'


@admin.register(models.partnergroep)
class PartnerGroepAdmin(BotsAdmin):
    # inlines = [PartnerInline,]
    # exclude = ('group',)
    list_display = ('active', 'idpartner', 'name', 'startdate', 'enddate')
    list_display_links = ('idpartner',)
    list_filter = ('active',)
    ordering = ('idpartner',)
    search_fields = ('idpartner', 'name', 'desc')
    fieldsets = (
        (None, {
            'fields': ('active', 'idpartner', 'name', 'desc', ('startdate', 'enddate')),
        }),
    )


class RouteAdminForm(forms.ModelForm):
    """customs form for route for additional checks"""

    dirmonitor_types = ['file']

    class Meta:
        model = models.routes
        fields = "__all__"

    class Media:
        js = ('admin/js/bots.js',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.fields:
            self.fields['fromeditype'].widget.attrs['onchange'] = "onchange_editype(this);"
            self.fields['toeditype'].widget.attrs['onchange'] = "onchange_editype(this);"
            self.fields['translateind'].widget.attrs['onchange'] = "onchange_translateind();"

    def clean_dirmonitor(self):
        if self.cleaned_data.get('dirmonitor'):
            fromchannel = self.cleaned_data.get('fromchannel')
            if not fromchannel:
                raise ValidationError(
                    _('Please specify a "file" fromchannel to activate dirmonitor for this route.'))
            if fromchannel.type not in self.dirmonitor_types:
                raise ValidationError(_(
                    """Dirmonitor doesn't work with fromchannel type "%(fromchannel_type)s","""
                    """ must be a fromchannel type %(dirmonitor_types)s""") % {
                        'fromchannel_type': fromchannel.type,
                        'dirmonitor_types': self.dirmonitor_types})
            if self.cleaned_data.get('active'):
                for route in models.routes.objects.filter(
                        active=True, dirmonitor=True, fromchannel=fromchannel):
                    if not self.instance.pk or route.pk != self.instance.pk:
                        raise ValidationError(_(
                            'Dirmonitor already active for fromchannel %(fromchannel)s'
                            ' route: %(route)s') % locals())
        return self.cleaned_data.get('dirmonitor')

    def clean(self):
        super().clean()
        if self.cleaned_data.get("fromchannel") and self.cleaned_data.get("translateind") != 2 and (
            not self.cleaned_data.get("fromeditype") or not self.cleaned_data.get("frommessagetype")
        ):
            raise ValidationError(_(
                'When using an inchannel and not pass-through, '
                'both "fromeditype" and "frommessagetype" are required.'))
        return self.cleaned_data


@admin.register(models.routes)
class RoutesAdmin(BotsAdmin):
    """Bots routes admin"""

    form = RouteAdminForm

    def get_dirmonitored_route(self, obj):
        """
        Query other dirmonitored route with same fromchannel of input route.
        return: route obj or None
        """
        for route in models.routes.objects.filter(
                active=True, dirmonitor=True, fromchannel=obj.fromchannel):
            if route.pk != obj.pk:
                return route
        return None

    def activate(self, cls, request, queryset, *args, **kwargs):
        """handles the routes admin 'activate' action."""
        for obj in queryset:
            if obj.dirmonitor and not obj.active:
                dirmonitored_route = self.get_dirmonitored_route(obj)
                if dirmonitored_route:
                    err = _('Could not activate dirmonitored route: %s, ') % admin_link(obj)
                    err += _(
                        'Dirmonitor already active for fromchannel %(fromchannel)s'
                        ' with route: %(route)s') % {
                            'fromchannel': admin_link(obj.fromchannel),
                            'route': admin_link(dirmonitored_route)}
                    messages.add_message(request, messages.ERROR, mark_safe(err))
                    continue
            obj.active = not obj.active
            obj.save()
            admin.ModelAdmin.log_change(self, request, obj, f"Changed active: {obj.active}")

    activate.short_description = _('activate/de-activate')
    activate.allowed_permissions = ('change',)

    def get_actions(self, request):
        actions = super().get_actions(request)
        if request.user.is_superuser:
            actions['make_plugin_notranslate'] = (
                make_plugin_notranslate,
                'make_plugin_notranslate',
                make_plugin_notranslate.short_description)
        if self.has_change_permission(request):
            actions['disable_dirmonitor'] = (
                self.disable_dirmonitor, 'disable_dirmonitor',
                self.disable_dirmonitor.short_description)
        return actions

    list_display = [
        'active',
        'idroute',
        'seq',
        'indefaultrun',
        'routescript_icon',
        'fromchannel_',
        'dirmonitor_',
        'fromeditype',
        'frommessagetype',
        'alt',
        'translt',
        'frompartner_',
        'topartner_',
        'tochannel_',
        'defer',
        'toeditype',
        'tomessagetype',
        'frompartner_tochannel',
        'topartner_tochannel',
        'testindicator',
        'zip_incoming',
        'zip_outgoing',
    ]

    def get_list_display(self, request, **kwargs):
        list_display = self.list_display[:]
        if request.user.has_perm('bots.change_translate'):
            list_display[list_display.index('routescript_icon')] = 'routescript_link'
            list_display[list_display.index('frommessagetype')] = 'frommessagetype_link'
            list_display[list_display.index('tomessagetype')] = 'tomessagetype_link'
        if request.user.has_perm('bots.view_translate'):
            list_display[list_display.index('translt')] = 'translt_'
        return list_display

    list_display_links = ('idroute',)
    list_filter = (
        'active', 'notindefaultrun', 'idroute', 'frompartner', 'topartner',
        'fromchannel', 'fromchannel__type', 'dirmonitor', 'fromeditype', 'frommessagetype',
        'tochannel', 'tochannel__type', 'toeditype', 'tomessagetype',
        'frompartner_tochannel', 'topartner_tochannel',
    )
    ordering = ('idroute', 'seq')
    readonly_fields = ('routescript_icon', 'routescript_link',)
    search_fields = (
        'idroute',
        'fromchannel__idchannel',
        'fromeditype',
        'frommessagetype',
        'alt',
        'tochannel__idchannel',
        'toeditype',
        'tomessagetype',
        'desc',
    )
    fieldsets = (
        (None, {
            'fields': [
                ('active', 'notindefaultrun'),
                'routescript_icon',
                ('idroute', 'seq'),
                ('fromchannel', 'dirmonitor'),
                ('fromeditype', 'frommessagetype'),
                ('translateind', 'alt'),
                'tochannel',
                'desc',
            ],
        }),
        (_('Filtering for outchannel'), {
            'fields': (
                'toeditype',
                'tomessagetype',
                'frompartner_tochannel',
                'topartner_tochannel',
                'testindicator',
            ),
            'classes': ('collapse',),
        }),
        (_('Advanced'), {
            'fields': (
                'frompartner',
                'topartner',
                'defer',
                'zip_incoming',
                'zip_outgoing',
            ),
            'classes': ('collapse',),
        }),
    )

    def get_fieldsets(self, request, obj=None):
        if request.user.has_perm('bots.change_translate'):
            fieldsets = copy.deepcopy(self.fieldsets)
            fieldsets[0][1]['fields'][fieldsets[0][1]['fields'].index('routescript_icon')] = 'routescript_link'
            return fieldsets
        return self.fieldsets

    @mark_safe
    def dirmonitor_(self, obj):
        if obj.dirmonitor:
            return models.ICON_YES
        return ''

    dirmonitor_.admin_order_field = 'dirmonitor'
    dirmonitor_.short_description = _('Dirmonitor')

    def disable_dirmonitor(self, cls, request, queryset, *args, **kwargs):
        """handles the admin 'activate' action."""
        for obj in queryset.filter(dirmonitor=True):
            obj.dirmonitor = False
            obj.save()
            admin.ModelAdmin.log_change(None, request, obj, 'Desactivate dirmonitor.')

    disable_dirmonitor.short_description = _('Disable dirmonitor')
    disable_dirmonitor.allowed_permissions = ('change',)

    def routescript_icon(self, obj):
        return script_icon(obj.routescript)

    routescript_icon.admin_order_field = 'idroute'
    routescript_icon.short_description = _('Script')

    @mark_safe
    def translt_(self, obj):
        return f"{obj.translt()} &nbsp; {obj.translate_link()}"

    translt_.admin_order_field = 'translateind'
    translt_.short_description = _('Translate')

    def fromchannel_(self, obj):
        if obj.fromchannel:
            return admin_link(obj.fromchannel, cssicon='ico-fromchannel')
        return obj.fromchannel

    fromchannel_.admin_order_field = 'fromchannel'
    fromchannel_.short_description = _('incoming channel')

    def tochannel_(self, obj):
        if obj.tochannel:
            return admin_link(obj.tochannel, cssicon='ico-tochannel')
        return obj.tochannel

    tochannel_.admin_order_field = 'tochannel'
    tochannel_.short_description = _('outgoing channel')

    def frompartner_(self, obj):
        if obj.frompartner:
            return admin_link(obj.frompartner, cssicon='ico-frompartner')
        return obj.frompartner

    frompartner_.admin_order_field = 'frompartner'
    frompartner_.short_description = _('From Partner')

    def topartner_(self, obj):
        if obj.topartner:
            return admin_link(obj.topartner, cssicon='ico-topartner')
        return obj.topartner

    topartner_.admin_order_field = 'topartner'
    topartner_.short_description = _('To Partner')

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        if request.user.has_perm('bots.change_translate'):
            extra_context['message_types'] = json.dumps(get_grammars())
        return super().add_view(request, form_url, extra_context=extra_context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        if request.user.has_perm('bots.change_translate'):
            extra_context['message_types'] = json.dumps(get_grammars())
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    def changelist_view(self, request, extra_context=None):
        """Set title with bots model._meta.verbose_name_plural"""
        extra_context = extra_context or {}
        extra_context["title"] = f"Bots {self.model._meta.verbose_name_plural.title()}"
        idroute = request.GET.get('idroute')
        if idroute:
            extra_context["title"] += f": {idroute}"
        return super().changelist_view(request, extra_context=extra_context)


class TranslateAdminForm(forms.ModelForm):
    """
    customs form for translations to check if entry exists
    (unique_together not validated right (because of null values in partner fields))
    """

    class Meta:
        model = models.translate
        fields = "__all__"

    class Media:
        js = ('admin/js/bots.js',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.fields:
            for field in ['fromeditype', 'toeditype']:
                self.fields[field].widget.attrs["onchange"] = "onchange_editype(this);"

    def clean(self):
        super().clean()
        blub = models.translate.objects.filter(
            fromeditype=self.cleaned_data.get('fromeditype'),
            frommessagetype=self.cleaned_data.get('frommessagetype'),
            alt=self.cleaned_data.get('alt'),
            frompartner=self.cleaned_data.get('frompartner'),
            topartner=self.cleaned_data.get('topartner'),
        )
        if blub and (self.instance.id is None or self.instance.id != blub[0].id):
            raise ValidationError(_(
                'Combination of fromeditype, frommessagetype, alt, frompartner, topartner '
                'already exists.'))
        return self.cleaned_data


@admin.register(models.translate)
class TranslateAdmin(BotsAdmin):
    """Bots translate admin"""

    form = TranslateAdminForm

    def get_actions(self, request):
        actions = super().get_actions(request)
        if request.user.is_superuser:
            actions['make_plugin_nogrammar'] = (
                make_plugin_nogrammar,
                'make_plugin_nogrammar',
                make_plugin_nogrammar.short_description)
            actions['make_grammar_plugin'] = (
                make_grammar_plugin,
                'make_grammar_plugin',
                make_grammar_plugin.short_description)
        return actions

    list_display = [
        'active',
        'fromeditype',
        'frommessagetype',
        'alt',
        'frompartner',
        'topartner',
        'tscript',
        'toeditype',
        'tomessagetype',
    ]

    def get_list_display(self, request, **kwargs):
        list_display = self.list_display[:]
        if request.user.has_perm('bots.change_translate'):
            for field in ['frommessagetype', 'tscript', 'tomessagetype']:
                list_display[list_display.index(field)] = f"{field}_link"
        return list_display

    list_display_links = ('fromeditype',)
    list_filter = (
        'active', 'frompartner', 'topartner',
        'fromeditype', 'frommessagetype',
        'tscript',
        'toeditype', 'tomessagetype',
        'alt',
    )
    ordering = ('fromeditype', 'frommessagetype')
    search_fields = (
        'fromeditype',
        'frommessagetype',
        'alt',
        'frompartner__idpartner',
        'topartner__idpartner',
        'tscript',
        'toeditype',
        'tomessagetype',
        'desc',
    )
    fieldsets = (
        (None, {
            'fields': [
                'active',
                ('fromeditype', 'frommessagetype'),
                'tscript',
                ('toeditype', 'tomessagetype'),
                'desc',
            ],
        }),
        (
            _("Multiple translations per editype/messagetype"),
            {
                "fields": ("alt", "frompartner", "topartner"),
            },
        ),
    )

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        if request.user.has_perm('bots.change_translate'):
            extra_context['message_types'] = json.dumps(get_grammars())
            extra_context['tscripts'] = json.dumps(get_mappings())
        return super().add_view(request, form_url, extra_context=extra_context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        if request.user.has_perm('bots.change_translate'):
            extra_context['message_types'] = json.dumps(get_grammars())
            extra_context['tscripts'] = json.dumps(get_mappings())
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    def changelist_view(self, request, extra_context=None):
        """Set title with bots model._meta.verbose_name_plural"""
        extra_context = extra_context or {}
        extra_context["title"] = f"Bots {self.model._meta.verbose_name_plural.title()}"
        fromessagetype = request.GET.get('frommessagetype')
        if fromessagetype:
            extra_context["title"] += f": {fromessagetype}"
        fromeditype = request.GET.get('fromeditype__exact')
        if fromeditype:
            extra_context["title"] += f" ({fromeditype})"
        alt = request.GET.get('alt')
        if alt:
            extra_context["title"] += f": {alt}"
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(models.uniek)
class UniekAdmin(BotsAdmin):
    """Bots counters admin"""

    def has_add_permission(self, request):
        """no adding counters permission"""
        return False

    def has_delete_permission(self, request, obj=None):
        """no deleting all counters permission"""
        if obj and obj.domein in ['bots_cleanup_day', 'messagecounter']:
            return False
        return request.user.has_perm('bots.delete_uniek')

    actions = None
    save_on_top = False
    list_display = ('domein', 'nummer')
    readonly_fields = ('domein',)  # never edit the domein field
    ordering = ('domein',)
    search_fields = ('domein',)
    fieldsets = (
        (None, {
            'fields': ('domein', 'nummer'),
        }),
    )


# User - change the default display of user screen
UserAdmin.save_on_top = True
UserAdmin.list_display = (
    'username',
    'first_name',
    'last_name',
    'email',
    'is_active',
    'is_staff',
    'is_superuser',
    'date_joined',
    'last_login',
)
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
