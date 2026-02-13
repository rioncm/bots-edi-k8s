# Platform Utilities and Scripts

This page documents shared utility APIs and operational scripts:

- `bots/bots/botslib.py`
- `scripts/healthcheck.py`
- `scripts/init-database.py`
- `bots/bots/engine2.py` (specialized utility runtime)

## `botslib.py` Core APIs

`botslib` is the central utility layer used across routing, transformation, communication, and engine code.

## Transaction API (`ta` table)

### Classes

- `_Transaction` (base)
- `OldTransaction(idta)`
- `NewTransaction(**ta_info)`
- `NewProcess(functionname='')`
- `ErrorProcess(...)`

### High-use methods

- `update(**ta_info)`
- `copyta(status, **ta_info)` (clone existing TA into new phase/status)
- `delete()`
- `deletechildren()`
- `syn(...)`, `synall()`

`NewProcess` pushes process ids to `_Transaction.processlist`; `update()` pops when complete.

## Database Helpers

- `query(sql, *args)` -> generator of dict-like rows
- `changeq(sql, *args)` -> execute update/delete, returns affected rows
- `insertta(sql, *args)` -> insert and return new id (supports DB-specific id retrieval)
- `addinfo`, `addinfocore`
- `updateinfo`, `updateinfocore`
- `changestatustinfo`

These helpers are the foundation for status transitions throughout the pipeline.

## Unique Counters

- `unique(domain, updatewith=None)`:
  - persistent counter in DB table `uniek`
- `unique_runcounter(domain, updatewith=None)`:
  - in-memory per-run counter
- `checkunique(domain, receivednumber)`:
  - verifies expected sequence and rolls back counter on mismatch

## Dynamic Import and Script Execution

- `botsbaseimport(modulename)`
- `botsimport(*args)`:
  - imports user-space modules from configured usersys path.
- `runscript(module, modulefile, functioninscript, **argv)`
- `tryrunscript(...)`
- `runscriptyield(...)`

Error wrappers:

- import failures -> `BotsImportError` / `ScriptImportError`
- runtime failures in user scripts -> `ScriptError`

## File and Path Helpers

- `join(*paths)` -> normalized path rooted in configured `botsenv`.
- `abspath(section, filename)`
- `abspathdata(filename)` -> internal data storage path convention.
- `opendata`, `readdata` (text)
- `opendata_bin`, `readdata_bin` (binary)
- `readdata_pickled`, `writedata_pickled`
- `dirshouldbethere(path)`
- `rreplace(...)`

## Confirm/Ack Rules

- `prepare_confirmrules()`
- `checkconfirmrules(confirmtype, **kwargs)`
- `set_asked_confirmrules(routedict, rootidta)`

Used for behavior like EDIFACT CONTRL, X12 997, and email MDN workflows.

## Misc Runtime Utilities

- `set_database_lock()`, `remove_database_lock()`
- `check_if_other_engine_is_running()`
- `trace_origin(ta, where=None)`
- `countoutfiles(idchannel, rootidta)`
- `lookup_translation(...)`
- `botsinfo()`, `botsinfo_display()`
- `datetime()`, `strftime()` (acceptance-mode-aware clock behavior)

## Health Check Script (`scripts/healthcheck.py`)

CLI usage:

```bash
python scripts/healthcheck.py --check live|ready|startup [--config-dir ...] [--json] [--quiet]
```

Exit codes:

- `0`: healthy
- `1`: unhealthy
- `2`: script/setup error

Checks:

- `live`:
  - process-level liveness only.
- `ready`:
  - DB connectivity;
  - optional directory checks (`botssys`, `usersys`);
  - `HEALTH_CHECK_DB_ONLY=true` enables DB-only mode.
- `startup`:
  - DB connectivity,
  - required tables,
  - config and directory initialization completeness.

## Database Initialization Script (`scripts/init-database.py`)

CLI usage:

```bash
python scripts/init-database.py [--config-dir ...] [--verbose]
```

Core workflow:

1. Initialize Django/Bots config.
2. Detect DB type (`sqlite`, `mysql`, `postgresql`).
3. Run Django migrations (managed tables).
4. Create unmanaged tables (`ta`, `mutex`, `persist`, `uniek`) from SQL files.
5. Verify required schema tables.

Designed to be idempotent:

- existing tables are detected and skipped.
- SQL statement-level failures are logged and processing continues where possible.

Exit code:

- `0` success
- `1` failure

## `engine2.py` (Specialized Non-GUI Runtime)

`engine2.py` is an alternate runtime path intended for controlled/custom scenarios:

- no normal DB-backed configuration flow for routes/channels,
- hard-coded control flow patterns,
- uses Bots parsing/mapping/enveloping primitives directly.

Use this as a reference for low-level orchestration experiments, not as the main production entrypoint.

