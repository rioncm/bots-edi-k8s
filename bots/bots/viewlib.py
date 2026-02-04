"""
Bots viewlib
"""
# pylint: disable=broad-exception-caught

import copy
import datetime
from io import BytesIO
import json
import os
import re
import sys

import django
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from lxml import etree

from . import botsglobal
from . import botslib
from . import models
from .botsconfig import FILEOUT, EXTERNIN, EXTERNOUT, SPLITUP
from .botslib import gettext as _
from .models import urllib_quote


DATE_FORMAT = '%Y-%m-%d'
TIME_FORMAT = '%H:%M:%S'
DATETIME_FORMAT = f"{DATE_FORMAT} {TIME_FORMAT}"


def get_selection_dir(form):
    """Get user selections dir"""
    return os.path.join(
        botsglobal.ini.get('directories', 'users'),
        str(form.request.user.id),
        'selections',
        form.action.split('/')[-1],
    )


def get_selection_file(form, selection):
    """Return selection file path"""
    return os.path.join(get_selection_dir(form), selection)


def get_user_selections(form):
    """Return list of user selections"""
    selections = []
    if form.request:
        selection_dir = get_selection_dir(form)
        selections = os.listdir(selection_dir) if os.path.isdir(selection_dir) else []
    return [("", f"------- {_('Selection')} -------")] + [(v, v) for v in sorted(selections)]


def save_selection(form):
    """Save cleaned_data to json file"""
    cleaned_data = form.cleaned_data
    selection = cleaned_data.pop('selection_name', None) or cleaned_data.pop('selection', None)
    if not selection:
        selection = 'default'
        if os.path.isfile(get_selection_file(form, selection)) or cleaned_data.get('datefrom') \
                or cleaned_data.get('dateuntil'):
            selection = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    cleaned_data['selection'] = selection
    selection_file = get_selection_file(form, selection)
    botslib.dirshouldbethere(os.path.dirname(selection_file))
    cleaned_data = cleaned_data.copy()
    cleaned_data['datefrom'] = str(cleaned_data.get('datefrom', '') or '')
    cleaned_data['dateuntil'] = str(cleaned_data.get('dateuntil', '') or '')
    with open(selection_file, "w", encoding="utf8") as selectionf:
        json.dump(cleaned_data, selectionf)
    botsglobal.logger.info('User selection saved: %s', selection_file)
    messages.add_message(form.request, messages.INFO, _("Selection '%s' saved.") % selection)


def load_selection(request, form, selection='default'):
    """
    Load cleaned_data from json file

    :return: dict
    """
    if request.GET and not request.GET.get('selection'):
        return None
    selection = request.GET.get('selection', selection)
    if selection:
        selection_file = os.path.join(
            botsglobal.ini.get('directories', 'users'),
            str(request.user.id),
            'selections',
            form.action.split('/')[-1],
            selection,
        )
        if os.path.isfile(selection_file):
            with open(selection_file, "r", encoding="utf8") as selectionf:
                return json.load(selectionf)
    return None


def delete_selection(form):
    """Delete selection file"""
    selection = form.cleaned_data['selection']
    selection_file = get_selection_file(form, selection)
    if os.path.isfile(selection_file) and os.access(selection_file, os.W_OK):
        try:
            os.remove(selection_file)
            botsglobal.logger.info('User selection deleted: %s', selection_file)
            messages.add_message(
                form.request, messages.INFO, _("Selection '%s' deleted.") % selection)
            form.cleaned_data['selection'] = ''
            return True
        except Exception:
            pass
    return False


def get_selection_url(form):
    """Return permanent url of selection"""
    url = form.action
    for key, val in form.cleaned_data.items():
        if not val and val != 0 and key not in ['datefrom', 'dateuntil']:
            continue
        if key != 'selection':
            sep = '&' if '?' in url else '?'
            val = urllib_quote(str(val).encode('utf-8')) if val or val == 0 else ''
            url += f"{sep}{key}={val}"
    return url


def safe_int(value) -> int:
    """
    Try to convert value to int else return 0

    :param value: (str/int)

    :return int value or 0
    """
    try:
        return int(value)
    except Exception:
        return 0


def preparereport2view(post, runidta):
    """Add params to display report view"""
    terugpost = post.copy()
    for key in ['selection', 'idta']:
        terugpost.pop(key, None)
    thisrun = models.report.objects.filter(idta=runidta).first()
    if thisrun:
        terugpost['datefrom'] = thisrun.ts
        try:
            nextrun = thisrun.get_next_by_ts()
            terugpost['dateuntil'] = nextrun.ts
        except Exception:
            terugpost['dateuntil'] = datetimeuntil()
    terugpost['sortedby'] = 'ts'
    return terugpost


