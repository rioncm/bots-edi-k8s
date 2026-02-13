# Debugging, Testing, and Hardening

This guide helps you diagnose failures quickly and promote mappings safely.

## Fast Triage Order

Always debug in this order:

1. Grammar load/validation
2. Parsing and splitting
3. Mapping logic
4. Writing/enveloping

If step 1 is unstable, step 3 debugging is usually wasted effort.

## Turn On Useful Debug Signals

In `bots.ini` (`[settings]`):

- `get_checklevel = 2` for strict mpath checking while developing.
- `mappingdebug = True` for detailed mapping logs.
- Ensure log levels include debug when actively diagnosing.

Relevant defaults/comments are documented in:

- `bots_config/bots.ini`
- `bots/bots/config/bots.ini`

## Validate Grammar Before Engine Runs

```bash
bots-grammarcheck -cbots_config <editype> <messagetype>
```

Examples:

```bash
bots-grammarcheck -cbots_config edifact ORDERSD96AUNEAN008
bots-grammarcheck -cbots_config fixed orders_intro
```

Tip: run this after every structural grammar edit.

## Repeatable Engine Test Runs

```bash
bots-engine --new
```

For custom config directory:

```bash
bots-engine -cbots_config --new
```

Use a stable fixture set so each run is comparable.

## Failure Pattern Matrix

### `BotsImportError` for grammar or mapping

Likely causes:

- Wrong module path/name.
- File not under configured `usersys` tree.
- Syntax/import error in target module.

Checks:

- Confirm `usersys` path in `bots.ini`.
- Confirm file naming matches configured script/messagetype.

### `GrammarError`

Likely causes:

- Invalid `recorddefs` field definition.
- `structure` record missing from `recorddefs`.
- Invalid `MIN`/`MAX` or malformed grammar constants.

Checks:

- Run `bots-grammarcheck`.
- Start from nearest known-good grammar and diff changes.

### Mapping succeeds partially with missing values

Likely causes:

- mpath points to wrong loop depth.
- qualifier condition too strict.
- source grammar split path or queries incorrect.

Checks:

- Verify `getloop` scope and discriminator fields.
- Add temporary mapping logging around critical `get` calls.
- Verify envelope/message `QUERIES` and `nextmessage*` definitions.

### Trailer/control count errors (X12/EDIFACT)

Likely causes:

- post-copy delete/change without recount update.

Checks:

- Recompute counters (`SE`, `UNT`) after structural edits.
- Compare against known-good output sample.

## Test Strategy That Scales

### Level 1: Grammar sanity

- One command per grammar with `bots-grammarcheck`.

### Level 2: Mapping fixture tests

- Keep representative input files per partner variant.
- Keep expected outputs (golden files) for deterministic diffs.
- Run engine and diff normalized output.

### Level 3: Route-level acceptance

- Reuse pattern from plugin acceptance scripts:
  - `bots-plugins/*/usersys/routescripts/bots_acceptancetest.py`

## Safe Promotion Workflow

1. Freeze input fixture pack for the target change.
2. Run grammar checks on all touched grammars.
3. Run base mapping fixtures.
4. Run partner-variant fixtures.
5. Compare outputs against golden baselines.
6. Promote to staging with unchanged fixtures.
7. Monitor first production run with enhanced logging.

## Hardening Guidelines

- Keep base and partner-specific logic separated.
- Use helper modules to remove duplicated business rules.
- Raise explicit exceptions when critical assumptions fail.
- Set `botskey` consistently for traceability and supportability.
- Avoid giant one-pass rewrites; ship in small validated increments.

## Advanced References

- Mapping API: `docs/developer-reference/message-tree-and-mapping-api.md`
- Parse/write/grammar internals: `docs/developer-reference/parsing-writing-and-grammar.md`
- Runtime orchestration: `docs/developer-reference/runtime-routing-and-enveloping.md`
