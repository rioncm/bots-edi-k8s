"""
Bots init lib
"""

import codecs
import configparser
import encodings
import logging
import logging.handlers
import os
import shutil
import sys

import django
import django.conf

# bots-modules
from . import botsglobal
from . import botslib
from . import node
from .exceptions import (
    BotsError,
    BotsImportError,
    PanicError,
)

LOG_FORMAT = '%(asctime)s %(levelname)-9s [%(name)s] %(message)s'
LOG_DT_FORMAT = '%Y.%m.%d %H:%M:%S'
LOG_CONSOLE_FORMAT = LOG_FORMAT


class BotsConfig(configparser.RawConfigParser):
    """As ConfigParser, but with defaults."""
    # pylint: disable=arguments-differ

    def get(self, section, option, default='', **kwargs):
        if self.has_option(section, option):
            result = super().get(section, option, **kwargs)
            return result or default
        if default == '':
            raise BotsError(f'No entry "{option}" in section "{section}" in "bots.ini"')
        return default

    def getint(self, section, option, default, **kwargs):
        if self.has_option(section, option):
            return configparser.RawConfigParser.getint(self, section, option, **kwargs)
        return default

    def getboolean(self, section, option, default, **kwargs):
        if self.has_option(section, option):
            return configparser.RawConfigParser.getboolean(self, section, option, **kwargs)
        return default


def renew_django_secret_key(settings_file: str):
    """
    Renew or add SECRET_KEY in a django settings file

    :param settings_file: str: Path of django settings file
    """
    # pylint: disable=import-outside-toplevel
    from django.core.management.utils import get_random_secret_key

    with open(settings_file, "r", encoding="utf8") as settingsfile:
        newsettings = settingsfile.read()
    with open(settings_file, "w", encoding="utf8") as settingsfile:
        skidx = newsettings.find("\nSECRET_KEY =") + 1
        if skidx > 0:
            settingsfile.write(
                newsettings[:skidx] +
                f'SECRET_KEY = "{get_random_secret_key()}"' +
                newsettings[skidx + newsettings[skidx:].find("\n"):]
            )
        else:
            settingsfile.write(
                newsettings + "\n" +
                f'SECRET_KEY = "{get_random_secret_key()}"' + "\n"
            )


