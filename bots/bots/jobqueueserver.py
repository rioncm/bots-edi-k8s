# -*- coding: utf-8 -*-
"""
Bots jobqueue: manage bots jobs by priority
There is the xml/rpc listner part, to add jobs in the queue
And some threads to run jobs in the queue.
"""

import atexit
import logging
import os
import queue
import signal
import subprocess
import sys
import threading
import time
from xmlrpc.server import SimpleXMLRPCServer

import defusedxml.xmlrpc

from . import botsglobal
from . import botsinit
from . import botslib
from .botsinit import LOG_LEVELS, STARTINFO
from .botslib import gettext as _


# security patch of xmlrpc lib
defusedxml.xmlrpc.monkey_patch()

STDOUT = STDERR = subprocess.PIPE

# Job args
PRIORITY = 0
JOBNUMBER = 1
TASK = 2

logger = logging.getLogger(__name__)

BOTS_TASKS = ['bots-engine']
AUTHORIZED_TASKS = BOTS_TASKS[:]
for path in os.environ.get('PATH', '').split(';' if os.name == 'nt' else ':'):
    for bots_task in BOTS_TASKS:
        task_path = os.path.join(path, bots_task)
        if os.path.isfile(task_path) and task_path not in AUTHORIZED_TASKS:
            AUTHORIZED_TASKS.append(task_path)


class Jobqueue:
    """
    handles the jobqueue.
    methodes can be called over xmlrpc (except the methods starting with '_')
    """

    def __init__(self, jobqueue):
        """ """
        # queue list of jobs. in jobqueue are jobs are: (priority,jobnumber,task)
        self.jobqueue = jobqueue
        # to assign unique sequential job-number
        self.jobcounter = 0

    def addjob(self, task, priority):
        """Add job to queue"""
        if not task:
            logger.error(_('No task specified.'))
            return 2
        if task[0] == 'isup':
            logger.info(_('%s is up.'), __name__)
            return 0
        # Filter dangerous task, as non-bots-tasks might be started ...
        # authorise only bots tasks.
        if task[0] not in AUTHORIZED_TASKS:
            logger.error(_('Invalid task received: %(task)s'), {'task': task})
            return 3
        # canonize task (to better find duplicates)??.
        # first check if job already in queue
        for job in self.jobqueue.queue:
            if job[TASK] == task:
                if job[PRIORITY] != priority:
                    # change priority. is this useful?
                    job[PRIORITY] = priority
                    logger.info(
                        _('Duplicate job, changed priority to %(priority)s: %(task)s'),
                        {'priority': priority, 'task': task},
                    )
                    self._sort()
                    # zero or other code??
                    return 0
                logger.warning(_('Duplicate job not added: %(task)s'), {'task': task})
                return 4
        # add the job
        self.jobcounter += 1
        job = [priority, self.jobcounter, task]
        self.jobqueue.put(job)
        logger.info(
            _('Added job %(job)s, priority %(priority)s: %(task)s'),
            {'job': self.jobcounter, 'priority': priority, 'task': task},
        )
        self._sort()
        return 0

    def listjobs(self):
        """List jobs queue"""
        if not self.jobqueue.empty():
            return list(self.jobqueue.queue)
        return 0

    def clearjobq(self):
        """Clear jobs queue"""
        self.jobqueue.queue.clear()
        logger.info(_('Job queue cleared.'))
        return 0

    def _sort(self):
        """Sort jobs by priority"""
        if not self.jobqueue.empty():
            # Lock queue
            self.jobqueue.mutex.acquire_lock()
            jobs = list(self.jobqueue.queue)
            jobs.sort(reverse=True)
            self.jobqueue.queue.clear()
            self.jobqueue.queue.extend(jobs)
            logger.debug(
                'Sorted jobs queue: \n%s',
                "\n".join([repr(job) for job in self.jobqueue.queue])
            )
            # Unlock queue
            self.jobqueue.mutex.release_lock()


