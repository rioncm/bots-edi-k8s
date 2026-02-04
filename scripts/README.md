# Scripts Directory

Utility scripts for Bots-EDI containerization and maintenance.

## Available Scripts

### init-database.py

Database initialization script that creates all required tables (managed and unmanaged).

**Usage:**
```bash
# Using Python directly
python scripts/init-database.py

# With custom config directory
python scripts/init-database.py --config-dir=/path/to/config

# Verbose output
python scripts/init-database.py --verbose

# Or as executable
./scripts/init-database.py
```

**What it does:**
1. Runs Django migrations to create managed tables
2. Executes SQL files to create unmanaged tables (ta, mutex, persist, uniek)
3. Verifies all required tables exist

**Requirements:**
- Configured database connection in settings.py
- SQL files in bots/bots/sql/

**Exit codes:**
- 0: Success
- 1: Failure

**Idempotent:** Safe to run multiple times. Will skip existing tables.

## Django Management Commands

You can also use Django's management command interface:

```bash
# From the bots package directory
cd bots
python -m django manage.py initdb

# Or if bots is installed
python manage.py initdb --settings=config.settings
```

## Container Usage

In Kubernetes, this is typically run as an init container or Job:

```yaml
initContainers:
- name: db-init
  image: bots-edi:latest
  command: ["python", "scripts/init-database.py"]
  env:
    - name: DB_HOST
      value: "mysql-host"
    # ... other DB env vars
```

Or as a one-time Job:

```bash
kubectl apply -f k3s/jobs/db-init-job.yaml
```
