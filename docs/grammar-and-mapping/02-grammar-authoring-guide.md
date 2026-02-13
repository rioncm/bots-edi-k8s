# Grammar Authoring Guide

This guide focuses on creating and evolving Bots grammar files with low risk and fast feedback.

## Grammar Contract in Bots

A message grammar module normally contains:

- `syntax` (dict): separators, envelope behavior, charset, merge options, etc.
- `structure` (list): segment/tree hierarchy with `ID`, `MIN`, `MAX`, `LEVEL`.
- `recorddefs` (dict): field definitions per record.
- Optional split controls:
  - `nextmessage`
  - `nextmessage2`
  - `nextmessageblock`

Core loading path:

- Bots imports from `usersys/grammars/<editype>/<messagetype>.py`.
- Grammar syntax is composed from defaults + envelope + message syntax.

Reference implementation details:

- `bots/bots/grammar.py`
- `docs/developer-reference/parsing-writing-and-grammar.md`

## File Placement Patterns

- Message grammar: `usersys/grammars/edifact/ORDERSD96AUNEAN008.py`
- Envelope grammar: `usersys/grammars/edifact/envelope.py`
- Shared recorddefs module: `usersys/grammars/edifact/recordsD96AUN.py`

Repo examples:

- `bots-plugins/usersys/grammars/edifact/ORDERSD96AUNEAN008.py`
- `bots-plugins/usersys/grammars/edifact/envelope.py`
- `bots-plugins/usersys/grammars/x12/850004010.py`
- `bots-plugins/usersys/grammars/xml/orders.py`

## Minimal Grammar Template

```python
from bots.botsconfig import *

syntax = {
    'charset': 'us-ascii',
}

structure = [
    {ID: 'ROOT', MIN: 1, MAX: 1, LEVEL: [
        {ID: 'HDR', MIN: 1, MAX: 1},
        {ID: 'LIN', MIN: 0, MAX: 99999},
    ]},
]

recorddefs = {
    'ROOT': [
        ['BOTSID', 'M', 255, 'A'],
    ],
    'HDR': [
        ['BOTSID', 'M', 255, 'A'],
        ['DOCNUM', 'M', 35, 'AN'],
    ],
    'LIN': [
        ['BOTSID', 'M', 255, 'A'],
        ['LINE', 'C', 6, 'N'],
        ['QTY', 'C', 16.3, 'N'],
    ],
}
```

## `recorddefs` Done Right

Required habits:

- Always include `BOTSID` in every record definition.
- Keep field names stable and explicit.
- Keep lengths realistic; avoid oversized “just in case” values.
- Use optional (`'C'`) for fields that are not guaranteed in production input.

Useful format reminders:

- Alphanumeric: `A`, `AN`
- Date/time: `D`, `T` (or editype variants like `DT`, `TM`)
- Numeric: `R`, `N`, `I` (converted internally per editype rules)

Safe shortcut: copy a field definition from a known nearby message and only adjust name/length when needed.

## `structure` Done Right

`structure` controls validation and looping behavior.

Rules that prevent most runtime errors:

- Exactly one logical root list entry.
- Keep `MIN`/`MAX` close to real business constraints.
- Nest loops only when hierarchy is actually required.
- Avoid “everything optional” root sections.

Example pattern from real EDIFACT/X12 grammars:

- Envelope level provides partner/query context.
- Message level contains business records and loops.

## QUERIES and SUBTRANSLATION

Use `QUERIES` to lift values into `ta_info` for mapping and routing.

Example usage in envelopes:

- EDIFACT envelope pulls `frompartner`, `topartner`, `testindicator`.
- X12 envelope pulls ISA/GS partner data and ST reference values.

Use `SUBTRANSLATION` to derive translation keys (often message type/version combinations).

Repo examples:

- `bots-plugins/usersys/grammars/edifact/envelope.py`
- `bots-plugins/usersys/grammars/x12/envelope.py`

## Split Controls: `nextmessage*`

When one file can contain multiple messages, split explicitly.

- `nextmessage`: primary split path.
- `nextmessage2`: secondary path (often grouped envelope variants).
- `nextmessageblock`: block grouping for flat/non-tree payloads.

If split logic is wrong, mappings will either see too much data or miss data entirely.

Safe shortcut: copy split definitions from a known envelope grammar and adapt only record IDs.

## Editype-Specific Tips

### EDIFACT

- Keep envelope and message grammars separated.
- Confirm UNH/UNT linkage in message structure.
- Use the envelope for partner extraction and subtranslation keys.

### X12

- Let envelope grammar define ISA/GS/ST split context.
- Keep `functionalgroup` and version syntax explicit where required.
- Validate control number fields lengths carefully.

### XML / JSON

- Prefer checked grammars (`xml`, `json`) unless ingesting very loose input.
- Use `xmlnocheck`/`jsonnocheck` intentionally as adapters, not canonical cores.

### Fixed / CSV

- Treat widths/precision as contractual.
- Validate decimal precision early with real files.

## Validation Workflow

1. Save grammar in the correct `usersys/grammars/<editype>/` folder.
2. Run grammar check:

```bash
bots-grammarcheck -cbots_config <editype> <messagetype>
```

3. Fix structural/field errors before mapping work.
4. Re-run check after every meaningful grammar edit.

Tip: grammar stability first, mapping second. This gives faster feedback loops.

## Common Failure Modes

- `BotsImportError`: wrong file path/module name.
- `GrammarError`: invalid `recorddefs` or `structure` shape.
- Missing data in mapping `inn.ta_info`: missing/wrong `QUERIES` in envelope/message grammar.
- Unexpected message splitting: incorrect `nextmessage` path.

## Safe Shortcuts

- Start from the nearest working grammar in the same `editype`.
- Reuse shared `recorddefs` modules where possible.
- Add new records as optional first (`MIN: 0`), then tighten when samples confirm behavior.
- Keep one “golden” fixture file per message variant and run grammar check against each variant after edits.
