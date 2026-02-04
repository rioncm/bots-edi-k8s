# ADR-001: Multi-Service Container Architecture

**Status**: Accepted  
**Date**: 2026-01-15  
**Decision Makers**: Development Team  
**Related**: Phase 3 Implementation

## Context

Bots EDI traditionally runs as a monolithic application with multiple Python processes started independently. For Kubernetes deployment, we needed to decide how to containerize these services.

### Options Considered

#### Option 1: Single Container with Supervisor
- **Approach**: One container image running all services via supervisord
- **Pros**:
  - Simple deployment (single pod)
  - Easy local development
  - Shared memory space
- **Cons**:
  - Difficult to scale individual services
  - Health check complexity
  - Resource allocation inflexible
  - Violates single-concern principle

#### Option 2: Separate Containers per Service
- **Approach**: One container image, different entrypoints for each service
- **Pros**:
  - Independent scaling
  - Better resource allocation
  - Kubernetes-native health checks
  - Failure isolation
  - Follows 12-factor app principles
- **Cons**:
  - More complex deployment
  - Shared storage required
  - Multiple manifests to maintain

#### Option 3: Fully Separate Images
- **Approach**: Different Dockerfiles for each service
- **Pros**:
  - Maximum optimization per service
  - Smallest possible images
- **Cons**:
  - Build complexity
  - Code duplication
  - Maintenance overhead

## Decision

**Chosen**: Option 2 - Separate Containers per Service

We will use a single container image with a flexible entrypoint script that accepts a service type argument:
- `webserver` - Django web UI
- `engine` - EDI processing engine
- `jobqueueserver` - Job queue server  
- `dirmonitor` - Directory monitor (optional)
- `init-db` - Database initialization
- `shell` - Interactive shell

## Rationale

### Why Separate Containers
1. **Scalability**: Webserver can scale to 3+ replicas while job queue remains singleton
2. **Resource Allocation**: Engine needs 2Gi RAM, webserver only 512Mi
3. **Kubernetes Native**: Each service gets proper health checks
4. **Failure Isolation**: Webserver crash doesn't affect job queue
5. **Operational Flexibility**: Update engine without restarting webserver

### Why Same Image
1. **Build Efficiency**: Single Docker build process
2. **Code Consistency**: All services use same codebase version
3. **Deployment Simplicity**: One image to tag/push/pull
4. **Reduced Complexity**: No code duplication

### Why Entrypoint Script
1. **Flexibility**: Easy to add new service types
2. **Initialization**: Common setup (env, config) happens once
3. **Signal Handling**: Graceful shutdown for all services
4. **Debugging**: Can override for troubleshooting

## Implementation

### Dockerfile Structure
```dockerfile
FROM python:3.11-slim as builder
# Build wheels

FROM python:3.11-slim as runtime
# Install dependencies

FROM runtime as production
COPY --from=builder /wheels /wheels
RUN pip install --no-index --find-links=/wheels ...
COPY entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["webserver"]
```

### Entrypoint Logic
```bash
#!/bin/bash
case "$SERVICE_TYPE" in
  webserver)
    exec python manage.py runserver 0.0.0.0:8080
    ;;
  engine)
    exec python bots-engine.py "$@"
    ;;
  jobqueueserver)
    exec python bots-jobqueueserver.py
    ;;
esac
```

### Kubernetes Manifests
- `deployments/webserver.yaml` - 3 replicas, port 8080
- `deployments/jobqueue.yaml` - 1 replica, no exposed port
- `jobs/engine-cronjob.yaml` - Scheduled every 5 minutes

## Consequences

### Positive
- ✅ Each service can be scaled independently
- ✅ Resource requests/limits tailored per service
- ✅ Health checks specific to service type
- ✅ Rolling updates per service
- ✅ Easier troubleshooting (isolated logs)
- ✅ Follows Kubernetes best practices

### Negative
- ❌ More Kubernetes manifests to maintain
- ❌ Shared storage (RWX PVC) required
- ❌ Slightly larger image (contains all code)
- ❌ Need to coordinate versions across deployments

### Mitigations
- Use Kustomize to reduce manifest duplication
- NFS/Longhorn provides reliable RWX storage
- Multi-stage builds keep image reasonable (~200MB)
- Image tagging strategy ensures version consistency

## Alternatives Rejected

### Supervisor Pattern
```yaml
# Rejected: Single pod with supervisord
containers:
- name: bots-all-in-one
  command: ["/usr/bin/supervisord"]
```
**Why**: Doesn't leverage Kubernetes orchestration, scaling limitations

### Service Mesh
**Why**: Overkill for current requirements, adds complexity

## References

- [12-Factor App](https://12factor.net/)
- [Kubernetes Best Practices](https://kubernetes.io/docs/concepts/configuration/overview/)
- [Container Design Patterns](https://kubernetes.io/blog/2016/06/container-design-patterns/)

## Review

This decision should be reviewed if:
- Performance issues arise from shared storage
- Service coupling becomes problematic
- New services require fundamentally different dependencies
- Microservices architecture becomes necessary
