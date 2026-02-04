"""
Functions for reading and writing bots plugins.
"""
# pylint: disable=too-many-lines, consider-using-f-string

from datetime import date, datetime
import hashlib
import json
import os
import shutil
import sys
import time
import zipfile
import zipimport

import django
from django.contrib import messages
from django.core import serializers
from django.db import connection, transaction
from django.db.models import Min

from . import botsglobal
from . import botslib
from . import models
from .botsinit import LOG_LEVELS
from .botslib import gettext as _
from .exceptions import PluginError, txtexc


# ******************************************
# * read a plugin **************************
# ******************************************
# See: https://docs.djangoproject.com/en/dev/topics/db/transactions/#managing-transactions
# if no exception raised: commit, else rollback.
@django.db.transaction.non_atomic_requests
def read_index(filename: str = "") -> dict[str, list]:
    """process index file in default location.
    :param filename: str: default=""
    :return report: dict
    """
    plugreport = {"info": [], "warning": []}
    try:
        if not filename:
            filename = os.path.join(botsglobal.ini.get("directories", "usersysabs"), "index.json")
            if not os.path.isfile(filename):
                filename = os.path.join(botsglobal.ini.get("directories", "usersysabs"), "index.py")
        elif not filename.startswith(os.sep):
            filename = botslib.join(botsglobal.ini.get("directories", "usersysabs"), filename)
        plugreport["index"] = filename
        if os.path.isfile(filename):
            # index.json
            if filename.endswith(".json"):
                with open(filename, "rb") as jsonfile:
                    importedbotsindex = json.load(jsonfile)
                pluglist = listplugsinplugins(importedbotsindex["plugins"], plugreport)
            # index.py
            # Importing python bots index will be removed
            elif filename.endswith(".py") and filename.startswith(botsglobal.ini.get("directories", "usersysabs")):
                index_module = os.path.basename(filename).split(".py")[0]
                importedbotsindex, _scriptname = botslib.botsimport(index_module)
                pluglist = importedbotsindex.plugins[:]
                if importedbotsindex.__name__ in sys.modules:
                    del sys.modules[importedbotsindex.__name__]
                warn = _(
                    "Bots index python import is deprecated and will be removed in python 3.15.\n"
                    "Make a new bots index to save it to json format.")
                plugreport["warning"].append(warn)
                botsglobal.logger.warning(warn)
            else:
                raise PluginError(f"Invalid bots index {filename}")
        else:
            plugreport["warning"].append(_("No bots index found"))
            return plugreport

    except Exception as exc:
        txt = txtexc()
        raise PluginError(
            _('Error in configuration index file. Nothing is written. Error:\n%(txt)s'),
            {'txt': txt},
        ) from exc
    botsglobal.logger.info(_('Configuration index file is OK.'))
    botsglobal.logger.info(_('Start writing to database.'))

    if not pluglist:
        warn = _("No plugin found in index.")
        botsglobal.logger.warning(warn)
        plugreport["warning"].append(warn)
        return plugreport

    # write content of index file to the bots database
    try:
        read_index2database(pluglist)
    except Exception as exc:
        txt = txtexc()
        raise PluginError(
            _('Error writing configuration index to database. Nothing is written. Error:\n%(txt)s'),
            {'txt': txt},
        ) from exc
    botsglobal.logger.info(_("Writing index to database is OK."))
    plugreport["info"].append(_("Configuration index file is read successful."))
    return plugreport


def listplugsinplugins(plugins: dict, plugreport: dict = None) -> list[dict]:
    """List all plugs in plugins dict"""
    pluglist = []
    for plugintype in plugins.keys():
        if plugintype not in PLUGINCOMPARELIST:
            warn = _("Invalid plugin type found: %s")
            botsglobal.logger.warning(warn, plugintype)
            if plugreport:
                plugreport["warning"].append(warn % plugintype)
            continue
        pluglist += plugins[plugintype]
    return pluglist


