# Secret Management for Bots-EDI

This directory contains templates and documentation for managing secrets in the Bots-EDI application.

## Overview

Bots-EDI requires the following secrets:
- **Database credentials** (`bots-edidb-secret`): MySQL connection details and Django SECRET_KEY
- **Superuser credentials** (`bots-superuser-secret`): Default admin account for Django
- **Optional**: SMTP credentials for email notifications

## Required Secrets

### 1. Database Secret (`bots-edidb-secret`)

Contains database connection details and Django configuration:
- `DB_NAME`: Database name (e.g., `botsedi_data`)
- `DB_USER`: Database username (e.g., `botsedi`)
- `DB_PASSWORD`: Database password (secure, minimum 32 chars)
- `DB_HOST`: Database hostname (e.g., `mysql.db.example.com`)
- `DB_PORT`: Database port (default: `3306`)
- `DJANGO_SECRET_KEY`: Django secret key (generate with Django utils)

### 2. Superuser Secret (`bots-superuser-secret`)

Contains Django admin/superuser credentials:
- `SUPERUSER_USERNAME`: Admin username (default: `admin`)
- `SUPERUSER_EMAIL`: Admin email address
- `SUPERUSER_PASSWORD`: Admin password (secure, minimum 16 chars)

This secret is used by the `create-superuser-job` to create or update the default admin user.

## Approaches

### 1. Sealed Secrets (Recommended for GitOps)

Sealed Secrets encrypt your secrets so they can be safely stored in Git.

#### Installation

```bash
# Install sealed-secrets controller
kubectl apply -f sealed-secrets-setup.yaml

# Install kubeseal CLI (macOS)
brew install kubeseal

# Or download from GitHub releases
# https://github.com/bitnami-labs/sealed-secrets/releases
```

#### Usage

```bash
# 1. Create database secret (do not commit this!)
kubectl create secret generic bots-edidb-secret \
  --from-literal=DB_NAME=botsedi_data \
  --from-literal=DB_USER=botsedi \
  --from-literal=DB_PASSWORD='your-secure-db-password' \
  --from-literal=DB_HOST=mysql.db.example.com \
  --from-literal=DB_PORT=3306 \
  --from-literal=DJANGO_SECRET_KEY='your-django-secret-key' \
  --dry-run=client -o yaml > temp-db-secret.yaml

# Seal the database secret
kubeseal -f temp-db-secret.yaml -w sealed-db-secret.yaml

# 2. Create superuser secret (do not commit this!)
kubectl create secret generic bots-superuser-secret \
  --from-literal=SUPERUSER_USERNAME=admin \
  --from-literal=SUPERUSER_EMAIL=admin@example.com \
  --from-literal=SUPERUSER_PASSWORD='your-secure-admin-password' \
  --dry-run=client -o yaml > temp-superuser-secret.yaml

# Seal the superuser secret
kubeseal -f temp-superuser-secret.yaml -w sealed-superuser-secret.yaml

# 3. Delete the unencrypted files
rm temp-db-secret.yaml temp-superuser-secret.yaml

# 4. Commit the sealed secrets
git add sealed-secret.yaml
git commit -m "Add sealed database secret"

# Apply to cluster
kubectl apply -f sealed-secret.yaml -n edi
```

#### Per-Environment Secrets

Create sealed secrets for each environment:

```bash
# Development
kubeseal -f dev-secret.yaml -w k3s/overlays/dev/sealed-secret.yaml

# Staging  
kubeseal -f staging-secret.yaml -w k3s/overlays/staging/sealed-secret.yaml

# Production
kubeseal -f prod-secret.yaml -w k3s/overlays/prod/sealed-secret.yaml
```

### 2. External Secrets Operator (ESO)

For integration with external secret managers like HashiCorp Vault, AWS Secrets Manager, etc.

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: bots-edidb-secret
  namespace: edi
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault-backend
    kind: SecretStore
  target:
    name: bots-edidb-secret
    creationPolicy: Owner
  data:
    - secretKey: DB_PASSWORD
      remoteRef:
        key: secret/bots-edi/db
        property: password