def action_when_time_out(maxruntime, job, proc, kill=False):  # pylint: disable=unused-argument
    """Function called when a job subprocess timeout is reached."""
    # pylint: disable=possibly-unused-variable
    jobnumber, task_to_run = job[1:]
    logger.error(_('Job %(jobnumber)s exceeded maxruntime of %(maxruntime)s minutes'), locals())
    botslib.sendbotserrorreport(
        _('[Bots Job Queue] - Job exceeded maximum runtime'),
        _('Job %(jobnumber)s exceeded maxruntime of %(maxruntime)s minutes:\n %(task_to_run)s')
        % locals()
    )
    if kill and not proc.returncode:
        logger.info(_('Terminating job %(jobnumber)s: %(task_to_run)s'), locals())
        proc.terminate()
        if not proc.returncode:
            logger.info(_('Killing job %(jobnumber)s: %(task_to_run)s'), locals())
            proc.kill()


def launcher(jobqueue, maxruntime):
    """
    Bots jobqueue launcher
    Listen jobs in queue and subprocess each one
    """
    timeout = maxruntime * 60
    # allow jobqserver to start
    time.sleep(2)
    logger.debug(_('Job launcher running'))
    nko = 0
    while True:
        # logger.debug('queue: %s', repr(jobqueue.queue))
        job = jobqueue.get(block=True, timeout=None)
        if job:
            jobnumber, task_to_run = job[1:]
            logger.log(LOG_LEVELS['START'], _('Starting job %(jobnumber)s: %(task_to_run)s'), locals())
            try:
                starttime = time.time()
                with subprocess.Popen(task_to_run, stdout=STDOUT, stderr=STDERR) as proc:
                    # Start a timer thread for process timeout action
                    timer = threading.Timer(
                        timeout,
                        action_when_time_out,
                        args=(
                            maxruntime,
                            job,
                            proc,
                            botsglobal.ini.getboolean("jobqueue", "killjobsintimeout", False),
                        ),
                    )
                    timer.start()
                    # timeout subprocess >= python 3.3
                    # proc reach timeout raise TimeoutExpired
                    # ex: proc.communicate(timeout=timeout)
                    # Useless here, keep thread timer.
                    outs, errs = proc.communicate()
                    timer.cancel()
                    time_taken = time.time() - starttime
                    returncode = proc.returncode
                if returncode != 0:
                    logger.error(_('job %(job)s, exit with code %(returncode)s'), locals())
                if errs:
                    if isinstance(errs, bytes):
                        errs = errs.decode()
                    if returncode != 0:
                        logger.error("%s%s", os.linesep, errs)
                    else:
                        logger.log(LOG_LEVELS["STDERR"], "%s %s", os.linesep, errs)
                if outs:
                    if isinstance(outs, bytes):
                        outs = outs.decode()
                    logger.log(LOG_LEVELS['STDOUT'], "%s %s", os.linesep, outs)
                logger.log(
                    LOG_LEVELS['DONE'],
                    _(
                        'Finished job %(jobnumber)s, elapsed time: %(time_taken)s,'
                        ' exit code %(returncode)s'
                    ),
                    {"jobnumber": jobnumber, "time_taken": time_taken, "returncode": returncode},
                )
                nko = 0
            except Exception as exc:  # pylint: disable=broad-exception-caught
                nko += 1
                logger.error(
                    _("Error starting job %(jobnumber)s: %(exc)"),
                    {"jobnumber": jobnumber, "exc": exc},
                )
                botslib.sendbotserrorreport(
                    _('[Bots Job Queue] - Error starting job'),
                    _('Error starting job %(jobnumber)s:\n %(task_to_run)s\n\n %(exc)s') % locals(),
                )
                if nko >= 10:
                    logger.error(_(
                        'More than 10 consecutive errors in the bots-jobqueueserver, '
                        'shutting down now'
                    ))
                    botslib.sendbotserrorreport(
                        _('[Bots Job Queue] bots-jobqueueserver has stopped'),
                        _('More than 10 consecutive errors occured in the bots-jobqueueserver, '
                          'so jobqueue-server is stopped now.')
                    )
                    sys.exit(1)

            jobqueue.task_done()


