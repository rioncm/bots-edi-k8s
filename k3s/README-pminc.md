# Quick Deployment Guide for Bots-EDI K8s Manifests

This directory contains refactored Kubernetes manifests for Bots-EDI with proper separation of concerns.

## Directory Structure

```
k3s/
├── base/                          # Base configuration
│   ├── namespace.yaml            # edi namespace
│   ├── configmap-botsini.yaml    # bots.ini configuration
│   ├── configmap-settings.yaml   # Django settings.py
│   ├── pvc.yaml                  # Persistent volume claims
│   └── service-webserver.yaml    # Webserver service
├── deployments/                   # Application deployments
│   ├── webserver.yaml            # Web UI (Django)
│   └── jobqueue.yaml             # Job queue server
├── jobs/                          # Kubernetes jobs
│   ├── db-init-job.yaml          # One-time database initialization
│   └── engine-cronjob.yaml       # Scheduled EDI processing
├── ingress.yaml                   # Traefik ingress (HTTPS)
├── sensor.yaml                    # Argo Events sensor (CI/CD)
├── secret.yaml                    # DB credentials (existing)
├── kustomization.yaml             # Kustomize configuration
└── README.md                      # This file
```

## Configuration

1. **NFS Storage or ReadWriteMany**: t1-shiva-nfs storage class configured
2. **Database**: MySQL database accessible (kona.db.pminc.me)
3. **Harbor Registry for custom image**: Access to harbor.pminc.me/priv/bots-edi
4. **Secrets**: bots-edidb-secret with DB credentials

## Deployment Order

### Option 1: Full Deployment with Kustomize

```bash
# Apply all manifests at once
kubectl apply -k k3s/

# Verify deployment
kubectl get all -n edi
```

### Option 2: Step-by-Step Deployment

```bash
# 1. Create namespace and base resources
kubectl apply -f k3s/base/namespace.yaml
kubectl apply -f k3s/base/pvc.yaml
kubectl apply -f k3s/base/configmap-botsini.yaml
kubectl apply -f k3s/base/configmap-settings.yaml
kubectl apply -f k3s/base/service-webserver.yaml

# 2. Apply secret (if not already exists)
kubectl apply -f k3s/secret.yaml

# 3. Initialize database (one-time)
kubectl apply -f k3s/jobs/db-init-job.yaml
kubectl wait --for=condition=complete --timeout=300s job/bots-db-init -n edi

# 4. Deploy applications
kubectl apply -f k3s/deployments/webserver.yaml
kubectl apply -f k3s/deployments/jobqueue.yaml

# 5. Set up engine cron job
kubectl apply -f k3s/jobs/engine-cronjob.yaml

# 6. Configure ingress and sensor
kubectl apply -f k3s/ingress.yaml
kubectl apply -f k3s/sensor.yaml
```

## Health Checks

```bash
# Check webserver health
kubectl port-forward -n edi svc/bots-webserver 8080:8080
curl http://localhost:8080/health/live
curl http://localhost:8080/health/ready
curl http://localhost:8080/health/startup

# Check pod status
kubectl get pods -n edi
kubectl describe pod -n edi <pod-name>

# Check logs
kubectl logs -n edi deployment/bots-webserver
kubectl logs -n edi deployment/bots-jobqueue
```

## Updating Configuration

### Update ConfigMaps

```bash
# Edit configuration
kubectl edit configmap -n edi bots-config-ini
kubectl edit configmap -n edi bots-config-settings

# Restart pods to pick up changes
kubectl rollout restart deployment/bots-webserver -n edi
kubectl rollout restart deployment/bots-jobqueue -n edi
```

### Update Image

```bash
# Update via Kustomize
cd k3s
kustomize edit set image harbor.pminc.me/priv/bots-edi:v4.0.1
kubectl apply -k .

# Or directly
kubectl set image deployment/bots-webserver -n edi webserver=harbor.pminc.me/priv/bots-edi:v4.0.1
```

## Troubleshooting

### Database Init Job Failed

```bash
# Check job logs
kubectl logs -n edi job/bots-db-init

# Delete and retry
kubectl delete job -n edi bots-db-init
kubectl apply -f k3s/jobs/db-init-job.yaml
```

### Webserver Not Ready

```bash
# Check startup probe
kubectl describe pod -n edi -l component=webserver

# Check logs
kubectl logs -n edi -l component=webserver --tail=100

# Manual health check
kubectl exec -it -n edi deployment/bots-webserver -- python /opt/bots/scripts/healthcheck.py --check startup
```

### Engine CronJob Not Running

```bash
# Check cronjob status
kubectl get cronjob -n edi bots-engine

# View recent jobs
kubectl get jobs -n edi -l component=engine

# Manually trigger
kubectl create job --from=cronjob/bots-engine -n edi bots-engine-manual
```

## Scaling

```bash
# Scale webserver (if stateless)
kubectl scale deployment/bots-webserver -n edi --replicas=2

# Note: jobqueue should remain at 1 replica
# Note: engine runs as CronJob, not deployment
```

## Clean Up

```bash
# Remove all resources
kubectl delete -k k3s/

# Or selectively
kubectl delete namespace edi
```

## Migration from Old Deployment

See [../fork/phase4-complete.md](../fork/phase4-complete.md) for detailed migration instructions.
