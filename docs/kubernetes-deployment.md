# Bots EDI - Kubernetes Deployment Guide

## Overview

Bots EDI is a complete software solution for EDI (Electronic Data Interchange) with a powerful translator engine. This guide covers deploying Bots EDI on Kubernetes using the containerized architecture.

## Storage Requirements

**IMPORTANT:** Bots-EDI requires ReadWriteMany (RWX) persistent storage for shared data access across multiple pods.

### ✅ Recommended: Longhorn

**Longhorn is the strongly recommended storage solution** for Bots-EDI deployments:

**Advantages:**
- ✅ Properly honors `fsGroup` - no permission issues with non-root containers
- ✅ Native Kubernetes integration with CSI driver
- ✅ Automatic replication and high availability
- ✅ Built-in volume snapshots and cloning
- ✅ Simple installation via Helm chart
- ✅ Web UI for management and monitoring
- ✅ Works reliably with Kubernetes security contexts

**Installation:**
```bash
# Add Longhorn Helm repository
helm repo add longhorn https://charts.longhorn.io
helm repo update

# Install Longhorn
helm install longhorn longhorn/longhorn \
  --namespace longhorn-system \
  --create-namespace \
  --set defaultSettings.defaultDataPath="/var/lib/longhorn"

# Set as default StorageClass (optional)
kubectl patch storageclass longhorn \
  -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
```

**Verification:**
```bash
kubectl -n longhorn-system get pods
kubectl get storageclass
```

### ❌ Not Recommended: NFS

**NFS has known issues** with Kubernetes and non-root containers:

**Problems:**
- ❌ Often ignores `fsGroup`, causing "Permission denied" errors
- ❌ Requires complex NFS server-side configuration (`all_squash`, `anonuid=10001`)
- ❌ Needs init containers in every pod to fix permissions
- ❌ Inconsistent behavior across NFS implementations
- ❌ Additional latency compared to block storage
- ❌ No native Kubernetes integration (manual provisioning)

**If you must use NFS**, configure exports with:
```bash
# /etc/exports
/export/path *(rw,sync,no_subtree_check,all_squash,anonuid=10001,anongid=10001)
```

And add init containers to all pods to fix permissions before main container starts.

### Alternative RWX Storage Options

- **Rook/Ceph**: Enterprise-grade, more complex setup, overkill for most deployments
- **GlusterFS**: Requires dedicated nodes, higher resource overhead than Longhorn
- **Cloud Provider Storage**:
  - AWS: EFS (Elastic File System)
  - GCP: Filestore
  - Azure: Azure Files
  - Generally more expensive than Longhorn, but fully managed

## Architecture

Bots EDI consists of four primary services:

1. **Webserver** - Django-based web UI for configuration and monitoring (port 8080)
2. **Engine** - EDI processing engine that transforms messages (scheduled via CronJob)
3. **Job Queue Server** - Background job processor using XML-RPC
4. **Directory Monitor** - File system watcher for automatic processing (optional)

### Container Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Kubernetes Cluster                       │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Webserver   │  │  Job Queue   │  │    Engine     │     │
│  │  Deployment  │  │  Deployment  │  │   CronJob     │     │
│  │  (3 replicas)│  │  (1 replica) │  │  (*/5 min)    │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬────────┘     │
│         │                  │                  │              │
│         └──────────────────┴──────────────────┘              │
│                            │                                 │
│                    ┌───────▼────────┐                        │
│                    │  Shared PVCs:  │                        │
│                    │  - data (20Gi) │                        │
│                    │  - logs (5Gi)  │                        │
│                    │  - config (1Gi)│                        │
│                    └────────────────┘                        │
│                                                              │
│  ┌──────────────────────────────────────────────────┐      │
│  │             MySQL Database                        │      │
│  │         (kona.db.pminc.me)                        │      │
│  └──────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

- Kubernetes cluster (1.19+) or k3s
- kubectl configured with cluster access
- Storage class supporting ReadWriteMany (RWX) for shared volumes
  - Examples: NFS, CephFS, Longhorn
