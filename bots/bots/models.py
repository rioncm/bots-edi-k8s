"""
Bots tables databases models for django
Django is not always perfect in generating db - but improving ;-)).
The generated database can be manipulated SQL. see bots/sql/*.
"""
# pylint: disable=invalid-name, too-few-public-methods, missing-class-docstring, missing-function-docstring, consider-using-f-string, line-too-long, too-many-lines
# flake8: noqa:E501

import datetime
import glob
import os
import re
from urllib.parse import quote as urllib_quote

# import django
from django.core.exceptions import ValidationError
from django.core.validators import validate_integer
from django.db import models
from django.urls import reverse_lazy
from django.utils.safestring import mark_safe
from django.utils.timezone import now

from . import botsglobal
from . import validate_email
from .botsconfig import (
    OPEN, ERROR, OK, DONE, RESEND, NO_RETRY,
    EXTERNIN, FILEIN, PARSED, SPLITUP, TRANSLATED, MERGED, FILEOUT, EXTERNOUT,
    PROCESS, DISCARD,
)
from .botslib import gettext as _
from .grammar import grammarread


BOTS_DOCS_URL = 'https://bots.readthedocs.io/en/latest'

ICON_YES = '<span class="icon-yes"></span>'
ICON_NO = '<span class="icon-no"></span>'
ICON_STATUST = '<span class="icon-statust%(statust)s" title="%(title)s"></span>'

# ***Declare constants, mostly codelists.**********************************************
DEFAULT_ENTRY = ('', '---------')

STATUST = [
    (OPEN, _('Open')),
    (ERROR, _('Error')),
    (OK, _('Stuck')),
    (DONE, _('Done')),
    (RESEND, _('Resend')),
    (NO_RETRY, _('No retry')),
]
STATUS = [
    (PROCESS, _('Process')),
    (DISCARD, _('Discarded')),
    (EXTERNIN, _('Received')),
    (FILEIN, _('Infile')),
    (PARSED, _('Parsed')),
    (SPLITUP, _('Document-in')),
    (TRANSLATED, _('Document-out')),
    (MERGED, _('Merged')),
    (FILEOUT, _('Outfile')),
    (EXTERNOUT, _('Send')),
]
GRAMMAR_TYPES = [
    'csv', 'edifact', 'excel', 'fixed', 'idoc', 'json', 'jsonnocheck',
    'templatehtml', 'tradacoms', 'xml', 'xmlnocheck', 'x12',
]
EDITYPES = [
    ('csv', _('csv')),
    ('database', _('database (old)')),
    ('db', _('db')),
    ('edifact', _('edifact')),
    ('email-confirmation', _('email-confirmation')),
    ('excel', _('excel (only incoming)')),
    ('fixed', _('fixed')),
    ('idoc', _('idoc')),
    ('json', _('json')),
    ('jsonnocheck', _('jsonnocheck')),
    ('mailbag', _('mailbag')),
    ('raw', _('raw')),
    ('templatehtml', _('template-html')),
    ('tradacoms', _('tradacoms')),
    ('xml', _('xml')),
    ('xmlnocheck', _('xmlnocheck')),
    ('x12', _('x12')),
]
INOROUT = (
    ('in', _('in')),
    ('out', _('out'))
)
CHANNELTYPE = (
    # Note: in communication.py these channeltypes are converted to channeltype
    # to use in acceptance tests.
    ('file', _('file')),
    ('smtp', _('smtp')),
    ('smtps', _('smtps')),
    ('smtpstarttls', _('smtpstarttls')),
    ('pop3', _('pop3')),
    ('pop3s', _('pop3s')),
    ('pop3apop', _('pop3apop')),
    ('http', _('http')),
    ('https', _('https')),
    ('imap4', _('imap4')),
    ('imap4s', _('imap4s')),
    ('ftp', _('ftp')),
    ('ftps', _('ftps (explicit)')),
    ('ftpis', _('ftps (implicit)')),
    ('sftp', _('sftp (ssh)')),
    ('xmlrpc', _('xmlrpc')),
    ('mimefile', _('mimefile')),
    ('trash', _('trash/discard')),
    ('communicationscript', _('communicationscript')),
    ('db', _('db')),
    ('database', _('database (old)')),
)
CONFIRMTYPE = [
    ('ask-email-MDN', _('ask an email confirmation (MDN) when sending')),
    ('send-email-MDN', _('send an email confirmation (MDN) when receiving')),
    ('ask-x12-997', _('ask a x12 confirmation (997) when sending')),
    ('send-x12-997', _('send a x12 confirmation (997) when receiving')),
    ('ask-edifact-CONTRL', _('ask an edifact confirmation (CONTRL) when sending')),
    ('send-edifact-CONTRL', _('send an edifact confirmation (CONTRL) when receiving')),
]
RULETYPE = (
    ('all', _('Confirm all')),
    ('confirmasked', _('Confirm asked')),
    ('route', _('Route')),
    ('channel', _('Channel')),
    ('frompartner', _('Frompartner')),
    ('topartner', _('Topartner')),
    ('messagetype', _('Messagetype')),
)
ENCODE_MIME = (
    ('always', _('Base64')),
    ('never', _('Never')),
    ('ascii', _('Base64 if not ascii')),
)
EDI_AS_ATTACHMENT = (
    ('attachment', _('As attachment')),
    ('body', _('In body of email')),
    ('multipart', _('multipart')),
    ('multipart_attach', _('multipart/attachment')),
)
ENCODE_ZIP_IN = (
    (1, _('Always unzip file')),
    (2, _('If zip-file: unzip')),
)
ENCODE_ZIP_OUT = (
    (1, _('Always zip')),
)
TRANSLATETYPES = (
    (0, _('Nothing')),
    (1, _('Translate')),
    (2, _('Pass-through')),
    (3, _('Parse & Pass-through')),
)
CONFIRMTYPELIST = [DEFAULT_ENTRY] + CONFIRMTYPE
EDITYPESLIST = [DEFAULT_ENTRY] + EDITYPES


# dirmonitor
def dirmonitor_trigger(cmd):
    """Write request to bots-dirmonitor daemon trigger."""
    with open(botsglobal.ini.get("dirmonitor", "trigger"), "w", encoding="utf8") as trigger:
        trigger.write(cmd)


def reload_dirmonitor():
    """Send reload request to bots-dirmonitor daemon."""
    return dirmonitor_trigger('reload')


def getroutelist():
    """Functions that produced codelists."""
    # needed because the routeid is needed (and this is not theprimary key
    return [DEFAULT_ENTRY] + [
        (val, val) for val in routes.objects.values_list(
            'idroute', flat=True).order_by('idroute').distinct()]


def getinmessagetypes():
    return [DEFAULT_ENTRY] + [
        (val, val) for val in translate.objects.values_list(
            'frommessagetype', flat=True).order_by('frommessagetype').distinct()]


def getoutmessagetypes():
    return [DEFAULT_ENTRY] + [
        (val, val) for val in translate.objects.values_list(
            'tomessagetype', flat=True).order_by('tomessagetype').distinct()]