```

### 3. Manual Secret Management (PM Inc Current Approach)

**For PM Inc deployment**, secrets are managed outside of Git and applied manually:

```bash
# Create secret from file (not in repo)
kubectl create secret generic bots-edidb-secret \
  --from-env-file=secrets.env \
  -n edi

# Or from literals
kubectl create secret generic bots-edidb-secret \
  --from-literal=DB_NAME=botsedi_data \
  --from-literal=DB_USER=botsedi \
  --from-literal=DB_PASSWORD='actual-password' \
  --from-literal=DB_HOST=kona.db.pminc.me \
  --from-literal=DB_PORT=3306 \
  --from-literal=DJANGO_SECRET_KEY='actual-secret-key' \
  -n edi
```

## Secret Structure

### Database Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: bots-edidb-secret
  namespace: edi
type: Opaque
stringData:
  DB_NAME: botsedi_data
  DB_USER: botsedi
  DB_PASSWORD: your-password-here
  DB_HOST: kona.db.pminc.me
  DB_PORT: "3306"
  DJANGO_SECRET_KEY: your-secret-key-here
```

### SMTP Secret (Optional)

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: bots-smtp-secret
  namespace: edi
type: Opaque
stringData:
  SMTP_HOST: smtp.example.com
  SMTP_PORT: "587"
  SMTP_USER: notifications@example.com
  SMTP_PASSWORD: smtp-password-here
  SMTP_FROM: bots-edi@example.com
```

## Secret Rotation

### With Sealed Secrets

1. Generate new secret values
2. Create and seal new secret manifest
3. Apply to cluster (controller will update automatically)
4. Restart affected pods if needed:
   ```bash
   kubectl rollout restart deployment/bots-webserver -n edi
   kubectl rollout restart deployment/bots-jobqueue -n edi
   ```

### Manual Rotation

1. Update the secret:
   ```bash
   kubectl create secret generic bots-edidb-secret \
     --from-literal=DB_PASSWORD='new-password' \
     --dry-run=client -o yaml | kubectl apply -f -
   ```

2. Restart deployments:
   ```bash
   kubectl rollout restart deployment/bots-webserver -n edi
   kubectl rollout restart deployment/bots-jobqueue -n edi
   ```

## Security Best Practices

1. **Never commit unencrypted secrets to Git**
2. **Use sealed-secrets or ESO for GitOps workflows**
3. **Rotate secrets regularly** (quarterly minimum)
4. **Use strong, randomly generated passwords**:
   ```bash
   # Generate Django SECRET_KEY
   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   
   # Generate random password (50 chars)
   openssl rand -base64 48
   ```
5. **Limit secret access with RBAC**
6. **Enable audit logging for secret access**
7. **Use different secrets per environment**

## Troubleshooting

### Pods stuck in Init or CrashLoopBackOff

Check if secret exists:
```bash
kubectl get secret bots-edidb-secret -n edi
```

Verify secret data:
```bash
kubectl get secret bots-edidb-secret -n edi -o jsonpath='{.data}'
```

### Sealed secret not creating actual secret

Check sealed-secrets controller logs:
```bash
kubectl logs -n kube-system -l app.kubernetes.io/name=sealed-secrets
```

Verify the sealed secret was created:
```bash
kubectl get sealedsecrets -n edi
```

### Wrong namespace

Sealed secrets are namespace-specific. Make sure you're sealing for the correct namespace:
```bash
kubeseal -f secret.yaml -w sealed-secret.yaml --namespace edi
```

## References

- [Sealed Secrets Documentation](https://github.com/bitnami-labs/sealed-secrets)
- [External Secrets Operator](https://external-secrets.io/)
- [Kubernetes Secrets](https://kubernetes.io/docs/concepts/configuration/secret/)
