# Kubernetes Deployment for Bots-EDI

This directory contains Kubernetes manifests for deploying Bots-EDI in a cloud-native environment.

## Overview

Bots-EDI is an open source EDI (Electronic Data Interchange) translator. This Kubernetes deployment provides:

- **Multi-service architecture**: Webserver, job queue, and EDI processing engine
- **Health checks**: Built-in liveness, readiness, and startup probes
- **Scalability**: Horizontal scaling for web components
- **Configuration management**: ConfigMaps for easy configuration updates
- **Storage**: Persistent volumes for data, logs, and configurations
- **Automated processing**: CronJob-based EDI file processing

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Webserver   │────▶│  Job Queue   │────▶│    Engine    │
│   (Django)   │     │  (XML-RPC)   │     │  (CronJob)   │
└──────────────┘     └──────────────┘     └──────────────┘
       │                     │                     │
       └─────────────────────┴─────────────────────┘
                             │
                      ┌──────▼──────┐
                      │   Database  │
                      │   (MySQL)   │
                      └─────────────┘
```

## Directory Structure

```
k3s/
├── base/                          # Base Kubernetes resources
│   ├── namespace.yaml             # Namespace definition
│   ├── configmap-botsini.yaml     # bots.ini configuration
│   ├── configmap-settings.yaml    # Django settings
│   ├── pvc.yaml                   # Persistent volume claims
│   └── service-webserver.yaml     # Webserver service
│
├── deployments/                   # Application deployments
│   ├── webserver.yaml             # Web UI (Django admin)
│   └── jobqueue.yaml              # Background job processing
│
├── jobs/                          # Kubernetes jobs
│   ├── db-init-job.yaml           # Database initialization
│   └── engine-cronjob.yaml        # Scheduled EDI processing
│
├── overlays/                      # Kustomize overlays
│   ├── dev/                       # Development environment
│   ├── staging/                   # Staging environment
│   └── prod/                      # Production environment
│
└── secrets/                       # Secret templates
    └── example-secret.yaml        # Example database secret
```

## Prerequisites

- **Kubernetes cluster**: v1.19+ (tested on k3s, EKS, GKE, AKS)
- **Storage class**: ReadWriteMany (RWX) storage for shared volumes (NFS, CephFS, etc.)
- **Database**: MySQL 5.7+ or MariaDB 10.3+ (PostgreSQL support also available)
- **Container registry**: Access to Docker Hub or private registry
- **kubectl**: v1.19+ with cluster access
- **Optional**: kustomize v3.0+ for overlay management

## Quick Start

### 1. Configure Your Environment

Create a namespace for Bots-EDI:

```bash
kubectl apply -f k3s/base/namespace.yaml
```

### 2. Configure Database Secret

Create a secret with your database credentials:

```bash
kubectl create secret generic bots-edidb-secret \
  --from-literal=DB_HOST=your-db-host \
  --from-literal=DB_NAME=botsedi \
  --from-literal=DB_USER=botsedi \
  --from-literal=DB_PASSWORD=your-password \
  -n edi
```

Or use the example template:

```bash
# Copy and edit the example
cp k3s/secrets/example-secret.yaml k3s/secrets/secret.yaml
# Edit with your credentials
kubectl apply -f k3s/secrets/secret.yaml
```

### 3. Update ConfigMaps

Edit the ConfigMaps to match your environment:

**bots.ini** (`k3s/base/configmap-botsini.yaml`):
- Set retention periods
- Configure directories
- Adjust settings for your needs

**settings.py** (`k3s/base/configmap-settings.yaml`):
- Verify database configuration
- Set allowed hosts
- Configure email settings (optional)

### 4. Deploy Using Kustomize

```bash
# Deploy base configuration
kubectl apply -k k3s/base/

# Or deploy with environment-specific overlay
kubectl apply -k k3s/overlays/dev/
```

### 5. Initialize Database

Run the one-time database initialization job:

```bash
kubectl apply -f k3s/jobs/db-init-job.yaml

# Wait for completion
kubectl wait --for=condition=complete --timeout=300s job/bots-db-init -n edi

# Check logs
kubectl logs -n edi job/bots-db-init
```

### 6. Deploy Applications

```bash
# Deploy webserver and job queue
kubectl apply -f k3s/deployments/webserver.yaml
kubectl apply -f k3s/deployments/jobqueue.yaml

# Deploy engine CronJob
kubectl apply -f k3s/jobs/engine-cronjob.yaml

# Verify deployment
kubectl get all -n edi
```

## Configuration

### Storage Requirements

The deployment requires three persistent volumes:

| Volume | Size | Access Mode | Purpose |
|--------|------|-------------|---------|
| `bots-edi-data-pvc` | 20Gi | ReadWriteMany | EDI files and data |
| `bots-edi-logs-pvc` | 5Gi | ReadWriteMany | Application logs |
| `bots-edi-config-pvc` | 1Gi | ReadWriteMany | Runtime configuration |

Adjust sizes in `k3s/base/pvc.yaml` based on your needs.

### Environment Variables

Configure via ConfigMaps or deployment environment:

| Variable | Default | Description |
|----------|---------|-------------|
| `BOTSENV` | `default` | Bots environment name |
| `DB_INIT_SKIP` | `false` | Skip database initialization on startup |
| `CONFIG_DIR` | `/config` | Configuration directory path |
| `PORT` | `8080` | Webserver port |

### Service Configuration

The webserver is exposed as a ClusterIP service on port 8080:

```bash
# Access via port-forward
kubectl port-forward -n edi svc/bots-webserver 8080:8080