def getallmessagetypes():
    return [DEFAULT_ENTRY] + [
        (val, val) for val in sorted(set(list(
            translate.objects.values_list('tomessagetype', flat=True).all()) + list(
                translate.objects.values_list('frommessagetype', flat=True).all())))]


def getpartners():
    return [DEFAULT_ENTRY] + [
        (l, f"{l} ({n})")
        for (l, n) in partner.objects.filter(active=True).values_list('idpartner', 'name')]


def getactivepartners():
    return [p[0] for p in partner.objects.filter(active=True).values_list('idpartner')]


def getinactivepartners():
    return [p[0] for p in partner.objects.filter(active=False).values_list('idpartner')]


def get_channels_types(**kwargs):
    query = channel.objects
    if kwargs:
        query = query.filter(**kwargs)
    return dict(query.values_list("idchannel", "type"))


def get_fromchannels_types():
    return get_channels_types(inorout='in')


def getfromchannels():
    return [DEFAULT_ENTRY] + [(l, f"{l} ({t})") for (l, t) in get_fromchannels_types().items()]


def get_tochannels_types():
    return get_channels_types(inorout='out')


def gettochannels():
    return [DEFAULT_ENTRY] + [(l, f"{l} ({t})") for (l, t) in get_tochannels_types().items()]


def get_grammarpath(editype, messagetype):
    """Return bots grammar python path.
    :param editype:
        edifact, x12, xml, json, csv, ...
    :param messagetype:
        ORDERD96A, 850005010, ...
        could accept subdirectory like UBL21.Invoice, 005010.997, ...
    """
    return '%s.py' % os.path.join(
        botsglobal.ini.get('directories', 'usersysabs'),
        'grammars', editype, *messagetype.split('.'))


def list_usersys(*args, **kwargs) -> list:
    """return a list of python script found in usersys *args,
    formated for relative python import str by default ['my_script', 'x12.99700510', ...]

    :args: path args
    :param: fullpath:  default: False
    :param: recursive:  default: True
    """
    scriptdir = os.path.abspath(os.path.join(botsglobal.ini.get("directories", "usersysabs"), *args))

    # Get only python files in usersys !
    if not scriptdir.startswith(botsglobal.ini.get('directories', 'usersysabs')):
        botsglobal.logger.error('Invalid source directory requested: %s', scriptdir)

    if not os.path.isdir(scriptdir):
        # botsglobal.logger.warning(_('Directory not found: %s'), scriptdir)
        return []

    def formatscript(script):
        if kwargs.get('fullpath'):
            return script
        # Python import format, skip scriptdir, add dot for subdir: 'my_script', 'x12.99700510', ...
        return os.path.splitext(script.split(scriptdir)[1].lstrip(os.sep))[0].replace(os.sep, '.')

    scripts = [
        formatscript(script) for script in glob.iglob(
            os.path.join(scriptdir, '**', '*.py'),
            recursive=kwargs.get('recursive', True)
        ) if not script.endswith('__init__.py')
    ]
    scripts.sort()
    return scripts


def get_userscripts(dirname=None, editypes=None, **kwargs):
    """return: dict of editypes containing list of usersys scripts found."""
    scripts = {}
    scriptdirs = ['charsets', 'communicationscripts', 'routescripts']
    editypedirs = ['envelopescripts', 'grammars', 'mappings', 'partners']

    if not dirname:
        for scriptdir in scriptdirs:
            scripts[scriptdir] = list_usersys(scriptdir, **kwargs)
        for editypedir in editypedirs:
            scripts[editypedir] = get_userscripts(editypedir, **kwargs)
        return scripts

    if dirname in scriptdirs:
        return {dirname: list_usersys(dirname, **kwargs)}

    if dirname not in editypedirs:
        botsglobal.logger.error('Invalid usersys directory: %s', dirname)
        return False

    if not editypes:
        editypes = GRAMMAR_TYPES
        if dirname == 'mappings':
            editypes = GRAMMAR_TYPES + ['db', 'raw']

    for editype in editypes:
        scripts[editype] = ['']
        scripts[editype] += list_usersys(dirname, editype, **kwargs) or []

    return scripts


def get_grammars(editypes=None, **kwargs):
    """return: dict of editypes keys containing a list of usersys grammars modules."""
    return get_userscripts('grammars', editypes, **kwargs)


def get_mappings(editypes=None, **kwargs):
    """return: dict of editypes containing a list of usersys mappings modules."""
    return get_userscripts('mappings', editypes, **kwargs)


def delete_from_ta(ta_object):
    """
    try to delete in ta table as much as possible.
    until a MERGE, this is easy.
    but a MERGE can contain messages from other infiles...
    in that case, just leave the MERGE
    """

    def gather_tas_before_merge(ta_object):
        """
        loop over ta tree untill MERGE.
        put all ta status MERGE in one list, others in deletelist
        """
        if ta_object.status == MERGED:
            tas_merge.append(ta_object)
            return
        tas_for_deletion.append(ta_object)
        if ta_object.child:
            # has a explicit child
            tmp_list = [ta.objects.get(idta=ta_object.child)]
        else:
            # search in ta_object-table who is reffering to ta_object
            tmp_list = list(ta.objects.filter(parent=ta_object.idta))
        for child in tmp_list:
            gather_tas_before_merge(child)

    def gather_tas_after_merge(ta_object):
        tas_for_deletion.append(ta_object)
        if ta_object.child:
            # has a explicit child
            tmp_list = [ta.objects.get(idta=ta_object.child)]
        else:
            # search in ta_object-table who is reffering to ta_object
            tmp_list = list(ta.objects.filter(parent=ta_object.idta))
        for child in tmp_list:
            gather_tas_after_merge(child)

    tas_for_deletion = []
    tas_merge = []
    gather_tas_before_merge(ta_object)
    tas_merge = list(set(tas_merge))
    # one MERGE only once in list
    for ta_merge in tas_merge:
        # for each MERGE ta:
        # if all included files in the MERGED file are to be deleted, MERGED can be deleted
        for includedta in ta.objects.filter(
                idta__range=(ta_merge.script, ta_merge.idta), child=ta_merge.idta):
            # select all db-ta_object's included in MERGED ta_object
            if includedta not in tas_for_deletion:
                break
        else:
            gather_tas_after_merge(ta_merge)
    for ta_obj in tas_for_deletion:
        ta_obj.delete()


# ***Database tables that produced codelists.**********************************************
class StripCharField(models.CharField):
    """strip values before saving to database. this is not default in django #%^&*"""

    def get_prep_value(self, value, *args, **kwargs):
        """Convert Python objects (value) to query values (returned)"""
        # pylint: disable=unused-argument
        if isinstance(value, str):
            return value.strip()
        return value


