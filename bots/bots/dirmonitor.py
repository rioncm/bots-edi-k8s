"""
Bots dirmonitor
Watch new files in directories.
If a new file appear, lauch a job to the jobqueue server (so: jobqueue-server is needed).
directories to wachs are in config/bots.ini
runs as a daemon/service.
this module contains separate implementations for linux and windows
"""

import atexit
import fnmatch
import glob
import logging
import os
import sys
import threading
import time

# bots-modules
from . import botsinit
from . import botsglobal
from . import job2queue
from .botsinit import STARTINFO
from .botslib import sendbotserrorreport, gettext as _
from .exceptions import DirmonitorError

# get path to bots-engine
BOTSENGINEPATH = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), 'bots-engine')

logger = logging.getLogger(__name__)


def add_job(task):
    """Add job to jobqueue"""
    logger.info(
        _('Sending job to queue: "%(path)s %(config)s %(task)s".'),
        {
            'path': BOTSENGINEPATH,
            'config': '-c' + botsglobal.configdir,
            'task': task,
        },
    )
    task_args = ['bots-engine']
    if os.path.dirname(BOTSENGINEPATH) not in os.environ['PATH'].split(':'):
        task_args = [BOTSENGINEPATH]
    task_args.append(f"-c{botsglobal.configdir}")
    task_args.append(task)
    logger.debug('task args: %s', task_args)
    ret = job2queue.send_job_to_jobqueue(task_args)
    if ret == 0:
        logger.info(job2queue.JOBQUEUEMESSAGE2TXT[ret])
    elif ret == 1:
        err = f"Task: {task}, "
        err += job2queue.JOBQUEUEMESSAGE2TXT[ret]
        logger.error(err)
        sendbotserrorreport(__name__, err)
    else:
        logger.warning(job2queue.JOBQUEUEMESSAGE2TXT[ret])
    return ret


def process_existing_files(dir_watch_data):
    """Launch route of watching directories if files are found in it."""
    # pylint: disable=too-many-branches
    logger.info(_('Looking for files in watched directories ...'))
    for dir_watch in dir_watch_data:
        match = False
        if dir_watch['idroute'] == 'dirmonitor-trigger':
            dirmonitor_trigger = botsglobal.ini.get('dirmonitor', 'trigger')
            if os.path.isfile(dirmonitor_trigger):
                # Clear dirmonitor_trigger
                if os.access(dirmonitor_trigger, os.W_OK):
                    os.remove(dirmonitor_trigger)
                else:
                    logger.critical(
                        _('dirminitor trigger file could not be deleted: %s'), dirmonitor_trigger)
            continue
        # Verify if route.fromchannel remove files
        if dir_watch.get('route') and not dir_watch['route'].fromchannel.remove:
            logger.info(
                _('Skip processing (not removed) files from file channel : %s'),
                dir_watch['route'].fromchannel)
            continue
        if dir_watch['rec']:
            for key in os.walk(dir_watch['path']):
                for filename in key[2]:
                    if fnmatch.fnmatch(filename, dir_watch['filemask']):
                        logger.debug('File(s) to process found: %s', os.path.join(key[0], filename))
                        match = True
                        break
                if match:
                    break
        else:
            for filename in glob.iglob(os.path.join(dir_watch['path'], dir_watch['filemask'])):
                if os.path.isfile(filename):
                    logger.info('File(s) to process found: %s', filename)
                    match = True
                    break
        if match:
            logger.debug('File(s) in directory: %s', dir_watch['path'])
            add_job(dir_watch['idroute'])


