**Purpose**
Document three channel-extension ideas for Bots EDI to support further review.

**Context**
Bots channels are defined by `CHANNELTYPE` in `bots/bots/models.py` and implemented in
`bots/bots/communication.py`. There is an existing `communicationscript` channel that can
implement custom transports without core changes. This document captures three options:
1) API channel via communicationscript, 2) S3-compatible via communicationscript, 3) Upstream
core contribution path.

**Option 1: API Channel (communicationscript)**
Summary: Implement a custom API transport in a `communicationscript` with JSON payloads and
minimal impact on core.

Proposed contract
- Incoming: API returns JSON with one or more payloads. Each payload includes a `content`
  field (base64 or raw) and metadata (filename, content-type, partner ids, etc).
- Outgoing: Bots posts raw file bytes plus metadata fields, or posts JSON with a base64 body.

Example response shape (incoming)
```json
{
  "items": [
    {
      "filename": "PO_1234.edi",
      "content_type": "application/edi-x12",
      "content_b64": "BASE64...",
      "metadata": {
        "from_partner": "ACME",
        "to_partner": "CONTOSO",
        "route": "x12_850"
      }
    }
  ]
}
```

Implementation sketch
1. Create `bots/usersys/communicationscripts/<channel_id>.py`.
2. Implement `connect()` to validate configuration and prep HTTP client.
3. Implement `main()` as a generator for inbound or as a sender hook for outbound.
4. For inbound, yield temp files or raw content that the script writes to a temp file.
5. For outbound, read the file from Bots and `POST` to the API.
6. Use channel fields for config:
   `host` or `path` as base URL, `username/secret` for auth, `parameters` for extra headers.

Operational notes
- Idempotency: include a unique `message_id` and dedupe at the API.
- Retries: rely on Bots retry flow and track `numberofresends` in API logs.
- Security: prefer token auth or mutual TLS.

Pros
- Fastest time-to-implementation.
- No core changes required, minimal review burden.
- API can own complex routing and business logic.

Cons
- You operate an API service with versioning and uptime needs.
- You still must materialize files into Bots for downstream processing.

**Option 2: S3-Compatible Channel (communicationscript)**
Summary: Implement S3-style object storage as a communicationscript before considering core.

Proposed semantics
- Incoming: list objects under a prefix, download each to Bots, mark complete.
- Outgoing: upload files as objects, optionally move to archive or delete after confirm.

Implementation sketch
1. Use `boto3` or an S3-compatible client (MinIO, Ceph, AWS).
2. Map channel fields to S3 settings:
   `host` as endpoint URL, `username/secret` as access key/secret, `path` as
   `bucket/prefix`, `filename` as glob-style filter, `parameters` for region and options.
3. For inbound, list objects with prefix, filter by filename, download each to Bots data dir.
4. For outbound, read file from Bots and `put_object` to bucket/prefix.
5. Honor `remove` by deleting objects after successful intake.
6. Use `archivepath` to move objects to a separate prefix or bucket after processing.

Operational notes
- Idempotency: use object metadata or an internal ledger to prevent reprocessing.
- Consistency: consider S3 list consistency and pagination.
- Security: use IAM policies scoped to bucket/prefix; support endpoint CA bundles if needed.

Pros
- Natural fit to Bots file-centric flow.
- Common across partners and platforms.
- No API service to maintain.

Cons
- More implementation effort and edge cases (listing, idempotency, retries).
- Introduces optional dependency and config complexity.

**Option 3: Upstream Core Contribution**
Summary: Propose a new channel type (likely `s3`) in core with documentation and tests.

Core changes required
1. Add `s3` to `CHANNELTYPE` in `bots/bots/models.py`.
2. Add `class s3(_comsession)` in `bots/bots/communication.py`.
3. Add config mapping and dependency handling (optional import, clear error messages).
4. Update docs and acceptance-test behavior for channel type substitutions.
5. Add example config and minimal tests or demo.

Contribution considerations
- A generic API channel is less likely to be accepted because `http/https` and
  `communicationscript` already cover it.
- An S3 channel has higher OSS value but must be optional and well-documented.
- Expect maintainers to request a plugin-style approach first unless adoption is clear.

**Recommendation Path**
1. Prototype using `communicationscript` for both API and S3.
2. Validate operational behavior and partner needs.
3. If S3 proves broadly useful, prepare an upstream proposal with clear config mapping.

**Open Questions**
1. Should channel fields be extended or reused for S3 settings?
2. What idempotency strategy is acceptable for inbound objects?
3. Do we need a standard JSON schema for API payloads?
