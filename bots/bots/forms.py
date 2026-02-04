# -*- coding: utf-8 -*-
"""
Bots forms
"""
# pylint: disable=missing-class-docstring, missing-function-docstring, protected-access, too-few-public-methods

import django
from django.core.validators import validate_unicode_slug

from . import botsglobal
from . import models
from . import viewlib
from .botsconfig import ERROR, DONE, RESEND, NO_RETRY, SPLITUP, TRANSLATED
from .botslib import gettext as _
from .models import reverse_lazy


HIDDENINPUT = django.forms.widgets.HiddenInput

LIMIT = 15
if botsglobal.ini:
    LIMIT = botsglobal.ini.getint('settings', 'limit', LIMIT)

LIMITS = (
    (10, '10'),
    (15, '15'),
    (20, '20'),
    (25, '25'),
    (30, '30'),
    (50, '50'),
    (75, '75'),
    (100, '100'),
    (150, '150'),
    (200, '200'),
    (250, '250'),
)
if LIMIT not in [a for a, b in LIMITS]:
    LIMITS += ((LIMIT, str(LIMIT)),)
LIMITS = sorted(LIMITS)

REFRESHS = (
    ('', '---'),
    (30, _('30 sec')),
    (60, _('1 min')),
    (120, _('2 mins')),
    (180, _('3 mins')),
    (240, _('4 mins')),
    (300, _('5 mins')),
    (600, _('10 mins')),
    (900, _('15 mins')),
    (1200, _('20 mins')),
    (1800, _('30 mins')),
    (2700, _('45 mins')),
    (3600, _('1 hour')),
)

FILENAME_WIDGET_TITLE = _(
    'Enter filename(s): (several values possible: myfile.xml -myfile_xxx.xml ...)')
REFERENCE_WIDGET_TITLE = _('Enter reference(s): (several values possible: 123456 -12345678 ...)')


INDENTS = {
    'edifact': ['edifact'],
    'x12': ['x12'],
    'json': [str(i) for i in range(0, 7)],
    "xml": ["\t", "0"] + [" " * i for i in range(1, 7)],
    'html': ['html'],
}
INDENTS.update({
    'xmlnocheck': INDENTS['xml'],
    'jsonnocheck': INDENTS['json'],
})

INDENT_TYPE = {
    'text/xml': 'xml',
    'application/xml': 'xml',
    'application/json': 'json',
    'text/html': 'html',
}

SKIP_INDENT_TYPES = [
    "message/rfc822",  # email
    "multipart/mixed",  # email
]

INDENT_CHOICES = {
    'edifact': [('edifact', 'edifact')],
    'x12': [('x12', 'x12')],
    'json': [(str(i), str(i)) for i in INDENTS['json']],
    'xml': [('\t', 'tab'), ('0', '0')] + [(' ' * i, str(i)) for i in range(1, 7)],
    'html': [('html', 'html')],
}
INDENT_CHOICES.update({
    'xmlnocheck': INDENT_CHOICES['xml'],
    'jsonnocheck': INDENT_CHOICES['json'],
})

DEFAULT_INDENT = {
    'edifact': 'edifact',
    'x12': 'x12',
    'json': '2',
    'xml': 4 * ' ',
    'templatehtml': 'html',
    'html': 'html',
}
DEFAULT_INDENT.update({
    'xmlnocheck': DEFAULT_INDENT['xml'],
    'jsonnocheck': DEFAULT_INDENT['json'],
})


def append_excludes(choices: list, num: bool = False) -> list:
    """Return new list with input and his copy with '-' to all first elem tuple"""
    if num:
        return choices + [
            (f"-{choice[0]}" if choice[0] == 0 else -choice[0], f"- {choice[1]}")
            for choice in choices[1:]]
    return choices + [(f"-{choice[0]}", f"- {choice[1]}") for choice in choices[1:]]


STATUST_CHOICES = append_excludes([('', _('Status'))] + models.STATUST, num=True)
REPORT_STATUS = [('', _('Status')), (ERROR, _('Error')), (0, _('Done'))]

