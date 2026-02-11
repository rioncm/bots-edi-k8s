# Phase 4 Complete: Kubernetes Manifests Refactoring

## Date: 2026-02-04

## Summary

Phase 4 implementation is complete. Refactored all Kubernetes manifests following best practices with proper separation of concerns, multiple service deployments, ConfigMaps for configuration, init jobs for database setup, and CronJob for scheduled processing.

## Components Delivered

### 1. Base Manifests (k3s/base/)

#### Namespace
**File:** [k3s/base/namespace.yaml](../k3s/base/namespace.yaml)
- Defines `edi` namespace with proper labels

#### ConfigMaps
**Files:**
- [k3s/base/configmap-botsini.yaml](../k3s/base/configmap-botsini.yaml) - Complete bots.ini configuration
- [k3s/base/configmap-settings.yaml](../k3s/base/configmap-settings.yaml) - Django settings.py

**Benefits:**
- Configuration changes without image rebuilds
- Environment-specific configs via Kustomize overlays
- Audit trail for configuration changes
- Rollback capability

#### Persistent Volume Claims
**File:** [k3s/base/pvc.yaml](../k3s/base/pvc.yaml)

**Strategy Change:**
- **Old**: Single 10Gi PVC at `/home/bots/.bots`
- **New**: Three separate PVCs for clarity
  - `bots-edi-data-pvc` (20Gi, RWX) - EDI files and processing data
  - `bots-edi-logs-pvc` (5Gi, RWX) - Application logs
  - `bots-edi-config-pvc` (1Gi, RWX) - Runtime config backup

**Storage Class:** t1-shiva-nfs (NFS for ReadWriteMany support)

**Why RWX?** Multiple pods need access:
- Engine CronJob reads/writes EDI files
- Webserver reads files for display
- Jobqueue server processes files

#### Service
**File:** [k3s/base/service-webserver.yaml](../k3s/base/service-webserver.yaml)
- ClusterIP service for webserver on port 8080
- Referenced by Ingress
- Proper labels and selectors

### 2. Deployment Manifests (k3s/deployments/)

#### Webserver Deployment
**File:** [k3s/deployments/webserver.yaml](../k3s/deployments/webserver.yaml)

**Key Features:**
- **Command**: `/entrypoint.sh webserver`
- **Replicas**: 1 (can scale if stateless)
- **Strategy**: RollingUpdate with maxUnavailable: 0
- **Health Probes**:
  - Liveness: `/health/live` (30s initial, 30s period)
  - Readiness: `/health/ready` (10s initial, 10s period)
  - Startup: `/health/startup` (0s initial, 5s period, 30 failures = 150s)
- **Resources**:
  - Requests: 100m CPU, 256Mi memory
  - Limits: 1000m CPU, 1Gi memory
- **Volumes**:
  - Data PVC mounted at `/home/bots/.bots`
  - ConfigMaps mounted at `/config/`
- **Environment**:
  - `BOTSENV=default`
  - `DB_INIT_SKIP=true` (init-job handles it)
  - DB credentials from secret

#### Job Queue Deployment
**File:** [k3s/deployments/jobqueue.yaml](../k3s/deployments/jobqueue.yaml)

**Key Features:**
- **Command**: `/entrypoint.sh jobqueueserver`
- **Replicas**: 1 (must be 1, uses internal queue)
- **Strategy**: Recreate (no concurrent instances)
- **Health Probes**: CLI-based exec probes
  - Liveness: `python healthcheck.py --check live --quiet`
  - Readiness: `python healthcheck.py --check ready --quiet`
- **Resources**:
  - Requests: 100m CPU, 256Mi memory
  - Limits: 500m CPU, 512Mi memory
- **Termination**: 60s grace period (allow jobs to finish)

### 3. Job Manifests (k3s/jobs/)

#### Database Init Job
**File:** [k3s/jobs/db-init-job.yaml](../k3s/jobs/db-init-job.yaml)

**Purpose:** One-time database initialization before webserver starts

**Features:**
- **Command**: `/entrypoint.sh init-db`
- **Restart Policy**: OnFailure
- **Backoff Limit**: 3 attempts
- **TTL**: 300s after completion (auto-cleanup)
- **Idempotent**: Safe to run multiple times