- Container registry access (Harbor, Docker Hub, etc.)
- MySQL database server
- Basic knowledge of Kubernetes concepts

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/bots_edi.git
cd bots_edi
```

### 2. Create Namespace

```bash
kubectl create namespace edi
```

### 3. Create Database Secret

Generate strong passwords:
```bash
# Django SECRET_KEY
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Database password
openssl rand -base64 48
```

Create the database secret:
```bash
kubectl create secret generic bots-edidb-secret \
  --from-literal=DB_NAME=botsedi_data \
  --from-literal=DB_USER=botsedi \
  --from-literal=DB_PASSWORD='your-secure-database-password' \
  --from-literal=DB_HOST=your-mysql-host \
  --from-literal=DB_PORT=3306 \
  --from-literal=DJANGO_SECRET_KEY='your-django-secret-key' \
  -n edi
```

**Optional:** Add CSRF trusted origins for your domain:
```bash
# If your ingress uses HTTPS, add CSRF_TRUSTED_ORIGINS to the secret
kubectl patch secret bots-edidb-secret -n edi --type=merge \
  -p '{"stringData":{"CSRF_TRUSTED_ORIGINS":"https://edi.k8.pminc.me,https://edi-dev.k8.pminc.me"}}'
```

Create the superuser secret:
```bash
# Generate a secure password for the admin user
ADMIN_PASSWORD=$(openssl rand -base64 24)

kubectl create secret generic bots-superuser-secret \
  --from-literal=SUPERUSER_USERNAME=admin \
  --from-literal=SUPERUSER_EMAIL=admin@yourcompany.com \
  --from-literal=SUPERUSER_PASSWORD="$ADMIN_PASSWORD" \
  -n edi

# Save the password securely!
echo "Admin password: $ADMIN_PASSWORD" | tee admin-credentials.txt
chmod 600 admin-credentials.txt
```

### 4. Deploy Base Resources

```bash
# Deploy ConfigMaps and PVCs
kubectl apply -f k3s/base/

# Wait for PVCs to be bound
kubectl wait --for=jsonpath='{.status.phase}'=Bound pvc/bots-edi-data-pvc -n edi --timeout=5m
```

### 5. Initialize Database

```bash
# Run one-time database initialization
kubectl apply -f k3s/jobs/db-init-job.yaml

# Wait for completion
kubectl wait --for=condition=complete job/bots-db-init -n edi --timeout=5m

# Check logs
kubectl logs job/bots-db-init -n edi
```

### 6. Create Default Superuser

```bash
# Run superuser creation job (idempotent)
kubectl apply -f k3s/jobs/create-superuser-job.yaml

# Wait for completion
kubectl wait --for=condition=complete job/bots-create-superuser -n edi --timeout=2m

# Check logs to see credentials confirmation
kubectl logs job/bots-create-superuser -n edi

# Retrieve your admin credentials
echo "Username: admin"
kubectl get secret bots-superuser-secret -n edi -o jsonpath='{.data.SUPERUSER_PASSWORD}' | base64 -d && echo
```

### 7. Deploy Services

```bash
# Deploy webserver and job queue
kubectl apply -f k3s/deployments/

# Deploy engine CronJob
kubectl apply -f k3s/jobs/engine-cronjob.yaml

# Deploy ingress (if using Traefik or other ingress controller)
kubectl apply -f k3s/base/ingress.yaml
```

### 8. Verify Deployment

```bash
# Check pod status
kubectl get pods -n edi

# Check logs
kubectl logs -n edi -l app=bots-edi --tail=50

# Test health endpoints
kubectl exec -n edi deployment/bots-webserver -- curl -f http://localhost:8080/health/ping
```

### 9. Access Web UI

```bash
# Get ingress URL
kubectl get ingress -n edi