def initbotsenv(**kwargs):
    """
    Initialise bots user env (config, botssys, usersys) with bots directories bots.[config,...]
    if configdir doesn't exist.
    Default bots env is here:
        ~/.bots/env/default

    You can specify a different bots env with env var $BOTSENV:
        ~/.bots/env/$BOTSENV

    :param botsenv:
        - With only botsenv specified, botsenv_path = ~/.bots/env/botsenv/

    :param configdir:
        This will install bots config dir in specified path.
        Note if no botsenv_path arg is specified, botsenv_path will be in ~/.bots/env/?botsenv

    :param botsenv_path:

    ex:
    >>> initbotsenv(botsenv_path='/path/to/botsenv')
    # Will Create:
        /path/to/botsenv/config
        /path/to/botsenv/botsys
        /path/to/botsenv/usersys
    """
    botsenv = kwargs.get("botsenv") or os.environ.get("BOTSENV") or "default"
    botsenv_path = kwargs.get("botsenv_path") or os.path.join(os.path.expanduser("~"), ".bots", "env", botsenv)
    configdir = kwargs.get('configdir') or os.path.join(botsenv_path, 'config')

    if os.sep in configdir and not os.path.isdir(configdir):
        bots_path = os.path.dirname(__file__)
        # Setup new bots env
        print('Installation of bots env:', botsenv_path, file=sys.stderr)
        if kwargs.get('interactive'):
            confirm = input(f"Confirm creation of bots env: '{botsenv_path}' (y/n) ? ")
            if confirm.lower() not in ['y', 'yes']:
                print('Bots env creation canceled.', file=sys.stderr)
                return False
        try:
            # config
            print('Installing bots config:', configdir, file=sys.stderr)
            os.makedirs(configdir)
            with open(os.path.join(configdir, "__init__.py"), "w", encoding="utf8") as initfile:
                initfile.write("")
            # Copy bots.ini and settings.py from bots/install/ in configdir/
            for configfile in ['bots.ini', 'settings.py']:
                shutil.copy(os.path.join(bots_path, 'install', configfile), configdir)
            # botssys
            botssys = os.path.join(botsenv_path, 'botssys')
            if not os.path.exists(botssys):
                print('Installing botssys:', botssys, file=sys.stderr)
                sqlitedb = os.path.join(botssys, 'sqlitedb')
                os.makedirs(sqlitedb)
                shutil.copy(os.path.join(bots_path, 'install', 'botsdb'), sqlitedb)
            # usersys
            usersys = os.path.join(botsenv_path, 'usersys')
            if not os.path.exists(usersys):
                print('Installing bots usersys:', usersys, file=sys.stderr)
                shutil.copytree(os.path.join(bots_path, 'usersys'), usersys)
            # settings.py:
            renew_django_secret_key(os.path.join(configdir, "settings.py"))
            # bots.ini: Set botssys and usersys path
            bots_ini = os.path.join(configdir, "bots.ini")
            with open(bots_ini, "r", encoding="utf8") as botsinifile:
                botsini = botsinifile.read()
            with open(bots_ini, "w", encoding="utf8") as botsinifile:
                botsinifile.write(botsini.replace(
                    "botssys = botssys", f"botssys = {botssys}").replace(
                    "usersys = usersys", f"usersys = {usersys}"))

        except Exception as exc:
            raise PanicError(f'Error while installing bots config "{configdir}": {exc}') from exc

    return configdir