if os.name == 'nt':
    try:
        import win32file
        import win32con
    except ImportError as exc:
        raise DirmonitorError(
            _(
                'Dependency failure: bots directory monitoring'
                ' requires python library "Python Win32 Extensions" on windows.'
            )
        ) from exc

    def windows_event_handler(dir_watch, cond, tasks):
        """Bots windows event handler"""
        # pylint: disable=invalid-name
        ACTIONS = {
            1: 'Created  ',  # tekst for printing results
            2: 'Deleted  ',
            3: 'Updated  ',
            4: 'Rename from',
            5: 'Rename to',
        }
        FILE_LIST_DIRECTORY = 0x0001
        hdir = win32file.CreateFile(
            dir_watch['path'],  # path to directory
            FILE_LIST_DIRECTORY,  # access (read/write) mode
            # share mode: FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE
            win32con.FILE_SHARE_READ
            | win32con.FILE_SHARE_WRITE
            | win32con.FILE_SHARE_DELETE,
            # security descriptor
            None,
            win32con.OPEN_EXISTING,  # how to create
            # file attributes: FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OVERLAPPED
            win32con.FILE_FLAG_BACKUP_SEMANTICS,
            None,
        )
        # detecting right events is not easy in windows :-(
        # want to detect: new file,  move, drop, rename, write/append to file
        # only FILE_NOTIFY_CHANGE_LAST_WRITE: copy yes, no move
        # for rec=True: event that subdirectory itself is updated (for file deletes in dir)
        while True:
            results = win32file.ReadDirectoryChangesW(
                hdir,
                8192,  # buffer size was 1024, do not want to miss anything
                dir_watch['rec'],  # recursive
                win32con.FILE_NOTIFY_CHANGE_FILE_NAME |
                # ~ win32con.FILE_NOTIFY_CHANGE_DIR_NAME |
                # ~ win32con.FILE_NOTIFY_CHANGE_ATTRIBUTES |
                # ~ win32con.FILE_NOTIFY_CHANGE_SIZE |
                # ~ win32con.FILE_NOTIFY_CHANGE_SECURITY |
                # ~ win32con.FILE_NOTIFY_CHANGE_CREATION |       # unknown, does not work!
                # ~ win32con.FILE_NOTIFsY_CHANGE_LAST_ACCESS |   # unknown, does not work!
                win32con.FILE_NOTIFY_CHANGE_LAST_WRITE,
                None,
                None,
            )
            if results:
                # for each incoming event: place route to run in a set. Main thread takes action.
                for action, filename in results:
                    logger.debug(
                        'Event: %(action)s %(filename)s',
                        {'action': ACTIONS.get(action, 'Unknown'), 'filename': filename},
                    )
                for action, filename in results:
                    if action in [1, 3, 5] and filename in glob.glob(
                            os.path.join(dir_watch['path'], dir_watch['filemask'])):
                        cond.acquire()
                        tasks.add(dir_watch['idroute'])
                        cond.notify()
                        cond.release()
                        # the route is triggered, do not need to trigger more often
                        break

    # end of windows-specific #####################################################################