def multiple_email_validator(value):
    """Problems with validating email adresses:
    django's email validating is to strict. (eg if quoted user part, space is not allowed).
    use case: x400 via IPmail (x400 addresses are used in email-addresses).
    Use re-expressions to get this better/conform email standards.

    In bots.ini
    ...
    [webserver]
    validate_email_address = False

    """
    # tric to disable email validation via bots.ini
    if botsglobal.ini.getboolean("webserver", "validate_email_address", True):
        emails = re.split(',(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)', value)  # split emails
        for email in emails:
            if not validate_email.validate_email_address(email):
                raise ValidationError(
                    _('Enter valid e-mail address(es) separated by commas.'), code='invalid')


@mark_safe
def script_link(script, text='', **kwargs):
    """
    if script exists return a plain text name as link; else return "no" icon, plain text name
    used in translate (all scripts should exist, missing script is an error).
    """
    if script and os.path.exists(script):
        script = script.split(
            botsglobal.ini.get('directories', 'usersysabs'))[1].lstrip(os.path.sep)
        attrs = kwargs.get(
            'attrs',
            {'class': kwargs.get(
                'classes',
                'botslink icon-py' if kwargs.get('as_link') else 'button botslink icon-py',
            )})
        return (
            '<a href="%(url)s/?src=%(src)s" title="%(title)s"%(attrs)s'
            ' onclick="return popup(this)">%(text)s</a>'
            % {
                'url': reverse_lazy('bots:srcfiler'),
                'src': urllib_quote(script.encode("utf-8")),
                'text': text,
                'title': f"{_('View source')}: {script}",
                "attrs": "".join((f' {k}="{v}"' for k, v in attrs.items())),
            })
    return f"{ICON_NO} {kwargs.get('noscript_text', text)}"


@mark_safe
def script_viewlink(script, **kwargs):
    """
    if script exists return "yes" icon + view link; else return "no" icon
    used in routes, channels (scripts are optional)
    """
    kwargs.setdefault('noscript_text', '')
    return script_link(
        script, kwargs.pop('text', _('View')), classes='icon-py nowrap botsheader', **kwargs)


class MultipleEmailField(models.CharField):
    default_validators = [multiple_email_validator]
    description = _('One or more e-mail address(es),separated by ",".')


class TextAsInteger(models.CharField):
    default_validators = [validate_integer]


# ***********************************************************************************
# ******** written by webserver ********************************************************
# ***********************************************************************************
class confirmrule(models.Model):
    active = models.BooleanField(default=False)
    confirmtype = StripCharField(max_length=35, choices=CONFIRMTYPE)
    ruletype = StripCharField(max_length=35, choices=RULETYPE)
    negativerule = models.BooleanField(
        default=False,
        help_text=_(
            "Use to exclude. Bots first checks positive rules, than negative rules. "
            "Eg include certain channel, exclude partner XXX."
        ),
    )
    frompartner = models.ForeignKey(
        'partner',
        related_name='cfrompartner',
        null=True,
        on_delete=models.CASCADE,
        blank=True,
        limit_choices_to={'isgroup': False},
    )
    topartner = models.ForeignKey(
        'partner',
        related_name='ctopartner',
        null=True,
        on_delete=models.CASCADE,
        blank=True,
        limit_choices_to={'isgroup': False},
    )
    idroute = StripCharField(max_length=35, null=True, blank=True, verbose_name=_('route'))
    idchannel = models.ForeignKey(
        'channel', null=True, on_delete=models.CASCADE, blank=True, verbose_name=_('channel')
    )
    editype = StripCharField(
        max_length=35, choices=EDITYPES, blank=True
    )  # 20121229"is not used anymore.....editype is always clear from context.
    messagetype = StripCharField(
        max_length=35, blank=True, help_text=_('Eg "850004010" (x12) or "ORDERSD96AUN" (edifact).')
    )
    rsrv1 = StripCharField(max_length=35, blank=True, null=True)  # added 20100501
    rsrv2 = models.IntegerField(null=True)  # added 20100501

    def __str__(self):
        return f"{self.confirmtype} {self.ruletype}"

    class Meta:
        db_table = 'confirmrule'
        verbose_name = _('confirm rule')
        verbose_name_plural = _('confirm rules')
        ordering = [
            'confirmtype',
            'ruletype',
            'negativerule',
            'frompartner',
            'topartner',
            'idroute',
            'idchannel',
            'messagetype',
        ]


class ccodetrigger(models.Model):
    ccodeid = StripCharField(primary_key=True, max_length=35, verbose_name=_('Type of user code'))
    ccodeid_desc = models.TextField(blank=True, null=True, verbose_name=_('Description'))

    def __str__(self):
        return str(self.ccodeid)

    class Meta:
        db_table = 'ccodetrigger'
        verbose_name = _('user code type')
        ordering = ['ccodeid']


class ccode(models.Model):
    ccodeid = models.ForeignKey(
        ccodetrigger, on_delete=models.CASCADE, verbose_name=_('Type of user code')
    )
    leftcode = StripCharField(max_length=35, db_index=True)
    rightcode = StripCharField(max_length=70, db_index=True)
    attr1 = StripCharField(max_length=70, blank=True)
    attr2 = StripCharField(max_length=35, blank=True)
    attr3 = StripCharField(max_length=35, blank=True)
    attr4 = StripCharField(max_length=35, blank=True)
    attr5 = StripCharField(max_length=35, blank=True)
    attr6 = StripCharField(max_length=35, blank=True)
    attr7 = StripCharField(max_length=35, blank=True)
    attr8 = StripCharField(max_length=35, blank=True)

    def __str__(self):
        return f"{self.ccodeid} {self.leftcode} {self.rightcode}"

    class Meta:
        db_table = 'ccode'
        verbose_name = _('user code')
        unique_together = (('ccodeid', 'leftcode', 'rightcode'),)
        ordering = ['ccodeid', 'leftcode']