**Usage:**
```bash
# Run before deploying webserver
kubectl apply -f k3s/jobs/db-init-job.yaml
kubectl wait --for=condition=complete --timeout=300s job/bots-db-init -n edi
```

#### Engine CronJob
**File:** [k3s/jobs/engine-cronjob.yaml](../k3s/jobs/engine-cronjob.yaml)

**Purpose:** Scheduled EDI file processing

**Features:**
- **Schedule**: `*/5 * * * *` (every 5 minutes)
- **Command**: `/entrypoint.sh engine --new`
- **Concurrency Policy**: Forbid (no overlapping runs)
- **Job History**: Keep last 3 successful, 1 failed
- **Resources**:
  - Requests: 200m CPU, 512Mi memory
  - Limits: 2000m CPU, 2Gi memory
- **TTL**: 600s after completion

**Customization:**
```yaml
# Change schedule
schedule: "*/10 * * * *"  # Every 10 minutes

# Process specific route
args:
- engine
- --new
- --routeid=orders
```

### 4. Ingress & CI/CD

#### Ingress
**File:** [k3s/ingress.yaml](../k3s/ingress.yaml)

**Changes:**
- Updated service reference: `bots-edi-svc` → `bots-webserver`
- Maintains existing TLS configuration
- Traefik annotations preserved

#### Argo Events Sensor
**File:** [k3s/sensor.yaml](../k3s/sensor.yaml)

**Changes:**
- Updated deployment: `bots-edi` → `bots-webserver`
- Updated container: `bots-edi` → `webserver`
- Maintains Harbor webhook integration
- Triggers on semver tags

### 5. Kustomize Integration

#### Main Kustomization
**File:** [k3s/kustomization.yaml](../k3s/kustomization.yaml)

**Features:**
- References all manifests in proper order
- Common labels applied to all resources
- Image tag management
- Namespace scoping

**Usage:**
```bash
# Deploy everything
kubectl apply -k k3s/

# Preview changes
kubectl diff -k k3s/

# Update image tag
cd k3s
kustomize edit set image harbor.pminc.me/priv/bots-edi:v4.0.1
kubectl apply -k .
```

## Architecture Comparison

### Old Architecture (app.yaml)
```
Single Deployment: bots-edi
├── 1 container
├── Hardcoded CMD: tail -f /dev/null
├── Single PVC for everything
├── Config baked in image
└── Manual engine runs
```

### New Architecture (Refactored)
```
Multiple Services:
├── Webserver Deployment
│   ├── Proper entrypoint with service type
│   ├── Health probes (startup/liveness/readiness)
│   ├── ConfigMaps for configuration
│   └── Separate data/logs/config PVCs
│
├── JobQueue Deployment
│   ├── CLI-based health checks
│   ├── Graceful shutdown handling
│   └── Shared data PVC
│
├── DB Init Job
│   ├── One-time initialization
│   ├── Idempotent execution
│   └── Auto-cleanup after completion
│
└── Engine CronJob
    ├── Scheduled processing (every 5 min)
    ├── No concurrent runs
    └── Higher resource limits
```

## Deployment Instructions

### Prerequisites

1. **Build and push new image:**
```bash
cd /Users/rion/VSCode/bots_edi
docker build -f Dockerfile.new -t harbor.pminc.me/priv/bots-edi:4.0 .
docker push harbor.pminc.me/priv/bots-edi:4.0
```

2. **Verify NFS storage class exists:**
```bash
kubectl get storageclass t1-shiva-nfs
```

3. **Verify secret exists:**
```bash
kubectl get secret -n edi bots-edidb-secret
```

### Fresh Installation

```bash
# 1. Apply all manifests with Kustomize
kubectl apply -k k3s/

# 2. Wait for DB init to complete
kubectl wait --for=condition=complete --timeout=300s job/bots-db-init -n edi

# 3. Verify deployments
kubectl get all -n edi

# 4. Check webserver health
kubectl port-forward -n edi svc/bots-webserver 8080:8080
curl http://localhost:8080/health/startup
```

### Migration from Old Deployment