EDITYPESLIST = append_excludes(models.EDITYPESLIST)
CONFIRMTYPELIST = append_excludes(models.CONFIRMTYPELIST)


class BotsForm(django.forms.Form):
    idta = django.forms.IntegerField(required=False, label=_('Index'))
    sortedby = django.forms.CharField(required=False, initial='idta', widget=HIDDENINPUT())
    sortedasc = django.forms.BooleanField(required=False, initial=False, widget=HIDDENINPUT())
    datefrom = django.forms.DateTimeField(
        required=False, initial=viewlib.datetimefrom, label=_('Date from'))
    dateuntil = django.forms.DateTimeField(
        required=False, initial=viewlib.datetimeuntil, label=_('Date until'))
    page = django.forms.IntegerField(required=False, initial=1)
    limit = django.forms.TypedChoiceField(required=False, choices=LIMITS, initial=LIMIT, coerce=int)
    refresh = django.forms.TypedChoiceField(required=False, choices=REFRESHS, initial='', coerce=int)
    selection = django.forms.ChoiceField(choices=[], required=False, initial='')
    popup = django.forms.BooleanField(label=_('No menu'), required=False, initial=False)
    admlink = django.forms.BooleanField(required=False, initial=False, label=_('Admin links'))

    limit.widget.attrs.update(title=_('Items per page'))
    admlink.widget.attrs.update(title=admlink.label)
    idta.widget.attrs.update(
        title=idta.label, placeholder=idta.label,
    )
    datefrom.widget.attrs.update(
        size='15', title=datefrom.label, placeholder=datefrom.label,
    )
    dateuntil.widget.attrs.update(
        size='15', title=dateuntil.label, placeholder=dateuntil.label,
    )

    action = None

    class Meta:
        model = None
        fields = []

    def __init__(self, *args, **kwargs):
        # pylint: disable=too-many-branches
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        self.fields['selection'].choices = viewlib.get_user_selections(self)
        if not self.request.user.has_perm('bots.change_mutex'):
            self.fields['admlink'].widget = HIDDENINPUT()
        self.initials = {}
        for key, field in self.fields.items():
            if field.initial:
                self.initials[key] = field.initial() if callable(field.initial) else field.initial

        # idta - reportidta
        if args and isinstance(args[0], dict):
            data = args[0]
            if data.get('idta') and 'idta' in self.fields:
                if getattr(self.request, 'GET', None):
                    if 'datefrom' not in self.request.GET:
                        data['datefrom'] = None
                    if 'dateuntil' not in self.request.GET:
                        data['dateuntil'] = None
            if data.get('reportidta'):
                # from report idta, set datefrom/dateuntil
                if 'reportidta' in self.fields:
                    if getattr(self.request, 'GET', None):
                        if 'datefrom' not in self.request.GET:
                            data['datefrom'] = None
                        if 'dateuntil' not in self.request.GET:
                            data['dateuntil'] = None
                else:
                    # GET (outgoing, document, ...)/?reportidta=xxxx
                    viewlib.report2dates(data)

        # Fields choices
        if 'idroute' in self.fields:
            self.fields['idroute'].choices = append_excludes(models.getroutelist())
        if 'fromchannel' in self.fields:
            fromchannels = models.getfromchannels()
            self.fromchannels_types = {c[0]: c[1].split(' ')[-1].strip('()') for c in fromchannels[1:]}
            self.fields['fromchannel'].choices = append_excludes(fromchannels)
        if 'tochannel' in self.fields:
            tochannels = models.gettochannels()
            self.tochannels_types = {c[0]: c[1].split(' ')[-1].strip('()') for c in tochannels[1:]}
            self.fields['tochannel'].choices = append_excludes(tochannels)
        if 'frompartner' in self.fields:
            partners = models.getpartners()
            self.partners = [p[0] for p in partners[1:]]
            partners_choices = append_excludes(partners)
            self.fields['frompartner'].choices = partners_choices
            self.fields['topartner'].choices = partners_choices

        onkeydownsubmits = [
            k for k in self.fields.keys()
            if isinstance(self.fields[k], (
                django.forms.fields.CharField,
                django.forms.IntegerField,
                django.forms.DateTimeField,
            ))
        ]
        for field in onkeydownsubmits:
            self.fields[field].widget.attrs.update(
                onkeydown="if (event.keyCode == 13) { this.form.submit();return false;}")

    def clean_admlink(self):
        return 1 if self.cleaned_data.get('admlink') else ''

    def clean_lastrun(self):
        return 1 if self.cleaned_data.get('lastrun') else ''

    def clean_popup(self):
        return 1 if self.cleaned_data.get('popup') else ''

    def clean_retransmit(self):
        return 1 if self.cleaned_data.get('retransmit') else ''

    def clean_sortedby(self):
        sortedby = self.cleaned_data.get('sortedby')
        if sortedby and sortedby not in self.Meta.fields:
            raise django.forms.ValidationError(_('Invalid sorting field: "%s"') % sortedby)
        return sortedby