class channel(models.Model):
    idchannel = StripCharField(max_length=35, primary_key=True)
    inorout = StripCharField(max_length=3, choices=INOROUT, verbose_name=_('in/out'))
    type = StripCharField(max_length=35, choices=CHANNELTYPE)  # protocol type: ftp, smtp, file, etc
    charset = StripCharField(
        max_length=35, default='us-ascii'
    )  # 20120828: not used anymore; in database is NOT NULL
    host = StripCharField(max_length=256, blank=True)
    port = models.PositiveIntegerField(default=0, blank=True, null=True)
    username = StripCharField(max_length=256, blank=True, verbose_name=_('username'))
    secret = StripCharField(max_length=256, blank=True, verbose_name=_('password'))
    starttls = models.BooleanField(
        default=False,
        verbose_name=_('No check from-address'),
        help_text=_('Do not check if incoming "from" email addresses is known.'),
    )  # 20091027: used as 'no check on "from:" email address'
    apop = models.BooleanField(
        default=False,
        verbose_name=_('No check to-address'),
        help_text=_('Do not check if incoming "to" email addresses is known.'),
    )  # 20110104: used as 'no check on "to:" email address'
    remove = models.BooleanField(
        default=False,
        verbose_name=_('remove'),
        help_text=_(
            'Delete incoming edi files after reading.<br>Use in production else files are read again and again.'
        ),
    )
    path = StripCharField(
        max_length=256, blank=True,
        verbose_name=_('path'),
    )  # different from host - in ftp both host and path are used
    filename = StripCharField(
        max_length=256,
        blank=True,
        verbose_name=_('filename'),
        help_text=(
            _('Incoming: use wild-cards eg: "*.edi".') + "<br>" +
            _("Outgoing: many options, see ") +
            f'<a target="_blank" href="{BOTS_DOCS_URL}/configuration/channel/filenames.html">wiki</a>.<br>' +
            _('Advised: use "*" in filename (is replaced by unique counter per channel).') +
            '<br>eg "D_*.edi" gives D_1.edi, D_2.edi, etc.',
        )
    )
    lockname = StripCharField(
        max_length=35,
        blank=True,
        verbose_name=_('Lock-file'),
        help_text=_(
            'Directory locking: if lock-file exists in directory, directory is locked for reading/writing.'
        ),
    )
    syslock = models.BooleanField(
        default=False,
        verbose_name=_('System locks'),
        help_text=_('Use system file locks for reading or writing edi files (windows, *nix).'),
    )
    parameters = StripCharField(
        max_length=70, blank=True,
        verbose_name=_('Parameters'),
        help_text=_('For use in user communication scripting.')
    )
    ftpaccount = StripCharField(
        max_length=35,
        blank=True,
        verbose_name=_('ftp account'),
        help_text=_('FTP accounting information; note that few systems implement this.'),
    )
    ftpactive = models.BooleanField(
        default=False,
        verbose_name=_('ftp active mode'),
        help_text=_('Passive mode is used unless this is ticked.'),
    )
    ftpbinary = models.BooleanField(
        default=False,
        verbose_name=_('ftp binary transfer mode'),
        help_text=_('File transfers are ASCII unless this is ticked.'),
    )
    askmdn = StripCharField(
        max_length=17, blank=True, choices=ENCODE_MIME, verbose_name=_('mime encoding')
    )  # 20100703: used to indicate mime-encoding
    sendmdn = StripCharField(
        max_length=17,
        blank=True,
        choices=EDI_AS_ATTACHMENT,
        verbose_name=_('as body or attachment'),
    )  # 20120922: for email/mime: edi file as attachment or in body
    mdnchannel = StripCharField(
        max_length=35,
        blank=True,
        verbose_name=_('Tmp-part file name'),
        help_text=_(
            'Write file than rename. Bots renames to filename without this tmp-part.<br>'
            'Eg first write "myfile.edi.tmp", tmp-part is ".tmp", rename to "myfile.edi".'
        ),
    )  # 20140113:use as tmp part of file name
    archivepath = StripCharField(
        max_length=256,
        blank=True,
        verbose_name=_('Archive path'),
        help_text=(
            _("Write edi files to an archive.") + "<br>" + _("See ") +
            f'<a target="_blank" href="{BOTS_DOCS_URL}/deployment/archiving.html">wiki</a>.'
            ' Eg: "C:/edi/archive/mychannel".'
        ),
    )  # added 20091028
    desc = models.TextField(max_length=256, null=True, blank=True, verbose_name=_('Description'))
    rsrv1 = TextAsInteger(
        max_length=35,
        blank=True,
        null=True,
        verbose_name=_('Max failures'),
        help_text=_(
            'Max number of connection failures of incommunication before this is reported '
            'as a processerror (default: direct report).'
        ),
    )  # added 20100501 #20140315: used as max_com
    rsrv2 = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_('Max seconds'),
        help_text=_(
            'Max seconds for in-communication channel to run. Purpose: limit incoming edi files; '
            'for large volumes it is better read more often than all files in one time.'
        ),
    )  # added 20100501. 20110906: max communication time.
    rsrv3 = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_('Max days archive'),
        help_text=_(
            'Max number of days files are kept in archive.<br>Overrules global setting in bots.ini.'
        ),
    )  # added 20121030. #20131231: use as maxdaysarchive
    keyfile = StripCharField(
        max_length=256,
        blank=True,
        null=True,
        verbose_name=_('Private key file'),
        help_text=_('Path to file that contains PEM formatted private key.'),
    )  # added 20121201
    certfile = StripCharField(
        max_length=256,
        blank=True,
        null=True,
        verbose_name=_('Certificate chain file'),
        help_text=_('Path to file that contains PEM formatted certificate chain.'),
    )  # added 20121201
    testpath = StripCharField(
        max_length=256,
        blank=True,
        verbose_name=_('Acceptance test path'),
        help_text=(
            _('Path used during acceptance tests, see ') +
            f'<a target="_blank" href="{BOTS_DOCS_URL}/deployment/change-management.html'
            '#isolated-acceptance-testing">wiki</a>.'
        ),
    )  # added 20120111
    debug = models.IntegerField(
        null=True, blank=True,
        choices=[(0, 0), (1, 1), (2, 2), (3, 3), (4, 4), (5, 5)],
        verbose_name=_('Debug level'),
        help_text=_(
            "Channel communication debug level: ftp (0 > 2), pop3 (0 > 2), imap4 (0 > 5), http (0 > 5), "
            "sftp (0=nolog, 1=critical, 2=error, 3=warn, 4=info, 5=debug)"
        ),
    )  # added 20220119

    class Meta:
        ordering = ['idchannel']
        db_table = 'channel'
        verbose_name = _('channel')
        verbose_name_plural = _('channels')

    def __str__(self):
        return f"{self.idchannel} ({self.type})"

    def save(self, *args, **kwargs):
        dirmonitored = False
        ori = None
        if self.pk:
            # Get dirmonitor route
            dirmonitored = routes.objects.filter(
                active=True, dirmonitor=True, fromchannel=self).first()
            ori = channel.objects.get(pk=self.pk) if dirmonitored else None
        super().save(*args, **kwargs)
        if dirmonitored and ori and (ori.path != self.path or ori.filename != self.filename):
            # reload bots-dirmonitor
            reload_dirmonitor()

    @property
    def communicationscript(self):
        return os.path.join(
            botsglobal.ini.get('directories', 'usersysabs'),
            'communicationscripts', self.idchannel + '.py')

    def comscript_link(self):
        return script_viewlink(self.communicationscript)

    comscript_link.admin_order_field = 'idchannel'
    comscript_link.short_description = _('User script')

    @mark_safe
    def routes_link(self, **kwargs):
        # Routes admin link
        if self.inorout == 'in':
            title = _('incoming channel')
            query = self.rfromchannel.all()
            hargs = f"?fromchannel__idchannel__exact={self.idchannel}&"
        else:  # elif self.inorout == "out":
            title = _('outgoing channel')
            query = self.rtochannel.all()
            hargs = f"?tochannel__idchannel__exact={self.idchannel}&"

        kwargs.setdefault('icon', 'ico-routes pad2')
        if len(query) > 1:
            kwargs['title'] = "%s: %s" % (_("Routes"), ", ".join([str(r) for r in query]))
            href = "%s%s" % (reverse_lazy('admin:bots_routes_changelist'), hargs)
            kwargs['icon'] += ' button'
        else:
            if query:
                # len(query) == 1:
                obj = query.first()
                kwargs['title'] = '%s: %s' % (_('Route'), obj)
                kwargs['icon'] += ' botsheader'
                href = '%s?' % reverse_lazy('admin:bots_routes_change', args=[obj.pk])
            else:
                kwargs['title'] = '%s: %s %s' % (_('Add route'), title, self)
                kwargs['icon'] = 'icon-add'
                href = '%s%s' % (
                    reverse_lazy('admin:bots_routes_add'), hargs.replace('__idchannel__exact', ''))
            href += '_popup'
            href += '" onclick="return popup(this)'

        kwargs['href'] = href
        return (
            '<a href="%(href)s" target="_blank" class="%(icon)s" '
            'title="%(title)s"></a>') % kwargs

    routes_link.short_description = _('Routes')