# if no exception raised: commit, else rollback.
@django.db.transaction.non_atomic_requests
def read_plugin(pathzipfile: str) -> dict[str, list]:
    """
    Import a bots (uploaded) plugin.
    """
    # pylint: disable=too-many-locals,too-many-branches,too-many-statements

    # test if valid zipfile
    if not zipfile.is_zipfile(pathzipfile):
        raise PluginError(_("Plugin is not a valid zip file."))

    # to report in GUI files have been overwritten, skipped, ...
    plugreport = {"warning": []}
    try:
        myzipimport = zipimport.zipimporter(pathzipfile)
        # read index file
        try:
            # botsindex.json
            importedbotsindex = json.loads(myzipimport.get_data("botsindex.json"))
            plugreport["bots_version"] = plugin_version = str(importedbotsindex["bots_version"])
            pluglist = listplugsinplugins(importedbotsindex["plugins"], plugreport)
        except OSError:
            # botsindex.py
            # Importing python bots index will be removed
            # pylint: disable=deprecated-method  # zipimport.load_module() will be removed in python 3.15
            importedbotsindex = myzipimport.load_module("botsindex")
            plugreport["bots_version"] = plugin_version = str(getattr(importedbotsindex, "version", 0))
            pluglist = importedbotsindex.plugins[:]
            if "botsindex" in sys.modules:
                del sys.modules["botsindex"]

            warn = _(
                "Bots plugin with python botsindex is deprecated and will be removed in python 3.15.\n"
                "Make a new bots plugin to save it with a botsindex in json format.")
            plugreport["warning"].append(warn)
            botsglobal.logger.warning(warn)

        # Check plugin version compatibility
        if plugin_version < "3.4":
            warn = _(
                "Bots plugin target an older version of Bots: '%s'\n"
                "Please check if the code is Python 3 compatible."
            ) % plugin_version
            botsglobal.logger.warning(warn)
            plugreport["warning"].append(warn)

    except Exception as exc:
        if isinstance(exc, zipimport.ZipImportError):
            txt = str(exc)
        else:
            txt = txtexc()
        raise PluginError(
            _('Error in plugin. Nothing is written. Error:\n%(txt)s'), {'txt': txt}
        ) from exc

    if not plugreport.get("warning"):
        botsglobal.logger.info(_('Plugin %s is OK.'), pathzipfile)
    botsglobal.logger.info(_('Start writing to database.'))

    # write content of index file to the bots database
    try:
        read_index2database(pluglist)
    except Exception as exc:
        txt = txtexc()
        raise PluginError(
            _('Error writing plugin to database. Nothing is written. Error:\n%(txt)s'), {'txt': txt}
        ) from exc

    botsglobal.logger.info(_('Writing to database is OK.'))

    # write files to the file system.
    botsglobal.logger.info(_('Start writing to files'))
    try:
        orgtargetpath = botsglobal.ini.get("directories", "botsenv")
        if orgtargetpath[-1:] in (os.path.sep, os.path.altsep) and len(os.path.splitdrive(orgtargetpath)[1]) > 1:
            orgtargetpath = orgtargetpath[:-1]
        with zipfile.ZipFile(pathzipfile, mode="r") as myzip:
            plugreport.update({"installed": [], "overwritten": [], "skipped": []})
            for zipfileobject in myzip.infolist():
                # botsglobal.logger.debug('Filename in zip "%s".', zipfileobject.filename)
                if zipfileobject.filename.endswith("/") or zipfileobject.filename in [
                        "botsindex.json",
                        "botsindex.py",
                        "README.md",
                        "botssys/sqlitedb/botsdb",
                        "config/bots.ini",
                        ]:
                    # Skip dir and root files
                    continue
                targetpath = zipfileobject.filename[1:] if zipfileobject.filename[0] == "/" else zipfileobject.filename
                if targetpath.startswith("usersys/"):
                    if not targetpath.endswith((".py", ".html", "/index.json")):
                        plugreport["skipped"].append(zipfileobject.filename)
                        botsglobal.logger.warning(_("Skipping file: %s"), zipfileobject.filename)
                        continue
                    if targetpath.rsplit("/", maxsplit=1)[-1].startswith("__init__."):
                        plugreport["skipped"].append(zipfileobject.filename)
                        botsglobal.logger.warning(_("__init__ file detected: %s ... skipping"), zipfileobject.filename)
                        continue
                    # convert for correct environment: repacle botssys, config, usersys in filenames
                    targetpath = targetpath.replace(
                        "usersys", botsglobal.ini.get("directories", "usersysabs"), 1
                    )
                elif targetpath.startswith("botssys/"):
                    targetpath = targetpath.replace(
                        "botssys", botsglobal.ini.get("directories", "botssys"), 1
                    )
                else:
                    botsglobal.logger.warning(_("Skipping invalid plugin file: %s"), zipfileobject.filename)
                    plugreport["skipped"].append(zipfileobject.filename)
                    continue
                # format targetpath with botsenv path
                targetpath = botslib.join(orgtargetpath, targetpath)
                botsglobal.logger.info(
                    _('    Start writing file: "%(targetpath)s".'), {"targetpath": targetpath}
                )
                if botslib.dirshouldbethere(os.path.dirname(targetpath)):
                    botsglobal.logger.info(
                        _('        Created directory "%(directory)s".'),
                        {"directory": os.path.dirname(targetpath)},
                    )
                # check if file already exists
                if os.path.isfile(targetpath):
                    botsglobal.logger.warning(_("Overwritten file: %s"), targetpath)
                    plugreport["overwritten"].append(targetpath)
                source = myzip.read(zipfileobject.filename)
                with open(targetpath, "wb") as target:
                    target.write(source)
                botsglobal.logger.log(
                    LOG_LEVELS["DONE"],
                    _('        File written: "%(targetpath)s".'), {"targetpath": targetpath}
                )
                plugreport["installed"].append(targetpath)
    except Exception as exc:
        txt = txtexc()
        raise PluginError(
            _('Error writing files to system. Nothing is written to database. Error:\n%(txt)s'),
            {'txt': txt},
        ) from exc

    botsglobal.logger.info(_('Writing files to filesystem is OK.'))
    return plugreport


# PLUGINCOMPARELIST: for filtering and sorting the plugins.
PLUGINCOMPARELIST = [
    'uniek',
    'persist',
    'mutex',
    'ta',
    'filereport',
    'report',
    'ccodetrigger',
    'ccode',
    'channel',
    'partner',
    'chanpar',
    'translate',
    'routes',
    'confirmrule',
]


