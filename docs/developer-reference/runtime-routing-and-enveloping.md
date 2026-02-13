# Runtime Routing and Enveloping

This page documents runtime orchestration in:

- `bots/bots/engine.py`
- `bots/bots/router.py`
- `bots/bots/preprocess.py`
- `bots/bots/envelope.py`

## Engine Entrypoint (`engine.py`)

`start()` is the CLI runtime entrypoint.

### Supported run options

- `--new`
- `--resend`
- `--rereceive`
- `--automaticretrycommunication`
- `--cleanup`
- `-c<config_dir>`
- Optional route ids to restrict execution.

### Exit codes

- `0`: successful run with no processing errors.
- `1`: fatal/system failure.
- `2`: run completed but with route/process errors.
- `3`: engine lock/port conflict (another instance active).

### Core startup flow

1. Parse CLI options.
2. `botsinit.generalinit(configdir)`.
3. Enforce single engine via local port bind.
4. Initialize logging.
5. Connect DB.
6. Load global route script hooks (`routescripts/botsengine.py`) if present.
7. Handle DB lock / crash recovery insertion.
8. Execute commands in sequence via `router.rundispatcher`.
9. Run cleanup and exit with code by result.

## Router Execution (`router.py`)

### Dispatcher

`rundispatcher(command, routestorun)`:

- Resolves class by command (`new`, `crashrecovery`, `resend`, etc).
- Executes `run()` then `evaluate()`.

### `new.router(route)` behavior

For each active route row (ordered by `seq`):

1. Load optional route script (`routescripts/<route>.py`).
2. Build `routedict`.
3. Execute `routepart(routedict)`.

### Route part execution order (`new.routepart`)

If route script has `main`, that short-circuits default flow.
Otherwise, default flow is:

1. Optional `start` route hook.
2. Incoming communication (`communication.run`) if `fromchannel` is set.
3. Apply route metadata to incoming TA rows.
4. Optional unzip (`zip_incoming` behavior).
5. Optional `mailbag` preprocessing for selected editypes.
6. Translation + merge path when `translateind in [1, 3]`:
   - `transform.translate(FILEIN -> TRANSLATED)`
   - `envelope.mergemessages(TRANSLATED -> MERGED)`
7. Pass-through path when `translateind == 2` (`FILEIN -> MERGED`).
8. Outgoing assignment (`MERGED -> FILEOUT`) for route/channel target.
9. Set confirm requests where configured.
10. Optional outgoing zip postprocess (`zip_outgoing`).
11. Outgoing communication (`communication.run`) unless deferred.
12. Normalize leftover `FILEOUT/OK` to `EXTERNOUT/ERROR` after comm attempt.
13. Optional `end` route hook.

## Pre/Post Processing (`preprocess.py`)

### Generic wrappers

- `preprocess(...)`: applies function to inbound TA rows (`FILEIN` by default).
- `postprocess(...)`: applies function to outbound TA rows (`FILEOUT` by default).

Both wrappers:

- Iterate matching TA rows.
- Create child transactions through function behavior.
- Mark source rows `DONE` on success.
- Mark `ERROR` and delete children on failure.

### Built-in processors

- `mailbag(...)`:
  - Detects and splits mixed EDIFACT/X12/TRADACOMS interchanges.
  - Also supports XML sniff fallback when configured as mailbag input.
- `botsunzip(...)`:
  - Extracts zip entries into child files.
  - Can pass non-zip files unchanged when `pass_non_zip=True`.
- `botszip(...)`:
  - Zips outgoing file content.
- `extractpdf(...)`:
  - PDF-to-CSV extraction helper (uses `pdfminer`).

## Enveloping and Merge (`envelope.py`)

### `mergemessages(startstatus, endstatus, idroute, rootidta, **kwargs)`

Two passes:

1. `merge=False`: envelope each message individually.
2. `merge=True`: group by envelope-relevant keys and merge into one output.

Grouping keys include:

- `editype`, `messagetype`, `envelope`, `rsrv3`,
- partner/test/charset fields,
- syntax metadata bucket `rsrv5`.

### Envelope class resolution

`envelope(ta_info, ta_list, **kwargs)` resolves in this order:

1. no envelope -> `noenvelope`
2. user envelope script class in `envelopescripts/<editype>/<envelope>.py`
3. built-in class by `editype` (`edifact`, `x12`, `tradacoms`, etc)

### Built-in envelope behaviors

- `noenvelope`: copy/single-file passthrough.
- `csv` with `envelope='csvheader'`: emits field-name row before payload.
- `edifact`:
  - Builds `UNB`/`UNZ`, optional `UNA`, reference counters, test indicator logic.
- `x12`:
  - Builds ISA/GS/GE/IEA, applies fixed-length ISA rules and separator insertion.
- `tradacoms`:
  - Builds `STX`/`END` with counter/reference behavior.
- `json`:
  - Merges messages into a single JSON list.
- `templatehtml`:
  - Renders envelope template via Genshi or Django.

### Mapping -> envelope data bridge

`transform.handle_out_message` stores mapping-provided envelope context in `ta.rsrv5` as JSON:

- `envelope_content`
- `syntax`

`envelope.envelope(...)` loads this and passes it into envelope class initialization.

## Extension Hooks Summary

### Global engine script (`routescripts/botsengine.py`)

- `pre`, `post`, `pre<command>`, `post<command>`

### Per-route script (`routescripts/<route>.py`)

- `main` (override default routepart flow)
- `start`, `end`
- `preincommunication`, `postincommunication`
- `pretranslation`, `posttranslation`
- `premerge`, `postmerge`
- `preoutcommunication`, `postoutcommunication`

### Envelope scripts (`envelopescripts/...`)

- `ta_infocontent(ta_info=...)`
- `envelopecontent(ta_info=..., out=...)`

