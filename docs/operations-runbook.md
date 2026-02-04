# Bots EDI - Operations Runbook

## Purpose

This runbook provides operational procedures for running Bots EDI in production on Kubernetes. It covers common tasks, troubleshooting, and incident response.

## Table of Contents

- [Daily Operations](#daily-operations)
- [Monitoring](#monitoring)
- [Common Tasks](#common-tasks)
- [Backup and Restore](#backup-and-restore)
- [Incident Response](#incident-response)
- [Maintenance](#maintenance)
- [Troubleshooting](#troubleshooting)

## Daily Operations

### Health Checks

**Morning Checks** (5 minutes):
```bash
# Check pod status
kubectl get pods -n edi

# Check recent logs for errors
kubectl logs -n edi -l app=bots-edi --since=24h | grep -i error

# Verify recent engine runs
kubectl get jobs -n edi -l app=bots-edi

# Check PVC usage
kubectl exec -n edi deployment/bots-webserver -- df -h /home/bots/.bots
```

**Expected**: All pods Running, no critical errors, CronJobs executing

### Transaction Monitoring

```bash
# Access web UI
open https://bots-edi.pminc.me

# Check dashboard for:
# - Transaction count (last 24h)
# - Error rate (<1% acceptable)
# - Queue depth (<100 acceptable)
# - Processing time (avg <30s)
```

### Quick Status Check

```bash
#!/bin/bash
# save as: check-bots-status.sh

echo "=== BOTS EDI STATUS ==="
echo

echo "Pods:"
kubectl get pods -n edi -l app=bots-edi

echo

echo "Services:"
kubectl get svc -n edi

echo

echo "Recent Jobs:"
kubectl get jobs -n edi -l app=bots-edi --sort-by=.metadata.creationTimestamp | tail -5

echo

echo "Ingress:"
kubectl get ingress -n edi

echo

echo "Health Check:"
curl -sf https://bots-edi.pminc.me/health/ping && echo "✓ Healthy" || echo "✗ Unhealthy"
```

## Monitoring

### Key Metrics

**Application Metrics**:
- Transactions processed/hour
- Average processing time
- Error rate (%)
- Queue depth
- Active connections

**Infrastructure Metrics**:
- Pod CPU usage
- Pod memory usage
- PVC capacity
- Database connections
- Network traffic

### Prometheus Queries

```promql
# Transaction rate
rate(bots_transactions_total[5m])

# Error rate
rate(bots_errors_total[5m]) / rate(bots_transactions_total[5m])

# Processing time
histogram_quantile(0.95, rate(bots_processing_duration_seconds_bucket[5m]))

# Pod CPU usage
container_cpu_usage_seconds_total{namespace="edi",pod=~"bots-.*"}

# Pod memory
container_memory_working_set_bytes{namespace="edi",pod=~"bots-.*"}
```

### Alerts

**Critical**:
- All webserver pods down → Page on-call
- Database unreachable → Page on-call
- PVC >90% full → Page on-call

**Warning**:
- Error rate >5% → Slack notification
- Processing time >2 minutes → Slack notification
- Engine job failed → Slack notification

## Common Tasks

### Restart a Service

```bash
# Restart webserver
kubectl rollout restart deployment/bots-webserver -n edi

# Restart job queue
kubectl rollout restart deployment/bots-jobqueue -n edi

# Wait for rollout
kubectl rollout status deployment/bots-webserver -n edi
```

### Scale Webserver

```bash
# Scale up
kubectl scale deployment/bots-webserver -n edi --replicas=5

# Scale down
kubectl scale deployment/bots-webserver -n edi --replicas=2

# Verify
kubectl get pods -n edi -l component=webserver
```

### Manual Engine Run

```bash
# Trigger engine immediately
kubectl create job --from=cronjob/bots-engine bots-engine-manual-$(date +%s) -n edi

# Watch logs
kubectl logs -n edi -f job/bots-engine-manual-<timestamp>
```

### Update Container Image

```bash
# Update to specific version
kubectl set image deployment/bots-webserver \
  webserver=harbor.pminc.me/priv/bots-edi:v1.2.0 -n edi

kubectl set image deployment/bots-jobqueue \
  jobqueue=harbor.pminc.me/priv/bots-edi:v1.2.0 -n edi

kubectl set image cronjob/bots-engine \
  engine=harbor.pminc.me/priv/bots-edi:v1.2.0 -n edi

# Monitor rollout
kubectl rollout status deployment/bots-webserver -n edi
```

### Update Configuration

```bash
# Edit ConfigMap
kubectl edit configmap bots-config-ini -n edi

# Restart pods to pick up changes
kubectl rollout restart deployment/bots-webserver -n edi
kubectl rollout restart deployment/bots-jobqueue -n edi
```

### View Logs

```bash
# All bots-edi logs (last hour)
kubectl logs -n edi -l app=bots-edi --since=1h --tail=500

# Webserver logs (follow)
kubectl logs -n edi -l component=webserver -f

# Job queue logs
kubectl logs -n edi -l component=jobqueue --tail=100

# Engine logs (latest job)
kubectl logs -n edi -l app=bots-edi,job-name --tail=200

# Specific pod
kubectl logs -n edi <pod-name> --tail=100 -f

# Previous container (if crashed)
kubectl logs -n edi <pod-name> --previous
```

### Access Database

```bash
# Via webserver pod
kubectl exec -it -n edi deployment/bots-webserver -- bash

# Inside pod
python manage.py dbshell
# or
mysql -h kona.db.pminc.me -u botsedi -p botsedi_data
```

## Backup and Restore

### Database Backup

**Automated (Recommended)**:
```bash
# Set up CronJob for daily backups
kubectl apply -f - <<EOF
apiVersion: batch/v1
kind: CronJob
metadata:
  name: bots-db-backup
  namespace: edi
spec:
  schedule: "0 2 * * *"  # 2 AM daily
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure
          containers:
          - name: backup
            image: harbor.pminc.me/priv/bots-edi:latest
            command:
            - /bin/bash
            - -c
            - |
              DATE=\$(date +%Y%m%d-%H%M%S)
              python manage.py dumpdata --exclude auth.permission --exclude contenttypes > /backup/backup-\${DATE}.json
              # Keep last 30 days
              find /backup -name "backup-*.json" -mtime +30 -delete
            volumeMounts:
            - name: backup
              mountPath: /backup
          volumes:
          - name: backup
            persistentVolumeClaim:
              claimName: bots-backup-pvc
EOF
```

**Manual Backup**:
```bash
# Django dumpdata
kubectl exec -n edi deployment/bots-webserver -- \
  python manage.py dumpdata \
  --exclude auth.permission \
  --exclude contenttypes \
  > backup-$(date +%Y%m%d).json

# MySQL dump
kubectl exec -n edi deployment/bots-webserver -- \
  mysqldump -h kona.db.pminc.me -u botsedi -p botsedi_data \
  > backup-$(date +%Y%m%d).sql
```

### PVC Backup

**Using Velero**:
```bash
# Backup all PVCs in namespace
velero backup create bots-edi-backup --include-namespaces edi

# Verify backup
velero backup describe bots-edi-backup

# List backups
velero backup get
```

**Manual Snapshot** (if CSI supports):
```bash
# Create VolumeSnapshot
kubectl apply -f - <<EOF
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: bots-data-snapshot-$(date +%Y%m%d)
  namespace: edi
spec:
  volumeSnapshotClassName: csi-snapclass
  source:
    persistentVolumeClaimName: bots-edi-data-pvc
EOF
```

### Restore from Backup

**Database Restore**:
```bash
# Django loaddata
kubectl exec -i -n edi deployment/bots-webserver -- \
  python manage.py loaddata < backup-20260204.json

# MySQL restore
kubectl exec -i -n edi deployment/bots-webserver -- \
  mysql -h kona.db.pminc.me -u botsedi -p botsedi_data \
  < backup-20260204.sql
```

**PVC Restore**:
```bash
# Create PVC from snapshot
kubectl apply -f - <<EOF
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: bots-edi-data-pvc-restored
  namespace: edi
spec:
  dataSource:
    name: bots-data-snapshot-20260204
    kind: VolumeSnapshot
    apiGroup: snapshot.storage.k8s.io
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 20Gi
  storageClassName: t1-shiva-nfs
EOF

# Update deployments to use restored PVC
kubectl edit deployment/bots-webserver -n edi
# Change claimName to: bots-edi-data-pvc-restored
```

## Incident Response

### Service Outage

**Symptoms**: Web UI unreachable, all services down

**Immediate Actions**:
1. Check pod status:
   ```bash
   kubectl get pods -n edi
   ```

2. Check node status:
   ```bash
   kubectl get nodes
   ```

3. Check ingress:
   ```bash
   kubectl get ingress -n edi
   kubectl describe ingress bots-edi-ingress -n edi
   ```

4. Check recent events:
   ```bash
   kubectl get events -n edi --sort-by='.lastTimestamp' | tail -20
   ```

**Resolution**:
- If pods CrashLoopBackOff → Check logs, fix configuration
- If nodes NotReady → Check node health, may need to drain/cordone
- If ingress misconfigured → Reapply correct ingress manifest
- If PVC not bound → Check storage provisioner

**Recovery Time**: Target <15 minutes

### Database Connection Loss

**Symptoms**: Pods running but operations failing, "Can't connect to MySQL" errors

**Immediate Actions**:
1. Test database connectivity:
   ```bash
   kubectl exec -n edi deployment/bots-webserver -- \
     nc -zv kona.db.pminc.me 3306
   ```

2. Check database server status:
   ```bash
   # On DB server
   systemctl status mysql
   ```

3. Verify secret:
   ```bash
   kubectl get secret bots-edidb-secret -n edi
   ```

**Resolution**:
- If DB server down → Restart MySQL, check logs
- If credentials wrong → Update secret, restart pods
- If network issue → Check firewall, security groups

**Recovery Time**: Depends on DB recovery (5-30 minutes)

### High Error Rate

**Symptoms**: Error rate >10%, transactions failing

**Investigation**:
1. Check recent logs:
   ```bash
   kubectl logs -n edi -l app=bots-edi --since=30m | grep -i error | head -50
   ```

2. Check specific errors:
   ```bash
   # Grammar errors
   grep "Grammar not found" /var/log/bots/*.log
   
   # Transformation errors
   grep "Mapping error" /var/log/bots/*.log
   ```

3. Access web UI dashboard:
   ```bash
   open https://bots-edi.pminc.me/admin/
   ```

**Common Causes**:
- Invalid input files → Contact trading partner
- Missing grammar → Deploy missing grammar file
- Configuration error → Review recent changes
- Resource exhaustion → Scale up replicas

### Disk Space Full

**Symptoms**: PVC at 100%, operations failing

**Immediate Actions**:
1. Check usage:
   ```bash
   kubectl exec -n edi deployment/bots-webserver -- df -h
   ```

2. Find large files:
   ```bash
   kubectl exec -n edi deployment/bots-webserver -- \
     du -sh /home/bots/.bots/* | sort -hr | head -20
   ```

3. Clean up old files:
   ```bash
   kubectl exec -n edi deployment/bots-webserver -- \
     find /home/bots/.bots/botssys/data -name "*.old" -mtime +30 -delete
   ```

4. If urgent, expand PVC:
   ```bash
   kubectl edit pvc bots-edi-data-pvc -n edi
   # Increase storage: 20Gi → 30Gi
   ```

**Prevention**:
- Set up log rotation
- Archive old transactions
- Monitor disk usage alerts

## Maintenance

### Planned Maintenance Window

**Preparation** (Day before):
1. Notify users
2. Schedule backup
3. Prepare rollback plan
4. Review change procedure

**During Maintenance**:
1. Put webserver in maintenance mode (optional)
2. Perform changes
3. Run tests
4. Monitor for issues

**Post-Maintenance**:
1. Verify all services healthy
2. Check recent transactions processed successfully
3. Monitor for 30 minutes
4. Send all-clear notification

### Database Migration

```bash
# 1. Backup database
kubectl exec -n edi deployment/bots-webserver -- \
  python manage.py dumpdata > pre-migration-backup.json

# 2. Apply migrations
kubectl exec -n edi deployment/bots-webserver -- \
  python manage.py migrate

# 3. Verify
kubectl exec -n edi deployment/bots-webserver -- \
  python manage.py showmigrations

# 4. Test application
curl https://bots-edi.pminc.me/health/ready
```

### Certificate Renewal

```bash
# Check certificate expiry
kubectl get certificate -n edi

# Force renewal (cert-manager)
kubectl delete secret bots-edi-tls -n edi
kubectl annotate certificate bots-edi-ingress -n edi \
  cert-manager.io/issue-temporary-certificate="true"

# Verify new certificate
kubectl get certificate -n edi
```

## Troubleshooting

### Pod Won't Start

**Check Events**:
```bash
kubectl describe pod <pod-name> -n edi
```

**Common Issues**:
- **ImagePullBackOff**: Check registry credentials, image tag exists
- **CrashLoopBackOff**: Check logs for startup errors
- **Pending**: Check PVC binding, resource availability

### Health Check Failing

**Test Manually**:
```bash
# Liveness
kubectl exec -n edi deployment/bots-webserver -- \
  curl -f http://localhost:8080/health/live

# Readiness
kubectl exec -n edi deployment/bots-webserver -- \
  curl -f http://localhost:8080/health/ready
```

**Common Causes**:
- Database unreachable
- Required paths missing
- Application not fully started

### Engine Not Processing Files

**Check**:
```bash
# CronJob status
kubectl get cronjob bots-engine -n edi

# Recent jobs
kubectl get jobs -n edi -l app=bots-edi

# Job logs
kubectl logs -n edi job/<latest-job-name>
```

**Common Issues**:
- CronJob suspended: `kubectl patch cronjob/bots-engine -n edi -p '{"spec":{"suspend":false}}'`
- Concurrency policy blocking: Wait for current job to complete
- Files in wrong directory: Check input path configuration

### Performance Degradation

**Investigation**:
```bash
# Check resource usage
kubectl top pods -n edi

# Check database queries
kubectl exec -n edi deployment/bots-webserver -- \
  python manage.py dbshell
# SHOW FULL PROCESSLIST;

# Check NFS performance
kubectl exec -n edi deployment/bots-webserver -- \
  dd if=/dev/zero of=/home/bots/.bots/test bs=1M count=100
```

**Solutions**:
- Scale up replicas if CPU high
- Optimize database queries
- Check NFS server load
- Review recent code changes

## Contact Information

- **On-Call Engineer**: PagerDuty
- **Database Admin**: dba@pminc.me
- **Kubernetes Admin**: k8s-admin@pminc.me
- **Security Team**: security@pminc.me

## Escalation

1. **Level 1**: On-call engineer (15 min response)
2. **Level 2**: Senior SRE (30 min response)
3. **Level 3**: Engineering manager (1 hour response)

## References

- [Kubernetes Deployment Guide](kubernetes-deployment.md)
- [Architecture Documentation](architecture.md)
- [Development Guide](development.md)
- [Bots EDI Documentation](https://bots.readthedocs.io)