def read_index2database(orgpluglist: list):
    """sanity checks on pluglist"""
    # pylint: disable=too-many-locals, too-many-branches, too-many-statements
    if not orgpluglist:
        # list of plugins is empty: is OK. DO nothing
        return
    if not isinstance(orgpluglist, list):
        # has to be a list!!
        raise PluginError(_("Plugins should be list of dicts. Nothing is written."))
    for plug in orgpluglist:
        if not isinstance(plug, dict):
            raise PluginError(_("Plugins should be list of dicts. Nothing is written."))
        for key in plug.keys():
            if not isinstance(key, str):
                raise PluginError(
                    _('Key of dict is not a string: "%(plug)s". Nothing is written.'),
                    {'plug': plug},
                )
        if 'plugintype' not in plug:
            raise PluginError(
                _('"Plugintype" missing in: "%(plug)s". Nothing is written.'), {'plug': plug}
            )

    # special case: compatibility with bots 1.* plugins.
    # in bots 1.*, partnergroup was in separate tabel; in bots 2.* partnergroup is in partner
    # later on, partnergroup will get filtered
    for plug in orgpluglist[:]:
        if plug['plugintype'] == 'partnergroup':
            for plugpartner in orgpluglist:
                if plugpartner["plugintype"] == "partner" and plugpartner["idpartner"] == plug["idpartner"]:
                    if 'group' in plugpartner:
                        plugpartner['group'].append(plug['idpartnergroup'])
                    else:
                        plugpartner['group'] = [plug['idpartnergroup']]
                    break

    # copy & filter orgpluglist; do plugtype specific adaptions
    pluglist = []
    for plug in orgpluglist:
        if plug['plugintype'] == 'ccode':
            # add ccodetrigger. #20101223: this is NOT needed; codetrigger shoudl be in plugin.
            for seachccodetriggerplug in pluglist:
                if (
                    seachccodetriggerplug["plugintype"] == "ccodetrigger" and
                    seachccodetriggerplug["ccodeid"] == plug["ccodeid"]
                ):
                    break
            else:
                pluglist.append({'plugintype': 'ccodetrigger', 'ccodeid': plug['ccodeid']})
        elif plug['plugintype'] == 'translate':
            # make some fields None instead of '' (translate formpartner, topartner)
            if not plug['frompartner']:
                plug['frompartner'] = None
            if not plug['topartner']:
                plug['topartner'] = None
        elif plug['plugintype'] == 'routes':
            plug['active'] = False
            if 'defer' not in plug:
                plug['defer'] = False
            else:
                if plug['defer'] is None:
                    plug['defer'] = False
        elif plug['plugintype'] == 'channel':
            # convert for correct environment: path and mpath in channels
            if 'path' in plug and plug['path'].startswith('botssys'):
                plug['path'] = plug['path'].replace(
                    'botssys', botsglobal.ini.get('directories', 'botssys_org'), 1
                )
            if 'testpath' in plug and plug['testpath'].startswith('botssys'):
                plug['testpath'] = plug['testpath'].replace(
                    'botssys', botsglobal.ini.get('directories', 'botssys_org'), 1
                )
        elif plug['plugintype'] == 'confirmrule':
            # id is an artificial key, delete,
            plug.pop('id', None)
        elif plug['plugintype'] not in PLUGINCOMPARELIST:
            # not in PLUGINCOMPARELIST: do not use
            continue
        pluglist.append(plug)
    # sort pluglist: this is needed for relationships
    # sort partners on being partnergroup or not
    pluglist.sort(key=lambda plug: plug.get('isgroup', False), reverse=True)
    # sort all plugs on plugintype; are partners/partenrgroups are already sorted,
    # this will still be true in this new sort (python guarantees!)
    pluglist.sort(key=lambda plug: PLUGINCOMPARELIST.index(plug['plugintype']))

    for plug in pluglist:
        botsglobal.logger.info('    Start write to database for: "%(plug)s".', {'plug': plug})
        # correction for reading partnergroups
        if plug['plugintype'] == 'partner' and plug['isgroup']:
            plug['plugintype'] = 'partnergroep'
        # remember the plugintype
        plugintype = plug['plugintype']

        table = django.apps.apps.get_model('bots', plugintype)

        # delete fields not in model for compatibility; note that 'plugintype' is also removed.
        # pylint: disable=protected-access
        for key in list(plug.keys()):
            try:
                table._meta.get_field(key)
            except django.core.exceptions.FieldDoesNotExist:
                del plug[key]

        # get key(s), put in dict 'sleutel'
        pk = table._meta.pk.name
        if pk == 'id':
            # 'id' is the artificial key django makes, if no key is indicated.
            # Note the django has no 'composite keys'.
            sleutel = {}
            if table._meta.unique_together:
                for key in table._meta.unique_together[0]:
                    sleutel[key] = plug.pop(key)
        else:
            sleutel = {pk: plug.pop(pk)}

        sleutelorg = sleutel.copy()  # make a copy of the original sleutel; this is needed later
        # now we have:
        # - plugintype (is removed from plug)
        # - sleutelorg: original key fields
        # - sleutel: unique key fields. mind: translate and confirmrule have empty 'sleutel'
        # - plug: rest of database fields
        # for sleutel and plug: convert names to real database names

        # get real column names for fields in plug
        for fieldname in list(plug.keys()):
            fieldobject = table._meta.get_field(fieldname)
            try:
                if fieldobject.column != fieldname:
                    # if name in plug is not the real field name (in database)
                    plug[fieldobject.column] = plug[fieldname]  # add new key in plug
                    del plug[fieldname]  # delete old key in plug
            except Exception as exc:
                raise PluginError(
                    _('No field column for: "%(fieldname)s".'), {'fieldname': fieldname}
                ) from exc
        # get real column names for fields in sleutel; basically the same loop but now for sleutel
        for fieldname in list(sleutel.keys()):
            fieldobject = table._meta.get_field(fieldname)
            try:
                if fieldobject.column != fieldname:
                    sleutel[fieldobject.column] = sleutel[fieldname]
                    del sleutel[fieldname]
            except Exception as exc:
                raise PluginError(
                    _('No field column for: "%(fieldname)s".'), {'fieldname': fieldname}
                ) from exc

        # find existing entry (if exists)
        listexistingentries = None
        if sleutelorg:
            # note that translate and confirmrule have an empty 'sleutel'
            listexistingentries = table.objects.filter(**sleutelorg)
        elif plugintype == 'translate':
            listexistingentries = table.objects.filter(
                fromeditype=plug['fromeditype'],
                frommessagetype=plug['frommessagetype'],
                alt=plug['alt'],
                frompartner=plug['frompartner_id'],
                topartner=plug['topartner_id'],
            )
        elif plugintype == 'confirmrule':
            listexistingentries = table.objects.filter(
                confirmtype=plug['confirmtype'],
                ruletype=plug['ruletype'],
                negativerule=plug['negativerule'],
                idroute=plug.get('idroute'),
                idchannel=plug.get('idchannel_id'),
                messagetype=plug.get('messagetype'),
                frompartner=plug.get('frompartner_id'),
                topartner=plug.get('topartner_id'),
            )
        if listexistingentries:
            # exists, so use existing db-object
            dbobject = listexistingentries[0]
        else:
            # create db-object
            dbobject = table(**sleutel)
            if plugintype == 'partner':
                # for partners, first the partner needs to be saved before groups can be made
                dbobject.save()
        for key, value in plug.items():
            # update object with attributes from plugin
            if isinstance(value, list):
                # for many2many fields
                obj = getattr(dbobject, key)
                obj.set(value)
            else:
                setattr(dbobject, key, value)
        # save the updated object.
        botsglobal.logger.debug('Saving Bots db obj: %s', dbobject)
        dbobject.save()
        botsglobal.logger.info(_('        Write to database is OK.'))


