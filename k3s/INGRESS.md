# Traefik Ingress Configuration

This directory contains Traefik ingress configurations for exposing the Bots-EDI webserver externally.

## Overview

The ingress configurations provide:
- HTTPS/TLS termination
- Automatic certificate management via cert-manager
- Domain-based routing
- Environment-specific configurations

## Architecture

```
Internet
   │
   ├──> Traefik (Ingress Controller)
   │       │
   │       ├──> TLS Certificate (Let's Encrypt)
   │       │
   │       └──> Route by hostname
   │               │
   │               └──> bots-webserver Service (ClusterIP)
   │                       │
   │                       └──> bots-webserver Pods (port 8080)
```

## Files

### Base Configuration

**`k3s/base/ingress.yaml`** - Generic template for upstream/other deployments
- Placeholder domain: `edi.example.com`
- Traefik annotations
- TLS enabled with cert-manager
- Ready to customize

### Environment-Specific Configurations

**`k3s/overlays/prod/ingress.yaml`** - Production
- Domain: `edi.k8.pminc.me` (PMINC-specific)
- Let's Encrypt production certificates
- Namespace: `edi`

**`k3s/overlays/staging/ingress.yaml`** - Staging
- Domain: `bots-edi-staging.pminc.me`
- Let's Encrypt production certificates
- Namespace: `edi-staging`

**`k3s/overlays/dev/ingress.yaml`** - Development
- Domain: `bots-edi-dev.pminc.me`
- Let's Encrypt production certificates
- Namespace: `edi-dev`

## Prerequisites

### 1. Traefik Ingress Controller

**k3s (Built-in)**:
```bash
# Traefik comes pre-installed with k3s
kubectl get pods -n kube-system -l app.kubernetes.io/name=traefik
```

**Other Kubernetes distributions**:
```bash
# Install via Helm
helm repo add traefik https://traefik.github.io/charts
helm repo update
helm install traefik traefik/traefik -n kube-system
```

### 2. cert-manager

**Install cert-manager** (if not already installed):
```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml
```

**Verify installation**:
```bash
kubectl get pods -n cert-manager
```

### 3. ClusterIssuer

Create a ClusterIssuer for Let's Encrypt:

**Production**:
```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: your-email@example.com  # Change this
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: traefik
```

**Staging** (for testing):
```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-staging
spec:
  acme:
    server: https://acme-staging-v02.api.letsencrypt.org/directory
    email: your-email@example.com
    privateKeySecretRef:
      name: letsencrypt-staging
    solvers:
    - http01:
        ingress:
          class: traefik
```

**Apply ClusterIssuer**:
```bash
kubectl apply -f cluster-issuer.yaml
```

### 4. DNS Configuration

Point your domain to the Traefik external IP:

```bash
# Get Traefik external IP
kubectl get svc -n kube-system traefik

# Create DNS A record:
# edi.example.com -> EXTERNAL-IP
```

For k3s with NodePort (no LoadBalancer):
```bash
# Traefik uses NodePort by default in k3s
# Point DNS to any cluster node IP
# Traefik listens on ports 80 and 443
```

## Deployment

### Using Base Configuration

1. **Edit the domain**:
```bash
# Edit k3s/base/ingress.yaml
# Replace edi.example.com with your domain
```

2. **Apply**:
```bash
kubectl apply -f k3s/base/ingress.yaml
```

### Using Overlays (Recommended)

**Production**:
```bash
# Edit overlay ingress with your domain
vim k3s/overlays/prod/ingress.yaml

# Apply with kustomize
kubectl apply -k k3s/overlays/prod/
```

**Staging**:
```bash
kubectl apply -k k3s/overlays/staging/
```

**Development**:
```bash
kubectl apply -k k3s/overlays/dev/
```

## Verification

### 1. Check Ingress Status

```bash
kubectl get ingress -n edi
kubectl describe ingress bots-edi-ingress -n edi
```

**Expected output**:
```
NAME                CLASS     HOSTS              ADDRESS         PORTS     AGE
bots-edi-ingress    traefik   edi.example.com    203.0.113.1     80, 443   5m
```

### 2. Check Certificate

```bash
# Check certificate request
kubectl get certificaterequest -n edi

# Check certificate
kubectl get certificate -n edi

# Check certificate details
kubectl describe certificate bots-edi-tls -n edi
```

**Healthy certificate**:
```
Status:
  Conditions:
    Status:  True
    Type:    Ready
```

### 3. Test Access

```bash
# HTTP (should redirect to HTTPS)
curl -I http://edi.example.com

# HTTPS
curl -I https://edi.example.com

# Check certificate
curl -v https://edi.example.com 2>&1 | grep -A 10 "SSL certificate"
```

### 4. Browser Test

Open https://edi.example.com in browser:
- Should redirect from HTTP to HTTPS
- Should show valid certificate (green lock)
- Should load Bots-EDI login page

## Customization

### Enable Basic Authentication

1. **Create htpasswd file**:
```bash
# Install apache2-utils
sudo apt-get install apache2-utils

# Create password file
htpasswd -c auth admin
# Enter password when prompted
```