elif os.name == 'posix':
    # linux specific ##############################################################################
    try:
        import pyinotify

    except ImportError as exc:
        raise ImportError(
            _(
                'Dependency failure: bots directory monitoring'
                ' requires python library "pyinotify" on linux.'
            )
        ) from exc

    class LinuxEventHandler(pyinotify.ProcessEvent):
        """
        incoming event contains:
            dir=<bool>    check? - looks like the mask does never contains dirs.
            mask=0x80
            maskname=eg IN_MOVED_TO
            name=<filename>
            path=<path>
            pathname=<path>/<filename>
            wd=<int>     #the watch
        """
        # pylint: disable=invalid-name

        dir_watch_data: list = []
        cond = None
        tasks: set = set()

        def my_init(self, dir_watch_data: list, cond, tasks: set):
            """Custom handler init"""
            # pylint: disable=arguments-differ
            self.dir_watch_data = dir_watch_data
            self.cond = cond
            self.tasks = tasks

        # def process_default(self, event):
        #     """All other events not catched."""
        #     logger.debug('Default event: %s' % event)

        def process_IN_CREATE(self, event):
            """these event are needed for auto_add with pyinotify.IN_CREATE mask."""

        # def process_IN_MODIFY(self, event):
        #     """pyinotify.IN_MODIFY event."""

        def process_IN_CLOSE_WRITE(self, event):
            """pyinotify.IN_CLOSE_WRITE event."""
            self.process_event(event)

        def process_IN_MOVED_TO(self, event):
            """pyinotify.IN_MOVED_TO event."""
            self.process_event(event)

        def process_event(self, event):
            """
            for each incoming event: place route to run in a set.
            Main thread sends actual job.
            """
            # if event.mask == pyinotify.IN_CLOSE_WRITE \
            #         and event.dir and self.watch_data[event.wd][2]:
            # logger.info('new directory!!"%s %s".', *event)
            logger.debug('Process event: %s', event)
            for dir_watch in self.dir_watch_data:
                if event.pathname.startswith(dir_watch['path'].split('*')[0]):
                    if event.pathname in glob.glob(
                            os.path.join(dir_watch['path'], dir_watch['filemask'])):
                        logger.debug('Event match: %s', dir_watch)
                        # if os.path.isfile(event.pathname):
                        logger.info(
                            'New file for route %s: %s',
                            dir_watch['idroute'], event.pathname)
                        self.cond.acquire()
                        self.tasks.add(dir_watch['idroute'])
                        self.cond.notify()
                        self.cond.release()
                        break

    # pylint: disable=no-member
    MASK = (
        pyinotify.IN_CLOSE_WRITE
        | pyinotify.IN_MOVED_TO
        # | pyinotify.IN_MODIFY
        | pyinotify.IN_CREATE
    )

    class WatchManager(pyinotify.WatchManager):
        """
        Init a pyinotify.WatchManager() and add watch to each path in data_watch_data arg.
        """
        # pylint: disable=too-few-public-methods

        def __init__(self, dir_watch_data, *args, **kwargs):
            super().__init__(*args, **kwargs)
            for dir_watch in dir_watch_data:
                logger.info(_('Watched directory: %s'), dir_watch['path'])
                self.add_watch(
                    path=dir_watch['path'].split('*')[0],
                    mask=MASK,
                    rec=dir_watch['rec'],
                    auto_add='*' in dir_watch['path'],
                    do_glob=True
                )

    def linux_event_handler(dir_watch_data, cond, tasks):
        """Function to watch and notify watched paths. (Obsolete)"""
        watch_manager = WatchManager(dir_watch_data)
        handler = LinuxEventHandler(
            dir_watch_data=dir_watch_data,
            cond=cond,
            tasks=tasks
        )
        notifier = pyinotify.Notifier(watch_manager, handler)
        notifier.loop()

    # end of linux-specific #######################################################################

else:
    raise DirmonitorError(_('Unsupported operating system: %s') % os.name)


def start():
    """Start bots dirmonitor"""
    usage = f"""
    This is "{os.path.basename(sys.argv[0])}" version {botsglobal.version},
    bots-dirmonitor run a specific route when new file(s) arrived in a configured directory

    Usage:
        %(name)s -c<directory>

    Options:
        -c<drrectory>   directory for configuration files (default: config).
        --reload        Reload bots-dirmonitor if already running.

    """
    # ***command line arguments**************************
    configdir = None
    reload_dirmonitor = False
    for arg in sys.argv[1:]:
        if arg.startswith('-c'):
            configdir = arg[2:]
            if not configdir:
                print(_('Error: configuration directory indicated, but no directory name.'))
                sys.exit(1)
        elif arg == '--reload':
            reload_dirmonitor = True
        else:
            print(usage)
            sys.exit(0)
    # ***end handling command line arguments**************************

    # find locating of bots, configfiles, init paths etc.
    botsinit.generalinit(configdir)
    if not botsglobal.ini.getboolean('jobqueue', 'enabled', False):
        print(
            _("Error: bots jobqueue is not enabled in %(configdir)s/bots.ini")
            % {'configdir': botsglobal.ini.get('directories', 'config')}
        )
        sys.exit(1)

    # Verify if jobqueue server is up
    if job2queue.send_job_to_jobqueue(['isup']) == 1:
        print(job2queue.JOBQUEUEMESSAGE2TXT[1].rsplit(". ", maxsplit=1)[-1])
        sys.exit(1)

    # TODO: Catch if dirmonitor is already running ?
    # print(_('Error: bots dirmonitor already running'))

    if reload_dirmonitor:
        dirmonitor_trigger = botsglobal.ini.get('dirmonitor', 'trigger')
        with open(dirmonitor_trigger, "w", encoding="utf8") as trig:
            trig.write("reload")
        print(_('bots dirmonitor reload task sent'))
        sys.exit(0)

    botsglobal.logger = botsinit.initserverlogging(__name__)
    atexit.register(logging.shutdown)
    logger.log(STARTINFO, _('Starting ...'))
    logger.log(
        STARTINFO,
        _('configdir: "%(configdir)s".'),
        {'configdir': botsglobal.ini.get('directories', 'config')},
    )
    tasks = set()
    while dirmonitoring(tasks):
        pass


