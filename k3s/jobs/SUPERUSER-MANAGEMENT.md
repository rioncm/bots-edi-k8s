# Bots-EDI Superuser Management

## Quick Start

### Create Superuser Secret

```bash
# Generate secure password
ADMIN_PASSWORD=$(openssl rand -base64 24)

# Create secret
kubectl create secret generic bots-superuser-secret \
  --from-literal=SUPERUSER_USERNAME=admin \
  --from-literal=SUPERUSER_EMAIL=admin@yourcompany.com \
  --from-literal=SUPERUSER_PASSWORD="$ADMIN_PASSWORD" \
  -n edi

# Save credentials securely
echo "Bots-EDI Admin Credentials" > admin-credentials.txt
echo "Username: admin" >> admin-credentials.txt
echo "Password: $ADMIN_PASSWORD" >> admin-credentials.txt
chmod 600 admin-credentials.txt

echo "✓ Superuser secret created"
echo "✓ Credentials saved to admin-credentials.txt"
```

### Run Superuser Creation Job

```bash
# Deploy the job
kubectl apply -f k3s/jobs/create-superuser-job.yaml

# Wait for completion
kubectl wait --for=condition=complete job/bots-create-superuser -n edi --timeout=2m

# View logs
kubectl logs job/bots-create-superuser -n edi

# Expected output:
# [INFO] Creating Django superuser (idempotent)...
# [SUCCESS] Created superuser 'admin'
# [INFO] Superuser 'admin' is ready
```

## Retrieve Admin Credentials

If you need to retrieve the admin password:

```bash
# Get username
kubectl get secret bots-superuser-secret -n edi -o jsonpath='{.data.SUPERUSER_USERNAME}' | base64 -d
echo

# Get password
kubectl get secret bots-superuser-secret -n edi -o jsonpath='{.data.SUPERUSER_PASSWORD}' | base64 -d
echo

# Get email
kubectl get secret bots-superuser-secret -n edi -o jsonpath='{.data.SUPERUSER_EMAIL}' | base64 -d
echo
```

## Change Admin Password

### Method 1: Via Web UI (Recommended)

1. Login to Bots-EDI web interface
2. Click your username in top-right corner
3. Select "Change password"
4. Enter current password and new password
5. Click "Change my password"

### Method 2: Via Secret Update

```bash
# Generate new password
NEW_PASSWORD=$(openssl rand -base64 24)

# Update secret
kubectl delete secret bots-superuser-secret -n edi
kubectl create secret generic bots-superuser-secret \
  --from-literal=SUPERUSER_USERNAME=admin \
  --from-literal=SUPERUSER_EMAIL=admin@yourcompany.com \
  --from-literal=SUPERUSER_PASSWORD="$NEW_PASSWORD" \
  -n edi

# Re-run superuser job to apply new password
kubectl delete job bots-create-superuser -n edi 2>/dev/null || true
kubectl apply -f k3s/jobs/create-superuser-job.yaml

# Wait for completion
kubectl wait --for=condition=complete job/bots-create-superuser -n edi --timeout=2m

echo "✓ Password updated to: $NEW_PASSWORD"
```

## Create Additional Admin Users

Via Django shell in webserver pod:

```bash
kubectl exec -it -n edi deployment/bots-webserver -- python manage.py shell << 'PYEOF'
from django.contrib.auth import get_user_model
User = get_user_model()

user = User.objects.create_superuser(
    username='jane.admin',
    email='jane@yourcompany.com',
    password='secure-password-here'
)
print(f"Created superuser: {user.username}")
PYEOF
```

Or via Django admin web UI:
1. Login as admin
2. Navigate to: Admin → Authentication and Authorization → Users
3. Click "Add user" button
4. Fill in username and password
5. Check "Superuser status" and "Staff status"
6. Click "Save"

## Reset Admin Password (Emergency)

If you've lost the admin password:

```bash
# Generate new password
NEW_PASSWORD=$(openssl rand -base64 24)

# Update via Django shell
kubectl exec -it -n edi deployment/bots-webserver -- python manage.py shell << PYEOF
from django.contrib.auth import get_user_model
User = get_user_model()

user = User.objects.get(username='admin')
user.set_password('${NEW_PASSWORD}')
user.save()
print('Password reset successfully')
PYEOF

echo "New password: $NEW_PASSWORD"
```

## Troubleshooting

### Job Fails with "User already exists"

This is normal - the job is idempotent. It will update the existing user with the password from the secret.

### Cannot login after password change

1. Verify secret has correct password:
   ```bash
   kubectl get secret bots-superuser-secret -n edi -o yaml
   ```

2. Re-run the superuser job:
   ```bash
   kubectl delete job bots-create-superuser -n edi
   kubectl apply -f k3s/jobs/create-superuser-job.yaml
   ```

3. Check job logs for errors:
   ```bash
   kubectl logs job/bots-create-superuser -n edi
   ```

### Secret not found error

Create the secret:
```bash
kubectl create secret generic bots-superuser-secret \
  --from-literal=SUPERUSER_USERNAME=admin \
  --from-literal=SUPERUSER_EMAIL=admin@example.com \
  --from-literal=SUPERUSER_PASSWORD='change-this-password' \
  -n edi
```

## Security Best Practices

1. **Use strong passwords**: Minimum 16 characters, use password generator
2. **Change default password immediately** after first deployment
3. **Rotate credentials regularly**: Every 90 days minimum
4. **Use SealedSecrets** or external secret management in production
5. **Never commit** unencrypted secrets to Git
6. **Limit admin access**: Create regular users for day-to-day operations
7. **Enable audit logging**: Track admin actions
8. **Use MFA** if integrating with external auth (LDAP/SAML)

## Multi-Environment Setup

### Development
```bash
kubectl create secret generic bots-superuser-secret \
  --from-literal=SUPERUSER_USERNAME=admin \
  --from-literal=SUPERUSER_EMAIL=admin@dev.example.com \
  --from-literal=SUPERUSER_PASSWORD='dev-password-123' \
  -n edi-dev
```

### Staging
```bash
kubectl create secret generic bots-superuser-secret \
  --from-literal=SUPERUSER_USERNAME=admin \
  --from-literal=SUPERUSER_EMAIL=admin@staging.example.com \
  --from-literal=SUPERUSER_PASSWORD='$(openssl rand -base64 24)' \
  -n edi-staging
```

### Production
```bash
# Use sealed secrets or external secret manager
# Never use simple passwords in production!
```

## Related Documentation

- [Kubernetes Deployment Guide](../../docs/kubernetes-deployment.md)
- [Secret Management](../secrets/README.md)
- [Operations Runbook](../../docs/operations-runbook.md)