# *********************************************
# * plugout / make a plugin (generate) ********
# *********************************************
def make_index(filename: str = "", cleaned_data: dict = None) -> bool:
    """
    generate only the index file of the plugin.
    used eg for configuration change management.
    :param filename: str
    :param cleaned_data: dict: Customs params to make bots index.

    :return bool:
    """
    if not filename.endswith(".json"):
        raise PluginError(_("Bots index extension must be '.json'"))

    plugreport = {"info": [], "warning": []}
    botsglobal.logger.info(
        _('Start writing configuration index file "%(file)s".'), {"file": filename}
    )
    dummy_cleaned_data = {
        "databaseconfiguration": True,
        "umlists": botsglobal.ini.getboolean("settings", "codelists_in_plugin", True),
        "databasetransactions": False,
    }
    if not cleaned_data:
        cleaned_data = dummy_cleaned_data
    plugs = all_database2plug(cleaned_data)
    # Generate index content
    indexstring = plugs2jsonstr(plugs)
    with open(filename, "w", encoding="utf-8") as filehandler:
        filehandler.write(indexstring)
    info = _("Bots index file written: %s")
    botsglobal.logger.info(info, filename)
    plugreport["info"].append(info % filename)
    return plugreport


def convertindex2json(infilename: str, outfilename: str) -> str:
    """
    Convert a python bots index to json bots index:
    index.py > index.json

    :param infilename: str: path to bots index.py
    :param outfilename: str: path converted bots index.json

    :return outfilename: if convertion success
    """
    # pylint: disable=import-outside-toplevel
    import random
    import string

    copied = None
    if not infilename.endswith(".py"):
        raise PluginError(_("Invalid input bots index: %s") % infilename)
    infilename = index_file = os.path.abspath(infilename)
    outfilename = os.path.abspath(outfilename)
    if not infilename.startswith(botsglobal.ini.get("directories", "usersysabs")):
        index_file = os.path.join(
            botsglobal.ini.get("directories", "usersysabs"),
            os.path.basename(infilename)[:-3] + "_to_json_" +
            "".join(random.choices(string.ascii_lowercase, k=12)) + ".py")
        copied = shutil.copy(infilename, index_file)
    index_module = index_file.split(
        botsglobal.ini.get("directories", "usersysabs") + os.sep)[-1][:-3].replace(os.sep, ".")
    importedbotsindex, _scriptname = botslib.botsimport(index_module)
    # Convert plugins list to dummy plugs list
    plugs = []
    for plugin in importedbotsindex.plugins:
        plugin[SortedFirstString("plugintype")] = plugin.pop("plugintype")
        plugs.append({"fields": plugin})
    # Generate index content
    indexstring = plugs2jsonstr(plugs)
    with open(outfilename, "w", encoding="utf-8") as outfile:
        outfile.write(indexstring)
    info = _("Bots index file converted: %s")
    botsglobal.logger.info(info, outfilename)
    if copied:
        os.remove(copied)
    if importedbotsindex.__name__ in sys.modules:
        del sys.modules[importedbotsindex.__name__]
    return outfilename


def make_plugin(cleaned_data: dict, zipfilename: str):
    """
    Write bots plugin zip file.

    :param cleaned_data: dict
    :param zipfilename: str:
    """
    plugs = all_database2plug(cleaned_data)
    plugin = plugs2dict(plugs)
    with zipfile.ZipFile(zipfilename, "w", zipfile.ZIP_DEFLATED) as pluginzipfilehandler:
        # Files
        files4plugin = plugout_files(cleaned_data)
        for filename, plugfilename in files4plugin:
            plugin.setdefault(SortedLastString("files"), {})
            with open(filename, "rb") as plugfile:
                plugin["files"][plugfilename] = {
                    "sha256": hashlib.sha256(plugfile.read()).hexdigest(),
                }
            pluginzipfilehandler.write(filename, plugfilename)
            botsglobal.logger.debug('    Write file "%(file)s".', {"file": plugfilename})
            botsglobal.logger.debug('    Filename: "%s"', filename)
        # write botsindex.json to pluginfile
        plugsasjsonstr = plugs2jsonstr(plugin)
        pluginzipfilehandler.writestr("botsindex.json", plugsasjsonstr.encode("utf-8"))
        botsglobal.logger.debug("    Write in index:\n %(index)s", {"index": plugsasjsonstr})


def file4plugout(filename: str, plugdir: str, files2return: list = None) -> list:
    """
    Append filename to files2return if not already in it.

    :param filename:
    :param plugdir:
    :param files2return:

    :return List[str, str] or None
    """
    file2add = []
    if files2return is None:
        files2return = []
    if os.path.isfile(filename):
        file2add = [filename, os.path.join(plugdir, os.path.basename(filename))]
        if file2add not in files2return:
            files2return.append(file2add)
    return file2add