def start():
    """
    Start Bots Jobqueue
    """
    usage = """
    This is "%(name)s" version %(version)s,
    part of Bots open source edi translator (https://bots-edi.org).

    Server program that ensures only a single bots-engine runs at any time,
    and no engine run requests are lost/discarded.
    Each request goes to a queue and is run in sequence when the previous run completes.

    # Use of the job queue is optional and must be configured in bots.ini (jobqueue section):
        enabled = True

    # To authorize custom task to be launched, add in bots.ini (jobqueue section):
        authorized_tasks = /path/bin/custom /path/bin/custom2

    # Kill Jobs in timeout (jobs exceeded maxruntime)
        killjobsintimeout = False

    Usage:
        %(name)s -c<directory>

    Options:
        -c<directory>   directory for configuration files (default: config).

    """ % {
        'name': os.path.basename(sys.argv[0]),
        'version': botsglobal.version,
    }

    # ***command line arguments**************************
    configdir = None
    for arg in sys.argv[1:]:
        if arg.startswith('-c'):
            configdir = arg[2:]
            if not configdir:
                print(_('Error: configuration directory indicated, but no directory name.'))
                sys.exit(1)
        else:
            print(usage)
            sys.exit(0)
    # ***end handling command line arguments**************************

    # find locating of bots, configfiles, init paths etc.
    botsinit.generalinit(configdir)
    if not botsglobal.ini.getboolean('jobqueue', 'enabled', False):
        print(_('Error: bots jobqueue is not enabled in %(configdir)s/bots.ini') % {
            'configdir': botsglobal.ini.get('directories', 'config')})
        sys.exit(1)

    botsglobal.logger = botsinit.initserverlogging(__name__)
    # atexit.register(logging.shutdown)
    logger.log(STARTINFO, _('Starting ...'))
    logger.log(
        STARTINFO,
        _('configdir: "%(configdir)s".'),
        {'configdir': botsglobal.ini.get('directories', 'config')},
    )
    # AUTHORIZED_TASKS in bots.ini
    if botsglobal.ini.get('jobqueue', 'authorized_tasks', False):
        authorized_tasks = botsglobal.ini.get('jobqueue', 'authorized_tasks').strip()
        globals()['AUTHORIZED_TASKS'] += list(filter(
            bool, authorized_tasks.replace(',', ' ').replace(';', ' ').split(' ')))
    logger.debug('AUTHORIZED_TASKS: %s', AUTHORIZED_TASKS)

    # Init job queue
    jobqueue = queue.Queue()
    atexit.register(jobqueue.join)

    # start launcher thread(s)
    maxruntime = botsglobal.ini.getint('settings', 'maxruntime', 60)
    nr_threads = botsglobal.ini.getint('jobqueue', 'nr_threads', 1)
    for __ in range(nr_threads):
        launcher_thread = threading.Thread(
            name='launcher',
            target=launcher,
            args=(jobqueue, maxruntime),
        )
        launcher_thread.start()
        atexit.register(launcher_thread.join)

    port = botsglobal.ini.getint('jobqueue', 'port', 28082)
    # the main thread is the xmlrpc server:
    # all adding, getting etc for jobqueue is done via xmlrpc.
    server = SimpleXMLRPCServer(('localhost', port), logRequests=False)
    server.register_instance(Jobqueue(jobqueue))
    atexit.register(server.shutdown)
    logger.log(
        STARTINFO,
        _('Listening xmlrpc request on port: "%(port)s".'),
        {'port': port},
    )

    try:
        server.serve_forever()

    except (KeyboardInterrupt, SystemExit):
        sys.stderr.write(os.linesep)

    logger.info(_('Exiting ...'))
    os.kill(os.getpid(), signal.SIGTERM)


if __name__ == '__main__':
    start()
