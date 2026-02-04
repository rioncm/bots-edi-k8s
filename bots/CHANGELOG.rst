Bots - CHANGELOG
================


4.0.0 (2025-10-xx)
------------------
- Python 3 only >= 3.9
- Django 5 support
- Bugs fixes
- Added responsive ui support
- views.filer: Fix xml indent == '0' display in some cases
- More universal and readable log format: "asctime levelname [logname] message"
- botstable: Updates & enhancements
- confirmrule enhancements: admin, 'confirmasked' ruletype added for x12
- envelope.x12: Dynamic ISA14 depending on confirmrule ask-x12-997
- inmessage.tradacoms: Fix: Add missing function set_syntax_used()
- Add strip_value grammar syntax parameter for inmessage (EDIFACT, X12, TRADACOMS, CSV)


3.8.5 (2023-05-30)
------------------
- admin/base.html: Fix nav-bots with django < 4
- bots.css:
    - Fix/clean --header-* color vars
    - Add styles to datetime clock
    - Updates/Fixes sticky positions


3.8.4 (2023-05-22)
------------------
- [UI] Add theme switch support (django >= 4.2)
- [UI] Add sticky bars (nav-bots, breadcrumbs, ...)
- document.html: Add log link
- admin/routes: Clear alt value when no translateind


3.8.3 (2023-04-08)
------------------
- botsinit: console log format is now same as file log format
- configure: Fixes locals() vars


3.8.2 (2023-03-30)
------------------
- locale/fr: Update
- views.(document, process): Update titles
- nav/documents.html: Remove useless PROCESS link
- Cleaning usage text of console-scripts
- Outgoing: Fix statust filter display for exclude values
- Fix js view_translate() for incoming, outgoing and document views
- document.html: Add filter/exclude to status field
- botstable:
    - No display of filter for already filtered field
    - No display of exclude if exclude value is not in field.options


3.8.1 (2023-03-24)
------------------
- nav/allruns.html: Add nav/documents.html: All Phases
- bots.ini[webserver] Add menu_changepassword
- filer: Add indent (json, xml, html)
- reports.html: Add dropdown filters to row.status and row.type
- bots.ini[webserver]: Add log_cherrypy_access (default: False)
- admin.py: Remove classes: wide, extrapretty, add get_form


3.8.0 (2023-03-03)
------------------
- locale/fr: Updates

- confirm: Fix displayed buttons when filtered

- models.routes: Same notindefaultrun value to all sequences of a route

- Fixes for Py2:
    - __init__.py for initbotsenv
    - models.py:    glob recursice arg need Py >= 3.5
    - transform.py: queries formating cleaning
    - admin.py:     Fix ModelAdmin.log_change
              :     Fix bugged js part
    - forms.py:     Fix not valid py3 syntax (v, *list)
    - templates:    Fixes for old django<2 translate > trans
    - botslib:      last fixes for ascii row keys needed by query()

- Drop support Django < 1.11

- Change name of all saved plugin to: bots_plugin_xxxxxx.zip

- views.py:
    - Remove cleaning of cleaned_data for idta and/or reportidta keys
    - Better args request parsing

- forms.LIMITS: Add 150 and 200 (items per page)
- [UI] Add save and delete selection to all views with botstable
- [UI] Better display performances
- botslib.Uri(): Little fix
- botslib.botsinfo_display(): added
- bots.config.settings.USE_TZ = False
- pluglib.py: Update, fixes & cleaning
    - plugout_backup_core() and delete() moved from views.py
- models.py: Add list_usersys(), get_userscripts() moved from admin.py

- envelope.py: Fix default envelope_content for envelope()

- [UI] Date/time:
    - displayed with settings.DATE(TIME)_FORMAT
    - DATE/TIME_INPUT_FORMAT context

