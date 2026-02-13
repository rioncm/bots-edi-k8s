# Developer Reference

This section documents the code-level APIs and runtime contracts that power Bots EDI in this repository.
It is written for experienced Python developers working on mappings, channel integrations, and runtime
extensions.

## Scope

This reference focuses on platform libraries and stable extension points in:

- `bots/bots/*`
- `minio_helper/app/*`
- `scripts/*`

It does not document every private helper in every module. Instead, it documents the public or
de-facto-public contracts you rely on when extending the platform.

## Read Order

1. [Message Tree and Mapping API](message-tree-and-mapping-api.md)
2. [Parsing, Writing, and Grammar](parsing-writing-and-grammar.md)
3. [Runtime Routing and Enveloping](runtime-routing-and-enveloping.md)
4. [Communication Channel Reference](communication-channel-reference.md)
5. [MinIO Helper Reference](minio-helper-reference.md)
6. [Platform Utilities and Scripts](platform-utilities-and-scripts.md)

## Companion User Guides

If you want hands-on grammar/mapping tutorials with copy-adapt examples, start with:

- [`docs/grammar-and-mapping/README.md`](../grammar-and-mapping/README.md)
- [`docs/grammar-and-mapping/01-quickstart-first-grammar-and-map.md`](../grammar-and-mapping/01-quickstart-first-grammar-and-map.md)

## API Stability Model

Use this model to decide what is safe to build on:

- Stable extension surfaces:
  - Mapping script entry points (`main`, optional translation helpers)
  - Route script hooks (`start`, `pretranslation`, `postmerge`, and related hooks)
  - Communication and envelope user scripts
  - Grammar files (`syntax`, `structure`, `recorddefs`, `nextmessage*`)
- Semi-stable internals:
  - High-level module entry points like `transform.translate`, `envelope.mergemessages`,
    `communication.run`
  - `botslib` transaction/query helpers
- Internal implementation details:
  - Private methods (`_parse`, `_tree2recordscore`, `_checkstructure`, etc)
  - Call ordering inside the engine/router unless explicitly documented in this section

If you need long-term compatibility, prefer user script hooks and grammar contracts first.

## Module Map

| Area | Primary modules | Primary responsibilities |
| --- | --- | --- |
| Mapping core | `transform.py`, `message.py`, `node.py` | Mapping lifecycle, node tree operations, helper functions |
| Parse/write | `inmessage.py`, `outmessage.py`, `grammar.py` | Parse incoming, validate/canonicalize, serialize outgoing |
| Runtime orchestration | `engine.py`, `router.py`, `preprocess.py`, `envelope.py` | End-to-end run scheduling, route parts, preprocessing/postprocessing, enveloping |
| Channel IO | `communication.py` | Inbound and outbound protocol handling (file/mail/ftp/http/db/script) |
| Utilities | `botslib.py` | Transaction DB API, dynamic imports, script execution, unique counters, file helpers |
| MinIO sidecar | `minio_helper/app/*` | File/S3 copy/move rules with retries, rename templates, environment-driven S3 transport |
| Ops scripts | `scripts/healthcheck.py`, `scripts/init-database.py` | Service probes and schema initialization |

## Conventions Used in This Reference

- "TA record" means a row in the `ta` table, represented by `botslib.OldTransaction` /
  `botslib.NewTransaction`.
- "Status" means the high-level processing phase (`FILEIN`, `TRANSLATED`, `MERGED`, etc).
- "Statust" means status health (`OK`, `DONE`, `ERROR`, `RESEND`).
- "mpath" means Bots path tuples used by `Node.get`, `Node.put`, and related functions.
