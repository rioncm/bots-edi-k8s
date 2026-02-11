Bots EDI MinIO File-Mover Job for K3s

You are a senior cloud-native Python engineer with deep Kubernetes experience.

I have an existing bots EDI deployment running in Kubernetes (k3s).
Bots itself remains unchanged and continues to manage channels natively via filesystem paths on a RWX PVC.

⸻

Goal

Design and implement a separate Kubernetes Job / CronJob–friendly container that acts as a rules-based file mover between:
	•	MinIO (S3-compatible object storage)
	•	Bots filesystem paths mounted via RWX PVC

This component must be:
	•	Stateless
	•	Cloud-native
	•	Configuration-driven

**note** s3 is used throughout to refer to MinIO only. development can and should focus on minio only. 
⸻

High-Level Behavior
	•	Runs as:
	•	a Job (on-demand)
	•	a CronJob (scheduled)
	•	Uses a YAML ConfigMap as the sole source of truth
	•	Authenticates to MinIO via Kubernetes Secret (env vars)
	•	Performs both pull and push operations
	•	Executes rules concurrently
	•	Fail-fast at run level: if any rule fails, the process exits with non-zero status
	•	Supports max_items throttling (default + per-rule override)
	•	Each run processes at most max_items objects/files per rule
	•	Deterministic ordering before slicing:
	•	file: mtime (oldest → newest), then name
	•	s3: key sort

⸻

File Handling Semantics (Critical)

This client is a rules-based file mover only — no workflow logic.

General Flow per Rule (mode: move)
	1.	Stage source → local tmp (copy / download)
	2.	Write tmp file → destination
	3.	On destination success: delete original source
	4.	If destination write fails: do not delete source
	5.	On failure:
	•	Retry (configurable)

No partial files should ever remain in source locations.

⸻

YAML Configuration Model
	•	YAML only
	•	Simple, explicit schema
	•	Rules are generic and extensible

config:
  defaults:                         # optional
    default_bucket: edi             # optional; used when type=s3 and bucket omitted
    base_file_path: /mnt/pvc        # optional; prepended to relative file paths
    mode: move                      # optional; move|copy (default move)
    retries: 0                      # optional
    wait_seconds: 10                # optional
    exit_on_first_failure: true     # optional; default true
    max_items: 250                  # optional; default throttle per rule per run

  <rule_name>:
    description: optional

    src:
      type: file|s3                 # required
      bucket: optional              # required if type=s3 AND no default_bucket
      path: required                # relative or absolute for file; prefix for s3
      match:                        # optional; matches all if not provided
        glob: "*.edi"               # optional
        regex: null                 # optional (mutually exclusive with glob)

    dest:
      type: file|s3                 # required
      bucket: optional              # required if type=s3 AND no default_bucket
      path: required
      rename:                       # optional
        regex: required
        replace: required

    mode: move|copy                 # optional override
    retries: int                    # optional override
    wait_seconds: int               # optional override
    max_items: int                  # optional override


⸻

Path Resolution Rules
	•	If type: file and path is relative:
	•	Final path = base_file_path + "/" + path
	•	If path is absolute`:
	•	Ignore base_file_path
	•	If type: s3:
	•	path is treated as a prefix
	•	Trailing / must be normalized

S3-specific handling
	•	Normalize keys to POSIX-style paths
	•	Strip the prefix before applying match
	•	Sort keys before applying max_items

⸻

Contract

For each eligible item:
	1.	Stage source → local temp file
	2.	Write temp file → destination
	3.	If step (2) succeeds and mode=move: delete source
	4.	If destination write fails: do not delete source
	5.	Retry up to retries, sleeping wait_seconds between attempts
	6.	After rule execution completes:
	•	If any rule failed → exit non-zero

⸻

Throttle Semantics (Safety)
	•	For each rule, list candidates in deterministic order:
	•	file: sort by mtime (oldest → newest)
	•	s3: sort by key
	•	Process only the first max_items
	•	If max_items is not defined anywhere, default to 100

⸻

Technical Requirements

MinIO Configuration
	•	S3-compatible
	•	Credentials via env vars from K8s Secret:
	•	MINIO_ENDPOINT
	•	MINIO_ACCESS_KEY
	•	MINIO_SECRET_KEY
	•	(optional) MINIO_BUCKET
	•	(optional) MINIO_REGION

Kubernetes
	•	Designed to run as:
	•	Job
	•	CronJob
	•	RWX PVC mounted at configurable mount point
	•	ConfigMap for rules
	•	No persistent state outside PVC paths

⸻

Implementation Expectations
	•	Python
	•	Clean separation of concerns:
	•	rule parsing (fail fast on schema errors)
	•	transport (S3 vs filesystem)
	•	execution engine
	•	Idempotent per run
	•	Safe parallel execution
	•	Clear logging per rule and per file to STDOUT

⸻

Deliverables
	1.	Python application structure
	2.	Core logic for:
	•	rule parsing
	•	temp-dir staging
	•	push / pull execution
	•	rename via regex
	•	retries + failure handling
	3.	Examples:
	•	Dockerfile
	•	Kubernetes Job
	•	Kubernetes CronJob
	•	ConfigMap
	•	Secret (env-based)
	4.	Documentation:
	•	README for deployment
	•	README for application (including defaults)
	•	README for configuration and usage

⸻

Constraints
    •	Do not design for other s3 compatible systems
	•	Do not modify bots itself
	•	Do not introduce workflow state or business logic
	•	Assume bots and downstream systems handle correctness