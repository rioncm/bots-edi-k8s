# Communication Channel Reference

This page documents communication/session behavior in:

- `bots/bots/communication.py`

## Dispatcher Contract

`run(idchannel, command, idroute, rootidta=None)`:

1. Loads channel row from DB.
2. Applies acceptance-test channel overrides when enabled.
3. Loads optional communication script (`communicationscripts/<idchannel>.py`).
4. Resolves channel class:
   - script class named as channel type, or
   - legacy `UserCommunicationClass`, or
   - built-in class by channel `type`.
5. Instantiates and runs class.

If channel is missing, raises `CommunicationError`.

## Session Lifecycle (`_comsession`)

The base lifecycle is orchestrated by `_comsession.run()`.

### Outbound channels (`inorout='out'`)

1. `precommunicate()`
2. `connect()` with retry loop
3. `outcommunicate()`
4. `disconnect()`
5. `archive()`

### Inbound channels (`inorout='in'`)

For `command == 'new'`:

1. `connect()` with retry and failure throttling support
2. `incommunicate()`
3. `disconnect()`

Then:

4. `postcommunicate()`
5. `archive()`

### Base hooks to override

- `precommunicate`
- `connect`
- `incommunicate`
- `outcommunicate`
- `postcommunicate`
- `disconnect`

## Common Utilities in `_comsession`

### `file2mime()` and `mime2file()`

These provide default email packaging/unpackaging behavior:

- `file2mime`: outgoing FILEOUT payload -> RFC822 document.
- `mime2file`: incoming RFC822 -> extracted attachments/messages.

Both integrate:

- partner mail address resolution,
- confirm/MDN rules,
- content-type filtering,
- TA status updates and error propagation.

### Filename templating: `filename_formatter(filename_mask, ta, runuserscript=True)`

Supports Python format-style tokens against TA attributes plus special values:

- `{unique}` (or legacy `*`)
- `{datetime:%Y%m%d...}`
- `{infile}`, `{infile:name}`, `{infile:ext}`
- `{overwrite}` marker in mask

Also supports script override via `filename(...)` in channel communication script.

## Built-in Channel Classes

Major built-in transport classes include:

- Local filesystem: `file`, `mimefile`, `trash`
- Mail inbound/outbound: `pop3`, `pop3s`, `pop3apop`, `imap4`, `imap4s`, `smtp`, `smtps`, `smtpstarttls`
- FTP variants: `ftp`, `ftps`, `ftpis`
- `sftp`
- Service protocols: `xmlrpc`, `http`, `https`
- Data/script adapters: `db`, `communicationscript`

All classes share the same TA-driven pattern:

- read source payloads into internal storage on inbound,
- emit outbound payloads from internal storage,
- maintain status progression (`EXTERNIN/FILEIN`, `FILEOUT/EXTERNOUT`) with `statust` semantics.

## File Channel Behavior (`class file`)

### Inbound (`file.incommunicate`)

- Scans `path/filename` glob.
- Creates `EXTERNIN -> FILEIN` TA chain per file.
- Optional OS-level file locks (`syslock`).
- Copies content into internal bots data files.
- Optionally removes source file (`remove`).

### Outbound (`file.outcommunicate`)

- Selects pending `FILEOUT/OK`.
- Creates `EXTERNOUT` child TA.
- Resolves output name with `filename_formatter`.
- Writes file (append or overwrite behavior via `{overwrite}` token).
- Supports lock and safe rename patterns.

## Archive Behavior (`_comsession.archive`)

Archiving is channel-driven via `archivepath`.

Features:

- date-based path partitioning by default,
- optional zip archive mode (`archivezip` setting),
- optional external filename archival mode (`archiveexternalname` setting),
- per-channel/per-script overrides via `archivepath` and `archivename` hooks.

## Extension Points in Communication Scripts

Channel script files can provide:

- a channel-type class override (class name equals channel type),
- optional hooks and helper overrides used by base logic, for example:
  - `frommail`, `tomail`, `subject`, `headers`, `filename`,
  - `archivepath`, `archivename`.

These hooks are called with TA/channeldict context.

## Operational Notes

- Connection retries and inbound failure suppression are configurable (`rsrv1` and global settings).
- Inbound channels support max-run-time bounding per channel (`rsrv2` / global fallback).
- Debug mode can redirect stdout/stderr from protocol clients into structured logs.

