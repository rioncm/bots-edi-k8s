# Configuration Reference

The helper expects a YAML file with a top-level `config` mapping that contains optional
`defaults` and one or more named rules.

## Schema (Summary)

```yaml
config:
  defaults:
    default_bucket: edi
    base_file_path: /mnt/pvc
    mode: move            # move|copy
    retries: 0
    wait_seconds: 10
    exit_on_first_failure: true
    max_items: 250

  <rule_name>:
    description: optional

    src:
      type: file|s3
      bucket: optional
      path: required
      match:
        glob: "*.edi"     # optional
        regex: null       # optional

    dest:
      type: file|s3
      bucket: optional
      path: required
      rename:
        regex: required
        replace: required

    mode: move|copy
    retries: int
    wait_seconds: int
    max_items: int
```

## Path Resolution
- If `type: file` and `path` is relative:
  - Final path = `base_file_path + "/" + path`
- If `path` is absolute:
  - `base_file_path` is ignored
- If `type: s3`:
  - `path` is a prefix within the bucket
  - Leading `/` is stripped, trailing `/` is normalized

## Matching Rules
- `glob` and `regex` are mutually exclusive.
- If omitted, all files/keys under the source path are eligible.
- For S3, the prefix is stripped before applying the match.

## Ordering and Throttling
- File sources: sorted by mtime (oldest to newest), then filename.
- S3 sources: keys sorted lexicographically.
- After sorting, the list is truncated to `max_items` for each rule.

## Rename Rules
- Applied to the relative filename (not the full destination path).
- `replace` supports regex backreferences (`\\1`, `\\g<name>`) and template tokens.
- Template tokens use local time unless noted. Local time uses `MINIO_HELPER_TIMEZONE` when set.

### Replace Template Tokens
- `{timestamp}` -> `YYYYMMDD-HHMMSS`
- `{time}` -> `HHMMSS`
- `{date}` -> `YYYYMMDD`
- `{date-iso}` -> `YYYY-MM-DD`
- `{timestamp-iso}` -> `YYYY-MM-DDTHHMMSS`
- `{timestamp-z}` -> `YYYYMMDDTHHMMSSZ` (UTC)
- Example:

```yaml
dest:
  type: s3
  path: out/x12/850
  rename:
    regex: "(.*)\\.edi$"
    replace: "\\1.{date}.ready"
```

## Example
See `config/example-config.yaml`.
