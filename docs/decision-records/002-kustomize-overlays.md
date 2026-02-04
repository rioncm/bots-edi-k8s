# ADR-002: Kustomize for Multi-Environment Configuration

**Status**: Accepted  
**Date**: 2026-02-02  
**Decision Makers**: Development Team, Operations Team  
**Related**: Phase 5 Implementation

## Context

Bots EDI needs to run in multiple environments (dev, staging, production) with different configurations:
- Resource limits vary significantly
- Database connections differ
- Scaling requirements differ
- Storage sizes vary

We needed a solution to manage environment-specific configurations without duplication.

### Options Considered

#### Option 1: Separate YAML Files per Environment
- **Approach**: `dev/`, `staging/`, `prod/` directories with complete manifests
- **Pros**:
  - Simple to understand
  - No dependencies
  - Complete control per environment
- **Cons**:
  - Massive duplication (~1000+ lines per env)
  - Updates require changes in multiple files
  - Error-prone maintenance
  - Drift between environments

#### Option 2: Helm Charts
- **Approach**: Template-based YAML generation
- **Pros**:
  - Industry standard
  - Rich templating with Go templates
  - Package management
  - Extensive ecosystem
- **Cons**:
  - Complex learning curve
  - Over-engineered for simple use case
  - Debugging template errors difficult
  - Additional tool dependency (helm)

#### Option 3: Kustomize
- **Approach**: Patch-based overlay system
- **Pros**:
  - Built into kubectl (no extra tools)
  - Pure YAML (no templates)
  - Clear base + overlay structure
  - Easy to understand diffs
  - GitOps friendly
- **Cons**:
  - Less powerful than Helm
  - Strategic merge patches can be tricky
  - Limited logic/conditionals

#### Option 4: Custom Scripts
- **Approach**: Shell/Python scripts to generate manifests
- **Pros**:
  - Full control
  - No framework limitations
- **Cons**:
  - Maintenance burden
  - Non-standard approach
  - Difficult for team collaboration

## Decision

**Chosen**: Option 3 - Kustomize

We will use Kustomize with a base + overlays pattern:
```
k3s/
├── base/              # Common resources
├── overlays/
│   ├── dev/          # Dev-specific patches
│   ├── staging/      # Staging-specific patches
│   └── prod/         # Production-specific patches
```

## Rationale

### Why Kustomize Over Helm
1. **Simplicity**: No templating language to learn, just YAML
2. **Built-in**: `kubectl apply -k` works out of the box
3. **Transparency**: Easy to see what changes per environment
4. **GitOps**: ArgoCD/Flux natively support Kustomize
5. **Debugging**: `kustomize build` shows exact output
6. **No Extra Dependencies**: Already in kubectl 1.14+

### Why Not Separate Files
- Base resources are 800+ lines
- DRY principle violation
- Maintenance nightmare (proven in past projects)

### Why Not Custom Scripts
- Non-standard approach confuses new team members
- Kustomize is industry-recognized
- Better tooling support (IDE plugins, CI/CD)

## Implementation

### Base Structure
```yaml
# k3s/base/kustomization.yaml
resources:
  - namespace.yaml
  - configmap-botsini.yaml
  - configmap-settings.yaml
  - pvc.yaml
  - service-webserver.yaml
```

### Dev Overlay
```yaml
# k3s/overlays/dev/kustomization.yaml
resources:
  - ../../base

nameSuffix: -dev

patches:
  - target:
      kind: Deployment
      name: bots-webserver
    patch: |-
      - op: replace
        path: /spec/replicas
        value: 1
      - op: replace
        path: /spec/template/spec/containers/0/resources/limits/memory
        value: "512Mi"
```

### Deployment
```bash
# Development
kubectl apply -k k3s/overlays/dev/

# Staging
kubectl apply -k k3s/overlays/staging/

# Production
kubectl apply -k k3s/overlays/prod/
```

## Consequences

### Positive
- ✅ Base resources maintained once
- ✅ Environment differences clearly visible
- ✅ Easy to add new environments (copy overlay)
- ✅ No tooling beyond kubectl required
- ✅ CI/CD integration straightforward
- ✅ ArgoCD native support
- ✅ Dry-run validation built-in

### Negative
- ❌ Strategic merge patches can be complex
- ❌ Limited conditional logic
- ❌ No variables/loops (not needed for our case)
- ❌ Large patches can become unwieldy

### Mitigations
- Use JSON6902 patches for complex modifications
- Keep patches small and focused
- Document patch rationale in comments
- Use `kustomize build` to verify output

## Environment-Specific Configurations

### Development
- 1 webserver replica
- Minimal resources (128Mi-512Mi RAM)
- 5Gi storage
- Debug logging enabled
- Image tag: `dev`

### Staging
- 2 webserver replicas
- Medium resources (256Mi-768Mi RAM)
- 10Gi storage
- Info logging
- Image tag: `staging`

### Production
- 3 webserver replicas
- Full resources (256Mi-1Gi RAM)
- 20Gi storage
- Info logging
- Image tag: `latest`

## Comparison with Alternatives

| Feature | Kustomize | Helm | Separate Files |
|---------|-----------|------|----------------|
| Learning Curve | Low | High | None |
| Maintenance | Easy | Medium | Hard |
| Tooling | Built-in | External | None |
| Flexibility | Medium | High | Limited |
| Debugging | Easy | Medium | Easy |
| GitOps | Native | Supported | Manual |

## Validation

### Test Commands
```bash
# Build and validate
kustomize build k3s/overlays/dev/ > /tmp/dev.yaml
kubectl apply --dry-run=client -f /tmp/dev.yaml

# Compare environments
diff <(kustomize build k3s/overlays/dev/) \
     <(kustomize build k3s/overlays/prod/)
```

### Quality Checks
- All overlays build without errors
- Namespace suffixes applied correctly
- Image tags differ per environment
- Resource limits appropriate per environment
- PVC sizes match requirements

## References

- [Kustomize Documentation](https://kustomize.io/)
- [Kubectl Kustomize](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/)
- [ArgoCD Kustomize Support](https://argo-cd.readthedocs.io/en/stable/user-guide/kustomize/)

## Review

This decision should be reviewed if:
- Complexity outgrows Kustomize capabilities
- Team prefers Helm ecosystem
- Need for package management emerges
- Conditional logic requirements increase significantly