def generalinit(configdir=None):
    """Load bots config from config dir.

    :param configdir: Path to bots config directory

    """
    # pylint: disable=too-many-branches, too-many-statements
    botsenv_path = ""
    if not configdir:
        if os.environ.get('BOTS_CONFIG_DIR'):
            # config dir set from env var $BOTS_CONFIG_DIR
            configdir = os.path.normpath(os.environ.get('BOTS_CONFIG_DIR'))
            botsenv_path = os.path.dirname(configdir.rstrip(os.sep))
        else:
            # config dir set from $BOTSENV in user space ~/.bots/env/$BOTSENV/config
            botsenv = os.environ.get("BOTSENV") or "default"
            botsenv_path = os.path.join(os.path.expanduser('~'), '.bots', 'env', botsenv)
            configdir = os.path.join(botsenv_path, 'config')
            initbotsenv(**locals())

    botsglobal.configdir = configdir = configdir.rstrip(os.path.sep)

    ##########################################################################
    # Configdir: settings.py & bots.ini ######################################
    # Configdir MUST be importable. So configdir is relative to PYTHONPATH.
    # Try several options for this import.
    try:
        # first check if is configdir outside bots-directory: import configdir.settings.py
        os.environ['DJANGO_SETTINGS_MODULE'] = importnameforsettings = os.path.normpath(
            os.path.join(configdir, 'settings')
        ).replace(os.sep, '.')
        settings = botslib.botsbaseimport(importnameforsettings)
    except ImportError:
        # normal: configdir is in bots directory: import bots.configdir.settings.py
        try:
            os.environ['DJANGO_SETTINGS_MODULE'] = importnameforsettings = os.path.normpath(
                os.path.join('bots', configdir, 'settings')
            ).replace(os.sep, '.')
            settings = botslib.botsbaseimport(importnameforsettings)
        except ImportError as exc:
            # set pythonpath to config directory first
            # check if configdir exists.
            if not os.path.exists(configdir):
                raise PanicError(
                    f'In initilisation: path to configuration does not exists: "{configdir}"'
                ) from exc
            moduletoimport = os.path.basename(configdir)
            botsenv_path = addtopythonpath = os.path.abspath(os.path.dirname(configdir))
            if addtopythonpath not in sys.path:
                # print('Adding python path:', addtopythonpath)
                sys.path.append(addtopythonpath)
            importnameforsettings = '.'.join((moduletoimport, 'settings'))
            os.environ['DJANGO_SETTINGS_MODULE'] = importnameforsettings
            # print('importnameforsettings:', importnameforsettings)
            settings = botslib.botsbaseimport(importnameforsettings)
            if not settings.__file__.startswith(configdir):
                raise PanicError(
                    f'Initilisation: settings file imported "{settings.__file__}" '
                    f'not in BOTS_CONFIG_DIR: "{configdir}"'
                    f'Fixe PYTHON_PATH or rename BOTS_CONFIG_DIR folder "{moduletoimport}"'
                ) from exc

    # settings is imported, so now we know where to find settings.py: importnameforsettings
    # note: the imported settings.py itself is NOT used, this is doen via django.conf.settings
    configdirectory = os.path.abspath(os.path.dirname(settings.__file__))
    # Read configuration-file bots.ini.
    botsglobal.ini = BotsConfig()
    botsglobal.ini.read(os.path.join(configdirectory, 'bots.ini'))
    # 'directories','botspath': absolute path for bots directory
    botsglobal.ini.set('directories', 'botspath', os.path.abspath(os.path.dirname(__file__)))
    # 'directories','config': absolute path for config directory
    botsglobal.ini.set('directories', 'config', configdirectory)
    # set config as originally received; used in starting engine via bots-monitor
    botsglobal.ini.set('directories', 'config_org', configdir)
    # "directories", "botsenv": absolute path to bots user env directory
    botsglobal.ini.set("directories", "botsenv", botsenv_path or os.path.dirname(configdirectory.rstrip(os.sep)))
    ###########################################################################
    # Usersys #################################################################
    # usersys MUST be importable. So usersys is relative to PYTHONPATH.
    # Try several options for this import.
    usersys = os.path.normpath(botsglobal.ini.get('directories', 'usersys', 'usersys'))
    try:
        # usersys outside bots-directory: import usersys
        importnameforusersys = usersys.replace(os.sep, '.')
        importedusersys = botslib.botsbaseimport(importnameforusersys)
    except ImportError:
        try:
            # usersys is in bots directory: import bots.usersys
            importnameforusersys = os.path.join('bots', usersys).replace(os.sep, '.')
            importedusersys = botslib.botsbaseimport(importnameforusersys)
        except ImportError as exc:
            # set pythonpath to usersys directory first
            if not os.path.exists(usersys):  # check if configdir exists.
                raise PanicError(f'In initilisation: path to configuration does not exists: "{usersys}"') from exc
            # Usersys directory is absolute path
            addtopythonpath = os.path.abspath(os.path.dirname(usersys))
            importnameforusersys = os.path.basename(usersys)
            if addtopythonpath not in sys.path:
                sys.path.append(addtopythonpath)
            importedusersys = botslib.botsbaseimport(importnameforusersys)

    # 'directories', 'usersysabs': absolute path for config usersysabs
    # Find pathname usersys using imported usersys
    botsglobal.ini.set('directories', 'usersysabs', importedusersys.__path__[0])
    # botsglobal.usersysimportpath: used for imports from usersys
    botsglobal.usersysimportpath = importnameforusersys
    botsglobal.ini.set(
        'directories', 'templatehtml', botslib.join(
            botsglobal.ini.get('directories', 'usersysabs'),
            'grammars/templatehtml/templates'
        )
    )

    ############################################################################
    # Botssys ##################################################################
    # 'directories','botssys': absolute path for config botssys
    botssys = botsglobal.ini.get('directories', 'botssys', 'botssys')
    # store original botssys setting
    botsglobal.ini.set('directories', 'botssys_org', botssys)
    # use absolute path
    botsglobal.ini.set('directories', 'botssys', botslib.join(botssys))
    botsglobal.ini.set('directories', 'data', botslib.join(botssys, 'data'))
    botsglobal.ini.set('directories', 'logging', botslib.join(botssys, 'logging'))
    botsglobal.ini.set('directories', 'users', botslib.join(botssys, '.users'))
    # dirmonitor trigger
    botsglobal.ini.set('dirmonitor', 'trigger', botslib.join(botssys, '.dirmonitor.trigger'))
    botsglobal.ini.set('settings', 'log_when', botsglobal.ini.get('settings', 'log_when', 'report'))
    ############################################################################
    # other inits ##############################################################
    botsglobal.ini.set("settings", "django_db_connection", botsglobal.ini.get("settings", "django_db_connection", None))
    # values in bots.ini are also used in setting up cherrypy
    if botsglobal.ini.get('webserver', 'environment', 'development') != 'development':
        # during production: if errors occurs in writing to log: ignore error.
        # (leads to a missing log line, better than error;-).
        logging.raiseExceptions = 0

    botslib.dirshouldbethere(botsglobal.ini.get('directories', 'data'))
    botslib.dirshouldbethere(botsglobal.ini.get('directories', 'logging'))
    # initialise bots charsets
    initbotscharsets()
    node.Node.checklevel = botsglobal.ini.getint('settings', 'get_checklevel', 1)
    botslib.settimeout(botsglobal.ini.getint('settings', 'globaltimeout', 10))

    ############################################################################
    # Init django ##############################################################
    if not django.conf.settings.configured:
        django.setup()

    # settings are accessed using botsglobal
    botsglobal.settings = django.conf.settings

    # Djediint add-on
    if 'djediint' in botsglobal.settings.INSTALLED_APPS:
        # pylint: disable=import-error, import-outside-toplevel
        import djediint.bots
        print(f"{djediint.bots.__name__} imported.")