def get_imported_files(pyfile):
    """return list of local python files imported in a python file."""
    # pylint: disable=consider-using-with, too-many-branches
    imported_files = []
    modules = []
    multi_lines = False
    parent_import = False
    for line in open(pyfile, "r", encoding="utf8"):
        if line.lstrip(' ').startswith('#'):
            continue
        if 'from .. import ' in line:
            imports = line.split('from .. import ')[1].strip('\n').strip('\r')
            if "(" in imports and ")" not in imports:
                multi_lines = parent_import = True
            for module in imports.strip('(').strip(')').strip(' ').split(','):
                if module:
                    modules.append('..%s' % module)
        elif 'from ..' in line:
            modules.append('..%s' % line.split('from ..')[1].split(' ')[0].split('.')[0])
        elif 'from . import ' in line:
            imports = line.split('from . import ')[1].strip('\n').strip('\r')
            if "(" in imports and ")" not in imports:
                multi_lines = True
            for module in imports.strip('(').strip(')').strip(' ').split(','):
                if module:
                    modules.append(module)
        elif 'from .' in line:
            modules.append(line.split('from .')[1].split(' ')[0].split('.')[0])
        elif multi_lines:
            for module in line.strip(')').strip(' ').split(','):
                if module:
                    if parent_import:
                        module = '..%s' % module
                    modules.append(module)
            if ')' in line:
                multi_lines = parent_import = False

    currentdir = os.path.dirname(pyfile)
    for module in modules:
        moduledir = currentdir
        if module.startswith('..'):
            moduledir = os.path.dirname(moduledir)
            module = module[2:]
        modulefile = os.path.join(moduledir, '%s.py' % module)
        if os.path.isfile(modulefile):
            imported_files.append(modulefile)
            imported_files.extend(get_imported_files(modulefile))

    return imported_files


def add_translate_grammarsfiles(translate, files2return=None):
    """Return list of grammars files"""
    if files2return is None:
        files2return = []
    usersys = botsglobal.ini.get('directories', 'usersysabs')
    # Grammar files
    if translate.fromeditype not in ['edifact', 'x12']:
        # Find incoming grammar file
        grammarin = os.path.join(
            usersys, 'grammars', translate.fromeditype,
            '%s.py' % translate.frommessagetype)
        if os.path.isfile(grammarin):
            plugdir = 'usersys/grammars/%s' % translate.fromeditype
            file4plugout(grammarin, plugdir, files2return)
            for filename in get_imported_files(grammarin):
                file4plugout(filename, plugdir, files2return)

    if translate.toeditype not in ['edifact', 'x12']:
        # Find outgoing grammar file
        grammarout = os.path.join(
            usersys, 'grammars', translate.toeditype,
            '%s.py' % translate.tomessagetype)
        if os.path.isfile(grammarout):
            plugdir = 'usersys/grammars/%s' % translate.toeditype
            file4plugout(grammarout, plugdir, files2return)
            for filename in get_imported_files(grammarout):
                file4plugout(filename, plugdir, files2return)

    return files2return