class partner(models.Model):
    idpartner = StripCharField(
        max_length=35, primary_key=True, verbose_name=_('partner identification')
    )
    active = models.BooleanField(default=False)
    isgroup = models.BooleanField(
        default=False,
        help_text=_(
            'Indicate if normal partner or a partner group. Partners can be assigned to partner groups.'
        ),
    )
    name = StripCharField(max_length=256)  # only used for user information
    mail = MultipleEmailField(max_length=256, blank=True)
    cc = MultipleEmailField(
        max_length=256,
        blank=True,
        help_text=_('Multiple CC-addresses supported (comma-separated).'),
    )
    mail2 = models.ManyToManyField(channel, through='chanpar', blank=True)
    group = models.ManyToManyField(
        'self',
        db_table='partnergroup',
        blank=True,
        symmetrical=False,
        limit_choices_to={'isgroup': True},
    )
    rsrv1 = StripCharField(max_length=35, blank=True, null=True)  # added 20100501
    rsrv2 = models.IntegerField(null=True)  # added 20100501
    name1 = StripCharField(max_length=70, blank=True, null=True)  # added 20121201
    name2 = StripCharField(max_length=70, blank=True, null=True)  # added 20121201
    name3 = StripCharField(max_length=70, blank=True, null=True)  # added 20121201
    address1 = StripCharField(max_length=70, blank=True, null=True)  # added 20121201
    address2 = StripCharField(max_length=70, blank=True, null=True)  # added 20121201
    address3 = StripCharField(max_length=70, blank=True, null=True)  # added 20121201
    city = StripCharField(max_length=35, blank=True, null=True)  # added 20121201
    postalcode = StripCharField(max_length=17, blank=True, null=True)  # added 20121201
    countrysubdivision = StripCharField(max_length=9, blank=True, null=True)  # added 20121201
    countrycode = StripCharField(max_length=3, blank=True, null=True)  # added 20121201
    phone1 = StripCharField(max_length=17, blank=True, null=True)  # added 20121201
    phone2 = StripCharField(max_length=17, blank=True, null=True)  # added 20121201
    startdate = models.DateField(blank=True, null=True)  # added 20121201
    enddate = models.DateField(blank=True, null=True)  # added 20121201
    desc = models.TextField(blank=True, null=True, verbose_name=_('Description'))  # added 20121201
    attr1 = StripCharField(
        max_length=35, blank=True, null=True, verbose_name=_('attr1')
    )  # user can customise verbose name
    attr2 = StripCharField(max_length=35, blank=True, null=True, verbose_name=_('attr2'))
    attr3 = StripCharField(max_length=35, blank=True, null=True, verbose_name=_('attr3'))
    attr4 = StripCharField(max_length=35, blank=True, null=True, verbose_name=_('attr4'))
    attr5 = StripCharField(max_length=35, blank=True, null=True, verbose_name=_('attr5'))

    class Meta:
        ordering = ['idpartner']
        db_table = 'partner'
        verbose_name = _('partner')
        verbose_name_plural = _('partners')

    def __str__(self):
        return f"{self.idpartner} ({self.name})"


class PartnerGroepManager(models.Manager):

    def get_queryset(self):
        return super().get_queryset().filter(isgroup=True)


class partnergroep(partner):

    class Meta:
        proxy = True
        ordering = ['idpartner']
        db_table = 'partner'
        verbose_name = _('partnergroup')
        verbose_name_plural = _('partnergroups')

    objects = PartnerGroepManager()

    def save(self, *args, **kwargs):
        self.isgroup = True
        super().save(*args, **kwargs)


class chanpar(models.Model):
    idpartner = models.ForeignKey(partner, on_delete=models.CASCADE, verbose_name=_('partner'))
    idchannel = models.ForeignKey(channel, on_delete=models.CASCADE, verbose_name=_('channel'))
    mail = MultipleEmailField(max_length=256)
    cc = MultipleEmailField(max_length=256, blank=True)  # added 20091111
    askmdn = models.BooleanField(default=False)  # not used anymore 20091019
    sendmdn = models.BooleanField(default=False)  # not used anymore 20091019

    class Meta:
        unique_together = (('idpartner', 'idchannel'),)
        ordering = ['idpartner', 'idchannel']
        db_table = 'chanpar'
        verbose_name = _('email address per channel')
        verbose_name_plural = _('email address per channel')

    def __str__(self):
        return f"{self.idpartner} {self.idchannel} {self.mail}"


class translate(models.Model):
    active = models.BooleanField(default=False)
    fromeditype = StripCharField(
        max_length=35, choices=EDITYPES, help_text=_('Editype to translate from.')
    )
    frommessagetype = StripCharField(max_length=35, help_text=_('Messagetype to translate from.'))
    alt = StripCharField(
        max_length=35,
        null=False,
        blank=True,
        verbose_name=_('Alternative translation'),
        help_text=_('Do translation only for this alternative translation.'),
    )
    frompartner = models.ForeignKey(
        partner,
        related_name='tfrompartner',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        help_text=_('Do translation only for this frompartner.'),
    )
    topartner = models.ForeignKey(
        partner,
        related_name='ttopartner',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        help_text=_('Do translation only for this topartner.'),
    )
    tscript = StripCharField(
        max_length=35,
        verbose_name=_('Mapping Script'),
        help_text=_('Mappingscript to use in translation.'),
    )
    toeditype = StripCharField(
        max_length=35, choices=EDITYPES, help_text=_('Editype to translate to.')
    )
    tomessagetype = StripCharField(max_length=35, help_text=_('Messagetype to translate to.'))
    desc = models.TextField(max_length=256, null=True, blank=True, verbose_name=_('Description'))
    rsrv1 = StripCharField(max_length=35, blank=True, null=True)  # added 20100501
    rsrv2 = models.IntegerField(null=True)  # added 20100501

    @property
    def mappingscript(self) -> str:
        """return full path of mapping script.
           subdirs allowed if '.' in self.tscript
        """
        if self.tscript:
            return '%s.py' % os.path.join(
                botsglobal.ini.get('directories', 'usersysabs'), 'mappings',
                self.fromeditype, *self.tscript.split('.'))
        return ""

    def tscript_link(self):
        return script_link(self.mappingscript, self.tscript, as_link=True)

    tscript_link.admin_order_field = 'tscript'
    tscript_link.short_description = _('Mapping Script')

    @property
    def fromgrammar(self):
        if self.fromgrammar_file:
            return grammarread(self.fromeditype, self.frommessagetype, 'grammars')
        return None

    @property
    def fromgrammar_file(self):
        return get_grammarpath(self.fromeditype, self.frommessagetype)

    def frommessagetype_link(self):
        if self.fromeditype in GRAMMAR_TYPES:
            return script_link(self.fromgrammar_file, self.frommessagetype, as_link=True)
        return self.frommessagetype

    frommessagetype_link.admin_order_field = 'frommessagetype'
    frommessagetype_link.short_description = 'Frommessagetype'

    @property
    def togrammar(self):
        if self.togrammar_file:
            return grammarread(self.toeditype, self.tomessagetype, 'grammars')
        return None

    @property
    def togrammar_file(self):
        return get_grammarpath(self.toeditype, self.tomessagetype)

    def tomessagetype_link(self):
        if self.toeditype in GRAMMAR_TYPES:
            return script_link(self.togrammar_file, self.tomessagetype, as_link=True)
        return self.tomessagetype

    tomessagetype_link.admin_order_field = 'tomessagetype'
    tomessagetype_link.short_description = 'Tomessagetype'

    class Meta:
        db_table = 'translate'
        verbose_name = _('translation rule')
        verbose_name_plural = _('translation rules')
        ordering = ['fromeditype', 'frommessagetype', 'frompartner', 'topartner', 'alt']

    def __str__(self):
        return f"{self.fromeditype} {self.frommessagetype} {self.alt} {self.frompartner} {self.topartner}"