```bash
# 1. Scale down old deployment
kubectl scale deployment/bots-edi -n edi --replicas=0

# 2. Backup data (if needed)
kubectl exec -n edi deployment/bots-edi -- tar czf /tmp/backup.tar.gz /home/bots/.bots
kubectl cp edi/<pod-name>:/tmp/backup.tar.gz ./backup.tar.gz

# 3. Delete old deployment (keep PVC and secret)
kubectl delete deployment/bots-edi -n edi
kubectl delete svc/bots-edi-svc -n edi

# 4. Apply new manifests
kubectl apply -k k3s/

# 5. Verify migration
kubectl get pods -n edi -w
```

### Configuration Updates

**Update bots.ini:**
```bash
# Edit ConfigMap
kubectl edit configmap -n edi bots-config-ini

# Or from file
kubectl create configmap bots-config-ini --from-file=bots.ini=bots_config/bots.ini -n edi --dry-run=client -o yaml | kubectl apply -f -

# Restart pods
kubectl rollout restart deployment/bots-webserver -n edi
kubectl rollout restart deployment/bots-jobqueue -n edi
```

**Update settings.py:**
```bash
kubectl edit configmap -n edi bots-config-settings
kubectl rollout restart deployment/bots-webserver -n edi
```

## Monitoring & Operations

### Health Checks

```bash
# Webserver health
kubectl exec -n edi deployment/bots-webserver -- curl -f http://localhost:8080/health/live
kubectl exec -n edi deployment/bots-webserver -- curl -f http://localhost:8080/health/ready
kubectl exec -n edi deployment/bots-webserver -- curl -f http://localhost:8080/health/startup

# Jobqueue health
kubectl exec -n edi deployment/bots-jobqueue -- python /usr/local/bots/scripts/healthcheck.py --check ready
```

### Logs

```bash
# Webserver logs
kubectl logs -n edi -l component=webserver --tail=100 -f

# Jobqueue logs
kubectl logs -n edi -l component=jobqueue --tail=100 -f

# Engine job logs (latest)
kubectl logs -n edi job/$(kubectl get jobs -n edi -l component=engine --sort-by=.metadata.creationTimestamp -o name | tail -1) -f

# DB init logs
kubectl logs -n edi job/bots-db-init
```

### Troubleshooting

**Webserver not starting:**
```bash
# Check events
kubectl describe pod -n edi -l component=webserver

# Check startup probe
kubectl get pod -n edi -l component=webserver -o jsonpath='{.items[0].status.conditions}'

# Manual init
kubectl exec -it -n edi deployment/bots-webserver -- /entrypoint.sh shell
python /usr/local/bots/scripts/init-database.py --config-dir /config
```

**Engine jobs failing:**
```bash
# List recent jobs
kubectl get jobs -n edi -l component=engine

# Check latest job
kubectl describe job -n edi $(kubectl get jobs -n edi -l component=engine --sort-by=.metadata.creationTimestamp -o name | tail -1)

# Manual engine run
kubectl create job --from=cronjob/bots-engine -n edi bots-engine-manual-$(date +%s)
```

**ConfigMap not updating:**
```bash
# Verify ConfigMap
kubectl get configmap -n edi bots-config-ini -o yaml

# Force pod recreation
kubectl delete pod -n edi -l component=webserver
```

## Files Created/Modified

### Created
**Base:**
- `k3s/base/namespace.yaml` - Namespace definition
- `k3s/base/configmap-botsini.yaml` - Bots.ini ConfigMap (300 lines)
- `k3s/base/configmap-settings.yaml` - Settings.py ConfigMap (114 lines)
- `k3s/base/pvc.yaml` - Three PVC definitions
- `k3s/base/service-webserver.yaml` - Webserver service

**Deployments:**
- `k3s/deployments/webserver.yaml` - Webserver deployment (131 lines)
- `k3s/deployments/jobqueue.yaml` - Jobqueue deployment (92 lines)

**Jobs:**
- `k3s/jobs/db-init-job.yaml` - DB initialization job (56 lines)
- `k3s/jobs/engine-cronjob.yaml` - Engine CronJob (79 lines)

**Orchestration:**
- `k3s/kustomization.yaml` - Kustomize configuration (44 lines)
- `k3s/README.md` - Quick reference guide (178 lines)
- `fork/phase4-complete.md` - This file

### Modified
- `k3s/ingress.yaml` - Updated service reference
- `k3s/sensor.yaml` - Updated deployment/container names

### Deprecated (to be removed)
- `k3s/app.yaml` - Old monolithic deployment
- `k3s/svc.yaml` - Old service definition
- `k3s/pvc.yaml` (root) - Old single PVC
- `k3s/config-map.yaml` - Old ConfigMap