def get_reportidta(data):
    """return report idta from any ta.idta"""
    inidta = data.get('inidta')
    if data.get('outidta'):
        rootta = django_trace_origin(
            safe_int(data.get('outidta')), {'status': EXTERNIN})
        if rootta:
            inidta = rootta[0].idta
    if inidta:
        filereport = models.filereport.objects.filter(idta=inidta).first()
        if filereport:
            return filereport.reportidta
    return None


def report2dates(data):
    """Search report with reportidta value and add report dates(from/until)"""
    if data.get('reportidta'):
        report = models.report.objects.filter(idta=data.get('reportidta')).first()
        if report:
            data['datefrom'] = report.ts
            try:
                nextrun = report.get_next_by_ts()
                data['dateuntil'] = nextrun.ts
            except Exception:
                data['dateuntil'] = datetimeuntil()


def changepostparameters(post, soort):
    """Filter cleaned data between views"""
    # pylint: disable=too-many-branches
    terugpost = post.copy()
    for key in ['selection', 'idta']:
        terugpost.pop(key, None)
    if soort == 'confirm2in':
        if terugpost.get('confirmtype', '').startswith('ask'):
            terugpost['outeditype'] = terugpost.pop('editype')[0]
            terugpost['outmessagetype'] = terugpost.pop('messagetype')[0]
        else:
            terugpost['ineditype'] = terugpost.pop('editype')[0]
            terugpost['inmessagetype'] = terugpost.pop('messagetype')[0]
        for key in ['confirmtype', 'confirmed']:
            terugpost.pop(key)
    elif soort == 'confirm2out':
        for key in ['confirmtype', 'confirmed', 'fromchannel']:
            terugpost.pop(key)
    elif soort == 'out2in':
        terugpost['outeditype'] = terugpost.pop('editype')[0]
        terugpost['outmessagetype'] = terugpost.pop('messagetype')[0]
        terugpost['outfilename'] = terugpost.pop('filename')[0]
    elif soort == 'out2confirm':
        for key in ['lastrun']:
            terugpost.pop(key, None)
    elif soort == 'in2out':
        terugpost['editype'] = terugpost.pop('outeditype')[0]
        terugpost['messagetype'] = terugpost.pop('outmessagetype')[0]
        terugpost['filename'] = terugpost.pop('outfilename')[0]
        for key in ['ineditype', 'inmessagetype']:
            terugpost.pop(key)
    elif soort == 'in2confirm':
        terugpost['editype'] = terugpost.pop('outeditype')[0]
        terugpost['messagetype'] = terugpost.pop('outmessagetype')[0]
        for key in ['lastrun', 'statust', 'ineditype', 'inmessagetype']:
            terugpost.pop(key, None)
    elif soort.endswith('2report'):
        # when going from in/out (Not used but is working)
        idta = terugpost.pop('idta', None) or terugpost.pop('2report', None)
        for key in list(terugpost.keys()):
            if key not in ['datefrom', 'dateuntil', 'limit', 'popup', 'admlink']:
                terugpost.pop(key)
        if idta:
            # pylint: disable=consider-using-f-string
            terugpost['%sidta' % ('in' if soort.startswith('in') else 'out')] = idta[0]
    elif soort == '2process':
        # when going to process, most parameters are deleted.
        for key in list(terugpost.keys()):
            if key in [
                    'datefrom', 'dateuntil', 'lastrun', 'idroute', 'fromchannel', 'tochannel',
                    'errortext', 'limit', 'popup', 'admlink']:
                # keep these
                continue
            terugpost.pop(key)
    elif soort == 'fromprocess':
        # is OK, all values are used
        pass
    terugpost['sortedby'] = 'ts'
    terugpost['sortedasc'] = False
    terugpost['page'] = 1
    return terugpost