# Or port forward for testing
kubectl port-forward -n edi svc/bots-webserver 8080:8080
```

Access at: http://localhost:8080 (or your ingress hostname)

**Login with your admin credentials**:
- Username: `admin` (or what you specified in secret)
- Password: Retrieve with `kubectl get secret bots-superuser-secret -n edi -o jsonpath='{.data.SUPERUSER_PASSWORD}' | base64 -d`

**IMPORTANT**: Change the password after first login via the web UI!

## Multi-Environment Deployment

Bots EDI supports multiple environments using Kustomize overlays:

### Development Environment
```bash
kubectl apply -k k3s/overlays/dev/
```
- Minimal resources (128Mi-512Mi RAM)
- Single replica
- Debug logging enabled
- Engine runs every minute

### Staging Environment
```bash
kubectl apply -k k3s/overlays/staging/
```
- Medium resources (256Mi-768Mi RAM)
- 2 webserver replicas
- Production-like configuration
- Engine runs every 5 minutes

### Production Environment
```bash
kubectl apply -k k3s/overlays/prod/
```
- Full resources (256Mi-1Gi RAM)
- 3 webserver replicas
- Optimized for performance
- Engine runs every 5 minutes

See [DEPLOYMENT.md](../k3s/DEPLOYMENT.md) for detailed multi-environment procedures.

## Configuration

### ConfigMaps

Configuration is managed via ConfigMaps:

- `bots-config-ini`: Main bots.ini configuration (300 lines)
- `bots-config-settings`: Django settings.py
- `bots-env-config`: Environment variables (per overlay)

To update configuration:
```bash
# Edit ConfigMap
kubectl edit configmap bots-config-ini -n edi

# Restart pods to pick up changes
kubectl rollout restart deployment/bots-webserver -n edi
kubectl rollout restart deployment/bots-jobqueue -n edi
```

### Environment Variables

The following environment variables are supported (configured via secrets or deployments):

**Database Configuration** (from `bots-edidb-secret`):
- `DB_NAME`: Database name (default: `botsedi_data`)
- `DB_USER`: Database username
- `DB_PASSWORD`: Database password
- `DB_HOST`: Database hostname
- `DB_PORT`: Database port (default: `3306`)

**Django Configuration**:
- `DJANGO_SECRET_KEY`: Django secret key for cryptographic signing (required)
- `CSRF_TRUSTED_ORIGINS`: Comma-separated list of trusted HTTPS origins for CSRF protection
  - Example: `https://edi.k8.pminc.me,https://edi-dev.k8.pminc.me`
  - Required for login forms when using HTTPS ingress
- `DEBUG`: Enable Django debug mode (`True`/`False`, default: `False`)
- `ALLOWED_HOSTS`: Comma-separated list of allowed hosts (default: `*`)

**Bots Application**:
- `BOTSENV`: Environment name (default: `default`)
- `DB_INIT_SKIP`: Skip database initialization on startup (`true`/`false`)
- `HEALTH_CHECK_DB_ONLY`: For jobqueue, only check database in readiness probe (`true`/`false`)

**Email Configuration** (optional):
- `EMAIL_HOST`: SMTP server hostname
- `EMAIL_PORT`: SMTP port (default: `25`)
- `EMAIL_USE_TLS`: Use TLS (`True`/`False`)
- `EMAIL_HOST_USER`: SMTP username
- `EMAIL_HOST_PASSWORD`: SMTP password
- `SERVER_EMAIL`: From address for error emails
- `ADMIN_EMAIL`: Admin email for notifications

### Secrets
kubectl delete secret bots-edidb-secret -n edi
kubectl create secret generic bots-edidb-secret ... -n edi

# Update superuser password
kubectl delete secret bots-superuser-secret -n edi
kubectl create secret generic bots-superuser-secret \
  --from-literal=SUPERUSER_USERNAME=admin \
  --from-literal=SUPERUSER_EMAIL=admin@yourcompany.com \
  --from-literal=SUPERUSER_PASSWORD='new-secure-password' \
  -n edi

# Run superuser job to apply new password
kubectl delete job bots-create-superuser -n edi
kubectl apply -f k3s/jobs/create-superuser-job.yaml

# Restart deployments to pick up secret changee
kubectl delete secret bots-edidb-secret -n edi
kubectl create secret generic bots-edidb-secret ... -n edi

