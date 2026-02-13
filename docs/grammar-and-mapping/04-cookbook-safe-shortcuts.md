# Cookbook: Safe Shortcuts and Patterns

Use this page as your copy-adapt-run toolbox.

## 1) Copy-through with Surgical Edits

Use when target output is mostly identical to input.

```python
import bots.transform as transform

def main(inn, out):
    transform.inn2out(inn, out)
    out.delete({'BOTSID': 'ST'}, {'BOTSID': 'REF', 'REF01': '87'})
```

Reference: `bots-plugins/x12/x12_837_4010_to_837_5010/usersys/mappings/x12/x12_837_4010_2_x12_837_5010.py`

## 2) Reliable Fallback for Multiple Qualifiers

Use when partners send one of several qualifier combinations.

```python
from bots import transform

buyer_id = transform.useoneof(
    party.get({'BOTSID': 'N1', 'N103': '92', 'N104': None}),
    party.get({'BOTSID': 'N1', 'N103': '91', 'N104': None}),
)
```

## 3) Date Mask Conversion

Use when source and target date formats differ.

```python
from bots import transform

normalized = transform.datemask(raw, 'CCYYMMDDHHMM', 'CCYY-MM-DD')
```

Reference: `orders_x122xml.py`

## 4) Helper for Repeating Qualifier Slots

Use when identifiers are spread across repeating element pairs.

```python
def get_art_num(node, qualifier, start=6, end=25):
    tag = node.record['BOTSID']
    pairs = [('%s%02d' % (tag, i), '%s%02d' % (tag, i + 1)) for i in range(start, end, 2)]
    for qual_element, id_element in pairs:
        result = node.get({'BOTSID': tag, qual_element: qualifier, id_element: None})
        if result:
            return result
    return None
```

Reference: `bots-plugins/usersys/mappings/x12/x12lib.py`

## 5) Stable Business Key in Trace

Use when you need fast document lookup and clean reconciliation.

```python
docnum = inn.get({'BOTSID': 'ST'}, {'BOTSID': 'BEG', 'BEG03': None})
inn.ta_info['botskey'] = docnum
out.ta_info['botskey'] = docnum
```

## 6) Partner Variant Wrapper

Use when one partner needs a small behavior delta.

```python
from . import asn_xml2x12_default

def main(inn, out):
    asn_xml2x12_default.main(inn, out)
    for shipment in out.getloop({'BOTSID': 'ST'}, {'BOTSID': 'HL', 'HL03': 'S'}):
        shipment.delete({'BOTSID': 'HL'}, {'BOTSID': 'DTM', 'DTM01': '017'})
```

Reference: `asn_xml2x12_partner2.py`

## 7) Chained Translation Branch

Use when one input needs an additional follow-up translation path.

```python
if inn.get({'BOTSID': 'UNH'}, {'BOTSID': 'BGM', '4343': 'AB'}):
    return 'edifactorders2aperak'
return None
```

Reference: `ordersedi2fixedchainaperak.py`

## 8) Controlled Party Mapping with Partner Lookup

Use when required IDs can be absent from payload.

```python
from bots import transform

if not inn.get({'BOTSID': 'message'}, {'BOTSID': 'partys'}, {'BOTSID': 'party', 'qual': 'BY'}):
    pou = shipment.putloop({'BOTSID': 'HL'}, {'BOTSID': 'N1'})
    pou.put({'BOTSID': 'N1', 'N101': 'BY', 'N102': transform.partnerlookup(inn.ta_info['topartner'], 'attr1')})
```

Reference: `asn_xml2x12_default.py`

## 9) Sender/Receiver Swap for Acknowledgements

Use when generating return acknowledgements back to sender.

```python
out.ta_info['topartner'] = inn.ta_info['frompartner']
out.ta_info['frompartner'] = inn.ta_info['topartner']
out.ta_info['testindicator'] = inn.ta_info['testindicator']
```

Reference: `ordersedi2aperak.py`

## 10) Loop-Safe Tree Writing

Use when writing repeated output records.

```python
for src_line in inn.getloop({'BOTSID': 'UNH'}, {'BOTSID': 'LIN'}):
    dst_line = out.putloop({'BOTSID': 'HEA'}, {'BOTSID': 'LIN'})
    dst_line.put({'BOTSID': 'LIN', 'LINENUMBER': src_line.get({'BOTSID': 'LIN', '1082': None})})
```

Rule: repeated output should almost always start with `putloop`.

## 11) Segment Count Recalculation After Structural Edits

Use when deleting/changing segments in X12.

```python
out.change(where=({'BOTSID': 'ST'}, {'BOTSID': 'SE'}), change={'SE01': str(out.getcount())})
```

Reference: `asn_xml2x12_partner2.py`

## 12) XML Tag Normalization from Numeric EDI Keys

Use when source keys violate XML naming rules.

```python
def tag2validxmltag(node):
    if node.record is not None:
        for key in list(node.record.keys()):
            if key not in ['BOTSID', 'BOTSIDnr']:
                node.record['_' + key.replace('#', '_')] = node.record.pop(key)
    for child in node.children:
        tag2validxmltag(child)
```

Reference: `edifactorder2xml.py`

## High-Confidence Shortcuts

- Start with a copy of the nearest successful mapping and delete until minimal.
- Build one helper module per editype for repeating qualifier/date/id logic.
- Keep partner customizations in wrapper scripts, not inline in base scripts.
- Add one field/loop at a time, then run the same fixture set immediately.
- Use `bots-grammarcheck` before chasing mapping errors caused by grammar defects.