# **********************************************************************************
# *** bots specific handling of character-sets (eg UNOA charset) *******************
def initbotscharsets():
    """set up right charset handling for specific charsets (UNOA, UNOB, UNOC, etc)."""
    # tell python how to search a codec defined by bots. Bots searches for this in usersys/charset
    codecs.register(codec_search_function)
    # syntax has parameters checkcharsetin or checkcharsetout. These can have value 'botsreplace'
    # eg: 'checkcharsetin':'botsreplace',  #strict, ignore or botsreplace
    # in case of errors: the 'wrong' character is replaced with char as set in bots.ini.
    # Default value in bots.ini is ' ' (space)
    botsglobal.botsreplacechar = str(botsglobal.ini.get("settings", "botsreplacechar", " "))
    # need to register the handler for botsreplacechar
    codecs.register_error('botsreplace', botsreplacechar_handler)
    # set aliases for the charsets in bots.ini
    for key, value in botsglobal.ini.items('charsets'):
        encodings.aliases.aliases[key] = value


def codec_search_function(encoding):
    """Try import charset"""
    try:
        module, _filename = botslib.botsimport('charsets', encoding)
    except BotsImportError:
        # charsetscript not there; other errors like syntax errors are not catched
        return None
    if hasattr(module, 'getregentry'):
        return module.getregentry()
    return None


def botsreplacechar_handler(info):
    """
    replaces an char outside a charset by a user defined char.
    Useful eg for fixed records: recordlength does not change.
    """
    return (botsglobal.botsreplacechar, info.start + 1)


# *** end of bots specific handling of character-sets ******************************
# **********************************************************************************