class routes(models.Model):
    idroute = StripCharField(
        max_length=35,
        db_index=True,
        help_text=_(
            'Identification of route; '
            'a composite route consists of multiple parts having the same "idroute".'
        ),
    )
    seq = models.PositiveIntegerField(
        default=1,
        verbose_name=_('Sequence'),
        help_text=_(
            'For routes consisting of multiple parts, this indicates the order these parts are run.'
        ),
    )
    active = models.BooleanField(default=False, help_text=_('Bots-engine only uses active routes.'))
    fromchannel = models.ForeignKey(
        channel,
        related_name='rfromchannel',
        null=True,
        on_delete=models.SET_NULL,
        blank=True,
        verbose_name=_('incoming channel'),
        limit_choices_to={'inorout': 'in'},
        help_text=_('Receive edi files via this communication channel.'),
    )
    fromeditype = StripCharField(
        max_length=35,
        choices=EDITYPES,
        blank=True,
        help_text=_('Editype of the incoming edi files.'),
    )
    frommessagetype = StripCharField(
        max_length=35,
        blank=True,
        help_text=_(
            'Messagetype of incoming edi files. '
            'For edifact: messagetype=edifact; for x12: messagetype=x12.'
        ),
    )
    tochannel = models.ForeignKey(
        channel,
        related_name='rtochannel',
        null=True,
        on_delete=models.SET_NULL,
        blank=True,
        verbose_name=_('outgoing channel'),
        limit_choices_to={'inorout': 'out'},
        help_text=_('Send edi files via this communication channel.'),
    )
    toeditype = StripCharField(
        max_length=35,
        choices=EDITYPES,
        blank=True,
        help_text=_('Filter edi files of this editype for outgoing channel.'),
    )
    tomessagetype = StripCharField(
        max_length=35,
        blank=True,
        help_text=_('Filter edi files of this messagetype for outgoing channel.'),
    )
    alt = StripCharField(
        max_length=35,
        default='',
        blank=True,
        verbose_name=_('Alternative translation'),
        help_text=_(
            'Only use if there is more than one "translation" for the same editype and messagetype.'
        ),
    )
    frompartner = models.ForeignKey(
        partner,
        related_name='rfrompartner',
        null=True,
        on_delete=models.SET_NULL,
        blank=True,
        limit_choices_to={'isgroup': False},
        help_text=_('The frompartner of the incoming edi files.'),
    )
    topartner = models.ForeignKey(
        partner,
        related_name='rtopartner',
        null=True,
        on_delete=models.SET_NULL,
        blank=True,
        limit_choices_to={'isgroup': False},
        help_text=_('The topartner of the incoming edi files.'),
    )
    frompartner_tochannel = models.ForeignKey(
        partner,
        related_name='rfrompartner_tochannel',
        null=True,
        on_delete=models.PROTECT,
        blank=True,
        help_text=_('Filter edi files of this partner/partnergroup for outgoing channel'),
    )
    topartner_tochannel = models.ForeignKey(
        partner,
        related_name='rtopartner_tochannel',
        null=True,
        on_delete=models.PROTECT,
        blank=True,
        help_text=_('Filter edi files of this partner/partnergroup for outgoing channel'),
    )
    testindicator = StripCharField(
        max_length=1,
        blank=True,
        help_text=_('Filter edi files with this test-indicator for outgoing channel.'),
    )
    translateind = models.IntegerField(
        default=1,
        choices=TRANSLATETYPES,
        verbose_name=_('translate'),
        help_text=_('Indicates what to do with incoming files for this route(part).'),
    )
    notindefaultrun = models.BooleanField(
        default=False,
        blank=True,
        verbose_name=_('Not in default run'),
        help_text=_(
            'Do not use this route in a normal run. Advanced, '
            'related to scheduling specific routes or not.'
        ),
    )
    desc = models.TextField(max_length=256, null=True, blank=True, verbose_name=_('Description'))
    rsrv1 = StripCharField(max_length=35, blank=True, null=True)  # added 20100501
    rsrv2 = models.IntegerField(null=True, blank=True)  # added 20100501
    defer = models.BooleanField(
        default=False,
        blank=True,
        verbose_name=_('Defer'),
        help_text=_(
            'Set ready for communication, defer actual communication. '
            'Communication is done later in another route(-part).'
        ),
    )  # added 20100601
    zip_incoming = models.IntegerField(
        null=True,
        blank=True,
        choices=ENCODE_ZIP_IN,
        verbose_name=_('Incoming zip-file handling'),
        help_text=_('Unzip received files.'),
    )  # added 20100501 #20120828: use for zip-options
    zip_outgoing = models.IntegerField(
        null=True,
        blank=True,
        choices=ENCODE_ZIP_OUT,
        verbose_name=_('Outgoing zip-file handling'),
        help_text=_('Send files as zip-files.'),
    )  # added 20100501
    dirmonitor = models.BooleanField(
        default=False,
        help_text=_('Monitor fromchannel (file) with bots-dirmonitor to trigger this route.'),
    )  # added 20220117

    class Meta:
        db_table = 'routes'
        verbose_name = _('route')
        unique_together = (('idroute', 'seq'),)
        ordering = ['idroute', 'seq']

    def __str__(self):
        return f"{self.idroute} {self.seq}"

    def save(self, *args, **kwargs):
        dirmonitored = False
        if self.pk:
            # Get dirmonitor route
            dirmonitored = routes.objects.filter(pk=self.pk, active=True, dirmonitor=True).first()
        super().save(*args, **kwargs)
        # Set same value to notindefaultrun field of others route sequences.
        routes.objects.filter(
            idroute=self.idroute,
            notindefaultrun=not self.notindefaultrun
        ).update(notindefaultrun=self.notindefaultrun)
        if self.dirmonitor and self.active and dirmonitored \
                and dirmonitored.fromchannel == self.fromchannel:
            return
        if self.dirmonitor and self.active or dirmonitored:
            # (De)activate dirmonitor for this route
            # reload bots-dirmonitor
            reload_dirmonitor()

    @property
    def routescript(self):
        return os.path.join(
            botsglobal.ini.get('directories', 'usersysabs'),
            'routescripts', self.idroute + '.py')

    def routescript_link(self):
        return script_viewlink(self.routescript)

    routescript_link.admin_order_field = 'idroute'
    routescript_link.short_description = 'Script'

    @property
    def fromgrammar_file(self):
        return get_grammarpath(self.fromeditype, self.frommessagetype)

    def frommessagetype_link(self):
        if self.fromeditype in GRAMMAR_TYPES:
            return script_link(self.fromgrammar_file, self.frommessagetype, as_link=True)
        return self.frommessagetype

    frommessagetype_link.admin_order_field = 'frommessagetype'
    frommessagetype_link.short_description = 'Frommessagetype'

    @property
    def togrammar_file(self):
        return get_grammarpath(self.toeditype, self.tomessagetype)

    def tomessagetype_link(self):
        # db and raw have no grammar, this is not an error!
        if self.toeditype in GRAMMAR_TYPES:
            return script_link(self.togrammar_file, self.tomessagetype, as_link=True)
        return self.tomessagetype

    tomessagetype_link.admin_order_field = 'tomessagetype'
    tomessagetype_link.short_description = 'Tomessagetype'

    def indefaultrun(self):
        return not self.notindefaultrun

    indefaultrun.boolean = True
    indefaultrun.short_description = _('Default run')

    @mark_safe
    def translate_link(self, **kwargs):
        if self.translateind == 1:
            query = translate.objects.all()
            hargs = '?'
            title = ''
            if self.fromeditype:
                query = query.filter(fromeditype=self.fromeditype)
                hargs += 'fromeditype__exact=%s&' % self.fromeditype
                title = '%s' % self.fromeditype
            if self.frommessagetype and self.frommessagetype != self.fromeditype:
                query = query.filter(frommessagetype=self.frommessagetype)
                hargs += 'frommessagetype=%s&' % self.frommessagetype
                title = '%s %s' % (self.fromeditype, self.frommessagetype)
            if self.alt:
                query = query.filter(alt=self.alt)
                hargs += 'alt=%s&' % self.alt
                title += ' %s' % self.alt
            kwargs.setdefault('icon', 'ico-translate pad2')
            if len(query) > 1:
                kwargs['title'] = '%s: %s' % (_('View translates'), title)
                href = "%s%s" % (reverse_lazy('admin:bots_translate_changelist'), hargs)
                kwargs['icon'] += ' button'
            else:
                if query:
                    # len(query) == 1:
                    obj = query.first()
                    href = '%s?' % reverse_lazy('admin:bots_translate_change', args=[obj.pk])
                    kwargs['title'] = '%s %s: %s' % (_('View translate'), obj.pk, obj)
                    kwargs['icon'] += ' botsheader'
                else:
                    kwargs['title'] = _('Add translate')
                    if title:
                        kwargs['title'] += ': %s' % title
                    kwargs['icon'] = 'icon-add'
                    href = '%s%s' % (
                        reverse_lazy('admin:bots_translate_add'), hargs.replace('__exact', ''))
                href += '_popup'
                href += '''" onclick="return popup(this, '60%', '80%')'''

            kwargs['href'] = href
            return (
                '<a href="%(href)s" target="_blank" class="%(icon)s" '
                'title="%(title)s"></a>') % kwargs
        return ''

    translate_link.admin_order_field = 'translateind'
    translate_link.short_description = ''

    def translt(self):
        if self.translateind in [0, 1, 2, 3]:
            return mark_safe(
                '<span class="icon-translt%(translateind)s" title="%(title)s"></span>' % {
                    'translateind': self.translateind,
                    'title': self.get_translateind_display(),
                })
        return ''

    translt.admin_order_field = 'translateind'
    translt.short_description = _('Translate')