# Restart deployments
kubectl rollout restart deployment/bots-webserver -n edi
```

See [k3s/secrets/README.md](../k3s/secrets/README.md) for secret management best practices.

### Persistent Storage

Three PVCs are used:

1. **bots-edi-data-pvc** (20Gi, RWX)
   - EDI files and processing data
   - Mounted at: `/home/bots/.bots`

2. **bots-edi-logs-pvc** (5Gi, RWX)
   - Application logs
   - Path: `/home/bots/.bots/env/default/botssys/logging`

3. **bots-edi-config-pvc** (1Gi, RWX)
   - Runtime configuration backup
   - Path: `/home/bots/.bots/env/default/config`

**Storage Class**: Must support ReadWriteMany (RWX) for multiple pod access.

## Operations

### Scaling

Scale webserver replicas:
```bash
kubectl scale deployment/bots-webserver -n edi --replicas=5
```

### Engine Schedule

Modify engine CronJob schedule:
```bash
kubectl edit cronjob/bots-engine -n edi
# Update spec.schedule (cron format)
```

### Manual Engine Run

Trigger engine processing manually:
```bash
kubectl create job --from=cronjob/bots-engine bots-engine-manual -n edi
```

### View Logs

```bash
# Webserver logs
kubectl logs -n edi -l component=webserver --tail=100 -f

# Job queue logs
kubectl logs -n edi -l component=jobqueue --tail=100 -f

# Engine logs (latest job)
kubectl logs -n edi -l job-name --tail=100

# All bots-edi logs
kubectl logs -n edi -l app=bots-edi --tail=200 -f
```

### Database Backup

```bash
# Backup database
kubectl exec -n edi deployment/bots-webserver -- \
  python manage.py dumpdata --exclude auth.permission --exclude contenttypes \
  > backup.json

# Restore database
kubectl exec -i -n edi deployment/bots-webserver -- \
  python manage.py loaddata < backup.json
```

### Rolling Updates

Update container image:
```bash
# Update deployment
kubectl set image deployment/bots-webserver \
  webserver=harbor.pminc.me/priv/bots-edi:v1.2.0 -n edi

# Monitor rollout
kubectl rollout status deployment/bots-webserver -n edi

# Rollback if needed
kubectl rollout undo deployment/bots-webserver -n edi
```

## Health Checks

Bots EDI includes comprehensive health endpoints:

### Web UI Health Endpoints

- `/health/ping` - Simple ping (200 OK)
- `/health/live` - Liveness check (basic functionality)
- `/health/ready` - Readiness check (DB + paths)
- `/health/startup` - Startup check (comprehensive)

Test endpoints:
```bash
curl http://your-domain/health/ping
kubectl exec -n edi deployment/bots-webserver -- curl http://localhost:8080/health/ready
```

### CLI Health Checks

For non-web services (jobqueue):
```bash
kubectl exec -n edi deployment/bots-jobqueue -- \
  python /usr/local/bots/scripts/healthcheck.py --check live
```

## Troubleshooting

### Pods Not Starting

```bash
# Check pod events
kubectl describe pod <pod-name> -n edi

# Common issues:
# - ImagePullBackOff: Check registry credentials
# - CrashLoopBackOff: Check logs for errors
# - Pending: Check PVC binding and resource availability
```

### Database Connection Errors

```bash
# Verify secret exists
kubectl get secret bots-edidb-secret -n edi

# Check secret values
kubectl get secret bots-edidb-secret -n edi -o yaml

# Test DB connection from pod
kubectl exec -n edi deployment/bots-webserver -- \
  nc -zv your-db-host 3306
```

### PVCwebserver liveness (HTTP)
kubectl exec -n edi deployment/bots-webserver -- \
  curl -f http://localhost:8080/health/live || echo "FAILED"

# Test jobqueue liveness (exec probe)
kubectl exec -n edi deployment/bots-jobqueue -- \
  python /usr/local/bots/scripts/healthcheck.py --config-dir /config --check live --quiet || echo "FAILED"

# Check application logs
kubectl logs -n edi deployment/bots-webserver --tail=100
kubectl logs -n edi deployment/bots-jobqueue
# Verify storage class exists
kubectl get storageclass

# Check provisioner logs
kubectl logs -n kube-system -l app=nfs-provisioner
```

### Health Checks Failing

```bash
# Test liveness
kubectl exec -n edi deployment/bots-webserver -- \
  curl -f http://localhost:8080/health/live || echo "FAILED"

# Check application logs
kubectl logs -n edi deployment/bots-webserver --tail=100

# Verify paths exist
kubectl exec -n edi deployment/bots-webserver -- \
  ls -la /home/bots/.bots
```

### Engine Not Processing