- [UI] Add icons (py, filter, log, user, group, logfiler(*)
- filer: Add numbered lines
- inmessage.x12.handleconfirm: Fix checkconfirmrules
- List grammars and mappings in subdirectories
- templates/403_csrf.html: New


3.7.15 (2022-12-03)
------------------
- [UI] Fix unclickable link in translate change_list page opened from a route change_form
- [UI] bots(-nav).css:
    - Fix nav-bar border
    - Add box-shadow
- [UI] *filer.css:
    - Add background-color filer and source content
    - Add css/dark_mode.css
    - Add & update colors
- [UI] Scale new window open by popup()

3.7.14 (2022-12-01)
------------------
- locale/fr: Update
- webserver.py: Add custom CherryPy error 404 page for static path
- bots/install/settings.py: Add [session,CSRF]_COOKIE_NAME

3.7.13 (2022-07-04)
------------------
- bots/nav/config.html: Add channel/[in,out]/Add [in,out] channel
- bots/channel/change_form.html: Fix remove field display for add channel
- refresh.html: Stop refresh page when selector is set with no value
   - This avoid refreshing page when selector change to no value
- bots-configure: Init and display user Bots config environment
- botsinit: initbotsenv() added, called in generalinit()
   - Now clean bots env is created at first run

3.7.12 (2022-05-28)
------------------
- bots.css: Add botsstatus4 text color for dark scheme
- models.channel.routes_link(): Added, in admin channel list_display
- channel/change_form.html: Hide remove field for out channel
- admin/bots/change_form.html: Add obj_title block in content_title block
  This fix title in add translate and channel admin view.
- admin routes: Add link to translates

3.7.11 (2022-05-19)
------------------
- __init__.py: default_app_config is no more used in Django >= 4
- link/confirmation.html: Add refresh button for pending confirmation
- views.logfiler: Fix max engine log files displayed (25) with log_when=report
- logfiler.html: Add link to top in subtitle
- communication.sftp: Fix paramiko.logger.level from channel.debug
- dirmonitor.process_existing_files(): Skip route.fromchannel not removed files
- dirmonitor/jobqueueserver: Verify if jobqueue is running with 'isup' task
- templates/bots/nav/[custom,shortcuts] Fixes for Django 4

3.7.10 (2022-05-12)
------------------
- dirmonitor.py: Linux Fixes/updates thread notifier and reload

3.7.9 (2022-05-02)
------------------
- views.runengine: Add redirect to reports
- views.runengine: Clean/update log and message
- bots.ini: Add log_when: daily, report (default - replace log_file_number = idta)
- bots.ini: log_file_number could be specified for [webserver, jobqueue, dirmonitor]
- views.document: Fix allstatus catch when idta is specified

3.7.8 (2022-03-23)
------------------
- Update locale/fr
- botstable/td/confirmed.html: Update for manual confirm
- bots/link/confirmation.html: Fix pending displayed for not confirmasked docs
- models.routes.dirmonitor: Update help_text

3.7.7 (2022-03-22)
------------------
- bots/select*.html: Add clear all filters button
- Update confirmations: confirmed, unconfirmed, pending ...
- admin: change_form title: channel: Add type, translate: Add fromeditype
- bots/js/vars.html-> bots/js/urls.html
- forms.DocumentForm: Add allstatus and filename
- models.py: Update for dirmonitor, add reload_dirmonitor(), ...
- dirmonitor.py: Update usage()

3.7.6 (2022-03-12)
------------------
- admin.py: Routes/Channel: title with filter values in change_list
- bots.css: botslink: Use default color: var(--link-fg)
- User shortcuts: Fix perms & exclude other user shortcuts
- communication.py: Updates & fixes reference[:128] > [:256]
- admin.py: Clean fix actions, more docsting

3.7.5 (2022-03-10)
------------------
- dirmonitor.linux_event_handler: Better events catch
- dirmonitor.add_job(): Log and catch send return error and sendbotserror
- Update services exit log
- botsinit.generalinit(): Add djediint.bots init
- dirmonitor: Update admin activation with others dirmonitored routes

3.7.4 (2022-03-07)
------------------
- config/settings.py: Default botssys is now in ~/.bots/env/$USER/botssys
- dirmonitor: Add trigger to reload conf while running
- incoming.html: Add filter by reportidta in dropdown menu
- admin.ChannelAdmin.list_filter: Add 'debug'
- communication.LoggerPipe: Better log display (imap4(s), smtp(s))

3.7.3 (2022-02-22)
------------------
- Add shortcuts menu for custom and user shortcuts urls
- Selected lines are now colorized
- filer.html: Fix sticky title & html/pdf height
- forms.py: LIMITS: add 250
- botsinit.py: LOG_LEVELS: STARTINFO=28, START=27, DONE=26, COM=25, STDOUT=11, STDERR=12
- models.(report,filereport): Add delete():
   - Add delete reports from ui. (cascade filereport(s) and ta related entries)
   - Add forms.incoming.reportidta
- communication.py: http debug log content and response depend on level
- admin.py: Add debug in channel list_display
- communication.py: Add stderr2log(): All debug log > engine.log
   - Now communication debug log are logged into engine.log
- models.ta.reference: max_length 128 > 256
- bots/filer.html: Better display for html/pdf content (full height)

3.7.2 (2022-02-11)
------------------
- botsinit.py: LOG_LEVELS: Add START: 25, DONE: 26, STARTINFO: 25 > 27
- envelope.envelope(): Fix json.loads() with empty ta_info['rsrv5']

3.7.1 (2022-02-10)
------------------
- jobqueueserver: Updates, add security enhancement, log (stderr, stdout)
   - Restrict tasks that could be run (bots-engine), Add others in bots.ini
   - stderr and stdout of job could now be logged.
   - If job exit with error, this is now logged.
- job2queue: Update & Fix start bug introduce with I18N JOBQUEUEMESSAGE2TXT
- admin.routes: Better display of dirmonitor in list_display
- logfiler.html: Add refresh button for current log (process.log)

3.7.0 (2022-02-08)
------------------
- forms.ReportsForm: Add type filter (new, resend, rereceive, retry)
- [templates] Display (from/to)channel (type) (file, ftp, http, smtp, ...)
- Increase len of models:
   - ta.reference, ta.divtext, ta.rsrv1 to 128
   - report.rsrv1 to 256
- Incoming email attachment filename > ta.divtext
- Add download file link after all filer link
- [templates] Add botstable/dropdown/*.html, update botstable/td/*, bots/link/*
- Update loglevel to INFO start/end route and channel communication
- communication.py: Set debug level from channeldict['debug']
- Fix infinite loop with communication.http.incommunicate()
- dirmonitor: Now watch routes fromchannel (file) with active dirmonitor
- bots-filer.css: Fix for several ta in idtas filer.html
- views.logfiler: Better download filename
- views.runengine(): Fix message and log level
- models.py: increase, clean, add routes.dirmonitor, channel.debug:
   - Add models.routes.dirmonitor: implementated in bots-dirmonitor
   - Add models.channel.debug: implemented in communication.py
- [core] Updates from eppeye-bots/bots3.3:
   - Json filed type
   - enveloppe access from mapping
   - ...
- communication.py: add filename parameter to accept_incoming_attachment
- outmessage.xml(): Remove python26 part
- PY3 module import first
- pluglib.py: plugout_files() Fix default charsetdirs os path (win)
- admin.py: Record activate/deactivate actions in Django object history
- communication.py: sftp: use keyfile; remove pycrypto depency, check for paramiko version; more comments
- update validate email
- router.py: Fix resend if mime


3.6.2 (2021-12-29)
------------------
- Add forms.View.actions and multiline select (incoming, outgoing, confirm):
   - Select several lines (incoming, outgoing, confirm) to run action:
     delete, rereceive, resend, manual confirm.

3.6.1 (2021-12-27)
------------------
- bots-icons.css: Change ico-run
- forms.py: Increase some CharField max_length to 512 (filename, ref, ...)
- js/refresh.html: Fix infinite reload loop when invalid form is posted
- templates/bots/botstable: Cleaning paths: Move td_*, thead_* > td/* thead/*
- botstable/checkbox_field.html: checkbox button style (lastrun, admlink, popup)
- clear_*.html: Update delete icons, now displayed with css class
- forms.py, outgoing.html: Add testindicator filter field

3.6.0 (2021-12-24)
------------------
- locale/fr: Update
- Add bots/refresh.html bots/js/refresh.html to bots/base.html
- botsinit.py: Little change of logging format
- Add admin/index.html admin/login.html
- Big update on web part: icons, filters line, cleaning views, ...
- Updates, fixes and clean: forms.py, views.py, viewlib.py
- favicon.ico -> bots.ico
- Add admin/js/bots.js and (from/to)messagetype selector in routes admin
- Refactor and clean javascript part of selectors of translate admin and now in routes admin.
- css: Update color values by var(--xxxx) from django
- admin.py: TranslateAdmin: Permit {editype}/{editype}.py messagetype
- get_grammars() could list edifact/edifact.py, x12/x12.py, ...
- Add bots/templates/bots/link/grammarsrc.html
- Cleaning for botslink css class in templates/bots/link/*
- bots.js: Fix add_class_sortedby() in some cases
- admin/base.html: Add block favicon in block extrastyle
- forms.py: Fix ConfirmForm.confirmed initial=''
- models.py: Update script_link* (script_link2 > script_viewlink)
- Add bots/link/messagetype.html
- Add (from/to)messagetype and tscript selectors for translate admin
- admin.py: Clean translate with read only perms
- admin.py: Fix & clean for translate list_display and perms script view
- Add bots/translate/change_form.html with view src link
- admin.py: Add perms to script links (route, comscript, grammars, mapping)
- Change script icon: icon-yes.svg > icon-viewlink.svg


3.5.4 (2021-09-17)
------------------
- bots.css: Fix user-tools links color
- Add favicon in srcfiler.html
- Add favicon in logfiler.html
- Fix arg sep link (; > &) in nav/(in-out)xoming.html,
  Django doen't support ';' arg request separator anymore.

3.5.3 (2021-09-10)
------------------
- Update usertools and userlinks blocks in templates/
- Fix password_change

3.5.2 (2021-09-05)
------------------
- change_form: Update for Django > 3.2 with new subtitle block

3.5.1 (2021-09-05)
------------------
- change_form: Better title with app name, model.verbose_name and entry name
- change_list: Better title with app_name and model._meta.verbose_name_plural

3.5.0 (2021-09-03)
------------------
- views.py: Updates & fixes GET request?* & ?select&*
- botslib.txtexc(limit=0): Parametize limit of traceback.format_exc(limit=limit)
- botslib.txtexc(): Log all calls: botsglobal.logger.error(terug)
- Add errors links in in/out/allrun nav
- Add GET request with fields value & permanent link on all views
- Add (from/to)partner_tochannel routes admin filters


3.4.9 (2021-06-21)
------------------
- Add admin filters for routes, translate, partner:
   - Partner admin view can be filtered by partnergroup
   - Add from/to partner filters in routes and translate admin view
   - add from/to messagetype, tscript, alt filters to translate admin view

3.4.8 (2021-05-23)
------------------
- Add make bots plugin admin actions:
   - route without translate
   - grammar plugin
   - translate plugin without grammar (entries and mappings scripts only)

3.4.7 (2021-05-17)
------------------
- Fixes & update models.scripts_link*, add scriptname in srcfiler.html title
- Better error display
- exceptions log level raise to ERROR in transform.py
- log level for exception up to ERROR for botslib.log_session
- Fix security in views.srfiler()
- Fix botslib.botsinfo() with sqlite db settings without user, host

3.4.6 (2021-01-14)
------------------
- Update/fixes permissions: admin, views, bots/nav/*.html
- New: make plugin from admin selection: ccodes, channel, routes,...
- make_plugin with queryset include all related entries and files:
   - routes: add related channels + scripts, partners + scripts
   - translate with mappings and grammars except for edifact/x12 without route.alt set
- Fix pluglib.read_index2database:
      django.db.models.fields.FieldDoesNotExist > django.core.exceptions.FieldDoesNotExist
- Fixes plugins*/plugout* views: form.action for delete
- Filters selections with several values and negative filtering rule
- Lots of fixes and update on ui
- Update boslib.Uri() and comunication.http path and filename
- Add missing fields (rsrv2, rsrv4) to filterlist in botslib._Transaction
- Add popup to all views: add _popup field in BotsForm
- Fix & Update logger.level

3.4.5 (2020-11-26)
------------------
- Add bots.apps for django apps config
- Fix/update bots.views.server_error()
- Update for django.setup() in botsinit.generalinit()
- Update bots-menu with bots-nav templates

3.4.4 (2020-11-10)
------------------
- Update bots environment infos display by engine log
- Fixes for Py2, super() call in class need class xxx(object)

3.4.3 (2020-09-21)
------------------
- Fix services launch by systemd in settings.py
- Fix bug with engine log file introduce logging name change in 3.4.2
- Change/Fix botsinit.BotsConfig().get()
- Update config/settings.py install/settings.py

3.4.2 (2020-09-09)
------------------
- Cleaning logging: logger.name = __name__
   - 'bots.webserver'
   - 'bots.jobqueueserver'
   - 'bots.dirmonitor'
   - ...
- Console log with timestamp
- Fix LOGIN_REDIRECT_URL = /bots/home in settings.py

3.4.1 (2020-09-03)
------------------
- Prefix bots views urls path: /bots/(in..,out..,report,...) 
- Now auth_patterns could be imported from bots.urls
- [UI] Fix bots menu integration with others nav bar (Django 3, ...)
- Update for Django 4 ugettext() > gettext()
- Django 3 compatibility, remove python_2_unicode_compatible in models.py
- Clean/add fields in all bots.ini
   log_file_number = idta
   compatibility_mailbag = False
   nr_threads = 1
   unow = utf_8
- Delete counter in admin are now allowed execept internals
- [ui] remove save_on_top for Ccodetrigger and Uniek in admin.py
- [ui] Fix title in link/logfiler.html
- [ui] Better menu, config>* submenus (routes, chan, ...)
- Add fromchannel, tochannel to routes list_filter in admin.py
- Add clear_filter for date fields when value
- node.display*() now use logger.info() instead of print()
- Add verification for imported settings in generalinit()
- Fix xml2botsgrammar with python3
- Fix & clean whatched recursive directories in dirmonitor.py
- Fix for Node, cast part results to string if enhancedget with list

3.4.0 (2020-03-02)
------------------

- Update all views with nicer botstable headers using filtered field menu.

- Added saving selection in select to recall a selection in view and select.

- Add botsmenu context to have possibility to customize menu like botslogo.


3.3.4 (2019-12-18)
------------------

- filer.html improvement, display html and pdf files.

- Download file in filer, now check editype/contenttype to set appropriate filename extention.

- templatehtml could access to ta_info, like ta_info['reference']
  in template.html and envelope.html to.

- Parametize and add templatehtml engines: genshi, django (for now)
  maybe more in future like jinja2, but genshi is already powerfull

- Add save_on_top for all admin change_form

- Update for new engine log file stored by idta,
  now param in bots.ini [settings] log_file_number is 'idta'.
  That store engine.log in logging/engine/idta of each run.

- Better title display for logfiler

- Update logging formating


3.3.3 (2019-10-14)
------------------

- Better display in views with colorized status

- New logging system available for engine, log could be keeped and viewed for each report

- Log files now have it's own process directory (logging/engine/.., logging/webserver/..)

- Some fixes


3.3.2 (2019-10-02)
------------------

- jobqueue fully fixed and now work as expected.

- dirmonitor now check files at starting.

- xml indent could be parametized with string like 'indented': '\t',

- Remove ``persistfilters.py``. already in Django > 1.6.

- Add local/fr for French translations.

- Big cleaning and littles fixes on all pythons files



3.3.1 (2019-07-18)
------------------

- Full Python 3 support

- Updated ``setup.py`` and build methods

- Update for tests

- Latest CherryPy support

- Django 2 support

- New datetime picker from https://github.com/xdan/datetimepicker

- Restore jobqueueserver. It was broken in 3.3.0 because of unfinished
  python2/3-support. Fixes https://github.com/bots-edi/bots/issues/21.
  [WouterVH]

- Remove ``bots_importlib``. Python2.6 is no longer supported.
  Cfr. https://github.com/bots-edi/bots/issues/23
  [WouterVH]

- Remove ``bots_ordereddict``. Python2.6 is no longer supported.
  Cfr. https://github.com/bots-edi/bots/issues/22
  [WouterVH]

- Add rst-version of GPL3-license.
  Thanks to https://github.com/shibukawa/rest-licenses/
  [WouterVH]

- Updated ``MANIFEST.in``.

- Add ``setup.cfg`` with config-settings for several tools.
  Also set ``bdist_wheel`` to ``universal``.
  [WouterVH]

- Move unittests to ``tests``-subdirectory.
  [WouterVH]

- Move scripts to ``scripts``-subdirectory.
  [WouterVH]


3.3.0 (2016-11-23)
------------------

- Add ``License.rst``
  [WouterVH - 22-11-2016]

- Update Readme, and .gitignore
  [JCapriotti - 19-11-2016]

- add setup.py using setuptools
  [WouterVH - 09-08-2016]

- add .gitignore-file
  [WouterVH - 09-08-2016]

- Revert ``Added gitignore and sphinx docs``
  [eppye - 08-03-2016]

- Revert ``Added gitignore and sphinx docs``
  [eppye - 08-03-2016]

- Merge pull request #367 from abhishek-ram/sphinx-docs
  Added gitignore and sphinx docs
  [eppye - 07-03-2016]

- Added gitignore and sphinx docs
  [ Abhishek Ram - 31-10-2015]

- last chagnes?
  [eppye - 15-08-2015]

- small change in text for 'ftp account'
  [eppye - 04-08-2015]

- Issue 362: add: more preprocessing
  [eppye - 21-05-2015]

- type in internal function name: save_int instead of safe_int
  [eppye - 21-05-2015]

- Issue 253: migrate to python 3.*
  python3 uses another pickle protocol by default.
  [eppye - 20-05-2015]

- change in comments
  [eppye - 20-05-2015]

- added some unittests.
  [eppye - 20-05-2015]

- small change i order to get unittests right: transform.getcodeset gets a list from ccodes.
  postgreSQL returns this in 'reversed' order.
  not an error, but use same orders as MySQL and SQLite
  [eppye - 20-05-2015]

- Issue 254: for persist: timestamp on update
  [eppye - 20-05-2015]

- Issue 359:  Add option for daily engine.log
  [eppye - 20-05-2015]

- Issue 341: Optionally add ``run cleanup`` to run menu. Allow cleanup run from commandline in acceptance testing.
  (missed some code at first try)
  [eppye - 20-05-2015]

- Issue 338: Error when incoming email with subject > 35 chars and db is not SQLite
  [eppye - 20-05-2015]

- Issue 347: bots_communication_failure counters: domein too long for db field
  [eppye - 20-05-2015]

- Issue 358: cleanup.py should not log ``vacuum database`` for non-sqlite installations
  [eppye - 20-05-2015]

- Issue 363: add: function to split up text (or lists)
  [eppye - 20-05-2015]

- change in comments
  [eppye - 20-05-2015]

- Issue 360: mapping is the centre of bots,
  set email-addresses from mapping
  [eppye - 19-05-2015]

- Issue 355: add: easier access to all envelope fields in mapping
  changed this again: envelope fields are in inn.envelope: a list of dicts: [mpath,mpath,etc]
  [eppye - 19-05-2015]

- Issue 360: mapping is the centre of bots
  - outcommented mysterious assignged to topartners in transform.py/_translate_one_file ; it does not do anything.
  - changes in comments
  [eppye - 16-05-2015]

- change in comments
  [eppye - 16-05-2015]

- Issue 328: pass frommail and tomail to mapping
  during testing found: tomail was not passed if there was no check on the toaddress.
  changed this, tomail is now always passed.
  [eppye - 15-05-2015]

- Issue 356: set all envelope fields from mapping
  - more data is passed for merging - so more data will get passed from maping script
  - more comments
  - fixed soem inconsistenties in enveloping
  [eppye - 13-05-2015]

- small code change for use in acceptance tests: get a frozen value for datetime objects.
  (needed this in some mappig scripts).
  [eppye - 12-05-2015]

- change in comments
  [eppye - 12-05-2015]

- Issue 355: add: easier access to all envelope fields in mapping envelope fields are in:
  inn.envelope (a dict), not in ta_info anymore.
  [eppye - 11-05-2015]

- small code change for use in acceptance tests: get a frozen value for datetime objects.
  (needed this in some mappig scripts).
  [eppye - 25-04-2015]

- Issue 355: add: easier access to all envelope fields in mapping
  [eppye - 23-04-2015]

- Improve & bug fix for Issue 353: add: function to 'strip diacritics'
  - one function (instead of 2)
  - can handled other charsets (not only ascii and latin1/iso-8859-1)
  - one char -> one char or nothing - but not eg 2 chars; better because fields lenghts should not get 'suddenly' bigger in edi
  [eppye - 22-04-2015]

- Issue 357: Add: pass to mapping number of messages and sequence number in file/interchange
  [eppye - 22-04-2015]

- Issue 354: better handling of partners in x12 (edifact)
  pick up combination of ISA-ID/ISA-qual/GS-ID.
  improved coding of enhancedget.
  [eppye - 17-04-2015]

- Issue 353: add: function to 'strip diacritics'
  [eppye - 16-04-2015]

- Issue 349: In translations, grammars not required for db or raw types, so do not show error icon
  [eppye - 15-04-2015]

- Issue 253: migrate to python 3.*
  roll back: callable() is available in python >= 3.2
  [eppye - 11-04-2015]

- small code/errors improvement:
  - different warning for missing frompartner and topartner
  - checking in subroutine: same for x12, edifact etc.
  [eppye - 11-04-2015]

- Issue 352: new: very strict checking on whitespace 'between' records
  [eppye - 11-04-2015]

- Issue 351: add: sanity checks on separators (edifact/x12)
  [eppye - 10-04-2015]

- Issue 348: set/change headers via user scripting
  [eppye - 09-04-2015]

- max integer was not tested correctly.
  limit here is the database: int is 2^31 -1
  to change that, have to change database -> next database migration
  [eppye - 09-04-2015]

- Issue 337: Add bots_environment_text in page title
  [eppye - 07-04-2015]

- Issue 340: Admin views minor changes for better usability
  [eppye - 07-04-2015]

- Issue 341: Optionally add ``run cleanup`` to run menu. Allow cleanup run from commandline in acceptance testing.
  [eppye - 06-04-2015]

- Issue 346: added option: when arything goes wrong in translation, skip whole file /no output
  [eppye - 03-04-2015]

- change in comments
  [eppye - 03-04-2015]

- Issue 345: remove in communication.py option to userscript keyfile, certfile
  [eppye - 03-04-2015]

- Issue 342: Add logfile viewer in GUI
  [eppye - 03-04-2015]

- change in comments.
  [eppye - 03-04-2015]

- restructured code for fixed files with noBOTSID
  [eppye - 02-04-2015]

- Issue 344: bug when re-using structures (in grammar)
  Other things for grammars/grammarreading:
  - more consistent fucntion calls (no more defaults)
  - much more comments in grammar.py
  - code is better structured.
  - soem extra checks were not performed bacause of typo
  [eppye - 02-04-2015]

- Issue 253: migrate to python 3.*
  in unittests: same conversion 'trics' as in source code
  [eppye - 02-04-2015]

- Issue 253: migrate to python 3.*
  [eppye - 01-04-2015]

- get grammar/grammar reading clearer:
  - changes in comments
  - no more defaults in grammar read functions - that only obscures things.
  [eppye - 31-03-2015]

- small change in coding: read/write pickled files via botslib.
  [eppye - 30-03-2015]

- change in comments.
  [eppye - 30-03-2015]

- Issue 334: better errors for numeric fields with exponentials
  [eppye - 30-03-2015]

- Issue 333: bug: charsets of incoming emails
  [eppye - 30-03-2015]

- minor change/improvement in logic of file->email mime.
  [eppye - 30-03-2015]

- Issue 332:  in node.change: convert eg int to string (like in put())
  [eppye - 30-03-2015]

- Issue 331: changed 'out_as_inn' implementation (same functionality)
  also other changes; see change for  Issue 253:  migrate to python 3.*
  [eppye - 30-03-2015]

- Issue 330: removed 'persistfilter' in GUI
  [eppye - 30-03-2015]

- Issue 329: filtering incoming email: add 'multipart/related' to whitelist_multipart
  [eppye - 30-03-2015]

- Issue 328: pass frommail and tomail to mapping
  [eppye - 30-03-2015]

- Issue 327: add more parameters to user exits for 997/CONTRL
  [eppye - 30-03-2015]

- Issue 326: edifact/UNA segment: if repetition seperator is space, assume they make a mistake
  plus: typo: seperator -> separator
  [eppye - 29-03-2015]

- Issue 325: fix bug in grammar read logic
  [eppye - 28-03-2015]

- Issue 324: other way of indicating unique part in filename
  [eppye - 28-03-2015]

- Issue 318:  mimefile msgid may exceed 70 chars (too big for database)
  [eppye - 28-03-2015]

- Issue 323: rollback Issue 314
  [eppye - 26-03-2015]

- Issue 253: migrate to python 3.*
  [eppye - 26-03-2015]

- Issue 319: better xml-generating
  [eppye - 26-03-2015]

- Issue 320: better json generating - sorted!
  [eppye - 26-03-2015]

- Issue 321: improve outgoing formatting fields
  [eppye - 26-03-2015]

- bug in bots 3.2.0. not serious/no harm.
  [eppye - 10-09-2014]

- bug in 2.3.0. Not very serious.
  [eppye - 10-09-2014]

- 2 bugs in bots 3.2.0 (reported by ludovic)
  [eppye - 10-09-2014]

- changes in comments
  [eppye - 10-09-2014]

- update windows build batchfiles.
  [eppye - 04-09-2014]

- correct version
  [eppye - 03-09-2014]

- ready for release 3.2.0
  [eppye - 01-09-2014]


3.2.0 (2014-09-02)
------------------

- TODO


3.2.0rc2 (2014-05-27)
---------------------

- TODO


3.2.0rc (2013-05-27)
--------------------

- TODO
