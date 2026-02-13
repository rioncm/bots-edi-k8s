# Quickstart: First Grammar and Mapping

This walkthrough gets you to a working translation quickly, using stable Bots patterns.

## Outcome

You will build:

- A simple outgoing fixed grammar.
- A Python mapping from EDIFACT `ORDERS` to that fixed format.
- A route-ready script pair you can evolve safely.

## Prerequisites

- Bots is configured and can run (`bots-engine`).
- You know your active `usersys` folder from `bots.ini`.
- You have a sample incoming order message.

## Step 1: Choose a Reference Pair

Start from a known working pair and trim it.

Recommended reference in this repo:

- Grammar: `bots-plugins/demo/my_first_plugin/usersys/grammars/fixed/ordersfixed.py`
- Mapping: `bots-plugins/demo/my_first_plugin/usersys/mappings/edifact/myfirstscriptordersedi2fixed.py`

Safe shortcut: clone the closest working files first, then remove fields. Do not start blank unless the format is truly new.

## Step 2: Create Your Outgoing Grammar

Create `usersys/grammars/fixed/orders_intro.py`.

```python
from bots.botsconfig import *

syntax = {
    'charset': 'us-ascii',
}

structure = [
    {ID: 'HEA', MIN: 1, MAX: 99999, LEVEL: [
        {ID: 'LIN', MIN: 0, MAX: 99999},
    ]},
]

recorddefs = {
    'HEA': [
        ['BOTSID', 'C', 3, 'A'],
        ['ORDERNUMBER', 'M', 35, 'AN'],
        ['SENDER', 'C', 35, 'AN'],
        ['RECEIVER', 'C', 35, 'AN'],
        ['ORDERDATE', 'C', 8, 'AN'],
    ],
    'LIN': [
        ['BOTSID', 'C', 3, 'A'],
        ['LINENUMBER', 'C', 6, 'N'],
        ['ARTICLE', 'C', 35, 'AN'],
        ['QUANTITY', 'C', 16.3, 'N'],
    ],
}
```

Tip: keep `recorddefs` minimal at first. Every extra field increases validation surface.

## Step 3: Create Your Mapping Script

Create `usersys/mappings/edifact/orders_intro.py`.

```python
# mapping-script

def main(inn, out):
    out.put({'BOTSID': 'HEA', 'SENDER': inn.ta_info.get('frompartner', '')})
    out.put({'BOTSID': 'HEA', 'RECEIVER': inn.ta_info.get('topartner', '')})

    order_number = inn.get({'BOTSID': 'UNH'}, {'BOTSID': 'BGM', '1004': None})
    out.put({'BOTSID': 'HEA', 'ORDERNUMBER': order_number})
    out.ta_info['botskey'] = order_number

    out.put({
        'BOTSID': 'HEA',
        'ORDERDATE': inn.get(
            {'BOTSID': 'UNH'},
            {'BOTSID': 'DTM', 'C507.2005': '137', 'C507.2380': None},
        ),
    })

    for lin in inn.getloop({'BOTSID': 'UNH'}, {'BOTSID': 'LIN'}):
        lou = out.putloop({'BOTSID': 'HEA'}, {'BOTSID': 'LIN'})
        lou.put({'BOTSID': 'LIN', 'LINENUMBER': lin.get({'BOTSID': 'LIN', '1082': None})})
        lou.put({'BOTSID': 'LIN', 'ARTICLE': lin.get({'BOTSID': 'LIN', 'C212.7140': None})})
        lou.put({
            'BOTSID': 'LIN',
            'QUANTITY': lin.get(
                {'BOTSID': 'LIN'},
                {'BOTSID': 'QTY', 'C186.6063': '21', 'C186.6060': None},
            ),
        })
```

Tip: put your business key in `out.ta_info['botskey']` so trace/document views are useful.

## Step 4: Wire Translation and Route

In your Bots configuration (GUI or DB), wire:

1. Incoming message type `ORDERS...` (EDIFACT) to translation script `orders_intro`.
2. Outgoing message type `orders_intro` (fixed editype).
3. Route/channel for your test run.

Safe shortcut: duplicate a working translation row and only change script/message type fields.

## Step 5: Validate Early

Run a grammar check before end-to-end processing.

```bash
bots-grammarcheck -cbots_config fixed orders_intro
```

Then run translation:

```bash
bots-engine --new
```

If your config dir is not `bots_config`, replace `-cbots_config` with your config path.

## Step 6: Tighten Incrementally

- Add one field at a time.
- Re-run with the same input set after each change.
- Keep a known-good baseline mapping script for fast rollback.

## First-Week Upgrade Path

1. Add date normalization with `transform.datemask`.
2. Move repeated logic into helper functions/modules.
3. Add partner variants by wrapping the base mapping.
4. Add a regression fixture set and automate a daily check run.
