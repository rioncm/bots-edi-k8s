# Mapping Authoring Guide

This guide shows how to write maintainable Bots mapping scripts that survive partner growth and format drift.

## Mapping Script Contract

Location pattern:

- `usersys/mappings/<from_editype>/<translation_script>.py`

Entry point:

```python
def main(inn, out):
    ...
```

`inn` and `out` are Bots `Message` objects. Most work happens through:

- `get`, `getloop` on `inn`
- `put`, `putloop`, `change`, `delete` on `out`

Deep API reference:

- `docs/developer-reference/message-tree-and-mapping-api.md`

## First Principles for Reliable Mappings

1. Extract only what you need.
2. Write output deterministically.
3. Keep partner-specific logic out of base mapping when possible.
4. Use helper functions/modules for repeated logic.

## Mpath Essentials

Mpaths are tuple-like path segments of dicts with `BOTSID` keys.

Read one value:

```python
docnum = inn.get({'BOTSID': 'UNH'}, {'BOTSID': 'BGM', '1004': None})
```

Iterate repeating loops:

```python
for lin in inn.getloop({'BOTSID': 'UNH'}, {'BOTSID': 'LIN'}):
    ...
```

Write one record:

```python
out.put({'BOTSID': 'HEA', 'ORDERNUMBER': docnum})
```

Write repeating loop record:

```python
lou = out.putloop({'BOTSID': 'HEA'}, {'BOTSID': 'LIN'})
lou.put({'BOTSID': 'LIN', 'LINENUMBER': '1'})
```

Tip: include discriminators (qualifiers, IDs) in your mpaths to avoid first-match mistakes.

## Core Read/Write Patterns

### Header + line mapping pattern

From `bots-plugins/demo/my_first_plugin/usersys/mappings/edifact/myfirstscriptordersedi2fixed.py`:

- Read header fields once.
- Loop `LIN` segments.
- Create one output loop row per source line.

### Complex hierarchical loop pattern

From `bots-plugins/demo/working_with_partners/usersys/mappings/xml/asn_xml2x12_default.py`:

- Build HL hierarchy with counters.
- Keep parent IDs explicit.
- Recalculate trailer counts at the end.

### Safe passthrough + targeted changes

From `bots-plugins/x12/x12_837_4010_to_837_5010/usersys/mappings/x12/x12_837_4010_2_x12_837_5010.py`:

```python
import bots.transform as transform

def main(inn, out):
    transform.inn2out(inn, out)
    out.delete({'BOTSID': 'ST'}, {'BOTSID': 'REF', 'REF01': '87'})
```

This is the fastest low-risk way to implement small deltas.

## `ta_info` and Traceability

Use metadata intentionally:

- `inn.ta_info['frompartner']`, `inn.ta_info['topartner']`, `inn.ta_info['testindicator']`
- `out.ta_info['botskey']` for business-key traceability

Pattern from supplier order mapping:

- `orders_x122xml.py` sets both `inn.ta_info['botskey']` and `out.ta_info['botskey']` using document number.

Safe shortcut: always set one stable document identifier as `botskey` early.

## High-Value `transform` Helpers

Common helpers from `bots/bots/transform.py`:

- `transform.inn2out(inn, out)`
- `transform.datemask(value, frommask, tomask)`
- `transform.useoneof(*values)`
- `transform.ccode(...)`
- `transform.partnerlookup(...)`

Example date normalization:

```python
from bots import transform

docdtm = transform.datemask(raw_date, 'CCYYMMDDHHMM', 'CCYY-MM-DD')
```

Example fallback value selection:

```python
uom = transform.useoneof(po1.get({'BOTSID': 'PO1', 'PO103': None}), 'EA')
```

## Helper Modules

Keep mapping scripts short by moving reusable logic into sibling modules.

Example:

- `bots-plugins/usersys/mappings/x12/x12lib.py`
- Imported by `orders_x122xml.py` as `from .x12lib import get_art_num`

Safe shortcut: if you paste the same qualifier lookup twice, move it to a helper.

## Chained Mappings (Advanced)

`main()` return values control chaining behavior:

- `None`: done
- `str`: next `alt` translation
- `dict` with `type` for advanced chaining (`out_as_inn`, loop-check override)

Real example:

- `ordersedi2fixedchainaperak.py` returns `'edifactorders2aperak'` based on input content.

Use chaining for explicit workflow branches only. Keep normal cases returning `None`.

## Partner Variant Strategy

Preferred pattern:

1. Build a clean base mapping.
2. Create partner-specific wrapper script.
3. Call base mapping first, then apply overrides.

Example:

- Base: `asn_xml2x12_default.py`
- Variant: `asn_xml2x12_partner2.py`

Benefits:

- Shared behavior stays centralized.
- Partner deltas are easier to review and test.

## Defensive Mapping Practices

- Validate critical assumptions with explicit checks and clear exceptions.
- Avoid hidden mutation of shared structures.
- Recalculate trailer/control counts after structural edits.
- Keep numeric/date conversions explicit; never rely on implicit source formatting.

## Common Pitfalls

- Using `get` on wrong loop context (returns first unrelated match).
- Writing line-level data with `out.put` instead of `out.putloop` (overwrites data).
- Mixing partner-specific logic throughout base script.
- Not resetting/recomputing segment counts after `change`/`delete`.

## Safe Shortcuts

- For tiny diffs: `inn2out` then `delete`/`change`.
- For partner fork: wrapper mapping calling base mapping.
- For repeated qualifier patterns: helper function in sibling module.
- For uncertain source value presence: `transform.useoneof` with explicit fallback.
