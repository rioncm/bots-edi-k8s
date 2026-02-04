"""
Bots communication lib
"""
# pylint: disable=invalid-name, missing-class-docstring, missing-function-docstring
# pylint: disable=too-many-branches, too-many-statements, broad-exception-caught, too-many-lines

import base64
import datetime
import email
import email.encoders
import email.generator
import email.header
import email.message
import email.policy
import email.utils
import ftplib
import fnmatch
import glob
import json as simplejson
import logging
import os
import posixpath
import shutil
import smtplib
import socket
import ssl
import sys
import time
import zipfile

# bots-modules
from . import botsglobal
from . import botslib
from .botsconfig import (
    OK,
    DONE,
    ERROR,
    MERGED,
    FILEIN,
    FILEOUT,
    EXTERNIN,
    EXTERNOUT,
)
from .botsinit import LOG_LEVELS
from .botslib import gettext as _
from .exceptions import (
    BotsError,
    BotsImportError,
    CommunicationError,
    CommunicationInError,
    CommunicationOutError,
    LockedFileError,
    ScriptImportError,
    txtexc,
)

# pylint: disable=import-error
if os.name == 'nt':
    import msvcrt
elif os.name == 'posix':
    import fcntl


MAXLINE = 100000000


class LoggerPipe:
    """Class to redirect stderr, stdout write(msg)/flush(), print() text to a logger."""

    def __init__(self, logger=botsglobal.logger, level=LOG_LEVELS['DEBUG']):
        self.logger = logger
        self.level = level
        self.buffer = ''

    def write(self, txt):
        self.buffer += txt
        if txt.endswith('\n'):
            self.flush()

    def flush(self):
        if self.buffer:
            self.logger.log(self.level, self.buffer.rstrip())
            self.buffer = ''


@botslib.log_session
def run(idchannel, command, idroute, rootidta=None):
    """run a communication session (dispatcher for communication functions)."""
    if rootidta is None:
        rootidta = botsglobal.currentrun.get_minta4query()
    for row in botslib.query(
            """SELECT *
               FROM channel
               WHERE idchannel=%(idchannel)s""",
            {'idchannel': idchannel}):
        # convert to real dictionary ()
        channeldict = dict(row)
        botsglobal.logger.log(
            LOG_LEVELS['START'],
            _('Start communication channel %(inorout)s: %(idchannel)s (%(type)s)'), channeldict
        )
        # for acceptance testing bots has an option to turn of external communication in channels
        if botsglobal.ini.getboolean('acceptance', 'runacceptancetest', False):
            # override values in channels for acceptance testing.
            # testpath is used to 'trigger' this: if testpath has value, use acceptance.
            if channeldict['testpath']:
                # use the testpath to specify where to find acceptance  tests.
                channeldict['path'] = channeldict['testpath']
                # never remove during acceptance testing
                channeldict['remove'] = False
                if channeldict['type'] in ['file', 'mimefile', 'trash']:
                    # do nothing, same type
                    pass
                elif channeldict['type'] in [
                        'smtp',
                        'smtps',
                        'smtpstarttls',
                        'pop3',
                        'pop3s',
                        'pop3apop',
                        'imap4',
                        'imap4s',
                ]:
                    channeldict['type'] = 'mimefile'
                else:
                    # channeldict["type"] in
                    # ["ftp", "ftps", "ftpis", "sftp", "xmlrpc", "ftp", "ftp", "communicationscript", "db"]
                    channeldict['type'] = 'file'
            botsglobal.logger.debug(
                'Channel "%(idchannel)s" adapted for acceptance test:'
                ' type "%(type)s", testpath "%(testpath)s".',
                channeldict,
            )

        # update communication/run process with idchannel  # pylint: disable=protected-access
        ta_run = botslib.OldTransaction(botslib._Transaction.processlist[-1])
        if channeldict['inorout'] == 'in':
            ta_run.update(fromchannel=channeldict['idchannel'])
        else:
            ta_run.update(tochannel=channeldict['idchannel'])

        try:
            userscript, scriptname = botslib.botsimport(
                'communicationscripts', channeldict['idchannel']
            )
        except BotsImportError:
            # communicationscript is not there; other errors like syntax errors are not catched
            userscript = scriptname = None
        # get the communication class to use:
        # check communication class in userscript (sub classing)
        if userscript and hasattr(userscript, channeldict['type']):
            classtocall = getattr(userscript, channeldict['type'])
        # check for communication class called 'UserCommunicationClass' in userscript.
        # 20110920: Obsolete, depreciated. Keep this for now.
        elif userscript and hasattr(userscript, 'UserCommunicationClass'):
            # 20130206: does have advantages...like for testing etc (no dependent upon type)
            classtocall = getattr(userscript, 'UserCommunicationClass')
        else:
            # get the communication class from this module
            classtocall = globals()[channeldict['type']]

        # call the class for this type of channel
        comclass = classtocall(channeldict, idroute, userscript, scriptname, command, rootidta)
        comclass.run()
        botsglobal.logger.log(
            LOG_LEVELS['DONE'],
            _('Finished communication channel %(inorout)s: %(idchannel)s (%(type)s)'),
            channeldict
        )
        # there can only be one channel;
        # this break takes care that if found, the 'else'-clause is skipped
        break
    else:
        raise CommunicationError(
            _('Channel "%(idchannel)s" is unknown.'), {'idchannel': idchannel}
        )


