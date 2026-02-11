# MinIO Helper for Bots EDI

A stateless, rules-based file mover that bridges MinIO (S3-compatible) object storage and
Bots EDI filesystem paths on a RWX PVC. Designed for Kubernetes Job or CronJob execution.

## Key Features
- Configuration-driven via YAML ConfigMap
- Uses MinIO credentials via environment variables (Kubernetes Secret)
- Deterministic ordering and per-rule throttling
- Concurrent rule execution
- Fail-fast behavior with non-zero exit on rule failure

## Quick Start (Local)
1. Create a config file (see `config/example-config.yaml`).
2. Export required environment variables:
   - `MINIO_ENDPOINT`
   - `MINIO_ACCESS_KEY`
   - `MINIO_SECRET_KEY`
   - Optional: `MINIO_BUCKET`, `MINIO_REGION`
3. Run:

```bash
python -m minio_helper --config config/example-config.yaml
```

## Environment Variables
- `MINIO_ENDPOINT` (required) : MinIO endpoint (eg `http://minio:9000`)
- `MINIO_ACCESS_KEY` (required)
- `MINIO_SECRET_KEY` (required)
- `MINIO_BUCKET` (optional) : default bucket if not set in config
- `MINIO_REGION` (optional)
- `MINIO_VERIFY` (optional) : `true|false` or path to CA bundle
- `MINIO_ADDRESSING_STYLE` (optional) : `path` or `virtual` (default: `path`)
- `MINIO_CONNECT_TIMEOUT` (optional) : seconds (default: 10)
- `MINIO_READ_TIMEOUT` (optional) : seconds (default: 60)
- `MINIO_HELPER_CONFIG` (optional) : config path override
- `MINIO_HELPER_LOG_LEVEL` (optional) : log level (default: `INFO`)
- `MINIO_HELPER_TIMEZONE` (optional) : IANA time zone for rename templates (default: local time)

## Docker Build
From repo root:

```bash
docker build -f minio_helper/Dockerfile -t bots-minio-helper:latest .
```

## Kubernetes
See `README-deployment.md` and the `k8s/` manifests for Job, CronJob, ConfigMap, and Secret
examples.