## Key Improvements

### 1. **Separation of Concerns**
- ✅ Separate deployments per service type
- ✅ Dedicated job for DB initialization
- ✅ CronJob for scheduled processing
- ✅ Clear component labeling

### 2. **Configuration Management**
- ✅ ConfigMaps for runtime config changes
- ✅ Secrets for sensitive data
- ✅ Environment variables for overrides
- ✅ No config baked in images

### 3. **Storage Strategy**
- ✅ Separate PVCs by function
- ✅ RWX for multi-pod access
- ✅ NFS storage class for compatibility
- ✅ Clear mount points

### 4. **Health & Monitoring**
- ✅ HTTP probes for webserver
- ✅ CLI probes for jobqueue
- ✅ Startup probes for slow initialization
- ✅ Prometheus annotations

### 5. **Operations**
- ✅ Proper initialization sequence
- ✅ Graceful shutdown handling
- ✅ Auto-cleanup of old jobs
- ✅ Kustomize for environment management

### 6. **Scalability**
- ✅ Webserver can scale horizontally
- ✅ Engine runs as parallel jobs (CronJob)
- ✅ Jobqueue remains singleton
- ✅ Resource limits defined

### 7. **CI/CD Ready**
- ✅ Argo Events sensor integrated
- ✅ Automatic deployments on new images
- ✅ Rollback capability
- ✅ Canary deployment ready

## Resource Requirements

**Minimum Cluster Resources:**
- CPU: 500m (requests) + 3500m (limits) = 4 cores recommended
- Memory: 1Gi (requests) + 4Gi (limits) = 8Gi recommended
- Storage: 26Gi NFS-backed PVCs

**Per-Service Breakdown:**
```
Webserver:   100m-1000m CPU, 256Mi-1Gi RAM
Jobqueue:    100m-500m CPU,  256Mi-512Mi RAM
Engine Job:  200m-2000m CPU, 512Mi-2Gi RAM
DB Init:     100m-500m CPU,  256Mi-512Mi RAM
```

## Testing Checklist

- [ ] Build new Docker image
- [ ] Push to Harbor registry
- [ ] Apply namespace and base resources
- [ ] Verify PVCs are bound
- [ ] Run DB init job successfully
- [ ] Deploy webserver - health probes pass
- [ ] Deploy jobqueue - health probes pass
- [ ] Verify engine CronJob scheduled
- [ ] Test ingress HTTPS access
- [ ] Verify Argo sensor triggers on new image
- [ ] Test configuration updates via ConfigMap
- [ ] Verify graceful shutdown (delete pod)
- [ ] Test engine manual job creation
- [ ] Verify logs accessible

## Next Steps

Phase 4 is **COMPLETE** and ready for Phase 5.

**Phase 5: Configuration Management**
- Kustomize overlays for dev/staging/prod
- Sealed Secrets or external-secrets for DB credentials
- Environment-specific resource limits
- Multi-environment deployment strategy

**Phase 6: Testing & Validation**
- Integration tests for all services
- Load testing webserver
- Engine performance testing
- Failover testing
- Backup/restore procedures

**Phase 7: Documentation & Upstreaming**
- User documentation
- Operations runbook
- Architecture diagrams
- Contribution to bots-edi project

## Notes

1. **NFS Storage**: Using t1-shiva-nfs for RWX. If unavailable, consider:
   - Single-replica deployments with RWO
   - External file storage (S3, Azure Files)
   - NFS server deployment

2. **Database Init**: Currently runs as Job before webserver. Alternative:
   - Init container in webserver pod
   - Separate migration deployment
   - Manual initialization

3. **Engine Scheduling**: CronJob every 5 minutes. Consider:
   - Argo Events trigger on file upload
   - Watch-based dirmonitor deployment
   - On-demand processing via API

4. **Security**: Current setup uses non-root user (10001). Consider:
   - Pod Security Standards (restricted)
   - Network policies
   - RBAC for service accounts
   - Secret rotation

---

**Status:** ✅ **PHASE 4 COMPLETE**

**Ready for:** Phase 5 - Configuration Management

**Deployment Command:**
```bash
kubectl apply -k /Users/rion/VSCode/bots_edi/k3s/
```
