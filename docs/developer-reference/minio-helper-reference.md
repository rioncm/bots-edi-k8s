# MinIO Helper Reference

This page documents the sidecar utility in:

- `minio_helper/app/config.py`
- `minio_helper/app/engine.py`
- `minio_helper/app/fs_transport.py`
- `minio_helper/app/s3_transport.py`
- `minio_helper/app/util.py`
- `minio_helper/app/main.py`

`minio_helper` moves or copies objects between filesystem and S3-compatible storage (MinIO/AWS S3).

## Runtime Entry Point

`main()` in `minio_helper/app/main.py`:

- Parses:
  - `--config` (default env `MINIO_HELPER_CONFIG` or `/config/config.yaml`)
  - `--log-level` (default env `MINIO_HELPER_LOG_LEVEL` or `INFO`)
- Loads config via `load_config(...)`.
- Returns exit code:
  - `0`: successful run
  - `1`: rule/runtime failures
  - `2`: config or config-file errors

## Config Model (`config.py`)

Top-level schema:

```yaml
config:
  defaults: ...
  <rule-name>: ...
```

### Dataclasses

- `Config(defaults, rules)`
- `Defaults`
- `Rule`
- `Endpoint`
- `MatchSpec`
- `RenameSpec`

### Endpoint types

- `type: file`
- `type: s3`

Common endpoint fields:

- `path` (required)
- `bucket` (for S3; optional if resolved from defaults/env)

Source-only:

- `match`:
  - `glob` or `regex` (mutually exclusive)

Destination-only:

- `rename`:
  - `regex`
  - `replace`

### Default settings

`Defaults` fields:

- `default_bucket`
- `base_file_path`
- `mode` (`move` or `copy`, default `move`)
- `retries` (default `0`)
- `wait_seconds` (default `10`)
- `exit_on_first_failure` (default `true`)
- `max_items` (optional)

### Validation behavior

- Negative integers are rejected.
- Invalid regex patterns raise `ConfigError`.
- Missing required strings raise `ConfigError`.
- At least one rule is required.

## Engine Flow (`engine.py`)

### `run(config, env) -> int`

- Runs rules concurrently (`ThreadPoolExecutor`, up to 4 workers).
- Returns `1` if any rule fails.
- Honors `defaults.exit_on_first_failure` via a shared stop event.

### `run_rule(rule, defaults, env, stop_event) -> bool`

Per-rule lifecycle:

1. Resolve mode/retries/wait/max_items.
2. Build S3 client lazily if needed.
3. Collect candidates (`list_candidates`).
4. Process each item with retry logic.
5. Stop early on first item failure for that rule.

### Candidate selection

`list_candidates(...)` behavior:

- File source:
  - Resolve path using `base_file_path` if needed.
  - If source directory does not exist:
    - logs a warning,
    - returns empty list,
    - does not fail the rule.
  - Same warning-and-skip behavior applies if directory disappears during scan.
- S3 source:
  - Lists keys under normalized prefix.
  - Filters directories (`.../`) and match rules.
  - Sorts lexicographically by full key.

`max_items` limits are applied after sorting.

### Item processing

`process_item(...)`:

1. Stage source content into temp file.
2. Write destination (file or S3).
3. If mode is `move`, delete source.
4. Retry failures `retries + 1` attempts, sleeping `wait_seconds` between attempts.

On final failure, returns `False`.

### Source/destination operations

- `stage_source(...)`
  - File -> temp copy
  - S3 -> download to temp
- `write_destination(...)`
  - File -> atomic write (`atomic_write_from_temp`)
  - S3 -> upload to resolved bucket/key
- `delete_source(...)`
  - File -> `os.remove`
  - S3 -> `delete_object`

## Rename and Path Semantics

### Rename tokens

`_render_replace_template(...)` supports:

- `{timestamp}` -> local `YYYYMMDD-HHMMSS`
- `{time}` -> local `HHMMSS`
- `{date}` -> local `YYYYMMDD`
- `{date-iso}` -> local `YYYY-MM-DD`
- `{timestamp-iso}` -> local `YYYY-MM-DDTHHMMSS`
- `{timestamp-z}` -> UTC `YYYYMMDDTHHMMSSZ`

Timezone source:

- `MINIO_HELPER_TIMEZONE` (IANA zone name), else local host timezone.

### Relative file paths

`resolve_file_path(path, base_file_path)`:

- Absolute paths are used as-is.
- Relative paths require `defaults.base_file_path`.

### S3 prefixes

`normalize_s3_prefix(path)` strips leading slash and guarantees trailing slash when non-empty.

## Environment Variables

S3 client creation uses:

- `MINIO_ENDPOINT` (required)
- `MINIO_ACCESS_KEY` (required)
- `MINIO_SECRET_KEY` (required)
- `MINIO_REGION` (optional but often required for signature compatibility)
- `MINIO_VERIFY`:
  - `0|false|no` -> bool `False`
  - `1|true|yes` -> bool `True`
  - any other non-empty value -> passed as verify path/string
- `MINIO_ADDRESSING_STYLE` (default `path`)
- `MINIO_CONNECT_TIMEOUT` (default `10`)
- `MINIO_READ_TIMEOUT` (default `60`)
- `MINIO_BUCKET` fallback bucket when endpoint bucket/default bucket absent

Values for key S3 vars are whitespace-trimmed before use.

## Error Semantics and Troubleshooting

### Missing source directory (`type: file`)

Behavior:

- Warning log only.
- Rule returns success with no candidates.
- Run does not fail because directory is missing.

This is intentional for optional or intermittently mounted source directories.

### `SignatureDoesNotMatch` on S3 list

When `ListObjectsV2` returns signature mismatch, engine raises a clearer `ValueError` hinting to verify:

- endpoint/key/secret,
- region (for MinIO typically `us-east-1`),
- pod/system clock synchronization.

## Minimal Example

```yaml
config:
  defaults:
    base_file_path: /data
    mode: move
    retries: 2
    wait_seconds: 5
    default_bucket: edi

  inbound_orders:
    src:
      type: file
      path: incoming/orders
      match:
        glob: "*.edi"
    dest:
      type: s3
      path: inbox/orders
      rename:
        regex: "^(.*)\\.edi$"
        replace: "\\1_{timestamp-z}.edi"
```

