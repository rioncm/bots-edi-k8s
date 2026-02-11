# Kubernetes Deployment

This helper is designed for Kubernetes Job or CronJob execution with:
- RWX PVC mounted at a known path
- ConfigMap containing the YAML rules
- Secret containing MinIO credentials

## Manifests
- `k8s/configmap.yaml`
- `k8s/secret.yaml`
- `k8s/job.yaml`
- `k8s/cronjob.yaml`

## Steps
1. Create the ConfigMap from your config:

```bash
kubectl apply -f minio_helper/k8s/configmap.yaml
```

2. Create the Secret with MinIO credentials:

```bash
kubectl apply -f minio_helper/k8s/secret.yaml
```

3. Run as a Job or CronJob:

```bash
kubectl apply -f minio_helper/k8s/job.yaml
# or
kubectl apply -f minio_helper/k8s/cronjob.yaml
```

## PVC
Update the PVC name and mount path in the Job/CronJob manifests to match your cluster.
