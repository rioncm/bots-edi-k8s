# Grammar and Mapping Mastery

This guide set is for Python developers building Bots EDI grammars and translation scripts in real projects.
It takes you from your first working flow to partner-specific, production-safe mapping.

## Who This Is For

- Developers writing or maintaining `usersys/grammars/*` files.
- Developers writing mapping scripts in `usersys/mappings/*`.
- Teams standardizing EDI onboarding patterns across partners.

## Where Your Files Go

Bots resolves user extensions from the `usersys` directory configured in `bots.ini` (`[directories] usersys = ...`).

```text
usersys/
  grammars/
    <editype>/
      <messagetype>.py
      envelope.py
      <shared-recorddefs>.py
  mappings/
    <from_editype>/
      <translation_script>.py
      <helper_module>.py
```

In this repository, many complete examples live under `bots-plugins/*/usersys/...`.

## Learning Path

1. [Quickstart: First Grammar and Mapping](01-quickstart-first-grammar-and-map.md)
2. [Grammar Authoring Guide](02-grammar-authoring-guide.md)
3. [Mapping Authoring Guide](03-mapping-authoring-guide.md)
4. [Cookbook: Safe Shortcuts and Patterns](04-cookbook-safe-shortcuts.md)
5. [Debugging, Testing, and Hardening](05-debugging-testing-and-hardening.md)

## Mastery Milestones

Use these milestones to track skill growth:

1. Starter: ship one single-message mapping with a validated grammar.
2. Practitioner: handle loops, qualifiers, and date/number conversions confidently.
3. Advanced: split shared/base mappings from partner-specific wrappers.
4. Expert: implement chained translations and robust acknowledgement flows.
5. Master: maintain fixture-driven regression coverage and promote changes safely.

## Real Example Files In This Repo

- Fixed grammar + beginner mapping:
  - `bots-plugins/demo/my_first_plugin/usersys/grammars/fixed/ordersfixed.py`
  - `bots-plugins/demo/my_first_plugin/usersys/mappings/edifact/myfirstscriptordersedi2fixed.py`
- X12 mapping with loops, helper module, and date conversion:
  - `bots-plugins/x12/x12_to_xml_supplier_version_850-856-810-997/usersys/mappings/x12/orders_x122xml.py`
  - `bots-plugins/usersys/mappings/x12/x12lib.py`
- Partner variant pattern (base mapping + override):
  - `bots-plugins/demo/working_with_partners/usersys/mappings/xml/asn_xml2x12_default.py`
  - `bots-plugins/demo/working_with_partners/usersys/mappings/xml/asn_xml2x12_partner2.py`
- Envelope/message split behavior:
  - `bots-plugins/usersys/grammars/edifact/envelope.py`
  - `bots-plugins/usersys/grammars/x12/envelope.py`

## Safe Workflow (Fast and Reliable)

1. Start from the closest existing grammar/mapping in the same `editype`.
2. Make the smallest possible change set to get a first passing run.
3. Validate grammar early with `bots-grammarcheck`.
4. Add partner-specific behavior in a thin wrapper mapping, not in your base mapping.
5. Keep helper logic in sibling modules and import them (`from .x12lib import ...`).
6. Only optimize after traces are clean and deterministic.

## Companion Reference

Use these when you need implementation-level details:

- [`docs/developer-reference/message-tree-and-mapping-api.md`](../developer-reference/message-tree-and-mapping-api.md)
- [`docs/developer-reference/parsing-writing-and-grammar.md`](../developer-reference/parsing-writing-and-grammar.md)
- [`docs/developer-reference/runtime-routing-and-enveloping.md`](../developer-reference/runtime-routing-and-enveloping.md)