class _comsession:
    """
    Abstract class for communication-session. Use only subclasses.
    Subclasses are called by dispatcher function 'run'
    Often 'idroute' is passed as a parameter.
    This is ONLY because of the @botslib.log_session-wrapper!
    use self.idroute!!
    """
    # pylint: disable=too-many-instance-attributes, too-many-arguments, too-many-positional-arguments

    def __init__(self, channeldict, idroute, userscript, scriptname, command, rootidta):
        self.channeldict = channeldict
        self.idroute = idroute
        self.userscript = userscript
        self.scriptname = scriptname
        self.command = command
        self.rootidta = rootidta
        self.transport = None
        self.session = None
        self.dbconnection = None
        self.filename = None
        self.dirpath = None
        self.xmlrpc_call = None
        self.lockname = None
        self.auth = None
        self.url = None
        self.cert = None
        self.requests = None
        self.listoftamarkedfordelete = None
        self.maxsecondsperchannel = None
        self.debug = channeldict.get('debug')

    def stderr2log(self):
        """Catch stdout and stderr to botsglobal.logger"""
        logging.addLevelName(LOG_LEVELS['COM'], self.__class__.__name__.upper())
        if self.debug:
            sys.stderr = LoggerPipe(botsglobal.logger, LOG_LEVELS['COM'])
            sys.stdout = LoggerPipe(botsglobal.logger, LOG_LEVELS['STDOUT'])

    def stderr2log_release(self):
        # Keep it, overided each connect() (imap4s, ...)
        # logging.addLevelName(LOG_LEVELS['COM'], 'COM')
        if self.debug and isinstance(sys.stderr, LoggerPipe):
            sys.stderr.flush()
            sys.stderr = sys.__stderr__
            sys.stdout.flush()
            sys.stdout = sys.__stdout__

    def run(self):
        if self.channeldict['inorout'] == 'out':
            self.precommunicate()
            # connect
            # maxconnectiontries: channel.rsrv1 should be integer, but only textfields were left.
            # so might be None->use 0.
            maxconnectiontries = int(self.channeldict['rsrv1']) if self.channeldict['rsrv1']\
                else botsglobal.ini.getint('settings', 'maxconnectiontries', 0)
            connect_tries = 0
            while True:
                connect_tries += 1
                try:
                    self.connect()
                    # out-connection OK
                    if self.debug:
                        botsglobal.logger.debug(
                            _('Out channel connected: %s'),
                            self.channeldict['idchannel'])
                    break
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    self.stderr2log_release()
                    botsglobal.logger.error(
                        _('Outgoing connection failure %(connect_tries)s'
                          ' on channel %(channel)s: %(exc)s'),
                        {
                            'connect_tries': connect_tries,
                            'channel': self.channeldict['idchannel'],
                            'exc': exc,
                        })
                    if connect_tries >= maxconnectiontries:
                        raise
            self.outcommunicate()
            self.disconnect()

        else:
            # self.channeldict['inorout'] == 'in'
            # do incommunication
            if self.command == 'new':
                # only in-communicate for new run
                # handle maxsecondsperchannel:
                #   - use global value from bots.ini unless specified in channel.
                # (In database this is field 'rsrv2'.)
                self.maxsecondsperchannel = (
                    self.channeldict['rsrv2']
                    if self.channeldict['rsrv2'] is not None and self.channeldict['rsrv2'] > 0
                    else botsglobal.ini.getint('settings', 'maxsecondsperchannel', sys.maxsize)
                )
                # Max failures (channel.rsrv1)

                # In-channel: bots keeps count of consecutive failures across runs
                # for an in-channel before reporting a process error
                # should be integer, but only textfields were left. so might be None->use 0.
                maxfailures = int(self.channeldict['rsrv1']) if self.channeldict['rsrv1'] else 0
                domain = f"bots_communication_failure_{self.channeldict['idchannel']}"

                # bots tries to connect several times.
                # this is probably a better stategy than having long time-outs.
                maxconnectiontries = botsglobal.ini.getint('settings', 'maxconnectiontries', 3)
                connect_tries = 0
                while True:
                    connect_tries += 1
                    try:
                        self.connect()
                        # in-connection OK
                        if maxfailures:
                            # set nr_failures to zero
                            botslib.unique(domain, updatewith=0)
                        break

                    except Exception as exc:  # pylint: disable=broad-exception-caught
                        self.stderr2log_release()
                        botsglobal.logger.error(
                            _('Communication try %(connect_tries)s error'
                              ' on channel %(channel)s: %(exc)s'),
                            {
                                'connect_tries': connect_tries,
                                'channel': self.channeldict['idchannel'],
                                'exc': exc,
                            })
                        # check if maxconnectiontries is reached
                        if connect_tries >= maxconnectiontries:
                            # in-connection failed (no files are received yet via this channel)
                            if maxfailures:
                                # store in database how many failed connection tries for this channel.
                                # useful if bots is scheduled quite often,
                                # and limiting number of error-reports eg when server is down.
                                # update nr_failures in database
                                nr_failures = botslib.unique(domain)
                                botsglobal.logger.error(
                                    _('Communication failure %(nr_failures)s/%(maxfailures)s'
                                      ' on channel %(channel)s: %(exc)s'),
                                    {
                                        'nr_failures': nr_failures,
                                        'maxfailures': maxfailures,
                                        'channel': self.channeldict['idchannel'],
                                        'exc': exc,
                                    })
                                if nr_failures >= maxfailures:
                                    # maxfailures is reached: reset nr_failures to zero and raise
                                    botslib.unique(domain, updatewith=0)
                                    raise
                                # maxfailures is not reached. return without error
                                return
                            raise
                self.incommunicate()
                self.disconnect()
            self.postcommunicate()
        self.archive()

    def archive(self):
        """
        after the communication channel has ran, archive received of send files.
        archivepath is the root directory for the archive (for this channel).
        within the archivepath files are stored by default as [archivepath]/[date]/[unique_filename]
        """
        if not self.channeldict['archivepath']:
            # do not archive if not indicated
            return
        if botsglobal.ini.getboolean('acceptance', 'runacceptancetest', False):
            # do not archive in acceptance testing
            return
        if self.channeldict['filename'] and self.channeldict['type'] in [
                'file',
                'ftp',
                'ftps',
                'ftpis',
                'sftp',
                'mimefile',
                'communicationscript',
                ]:
            # use external filename in archive
            archiveexternalname = botsglobal.ini.getboolean(
                'settings', 'archiveexternalname', False
            )
        else:
            archiveexternalname = False
        if self.channeldict['inorout'] == 'in':
            status = FILEIN
            statust = OK
            channel = 'fromchannel'
        else:
            if archiveexternalname:
                status = EXTERNOUT
            else:
                status = FILEOUT
            statust = DONE
            channel = 'tochannel'
        # user script can manipulate archivepath
        if self.userscript and hasattr(self.userscript, 'archivepath'):
            archivepath = botslib.runscript(
                self.userscript, self.scriptname, 'archivepath', channeldict=self.channeldict
            )
        else:
            archivepath = botslib.join(self.channeldict['archivepath'], time.strftime('%Y%m%d'))
        # archive to zip or not
        archivezip = botsglobal.ini.getboolean('settings', 'archivezip', False)
        if archivezip:
            archivepath += '.zip'
        # for a outchannel that is less used, lots of empty dirs will be created.
        # This var is used to check within loop if dir exist, but this is only checked one time.
        checkedifarchivepathisthere = False
        # pylint: disable=consider-using-with
        archivezipfilehandler = None
        for row in botslib.query(
                f"""SELECT filename,idta
                FROM ta
                WHERE idta>%(rootidta)s
                AND status=%(status)s
                AND statust=%(statust)s
                AND {channel}=%(idchannel)s""",
                {
                    'idchannel': self.channeldict['idchannel'],
                    'status': status,
                    'statust': statust,
                    'rootidta': self.rootidta,
                }):
            if not checkedifarchivepathisthere:
                if archivezip:
                    botslib.dirshouldbethere(os.path.dirname(archivepath))
                    archivezipfilehandler = zipfile.ZipFile(archivepath, 'a', zipfile.ZIP_DEFLATED)
                else:
                    botslib.dirshouldbethere(archivepath)
                checkedifarchivepathisthere = True

            if archiveexternalname:
                if self.channeldict['inorout'] == 'in':
                    # we have internal filename, get external
                    absfilename = botslib.abspathdata(row["filename"])
                    taparent = botslib.OldTransaction(idta=row["idta"])
                    ta_list = botslib.trace_origin(ta=taparent, where={'status': EXTERNIN})
                    if ta_list:
                        archivename = os.path.basename(ta_list[-1].filename)
                    else:
                        archivename = row["filename"]
                else:
                    # we have external filename, get internal
                    archivename = os.path.basename(row["filename"])
                    taparent = botslib.OldTransaction(idta=row["idta"])
                    ta_list = botslib.trace_origin(ta=taparent, where={'status': FILEOUT})
                    absfilename = botslib.abspathdata(ta_list[0].filename)
            else:
                # use internal name in archive
                absfilename = botslib.abspathdata(row["filename"])
                archivename = os.path.basename(row["filename"])

            if self.userscript and hasattr(self.userscript, 'archivename'):
                archivename = botslib.runscript(
                    self.userscript,
                    self.scriptname,
                    'archivename',
                    channeldict=self.channeldict,
                    idta=row["idta"],
                    filename=absfilename,
                )

            if archivezip:
                archivezipfilehandler.write(absfilename, archivename)
            else:
                # if a file of the same name already exists, add a timestamp
                if os.path.isfile(botslib.join(archivepath, archivename)):
                    archivename = (
                        os.path.splitext(archivename)[0]
                        + time.strftime('_%H%M%S')
                        + os.path.splitext(archivename)[1]
                    )
                shutil.copy(absfilename, botslib.join(archivepath, archivename))

        if archivezip and checkedifarchivepathisthere:
            archivezipfilehandler.close()

    def incommunicate(self):
        pass

    def outcommunicate(self):
        pass

    def postcommunicate(self):
        pass

    def precommunicate(self):
        pass

    def file2mime(self):
        """
        convert 'plain' files into email (mime-document).
        1 edi file always in 1 mail.
        from status FILEOUT to FILEOUT
        """
        # pylint: disable=too-many-locals, too-many-nested-blocks
        # select files with right statust, status and channel.
        for row in botslib.query(
                """SELECT idta,filename,frompartner,topartner,charset,contenttype,editype,frommail,tomail,cc
                   FROM ta
                   WHERE idta>%(rootidta)s
                   AND status=%(status)s
                   AND statust=%(statust)s
                   AND tochannel=%(idchannel)s
                   ORDER BY idta
                """,
                {
                    'idchannel': self.channeldict['idchannel'],
                    'status': FILEOUT,
                    'statust': OK,
                    'idroute': self.idroute,
                    'rootidta': self.rootidta,
                }):
            try:
                ta_from = botslib.OldTransaction(row["idta"])
                ta_to = ta_from.copyta(status=FILEOUT)
                # needed for user exits: get all parameters of ta_to from database;
                ta_to.synall()
                confirmtype = ''
                confirmasked = False
                charset = row["charset"]

                if row["editype"] == "email-confirmation" \
                        or self.command == "automaticretrycommunication":
                    # outgoing MDN: message is already assembled
                    outfilename = row["filename"]
                else:
                    # assemble message: headers and payload.
                    # Bots uses simple MIME-envelope; by default payload is an attachment
                    message = email.message.Message()
                    # set frompartner/sender/'from' header
                    frommail = row["frommail"]
                    if self.userscript and hasattr(self.userscript, 'frommail'):
                        # user exit to determine to-address/sender
                        frommail = botslib.runscript(
                            self.userscript,
                            self.scriptname,
                            'frommail',
                            channeldict=self.channeldict,
                            ta=ta_to,
                        )
                    if not frommail:
                        # lookup email address for partnerID
                        frommail, _ccfrom_not_used_variable = self.idpartner2mailaddress(
                            row["frompartner"]
                        )
                    message.add_header('From', frommail)

                    # set topartner/receiver/'to' header
                    tomail = row["tomail"]
                    ccto = row["cc"]
                    if self.userscript:
                        tomailscript = None
                        if hasattr(self.userscript, 'tomail'):
                            tomailscript = 'tomail'
                        elif hasattr(self.userscript, 'getmailaddressforreceiver'):
                            tomailscript = 'getmailaddressforreceiver'
                        if tomailscript:
                            # user exit to determine to-address/receiver
                            tomail = botslib.runscript(
                                self.userscript,
                                self.scriptname,
                                tomailscript,
                                channeldict=self.channeldict,
                                ta=ta_to,
                            )
                            if isinstance(tomail, tuple):
                                if len(tomail) > 1:
                                    ccto = tomail[1]
                                tomail = tomail[0]
                    if not tomail:
                        # lookup email address for partnerID
                        tomail, ccto = self.idpartner2mailaddress(row["topartner"])
                    message.add_header('To', tomail)
                    if ccto:
                        message.add_header('CC', ccto)

                    if botsglobal.ini.getboolean('acceptance', 'runacceptancetest', False):
                        reference = '123message-ID email should be unique123'
                        email_datetime = email.utils.formatdate(
                            timeval=time.mktime(
                                time.strptime('2013-01-23 01:23:45', '%Y-%m-%d %H:%M:%S')
                            ),
                            localtime=True,
                        )
                    else:
                        # use transaction idta in message id.
                        reference = email.utils.make_msgid(str(ta_to.idta))
                        email_datetime = email.utils.formatdate(localtime=True)
                    message.add_header('Message-ID', reference)
                    message.add_header('Date', email_datetime)
                    # update now (in order to use correct & updated ta_to in userscript)
                    # 20220131  for now field 'reference' is max 256
                    ta_to.update(
                        frommail=frommail, tomail=tomail, cc=ccto, reference=reference[:256]
                    )
                    # set Disposition-Notification-To: ask/ask not a a MDN?
                    if botslib.checkconfirmrules(
                            'ask-email-MDN',
                            idroute=self.idroute,
                            idchannel=self.channeldict['idchannel'],
                            frompartner=row["frompartner"],
                            topartner=row["topartner"]):
                        message.add_header('Disposition-Notification-To', frommail)
                        confirmtype = 'ask-email-MDN'
                        confirmasked = True

                    # set subject
                    subject = str(row["idta"])
                    if botsglobal.ini.getboolean('acceptance', 'runacceptancetest', False):
                        subject = '12345678'
                    # get attachment from data file
                    content = botslib.readdata_bin(row["filename"])
                    if self.userscript and hasattr(self.userscript, 'subject'):
                        # user exit to determine subject
                        subject = botslib.runscript(
                            self.userscript,
                            self.scriptname,
                            'subject',
                            channeldict=self.channeldict,
                            ta=ta_to,
                            subjectstring=subject,
                            content=content,
                        )
                    message.add_header('Subject', subject)

                    # set MIME-version
                    message.add_header('MIME-Version', '1.0')

                    # set attachment filename
                    filename_mask = self.channeldict['filename'] or '*'
                    attachmentfilename = self.filename_formatter(filename_mask, ta_to)

                    # set multipart message ?
                    filemessage = message
                    if 'multipart' in self.channeldict['sendmdn']:
                        message.add_header('Content-Type', 'multipart/mixed')
                        filemessage = email.message.Message()

                    # is message send as body or attachment ?
                    if attachmentfilename and 'body' not in self.channeldict['sendmdn']:
                        # there is an field in channel for this:
                        #    'sendmdn' (in interface this is called: 'as body or as attachment')
                        # another option is to use user scripting (set attachmentfilename - or not)
                        # user scripting can also be used to set
                        # - within one channel - one message as  body other as attachment.
                        # send as attachment:
                        #    if 'As body or attachment' is not 'body' AND there is an attachmentfilename
                        # send as body:
                        #     if 'As body or attachment' is 'body' or if there is not attachmentfilename
                        # attachmentfilename can be set to None or '' via user exit 'filename'

                        if 'attach' in self.channeldict['sendmdn']:
                            filemessage.add_header(
                                'Content-Disposition', 'attachment', filename=attachmentfilename
                            )

                    # set Content-Type and charset
                    charset = self.convertcodecformime(charset)
                    # contenttype is set in grammar.syntax
                    filemessage.add_header(
                        'Content-Type', row["contenttype"].lower(),
                        **{'charset': charset} if charset else {}
                    )

                    # set attachment/payload; the Content-Transfer-Encoding is set by python encoder
                    # do not use charset; this lead to unwanted encodings...bots always uses base64
                    filemessage.set_payload(content)

                    if self.channeldict['askmdn'] == 'never':
                        # channeldict['askmdn'] is the Mime encoding
                        # no encoding; but the Content-Transfer-Encoding is set to 7-bit or 8-bt
                        email.encoders.encode_7or8bit(filemessage)
                    elif self.channeldict['askmdn'] == 'ascii' and charset == 'us-ascii':
                        # do nothing: ascii is default encoding
                        pass
                    else:
                        # if Mime encoding is 'always' or  (Mime encoding == 'ascii'
                        # and charset!='us-ascii'): use base64
                        email.encoders.encode_base64(filemessage)

                    if 'multipart' in self.channeldict['sendmdn']:
                        message.attach(filemessage)

                    # set/change email header in user scripting
                    if self.userscript and hasattr(self.userscript, 'headers'):
                        headers = botslib.runscript(
                            self.userscript,
                            self.scriptname,
                            'headers',
                            message=message,
                            channeldict=self.channeldict,
                            ta=ta_to,
                            content=content,
                        )
                        if isinstance(headers, dict):
                            # Update message headers if returned headers is dict
                            for key, val in headers.items():
                                message.add_header(key, val)
                        elif isinstance(headers, email.message.Message):
                            message = headers

                    # *******write email to file***************************
                    outfilename = str(ta_to.idta)
                    with botslib.opendata_bin(outfilename, 'wb') as outfile:
                        generator = email.generator.BytesGenerator(
                            outfile, mangle_from_=False, maxheaderlen=78,
                            policy=email.policy.SMTP,
                        )
                        generator.flatten(message, unixfrom=False)
            except Exception:
                txt = txtexc()
                ta_to.update(statust=ERROR, errortext=txt)
            else:
                ta_to.update(
                    statust=OK,
                    filename=outfilename,
                    confirmtype=confirmtype,
                    confirmasked=confirmasked,
                    contenttype='message/rfc822',
                    charset=charset,
                    rsrv2=1
                )
            finally:
                ta_from.update(statust=DONE)

    def mime2file(self):
        """
        convert emails (mime-documents) to 'plain' files.
        from status FILEIN to FILEIN
        process emails:
         - extract information (eg sender-address)
         - generate MDN (if asked and OK from bots-configuration)
         - process MDN
         - save 'attachments' as files
         - filter emails/attachments based on contenttype
         - email-address should be know by bots (can be turned off)
        """
        # pylint: disable=too-many-locals
        allowlist_multipart = set([
            'multipart/mixed',
            'multipart/digest',
            'multipart/signed',
            'multipart/report',
            'message/rfc822',
            'multipart/alternative',
            'multipart/related',
        ])
        allowlist_major = ['text', 'application']
        blocklist_contenttype = set([
            'text/html',
            'text/enriched',
            'text/rtf',
            'text/richtext',
            'application/postscript',
            'text/vcard',
            'text/css',
        ])

        logging.addLevelName(LOG_LEVELS["COM"], self.__class__.__name__.upper())

        def savemime(msg):
            """
            save contents of email as separate files.
            is a nested function.
            3x filtering:
             - allowlist of multipart-contenttype
             - allowlist of body-contentmajor
             - blocklist of body-contentytpe
            """
            # count nr of valid 'attachments'
            nrmimesaved = 0
            contenttype = msg.get_content_type()
            if msg.is_multipart():
                if contenttype in allowlist_multipart:
                    for part in msg.get_payload():
                        nrmimesaved += savemime(part)
            else:
                # is not a multipart
                if msg.get_content_maintype() not in allowlist_major \
                        or contenttype in blocklist_contenttype:
                    return 0
                content = msg.get_payload(decode=True)
                if not content or content.isspace():
                    return 0
                charset = msg.get_content_charset('ascii')
                content_disposition = msg.get_content_disposition()
                filename = msg.get_filename('body')
                if self.userscript and hasattr(self.userscript, 'accept_incoming_attachment'):
                    accept_attachment = botslib.runscript(
                        self.userscript,
                        self.scriptname,
                        'accept_incoming_attachment',
                        channeldict=self.channeldict,
                        ta=ta_from,
                        charset=charset,
                        content=content,
                        contenttype=contenttype,
                        content_disposition=content_disposition,
                        filename=filename,
                    )
                    if not accept_attachment:
                        return 0
                filesize = len(content)
                ta_file = ta_from.copyta(status=FILEIN)
                outfilename = str(ta_file.idta)
                with botslib.opendata_bin(outfilename, 'wb') as outfile:
                    outfile.write(content)
                nrmimesaved += 1
                ta_file.update(
                    statust=OK,
                    charset=charset,
                    contenttype=contenttype,
                    filename=outfilename,
                    filesize=filesize,
                    divtext=filename[:128],
                )
            return nrmimesaved

        # *****************end of nested function savemime***************************
        @botslib.log_session
        def mdnreceive():
            tmp = msg.get_param('reporttype')
            if tmp is None or email.utils.collapse_rfc2231_value(tmp) != 'disposition-notification':
                # invalid MDN
                raise CommunicationInError(_("Received email-MDN with errors."))
            for part in msg.get_payload():
                if part.get_content_type() == 'message/disposition-notification':
                    originalmessageid = part['original-message-id']
                    if originalmessageid is not None:
                        break
            else:
                # invalid MDN: 'message/disposition-notification' not in email
                raise CommunicationInError(_("Received email-MDN with errors."))
            botslib.changeq(
                """UPDATE ta
                   SET confirmed=%(confirmed)s, confirmidta=%(confirmidta)s
                   WHERE reference=%(reference)s
                   AND status=%(status)s
                   AND confirmasked=%(confirmasked)s
                   AND confirmtype=%(confirmtype)s
                """,
                {
                    'status': FILEOUT,
                    'reference': originalmessageid,
                    'confirmed': True,
                    'confirmtype': 'ask-email-MDN',
                    'confirmidta': ta_from.idta,
                    'confirmasked': True,
                },
            )
            # for now no checking if processing was OK.....
            # performance: not good. Index should be on the reference.

        @botslib.log_session
        def mdnsend(ta_from):
            if not botslib.checkconfirmrules(
                    'send-email-MDN',
                    idroute=self.idroute,
                    idchannel=self.channeldict['idchannel'],
                    frompartner=frompartner,
                    topartner=topartner,
            ):
                return 0  # do not send
            # make message
            message = email.message.Message()
            message.add_header('From', tomail)
            dispositionnotificationto = email.utils.parseaddr(msg['disposition-notification-to'])[1]
            message.add_header('To', dispositionnotificationto)
            message.add_header('Subject', 'Return Receipt (displayed) - ' + subject)
            message.add_header('MIME-Version', '1.0')
            message.add_header(
                'Content-Type', 'multipart/report', reporttype='disposition-notification'
            )
            # ~ message.set_type('multipart/report')
            # ~ message.set_param('reporttype','disposition-notification')

            # make human readable message
            humanmessage = email.message.Message()
            humanmessage.add_header('Content-Type', 'text/plain')
            humanmessage.set_payload(
                'This is an return receipt for the mail that you send to ' + tomail
            )
            message.attach(humanmessage)

            # make machine readable message
            machinemessage = email.message.Message()
            machinemessage.add_header('Content-Type', 'message/disposition-notification')
            machinemessage.add_header('Original-Message-ID', reference)
            nep = email.message.Message()
            machinemessage.attach(nep)
            message.attach(machinemessage)

            # write email to file;
            # new transaction for group-file
            ta_mdn = botslib.NewTransaction(status=MERGED)

            if botsglobal.ini.getboolean('acceptance', 'runacceptancetest', False):
                mdn_reference = '123message-ID email should be unique123'
                mdn_datetime = email.utils.formatdate(
                    timeval=time.mktime(time.strptime('2013-01-23 01:23:45', '%Y-%m-%d %H:%M:%S')),
                    localtime=True,
                )
            else:
                # we first have to get the mda-ta to make this reference
                mdn_reference = email.utils.make_msgid(str(ta_mdn.idta))
                mdn_datetime = email.utils.formatdate(localtime=True)
            message.add_header('Date', mdn_datetime)
            message.add_header('Message-ID', mdn_reference)
            mdnfilename = str(ta_mdn.idta)
            with botslib.opendata_bin(mdnfilename, 'wb') as mdnfile:
                generator = email.generator.BytesGenerator(
                    mdnfile, mangle_from_=False, maxheaderlen=78,
                    policy=email.policy.SMTP,
                )
                generator.flatten(message, unixfrom=False)
            ta_mdn.update(
                statust=OK,
                idroute=self.idroute,
                filename=mdnfilename,
                editype='email-confirmation',
                frompartner=topartner,
                topartner=frompartner,
                frommail=tomail,
                tomail=dispositionnotificationto,
                reference=mdn_reference,
                content='multipart/report',
                fromchannel=self.channeldict['idchannel'],
                charset='ascii',
                parent=ta_from.idta,
            )
            return ta_mdn.idta

        # *****************end of nested function dispositionnotification***************************
        # get received mails for channel
        for row in botslib.query(
                """SELECT idta,filename
                   FROM ta
                   WHERE idta>%(rootidta)s
                   AND status=%(status)s
                   AND statust=%(statust)s
                   AND fromchannel=%(fromchannel)s
                """,
                {
                    'status': FILEIN,
                    'statust': OK,
                    'rootidta': self.rootidta,
                    'fromchannel': self.channeldict['idchannel'],
                    'idroute': self.idroute,
                }):
            try:
                # default values for sending MDN; used to update ta if MDN is not asked
                confirmtype = ''
                confirmed = False
                confirmasked = False
                confirmidta = 0

                # read & parse email
                ta_from = botslib.OldTransaction(row["idta"])
                with botslib.opendata_bin(row["filename"], "rb") as infile:
                    # read and parse mail
                    msg = email.message_from_binary_file(infile)

                # ******get information from email (sender, receiver etc)*************************
                reference = self.checkheaderforcharset(msg['message-id']) or ''
                botsglobal.logger.log(LOG_LEVELS["COM"], "Email received: %s", reference)
                subject = self.checkheaderforcharset(msg['subject']) or ''
                botsglobal.logger.log(LOG_LEVELS["COM"], "Subject: %s", subject)
                contenttype = self.checkheaderforcharset(msg.get_content_type())

                # frompartner
                frommail = self.checkheaderforcharset(email.utils.parseaddr(msg['from'])[1])
                botsglobal.logger.log(LOG_LEVELS["COM"], 'From: "%s"', frommail)
                frompartner = ''
                if not self.channeldict['starttls']:
                    # authorise frompartner or skip authorisation.
                    # starttls in channeldict is: 'no check on "from:" email adress'
                    frompartner = self.mailaddress2idpartner(frommail)
                    if frompartner is None:
                        raise CommunicationInError(
                            _(
                                '"From" emailaddress(es) %(email)s not authorised/unknown'
                                ' for channel "%(idchannel)s".'
                            ),
                            {'email': frommail, 'idchannel': self.channeldict['idchannel']},
                        )
                    botsglobal.logger.log(LOG_LEVELS['COM'], 'frompartner: "%s"', frompartner)

                # topartner, cc
                list_to_address = [
                    self.checkheaderforcharset(address)
                    for name_not_used_variable, address in email.utils.getaddresses(
                        msg.get_all('to', [])
                    )
                ]
                list_cc_address = [
                    self.checkheaderforcharset(address)
                    for name_not_used_variable, address in email.utils.getaddresses(
                        msg.get_all('cc', [])
                    )
                ]
                # in cc field goes complete list of addresses.
                cc_content = ','.join(address for address in list_to_address + list_cc_address)
                if not self.channeldict['apop']:
                    # authorise topartner or skip authorisation. 'apop' in channeldict is:
                    #   'no check on "to:" email adress'
                    for address in list_to_address:
                        # all tos-addresses are checked;
                        # only one needs to be authorised.
                        topartner = self.mailaddress2idpartner(address)
                        tomail = address
                        if topartner is not None:
                            # topartner found: break out of loop
                            break
                    else:
                        # no valid topartner: generate error
                        raise CommunicationInError(
                            _(
                                '"To" emailaddress(es) %(email)s not authorised/unknown'
                                ' for channel "%(idchannel)s".'
                            ),
                            {'email': list_to_address, 'idchannel': self.channeldict['idchannel']},
                        )
                    botsglobal.logger.log(LOG_LEVELS['COM'], 'topartner: %s', topartner)
                else:
                    topartner = ''
                    tomail = list_to_address[0] if list_to_address else ''

                botsglobal.logger.log(LOG_LEVELS["COM"], 'To: "%s"', tomail)

                # update transaction of mail with information found in mail
                # why save now not later:
                #   when saving the attachments need the mail-header-info to be in ta (copyta)
                ta_from.update(
                    frommail=frommail,
                    tomail=tomail,
                    reference=reference[:256],  # 20220131  for now field 'reference' is max 256
                    contenttype=contenttype,
                    frompartner=frompartner,
                    topartner=topartner,
                    cc=cc_content,
                    rsrv1=subject[:128],
                )
                if contenttype == 'multipart/report':
                    # process received MDN confirmation
                    mdnreceive()
                else:
                    if 'disposition-notification-to' in msg:
                        # sender requests a MDN
                        confirmidta = mdnsend(ta_from)
                        if confirmidta:
                            confirmtype = 'send-email-MDN'
                            confirmed = True
                            confirmasked = True
                    nrmimesaved = savemime(msg)
                    if not nrmimesaved:
                        raise CommunicationInError(
                            _('No valid attachment in received email')
                        )
            except Exception:
                txt = txtexc()
                ta_from.update(statust=ERROR, errortext=txt)
                ta_from.deletechildren()
            else:
                ta_from.update(
                    statust=DONE,
                    confirmtype=confirmtype,
                    confirmed=confirmed,
                    confirmasked=confirmasked,
                    confirmidta=confirmidta,
                )

    @staticmethod
    def checkheaderforcharset(org_header):
        """correct handling of charset for email headers that are saved in database."""
        # for subjects with non-ascii content special notation exists in MIME-standard
        header, encoding = email.header.decode_header(org_header)[0]
        try:
            if encoding is not None:
                # decode (to unicode)
                return header.decode(encoding)
            # test if valid; use case: spam...
            # need to test because database-storage will give errors otherwise.
            header.encode('utf8')
            return header
        except Exception as exc:
            raise CommunicationInError(
                _('Email header invalid - probably issues with characterset.')
            ) from exc

    def mailaddress2idpartner(self, mailaddress):
        """lookup email address to see if know in configuration."""
        mailaddress_lower = mailaddress.lower()
        # first check in chanpar email-addresses for this channel
        for row in botslib.query(
                """SELECT chanpar.idpartner_id as idpartner
                   FROM chanpar,channel,partner
                   WHERE chanpar.idchannel_id=channel.idchannel
                   AND chanpar.idpartner_id=partner.idpartner
                   AND partner.active=%(active)s
                   AND chanpar.idchannel_id=%(idchannel)s
                   AND LOWER(chanpar.mail)=%(mail)s""",
                {
                    'active': True, 'idchannel': self.channeldict['idchannel'],
                    'mail': mailaddress_lower
                }):
            return row["idpartner"]
        # if not found, check in partner-tabel (is less specific).
        for row in botslib.query(
                """SELECT idpartner
                   FROM partner
                   WHERE active=%(active)s
                   AND LOWER(mail) = %(mail)s """,
                {'active': True, 'mail': mailaddress_lower}):
            return row["idpartner"]
        # indicate email address is unknown
        return None

    def idpartner2mailaddress(self, idpartner):
        for row in botslib.query(
                """SELECT chanpar.mail as mail,chanpar.cc as cc
                   FROM chanpar,channel,partner
                   WHERE chanpar.idchannel_id=channel.idchannel
                   AND chanpar.idpartner_id=partner.idpartner
                   AND partner.active=%(active)s
                   AND chanpar.idchannel_id=%(idchannel)s
                   AND chanpar.idpartner_id=%(idpartner)s""",
                {
                    'active': True,
                    'idchannel': self.channeldict['idchannel'],
                    'idpartner': idpartner},
                ):
            if row["mail"]:
                return row["mail"], row["cc"]
        for row in botslib.query(
                """SELECT mail,cc
                   FROM partner
                   WHERE active=%(active)s
                   AND idpartner=%(idpartner)s""",
                {'active': True, 'idpartner': idpartner}):
            if row["mail"]:
                return row["mail"], row["cc"]
        raise CommunicationOutError(
            _('No mail-address for partner "%(partner)s" (channel "%(idchannel)s").'),
            {'partner': idpartner, 'idchannel': self.channeldict['idchannel']},
        )

    def connect(self):
        pass

    def disconnect(self):
        pass

    @staticmethod
    def convertcodecformime(codec_in):
        convertdict = {
            'ascii': 'us-ascii',
            'unoa': 'us-ascii',
            'unob': 'us-ascii',
            'unoc': 'iso-8859-1',
        }
        codec_in = codec_in.lower().replace('_', '-')
        return convertdict.get(codec_in, codec_in)

    def filename_formatter(self, filename_mask, ta, runuserscript=True):
        """
        Output filename generation from template filename configured in the channel
        Basically python's string.Formatter is used; see http://docs.python.org/library/string.html
        As in string.Formatter, substitution values are surrounded by braces;
        format specifiers can be used.
        Any ta value can be used
          eg. {botskey}, {alt}, {editype}, {messagetype}, {topartner}
        Next to the value in ta you can use:
         - * : an unique number (per outchannel) using an asterisk; since bots3.3: {unique}
         - {datetime}  use datetime with a valid strftime format:
           eg. {datetime:%Y%m%d}, {datetime:%H%M%S}
         - {infile} use the original incoming filename; use name and extension,
           or either part separately:
           eg. {infile}, {infile:name}, {infile:ext}
         - {overwrite}  if file wit hfielname exists: overwrite it (instead of appending)

        Exampels of usage:
         - use incoming order number, add unique number, use extension '.idoc'
           {botskey}_{unique}.idoc
         - passthrough incoming filename & extension, prepend with unique number
           {unique}_{infile}
         - passthrough incoming filename, add unique number but change extension to .txt
           {infile:name}_{unique}.txt
         - use editype, messagetype, date and unique number with extension from the incoming file
           {editype}-{messagetype}-{datetime:%Y%m%d}-{unique}.{infile:ext}
         - Usage of subdirectories in the filename, they must already exist. In the example:
           {topartner}/{messagetype}/{unique}.edi
         - sort into folders by partner and messagetype.

        Note1: {botskey} can only be used if merge is False for that messagetype
        """

        class infilestr(str):
            """class for the {infile} parameter """

            def __format__(self, format_spec):
                if not format_spec:
                    return str(self)
                name, ext = os.path.splitext(str(self))
                if format_spec == 'ext':
                    return ext[1:] if ext.startswith('.') else ext
                if format_spec == 'name':
                    return name
                raise CommunicationOutError(
                    _('Error in format of "{filename}": unknown format: "%(format)s".'),
                    {'format': format_spec},
                )

        # handling of the 'unique' part in the filename
        # this was astriks ('*') in bots<-3.2, is now {unique}.
        # Reason for change: more options in format via python formatstrings
        # old way (asteriks) will keep working
        # create unique part for attachment-filename; stoe in ta-obejct so is assesible for {unique}
        ta.unique = str(botslib.unique(self.channeldict["idchannel"]))
        # replace 'old' way of making filenames unique by new way.
        tofilename = filename_mask.replace('*', '{unique}')
        ta.synall()
        if '{infile' in tofilename:
            ta_list = botslib.trace_origin(ta=ta, where={'status': EXTERNIN})
            if ta_list:
                ta.infile = ta.infilename = infilestr(os.path.basename(ta_list[-1].filename))
            else:
                ta.infilename = ''
        if '{datetime' in tofilename:
            ta.datetime = datetime.datetime.now()
            if botsglobal.ini.getboolean('acceptance', 'runacceptancetest', False):
                ta.datetime = datetime.datetime.strptime('2013-01-23 01:23:45', '%Y-%m-%d %H:%M:%S')
        try:
            # do the actual formatting
            tofilename = tofilename.format(**ta.__dict__)
        except Exception as exc:
            txt = txtexc()
            raise CommunicationOutError(
                _('Error in formatting outgoing filename "%(filename)s". Error: "%(error)s".'),
                {'filename': tofilename, 'error': txt},
            ) from exc
        if runuserscript and self.userscript and hasattr(self.userscript, 'filename'):
            return botslib.runscript(
                self.userscript,
                self.scriptname,
                'filename',
                channeldict=self.channeldict,
                filename=tofilename,
                ta=ta,
            )
        return tofilename