def connect():
    """connect to database for non-django modules eg engine"""
    # pylint: disable=import-error, import-outside-toplevel
    from django.db import connections

    db = botsglobal.ini.get("settings", "django_db_connection", None)
    if db:
        botsglobal.db = connections[db]
        botsglobal.logger.debug("botsglobal.db: %s", botsglobal.db)
        botsglobal.logger.debug("botsglobal.db.__module__: %s", botsglobal.db.__module__)
        return botsglobal.db

    db_settings = botsglobal.settings.DATABASES["default"]
    db_engine = db_settings["ENGINE"]
    if db_engine == 'django.db.backends.sqlite3':
        # sqlite has some more fiddling; in separate file.
        # Mainly because of some other method of parameter passing.
        if not os.path.isfile(db_settings["NAME"]):
            raise PanicError('Could not find database file for SQLite')
        from . import botssqlite

        botsglobal.db = botssqlite.connect(
            database=db_settings["NAME"]
        )
    elif db_engine == "django.db.backends.postgresql":
        import psycopg
        from psycopg.rows import dict_row

        botsglobal.db = psycopg.connect(
            host=db_settings["HOST"],
            port=db_settings["PORT"],
            dbname=db_settings["NAME"],
            user=db_settings["USER"],
            password=db_settings["PASSWORD"],
            row_factory=dict_row,
            # client_encoding="utf-8",
            **db_settings["OPTIONS"]
        )
    elif db_engine == 'django.db.backends.mysql':
        import MySQLdb
        from MySQLdb import cursors

        botsglobal.db = MySQLdb.connect(
            host=db_settings["HOST"],
            port=int(db_settings["PORT"]),
            db=db_settings["NAME"],
            user=db_settings["USER"],
            passwd=db_settings["PASSWORD"],
            cursorclass=cursors.DictCursor,
            **db_settings["OPTIONS"]
        )
    elif db_engine == "django.db.backends.postgresql_psycopg2":
        import psycopg2
        import psycopg2.extensions
        import psycopg2.extras

        psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)
        botsglobal.db = psycopg2.connect(
            host=db_settings["HOST"],
            port=db_settings["PORT"],
            database=db_settings["NAME"],
            user=db_settings["USER"],
            password=db_settings["PASSWORD"],
            connection_factory=psycopg2.extras.DictConnection,
        )
        botsglobal.db.set_client_encoding('UNICODE')
    elif db_engine:
        botsglobal.logger.warning("Using untested django database engine: %s", db_engine)
        botsglobal.db = connections[db]
    else:
        raise PanicError("Database engine not set")
    botsglobal.logger.debug("botsglobal.db: %s", botsglobal.db)
    return botsglobal.db


# *******************************************************************
# *** init logging **************************************************
# *******************************************************************
STARTINFO = 28
LOG_LEVELS = {
    'DEBUG': logging.DEBUG,
    'STDOUT': 11,  # coms & jobqueue-server job stdout
    'STDERR': 12,  # coms & jobqueue-server job stderr
    'INFO': logging.INFO,
    'COM': 25,
    'DONE': 26,
    'START': 27,
    'STARTINFO': STARTINFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL,
}
logging.addLevelName(LOG_LEVELS['STARTINFO'], 'STARTINFO')
logging.addLevelName(LOG_LEVELS['STDOUT'], 'STDOUT')
logging.addLevelName(LOG_LEVELS['STDERR'], 'STDERR')
logging.addLevelName(LOG_LEVELS['START'], 'START')
logging.addLevelName(LOG_LEVELS['DONE'], 'DONE')