def django_trace_origin(idta, where):
    """
    bots traces back all from the current step/ta_object.
    where is a dict that is used to indicate a condition.
    eg:  {'status':EXTERNIN}
    If bots finds a ta_object for which this is true,
    the ta_object is added to a list.
    The list is returned when all tracing is done,
    and contains all ta_object's for which 'where' is True
    """

    def trace_recurse(ta_object):
        """
        recursive walk over ta_object's backward (to origin).
        If condition is met, add the ta_object to a list
        """
        for parent in get_parent(ta_object):
            donelijst.append(parent.idta)
            for key, value in where.items():
                if getattr(parent, key) != value:
                    break
            else:
                # all where-criteria are true
                # check if we already have this ta_object
                teruglijst.append(parent)
            trace_recurse(parent)

    def get_parent(ta_object):
        """yields the parents of a ta_object"""
        if ta_object.parent:
            if ta_object.parent not in donelijst:  # search via parent
                yield models.ta.objects.get(idta=ta_object.parent)
        else:
            for parent in models.ta.objects.filter(
                    idta__range=(ta_object.script, ta_object.idta), child=ta_object.idta):
                if parent.idta in donelijst:
                    continue
                yield parent

    donelijst = []
    teruglijst = []
    ta_object = models.ta.objects.filter(idta=idta).first()
    if ta_object:
        trace_recurse(ta_object)
    return teruglijst


def trace_document(pquery):
    """
    trace forward & backwardfrom the current step/ta_object (status SPLITUP).
    gathers confirm information
    """

    def trace_forward(ta_object):
        """recursive. walk over ta_object's forward (to exit)."""
        if ta_object.child:
            child = models.ta.objects.get(idta=ta_object.child)
        else:
            try:
                child = models.ta.objects.filter(parent=ta_object.idta)[0]
            except IndexError:
                # no result
                return
        if child.confirmasked:
            if not hasattr(ta_object, 'confirmtext'):
                ta_object.confirmtext = ''
            ta_object.confirmtext += '%(confirmtype)s\n'
            ta_object.confirmtext %= {
                'confirmasked': child.confirmasked,
                'confirmed': child.confirmed,
                'confirmtype': child.confirmtype,
            }
            ta_object.confirmidta = child.confirmidta
        if child.status == EXTERNOUT:
            ta_object.outgoing = child.idta
            ta_object.channel = child.tochannel
        trace_forward(child)

    def trace_back(ta_object):
        """recursive. walk over ta_object's backward (to origin)."""
        if ta_object.parent:
            parent = models.ta.objects.get(idta=ta_object.parent)
        else:
            try:
                # just get one parent
                parent = models.ta.objects.filter(
                    idta__range=(ta_object.script, ta_object.idta), child=ta_object.idta
                )[0]
            except IndexError:
                # no result
                return
        if parent.confirmasked:
            if not hasattr(ta_object, 'confirmtext'):
                ta_object.confirmtext = ''
            ta_object.confirmtext += '%(confirmtype)s\n'
            ta_object.confirmtext %= {
                'confirmasked': parent.confirmasked,
                'confirmed': parent.confirmed,
                'confirmtype': parent.confirmtype,
            }
            ta_object.confirmidta = parent.confirmidta
        if parent.status == EXTERNIN:
            ta_object.incoming = parent.idta
            ta_object.channel = parent.fromchannel
        trace_back(parent)

    # main for trace_document*****************
    for taorg in pquery.object_list:
        taorg.confirmtext = ''
        if taorg.status == SPLITUP:
            trace_back(taorg)
        else:
            trace_forward(taorg)


def gettrace(ta_object):
    """
    recursive. Builds a tree of ta's (a trace) for parameter ta_object.
    children are a list in ta.
    """
    if ta_object.child:
        # has a explicit child
        ta_object.talijst = [models.ta.objects.get(idta=ta_object.child)]
    else:
        # search in ta_object-table who is reffering to ta_object
        ta_object.talijst = list(models.ta.objects.filter(parent=ta_object.idta))
    for child in ta_object.talijst:
        gettrace(child)


def trace2detail(ta_object) -> list:
    """
    Parse ta_oject and his childs to format indicators
    to display in detail view.

    :param ta_object:

    """
    def newbranche(ta_object, level=0):
        def dota(ta_object, isfirststep=False):
            levelindicator = (level) * '| '
            if isfirststep and level:
                ta_object.ind = levelindicator[:-2] + '___'
            elif ta_object.status == FILEOUT and ta_object.nrmessages > 1:
                ta_object.ind = levelindicator
            elif ta_object.status == EXTERNOUT:
                ta_object.ind = levelindicator[:-2]
                if levelindicator:
                    ta_object.ind += 'o=='
            else:
                ta_object.ind = levelindicator
            # ~ ta_object.action = models.ta.objects.only('filename').get(idta=ta_object.script)
            ta_object.channel = ta_object.fromchannel
            if ta_object.tochannel:
                ta_object.channel = ta_object.tochannel
            detaillist.append(ta_object)
            lengtetalijst = len(ta_object.talijst)
            if lengtetalijst > 1:
                for child in ta_object.talijst:
                    newbranche(child, level=level + 1)
            elif lengtetalijst == 1:
                dota(ta_object.talijst[0])

        # start new level
        dota(ta_object, isfirststep=True)

    detaillist = []
    newbranche(ta_object)
    return detaillist