```bash
# Check CronJob status
kubectl get cronjob bots-engine -n edi

# View recent jobs
kubectl get jobs -n edi -l app=bots-edi

# Check latest job logs
kubectl logs -n edi job/<latest-job-name>

# Manually trigger engine
kubectl create job --from=cronjob/bots-engine test-run -n edi
```

## Upgrading

### Minor Version Upgrade

```bash
# Update image tag
kubectl set image deployment/bots-webserver \
  webserver=harbor.pminc.me/priv/bots-edi:v1.2.0 -n edi

kubectl set image deployment/bots-jobqueue \
  jobqueue=harbor.pminc.me/priv/bots-edi:v1.2.0 -n edi

# Update CronJob
kubectl set image cronjob/bots-engine \
  engine=harbor.pminc.me/priv/bots-edi:v1.2.0 -n edi
```

### Major Version Upgrade

1. **Backup database and data**
   ```bash
   kubectl exec -n edi deployment/bots-webserver -- \
     python manage.py dumpdata > backup-$(date +%Y%m%d).json
   ```

2. **Review release notes** for breaking changes

3. **Test in staging environment first**

4. **Update ConfigMaps** if configuration format changed

5. **Run database migrations**
   ```bash
   kubectl exec -n edi deployment/bots-webserver -- \
     python manage.py migrate
   ```

6. **Update deployments** with new image version

7. **Verify functionality** through web UI and engine runs
Secure the superuser secret** - use SealedSecrets or external secret management in production
3. **Use strong passwords** for database and Django SECRET_KEY (minimum 32 characters)
4. **Rotate credentials regularly** - database passwords, admin password, SECRET_KEY
5. **Enable TLS** on ingress with valid certificates
6. **Restrict network access** using NetworkPolicies
7. **Regularly update** container images for security patches
8. **Use sealed secrets** or external secret management (Vault, AWS Secrets Manager) for production
9. **Enable RBAC** and limit service account permissions
10. **Scan images** for vulnerabilities before deployment
11. **Audit user access** regularly through Django admin
12. **Enable Django security features** in settings.py (CSRF, XSS protection, etc.)
# Or delete namespace (includes all resources)
kubectl delete namespace edi

# Note: PVCs may need manual deletion if using retain policy
kubectl delete pvc -n edi --all
```

## Security Considerations

1. **Change default admin password** immediately after first login
2. **Use strong passwords** for database and Django SECRET_KEY
3. **Enable TLS** on ingress with valid certificates
4. **Restrict network access** using NetworkPolicies
5. **Regularly update** container images for security patches
6. **Use sealed secrets** or external secret management for production
7. **Enable RBAC** and limit service account permissions
8. **Scan images** for vulnerabilities before deployment

## Performance Tuning

### Resource Limits

Adjust based on workload:
```yaml
resources:
  requests:
    cpu: 200m      # Minimum guaranteed
    memory: 512Mi
  limits:
    cpu: 2000m     # Maximum allowed
    memory: 2Gi
```

### Engine Schedule

High-volume environments may need more frequent processing:
```yaml
spec:
  schedule: "*/2 * * * *"  # Every 2 minutes
```

### Replica Count

Scale webserver based on traffic:
```bash
kubectl scale deployment/bots-webserver -n edi --replicas=5
```

### Database Connection Pooling

Configure in Django settings via ConfigMap:
```python
DATABASES['default']['OPTIONS'] = {
    'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
    'charset': 'utf8mb4',
}
DATABASES['default']['CONN_MAX_AGE'] = 600
```

## Support

- **Documentation**: [docs/](.)
- **Issues**: GitHub Issues
- **Commercial Support**: EDI Intelligentsia - https://www.edi-intelligentsia.com
- **Community**: Bots EDI community forums

## License

Bots EDI is licensed under GNU GENERAL PUBLIC LICENSE Version 3.  
Full license: http://www.gnu.org/copyleft/gpl.html

## Additional Resources

- [Multi-Environment Deployment Guide](../k3s/DEPLOYMENT.md)
- [Secret Management Guide](../k3s/secrets/README.md)
- [Development Guide](development.md)
- [Architecture Documentation](architecture.md)
- [Operations Runbook](operations-runbook.md)
- [Contributing Guidelines](../CONTRIBUTING.md)