class Select(BotsForm):
    template = 'bots/selectform.html'
    selection_name = django.forms.CharField(required=False, max_length=64)
    selection_name.widget.attrs.update(
        placeholder=_('Selection'), size='10',
        title=_('Name of the selection to be saved'),
        # pattern='[A-Za-z0-9 ]+',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in ['page', 'limit', 'refresh']:
            self.fields[field].widget = HIDDENINPUT()
        self.fields['selection'].widget.attrs.update(
            onchange=f"document.location.href='{self.action}?select&selection=' + this.value;")
        # Add onchange event listner to add or remove clear field style and button
        for field in [k for k in self.fields.keys() if not self.fields[k].widget.is_hidden]:
            if field not in ['selection', 'selection_name']:
                self.fields[field].widget.attrs.update(onchange='fieldchange(this)')

    def clean_selection_name(self):
        """Clean invalid characters"""
        selection_name = self.cleaned_data.get('selection_name')
        if selection_name:
            validate_unicode_slug(selection_name)
        return selection_name


class View(BotsForm):
    actions = django.forms.ChoiceField(choices=[], required=False, initial='')

    actions.widget.attrs.update({
        'onchange': 'update_selcount()',
    })

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["actions"].choices = [("", f"--- {_('Action')} ---"),]
        onchangesubmits = [
            k for k in self.fields.keys()
            if isinstance(self.fields[k], (
                django.forms.BooleanField,
                django.forms.IntegerField,
            ))
            or getattr(self.fields[k].widget, 'input_type', '') == 'select'
            and k not in ['selection', 'actions', 'refresh']
            and not self.fields[k].widget.is_hidden
        ]
        for field in onchangesubmits:
            self.fields[field].widget.attrs.update(onchange='this.form.submit()')
        self.fields['refresh'].widget.attrs.update(
            onchange='if (!this.value) {return false;}this.form.submit()',
            title=_('Refresh page timer'),
        )
        self.fields['selection'].widget.attrs.update(
            onchange=f"document.location.href='{self.action}?selection=' + this.value;")
        if 'frompartner' in self.fields:
            self.inactive_partners = models.getinactivepartners()


class ReportsForm(BotsForm):
    action = reverse_lazy('bots:reports')

    class Meta:
        model = models.report
        fields = [f.name for f in model._meta.get_fields()]

    status = django.forms.TypedChoiceField(
        choices=append_excludes(REPORT_STATUS, num=True),
        required=False,
        initial='',
        coerce=int,
        label=_('State'),
    )
    type = django.forms.ChoiceField(
        choices=append_excludes([
            models.DEFAULT_ENTRY,
            ('new', _('New')),
            ('resend', _('Resend')),
            ('rereceive', _('Rereceive')),
            ('automaticretrycommunication', _('Retry')),
        ]),
        required=False,
        initial='',
        label=_('Type'),
    )
    rsrv1 = django.forms.CharField(
        required=False, label=_('Commandline'), max_length=256,
        widget=django.forms.Textarea(),
    )
    acceptance = django.forms.TypedChoiceField(
        choices=[models.DEFAULT_ENTRY, (-1, 'False'), (1, _('True'))],
        coerce=int,
        required=False,
        initial='',
        label=_('Acceptance'),
    )

    rsrv1.widget.attrs.update(
        placeholder=_('Commandline'),
        rows=2, cols=35,
        title=_(
            'Filter command line (several value possible):'
            ' myroute -hiddenroute_otherroute ...)'),
    )

    def __init__(self, *args, **kwargs):
        if args and not args[0].get('idta'):
            # GET reports/?outidta=xxxx
            # GET reports/?inidta=xxxx
            idta = viewlib.get_reportidta(args[0])
            if idta:
                try:
                    args[0]['idta'] = idta
                except AttributeError:
                    args = (args[0].copy(),) + args[1:]
                    args[0]['idta'] = idta
        super().__init__(*args, **kwargs)
        self.fields['admlink'].widget = HIDDENINPUT()


class SelectReports(Select, ReportsForm):
    title = _('Select reports')


class ViewReports(View, ReportsForm):
    template = 'bots/reports.html'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['idta'].widget = HIDDENINPUT()
        if self.request.user.has_perm('bots.delete_report'):
            self.fields['actions'].choices += [('delete', _('Delete report(s) & in/out'))]
        else:
            self.fields['actions'].widget = HIDDENINPUT()


class IncomingForm(BotsForm):
    action = reverse_lazy('bots:incoming')

    class Meta:
        model = models.filereport
        fields = [f.name for f in model._meta.get_fields()]

    reportidta = django.forms.IntegerField(required=False, label=_('Report'))
    statust = django.forms.TypedChoiceField(
        choices=STATUST_CHOICES,
        required=False,
        initial='',
        coerce=int,
        label=_('Status'),
    )
    idroute = django.forms.ChoiceField(choices=[], required=False, initial='', label=_('Route'))
    fromchannel = django.forms.ChoiceField(choices=[], required=False, label=_('From channel'))
    tochannel = django.forms.ChoiceField(choices=[], required=False, label=_('To channel'))
    frompartner = django.forms.ChoiceField(choices=[], required=False, label=_('From partner'))
    topartner = django.forms.ChoiceField(choices=[], required=False, label=_('To partner'))
    ineditype = django.forms.ChoiceField(choices=EDITYPESLIST, required=False)
    inmessagetype = django.forms.ChoiceField(choices=[], required=False)
    outeditype = django.forms.ChoiceField(choices=EDITYPESLIST, required=False)
    outmessagetype = django.forms.ChoiceField(choices=[], required=False)
    infilename = django.forms.CharField(
        required=False, label=_('InFile'), max_length=512,
        widget=django.forms.Textarea(),
    )
    outfilename = django.forms.CharField(
        required=False, label=_('OutFile'), max_length=512,
        widget=django.forms.Textarea(),
    )
    errortext = django.forms.CharField(
        required=False, label=_('Error'), max_length=256,
        widget=django.forms.Textarea(),
    )
    lastrun = django.forms.BooleanField(required=False, initial=False)
    retransmit = django.forms.BooleanField(required=False, initial=False, label=_('ReReceive'))
    divtext = django.forms.CharField(
        required=False, label=_('MappingScript'), max_length=256,
    )

    reportidta.widget.attrs.update(
        title=reportidta.label, placeholder=reportidta.label,
    )
    divtext.widget.attrs.update(
        placeholder=_('mapping'),
    )
    infilename.widget.attrs.update(
        placeholder=_('Incoming filename'),
        rows=1, cols=15,
        title=FILENAME_WIDGET_TITLE,
        # autofocus=True,
    )
    outfilename.widget.attrs.update(
        placeholder=_('Outgoing filename'),
        rows=1, cols=15,
        title=FILENAME_WIDGET_TITLE,
    )
    errortext.widget.attrs.update(
        placeholder=_('Error text'),
        rows=1, cols=20,
        title=_('Search error'),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['inmessagetype'].choices = append_excludes(models.getinmessagetypes())
        self.fields['outmessagetype'].choices = append_excludes(models.getoutmessagetypes())


class SelectIncoming(Select, IncomingForm):
    title = _('Select incoming')


class ViewIncoming(View, IncomingForm):
    template = 'bots/incoming.html'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request.user.has_perm('bots.delete_filereport'):
            self.fields['actions'].choices += [('delete', _('Delete'))]
        if self.request.user.has_perm('bots.change_mutex'):
            self.fields['actions'].choices += [('rereceive', _('Rereceive'))]
        if len(self.fields['actions'].choices) < 2:
            self.fields['actions'].widget = HIDDENINPUT()


class DocumentForm(BotsForm):
    action = reverse_lazy('bots:document')

    class Meta:
        model = models.ta
        fields = [f.name for f in model._meta.get_fields()]

    status = django.forms.TypedChoiceField(
        choices=[
            models.DEFAULT_ENTRY,
            (SPLITUP, _('Document-in')),
            (TRANSLATED, _('Document-out')),
        ],
        required=False,
        coerce=int,
        label=_('Phase'),
    )
    allstatus = django.forms.BooleanField(required=False, initial=False, label=_('All Phases'))
    idroute = django.forms.ChoiceField(choices=[], required=False, initial='', label=_('Route'))
    fromchannel = django.forms.ChoiceField(choices=[], required=False, label=_('From channel'))
    frompartner = django.forms.ChoiceField(choices=[], required=False, label=_('From partner'))
    topartner = django.forms.ChoiceField(choices=[], required=False, label=_('To partner'))
    editype = django.forms.ChoiceField(choices=EDITYPESLIST, required=False)
    messagetype = django.forms.ChoiceField(required=False)
    confirmtype = django.forms.ChoiceField(
        choices=CONFIRMTYPELIST, required=False, initial='',
    )
    confirmidta = django.forms.IntegerField(required=False, label=_('ConfirmFile'))
    contenttype = django.forms.CharField(
        required=False, label=_('Content-Type'), max_length=70,
        widget=django.forms.Textarea(),
    )
    reference = django.forms.CharField(
        required=False, label=_('Reference'), max_length=512,
        widget=django.forms.Textarea(),
    )
    filename = django.forms.CharField(
        required=False, label=_('Filename'), max_length=512,
        widget=django.forms.Textarea(),
    )
    lastrun = django.forms.BooleanField(required=False, initial=False)

    confirmidta.widget.attrs.update(
        title=confirmidta.label, placeholder=confirmidta.label,
    )
    contenttype.widget.attrs.update(
        placeholder=_('text/xml'),
        rows=1, cols=16,
    )
    reference.widget.attrs.update(
        placeholder=_('Enter reference'),
        rows=1, cols=22,
        title=REFERENCE_WIDGET_TITLE,
    )
    filename.widget.attrs.update(
        placeholder=_('Filename'),
        rows=1, cols=22,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.initial.get('allstatus') or args and args[0].get('allstatus'):
            self.fields['status'].choices = [models.DEFAULT_ENTRY] + models.STATUS[1:]
        getmessagetypes = models.getallmessagetypes
        if self.initial.get('status') == SPLITUP:
            getmessagetypes = models.getinmessagetypes
        elif self.initial.get('status') == TRANSLATED:
            getmessagetypes = models.getoutmessagetypes
        self.fields['messagetype'].choices = append_excludes(getmessagetypes())


class SelectDocument(Select, DocumentForm):
    title = _('Select document')


class ViewDocument(View, DocumentForm):
    template = 'bots/document.html'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['idta'].widget = HIDDENINPUT()
        self.fields['actions'].widget = HIDDENINPUT()
        self.fields['reference'].widget.attrs.update(autofocus=True)


class OutgoingForm(BotsForm):
    action = reverse_lazy('bots:outgoing')

    class Meta:
        model = models.ta
        fields = [f.name for f in model._meta.get_fields()]

    statust = django.forms.TypedChoiceField(
        choices=append_excludes([
            ('', _('Status')),
            (ERROR, _('Error')), (DONE, _('Done')),
            (RESEND, _('Resend')), (NO_RETRY, _('No retry')),
        ], num=True),
        required=False,
        initial='',
        coerce=int,
        label=_('Status'),
    )
    idroute = django.forms.ChoiceField(choices=[], required=False, initial='', label=_('Route'))
    tochannel = django.forms.ChoiceField(choices=[], required=False, label=_('To channel'))
    frompartner = django.forms.ChoiceField(choices=[], required=False, label=_('From partner'))
    topartner = django.forms.ChoiceField(choices=[], required=False, label=_('To partner'))
    editype = django.forms.ChoiceField(choices=EDITYPESLIST, required=False)
    messagetype = django.forms.ChoiceField(required=False)
    filename = django.forms.CharField(
        required=False, label=_('OutFile'), max_length=512,
        widget=django.forms.Textarea(),
    )
    reference = django.forms.CharField(
        required=False, label=_('Reference'), max_length=512,
        widget=django.forms.Textarea(),
    )
    errortext = django.forms.CharField(
        required=False, label=_('Error'), max_length=256,
        widget=django.forms.Textarea(),
    )
    lastrun = django.forms.BooleanField(required=False, initial=False)
    retransmit = django.forms.BooleanField(required=False, initial=False, label=_('Resend'))
    testindicator = django.forms.CharField(
        required=False, initial='', max_length=12, label=_('Test'),
    )

    filename.widget.attrs.update(
        placeholder=_('Enter filename'),
        rows=1, cols=15,
        title=FILENAME_WIDGET_TITLE,
    )
    reference.widget.attrs.update(
        placeholder=_('Enter reference'),
        rows=1, cols=22,
        title=REFERENCE_WIDGET_TITLE,
    )
    errortext.widget.attrs.update(
        placeholder=_('Error text'),
        rows=1, cols=20,
        title=_('Search error'),
    )
    testindicator.widget.attrs.update(
        size=1,
        title=_('Test indicator'),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['messagetype'].choices = append_excludes(models.getoutmessagetypes())


class SelectOutgoing(Select, OutgoingForm):
    title = _('Select outgoing')


class ViewOutgoing(View, OutgoingForm):
    template = 'bots/outgoing.html'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request.user.has_perm('bots.change_mutex'):
            self.fields['actions'].choices += [
                ('resend', _('Resend')),
                ('noautomaticretry', _('No automatic retry')),
            ]
        else:
            self.fields['actions'].widget = HIDDENINPUT()


class ProcessForm(BotsForm):
    action = reverse_lazy('bots:process')

    class Meta:
        model = models.ta
        fields = [f.name for f in model._meta.get_fields()]

    idroute = django.forms.ChoiceField(choices=[], required=False, initial='', label=_('Route'))
    fromchannel = django.forms.ChoiceField(choices=[], required=False, label=_('From channel'))
    tochannel = django.forms.ChoiceField(choices=[], required=False, label=_('To channel'))
    errortext = django.forms.CharField(
        required=False, label=_('Error'), max_length=256,
        widget=django.forms.Textarea(),
    )
    lastrun = django.forms.BooleanField(required=False, initial=False)

    errortext.widget.attrs.update(
        placeholder=_('Error'),
        rows=1, cols=20,
        title=_('Search process error'),
    )


class SelectProcess(Select, ProcessForm):
    title = _('Select process errors')


class ViewProcess(View, ProcessForm):
    template = 'bots/process.html'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['idta'].widget = HIDDENINPUT()
        self.fields['actions'].widget = HIDDENINPUT()


class ConfirmForm(BotsForm):
    action = reverse_lazy('bots:confirm')

    class Meta:
        model = models.ta
        fields = [f.name for f in model._meta.get_fields()]

    confirmtype = django.forms.ChoiceField(
        choices=CONFIRMTYPELIST, required=False, initial='',
        label=_('Confirm Type'),
    )
    confirmed = django.forms.ChoiceField(
        choices=[
            models.DEFAULT_ENTRY,
            ('0', _('Unconfirmed')),
            ('1', _('Confirmed')),
        ],
        required=False,
        initial='',
        label=_('Confirmation'),
    )
    confirmidta = django.forms.IntegerField(required=False, label=_('ConfirmFile'))
    idroute = django.forms.ChoiceField(choices=[], required=False, initial='', label=_('Route'))
    editype = django.forms.ChoiceField(choices=EDITYPESLIST, required=False)
    messagetype = django.forms.ChoiceField(choices=[], required=False)
    frompartner = django.forms.ChoiceField(choices=[], required=False, label=_('From partner'))
    topartner = django.forms.ChoiceField(choices=[], required=False, label=_('To partner'))
    fromchannel = django.forms.ChoiceField(choices=[], required=False, label=_('From channel'))
    tochannel = django.forms.ChoiceField(choices=[], required=False, label=_('To channel'))
    filename = django.forms.CharField(
        required=False, label=_('File'), max_length=512,
        widget=django.forms.Textarea(),
    )
    reference = django.forms.CharField(
        required=False, label=_('Reference'), max_length=512,
        widget=django.forms.Textarea(),
    )

    confirmidta.widget.attrs.update(
        title=confirmidta.label, placeholder=confirmidta.label,
    )
    filename.widget.attrs.update(
        placeholder=_('File'),
        rows=1, cols=18,
        title=FILENAME_WIDGET_TITLE,
    )
    reference.widget.attrs.update(
        placeholder=_('Enter reference'),
        rows=1, cols=25,
        title=REFERENCE_WIDGET_TITLE,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['messagetype'].choices = append_excludes(models.getallmessagetypes())


class SelectConfirm(Select, ConfirmForm):
    title = _('Select confirmations')


class ViewConfirm(View, ConfirmForm):
    template = 'bots/confirm.html'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request.user.has_perm('bots.change_ta'):
            self.fields['actions'].choices += [('confirm', _('Confirm manual'))]
        else:
            self.fields['actions'].widget = HIDDENINPUT()
        self.fields['reference'].widget.attrs.update(autofocus=True)


class UploadFileForm(django.forms.Form):
    file = django.forms.FileField(
        label=_('Plugin to read'),
        required=True,
        widget=django.forms.widgets.FileInput(attrs={'size': '100'}),
    )


class PlugoutForm(django.forms.Form):
    action = reverse_lazy('bots:plugout')
    template = 'bots/plugout.html'

    databaseconfiguration = django.forms.BooleanField(
        required=False,
        initial=True,
        label=_('Database configuration'),
        help_text=_('Routes, channels, translations, partners, etc. from the database.'),
    )
    umlists = django.forms.BooleanField(
        required=False,
        initial=True,
        label=_('User code lists'),
        help_text=_('Your user code data from the database.'),
    )
    fileconfiguration = django.forms.BooleanField(
        required=False,
        initial=True,
        label=_('Script files'),
        help_text=_('[bots/usersys] Grammars, mapping scrips, routes scripts, etc.'),
    )
    infiles = django.forms.BooleanField(
        required=False,
        initial=True,
        label=_('Input files'),
        help_text=_('[bots/botssys/infile] Example/test edi files.'),
    )
    charset = django.forms.BooleanField(
        required=False,
        initial=False,
        label=_('Edifact character sets'),
        help_text=_('[bots/usersys/charsets] Seldom needed, only if changed.'),
    )
    databasetransactions = django.forms.BooleanField(
        required=False,
        initial=False,
        label=_('Database transactions'),
        help_text=_(
            'Transaction details of all bots runs from the database.'
            ' Only for support purposes, on request.'
            ' May generate a very large plugin!'
        ),
    )
    data = django.forms.BooleanField(
        required=False,
        initial=False,
        label=_('All transaction files'),
        help_text=_(
            '[bots/botssys/data] Copies of all incoming, intermediate and outgoing files.'
            ' Only for support purposes, on request.'
            ' May generate a very large plugin!'
        ),
    )
    logfiles = django.forms.BooleanField(
        required=False,
        initial=False,
        label=_('Log files'),
        help_text=_(
            '[bots/botssys/logging] Log files from engine, webserver etc.'
            ' Only for support purposes, on request.'
        ),
    )
    config = django.forms.BooleanField(
        required=False,
        initial=False,
        label=_('Configuration files'),
        help_text=_(
            '[bots/config] Your customised configuration files.'
            ' Only for support purposes, on request.'
        ),
    )
    database = django.forms.BooleanField(
        required=False,
        initial=False,
        label=_('SQLite database'),
        help_text=_(
            '[bots/botssys/sqlitedb] Entire database file.'
            ' Only for support purposes, on request.'
        ),
    )


class DeleteForm(django.forms.Form):
    action = reverse_lazy('bots:delete')
    template = 'bots/delete.html'

    delacceptance = django.forms.BooleanField(
        required=False,
        label=_('Delete transactions in acceptance testing'),
        initial=True,
        help_text=_(
            'Delete runs, reports, incoming, outgoing, data files from acceptance testing.'
        ),
    )
    deltransactions = django.forms.BooleanField(
        required=False,
        label=_('Delete transactions'),
        initial=True,
        help_text=_('Delete runs, reports, incoming, outgoing, data files.'),
    )
    deloutfile = django.forms.BooleanField(
        required=False,
        label=_('Delete botssys/outfiles'),
        initial=False,
        help_text=_('Delete files in botssys/outfile.'),
    )
    delcodelists = django.forms.BooleanField(
        required=False,
        label=_('Delete user code lists'),
        initial=False,
        help_text=_('Delete user code lists.'),
    )
    deluserscripts = django.forms.BooleanField(
        required=False,
        label=_('Delete all user scripts'),
        initial=False,
        help_text=_('Delete all scripts in usersys (grammars, mappings etc) except charsets.'),
    )
    delinfile = django.forms.BooleanField(
        required=False,
        label=_('Delete botssys/infiles'),
        initial=False,
        help_text=_('Delete files in botssys/infile.'),
    )
    delconfiguration = django.forms.BooleanField(
        required=False,
        label=_('Delete configuration'),
        initial=False,
        help_text=_('Delete routes, channels, translations, partners etc.'),
    )
    delpersist = django.forms.BooleanField(
        required=False,
        label=_('Delete persist'),
        initial=False,
        help_text=_('Delete the persist information.'),
    )


class FilerForm(django.forms.Form):
    target = reverse_lazy('bots:filer')
    template = 'bots/filer.html'

    idta = django.forms.IntegerField(required=False, label=_('Index'))
    action = django.forms.ChoiceField(
        choices=[
            ('this', _('this')),
            ('next', _('next')),
            ('previous', _('previous')),
            ('downl', _('Download')),
        ],
        required=False,
        initial='this',
    )
    numbered = django.forms.BooleanField(required=False, initial=True)
    indent = django.forms.ChoiceField(
        choices=[('', '---')],
        required=False,
        initial='',
        label=_('Indent'),
    )
    fontsize = django.forms.ChoiceField(
        choices=[
            (i, f"{i}%")
            for i in [25, 33, 50, 67, 75, 80, 90, 100, 110, 125, 150, 175, 200, 250, 300, 400, 500]
        ],
        required=False,
        initial=100,
    )

    fontsize.widget.attrs.update({
        'onchange': 'SetFontSize(this)',
        'title': _('Text size'),
    })
    indent.widget.attrs.update({
        'onchange': 'this.form.submit()',
        'title': _('Indent'),
    })
    numbered.widget.attrs.update({
        'id': 'cbx_numbered',
    })

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        self.instance = kwargs.pop('ta', None)
        super().__init__(*args, **kwargs)
        self.initials = {}
        self.indent_type = None
        for key, field in self.fields.items():
            if field.initial:
                self.initials[key] = field.initial() if callable(field.initial) else field.initial
        for field in ['idta', 'action']:
            self.fields[field].widget = HIDDENINPUT()
        if self.instance:
            # Set indent type
            if self.instance.contenttype in SKIP_INDENT_TYPES:
                # Skip indent for specific output com content type
                pass
            elif self.instance.editype in INDENTS:
                self.indent_type = self.instance.editype
            elif self.instance.contenttype in INDENT_TYPE:
                self.indent_type = INDENT_TYPE[self.instance.contenttype]
            if self.indent_type:
                self.fields['indent'].choices += INDENT_CHOICES[self.indent_type]
                self.fields["indent"].widget.attrs["title"] += f" ({self.indent_type})"
            else:
                self.fields['indent'].widget.attrs['disabled'] = True
            if self.instance.contenttype == 'application/pdf':
                self.fields['numbered'].widget.attrs['disabled'] = True