def initenginelogging(logname):
    """initialise engine logging: create engine logger."""
    logger = logging.getLogger(logname)
    proc_name = logname.replace(f"{__package__}.", "")
    logdir = os.path.join(botsglobal.ini.get('directories', 'logging'), proc_name)
    botslib.dirshouldbethere(logdir)
    log_when = botsglobal.ini.get('settings', 'log_when', None)
    if log_when == 'daily':
        handler = logging.handlers.TimedRotatingFileHandler(
            os.path.join(logdir, proc_name + '.log'),
            encoding="utf-8",
            when='midnight',
            backupCount=botsglobal.ini.getint('settings', 'log_file_number', 30),
        )
    else:
        handler = logging.handlers.RotatingFileHandler(
            os.path.join(logdir, proc_name + '.log'),
            encoding="utf-8",
            backupCount=botsglobal.ini.getint('settings', 'log_file_number', 10),
        )
        if log_when is None:
            # each run a new log file is used; old one is rotated
            handler.doRollover()
    fileformat = logging.Formatter(LOG_FORMAT, LOG_DT_FORMAT)
    handler.setFormatter(fileformat)
    handler.setLevel(botsglobal.ini.get('settings', 'log_file_level', 'INFO'))
    logger.addHandler(handler)

    # initialise file logging: logger for trace of mapping;
    # tried to use filters but got this not to work ...
    botsglobal.logmap = logging.getLogger('engine.map')
    if not botsglobal.ini.getboolean('settings', 'mappingdebug', False):
        botsglobal.logmap.setLevel(logging.CRITICAL)
    # logger for reading edifile. is now used only very limited (1 place); is done with 'if'
    # botsglobal.ini.getboolean('settings', 'readrecorddebug', False)

    # initialise console/screen logging
    if botsglobal.ini.getboolean('settings', 'log_console', True):
        console = logging.StreamHandler()
        consoleformat = logging.Formatter(LOG_CONSOLE_FORMAT, LOG_DT_FORMAT)
        # add formatter to console
        console.setFormatter(consoleformat)
        # Set console log level
        console.setLevel(botsglobal.ini.get('settings', 'log_console_level', 'INFO'))
        # add console to logger
        logger.addHandler(console)

    # Global Bots LOG LEVEL: bots.engine, bots.engine2
    logger.setLevel(botsglobal.ini.get('settings', 'log_level', 'INFO'))
    if not botsglobal.ini.get('settings', 'log_level', None):
        for handler in logger.handlers:
            if handler.level < logger.level:
                logger.setLevel(handler.level)
    return logger


def initserverlogging(logname):
    """initialise file logging"""
    logger = logging.getLogger(logname)
    proc_name = logname.replace(f"{__package__}.", "").replace("jobqueueserver", "jobqueue")
    logdir = os.path.join(botsglobal.ini.get('directories', 'logging'), proc_name)
    botslib.dirshouldbethere(logdir)
    handler = logging.handlers.TimedRotatingFileHandler(
        os.path.join(logdir, proc_name + '.log'),
        encoding="utf-8",
        when='midnight',
        backupCount=botsglobal.ini.getint(
            proc_name, 'log_file_number', botsglobal.ini.getint('settings', 'log_file_number', 30)),
    )
    fileformat = logging.Formatter(LOG_FORMAT, LOG_DT_FORMAT)
    handler.setFormatter(fileformat)
    handler.setLevel(botsglobal.ini.get(proc_name, 'log_file_level', 'INFO'))
    logger.addHandler(handler)

    # initialise console/screen logging
    if botsglobal.ini.getboolean(proc_name, 'log_console', True):
        console = logging.StreamHandler()
        consoleformat = logging.Formatter(LOG_CONSOLE_FORMAT, LOG_DT_FORMAT)
        # add formatter to console
        console.setFormatter(consoleformat)
        # Set console log level
        console.setLevel(botsglobal.ini.get(proc_name, 'log_console_level', 'STARTINFO'))
        # add console to logger
        logger.addHandler(console)

    # Bots server(s) LOG LEVEL: bots.jobqueue, bots.dirmonitor, bots.webserver
    logger.setLevel(botsglobal.ini.get(proc_name, 'log_level', 'INFO'))
    if not botsglobal.ini.get(proc_name, 'log_level', None):
        for handler in logger.handlers:
            if handler.level < logger.level:
                logger.setLevel(handler.level)
    return logger