def all_database2plug(cleaned_data):
    """get all database objects, serialize these (to dict), adapt."""
    # pylint: disable=too-many-locals, too-many-branches, too-many-statements
    plugs = []
    channels = []
    partners = []
    translates = []
    files2return = cleaned_data.setdefault('files2return', [])
    usersys = botsglobal.ini.get('directories', 'usersysabs')

    def find_alt_translation(translate):
        """Search chained and alt translation in mapping script."""
        tscript = os.path.join(
            usersys,
            'mappings', translate.fromeditype, '%s.py' % translate.tscript)
        if not os.path.isfile(tscript):
            return
        # Find alternative translation with 'out_as_inn' and 'alt' return in mapping script
        # pylint: disable=consider-using-with
        in_main = False
        for line in open(tscript, "r", encoding="utf8"):
            if line.lstrip(' ').startswith('#'):
                continue
            if line.startswith('def main('):
                in_main = True
                continue
            if line.startswith('def ') or line.startswith('class '):
                in_main = False
                continue
            if not in_main:
                continue
            if 'return ' in line and line.lstrip().startswith('return '):
                alt = line.split('return ')[1].split('#')[0]
                if not alt:
                    continue
                alt = alt.replace('"', "'").strip()
                alttranslate = None
                if "'out_as_inn'" in alt and "'alt'" in alt:
                    # {'type': 'out_as_inn', 'alt': 'my_next_translation'}
                    alt = alt.split("'alt'")[1].lstrip(" :'").split("'")[0]
                    alttranslate = models.translate.objects.filter(
                        fromeditype=translate.toeditype,
                        frommessagetype=translate.tomessagetype,
                        alt=alt).first() if alt else None
                elif alt.startswith("'"):
                    alt = alt.strip("'").strip()
                    alttranslate = models.translate.objects.filter(
                        fromeditype=translate.fromeditype,
                        frommessagetype=translate.frommessagetype,
                        alt=alt).first() if alt else None
                if alttranslate and alttranslate.pk not in translates:
                    add_translate(alttranslate)

    def add_translate(translate):
        if translate.frompartner_id and translate.frompartner_id not in partners:
            partners.append(translate.frompartner_id)
        if translate.topartner_id and translate.topartner_id not in partners:
            partners.append(translate.topartner_id)
        if translate.pk not in translates:
            translates.append(translate.pk)
            if not cleaned_data.get('nogrammar'):
                # Add grammars files
                add_translate_grammarsfiles(translate, files2return)
            if not cleaned_data.get('grammaronly'):
                # Find mapping script
                tscript = os.path.join(
                    usersys,
                    'mappings', translate.fromeditype, '%s.py' % translate.tscript)
                if os.path.isfile(tscript):
                    plugdir = 'usersys/mappings/%s' % translate.fromeditype
                    # Add local import files
                    for filename in get_imported_files(tscript):
                        file4plugout(filename, plugdir, files2return)
                    # Add mapping script file
                    file4plugout(tscript, plugdir, files2return)
                    find_alt_translation(translate)

    def add_translates(translateq):
        for translate in translateq:
            add_translate(translate)

    def add_channel(channel):
        # Channels
        if channel and channel.pk not in channels:
            channels.append(channel.pk)
            # Add fromchannel script
            file4plugout(channel.communicationscript, 'usersys/communicationscripts', files2return)

    def add_channels(queryset):
        for channel in queryset:
            add_channel(channel)

    # pylint: disable=protected-access
    if cleaned_data.get('queryset'):
        queryset = cleaned_data['queryset']

        if queryset.first()._meta.model == models.channel:
            add_channels(queryset)

        elif queryset.first()._meta.model == models.translate:
            add_translates(queryset)
            if cleaned_data.get('grammaronly'):
                translates = []

        elif queryset.first()._meta.model == models.ccode:
            ccodeids = []
            for ccode in queryset:
                if ccode.ccodeid_id not in ccodeids:
                    ccodeids.append(ccode.ccodeid_id)
            # Add ccode type
            plugs += queryset2plug(models.ccodetrigger.objects.filter(pk__in=ccodeids))
            # Add ccodes
            plugs += queryset2plug(queryset)

        elif queryset.first()._meta.model == models.ccodetrigger:
            plugs += queryset2plug(queryset)
            for ccodeid in queryset:
                # Add ccodes
                plugs += queryset2plug(models.ccode.objects.filter(ccodeid=ccodeid))

        elif queryset.first()._meta.model == models.routes:
            plugs += queryset2plug(queryset)
            for route in queryset:
                # Route script
                routescript = os.path.join(usersys, "routescripts", f"{route.idroute}.py")
                file4plugout(routescript, 'usersys/routescripts', files2return)

                # Channels
                add_channel(route.fromchannel)
                add_channel(route.tochannel)

                # Partners
                for attr in [
                        'frompartner', 'topartner',
                        'frompartner_tochannel', 'topartner_tochannel']:
                    partner = getattr(route, attr, None)
                    if partner and partner.pk not in partners:
                        partners.append(partner.pk)

                # Translates entry except for normalized edifact/x12
                if route.translateind == 1 and not cleaned_data.get('notranslate'):
                    translateq = models.translate.objects.filter(
                        fromeditype=route.fromeditype,
                        alt=route.alt,
                    )
                    if route.fromeditype not in ['edifact', 'x12']:
                        translateq = translateq.filter(frommessagetype=route.frommessagetype)
                    elif len(translateq) > 1:
                        continue
                    add_translates(translateq)
        else:
            plugs += queryset2plug(queryset)

        if channels:
            plugs += queryset2plug(models.channel.objects.filter(pk__in=channels))
        if translates:
            plugs += queryset2plug(models.translate.objects.filter(pk__in=translates))
        if partners:
            plugs += queryset2plug(models.partner.objects.filter(pk__in=partners))
            # Add usersys/partners/*/idpartner.py
            partners_dir = os.path.join(usersys, 'partners')
            for pscript in plugout_files_bydir(partners_dir, 'usersys/partners'):
                for idpartner in partners:
                    if pscript[0].endswith(f"{idpartner}.py"):
                        files2return.append(pscript)

    if cleaned_data.get('databaseconfiguration'):
        plugs += (
            database2plug(models.channel)
            + database2plug(models.partner)
            + database2plug(models.chanpar)
            + database2plug(models.translate)
            + database2plug(models.routes)
            + database2plug(models.confirmrule)
        )
    if cleaned_data.get('umlists'):
        plugs += database2plug(models.ccodetrigger) + database2plug(models.ccode)
    if cleaned_data.get('databasetransactions'):
        # list(models.persist.objects.all()) + \  # should persist object alos be included?
        plugs += (
            database2plug(models.uniek)
            + database2plug(models.mutex)
            + database2plug(models.ta)
            + database2plug(models.filereport)
            + database2plug(models.report)
        )
    return plugs


class SortedFirstString(str):
    """Subclass of str for plugintype plugin field, to be sorted first
    for json sorting"""
    def __lt__(self, other):
        return True


class SortedLastString(str):
    """Subclass of str for plugintype plugin field, to be sorted last"""
    def __lt__(self, other):
        return False


def queryset2plug(queryset):
    """serialize django queryset"""
    # pylint: disable=protected-access
    plugs = serializers.serialize('python', queryset)
    if plugs:
        app, tablename = plugs[0]['model'].split('.', 1)
        table = django.apps.apps.get_model(app, tablename)
        pk = table._meta.pk.name
        # adapt plugs
        for plug in plugs:
            plug["fields"][SortedFirstString("plugintype")] = tablename
            if pk != 'id':
                plug['fields'][pk] = plug['pk']
            # convert for correct environment: replace botssys in channels[path, mpath]
            if tablename == 'channel':
                if 'path' in plug['fields'] and plug['fields']['path'].startswith(
                        botsglobal.ini.get('directories', 'botssys_org')):
                    plug['fields']['path'] = plug['fields']['path'].replace(
                        botsglobal.ini.get('directories', 'botssys_org'), 'botssys', 1
                    )
                if 'testpath' in plug['fields'] and plug['fields']['testpath'].startswith(
                        botsglobal.ini.get('directories', 'botssys_org')):
                    plug['fields']['testpath'] = plug['fields']['testpath'].replace(
                        botsglobal.ini.get('directories', 'botssys_org'), 'botssys', 1
                    )
    return plugs


def database2plug(db_table):
    """serialize database objects"""
    return queryset2plug(db_table.objects.all())


def plugs2dict(plugs: list) -> dict:
    """Make bots plugin dict"""
    plugin = {
        SortedFirstString("bots_version"): botsglobal.version,
        "plugins": {},
    }
    for plug in plugs:
        plugintype = plug["fields"].get("plugintype")
        plugin["plugins"].setdefault(plugintype, [])
        plugin["plugins"][plugintype].append(plug["fields"])
    return plugin