# ***********************************************************************************
# ******** written by engine ********************************************************
# ***********************************************************************************
class filereport(models.Model):
    idta = models.IntegerField(primary_key=True)
    reportidta = models.IntegerField()
    statust = models.IntegerField(choices=STATUST)
    retransmit = models.IntegerField()
    idroute = StripCharField(max_length=35)
    fromchannel = StripCharField(max_length=35)
    tochannel = StripCharField(max_length=35)
    frompartner = StripCharField(max_length=35)
    topartner = StripCharField(max_length=35)
    frommail = StripCharField(max_length=256)
    tomail = StripCharField(max_length=256)
    ineditype = StripCharField(max_length=35, choices=EDITYPES)
    inmessagetype = StripCharField(max_length=35)
    outeditype = StripCharField(max_length=35, choices=EDITYPES)
    outmessagetype = StripCharField(max_length=35)
    incontenttype = StripCharField(max_length=35)
    outcontenttype = StripCharField(max_length=35)
    nrmessages = models.IntegerField()
    ts = models.DateTimeField(db_index=True)  # copied from ta
    infilename = StripCharField(max_length=256)
    inidta = models.IntegerField(null=True)  # not used anymore
    outfilename = StripCharField(max_length=256)
    outidta = models.IntegerField()
    divtext = StripCharField(max_length=128)
    errortext = models.TextField()
    rsrv1 = StripCharField(max_length=128, blank=True, null=True)  # added 20100501; 20120618: email subject; 20220131: len to 128
    rsrv2 = models.IntegerField(null=True)                         # added 20100501
    filesize = models.IntegerField(null=True)                      # added 20121030

    class Meta:
        db_table = 'filereport'
        ordering = ['-idta']

    def statust_icon(self):
        return mark_safe(
            ICON_STATUST % {'statust': self.statust, 'title': self.get_statust_display()})

    def delete(self, *args, **kwargs):
        """Delete this filereport entry and all linked ta entries"""
        botsglobal.logger.debug('Deleting filereport: %s', self.idta)
        ta_object = ta.objects.filter(idta=self.idta).first()
        if ta_object:
            # delete as much as possible in ta table
            delete_from_ta(ta_object)
        super().delete(*args, **kwargs)


class mutex(models.Model):
    # specific SQL is used (database defaults are used)
    mutexk = models.IntegerField(primary_key=True)  # is always value '1'
    mutexer = models.IntegerField()
    ts = models.DateTimeField(default=now)  # timestamp of mutex

    class Meta:
        db_table = 'mutex'
        managed = False