class file(_comsession):
    def connect(self):
        """
        directory locking: create lock-file.
        If the lockfile is already present an exception is raised.
        """
        if self.channeldict['lockname']:
            self.lockname = botslib.join(self.channeldict['path'], self.channeldict['lockname'])
            lock = os.open(self.lockname, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            os.close(lock)

    @botslib.log_session
    def incommunicate(self):
        """gets files from filesystem."""
        frompath = botslib.join(self.channeldict['path'], self.channeldict['filename'])
        filelist = sorted(filename for filename in glob.iglob(frompath) if os.path.isfile(filename))
        startdatetime = datetime.datetime.now()
        remove_ta = False
        for fromfilename in filelist:
            try:
                ta_from = botslib.NewTransaction(
                    filename=fromfilename,
                    status=EXTERNIN,
                    fromchannel=self.channeldict['idchannel'],
                    idroute=self.idroute,
                )
                ta_to = ta_from.copyta(status=FILEIN)
                remove_ta = True
                # open fromfile, syslock if indicated
                with open(fromfilename, "rb") as fromfile:
                    filesize = os.fstat(fromfile.fileno()).st_size
                    if self.channeldict["syslock"]:
                        if os.name == "nt":
                            msvcrt.locking(fromfile.fileno(), msvcrt.LK_LOCK, 0x0fffffff)
                        elif os.name == "posix":
                            fcntl.lockf(fromfile.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
                        else:
                            raise LockedFileError(_("Can not do a systemlock on this platform"))
                    # open tofile
                    tofilename = str(ta_to.idta)
                    with botslib.opendata_bin(tofilename, "wb") as tofile:
                        # copy
                        shutil.copyfileobj(fromfile, tofile, 1048576)
            except Exception:
                txt = txtexc()
                botslib.ErrorProcess(
                    functionname='file-incommunicate', errortext=txt, channeldict=self.channeldict
                )
                if remove_ta:
                    try:
                        ta_from.delete()
                        ta_to.delete()
                    except Exception:
                        pass
            else:
                ta_to.update(filename=tofilename, statust=OK, filesize=filesize)
                ta_from.update(statust=DONE)
                if self.channeldict['remove']:
                    os.remove(fromfilename)
            finally:
                remove_ta = False
            if (datetime.datetime.now() - startdatetime).seconds >= self.maxsecondsperchannel:
                break

    @botslib.log_session
    def outcommunicate(self):
        """
        does output of files to filesystem. To be used via send-dispatcher.
        Output is either:
        1.  outputfile, messages are appended; filename is a fixed name
        2.  to directory; new file for each db-ta; if file exits: overwrite.
            File has to have a unique name.
        """
        # check if output dir exists, else create it.
        outputdir = botslib.join(self.channeldict['path'])
        botslib.dirshouldbethere(outputdir)
        # get right filename_mask & determine if fixed name (append) or files with unique names
        filename_mask = self.channeldict['filename'] if self.channeldict['filename'] else '*'
        if '{overwrite}' in filename_mask:
            filename_mask = filename_mask.replace('{overwrite}', '')
            mode = 'wb'
        else:
            mode = 'ab'
        # select the db-ta's for this channel
        for row in botslib.query(
                """SELECT idta,filename,numberofresends
                   FROM ta
                   WHERE idta>%(rootidta)s
                   AND status=%(status)s
                   AND statust=%(statust)s
                   AND tochannel=%(tochannel)s
                   ORDER BY idta
                """,
                {
                    'tochannel': self.channeldict['idchannel'],
                    'rootidta': self.rootidta,
                    'status': FILEOUT,
                    'statust': OK,
                }):
            ta_to = None
            try:
                # for each db-ta:
                ta_from = botslib.OldTransaction(row["idta"])
                ta_to = ta_from.copyta(status=EXTERNOUT)
                # open tofile, incl syslock if indicated
                tofilename = self.filename_formatter(filename_mask, ta_from)
                tofilename = botslib.join(outputdir, tofilename)
                with open(tofilename, mode) as tofile:
                    if self.channeldict["syslock"]:
                        if os.name == "nt":
                            msvcrt.locking(tofile.fileno(), msvcrt.LK_LOCK, 0x0fffffff)
                        elif os.name == "posix":
                            fcntl.lockf(tofile.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        else:
                            raise LockedFileError(_("Can not do a systemlock on this platform"))
                    # open fromfile
                    with botslib.opendata_bin(row["filename"], "rb") as fromfile:
                        # copy
                        shutil.copyfileobj(fromfile, tofile, 1048576)
                # Rename filename after writing file.
                # Function: safe file writing: do not want another process
                # to read the file while it is being written.
                # This is safe because file rename is atomic within same file system
                # (?what about network shares?)
                if self.channeldict['mdnchannel']:
                    tofilename_old = tofilename
                    tofilename = botslib.rreplace(tofilename_old, self.channeldict['mdnchannel'])
                    os.rename(tofilename_old, tofilename)
            except Exception:
                txt = txtexc()
                if ta_to:
                    ta_to.update(
                        statust=ERROR, errortext=txt, numberofresends=row["numberofresends"] + 1
                    )
                else:
                    botsglobal.logger.critical("file-outcommunicate: %s", txt)
            else:
                ta_to.update(
                    statust=DONE,
                    filename=tofilename,
                    numberofresends=row["numberofresends"] + 1,
                )
            finally:
                ta_from.update(statust=DONE)

    def disconnect(self):
        """delete directory-lockfile"""
        if self.channeldict['lockname']:
            os.remove(self.lockname)


class pop3(_comsession):

    def _connect(self):
        """pop3 session"""
        # pylint: disable=import-outside-toplevel
        import poplib

        # there has to be 'some' limit. This is 10Mb *outlook.com, hotmail.
        poplib._MAXLINE = MAXLINE  # pylint: disable=protected-access
        self.poplib = poplib  # pylint: disable=attribute-defined-outside-init

        # if used, gives information about session (on screen), for debugging pop3
        if self.debug is None:
            self.debug = botsglobal.ini.getint("settings", "pop3debug", 0)

    def connect(self):
        """Init pop3 session"""
        self._connect()
        self.session = self.poplib.POP3(
            host=self.channeldict['host'], port=int(self.channeldict['port'])
        )
        self.session.set_debuglevel(self.debug)
        self.session.user(self.channeldict['username'])
        self.session.pass_(self.channeldict['secret'])

    @botslib.log_session
    def incommunicate(self):
        """
        Fetch messages from Pop3-mailbox.
        A bad connection is tricky, because mails are actually only deleted
        on the server when QUIT is successful.
        A solution would be to connect, fetch, delete and quit for each mail,
        but this might introduce other problems.
        So: keep a list of idta received OK.
        If QUIT is not successful than delete these ta's
        """
        self.listoftamarkedfordelete = []
        # get list of messages #alt: (response, messagelist, octets) = popsession.list()
        maillist = self.session.list()[1]
        startdatetime = datetime.datetime.now()
        remove_ta = False
        for mail in maillist:
            try:
                ta_from = botslib.NewTransaction(
                    filename=f"pop3://{self.channeldict['username']}@{self.channeldict['host']}",
                    status=EXTERNIN,
                    fromchannel=self.channeldict['idchannel'],
                    idroute=self.idroute,
                )
                ta_to = ta_from.copyta(status=FILEIN)
                remove_ta = True
                tofilename = str(ta_to.idta)
                # first 'word' is the message number/ID
                mailid = int(mail.split()[0])
                # alt: (header, messagelines, octets) = popsession.retr(messageID)
                maillines = self.session.retr(mailid)[1]
                content = b'\n'.join(maillines)
                filesize = len(content)
                with botslib.opendata_bin(tofilename, 'wb') as tofile:
                    tofile.write(content)
                if self.channeldict['remove']:
                    # on server side mail is marked to be deleted.
                    # The pop3-server will actually delete the file if the QUIT commnd is receieved!
                    self.session.dele(mailid)
                    # add idta's of received mail in a list.
                    # If connection is not OK, QUIT command to POP3 server will not work.
                    # deleted mail will still be on server.
                    self.listoftamarkedfordelete += [ta_from.idta, ta_to.idta]
            except Exception:
                # something went wrong for this mail.
                txt = txtexc()
                botslib.ErrorProcess(
                    functionname='pop3-incommunicate', errortext=txt, channeldict=self.channeldict
                )
                if remove_ta:
                    try:
                        ta_from.delete()
                        ta_to.delete()
                    except Exception:
                        pass
                # test connection. if connection is not OK stop fetching mails.
                try:
                    self.session.noop()
                except Exception:
                    # indicate session is not valid anymore
                    self.session = None
                    break
            else:
                ta_to.update(statust=OK, filename=tofilename, filesize=filesize)
                ta_from.update(statust=DONE)
            finally:
                remove_ta = False
            if (datetime.datetime.now() - startdatetime).seconds >= self.maxsecondsperchannel:
                break

    def disconnect(self):
        """disconnect"""
        # pylint: disable=broad-exception-caught
        try:
            self.stderr2log_release()
            if not self.session:
                raise CommunicationError(_("Pop3 connection not OK"))
            # pop3 server will now actually delete the mails
            resp = self.session.quit()
            if not resp.startswith(b'+'):
                raise CommunicationError(_("QUIT command to POP3 server failed"))
        except (CommunicationError, Exception):
            # connection is gone. Delete everything that is received to avoid double receiving.
            botslib.ErrorProcess(
                functionname='pop3-incommunicate',
                errortext='Could not fetch emails via POP3; probably communication problems',
                channeldict=self.channeldict,
            )
            for idta in self.listoftamarkedfordelete:
                ta = botslib.OldTransaction(idta)
                ta.delete()

    @botslib.log_session
    def postcommunicate(self):
        self.mime2file()


class pop3s(pop3):

    def connect(self):
        """Init pop3 session"""
        self._connect()
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        if self.channeldict.get("keyfile") and self.channeldict.get("certfile"):
            context.load_cert_chain(
                keyfile=self.channeldict["keyfile"],
                certfile=self.channeldict["certfile"],
            )
        elif self.channeldict.get("certfile"):
            # self-signed server certificate
            context.load_verify_locations(self.channeldict["certfile"])
        self.session = self.poplib.POP3_SSL(
            host=self.channeldict['host'],
            port=int(self.channeldict['port']),
            context=context,
        )
        self.session.set_debuglevel(self.debug)
        self.session.user(self.channeldict['username'])
        self.session.pass_(self.channeldict['secret'])


class pop3apop(pop3):

    def connect(self):
        """Init pop3 session"""
        self._connect()
        self.session = self.poplib.POP3(
            host=self.channeldict['host'], port=int(self.channeldict['port'])
        )
        self.session.set_debuglevel(self.debug)
        # python handles apop password encryption
        self.session.apop(self.channeldict['username'], self.channeldict['secret'])


class imap4(_comsession):
    """Fetch email from IMAP server."""

    def _connect(self):
        """imap4 session"""
        # if used, gives information about session (on screen), for debugging imap4
        if self.debug is None:
            self.debug = botsglobal.ini.getint("settings", "imap4debug", 0)
        self.stderr2log()

    def connect(self):
        """Init imap4 session"""
        # pylint: disable=import-outside-toplevel
        import imaplib

        self._connect()
        imaplib.Debug = self.debug
        self.session = imaplib.IMAP4(
            host=self.channeldict['host'], port=int(self.channeldict['port'])
        )
        self.session.login(self.channeldict['username'], self.channeldict['secret'])

    @botslib.log_session
    def incommunicate(self):
        """Fetch messages from imap4-mailbox."""

        # path may contain a mailbox name, otherwise use INBOX
        mailbox_name = self.channeldict.get('path') or 'INBOX'
        botsglobal.logger.log(LOG_LEVELS['COM'], 'Fetching mail(s) in: %s', mailbox_name)

        response, data = self.session.select(mailbox_name)
        if response != 'OK':
            # eg. mailbox does not exist
            raise CommunicationInError(mailbox_name + ": " + data[0].decode())

        # Get the message UIDs that should be read
        response, data = self.session.uid('search', None, '(UNDELETED)')
        if response != 'OK':
            # have never seen this happen, but just in case!
            raise CommunicationInError(mailbox_name + ": " + data[0].decode())

        maillist = data[0].split()
        startdatetime = datetime.datetime.now()
        remove_ta = False
        for mail in maillist:
            try:
                ta_from = botslib.NewTransaction(
                    filename=f"imap4://{self.channeldict['username']}@{self.channeldict['host']}",
                    status=EXTERNIN,
                    fromchannel=self.channeldict['idchannel'],
                    idroute=self.idroute,
                )
                ta_to = ta_from.copyta(status=FILEIN)
                remove_ta = True
                filename = str(ta_to.idta)
                # Get the message (header and body)
                response, msg_data = self.session.uid('fetch', mail, '(RFC822)')
                filesize = len(msg_data[0][1])
                with botslib.opendata_bin(filename, 'wb') as filehandler:
                    filehandler.write(msg_data[0][1])
                # Flag message for deletion AND expunge.
                # Direct expunge has advantages for bad (internet)connections.
            except Exception:
                txt = txtexc()
                botslib.ErrorProcess(
                    functionname='imap4-incommunicate', errortext=txt, channeldict=self.channeldict
                )
                if remove_ta:
                    try:
                        ta_from.delete()
                        ta_to.delete()
                    except Exception:
                        pass
            else:
                ta_to.update(statust=OK, filename=filename, filesize=filesize)
                ta_from.update(statust=DONE)
                if self.channeldict['remove']:
                    self.session.uid('store', mail, '+FLAGS', r'(\Deleted)')
                    self.session.expunge()
            finally:
                remove_ta = False
            if (datetime.datetime.now() - startdatetime).seconds >= self.maxsecondsperchannel:
                break

        # Close currently selected mailbox. This is the recommended command before 'LOGOUT'.
        self.session.close()

    @botslib.log_session
    def postcommunicate(self):
        self.mime2file()

    def disconnect(self):
        self.session.logout()
        self.stderr2log_release()


class imap4s(imap4):

    def connect(self):
        """Init imap4 session"""
        # pylint: disable=import-outside-toplevel
        import imaplib

        self._connect()
        imaplib.Debug = self.debug
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        if self.channeldict.get("keyfile") and self.channeldict.get("certfile"):
            context.load_cert_chain(
                keyfile=self.channeldict["keyfile"],
                certfile=self.channeldict["certfile"],
            )
        elif self.channeldict.get("certfile"):
            # self-signed server certificate
            context.load_verify_locations(self.channeldict["certfile"])
        self.session = imaplib.IMAP4_SSL(
            host=self.channeldict['host'],
            port=int(self.channeldict['port']),
            ssl_context=context,
        )
        self.session.login(self.channeldict['username'], self.channeldict['secret'])


class smtp(_comsession):

    @botslib.log_session
    def precommunicate(self):
        self.file2mime()

    def _connect(self):
        """smtp session"""
        if self.debug is None:
            self.debug = botsglobal.ini.getint("settings", "smtpdebug", 0)
        self.stderr2log()

    def connect(self):
        """Init smtp session"""
        self._connect()
        # make connection
        self.session = smtplib.SMTP(
            host=self.channeldict['host'], port=int(self.channeldict['port'])
        )
        # if used, gives information about session (on screen), for debugging smtp
        self.session.set_debuglevel(min(self.debug, 1))
        self.login()

    def login(self):
        if self.channeldict['username'] and self.channeldict['secret']:
            try:
                # error in python 2.6.4....user and password can not be unicode
                self.session.login(
                    str(self.channeldict['username']), str(self.channeldict['secret'])
                )
            except smtplib.SMTPAuthenticationError as exc:
                raise CommunicationOutError(
                    _('SMTP server did not accept user/password combination.')
                ) from exc
            except Exception as exc:
                txt = txtexc()
                raise CommunicationOutError(
                    _('SMTP login failed. Error:\n%(txt)s'), {'txt': txt}
                ) from exc

    @botslib.log_session
    def outcommunicate(self):
        """
        does smtp-session.
        SMTP does not allow rollback.
        So if the sending of a mail fails, other mails may have been send.
        """
        # send messages
        for row in botslib.query(
                """SELECT idta,filename,frommail,tomail,cc,numberofresends
                   FROM ta
                   WHERE idta>%(rootidta)s
                   AND status=%(status)s
                   AND statust=%(statust)s
                   AND tochannel=%(tochannel)s
                """,
                {
                    'status': FILEOUT,
                    'statust': OK,
                    'rootidta': self.rootidta,
                    'tochannel': self.channeldict['idchannel'],
                }):
            ta_to = None
            try:
                ta_from = botslib.OldTransaction(row["idta"])
                ta_to = ta_from.copyta(status=EXTERNOUT)
                addresslist = row["tomail"].split(",") + row["cc"].split(",")
                addresslist = [x.strip() for x in addresslist if x.strip()]
                with botslib.opendata_bin(row["filename"], "rb") as sendfile:
                    msg = sendfile.read()
                self.session.sendmail(row["frommail"], addresslist, msg)
            except Exception:
                txt = txtexc()
                if ta_to:
                    ta_to.update(
                        statust=ERROR,
                        errortext=txt,
                        filename=f"smtp://{self.channeldict['username']}@{self.channeldict['host']}",
                        numberofresends=row["numberofresends"] + 1,
                    )
                else:
                    botsglobal.logger.critical("smtp-outcommunicate: %s", txt)
            else:
                ta_to.update(
                    statust=DONE,
                    filename=f"smtp://{self.channeldict['username']}@{self.channeldict['host']}",
                    numberofresends=row["numberofresends"] + 1,
                )
            finally:
                ta_from.update(statust=DONE)

    def disconnect(self):
        try:
            # Google gives/gave error closing connection. Not a real problem.
            self.session.quit()
        except ssl.SSLError:
            # for a starttls connection
            self.session.close()
        except Exception:
            pass
        self.stderr2log_release()


class smtps(smtp):

    def connect(self):
        """Init smpts connection"""
        self._connect()
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        if self.channeldict.get("keyfile") and self.channeldict.get("certfile"):
            context.load_cert_chain(
                keyfile=self.channeldict["keyfile"],
                certfile=self.channeldict["certfile"],
            )
        elif self.channeldict.get("certfile"):
            # self-signed server certificate
            context.load_verify_locations(self.channeldict["certfile"])
        self.session = smtplib.SMTP_SSL(
            host=self.channeldict['host'],
            port=int(self.channeldict['port']),
            context=context,
        )
        # if used, gives information about session (on screen), for debugging smtp
        self.session.set_debuglevel(self.debug)
        self.login()


class smtpstarttls(smtp):

    def connect(self):
        """Init smptttls connection"""
        self._connect()
        self.session = smtplib.SMTP(
            host=self.channeldict['host'], port=int(self.channeldict['port'])
        )
        # if used, gives information about session (on screen), for debugging smtp
        self.session.set_debuglevel(self.debug)
        self.session.ehlo()
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        if self.channeldict.get("keyfile") and self.channeldict.get("certfile"):
            context.load_cert_chain(
                keyfile=self.channeldict["keyfile"],
                certfile=self.channeldict["certfile"],
            )
        elif self.channeldict.get("certfile"):
            # self-signed server certificate
            context.load_verify_locations(self.channeldict["certfile"])
        self.session.starttls(context=context)
        self.session.ehlo()
        self.login()


class mimefile(file):

    @botslib.log_session
    def postcommunicate(self):
        self.mime2file()

    @botslib.log_session
    def precommunicate(self):
        self.file2mime()


class ftp(_comsession):

    def _connect(self):
        """ftp session"""
        if self.debug is None:
            self.debug = botsglobal.ini.getint("settings", "ftpdebug", 0)
        self.stderr2log()
        botslib.settimeout(botsglobal.ini.getint("settings", "ftptimeout", 10))

    def connect(self):
        """Init ftp session"""
        self._connect()
        self.session = ftplib.FTP()
        # set debug level (0=no, 1=medium, 2=full debug)
        self.session.set_debuglevel(min(self.debug, 2))
        # active or passive ftp
        self.session.set_pasv(not self.channeldict['ftpactive'])
        self.session.connect(host=self.channeldict['host'], port=int(self.channeldict['port']))
        self.session.login(
            user=self.channeldict['username'],
            passwd=self.channeldict['secret'],
            acct=self.channeldict['ftpaccount'],
        )
        self.set_cwd()

    def set_cwd(self):
        self.dirpath = self.session.pwd()
        if self.channeldict['path']:
            self.dirpath = posixpath.normpath(
                posixpath.join(self.dirpath, self.channeldict['path'])
            )
            try:
                # set right path on ftp-server
                self.session.cwd(self.dirpath)
            except Exception:
                # set right path on ftp-server; no nested directories
                self.session.mkd(self.dirpath)
                # set right path on ftp-server
                self.session.cwd(self.dirpath)

    @botslib.log_session
    def incommunicate(self):
        """
        do ftp: receive files. To be used via receive-dispatcher.
        each to be imported file is transaction.
        each imported file is transaction.
        """

        def writeline_callback(line):
            """inline function to write to file for non-binary ftp"""
            tofile.write(line + '\n')

        startdatetime = datetime.datetime.now()
        files = []
        try:
            # some ftp servers give errors when directory is empty;
            # catch these errors here
            files = self.session.nlst()
        except (ftplib.error_perm, ftplib.error_temp) as exc:
            if str(exc)[:3] not in ["550", "450"]:
                raise

        lijst = fnmatch.filter(files, self.channeldict['filename'])
        remove_ta = False
        # fetch messages from ftp-server.
        for fromfilename in lijst:
            try:
                ta_from = botslib.NewTransaction(
                    filename='ftp:/' + posixpath.join(self.dirpath, fromfilename),
                    status=EXTERNIN,
                    fromchannel=self.channeldict['idchannel'],
                    idroute=self.idroute,
                )
                ta_to = ta_from.copyta(status=FILEIN)
                remove_ta = True
                tofilename = str(ta_to.idta)
                try:
                    if self.channeldict['ftpbinary']:
                        tofile = botslib.opendata_bin(tofilename, 'wb')
                        self.session.retrbinary('RETR ' + fromfilename, tofile.write)
                    else:
                        # python3 gives back a 'string'.
                        tofile = botslib.opendata(tofilename, "w", charset="latin-1")
                        self.session.retrlines('RETR ' + fromfilename, writeline_callback)
                except ftplib.error_perm as exc:
                    if str(exc)[:3] in ["550"]:
                        # we are trying to download a directory...
                        raise BotsError("To be catched") from exc
                    raise
                tofile.close()
                filesize = os.path.getsize(botslib.abspathdata(tofilename))
                if not filesize:
                    raise BotsError("To be catched; directory (or empty file)")
            except BotsError:
                # directory or empty file; handle exception but generate no error.
                if remove_ta:
                    try:
                        ta_from.delete()
                        ta_to.delete()
                    except Exception:
                        pass
            except Exception:
                txt = txtexc()
                botslib.ErrorProcess(
                    functionname='ftp-incommunicate', errortext=txt, channeldict=self.channeldict
                )
                if remove_ta:
                    try:
                        ta_from.delete()
                        ta_to.delete()
                    except Exception:
                        pass
            else:
                ta_to.update(filename=tofilename, statust=OK, filesize=filesize)
                ta_from.update(statust=DONE)
                if self.channeldict['remove']:
                    self.session.delete(fromfilename)
            finally:
                remove_ta = False
            if (datetime.datetime.now() - startdatetime).seconds >= self.maxsecondsperchannel:
                break

    @botslib.log_session
    def outcommunicate(self):
        """
        do ftp: send files. To be used via receive-dispatcher.
        each to be send file is transaction.
        each send file is transaction.
        NB: ftp command APPE should be supported by server
        """
        # get right filename_mask & determine if fixed name (append) or files with unique names
        filename_mask = self.channeldict['filename'] if self.channeldict['filename'] else '*'
        if '{overwrite}' in filename_mask:
            filename_mask = filename_mask.replace('{overwrite}', '')
            mode = 'STOR '
        else:
            mode = 'APPE '
        for row in botslib.query(
                """SELECT idta,filename,numberofresends
                   FROM ta
                   WHERE idta>%(rootidta)s
                   AND status=%(status)s
                   AND statust=%(statust)s
                   AND tochannel=%(tochannel)s
                   ORDER BY idta
                """,
                {
                    'tochannel': self.channeldict['idchannel'],
                    'rootidta': self.rootidta,
                    'status': FILEOUT,
                    'statust': OK,
                }):
            ta_to = None
            try:
                ta_from = botslib.OldTransaction(row["idta"])
                ta_to = ta_from.copyta(status=EXTERNOUT)
                tofilename = self.filename_formatter(filename_mask, ta_from)
                with botslib.opendata_bin(row["filename"], "rb") as fromfile:
                    if self.channeldict['ftpbinary']:
                        self.session.storbinary(mode + tofilename, fromfile)
                    else:
                        self.session.storlines(mode + tofilename, fromfile)
                # Rename filename after writing file.
                # Function: safe file writing:
                #   do not want another process to read the file while it is being written.
                if self.channeldict['mdnchannel']:
                    tofilename_old = tofilename
                    tofilename = botslib.rreplace(tofilename_old, self.channeldict['mdnchannel'])
                    self.session.rename(tofilename_old, tofilename)
            except Exception:
                txt = txtexc()
                if ta_to:
                    ta_to.update(
                        statust=ERROR,
                        errortext=txt,
                        filename="ftp:/" + posixpath.join(self.dirpath, tofilename),
                        numberofresends=row["numberofresends"] + 1,
                    )
                else:
                    botsglobal.logger.critical("ftp-outcommunicate: %s", txt)
            else:
                ta_to.update(
                    statust=DONE,
                    filename='ftp:/' + posixpath.join(self.dirpath, tofilename),
                    numberofresends=row["numberofresends"] + 1,
                )
            finally:
                ta_from.update(statust=DONE)

    def disconnect(self):
        try:
            self.session.quit()
        except Exception:
            self.session.close()
        botslib.settimeout(botsglobal.ini.getint('settings', 'globaltimeout', 10))
        self.stderr2log_release()


class ftps(ftp):
    """
    explicit ftps as defined in RFC 2228 and RFC 4217.
    standard port to connect to is as in normal FTP (port 21)
    ftps is supported by python >= 2.7
    """

    def connect(self):
        """Init ftps session"""
        self._connect()
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        if self.channeldict.get("keyfile") and self.channeldict.get("certfile"):
            context.load_cert_chain(
                keyfile=self.channeldict["keyfile"],
                certfile=self.channeldict["certfile"],
            )
        elif self.channeldict.get("certfile"):
            # self-signed server certificate
            context.load_verify_locations(self.channeldict["certfile"])
        self.session = ftplib.FTP_TLS(context=context)
        # set debug level (0=no, 1=medium, 2=full debug)
        self.session.set_debuglevel(min(self.debug, 2))
        # active or passive ftp
        self.session.set_pasv(not self.channeldict['ftpactive'])
        self.session.connect(
            host=self.channeldict["host"],
            port=int(self.channeldict["port"]),
        )
        self.session.auth()
        self.session.login(
            user=self.channeldict['username'],
            passwd=self.channeldict['secret'],
            acct=self.channeldict['ftpaccount'],
        )
        self.session.prot_p()
        self.set_cwd()


# sub classing of ftplib for ftpis
class Ftp_tls_implicit(ftplib.FTP_TLS):
    """
    FTPS implicit is not directly supported by python; python>=2.7 supports only ftps explicit.
    So class ftplib.FTP_TLS is sub-classed here, with the needed modifications.
    (code is nicked from ftplib.ftp v. 2.7; additions/changes are indicated)
    """
    # pylint: disable=too-many-instance-attributes

    def connect(self, host="", port=0, timeout=-999, source_address=None):
        if host != "":
            self.host = host
        if port > 0:
            self.port = port
        if timeout != -999:
            self.timeout = timeout
        if self.timeout is not None and not self.timeout:
            raise ValueError("Non-blocking socket (timeout=0) is not supported")
        if source_address is not None:
            self.source_address = source_address
        sys.audit("ftplib.connect", self, self.host, self.port)
        self.sock = socket.create_connection(
            (self.host, self.port),
            self.timeout,
            source_address=self.source_address,
        )
        self.af = self.sock.family
        self.sock = self.context.wrap_socket(self.sock)
        self.file = self.sock.makefile("r", encoding=self.encoding)
        self.welcome = self.getresp()
        return self.welcome

    def prot_p(self):
        # Inovis FTPIS gives errors on 'PBSZ 0' and 'PROT P',
        # vsftp does not work without these commands.
        # These errors are just catched, nothing is done with them.
        try:
            self.voidcmd("PBSZ 0")
        except ftplib.error_perm:
            pass
        try:
            resp = self.voidcmd("PROT P")
        except ftplib.error_perm:
            resp = None
        self._prot_p = True
        return resp


class ftpis(ftp):
    """
    FTPS implicit; is not defined in a RFC.
    standard port to connect is port 990.
    FTPS implicit is not supported by python.
    python>=2.7 supports ftps explicit.
    So used is the sub-class Ftp_tls_implicit.
    Tested with Inovis and VSFTPd.
    Python library FTP_TLS uses ssl_version = ssl.PROTOCOL_TLSv1
    Inovis seems to need PROTOCOL_SSLv3
    This is 'solved' by using 'parameters' in the channel.
    ~ ssl.PROTOCOL_SSLv2      = 0 (removed py >= 3.10)
    ~ ssl.PROTOCOL_SSLv3      = 1 (removed py >= 3.10)
    ~ ssl.PROTOCOL_SSLv23     = 2
    ~ ssl.PROTOCOL_TLS        = 2
    ~ ssl.PROTOCOL_TLSv1      = 3
    ~ ssl.PROTOCOL_TLSv1_1    = 4
    ~ ssl.PROTOCOL_TLSv1_2    = 5
    ~ ssl.PROTOCOL_TLS_CLIENT = 16
    ~ ssl.PROTOCOL_TLS_SERVER = 17
    """
    ssl_versions = [2, 3, 4, 5, 16, 17]

    def connect(self):
        """Init ftpis session"""
        self._connect()
        ssl_version = 2
        if self.channeldict["parameters"]:
            try:
                ssl_version = int(self.channeldict["parameters"])
                # Verify if ssl_version is valid
                if ssl_version not in self.ssl_versions:
                    raise ValueError(ssl_version)
            except ValueError:
                botsglobal.logger.warning(_("Invalid ssl_version set in channel parameter: '%s'"), ssl_version)
                botsglobal.logger.warning(_("Valid ssl_version values: %s"), self.ssl_versions)
                ssl_version = 2
        context = ssl.SSLContext(ssl_version)
        if self.debug:
            botsglobal.logger.log(LOG_LEVELS["COM"], "SSLContext protocol: %s", context.protocol)
        if self.channeldict.get("keyfile") and self.channeldict.get("certfile"):
            context.load_cert_chain(
                keyfile=self.channeldict["keyfile"],
                certfile=self.channeldict["certfile"],
            )
        elif self.channeldict.get("certfile"):
            # self-signed server certificate
            context.load_verify_locations(self.channeldict["certfile"])
        self.session = Ftp_tls_implicit(context=context)
        # set debug level (0=no, 1=medium, 2=full debug)
        self.session.set_debuglevel(min(self.debug, 2))
        # active or passive ftp
        self.session.set_pasv(not self.channeldict['ftpactive'])
        self.session.connect(host=self.channeldict['host'], port=int(self.channeldict['port']))
        # ~ self.session.auth()
        self.session.login(
            user=self.channeldict['username'],
            passwd=self.channeldict['secret'],
            acct=self.channeldict['ftpaccount'],
        )
        self.session.prot_p()
        self.set_cwd()


class sftp(_comsession):
    """
    SFTP: SSH File Transfer Protocol (SFTP is not FTP run over SSH,
    SFTP is not Simple File Transfer Protocol)
    standard port to connect to is port 22.
    requires paramiko library.
    based on class ftp and ftps above with code from demo_sftp.py which is included with paramiko
    """

    def connect(self):
        """
        Init sftp session
        """
        # pylint: disable=import-outside-toplevel
        # check dependencies
        try:
            import paramiko
        except Exception as exc:
            raise ImportError(
                _(
                    'Dependency failure: communicationtype "sftp"'
                    ' requires python library "paramiko".'
                )) from exc
        if paramiko.__version__ < '2.0':
            raise ImportError(
                'Dependency failure: communicationtype "sftp" requires python library'
                f' "paramiko" version 2.0 or higher (version {paramiko.__version__} installed)')

        # setup logging if required
        if self.debug is None:
            self.debug = botsglobal.ini.getint('settings', 'ftpdebug', 0) or None
        if self.debug is not None:
            # log_file = botslib.join(botsglobal.ini.get('directories', 'logging'), 'sftp.log')
            # paramiko.util.log_to_file(log_file, (5 - self.debug) * 10)
            logger = logging.getLogger('paramiko')
            # Convert debug level to logging level:
            # (0=nolog, 1=50=critical, 2=40=error, 3=30=warn, 4=20=info, 5=10=debug)
            if self.debug == 0:
                level = 0
            else:
                level = (6 - self.debug) * 10
            logger.setLevel(level)

            # Add bots logger handlers to paramiko logger handlers
            for handler in botsglobal.logger.handlers:
                logger.addHandler(handler)

        # Get hostname and port to use
        hostname = self.channeldict['host']
        try:
            port = int(self.channeldict['port'])
        except Exception:
            # default port for sftp
            port = 22

        # Server authentication: hostkey to validate a server's identity. only via user scripting
        hostkey = None
        if self.userscript and hasattr(self.userscript, 'hostkey'):
            hostkey = botslib.runscript(
                self.userscript, self.scriptname, 'hostkey', channeldict=self.channeldict)
        # Client identification
        # either:
        # 1 user-password
        # 2 user-privatekey
        # 2 user-encrypted privatekey --> passphrase is needed
        pkey = None
        # if password is empty string: use None, else error can occur.
        secret = self.channeldict['secret'] or None
        if self.userscript and hasattr(self.userscript, 'privatekey'):
            # via user scripting
            privatekeyfile, pkeytype, passphrase = botslib.runscript(
                self.userscript, self.scriptname, 'privatekey', channeldict=self.channeldict)
            if pkeytype == 'RSA':
                pkey = paramiko.RSAKey.from_private_key_file(
                    filename=privatekeyfile, password=passphrase)
            else:
                pkey = paramiko.DSSKey.from_private_key_file(
                    filename=privatekeyfile, password=passphrase)
        elif self.channeldict['keyfile']:
            # keyfile is indicated in channel.
            # for now: always RSAKey.
            pkey = paramiko.RSAKey.from_private_key_file(
                filename=self.channeldict['keyfile'], password=secret)
            # if keyfile, secret is used as passphrase.
            # So clear secret for login (assuming: if keyfile, no password is used)
            secret = None

        # connect and use paramiko Transport to negotiate SSH2 across the connection
        self.transport = paramiko.Transport((hostname, port))
        self.transport.connect(
            username=self.channeldict['username'], password=secret, hostkey=hostkey, pkey=pkey)
        self.session = paramiko.SFTPClient.from_transport(self.transport)
        channel = self.session.get_channel()
        channel.settimeout(botsglobal.ini.getint('settings', 'ftptimeout', 10))
        self.set_cwd()

    def set_cwd(self):
        self.session.chdir('.')
        # getcwd does not work without this chdir first!
        self.dirpath = self.session.getcwd()
        if self.channeldict['path']:
            self.dirpath = posixpath.normpath(
                posixpath.join(self.dirpath, self.channeldict['path']))
            try:
                self.session.chdir(self.dirpath)
            except Exception:
                self.session.mkdir(self.dirpath)
                self.session.chdir(self.dirpath)

    def disconnect(self):
        self.session.close()
        self.transport.close()
        if self.debug:
            logger = logging.getLogger('paramiko')
            logger.setLevel(0)
            # Remove bots logger handlers of paramiko logger handlers
            for handler in botsglobal.logger.handlers:
                if handler in logger.handlers:
                    logger.removeHandler(handler)

    @botslib.log_session
    def incommunicate(self):
        """
        do ftp: receive files. To be used via receive-dispatcher.
        each to be imported file is transaction.
        each imported file is transaction.
        """
        startdatetime = datetime.datetime.now()
        files = self.session.listdir('.')
        lijst = fnmatch.filter(files, self.channeldict['filename'])
        remove_ta = False
        for fromfilename in lijst:
            # fetch messages from sftp-server.
            try:
                ta_from = botslib.NewTransaction(
                    filename='sftp:/' + posixpath.join(self.dirpath, fromfilename),
                    status=EXTERNIN,
                    fromchannel=self.channeldict['idchannel'],
                    idroute=self.idroute,
                )
                ta_to = ta_from.copyta(status=FILEIN)
                remove_ta = True
                tofilename = str(ta_to.idta)
                # SSH treats all files as binary. paramiko doc says: b-flag is ignored
                with self.session.open(fromfilename, 'r') as fromfile:
                    content = fromfile.read()
                    filesize = len(content)
                    with botslib.opendata_bin(tofilename, 'wb') as tofile:
                        tofile.write(content)
            except Exception:
                txt = txtexc()
                botslib.ErrorProcess(
                    functionname='sftp-incommunicate', errortext=txt, channeldict=self.channeldict
                )
                if remove_ta:
                    try:
                        ta_from.delete()
                        ta_to.delete()
                    except Exception:
                        pass
            else:
                ta_to.update(filename=tofilename, statust=OK, filesize=filesize)
                ta_from.update(statust=DONE)
                if self.channeldict['remove']:
                    self.session.remove(fromfilename)
            finally:
                remove_ta = False
            if (datetime.datetime.now() - startdatetime).seconds >= self.maxsecondsperchannel:
                break

    @botslib.log_session
    def outcommunicate(self):
        """
        do ftp: send files. To be used via receive-dispatcher.
        each to be send file is transaction.
        each send file is transaction.
        """
        # get right filename_mask & determine if fixed name (append) or files with unique names
        filename_mask = self.channeldict['filename'] if self.channeldict['filename'] else '*'
        if '{overwrite}' in filename_mask:
            filename_mask = filename_mask.replace('{overwrite}', '')
            mode = 'w'
        else:
            mode = 'a'
        for row in botslib.query(
                """SELECT idta,filename,numberofresends
                   FROM ta
                   WHERE idta>%(rootidta)s
                   AND status=%(status)s
                   AND statust=%(statust)s
                   AND tochannel=%(tochannel)s
                   ORDER BY idta
                """,
                {
                    'tochannel': self.channeldict['idchannel'],
                    'rootidta': self.rootidta,
                    'status': FILEOUT,
                    'statust': OK,
                }):
            ta_to = None
            try:
                ta_from = botslib.OldTransaction(row["idta"])
                ta_to = ta_from.copyta(status=EXTERNOUT)
                tofilename = self.filename_formatter(filename_mask, ta_from)
                with botslib.opendata_bin(row["filename"], "rb") as fromfile:
                    # SSH treats all files as binary. paramiko doc says: b-flag is ignored
                    with self.session.open(tofilename, mode) as tofile:
                        tofile.write(fromfile.read())
                # Rename filename after writing file.
                # Function: safe file writing: do not want another process
                # to read the file while it is being written.
                if self.channeldict['mdnchannel']:
                    tofilename_old = tofilename
                    tofilename = botslib.rreplace(tofilename_old, self.channeldict['mdnchannel'])
                    self.session.rename(tofilename_old, tofilename)
            except Exception:
                txt = txtexc()
                if ta_to:
                    ta_to.update(
                        statust=ERROR,
                        errortext=txt,
                        filename="sftp:/" + posixpath.join(self.dirpath, tofilename),
                        numberofresends=row["numberofresends"] + 1,
                    )
                else:
                    botsglobal.logger.critical("sftp-outcommunicate: %s", txt)
            else:
                ta_to.update(
                    statust=DONE,
                    filename='sftp:/' + posixpath.join(self.dirpath, tofilename),
                    numberofresends=row["numberofresends"] + 1,
                )
            finally:
                ta_from.update(statust=DONE)


class xmlrpc(_comsession):
    """
    General xmlrpc implementation. Xmlrpc is often quite specific.
    Probably you will have to script your own xmlrpc class, but this is a good starting point.
    From channel is used: usernaem, secret, host, port, path.
    Path is the function to be used/called.
    """

    def connect(self):
        """
        Init xmlrpc session
        """
        # pylint: disable=import-outside-toplevel
        import xmlrpc.client as xmlrpclib
        import defusedxml.xmlrpc

        # security patch of xmlrpc lib
        defusedxml.xmlrpc.monkey_patch()

        uri = "http://{username}{secret}@{host}:{port}".format_map(self.channeldict)
        # used as 'filename' in reports etc
        self.filename = "http://{username}@{host}:{port}".format_map(self.channeldict)
        session = xmlrpclib.ServerProxy(uri)
        # self.xmlrpc_call is called in communication
        self.xmlrpc_call = getattr(session, self.channeldict['path'])

    @botslib.log_session
    def incommunicate(self):
        startdatetime = datetime.datetime.now()
        remove_ta = False
        while True:
            try:
                content = self.xmlrpc_call()
                if content is None:
                    # nothing (more) to receive.
                    break
                ta_from = botslib.NewTransaction(
                    filename=self.filename,
                    status=EXTERNIN,
                    fromchannel=self.channeldict['idchannel'],
                    idroute=self.idroute,
                )
                ta_to = ta_from.copyta(status=FILEIN)
                remove_ta = True
                tofilename = str(ta_to.idta)
                with botslib.opendata_bin(tofilename, 'wb') as tofile:
                    simplejson.dump(
                        content, tofile, skipkeys=False, ensure_ascii=False, check_circular=False
                    )
                filesize = os.path.getsize(botslib.abspathdata(tofilename))
            except Exception:
                txt = txtexc()
                botslib.ErrorProcess(
                    functionname='xmlprc-incommunicate', errortext=txt, channeldict=self.channeldict
                )
                if remove_ta:
                    try:
                        ta_from.delete()
                        ta_to.delete()
                    except Exception:
                        pass
                # break out of while loop (else this would be endless)
                break
            else:
                ta_to.update(filename=tofilename, statust=OK, filesize=filesize)
                ta_from.update(statust=DONE)
            finally:
                remove_ta = False
            if (datetime.datetime.now() - startdatetime).seconds >= self.maxsecondsperchannel:
                break

    @botslib.log_session
    def outcommunicate(self):
        """
        do xml-rpc: send files. To be used via receive-dispatcher.
        each to be send file is transaction.
        each send file is transaction.
        """
        for row in botslib.query(
                """SELECT idta,filename,charset,numberofresends
                   FROM ta
                   WHERE idta>%(rootidta)s
                   AND status=%(status)s
                   AND statust=%(statust)s
                   AND tochannel=%(tochannel)s
                   ORDER BY idta
                   """,
                {
                    'tochannel': self.channeldict['idchannel'],
                    'rootidta': self.rootidta,
                    'status': FILEOUT,
                    'statust': OK,
                }):
            ta_to = None
            try:
                ta_from = botslib.OldTransaction(row["idta"])
                ta_to = ta_from.copyta(status=EXTERNOUT)
                with botslib.opendata(row["filename"], "r", row["charset"]) as fromfile:
                    content = fromfile.read()
                response = self.xmlrpc_call(content)
                if self.debug:
                    botsglobal.logger.log(LOG_LEVELS["COM"], "xmlrpc response: %s", response)
            except Exception:
                txt = txtexc()
                if ta_to:
                    ta_to.update(
                        statust=ERROR, errortext=txt, numberofresends=row["numberofresends"] + 1
                    )
                else:
                    botsglobal.logger.critical("xmlprc-outcommunicate: %s", txt)
            else:
                ta_to.update(
                    statust=DONE,
                    filename=self.filename,
                    numberofresends=row["numberofresends"] + 1,
                )
            finally:
                ta_from.update(statust=DONE)


class db(_comsession):
    """
    communicate with a database; directly read or write from a database.
    the user HAS to provide a userscript file in usersys/communicationscripts
    that does the actual import/export using **some** python database library.
    the userscript file should contain:
     - connect
     - (for incoming) incommunicate
     - (for outgoing) outcommunicate
     - disconnect
    Other parameters are passed, use them for your own convenience.
    Bots 'pickles' the results returned from the userscript (and unpickles for the translation).
    """

    def connect(self):
        if self.userscript is None:
            raise BotsImportError(
                _('Channel "%(idchannel)s" is type "db", but no communicationscript exists.'),
                {'idchannel': self.channeldict['idchannel']},
            )
        # check functions bots assumes to be present in userscript:
        if not hasattr(self.userscript, 'connect'):
            raise ScriptImportError(
                _(
                    'No function "connect" in imported communicationscript'
                    ' "%(communicationscript)s".'
                ),
                {'communicationscript': self.scriptname},
            )
        if self.channeldict['inorout'] == 'in' and not hasattr(self.userscript, 'incommunicate'):
            raise ScriptImportError(
                _(
                    'No function "incommunicate" in imported communicationscript'
                    ' "%(communicationscript)s".'
                ),
                {'communicationscript': self.scriptname},
            )
        if self.channeldict['inorout'] == 'out' and not hasattr(self.userscript, 'outcommunicate'):
            raise ScriptImportError(
                _(
                    'No function "outcommunicate" in imported communicationscript'
                    ' "%(communicationscript)s".'),
                {'communicationscript': self.scriptname},
            )
        if not hasattr(self.userscript, 'disconnect'):
            raise ScriptImportError(
                _(
                    'No function "disconnect" in imported communicationscript'
                    ' "%(communicationscript)s".'
                ),
                {'communicationscript': self.scriptname},
            )

        self.dbconnection = botslib.runscript(
            self.userscript, self.scriptname, 'connect', channeldict=self.channeldict
        )

    @botslib.log_session
    def incommunicate(self):
        """
        read data from database.
        communication user script return 'db_objects'.
        This can be one edi-message or several edi-messages.
        if db_objects is a list or tuple is passed:
            each element of list/tuple is treated as seperate edi-message;
            each message is pickled and saved.
        if db_objects is None, nothing is done
        else: one message; the object is pickled and saved.
        So if you want all information from userscript to be passed as one edi message:
            pass as dict, eg {'data': <list of queries>}
        """
        db_objects = botslib.runscript(
            self.userscript,
            self.scriptname,
            'incommunicate',
            channeldict=self.channeldict,
            dbconnection=self.dbconnection,
        )
        if not db_objects:
            # there should be a useful db_objects; if not just return (do nothing)
            return
        if not isinstance(db_objects, (list, tuple)):
            # a list or tuple is expected: pack received object in a list (list with one member).
            db_objects = [db_objects]

        remove_ta = False
        for db_object in db_objects:
            try:
                ta_from = botslib.NewTransaction(
                    filename=self.channeldict['path'],
                    status=EXTERNIN,
                    fromchannel=self.channeldict['idchannel'],
                    idroute=self.idroute,
                )
                ta_to = ta_from.copyta(status=FILEIN)
                remove_ta = True
                tofilename = str(ta_to.idta)
                botslib.writedata_pickled(tofilename, db_object)
                filesize = os.path.getsize(botslib.abspathdata(tofilename))
            except Exception:
                txt = txtexc()
                botslib.ErrorProcess(
                    functionname='db-incommunicate', errortext=txt, channeldict=self.channeldict
                )
                if remove_ta:
                    try:
                        ta_from.delete()
                        ta_to.delete()
                    except Exception:
                        pass
            else:
                ta_to.update(filename=tofilename, statust=OK, filesize=filesize)
                ta_from.update(statust=DONE)
            finally:
                remove_ta = False

    @botslib.log_session
    def outcommunicate(self):
        """read file; pass unpickled object to user script."""
        for row in botslib.query(
                """SELECT idta,filename,numberofresends
                   FROM ta
                   WHERE idta>%(rootidta)s
                   AND status=%(status)s
                   AND statust=%(statust)s
                   AND tochannel=%(tochannel)s
                   ORDER BY idta
                """,
                {
                    'tochannel': self.channeldict['idchannel'],
                    'rootidta': self.rootidta,
                    'status': FILEOUT,
                    'statust': OK,
                }):
            ta_to = None
            try:
                ta_from = botslib.OldTransaction(row["idta"])
                ta_to = ta_from.copyta(status=EXTERNOUT)
                db_object = botslib.readdata_pickled(filename=row["filename"])
                botslib.runscript(
                    self.userscript,
                    self.scriptname,
                    'outcommunicate',
                    channeldict=self.channeldict,
                    dbconnection=self.dbconnection,
                    db_object=db_object,
                )
            except Exception:
                txt = txtexc()
                if ta_to:
                    ta_to.update(
                        statust=ERROR,
                        errortext=txt,
                        filename=self.channeldict["path"],
                        numberofresends=row["numberofresends"] + 1,
                    )
                else:
                    botsglobal.logger.critical("db-outcommunicate: %s", txt)
            else:
                ta_to.update(
                    statust=DONE,
                    filename=self.channeldict['path'],
                    numberofresends=row["numberofresends"] + 1,
                )
            finally:
                ta_from.update(statust=DONE)

    def disconnect(self):
        botslib.runscript(
            self.userscript,
            self.scriptname,
            'disconnect',
            channeldict=self.channeldict,
            dbconnection=self.dbconnection,
        )


class communicationscript(_comsession):
    """
    For running an userscript for communication.
    Examples of use:
     - call external communication program
     - call external program that extract messages from ERP-database
     - call external program that imports messages in ERP system
     - communication method not available in Bots ***or use sub-classing for this***
     - specialised I/O wishes; eg specific naming of output files.
       (eg including partner name) ***beter: use sub-classing or have more user exits***
    place of communicationscript: bots/usersys/communicationscripts
    name of communicationscript: same name as channel (the channelID)
    in this communicationscript some functions will be called:
     - connect (required)
     - main (optional, 'main' should handle files one by one)
     - disconnect  (required)
    arguments: dict 'channel' which has all channel attributes
    more parameters/data for communicationscript:
        hard code this in communicationscript; or use bots.ini
    Different ways of working:
    1. for incoming files (bots receives the files):
        1.1 connect puts all files in a directory, there is no 'main' function.
            bots can remove the files (if you use the 'remove' switch of the channel).
        1.2 connect only builds the connection, 'main' is a generator that passes the messages
            one by one (using 'yield'). bots can remove the files
            (if you use the 'remove' switch of the channel).
    2. for outgoing files (bots sends the files):
        2.1 if there is a 'main' function: the 'main' function is called by bots
            after writing each file.
            bots can remove the files (if you use the 'remove' switch of the channel).
        2.2 no 'main' function: the processing of all the files can be done in 'disconnect'.
            bots can remove the files (if you use the 'remove' switch of the channel).
    """

    def connect(self):
        self.stderr2log()
        logging.addLevelName(LOG_LEVELS["COM"], "COMSCRIPT")
        if self.userscript is None or not botslib.tryrunscript(
                self.userscript, self.scriptname, 'connect', channeldict=self.channeldict):
            self.stderr2log_release()
            raise BotsImportError(
                _(
                    'Channel "%(idchannel)s" is type "communicationscript",'
                    ' but no communicationscript exists.'
                ),
                {'idchannel': self.channeldict},
            )

    @botslib.log_session
    def incommunicate(self):
        startdatetime = datetime.datetime.now()
        # process files one by one; communicationscript has to be a generator
        if hasattr(self.userscript, 'main'):
            remove_ta = False
            for fromfilename in botslib.runscriptyield(
                    self.userscript, self.scriptname, 'main', channeldict=self.channeldict):
                try:
                    ta_from = botslib.NewTransaction(
                        filename=fromfilename,
                        status=EXTERNIN,
                        fromchannel=self.channeldict['idchannel'],
                        idroute=self.idroute,
                    )
                    ta_to = ta_from.copyta(status=FILEIN)
                    remove_ta = True
                    # open fromfile
                    with open(fromfilename, 'rb') as fromfile:
                        filesize = os.fstat(fromfile.fileno()).st_size
                        # open tofile
                        tofilename = str(ta_to.idta)
                        with botslib.opendata_bin(tofilename, 'wb') as tofile:
                            # copy
                            shutil.copyfileobj(fromfile, tofile, 1048576)
                except Exception:
                    txt = txtexc()
                    botslib.ErrorProcess(
                        functionname='communicationscript-incommunicate',
                        errortext=txt,
                        channeldict=self.channeldict,
                    )
                    if remove_ta:
                        try:
                            ta_from.delete()
                            ta_to.delete()
                        except Exception:
                            pass
                else:
                    ta_to.update(filename=tofilename, statust=OK, filesize=filesize)
                    ta_from.update(statust=DONE)
                    if self.channeldict['remove']:
                        os.remove(fromfilename)
                finally:
                    remove_ta = False
                if (datetime.datetime.now() - startdatetime).seconds >= self.maxsecondsperchannel:
                    break
        else:
            # all files have been set ready by external communicationscript using 'connect'.
            frompath = botslib.join(self.channeldict['path'], self.channeldict['filename'])
            filelist = sorted(
                filename for filename in glob.iglob(frompath) if os.path.isfile(filename)
            )
            remove_ta = False
            for fromfilename in filelist:
                try:
                    ta_from = botslib.NewTransaction(
                        filename=fromfilename,
                        status=EXTERNIN,
                        fromchannel=self.channeldict['idchannel'],
                        idroute=self.idroute,
                    )
                    ta_to = ta_from.copyta(status=FILEIN)
                    remove_ta = True
                    with open(fromfilename, 'rb') as fromfile:
                        content = fromfile.read()
                        filesize = len(content)
                        tofilename = str(ta_to.idta)
                        with botslib.opendata_bin(tofilename, 'wb') as tofile:
                            tofile.write(content)
                except Exception:
                    txt = txtexc()
                    botslib.ErrorProcess(
                        functionname='communicationscript-incommunicate',
                        errortext=txt,
                        channeldict=self.channeldict,
                    )
                    if remove_ta:
                        try:
                            ta_from.delete()
                            ta_to.delete()
                        except Exception:
                            pass
                else:
                    ta_to.update(filename=tofilename, statust=OK, filesize=filesize)
                    ta_from.update(statust=DONE)
                    if self.channeldict['remove']:
                        os.remove(fromfilename)
                finally:
                    remove_ta = False
                if (datetime.datetime.now() - startdatetime).seconds >= self.maxsecondsperchannel:
                    break

    @botslib.log_session
    def outcommunicate(self):
        # check if output dir exists, else create it.
        outputdir = botslib.join(self.channeldict['path'])
        botslib.dirshouldbethere(outputdir)
        # get right filename_mask & determine if fixed name (append) or files with unique names
        filename_mask = self.channeldict['filename'] if self.channeldict['filename'] else '*'
        if '{overwrite}' in filename_mask:
            filename_mask = filename_mask.replace('{overwrite}', '')
            mode = 'wb'
        else:
            mode = 'ab'
        # select the db-ta's for this channel
        for row in botslib.query(
                """SELECT idta,filename,numberofresends
                   FROM ta
                   WHERE idta>%(rootidta)s
                   AND status=%(status)s
                   AND statust=%(statust)s
                   AND tochannel=%(tochannel)s
                   ORDER BY idta
                """,
                {
                    'tochannel': self.channeldict['idchannel'],
                    'rootidta': self.rootidta,
                    'status': FILEOUT,
                    'statust': OK,
                }):
            ta_to = None
            try:
                # for each db-ta:
                ta_from = botslib.OldTransaction(row["idta"])
                ta_to = ta_from.copyta(status=EXTERNOUT)
                tofilename = self.filename_formatter(filename_mask, ta_from)
                # open tofile
                tofilename = botslib.join(outputdir, tofilename)
                with open(tofilename, mode) as tofile:
                    # open fromfile
                    with botslib.opendata_bin(row["filename"], "rb") as fromfile:
                        # copy
                        shutil.copyfileobj(fromfile, tofile, 1048576)
                # one file is written; call external
                if botslib.tryrunscript(
                        self.userscript,
                        self.scriptname,
                        'main',
                        channeldict=self.channeldict,
                        filename=tofilename,
                        ta=ta_from,
                ):
                    if self.channeldict['remove']:
                        os.remove(tofilename)
            except Exception:
                txt = txtexc()
                if ta_to:
                    ta_to.update(
                        statust=ERROR, errortext=txt, numberofresends=row["numberofresends"] + 1
                    )
                else:
                    botsglobal.logger.critical("communicationscript-outcommunicate: %s", txt)
            else:
                ta_to.update(
                    statust=DONE,
                    filename=tofilename,
                    numberofresends=row["numberofresends"] + 1,
                )
            finally:
                ta_from.update(statust=DONE)

    def disconnect(self):
        self.stderr2log_release()
        botslib.tryrunscript(
            self.userscript, self.scriptname, 'disconnect', channeldict=self.channeldict
        )
        if self.channeldict['remove'] and not hasattr(self.userscript, 'main'):
            # if bots should remove the files, and all files are passed at once, delete these files.
            outputdir = botslib.join(self.channeldict['path'], self.channeldict['filename'])
            for filename in glob.iglob(outputdir):
                if os.path.isfile(filename):
                    try:
                        os.remove(filename)
                    except Exception:
                        pass


class trash(_comsession):
    @botslib.log_session
    def outcommunicate(self):
        """outcommunicate files to 'nothing' (trash it)."""
        # select the db-ta's for this channel
        for row in botslib.query(
                """SELECT idta
                   FROM ta
                   WHERE idta>%(rootidta)s
                   AND status=%(status)s
                   AND statust=%(statust)s
                   AND tochannel=%(tochannel)s
                   ORDER BY idta
                """,
                {
                    'tochannel': self.channeldict['idchannel'],
                    'rootidta': self.rootidta,
                    'status': FILEOUT,
                    'statust': OK,
                }):
            try:
                # for each db-ta:
                ta_from = botslib.OldTransaction(row["idta"])
                ta_from.update(statust=DONE)
            except Exception:
                txt = txtexc()
                botsglobal.logger.critical(txt)


class http(_comsession):
    """scheme used for building url"""
    scheme = 'http'

    # A dictionary with header params
    # used if specified; eg {'content-type': 'application/json'},
    headers = {}

    # used if specified; eg {'key1':'value1','key2':'value2'}
    # -> http://server.com/path?key2=value2&key1=value1
    params = {}

    # True, False or name of CA-file
    verify = False

    auth = None
    cert = None

    def connect(self):
        try:
            self.requests = botslib.botsbaseimport('requests')
        except ImportError as exc:
            raise ImportError(
                _(
                    'Dependency failure: communicationtype "http(s)"'
                    ' requires python library "requests".'
                )
            ) from exc
        if self.channeldict['username'] and self.channeldict['secret']:
            self.auth = (self.channeldict['username'], self.channeldict['secret'])
        self.url = botslib.Uri(
            scheme=self.scheme,
            hostname=self.channeldict['host'],
            port=self.channeldict['port'],
            path=self.channeldict['path'],
        )
        self.get_params()
        if self.debug is None:
            self.debug = botsglobal.ini.getint('settings', 'httpdebug', 0)
        logging.addLevelName(LOG_LEVELS['COM'], self.__class__.__name__.upper())

    def get_params(self, ta_from=None):
        """Set self.params from self.channeldict['parameters']"""
        parameters = self.channeldict['parameters'].strip('?')
        if parameters:
            if ta_from:
                parameters = self.filename_formatter(parameters, ta_from, runuserscript=False)
            sep = None
            if '&' in parameters:
                sep = '&'
            elif ';' in parameters:
                sep = ';'
            elif ',' in parameters:
                sep = ','
            elif ' ' in parameters:
                sep = ' '
            if sep:
                parameters = parameters.split(sep)
                for param in parameters:
                    if '=' in param:
                        param = param.split('=')
                        self.params[param[0]] = param[1]
        return self.params

    @botslib.log_session
    def incommunicate(self):
        startdatetime = datetime.datetime.now()
        remove_ta = False
        while True:
            # loop until no content is received or max communication time is expired
            try:
                # fetch via requests library
                response = self.requests.get(
                    self.url.uri(),
                    auth=self.auth,
                    cert=self.cert,
                    params=self.params,
                    headers=self.headers,
                    verify=self.verify,
                )
                if self.debug:
                    botsglobal.logger.log(
                        LOG_LEVELS['COM'],
                        'GET URL: %s', response.request.url)
                    botsglobal.logger.log(
                        LOG_LEVELS['COM'],
                        'GET Request: headers: %s', response.request.headers)
                    botsglobal.logger.log(
                        LOG_LEVELS['COM'],
                        'GET Response: status: %s', response.status_code)
                    botsglobal.logger.log(
                        LOG_LEVELS['COM'],
                        'GET Response: headers: %s', response.headers)
                    if self.debug > 3:
                        botsglobal.logger.log(
                            LOG_LEVELS['COM'], 'GET Response: %s', response.__dict__)
                    elif self.debug > 1:
                        botsglobal.logger.log(
                            LOG_LEVELS['COM'],
                            'GET Response: content: "%s"', response.content)
                if response.status_code != self.requests.codes.ok:
                    # communication not OK: exception
                    raise CommunicationInError(
                        _('%(scheme)s receive error, response code: "%(status_code)s".'),
                        {'scheme': self.scheme, 'status_code': response.status_code},
                    )
                if not response.content:
                    # communication OK, but nothing received: break
                    break
                ta_from = botslib.NewTransaction(
                    filename=self.url.uri(),
                    status=EXTERNIN,
                    fromchannel=self.channeldict['idchannel'],
                    idroute=self.idroute,
                )
                ta_to = ta_from.copyta(status=FILEIN)
                remove_ta = True
                tofilename = str(ta_to.idta)
                with botslib.opendata_bin(tofilename, 'wb') as tofile:
                    tofile.write(response.content)
                filesize = len(response.content)
            except Exception:
                txt = txtexc()
                botslib.ErrorProcess(
                    functionname='http-incommunicate', errortext=txt, channeldict=self.channeldict
                )
                if remove_ta:
                    try:
                        ta_from.delete()
                        ta_to.delete()
                    except Exception:
                        pass
                break
            else:
                ta_to.update(filename=tofilename, statust=OK, filesize=filesize)
                ta_from.update(statust=DONE)
                break
            finally:
                remove_ta = False
            if (datetime.datetime.now() - startdatetime).seconds >= self.maxsecondsperchannel:
                break

    @botslib.log_session
    def outcommunicate(self):
        """
        not used now:
        if send as 'body':
            outResponse = requests.post(url, ..., data = filedata)
        elif send as 'attachment':
            # Use channeldict['filename'] is specified in headers not to format url
            outResponse = requests.post(url, ..., data = filedata)
        elif send as 'multipart':
            outResponse = requests.post(url, ..., files={'file': filedata})
        """
        for row in botslib.query(
                """SELECT idta,filename,numberofresends
                   FROM ta
                   WHERE idta>%(rootidta)s
                   AND status=%(status)s
                   AND statust=%(statust)s
                   AND tochannel=%(tochannel)s
                   ORDER BY idta
                """,
                {
                    'tochannel': self.channeldict['idchannel'],
                    'rootidta': self.rootidta,
                    'status': FILEOUT,
                    'statust': OK,
                }):
            ta_to = None
            try:
                ta_from = botslib.OldTransaction(row["idta"])
                ta_to = ta_from.copyta(status=EXTERNOUT)
                filename = row["filename"]
                with botslib.opendata_bin(filename, 'rb') as fromfile:
                    content = fromfile.read()
                filename = self.filename_formatter(self.channeldict['filename'], ta_from)
                disposition = self.channeldict['sendmdn']
                if disposition != 'attachment':
                    disposition = 'inline'
                self.headers['Content-Disposition'] = disposition
                if filename:
                    self.headers['Content-Disposition'] += f"; filename={filename}"
                ta_from.syn("charset", "contenttype")
                # pylint: disable=no-member
                if ta_from.contenttype:
                    self.headers['Content-Type'] = ta_from.contenttype.lower()
                    charset = self.convertcodecformime(ta_from.charset) if ta_from.charset else None
                    if charset:
                        self.headers["Content-Type"] += f"; charset={charset}"

                encoding = self.channeldict['askmdn']
                if encoding == 'always' or (encoding == 'ascii' and charset != 'us-ascii'):
                    self.headers['Content-Transfer-Encoding'] = 'base64'
                    content = base64.b64encode(content)

                self.get_params(ta_from)
                botsglobal.logger.log(
                    LOG_LEVELS['COM'],
                    "http post to '%s' with params: %s", self.url.uri(), self.params)
                botsglobal.logger.log(LOG_LEVELS['COM'], 'http post headers: %s', self.headers)
                # communicate via requests library
                response = self.requests.post(
                    self.url.uri(),
                    auth=self.auth,
                    cert=self.cert,
                    params=self.params,
                    headers=self.headers,
                    data=content,
                    verify=self.verify,
                )
                if self.debug:
                    botsglobal.logger.log(
                        LOG_LEVELS['COM'],
                        'POST URL: %s', response.request.url)
                    botsglobal.logger.log(
                        LOG_LEVELS['COM'],
                        'POST Request: headers: %s', response.request.headers)
                    if self.debug > 1:
                        botsglobal.logger.log(
                            LOG_LEVELS['COM'],
                            'POST Request: content: "%s".', response.request.content)
                    botsglobal.logger.log(
                        LOG_LEVELS['COM'], 'POST Response: status: %s', response.status_code)
                    botsglobal.logger.log(
                        LOG_LEVELS['COM'], 'POST Response: headers: %s', response.headers)
                    if self.debug > 3:
                        botsglobal.logger.log(
                            LOG_LEVELS['COM'], 'POST Response: %s', response.__dict__)
                    elif self.debug > 1:
                        botsglobal.logger.log(
                            LOG_LEVELS['COM'],
                            'POST Response: content: "%s"', response.content)
                if response.status_code != self.requests.codes.ok:
                    raise CommunicationOutError(
                        _('%(scheme)s send error, response code: "%(status_code)s".'),
                        {'scheme': self.scheme, 'status_code': response.status_code},
                    )
            except Exception:
                txt = txtexc()
                if ta_to:
                    ta_to.update(
                        statust=ERROR,
                        errortext=txt,
                        filename=self.url.uri(filename=filename),
                        numberofresends=row["numberofresends"] + 1,
                    )
                else:
                    botsglobal.logger.critical("%s-outcommunicate: %s", self.scheme, txt)
            else:
                ta_to.update(
                    statust=DONE,
                    filename=self.url.uri(filename=filename),
                    numberofresends=row["numberofresends"] + 1,
                )
            finally:
                ta_from.update(statust=DONE)

    def disconnect(self):
        pass


class https(http):
    """
    testing results:
    - http server with self-signed certificate:
        - caCert=None, verify='/pathtocert/ca.pem': OK, certificate is verified.
        - caCert points to same certificate, verify = None: OK, certificate is verified.
        - verify = True: OK, but certificate is not verified.
    """

    # scheme used for building url
    scheme = 'https'
    # verify host certificate: True, False or path to CA bundle eg '/pathtocert/ca.pem'
    verify = True
    # None or path to CA bundle eg '/pathtocert/ca.pem',
    # Specify if https server has an unrecognized CA.
    # Looks like verify needs to be None in order to work(??)
    ca_cert = None

    def connect(self):
        """
        option to set environement variable for requests library;
        use if https server has an unrecognized CA
        """
        super().connect()
        if self.ca_cert:
            os.environ["REQUESTS_CA_BUNDLE"] = self.ca_cert
        if self.channeldict.get("certfile") and self.channeldict.get("keyfile"):
            self.cert = (self.channeldict["certfile"], self.channeldict["keyfile"])