def datetimefrom() -> str:
    """
    Calculate timedelta with maxdays in config.

    :return str fromated datetime:
    """
    terug = datetime.datetime.today() - datetime.timedelta(
        days=botsglobal.ini.getint('settings', 'maxdays', 30)
    )
    return datetime.datetime.strptime(terug.strftime(f"{DATE_FORMAT} 00:00:00"), DATETIME_FORMAT)


def datetimeuntil() -> str:
    """
    It will return the last second of curent day: {TODAY} 23:59:59

    :return str fromated datetime:
    """
    terug = datetime.datetime.today()
    return datetime.datetime.strptime(terug.strftime(f"{DATE_FORMAT} 23:59:59"), DATETIME_FORMAT)


def handlepagination(requestpost, formin):
    """use requestpost to set criteria for pagination in cleaned_data"""
    cleaned_data = formin.cleaned_data
    if 'first' in requestpost:
        cleaned_data['page'] = 1
    elif 'previous' in requestpost:
        cleaned_data['page'] -= 1
    elif 'next' in requestpost:
        cleaned_data['page'] += 1
    elif 'last' in requestpost:
        cleaned_data['page'] = sys.maxsize
    elif 'order' in requestpost:
        # change the sorting order
        if requestpost['order'] == cleaned_data['sortedby']:
            # sort same row, but desc->asc etc
            cleaned_data['sortedasc'] = not cleaned_data['sortedasc']
        else:
            order = requestpost['order'].lower()
            if order in formin.Meta.fields:
                cleaned_data['sortedby'] = order
                cleaned_data['sortedasc'] = bool(order not in ['idta', 'ts'])
            elif not order:
                cleaned_data['sortedby'] = ''
                cleaned_data['sortedasc'] = False


def getidtalastrun() -> int:
    """Return the index (report idta) of the last run"""
    return models.filereport.objects.all().aggregate(
        django.db.models.Max('reportidta'))['reportidta__max']


def filterquery_contains(query, cleaned_data, field):
    """
    filter a query with field__contains = value(s) in cleaned_data[field]
    Could specify several values and negative rules with minus sign to exclude someting.

    ex: cleaned_data['reference'] = '-xxxx1 -xxxx2'

    Or several values:
        cleaned_data['reference'] = '123 xx1 xx2 -xx3 ...'
    """
    for val in cleaned_data.pop(field).split(' '):
        query_filter = query.filter
        if val[0] == '-' and val[1:]:
            val = val[1:]
            query_filter = query.exclude
        query = query_filter(**{f"{field}__contains": val})
    return query


def filterquery(query, org_cleaned_data, **kwargs):
    """
    filter query using the data of the form (mostly in hidden fields).
    parameter 'paginate' controls if pagination is used or not.
    """
    # pylint: disable=too-many-branches
    org_cleaned_data.pop('actions', None)
    # copy because it it destroyed in setting up query
    cleaned_data = copy.copy(org_cleaned_data)
    # do not use this in query, use in paginator
    page = cleaned_data.pop('page', None) or 1
    limit = cleaned_data.pop('limit', None) or botsglobal.ini.getint('settings', 'limit', 30)
    kwargs.get('context', {})['admlink'] = cleaned_data.pop('admlink', False)
    if cleaned_data.get('sortedby'):
        # pylint: disable=consider-using-f-string
        query = query.order_by('%s%s' % (
            '' if cleaned_data.pop('sortedasc', False) else '-', cleaned_data.pop('sortedby')))
    if cleaned_data.pop('lastrun', None):
        idtalastrun = getidtalastrun()
        if idtalastrun:
            # no result (=None): there are no filereports.
            if kwargs.get('incoming'):
                # incoming detected: do other selection
                query = query.filter(reportidta=idtalastrun)
            else:
                query = query.filter(idta__gt=idtalastrun)
    for key, value in list(cleaned_data.items()):
        if not value and value != 0:
            del cleaned_data[key]
            continue
        if key == 'datefrom':
            query = query.filter(ts__gte=cleaned_data.pop(key))
            continue
        if key == 'dateuntil':
            query = query.filter(ts__lt=cleaned_data.pop(key))
            continue
        if key in [
                'acceptance', 'status', 'statust',
                'idta', 'reportidta', 'retransmit', 'confirmidta']:
            if value < 0:
                # Negative int value is for query.exclude()
                query = query.exclude(**{key: -cleaned_data.pop(key)})
            continue
        if key in ['refresh', 'selection', 'selection_name', 'popup', 'sortedasc', 'allstatus']:
            cleaned_data.pop(key, None)
            continue
        if key in ['frompartner', 'topartner']:
            query = filterpartnerinquery(query, cleaned_data.pop(key), key)
            continue
        if key.startswith('rsrv') or key in [
                'infilename', 'outfilename', 'filename', 'divtext',
                'reference', 'errortext', 'contenttype', 'testindicator']:
            query = filterquery_contains(query, cleaned_data, key)
            continue
        if value.startswith('-'):
            query = query.exclude(**{key: cleaned_data.pop(key).lstrip('-')})

    query = query.filter(**cleaned_data)
    if kwargs.get('paginate', True):
        paginator = Paginator(query, limit)
        try:
            return paginator.page(page)
        except (EmptyPage, InvalidPage):
            # page does not exist: use last page
            lastpage = paginator.num_pages
            # change value in form as well
            org_cleaned_data['page'] = lastpage
            return paginator.page(lastpage)
    # do not use paginator; return everything
    return query


