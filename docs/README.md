# Bots EDI Documentation

Welcome to the Bots EDI documentation! This directory contains comprehensive guides for deploying, developing, and operating Bots EDI in containerized environments.

## Quick Links

### For Users
- **[Kubernetes Deployment Guide](kubernetes-deployment.md)** - Deploy Bots EDI on Kubernetes
- **[Operations Runbook](operations-runbook.md)** - Day-to-day operations and troubleshooting

### For Developers
- **[Development Guide](development.md)** - Set up local development environment
- **[Contributing Guidelines](../CONTRIBUTING.md)** - How to contribute to the project

### For System Administrators
- **[Architecture Documentation](architecture.md)** - System design and component overview
- **[Decision Records](decision-records/)** - Key architectural decisions (ADRs)

## Documentation Structure

```
docs/
├── README.md                          # This file
├── kubernetes-deployment.md           # K8s deployment guide (550 lines)
├── development.md                     # Development setup (500 lines)
├── architecture.md                    # System architecture (450 lines)
├── operations-runbook.md              # Operations procedures (550 lines)
└── decision-records/                  # Architecture Decision Records
    ├── 001-multi-service-architecture.md
    ├── 002-kustomize-overlays.md
    └── 003-rwx-storage.md
```

## Getting Started

### I want to... Deploy Bots EDI

1. Read [Kubernetes Deployment Guide](kubernetes-deployment.md)
2. Follow Quick Start section
3. Reference [Operations Runbook](operations-runbook.md) for daily operations

**Time estimate**: 30 minutes for basic deployment

### I want to... Develop with Bots EDI

1. Read [Development Guide](development.md)
2. Set up Python environment
3. Initialize local database
4. Start development server

**Time estimate**: 1 hour for complete setup

### I want to... Understand the Architecture

1. Read [Architecture Documentation](architecture.md)
2. Review [Decision Records](decision-records/) for design rationale
3. Check component diagrams

**Time estimate**: 30 minutes

### I want to... Contribute Code

1. Read [Contributing Guidelines](../CONTRIBUTING.md)
2. Fork repository and create feature branch
3. Follow [Development Guide](development.md) for local testing
4. Submit pull request

**Time estimate**: Varies by contribution

## Key Concepts

### Multi-Service Architecture

Bots EDI consists of four services:
- **Webserver** (Django UI) - Configuration and monitoring
- **Engine** (EDI Processor) - Message transformation
- **Job Queue** (Background Jobs) - Asynchronous processing
- **Directory Monitor** (Optional) - File system watching

See [Architecture](architecture.md#component-architecture) for details.

### Environment Strategy

Three environments supported:
- **Development** (edi-dev) - Testing and experimentation
- **Staging** (edi-staging) - Pre-production validation
- **Production** (edi) - Live system

See [Kubernetes Deployment](kubernetes-deployment.md#multi-environment-deployment) for configuration differences.

### Storage Requirements

Bots EDI requires **ReadWriteMany (RWX)** storage for:
- EDI files (20Gi production)
- Application logs (5Gi production)
- Runtime configuration (1Gi production)

See [ADR-003](decision-records/003-rwx-storage.md) for rationale.

## Common Tasks

### Deploy to Development
```bash
kubectl apply -k k3s/overlays/dev/
```

### Deploy to Production
```bash
kubectl apply -k k3s/overlays/prod/
```

### View Logs
```bash
kubectl logs -n edi -l app=bots-edi --tail=100 -f
```

### Run Engine Manually
```bash
kubectl create job --from=cronjob/bots-engine manual-run -n edi
```

### Backup Database
```bash
kubectl exec -n edi deployment/bots-webserver -- \
  python manage.py dumpdata > backup.json
```

## Additional Resources

### External Documentation
- [Official Bots Documentation](https://bots.readthedocs.io) - Original Bots EDI docs
- [Django Documentation](https://docs.djangoproject.com/) - Django framework
- [Kubernetes Documentation](https://kubernetes.io/docs/) - Kubernetes concepts

### Related Files
- [k3s/DEPLOYMENT.md](../k3s/DEPLOYMENT.md) - Multi-environment deployment procedures
- [k3s/secrets/README.md](../k3s/secrets/README.md) - Secret management guide
- [fork/container_project.md](../fork/container_project.md) - Containerization project notes

### Phase Implementation Details
- [fork/phase1-complete.md](../fork/phase1-complete.md) - Database initialization
- [fork/phase2-complete.md](../fork/phase2-complete.md) - Health checks
- [fork/phase3-complete.md](../fork/phase3-complete.md) - Docker implementation
- [fork/phase4-complete.md](../fork/phase4-complete.md) - Kubernetes manifests
- [fork/phase5-complete.md](../fork/phase5-complete.md) - Configuration management
- [fork/phase7-complete.md](../fork/phase7-complete.md) - Documentation

## Documentation Standards

### Markdown Style
- ATX-style headers (`#` not underlines)
- Code blocks specify language
- Relative links for internal references
- Keep line length reasonable (~100 chars)

### Code Examples
Always include:
- Context (what the code does)
- Prerequisites
- Expected output
- Error handling examples

### Diagrams
- Use Mermaid for flowcharts/diagrams
- Include ASCII art for simple diagrams
- Keep diagrams up to date with code

## Contributing to Documentation

Documentation improvements are always welcome!

**High Priority**:
- Fixing errors or outdated information
- Adding missing procedures
- Improving clarity
- Adding examples

**Process**:
1. Edit markdown files
2. Test all commands/code
3. Check links work
4. Submit pull request

See [Contributing Guidelines](../CONTRIBUTING.md) for details.

## Getting Help

- **Issues**: [GitHub Issues](https://github.com/your-org/bots_edi/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/bots_edi/discussions)
- **Commercial Support**: [EDI Intelligentsia](https://www.edi-intelligentsia.com)

## License

Bots EDI is licensed under GNU GENERAL PUBLIC LICENSE Version 3.  
Full license: http://www.gnu.org/copyleft/gpl.html

## Changelog

- **2026-02-04**: Phase 7 documentation completed
  - Added kubernetes-deployment.md
  - Added development.md
  - Added architecture.md
  - Added operations-runbook.md
  - Added decision records (ADRs)
- **2026-01-15**: Project containerization started
- **Earlier**: Original Bots EDI documentation

---

**Last Updated**: February 4, 2026  
**Documentation Version**: 1.0.0  
**Bots EDI Version**: 4.0.0 (containerized)