def plugin_serializer(obj):
    """
    Convert datetime/date to iso format string
    """
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def plugs2jsonstr(plugs: dict | list) -> str:
    """Make botsindex.json str

    :param plugs: dict | list: Plugin dict or plugs list

    :return json string
    """
    if isinstance(plugs, list):
        plugs = plugs2dict(plugs)
    if not isinstance(plugs, dict):
        raise PluginError("Invalid plugs, must be dict or list")
    return json.dumps(
        plugs,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        default=plugin_serializer,
    )


def plugout_files(cleaned_data):
    """gather list of files for the plugin that is generated."""
    files2return = cleaned_data.setdefault('files2return', [])
    usersys = str(botsglobal.ini.get("directories", "usersysabs"))
    botssys = str(botsglobal.ini.get("directories", "botssys"))
    if cleaned_data.get('fileconfiguration'):
        # gather from usersys
        files2return.extend(plugout_files_bydir(usersys, 'usersys'))
        if not cleaned_data.get('charset'):
            # if edifact charsets are not needed: remove them (are included in default bots installation).
            charsetdirs = plugout_files_bydir(
                os.path.join(usersys, 'charsets'),
                os.path.join('usersys', 'charsets'))
            for charset in charsetdirs:
                try:
                    index = files2return.index(charset)
                    files2return.pop(index)
                except ValueError:
                    pass
    else:
        if cleaned_data.get('charset'):
            # if edifact charsets are not needed:
            # remove them (are included in default bots installation).
            files2return.extend(
                plugout_files_bydir(os.path.join(usersys, 'charsets'), 'usersys/charsets')
            )
    if cleaned_data.get('config'):
        config = botsglobal.ini.get('directories', 'config')
        files2return.extend(plugout_files_bydir(config, 'config'))
    if cleaned_data.get('data'):
        data = botsglobal.ini.get('directories', 'data')
        files2return.extend(plugout_files_bydir(data, 'botssys/data'))
    if cleaned_data.get('database'):
        files2return.extend(
            plugout_files_bydir(os.path.join(botssys, 'sqlitedb'), 'botssys/sqlitedb.copy')
        )  # yeah...reading a plugin with a new database will cause a crash...do this manually...
    if cleaned_data.get('infiles'):
        files2return.extend(plugout_files_bydir(os.path.join(botssys, 'infile'), 'botssys/infile'))
    if cleaned_data.get('logfiles'):
        log_file = botsglobal.ini.get('directories', 'logging')
        files2return.extend(plugout_files_bydir(log_file, 'botssys/logging'))
    return files2return


def plugout_files_bydir(dirname, defaultdirname):
    """gather all files from directory dirname"""
    files2return = []
    for root, _dirs, files in os.walk(dirname):
        # convert for correct environment: replace dirname with the default directory name
        rootinplugin = root.replace(dirname, defaultdirname, 1)
        for bestand in files:
            ext = os.path.splitext(bestand)[1]
            if ext and (ext in ['.pyc', '.pyo'] or bestand in ['__init__.py']):
                continue
            files2return.append([os.path.join(root, bestand), os.path.join(rootinplugin, bestand)])
    return files2return


def plugout_backup_core(request=None):
    """Make a backup plugin (database config, usersys/*, charset/*"""
    # pylint: disable=broad-exception-caught
    backup_dir = botslib.join(botsglobal.ini.get("directories", "botssys"), "backup")
    botslib.dirshouldbethere(backup_dir)
    filename = botslib.join(
        backup_dir,
        f"backup_plugin_{time.strftime('%Y%m%d%H%M%S')}.zip",
    )
    botsglobal.logger.info(_('Start writing backup plugin "%(file)s".'), {'file': filename})
    try:
        dummy_for_cleaned_data = {
            'databaseconfiguration': True,
            'umlists': botsglobal.ini.getboolean('settings', 'codelists_in_plugin', True),
            'fileconfiguration': True,
            'infiles': False,
            'charset': True,
            'databasetransactions': False,
            'data': False,
            'logfiles': False,
            'config': False,
            'database': False,
        }
        make_plugin(dummy_for_cleaned_data, filename)
        notification = _('Backup plugin "%s" is written successful.') % filename
        botsglobal.logger.log(LOG_LEVELS['DONE'], notification)
        if request:
            messages.add_message(request, messages.INFO, notification)

    except Exception as exc:
        notification = _('Error writing backup plugin: "%s".') % str(exc)
        botsglobal.logger.error(notification)
        if request:
            messages.add_message(request, messages.ERROR, notification)


