#!/usr/bin/env python
"""
Bots job2queue: Send job to bots jobqueue
"""

import os
import socket
import sys
import xmlrpc.client

import defusedxml.xmlrpc

# Bots-modules
from . import botsglobal
from . import botsinit
from .botslib import gettext
from .jobqueueserver import AUTHORIZED_TASKS


# security patch of xmlrpc lib
defusedxml.xmlrpc.monkey_patch()


def _(txt):
    return gettext(txt) if botsglobal.settings else txt


JOBQUEUEMESSAGE2TXT = {
    0: _('OK, job added to queue.'),
    1: _('Error, job not added to queue. Can not contact jobqueue-server !'),
    2: _('Error, no task specified.'),
    3: _('Error, invalid task !'),
    4: _('Duplicate, job already in queue, not added.'),
}


def send_job_to_jobqueue(task_args, priority=5):
    """
    adds a new job to the bots-jobqueueserver.
    is an xmlrpc client.
    Import this function in eg views.py.
    Received return codes from jobqueueserver:
    0: OK, job added to job queue.
    4: job is a duplicate of job already in the queue
    """
    try:
        remote_server = xmlrpc.client.ServerProxy(
            f"http://localhost:{botsglobal.ini.getint('jobqueue', 'port', 28082)}"
        )
        return remote_server.addjob(task_args, priority)

    except socket.error as exc:
        print('socket.error', exc)
        # jobqueueserver server not active
        return 1


def start():
    """
    Bots Job2queue

    command line argument
    if config (-c option):
      - is before job argument:
              - will be used as config-dir of job2queue it self and not for job
      - is after job argument:
              - use both as config-dir of job2queue and as -c option of job.
      - is before and after job argument:
              - use only the after...
                could change that but seems not to be useful.
    """
    # pylint: disable=too-many-branches
    usage = """
    This is "%(name)s" version %(version)s,
    part of Bots open source edi translator (https://bots-edi.org).
    Places a job in the bots jobqueue.
    Bots jobqueue takes care of correct processing of jobs.

    Usage:
        %(name)s [-c<directory>] [-p<priority>] job [job-parameters]

    Options:
        -c<directory>   directory for configuration files (default: config).
        -p<priority>    priority of job, 1-9 (default: 5, highest priority is 1).

    Example of usage:
        %(name)s bots-engine
        %(name)s /usr/local/bin/bots-engine
        %(name)s -p1 bots-engine -cconfig2 myroute

    """ % {
        'name': os.path.basename(sys.argv[0]),
        'version': botsglobal.version,
    }
    configdir = None
    # default value
    priority = 5
    task_args = []
    for arg in sys.argv[1:]:
        if arg.startswith('-c'):
            if not configdir:
                configdir = arg[2:]
                if not configdir:
                    print(usage)
                    print(_('Error: configuration directory indicated, but no directory name.'))
                    sys.exit(1)
            if task_args:
                task_args.append(arg)
            continue
        if not task_args:
            if arg.startswith('-p'):
                try:
                    priority = int(arg[2:])
                except ValueError:
                    print(usage)
                    print(_('Error: priority should be numeric (1=highest, 9=lowest).'))
                    sys.exit(1)
                continue
            if arg in ['?', '/?', '-h', '--help']:
                print(usage)
                sys.exit(0)
        task_args.append(arg)
    # ***end handling command line arguments**************************

    # No task specified
    if not task_args:
        print(usage)
        print(JOBQUEUEMESSAGE2TXT[2])
        sys.exit(2)

    botsinit.generalinit(configdir)
    if not botsglobal.ini.getboolean('jobqueue', 'enabled', False):
        print(
            _("Error: bots jobqueue is not enabled in %(configdir)s/bots.ini")
            % {"configdir": botsglobal.ini.get("directories", "config")}
        )
        sys.exit(1)

    # Custom AUTHORIZED_TASKS
    if botsglobal.ini.get('jobqueue', 'authorized_tasks', False):
        authorized_tasks = botsglobal.ini.get('jobqueue', 'authorized_tasks').strip()
        globals()['AUTHORIZED_TASKS'] += list(filter(
            bool, authorized_tasks.replace(',', ' ').replace(';', ' ').split(' ')))

    # Invalid task
    if task_args[0] not in AUTHORIZED_TASKS:
        print(usage)
        print(JOBQUEUEMESSAGE2TXT[3])
        sys.exit(3)

    terug = send_job_to_jobqueue(task_args, priority)
    print(JOBQUEUEMESSAGE2TXT[terug])
    sys.exit(terug)


if __name__ == '__main__':
    start()
