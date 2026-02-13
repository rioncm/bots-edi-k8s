# Message Tree and Mapping API

This page documents the core mapping-facing APIs in:

- `bots/bots/transform.py`
- `bots/bots/message.py`
- `bots/bots/node.py`

## Core Objects

### `Message`

`Message` is the abstract base for incoming and outgoing messages.

Important attributes:

- `ta_info`: metadata and processing context.
- `root`: root `Node` of the message tree.
- `errorlist`: non-fatal validation/parsing errors collected before raising.

Important behavior:

- `checkforerrorlist()` raises if accumulated errors exist.
- Wrapper methods (`get`, `put`, `getloop`, `delete`, `sort`, etc) delegate to `Node`.
- For split messages, `Message` may use a dummy root (no record, children only). In that case,
  methods like `get` and `change` raise `MappingRootError` with guidance to use loops.

### `Node`

`Node` is the in-memory tree element:

- `record`: dict containing fields plus `BOTSID` and `BOTSIDnr`.
- `children`: child `Node` list.
- `queries`: inherited/extracted context.

#### Mpath contract

Mpaths are tuples of dicts; each dict must include `BOTSID`.
Examples:

```python
({'BOTSID': 'UNH'}, {'BOTSID': 'LIN', 'C212.7140': None})
```

Rules enforced by `Node`:

- Keys must be strings.
- Values are generally strings.
- In `get(...)`, at most one `None` is allowed in the final path part and means "return this field".
- `BOTSIDnr` defaults to `'1'` when omitted.

#### High-value `Node` methods

- `get(*mpaths) -> str | int | None`
  - Returns first matching value.
  - Returns `1` when no `None` selector is used and match succeeds.
- `getloop(*mpaths) -> generator[Node]`
  - Iterates all matching nodes.
- `getloop_including_mpath(*mpaths)`
  - Like `getloop`, but returns ancestor path context plus node.
- `put(*mpaths, strip=True) -> bool`
  - Upserts along path; can return `False` on empty/`None` values.
- `putloop(*mpaths) -> Node`
  - Creates a new occurrence at loop end and returns that node.
- `change(where, change) -> bool`
- `delete(*mpaths) -> bool`
- `sort(..., sortfrom=..., compare=..., reverse=False, sort_decimal=False, sort_if_none='...')`

#### Query propagation utilities

- `processqueries(queries, maxlevel)`: pushes query context downward.
- `enhancedget(...)`: supports dict/tuple/list/function/string selectors for grammar `QUERIES`,
  `SUBTRANSLATION`, and `nextmessageblock`.

## Translation Pipeline Contract (`transform.py`)

### Entry point

`translate(startstatus, endstatus, routedict, rootidta)`:

1. Selects candidate TA rows in `startstatus`.
2. Calls `_translate_one_file` for each.

### `_translate_one_file` lifecycle

For each input file:

1. Parse input via `inmessage.parse_edi_file(...)`.
2. Validate parse (`checkforerrorlist()`).
3. Split into messages (`edifile.nextmessage()`).
4. Resolve translation mapping via:
   - DB translate table (`botslib.lookup_translation`) first.
   - Optional user script fallback `mappings/translation.py:gettranslation`.
5. Instantiate outgoing message via `outmessage.outmessage_init(...)`.
6. Run mapping script `main(inn=..., out=...)`.
7. Handle chaining behavior from the mapping return value.
8. Write output with `handle_out_message(...)`.

### Mapping script return value semantics

`main(...)` can return:

- `None`:
  - Normal completion for current message.
- `str`:
  - Treated as new `alt` for chained translation.
- `dict` with special `type`:
  - `{'type': 'out_as_inn', 'alt': '...'}`:
    - Writes current out message, then uses it as next input message.
  - `{'type': 'no_check_on_infinite_loop', 'alt': '...'}`:
    - Allows repeated same-alt chaining without loop guard.

Loop guard:

- Returning the same `alt` repeatedly triggers a safety error after >10 loops unless using
  `no_check_on_infinite_loop`.

### `handle_out_message(out_translated, ta_translated)`

- If `out.ta_info['statust'] == DONE`:
  - Message is explicitly discarded (`status=DISCARD`, no filename).
- Otherwise:
  - Calls `out.writeall()`.
  - Computes output file size.
  - Stores mapping-derived envelope/syntax metadata in `rsrv5` (JSON) for later enveloping.

## Mapping Helper Functions (`transform.py`)

### Persistence and conversion helpers

- `persist_add`, `persist_update`, `persist_add_update`, `persist_delete`, `persist_lookup`
- `ccode`, `reverse_ccode`, `getcodeset`
- `partnerlookup`
- `unique`, `unique_runcounter`

`safe` behavior for lookup helpers:

- `safe=True`: return original input when not found.
- `safe=False`: raise conversion error.
- `safe=None`: return `None`.

### Utility helpers used in mappings

- `inn2out(inn, out)`: safe node copy (`copynode`), not shared reference.
- `useoneof(*args)`: first truthy value.
- `dateformat(date)`: EDIFACT date format code from length.
- `datemask(value, frommask, tomask)`: position-based mask conversion.
- `truncate(maxpos, value)`.
- `concat(*args, sep='')`.
- `dropdiacritics(content, charset='ascii')`.
- `chunk(sequence, size)` generator.

## Error and Failure Semantics

- Parse/format problems collect in `errorlist` until checked.
- Mapping/serialization exceptions usually mark split TA rows `ERROR` and continue,
  unless `KillWholeFile` semantics are active.
- `ParsePassthroughException` path marks parsed file as passed-through to `MERGED`.

## Practical Guidance

- Use `putloop` when creating repeated loop segments; use `put` for deterministic upsert.
- Keep mpaths explicit and include enough discriminator fields to avoid first-match surprises.
- Use `inn.getloop(...)` for split-root inputs; avoid root-level `get` on dummy roots.
- Prefer returning `None` from mapping scripts unless chained translation is intentional.

