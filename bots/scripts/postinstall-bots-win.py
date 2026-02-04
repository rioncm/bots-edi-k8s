from __future__ import unicode_literals, print_function

import os
import shutil
import subprocess
import sys
import time
import traceback
import pkg_resources

from bots import botsglobal, __about__ as about


def join(path, *paths):
    return os.path.normpath(os.path.join(path, *paths))


# ******************************************************************************
# ***    start                     *********************************************
# ******************************************************************************
def start():
    print('Installation of %s.' % about.__summary__)
    pkg = pkg_resources.get_distribution(about.__title__)

    # python version dependencies
    version = str(sys.version_info[0]) + str(sys.version_info[1])
    if version <= '26' or (version >= '30' and version < '34'):
        raise Exception('Wrong python version, use python2 2.7.* or python3 >= 3.4.*')

    botsdir = os.path.dirname(botsglobal.__file__)
    print('    Installed bots in "%s".' % (botsdir))

    # ******************************************************************************
    # ***    install libraries, dependencies  ***************************************
    # ******************************************************************************
    installers = []
    packages_dir = join(botsdir, 'install')

    # pip doesn't support egg-info/requires.txt as requirements file ...
    requirements = [requirement.__str__() for requirement in pkg.requires()]

    for requirement in requirements:
        installers.append(subprocess.Popen([
            join(sys.prefix, 'pythonw.exe'), '-m', 'pip', 'install',
            '-f', packages_dir,
            '--no-index',  # Offline mode
            requirement]))

    ready = False
    while not ready:
        time.sleep(1)
        for installer in installers:
            if installer.poll() is None:
                break
        else:
            ready = True

    print('    Installed requires libraries.')

    # ******************************************************************************
    # ***    shortcuts       *******************************************************
    # ******************************************************************************
    scriptpath = join(sys.prefix, 'Scripts')
    shortcutdir = join(
        get_special_folder_path('CSIDL_COMMON_PROGRAMS'),
        '%s-%s' % (about.__title__, about.__version__))
    try:
        os.mkdir(shortcutdir)
    except:
        pass
    else:
        directory_created(shortcutdir)

    try:
        create_shortcut(
            join(scriptpath, 'bots-webserver.exe'),
            'bots open source edi translator',
            join(shortcutdir, 'bots-webserver.lnk'),
            '',  # Params
            '',  # workdir
            join(botsdir, 'static', 'images', 'favicon.ico')
        )
        file_created(join(shortcutdir, 'bots-webserver.lnk'))
        shutil.copy(
            join(shortcutdir, 'bots-webserver.lnk'),
            join(DESKTOP_FOLDER, 'bots-webserver.lnk'),
        )
        file_created(join(DESKTOP_FOLDER, 'bots-webserver.lnk'))
    except:
        print('    Failed to install shortcut/link for bots in your menu.')
    else:
        print('    Installed shortcut in "Program Files".')

    # ******************************************************************************
    # ***    install configuration files      **************************************
    # ******************************************************************************
    # use this to see if this is an existing installation
    if os.path.exists(join(botsdir, 'config', 'settings.py')):
        print('    Found existing configuration files')
        print('        Configuration files bots.ini and settings.py not overwritten.')
        print('        Manual action is needed for these configuration files.')
        print('        See bots wiki for more info: https://bots.readthedocs.io/')
    else:
        shutil.copy(join(botsdir, 'install', 'bots.ini'), join(botsdir, 'config', 'bots.ini'))
        shutil.copy(join(botsdir, 'install', 'settings.py'), join(botsdir, 'config', 'settings.py'))
        print('    Installed configuration files')

    # ******************************************************************************
    # ***    install database; upgrade existing db *********************************
    # ******************************************************************************
    sqlitedir = join(botsdir, 'botssys', 'sqlitedb')
    # Look at existing installed database
    if os.path.exists(join(sqlitedir, 'botsdb')):
        print('    Found existing database file botssys/sqlitedb/botsdb')
        print('        Manual action is needed to convert the database to new bots 3.0 format.')
        print('        There is a script to update the database.')
        print('        See bots wiki for more info: https://bots.readthedocs.io/')
    else:
        if not os.path.exists(sqlitedir):
            os.makedirs(sqlitedir)
        shutil.copy(join(botsdir, 'install', 'botsdb'), join(sqlitedir, 'botsdb'))
        print('    Installed SQLite database')


#******************************************************************************
#******************************************************************************

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '-install':
        try:
            start()
        except:
            print(traceback.format_exc(0))
            print('\r\nBots installation failed.')
        else:
            print('\r\nBots installation succeeded.')
    # avoid strange errors when UAC is off.
    try:
        sys.stdout.flush()
    except IOError:
        pass
    try:
        sys.stderr.flush()
    except IOError:
        pass
