# -*- coding: utf-8 -*-
"""
Bots webserver
"""

import os
import sys

import cherrypy
from django.core import management
from django.core.handlers.wsgi import WSGIHandler

from . import botsglobal, botsinit
from .botsinit import STARTINFO
from .botslib import gettext as _

try:
    from cheroot.server import get_ssl_adapter_class
    from cheroot.wsgi import Server, PathInfoDispatcher

except ImportError:
    from cherrypy.wsgiserver import (
        get_ssl_adapter_class,
        CherryPyWSGIServer as Server,
        WSGIPathInfoDispatcher as PathInfoDispatcher
    )


def error_page(status, message, _traceback, _version) -> str:
    """Return html error page"""
    return f"""\
<!DOCTYPE html>
<html>
<head>
<title{status}</title>
</head>
<body>
<h2>{status}</h2>
<p>{message}</p>
</body>
</html>"""


def start():
    """Start Bots webserver"""
    usage = """
    This is "%(name)s" version %(version)s,
    part of Bots open source edi translator (https://bots-edi.org).
    The %(name)s is the web server for bots; the interface (bots-monitor) can be accessed in a
    browser, eg 'http://localhost:8080'.

    Usage:
        %(name)s -c<directory>

    Options:
        -c<directory>   directory for configuration files (default: config).

    """ % {'name': os.path.basename(sys.argv[0]), 'version': botsglobal.version}

    # ***command line arguments**************************
    configdir = None
    for arg in sys.argv[1:]:
        if arg.startswith('-c'):
            configdir = arg[2:]
            if not configdir:
                print('Error: configuration directory indicated, but no directory name.')
                sys.exit(1)
        else:
            print(usage)
            sys.exit(0)
    # ***end handling command line arguments**************************

    # find locating of bots, configfiles, init paths etc.
    botsinit.generalinit(configdir)
    settings = botsglobal.settings

    # initialise file-logging for web-server.
    # This logging only contains the logging from bots-webserver, not from cherrypy.
    botsglobal.logger = botsinit.initserverlogging(__name__)
    botsglobal.logger.log(STARTINFO, _('Starting ...'))

    # ***init cherrypy as webserver*********************************************
    # global configuration for cherrypy
    cherrypy.config.update({
        'global': {
            'log.screen': False,
            'server.environment': botsglobal.ini.get('webserver', 'environment', 'production'),
        },
        # error 404
        'error_page.404': error_page,
    })

    # cherrypy log
    for handler in botsglobal.logger.handlers:
        cherrypy.log.error_log.addHandler(handler)
        if botsglobal.ini.getboolean('webserver', 'log_cherrypy_access', False):
            cherrypy.log.access_log.addHandler(handler)

    # /static
    static_root = settings.STATIC_ROOT.rstrip(os.path.sep)
    if not os.path.isdir(static_root) and not os.access(os.path.dirname(static_root), os.W_OK):
        botsglobal.logger.warning(_('Invalid STATIC_ROOT: %s'), settings.STATIC_ROOT)
    else:
        management.call_command('collectstatic', '--noinput')

    # cherrypy handling of static files
    staticdir = settings.STATIC_ROOT.split(os.sep)
    conf = {'/': {
        'tools.staticdir.on': True,
        'tools.staticdir.dir': staticdir[-1],
        'tools.staticdir.root': os.sep.join((staticdir[:-1])),
    }}
    # None: no cherrypy application (as this only serves static files)
    servestaticfiles = cherrypy.tree.mount(
        None,
        settings.STATIC_URL.rstrip('/'),
        conf
    )

    # cherrypy handling of django
    servedjango = WSGIHandler()
    # cherrypy uses a dispatcher in order to handle the serving of static files and django.
    # UNICODEPROBLEM: needs to be binary
    dispatcher = PathInfoDispatcher({
        '/': servedjango,
        str(settings.STATIC_URL.rstrip('/')): servestaticfiles}
    )
    botswebserver = Server(
        bind_addr=('0.0.0.0', botsglobal.ini.getint('webserver', 'port', 8080)),
        wsgi_app=dispatcher,
        server_name=botsglobal.ini.get('webserver', 'name', 'bots-webserver')
    )
    botsglobal.logger.log(
        STARTINFO,
        _('configdir: "%(configdir)s".'),
        {'configdir': botsglobal.ini.get('directories', 'config')}
    )
    ssl_certificate = botsglobal.ini.get('webserver', 'ssl_certificate', None)
    ssl_private_key = botsglobal.ini.get('webserver', 'ssl_private_key', None)
    if ssl_certificate and ssl_private_key:
        adapter_class = get_ssl_adapter_class('builtin')
        botswebserver.ssl_adapter = adapter_class(ssl_certificate, ssl_private_key)
        botsglobal.logger.log(STARTINFO, _('using ssl (https).'))
    else:
        botsglobal.logger.log(STARTINFO, _('using plain http (no ssl).'))
    botsglobal.logger.log(
        STARTINFO, _('Serving at port: "%(port)s".'),
        {'port': botsglobal.ini.getint('webserver', 'port', 8080)}
    )

    # start the cherrypy webserver.************************************************
    try:
        botswebserver.start()

    except (KeyboardInterrupt, SystemExit):
        sys.stderr.write(os.linesep)

    botsglobal.logger.log(STARTINFO, _('Exiting ...'))
    botswebserver.stop()


if __name__ == '__main__':
    start()
