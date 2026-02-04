# Bots-EDI Containerized

> A containerized, cloud-native version of Bots-EDI for Kubernetes deployment

## About This Fork

This project is a containerization fork of **Bots-EDI**, an open-source EDI (Electronic Data Interchange) translator. The purpose of this fork is to create a production-ready version of Bots-EDI suitable for deployment in modern container environments, specifically Kubernetes and k3s clusters.

### Acknowledgments

Bots-EDI is the work of talented developers who have made EDI translation accessible to everyone. This fork builds upon their foundation:

- **Original Bots-EDI**: Developed by [Henk-Jan Ebbers](http://bots.sourceforge.net/en/index.shtml)
- **Current Upstream**: Maintained at [GitLab - bots-edi/bots](https://gitlab.com/bots-edi/bots)
- **Related Projects**:
  - [bots-grammars](https://gitlab.com/bots-edi/bots-grammars) - EDI message definitions
  - [bots-plugins](https://gitlab.com/bots-edi/bots-plugins) - Example translations and mappings

All credit for the core EDI translation functionality goes to the original authors and maintainers. This fork focuses on deployment infrastructure while preserving the excellent translation engine.

## What's Different in This Fork

This containerized version adds:

- **Production-ready Dockerfile**: Multi-stage build with Python 3.11, optimized layers
- **Kubernetes manifests**: Complete k8s deployment for multi-service architecture
- **Health checks**: HTTP endpoints and CLI tools for liveness, readiness, and startup probes
- **Database initialization**: Automated schema setup for both managed and unmanaged tables
- **Configuration management**: Kustomize overlays for dev/staging/prod environments
- **Service wrappers**: Clean process management for webserver, engine, and job queue
- **Documentation**: Comprehensive guides for deployment, operations, and development

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

## Quick Start

### Local Development

```bash
# Clone the repository
git clone <this-repo>
cd bots_edi

# Setup Python environment
conda create -n botsedi python=3.11
conda activate botsedi
pip install -r bots/requirements/base.txt

# Initialize database
python scripts/init-database.py --config-dir bots_config

# Run development server
python scripts/run_test_server.py
```

Access at: http://localhost:8080

### Docker

```bash
# Build image
docker build -t bots-edi:latest -f Dockerfile.new .

# Run webserver
docker run -p 8080:8080 \
  -v $(pwd)/data:/home/bots/.bots \
  bots-edi:latest /entrypoint.sh webserver
```

### Kubernetes

```bash
# Deploy to k8s cluster
kubectl apply -k k3s/overlays/dev/

# Check status
kubectl get all -n edi

# Access webserver
kubectl port-forward -n edi svc/bots-webserver 8080:8080
```

See [k3s/README.md](k3s/README.md) for detailed Kubernetes deployment instructions.

## Documentation

- **[Development Guide](docs/development.md)** - Local development setup and workflows
- **[Kubernetes Deployment](k3s/README.md)** - Container orchestration deployment
- **[Health Checks](docs/operations.md#health-checks)** - Monitoring and probes
- **[Configuration](docs/configuration.md)** - Settings and environment variables
- **[Contributing](CONTRIBUTING.md)** - How to contribute to this fork

## Project Structure

```
bots_edi/
├── bots/                      # Core Bots-EDI application (upstream)
├── bots-grammars/            # EDI message definitions (upstream)
├── bots-plugins/             # Example plugins (upstream)
├── bots_config/              # Configuration files (bots.ini, settings.py)
├── scripts/                  # Database init, health checks, utilities
├── k3s/                      # Kubernetes manifests
│   ├── base/                 # Base resources
│   ├── deployments/          # Application deployments
│   ├── jobs/                 # Jobs and CronJobs
│   └── overlays/             # Environment-specific configs
├── docs/                     # Documentation
├── Dockerfile.new            # Production-ready container image
└── entrypoint.sh             # Container entrypoint script
```

## Requirements

- **Python**: 3.11+
- **Database**: MySQL 5.7+ or MariaDB 10.3+ (PostgreSQL also supported)
- **Container Runtime**: Docker 20.10+ or containerd
- **Kubernetes**: 1.19+ (for k8s deployment)
- **Storage**: ReadWriteMany (RWX) storage class for k8s (NFS, CephFS, etc.)

## Features

From upstream Bots-EDI:
- Supports many EDI formats: EDIFACT, X12, TRADACOMS, XML, JSON, CSV, fixed-width, Excel
- Powerful mapping/translation engine with Python scripting
- Web-based administration interface
- Scheduling and monitoring
- Database backend for transaction tracking
- Email and FTP/SFTP communication

Added in this fork:
- Production-ready containerization
- Kubernetes-native deployment
- Automated health checks
- Database migration tooling
- Multi-environment configuration management
- Comprehensive operational documentation

## License

This fork maintains the original GNU General Public License v3.0 from Bots-EDI.

See [license.rst](bots/license.rst) for full license text.

## Support

- **Upstream Bots-EDI**: https://gitlab.com/bots-edi/bots
- **Documentation**: https://bots.readthedocs.io/
- **Commercial Support**: https://www.edi-intelligentsia.com

For issues specific to this containerized fork, please open an issue in this repository.

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

Areas where contributions would be particularly valuable:
- Additional Kubernetes examples (GKE, EKS, AKS)
- Helm chart development
- CI/CD pipeline improvements
- Documentation enhancements
- Testing and validation

---

**Note**: This is an independent fork focused on containerization. For core EDI functionality questions, please refer to the [upstream Bots-EDI project](https://gitlab.com/bots-edi/bots).
