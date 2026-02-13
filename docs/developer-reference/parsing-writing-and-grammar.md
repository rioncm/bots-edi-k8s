# Parsing, Writing, and Grammar

This page documents the parser/serializer/grammar contracts in:

- `bots/bots/inmessage.py`
- `bots/bots/outmessage.py`
- `bots/bots/grammar.py`

## Incoming Parse Flow (`inmessage.py`)

### Dispatch entry point

`parse_edi_file(**ta_info)`:

1. Resolves class by `ta_info['editype']` (eg `edifact`, `x12`, `xml`, `json`, `fixed`, `csv`).
2. Instantiates message object.
3. Runs `initfromfile()`.
4. Converts fatal exceptions into `errorlist` entries.
5. Returns object even on parse failure; caller checks with `checkforerrorlist()`.

### `Inmessage.initfromfile()` lifecycle

1. `messagegrammarread('grammars')`
2. `_readcontent_edifile()`
3. `_sniff()` (editype-specific separators/metadata discovery)
4. `_lex()`
5. Optional `preprocess_lex` hook from syntax
6. `set_syntax_used()`
7. `_parse(...)` to build `Node` tree
8. `checkenvelope()`
9. `checkmessage(...)` validation/canonicalization
10. Query extraction into `ta_info`

### Message splitting (`nextmessage`)

`Inmessage.nextmessage()` yields message objects for mapping based on grammar options:

- `nextmessage`: path-driven split (primary mechanism).
- `nextmessage2`: secondary split path (used by some envelopes, eg EDIFACT variants).
- `nextmessageblock`: group contiguous flat rows by key function.
- No split rule:
  - Pass full root if root has record or `pass_all=True`.
  - Else emit root children one by one.

Each yielded message gets:

- `message_number`
- `total_number_of_messages`
- `bots_accessenvelope` (full envelope/root context)

## Outgoing Write Flow (`outmessage.py`)

### Dispatch entry point

`outmessage_init(**ta_info)` resolves class by outgoing `editype`.

### `Outmessage.writeall()` lifecycle

1. `messagegrammarread('grammars')`
2. `checkmessage(...)` (structure + field constraints)
3. `checkforerrorlist()`
4. Write one tree or many root children depending on root shape
5. Set `nrmessages` where applicable

### Serialization path

For most structured editypes:

1. `tree2records(...)` flattens node tree to lex records.
2. `record2string(...)` formats separators, escapes, quotes, and line endings.
3. `_write(...)` writes to stream, with optional `wrap_length`.

Specialized writers:

- `xml`/`xmlnocheck`: ElementTree serialization with optional prolog/doctype/PI/indent.
- `json`/`jsonnocheck`: node-to-object serialization with optional list wrapping and indent.
- `templatehtml`: renders via Genshi or Django templates.
- `db`: pickles arbitrary object from `out.root`.
- `raw`: writes raw byte stream from `out.root`.

## Grammar Loading and Validation (`grammar.py`)

### Entry point

`grammarread(editype, grammarname, typeofgrammarfile)`:

- `typeofgrammarfile='grammars'`:
  - Loads message grammar.
  - Builds syntax in this order:
    1. editype default syntax
    2. envelope grammar syntax (if present)
    3. message grammar syntax
- `typeofgrammarfile='envelope'`:
  - Resolves envelope grammar for outgoing enveloping.
- `typeofgrammarfile='partners'`:
  - Loads syntax-only partner overrides.

### Grammar parts

A grammar module can define:

- `syntax` (dict)
- `structure` (single-root list of record/group dicts)
- `recorddefs` (dict record id -> field list)
- split options:
  - `nextmessage`
  - `nextmessage2`
  - `nextmessageblock`

### Validation performed by `Grammar`

- `recorddefs` integrity:
  - Required shape and types.
  - `BOTSID` presence.
  - Field uniqueness.
  - Composite/subfield correctness.
  - Format normalization via `formatconvert`.
- `structure` integrity:
  - Exactly one root record.
  - Required keys (`ID`, `MIN`, `MAX`).
  - `MIN <= MAX`, `MAX > 0`.
  - Adds `MPATH`.
- Links recorddefs to structure.
- Collision checks (when enabled):
  - back-collision
  - nested collision
  - same-level tag collisions (`BOTSIDnr` assignment)

## Editype Classes and Defaults

Major grammar subclasses include:

- `csv`, `excel`
- `fixed`, `idoc`
- `edifact`
- `x12`
- `tradacoms`
- `xml`, `xmlnocheck`
- `json`, `jsonnocheck`
- `templatehtml`

Notable defaults:

- `edifact` and `x12` use `lengthnumericbare=True` and `stripfield_sep=True`.
- `xml` and `json` disable collision checks.
- `xmlnocheck` and `jsonnocheck` set `has_structure=False` for permissive handling.
- `fixed` enforces consistent BOTSID position across record definitions.

## Numeric and Field Formatting Semantics

Formatting is grammar-driven (`BFORMAT` internalized from `FORMAT`):

- Alphanumeric: `A`
- Date/time: `D`, `T`
- Numeric:
  - `R` floating decimal
  - `N` fixed decimal
  - `I` implicit decimal

Outgoing conversion rules include:

- rounding/quantization for `N`
- scale shifting for `I`
- optional JSON numeric typing via `json_write_numericals`

## Practical Guidance

- Keep grammar split rules (`nextmessage*`) explicit and minimal.
- Use partner syntax overrides only for partner-specific separators/identifiers.
- Prefer checked variants (`xml`, `json`) unless intentionally ingesting non-conforming payloads.
- Treat `has_structure=False` grammars as integration boundary adapters, not core canonical formats.