# ********************
# * Delete  **********
# ********************
def delete(**kwargs):
    """
    Delete bots user parts (database, usersys, botssys, ...)

    :param delconfiguration: boolean
    :param delcodelists: boolean
    :param deluserscripts: boolean
    :param deltransactions: boolean
    :param delacceptance: boolean
    :param delpersist: boolean
    :param delinfile: boolean
    :param deloutfile: boolean

    :param request: HttpRequest object
    """
    # pylint: disable=too-many-locals, too-many-branches, too-many-statements
    if not kwargs:
        botsglobal.logger.info(_('Nothing specified to delete.'))
        botsglobal.logger.info(delete.__doc__)
        return

    request = kwargs.get('request')

    if kwargs.get('delconfiguration') \
            or kwargs.get('delcodelists') \
            or kwargs.get('deluserscripts'):
        # write backup plugin first
        plugout_backup_core(request)

    botsglobal.logger.info(_('Start deleting in configuration.'))

    # deltransactions
    if kwargs.get('deltransactions'):
        # while testing with very big loads,
        # deleting gave error. Using raw SQL solved this.
        with transaction.atomic():
            cursor = connection.cursor()
            cursor.execute("""DELETE FROM ta""")
            cursor.execute("""DELETE FROM filereport""")
            cursor.execute("""DELETE FROM report""")

        notification = _('Transactions are deleted.')
        botsglobal.logger.log(LOG_LEVELS['DONE'], notification)
        if request:
            messages.add_message(request, messages.INFO, notification)

        # clean engine logs
        if botsglobal.ini.get('settings', 'log_file_number', None) == 'idta':
            logdir = botslib.join(botsglobal.ini.get('directories', 'logging'), 'engine')
            if os.access(logdir, os.W_OK):
                shutil.rmtree(logdir, ignore_errors=True)

        # clean botssys/data files
        deletefrompath = botsglobal.ini.get('directories', 'data', 'botssys/data')
        shutil.rmtree(deletefrompath, ignore_errors=True)
        botslib.dirshouldbethere(deletefrompath)

        notification = _('Data files are deleted.')
        botsglobal.logger.log(LOG_LEVELS['DONE'], notification)
        if request:
            messages.add_message(request, messages.INFO, notification)

    # delacceptance
    elif kwargs.get('delacceptance'):
        # list of files for deletion in data-directory
        list_file = []
        report_idta_lowest = 0
        # for each acceptance report. is not very efficient.
        for acc_report in models.report.objects.filter(acceptance=1):
            if not report_idta_lowest:
                report_idta_lowest = acc_report.idta
            # select 'next' report...
            max_report_idta = models.report.objects.filter(
                idta__gt=acc_report.idta
            ).aggregate(Min('idta'))['idta__min']
            if not max_report_idta:
                # if report is report of last run, there is no next report
                max_report_idta = sys.maxsize
            # we have a idta-range now: from (and including) acc_report.idta
            # till (and excluding) max_report_idta
            list_file += (
                models.ta.objects.filter(
                    idta__gte=acc_report.idta, idta__lt=max_report_idta
                )
                .exclude(status=1)
                .values_list('filename', flat=True)
                .distinct()
            )
            # delete ta in range
            models.ta.objects.filter(
                idta__gte=acc_report.idta, idta__lt=max_report_idta
            ).delete()
            # delete filereports in range
            models.filereport.objects.filter(
                idta__gte=acc_report.idta, idta__lt=max_report_idta
            ).delete()

        if report_idta_lowest:
            # delete all acceptance reports
            models.report.objects.filter(
                idta__gte=report_idta_lowest, acceptance=1
            ).delete()
            # delete all files in data directory geenrated during acceptance testing
            for filename in list_file:
                if filename.isdigit():
                    botslib.deldata(filename)

        notification = _('Transactions from acceptance-testing deleted.')
        botsglobal.logger.log(LOG_LEVELS['DONE'], notification)
        if request:
            messages.add_message(request, messages.INFO, notification)

    # delconfiguration
    if kwargs.get('delconfiguration'):
        models.confirmrule.objects.all().delete()
        models.routes.objects.all().delete()
        models.channel.objects.all().delete()
        models.chanpar.objects.all().delete()
        models.translate.objects.all().delete()
        models.partner.objects.all().delete()

        notification = _('Database configuration is deleted.')
        botsglobal.logger.log(LOG_LEVELS['DONE'], notification)
        if request:
            messages.add_message(request, messages.INFO, notification)

    # delcodelists
    if kwargs.get('delcodelists'):
        # while testing with very big loads, deleting gave error.
        # Using raw SQL solved this.
        with transaction.atomic():
            cursor = connection.cursor()
            cursor.execute("""DELETE FROM ccode""")
            cursor.execute("""DELETE FROM ccodetrigger""")

        notification = _('User code lists are deleted.')
        botsglobal.logger.log(LOG_LEVELS['DONE'], notification)
        if request:
            messages.add_message(request, messages.INFO, notification)

    # delpersist
    if kwargs.get('delpersist'):
        with transaction.atomic():
            cursor = connection.cursor()
            cursor.execute("""DELETE FROM persist""")

        notification = _('Persist data is deleted.')
        botsglobal.logger.log(LOG_LEVELS['DONE'], notification)
        if request:
            messages.add_message(request, messages.INFO, notification)

    # delinfile
    if kwargs.get('delinfile'):
        deletefrompath = botslib.join(
            botsglobal.ini.get('directories', 'botssys', 'botssys'), 'infile')
        shutil.rmtree(deletefrompath, ignore_errors=True)

        notification = _('Files in botssys/infile are deleted.')
        botsglobal.logger.log(LOG_LEVELS['DONE'], notification)
        if request:
            messages.add_message(request, messages.INFO, notification)

    # deloutfile
    if kwargs.get('deloutfile'):
        deletefrompath = botslib.join(
            botsglobal.ini.get('directories', 'botssys', 'botssys'), 'outfile')
        shutil.rmtree(deletefrompath, ignore_errors=True)

        notification = _('Files in botssys/outfile are deleted.')
        botsglobal.logger.log(LOG_LEVELS['DONE'], notification)
        if request:
            messages.add_message(request, messages.INFO, notification)

    # deluserscripts
    if kwargs.get('deluserscripts'):
        deletefrompath = botsglobal.ini.get('directories', 'usersysabs')
        for root, dirs, files in os.walk(deletefrompath):
            _head, tail = os.path.split(root)
            if tail == 'charsets':
                del dirs[:]
                continue
            for bestand in files:
                if bestand != '__init__.py':
                    os.remove(os.path.join(root, bestand))

        notification = _('User scripts are deleted (in usersys).')
        botsglobal.logger.log(LOG_LEVELS['DONE'], notification)
        if request:
            messages.add_message(request, messages.INFO, notification)

    botsglobal.logger.log(LOG_LEVELS['DONE'], _('Finished deleting in configuration.'))