def dirmonitoring(tasks: set) -> bool:
    """List and watch active bots directories files and launch corresponding bots route"""
    # pylint: disable=import-outside-toplevel, too-many-branches, too-many-statements, too-many-locals
    from . import models

    cond = threading.Condition()
    dir_watch_data = []
    watched_path = {}
    # Add dirmonitor sections in bots.ini
    for section in botsglobal.ini.sections():
        if section.startswith('dirmonitor') and section[len('dirmonitor'):]:
            watch_data = {
                'path': botsglobal.ini.get(section, 'path'),
                'rec': botsglobal.ini.getboolean(section, 'recursive', False),
                'filemask': botsglobal.ini.get(section, 'filemask', '*'),
                'idroute': botsglobal.ini.get(section, 'route', ''),
            }
            watched_path.setdefault(watch_data['path'], {})
            if watched_path.get(watch_data['path']):
                if watched_path[watch_data['path']].get(watch_data['filemask']):
                    logger.warning(
                        'Skipping already watched path for route "%s": %s%s%s',
                        watch_data['idroute'], watch_data['path'], os.sep, watch_data['filemask'])
                    if watched_path[watch_data['path']][watch_data['filemask']] != watch_data['idroute']:
                        logger.error(
                            'Several routes to run for same watched path/filemask: "%s" != "%s"',
                            watch_data['idroute'],
                            watched_path[watch_data['path']][watch_data['filemask']])
                    continue
            logger.info(
                'Watched path added for route "%s": %s',
                watch_data['idroute'], os.path.join(watch_data['path'], watch_data['filemask']))
            watched_path[watch_data['path']][watch_data['filemask']] = watch_data['idroute']
            dir_watch_data.append(watch_data)

    # Add dirmonitored route with fromchannel (file)
    for route in models.routes.objects.filter(active=True, dirmonitor=True):
        logger.info('Monitored route found: %s', route)
        watch_data = {
            'path': route.fromchannel.path,
            'rec': '*' in route.fromchannel.path,
            'filemask': route.fromchannel.filename,
            'idroute': route.idroute,
            'route': route,
        }
        watched_path.setdefault(watch_data['path'], {})
        if watched_path.get(watch_data['path']):
            if watched_path[watch_data['path']].get(watch_data['filemask']):
                logger.warning(
                    'Skipping already watched path for route "%s": %s%s%s',
                    watch_data['route'], watch_data['path'], os.sep, watch_data['filemask'])
                if watched_path[watch_data['path']][watch_data['filemask']] != watch_data['route']:
                    logger.error(
                        'Several routes to run for same watched path/filemask: "%s" != "%s"',
                        watch_data['route'],
                        watched_path[watch_data['path']][watch_data['filemask']])
                continue
        logger.info(
            'Watched path added for route "%s": %s',
            watch_data['route'], os.path.join(watch_data['path'], watch_data['filemask']))
        watched_path[watch_data['path']][watch_data['filemask']] = watch_data['idroute']
        dir_watch_data.append(watch_data)

    if not dir_watch_data:
        logger.warning(_('No directory to monitor found.'))

    # Add dirmonitor trigger
    dirmonitor_trigger = botsglobal.ini.get('dirmonitor', 'trigger')
    dir_watch_data.append({
        'path': os.path.dirname(dirmonitor_trigger),
        'rec': False,
        'filemask': os.path.basename(dirmonitor_trigger),
        'idroute': 'dirmonitor-trigger',
    })

    # process existings files before watcher
    if botsglobal.ini.getboolean('dirmonitor', 'process_existing', True):
        process_existing_files(dir_watch_data)

    if os.name == 'nt':
        # for windows: start a thread per directory watcher
        dir_watch_threads = []
        for dir_watch in dir_watch_data:
            dir_watch_thread = threading.Thread(
                target=windows_event_handler,
                args=(dir_watch, cond, tasks),
            )
            # do not wait for thread when exiting
            dir_watch_thread.daemon = True
            dir_watch_thread.start()
            dir_watch_threads.append(dir_watch_thread)
    else:
        watch_manager = WatchManager(dir_watch_data)
        event_handler = LinuxEventHandler(
            dir_watch_data=dir_watch_data,
            cond=cond,
            tasks=tasks,
        )
        notifier = pyinotify.ThreadedNotifier(watch_manager, event_handler)
        notifier.start()

    # this main thread get the results from the watch-thread(s).
    active_receiving = False
    timeout = 2.0
    cond.acquire()
    logger.info(_('Started.'))
    # pylint: disable=too-many-nested-blocks
    try:
        while True:
            # this functions as a buffer: all events go into set tasks.
            # the tasks are fired to jobqueue after TIMOUT sec.
            # this is to avoid firing to many tasks to jobqueue;
            # events typically come in bursts.
            # is value of timeout is larger, reaction times are slower...
            # but less tasks are fired to jobqueue.
            # in itself this is not a problem, as jobqueue will alos discard duplicate jobs.
            # 2 sec seems to e a good value: reasonable quick, not to nervous.

            # get back when results, or after timeout sec
            cond.wait(timeout=timeout)
            if tasks:
                if not active_receiving:
                    # first request (after tasks have been fired, or startup of dirmonitor)
                    active_receiving = True
                    last_time = time.time()
                else:
                    # active receiving events
                    current_time = time.time()
                    if current_time - last_time >= timeout:
                        # cond.wait returned probably because of a timeout
                        try:
                            while tasks:
                                task = tasks.pop()
                                if task and task == 'dirmonitor-trigger':
                                    if os.path.isfile(dirmonitor_trigger):
                                        with open(dirmonitor_trigger, "r", encoding="utf8") as trig:
                                            todos = trig.read().strip().split(" ")
                                        # Delete dirmonitor_trigger
                                        if os.access(dirmonitor_trigger, os.W_OK):
                                            os.remove(dirmonitor_trigger)
                                        else:
                                            logger.critical(
                                                'dirmonitor trigger file could not be deleted: %s',
                                                dirmonitor_trigger)
                                        if todos:
                                            logger.info('%s: %s', task, todos)
                                            for todo in todos:
                                                if todo == 'reload':
                                                    # Reload dirmonitor
                                                    logger.info('Reloading dirmonitor ...')
                                                    if os.name == 'posix':
                                                        notifier.stop()
                                                        if task in tasks:
                                                            tasks.remove(task)
                                                    elif os.name == 'nt':
                                                        for dir_watch_thread in dir_watch_threads:
                                                            dir_watch_thread.do_run = False
                                                            dir_watch_thread.join()
                                                    cond.release()
                                                    return True
                                                if todo:
                                                    logger.error(_('Unknown request: %s'), todo)
                                else:
                                    add_job(task)
                        # pylint: disable=broad-exception-caught
                        except Exception as exc:
                            logger.error(
                                _('Error in running task: "%(exc)s".'),
                                {'exc': exc}
                            )
                        active_receiving = False
                    else:
                        # cond.wait returned probably because of a timeout
                        logger.debug(_('time difference to small.'))
                        last_time = current_time

    except (KeyboardInterrupt, SystemExit):
        sys.stderr.write(os.linesep)

    logger.info(_('Exiting ...'))
    if os.name == 'posix':
        notifier.stop()
    # pylint: disable=protected-access
    if cond._is_owned():
        cond.release()
    return False


if __name__ == '__main__':
    start()