class persist(models.Model):
    # OK, this has gone wrong. There is no primary key here, so django generates this.
    # But there is no ID in the custom sql.
    # Django still uses the ID in sql manager. This leads to an error in snapshot plugin.
    # Disabled this in snapshot function; to fix this really database has to be changed.
    # specific SQL is used (database defaults are used)
    domein = StripCharField(max_length=35)
    botskey = StripCharField(max_length=35)
    content = models.TextField()
    ts = models.DateTimeField(default=now)

    class Meta:
        db_table = 'persist'
        unique_together = (('domein', 'botskey'),)
        managed = False


class report(models.Model):
    idta = models.IntegerField(primary_key=True)  # rename to reportidta
    lastreceived = models.IntegerField()
    lastdone = models.IntegerField()
    lastopen = models.IntegerField()
    lastok = models.IntegerField()
    lasterror = models.IntegerField()
    send = models.IntegerField()
    processerrors = models.IntegerField()
    ts = models.DateTimeField(db_index=True)                    # copied from (runroot)ta
    type = StripCharField(max_length=35)
    status = models.BooleanField()
    rsrv1 = StripCharField(max_length=256, blank=True, null=True)  # added 20100501. 20131230: commandline for the run; 20220201: len > 256
    rsrv2 = models.IntegerField(null=True)                      # added 20100501.
    filesize = models.IntegerField(null=True)                   # added 20121030: total size of messages that have been translated.
    acceptance = models.IntegerField(null=True)                 # added 20130114.

    class Meta:
        db_table = 'report'
        ordering = ['-idta']

    def delete(self, *args, **kwargs):
        """Delete filereport/ta/process entries and linked files (engine logs)"""
        # pylint: disable=broad-exception-caught
        botsglobal.logger.debug('Deleting report: %s', self.idta)
        filereports = filereport.objects.filter(reportidta=self.idta)
        if filereports:
            # delete report filereports
            deleted = []
            for filereport_obj in filereports:
                deleted.append(filereport_obj.idta)
                filereport_obj.delete()
            botsglobal.logger.debug(
                'Report %s: %s filereport(s) deleted: %s',
                self.idta, len(deleted), deleted)

        # PROCESS ERRORS: Delete related process errors ta.status=PROCESS, statust=ERROR
        if self.processerrors:
            try:
                # pylint: disable=no-member
                dateuntil = self.get_next_by_ts().ts
            except Exception:
                dateuntil = datetime.datetime.now()
            procerrs = ta.objects.filter(
                status=PROCESS, statust=ERROR,
                ts__gte=self.ts, ts__lt=dateuntil,
            )
            if procerrs:
                botsglobal.logger.debug(
                    'Report %s: %s process error(s) deleted.',
                    self.idta, len(procerrs))
                procerrs.delete()

        # engine log by report idta
        logfile = os.path.join(
            botsglobal.ini.get('directories', 'logging'), 'engine', str(self.idta),
        )
        if os.path.isfile(logfile):
            if os.access(logfile, os.W_OK):
                os.remove(logfile)
                botsglobal.logger.debug('Report %s: log file deleted.', self.idta)
            else:
                botsglobal.logger.error(_('Could not remove file: %s'), logfile)
        super().delete(*args, **kwargs)


# trigger for sqlite to use local time (instead of utc).
# I can not add this to sqlite specific sql code, as django does not allow complex (begin ... end) sql here.
# CREATE TRIGGER uselocaltime  AFTER INSERT ON ta
# BEGIN
# UPDATE ta
# SET ts = datetime('now','localtime')
# WHERE idta = new.idta ;
# END;
class ta(models.Model):
    # specific SQL is used (database defaults are used)
    idta = models.AutoField(primary_key=True)
    statust = models.IntegerField(choices=STATUST, default=0)
    status = models.IntegerField(choices=STATUS, default=0)
    parent = models.IntegerField(db_index=True, default=0)
    child = models.IntegerField(default=0)
    script = models.IntegerField(default=0)
    idroute = StripCharField(max_length=35, default='')
    filename = StripCharField(max_length=256, default='')
    frompartner = StripCharField(max_length=35, default='')
    topartner = StripCharField(max_length=35, default='')
    fromchannel = StripCharField(max_length=35, default='')
    tochannel = StripCharField(max_length=35, default='')
    editype = StripCharField(max_length=35, default='')
    messagetype = StripCharField(max_length=35, default='')
    alt = StripCharField(max_length=35, default='')
    divtext = StripCharField(max_length=128, default="")       # name of translation script. #20200929: filename of attachment in email
    merge = models.BooleanField(default=False)
    nrmessages = models.IntegerField(default=1)
    testindicator = StripCharField(max_length=10, default='')  # 0:production; 1:test.
    reference = StripCharField(max_length=256, db_index=True, default='')
    frommail = StripCharField(max_length=256, default='')
    tomail = StripCharField(max_length=256, default='')
    charset = StripCharField(max_length=35, default='')
    retransmit = models.BooleanField(default=False)            # 20070831: only retransmit, not rereceive
    contenttype = StripCharField(max_length=35, default='text/plain')
    errortext = models.TextField()                             # 20120921: unlimited length
    ts = models.DateTimeField(default=now)
    confirmasked = models.BooleanField(default=False)          # added 20091019; confirmation asked or send
    confirmed = models.BooleanField(default=False)             # added 20091019; is confirmation received (when asked)
    confirmtype = StripCharField(max_length=35, default="")    # added 20091019
    confirmidta = models.IntegerField(default=0)               # added 20091019
    envelope = StripCharField(max_length=35, default="")       # added 20091024
    botskey = StripCharField(max_length=64, default="")        # added 20091024; 20161122: increase size up to 64
    cc = StripCharField(max_length=512, default="")            # added 20091111
    rsrv1 = StripCharField(max_length=128, default="")         # added 20100501; 20120618: email subject; 20220131: change to 128
    rsrv2 = models.IntegerField(default=0)                     # added 20100501; 20190116: indicate file is mime (1=mime)
    rsrv3 = StripCharField(max_length=35, default="")          # added 20100501; 20131231: envelopeID to explicitly control enveloping (enveloping criterium)
    rsrv4 = models.IntegerField(default=0)                     # added 20100501
    rsrv5 = StripCharField(max_length=256, default="")         # added 20121030; 20190408: envelope data (as filled from mapping) changed to 256
    filesize = models.IntegerField(default=0)                  # added 20121030
    numberofresends = models.IntegerField(default=0)           # added 20121030; if all OK (no resend) this is 0

    class Meta:
        db_table = 'ta'
        ordering = ['-idta']
        managed = False

    def statust_icon(self):
        return mark_safe(
            ICON_STATUST % {'statust': self.statust, 'title': self.get_statust_display()})


class uniek(models.Model):
    # specific SQL is used (database defaults are used)
    domein = StripCharField(max_length=35, primary_key=True, verbose_name=_('Counter domain'))
    nummer = models.IntegerField(verbose_name=_('Last used number'), default=1)

    class Meta:
        db_table = 'uniek'
        verbose_name = _('counter')
        ordering = ['domein']
        managed = False