# Or create an Ingress for external access
```

## Health Checks

All deployments include health check endpoints:

- **Liveness**: `/health/live` - Is the process running?
- **Readiness**: `/health/ready` - Can it accept traffic?
- **Startup**: `/health/startup` - Has initialization completed?

Test health checks:

```bash
# Via kubectl
kubectl port-forward -n edi svc/bots-webserver 8080:8080
curl http://localhost:8080/health/ready

# Direct pod exec
kubectl exec -n edi deployment/bots-webserver -- \
  python /usr/local/bots/scripts/healthcheck.py --check ready
```

## Operations

### Updating Configuration

Update ConfigMaps and restart pods:

```bash
# Edit configuration
kubectl edit configmap -n edi bots-config-ini

# Restart to apply changes
kubectl rollout restart deployment/bots-webserver -n edi
kubectl rollout restart deployment/bots-jobqueue -n edi
```

### Updating Image

```bash
# Update to specific version
kubectl set image deployment/bots-webserver \
  webserver=your-registry/bots-edi:v4.0.1 -n edi

# Or edit deployment directly
kubectl edit deployment/bots-webserver -n edi
```

### Scaling

```bash
# Scale webserver (supports multiple replicas)
kubectl scale deployment/bots-webserver -n edi --replicas=3

# Job queue should remain at 1 replica
# Engine runs as CronJob (scheduled)
```

### Viewing Logs

```bash
# Webserver logs
kubectl logs -n edi -l component=webserver --tail=100 -f

# Job queue logs
kubectl logs -n edi -l component=jobqueue --tail=100 -f

# Engine job logs (get latest job)
kubectl logs -n edi -l component=engine --tail=100
```

### Manual Engine Run

Trigger EDI processing manually:

```bash
# Create job from CronJob template
kubectl create job --from=cronjob/bots-engine -n edi bots-engine-manual

# Watch progress
kubectl logs -n edi -l job-name=bots-engine-manual -f
```

## Troubleshooting

### Pod Not Starting

```bash
# Check pod status
kubectl describe pod -n edi <pod-name>

# Check events
kubectl get events -n edi --sort-by='.lastTimestamp'

# Check logs
kubectl logs -n edi <pod-name>
```

### Database Connection Issues

```bash
# Verify secret exists
kubectl get secret -n edi bots-edidb-secret

# Test database connectivity from pod
kubectl exec -it -n edi deployment/bots-webserver -- \
  python -c "from django.db import connection; connection.ensure_connection(); print('OK')"
```

### Storage Issues

```bash
# Check PVC status
kubectl get pvc -n edi

# Check PV binding
kubectl get pv | grep edi

# Verify storage class
kubectl get storageclass
```

### Health Check Failures

```bash
# Run health check manually
kubectl exec -it -n edi deployment/bots-webserver -- \
  python /usr/local/bots/scripts/healthcheck.py --check startup --verbose

# Check startup logs
kubectl logs -n edi <pod-name> --previous
```

## Multi-Environment Setup

Use Kustomize overlays for different environments:

```bash
# Development
kubectl apply -k k3s/overlays/dev/

# Staging
kubectl apply -k k3s/overlays/staging/

# Production
kubectl apply -k k3s/overlays/prod/
```

Each overlay can customize:
- Resource limits
- Replica counts
- Image tags
- Storage sizes
- Environment-specific configuration

## Security Considerations

1. **Secrets Management**: Store database credentials in Kubernetes Secrets or external secret managers (Vault, AWS Secrets Manager, etc.)
2. **Network Policies**: Consider implementing NetworkPolicies to restrict pod-to-pod communication
3. **RBAC**: Apply principle of least privilege for service accounts
4. **Container Security**: Use read-only root filesystems where possible
5. **Image Scanning**: Scan container images for vulnerabilities
6. **TLS**: Use TLS for database connections and ingress

## Production Recommendations

1. **High Availability**:
   - Run 2+ webserver replicas behind a load balancer
   - Use a managed database service (RDS, Cloud SQL, etc.)
   - Deploy across multiple availability zones

2. **Resource Management**:
   - Set resource requests and limits
   - Configure PodDisruptionBudgets
   - Use HorizontalPodAutoscaler for web tier

3. **Monitoring**:
   - Integrate with Prometheus for metrics
   - Set up log aggregation (ELK, Loki, etc.)
   - Configure alerting for critical issues

4. **Backup**:
   - Regular database backups
   - Snapshot persistent volumes
   - Document recovery procedures

5. **Updates**:
   - Use rolling updates for zero-downtime deployments
   - Test in staging before production
   - Maintain rollback procedures

## Clean Up

Remove all resources:

```bash
# Using kustomize
kubectl delete -k k3s/base/

# Or delete namespace (removes all resources)
kubectl delete namespace edi
```

## Additional Resources

- [Bots-EDI Documentation](https://bots.readthedocs.io/)
- [Deployment Guide](DEPLOYMENT.md) - Detailed deployment procedures
- [Contributing Guide](../CONTRIBUTING.md) - How to contribute
- [Development Guide](../docs/development.md) - Local development setup

## Support

- **Issues**: Report bugs or request features via GitHub Issues
- **Documentation**: See official Bots documentation
- **Community**: Join the Bots-EDI community forums

## License

Bots-EDI is licensed under the GNU General Public License v3.0. See the LICENSE file for details.