def filterpartnerinquery(query, idpartner, partnerfield):
    """
    return the appropriate query according to partner type
    if group: select partners in the group
    else: select the partner
    """
    qfilter = query.filter
    if idpartner.startswith('-'):
        idpartner = idpartner.lstrip('-')
        qfilter = query.exclude
    isgroup = models.partner.objects.values_list('isgroup', flat=True).filter(idpartner=idpartner)
    if isgroup[0]:
        return qfilter(**{f"{partnerfield}__in": models.partner.objects.values_list(
            'idpartner', flat=True).filter(group=idpartner)})
    return qfilter(**{partnerfield: idpartner})


def indent_x12(content, **kwargs):
    """
    Format x12 str content for display.
    """
    # pylint: disable=unused-argument
    if content.count('\n') > 6:
        return content
    count = 0
    for char in content[:200].lstrip():
        if char in '\r\n' and count != 105:  # pos 105: is record_sep, could be \r\n
            continue
        count += 1
        if count == 106:
            sep = char
            break
    else:
        return content
    if sep.isalnum() or sep.isspace():
        return content
    return content.replace(sep, sep + '\n')


EDIFACT_INDENT = re.compile(
    r"(?<!\?)"     # if no preceding escape (?)
    "'"            # apostrophe
    "(?![\n\r])",  # if no following CR of LF
    re.VERBOSE,
)


def indent_edifact(content, **kwargs):
    """
    three options:
    1 is already indented (each segment on separate line)
    2 block mode: lines of fixed lengths eg 80 chars
    3 one string, one line
    """
    # pylint: disable=unused-argument
    if content.count('\n') > 4:
        return content
    return EDIFACT_INDENT.sub("'\n", content)


def indent_json(content, **kwargs):
    """Return json in nice indented format.
    Unfortunately, sequencing is not preserved though :-(

    :param content: str: json string
    :param indent: int: number of space char for json indentation (default=2)

    :return: str: indented json
    """
    parsed = json.loads(content)
    return json.dumps(
        parsed,
        indent=int(kwargs.get("indent", 2)),
        sort_keys=False,
        separators=(",", ": "),
    )


indent_jsonnocheck = indent_json


def indent_xml(content, **kwargs):
    """Indent xml str content.

    :param content: str: xml string

    :param filename: str: Path of a xml file (overide content)
    :param indent: str: intentation char(s) (default="    ")
    :param encoding: str: encoding of xml content (default="utf-8")

    :return: Tuple(str, str): indented xml, encoding
    """
    # pylint: disable=c-extension-no-member
    doc = etree.parse(
        kwargs.get("filename") or BytesIO(content.encode(encoding=kwargs.get("encoding", "utf-8")))
    )
    etree.indent(doc, space=kwargs.get('indent', ' ' * 4))
    encoding = doc.docinfo.encoding
    # botsglobal.logger.debug("xml document encoding: %s", encoding)
    return etree.tostring(
        doc,
        pretty_print=True,
        method=kwargs.get('method', 'xml'),
        encoding=encoding,
        # with_comments=kwargs.get("with_comments", True),
    ).decode(), encoding.lower()


indent_xmlnocheck = indent_xml