2. **Create Kubernetes secret**:
```bash
kubectl create secret generic bots-basic-auth \
  --from-file=auth \
  -n edi
```

3. **Update ingress annotations**:
```yaml
annotations:
  traefik.ingress.kubernetes.io/auth-type: basic
  traefik.ingress.kubernetes.io/auth-secret: bots-basic-auth
```

### Enable Rate Limiting

Add to ingress annotations:
```yaml
annotations:
  traefik.ingress.kubernetes.io/rate-limit: |
    extractorfunc: client.ip
    rateset:
      rate1:
        period: 1m
        average: 100
        burst: 200
```

### Enable IP Whitelist

Add to ingress annotations:
```yaml
annotations:
  traefik.ingress.kubernetes.io/whitelist-source-range: "10.0.0.0/8,192.168.0.0/16"
```

### Multiple Domains

```yaml
spec:
  tls:
    - secretName: bots-edi-tls
      hosts:
        - edi.example.com
        - www.edi.example.com
  rules:
    - host: edi.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: bots-webserver
                port:
                  name: http
    - host: www.edi.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: bots-webserver
                port:
                  name: http
```

### Path-Based Routing

```yaml
rules:
  - host: apps.example.com
    http:
      paths:
        - path: /edi
          pathType: Prefix
          backend:
            service:
              name: bots-webserver
              port:
                name: http
```

## Troubleshooting

### Ingress Shows No Address

**Symptom**:
```bash
kubectl get ingress -n edi
# ADDRESS column is empty
```

**Solution**:
```bash
# Check Traefik is running
kubectl get pods -n kube-system -l app.kubernetes.io/name=traefik

# Check Traefik service
kubectl get svc -n kube-system traefik

# Restart Traefik if needed
kubectl rollout restart deployment traefik -n kube-system
```

### Certificate Not Issued

**Symptom**:
```bash
kubectl get certificate -n edi
# Shows "False" or "Unknown" under READY
```

**Debug**:
```bash
# Check certificate order
kubectl describe certificate bots-edi-tls -n edi

# Check certificate request
kubectl get certificaterequest -n edi
kubectl describe certificaterequest <name> -n edi

# Check cert-manager logs
kubectl logs -n cert-manager -l app=cert-manager -f
```

**Common issues**:
1. DNS not pointing to correct IP
2. ClusterIssuer doesn't exist
3. Email not set in ClusterIssuer
4. Firewall blocking port 80 (needed for HTTP-01 challenge)

### 502 Bad Gateway

**Symptom**: Ingress works but shows 502 error

**Solution**:
```bash
# Check webserver service exists
kubectl get svc bots-webserver -n edi

# Check webserver pods are running
kubectl get pods -n edi -l component=webserver

# Check pod health
kubectl exec -n edi deployment/bots-webserver -- \
  curl -f http://localhost:8080/health/live

# Check service endpoints
kubectl get endpoints bots-webserver -n edi
```

### TLS Certificate Errors

**Symptom**: Browser shows certificate warning

**If using staging certificates**:
- Expected - Let's Encrypt staging certs are not trusted
- Switch to production ClusterIssuer when ready

**If using production certificates**:
```bash
# Check certificate details
kubectl get secret bots-edi-tls -n edi -o yaml

# Delete and recreate if invalid
kubectl delete certificate bots-edi-tls -n edi
# Will automatically recreate via ingress
```

### Redirect Loop

**Symptom**: Browser shows "Too many redirects"

**Solution**: Remove conflicting redirect annotations:
```yaml
# Remove or comment out:
# traefik.ingress.kubernetes.io/redirect-entry-point: https
```

## Monitoring

### Watch Certificate Renewal

```bash
# Certificates auto-renew 30 days before expiration
kubectl get certificate -n edi -w
```

### Traefik Dashboard

Access Traefik dashboard (if enabled):
```bash
kubectl port-forward -n kube-system \
  $(kubectl get pods -n kube-system -l app.kubernetes.io/name=traefik -o name) \
  9000:9000

# Open http://localhost:9000/dashboard/
```

## Security Best Practices

1. **Always use HTTPS in production**
2. **Use production Let's Encrypt certificates** (not staging)
3. **Consider basic auth** for admin interfaces
4. **Implement rate limiting** to prevent abuse
5. **Use IP whitelisting** if accessing from known networks
6. **Monitor certificate expiration** (automatic renewal should work)
7. **Keep Traefik updated** for security patches

## Migration Notes

When migrating from archive ingress (`archive/k3s/ingress.yaml`):
1. Existing TLS secrets are preserved
2. Update DNS if hostname changes
3. Test with staging first
4. Certificates will auto-renew with new ingress

## Additional Resources

- [Traefik Documentation](https://doc.traefik.io/traefik/)
- [Traefik Kubernetes Ingress](https://doc.traefik.io/traefik/routing/providers/kubernetes-ingress/)
- [cert-manager Documentation](https://cert-manager.io/docs/)
- [Let's Encrypt Rate Limits](https://letsencrypt.org/docs/rate-limits/)
- [k3s Traefik Documentation](https://docs.k3s.io/networking#traefik-ingress-controller)
