# Bots EDI - Development Guide

## Overview

This guide covers setting up a local development environment for Bots EDI, including containerized development workflows, testing procedures, and contribution guidelines.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Local Development Setup](#local-development-setup)
- [Container Development](#container-development)
- [Testing](#testing)
- [Code Structure](#code-structure)
- [Making Changes](#making-changes)
- [Building Images](#building-images)
- [Debugging](#debugging)

## Prerequisites

### Required Software

- **Python 3.11+**
- **Git**
- **Docker** (for container development)
- **kubectl** (for Kubernetes testing)
- **MySQL** or **SQLite** (for local database)

### Recommended Tools

- **VS Code** with Python extension
- **k3d** or **minikube** (local Kubernetes cluster)
- **kustomize** (built into kubectl 1.14+)
- **kubeseal** (for sealed secrets)

### Operating Systems

Bots EDI supports:
- Linux (Ubuntu, Debian, RHEL, etc.)
- macOS
- Windows (via WSL2)

## Local Development Setup

### 1. Clone Repository

```bash
git clone https://github.com/your-org/bots_edi.git
cd bots_edi
```

### 2. Set Up Python Environment

#### Using Conda (Recommended)
```bash
# Create environment
conda create -n botsedi python=3.11
conda activate botsedi

# Install dependencies
pip install -r bots/requirements/base.txt
pip install -r bots/requirements/test.txt
pip install -r bots/requirements/extras.txt
```

#### Using venv
```bash
# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r bots/requirements/base.txt
pip install -r bots/requirements/test.txt
```

### 3. Configure Database

#### SQLite (Simplest for development)
```bash
# Copy example config
cp bots_config/bots.ini.example bots_config/bots.ini

# SQLite is default in settings.py for development
# No additional configuration needed
```

#### MySQL (Production-like)
```bash
# Create database
mysql -u root -p <<EOF
CREATE DATABASE botsedi_dev CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'botsedi'@'localhost' IDENTIFIED BY 'devpassword';
GRANT ALL PRIVILEGES ON botsedi_dev.* TO 'botsedi'@'localhost';
FLUSH PRIVILEGES;
EOF

# Update bots_config/settings.py
# Set DB_HOST, DB_NAME, DB_USER, DB_PASSWORD
```

### 4. Initialize Database

```bash
# Run database initialization
python scripts/init-database.py \
  --config-dir bots_config \
  --django-settings settings

# Or using Django command
cd bots
python manage.py initdb --config-dir ../bots_config

# Create admin user
python manage.py createsuperuser
```

### 5. Run Development Server

```bash
cd bots
python manage.py runserver 8080
```

Access at: http://localhost:8080

**Default credentials**: admin / botsbots

### 6. Run Background Services (Optional)

In separate terminals:

```bash
# Job queue server
cd bots
python bots-jobqueueserver.py

# Directory monitor
python bots-dirmonitor.py

# Engine (manual run)
python bots-engine.py --new
```

## Container Development

### Build Development Image

```bash
# Build image
docker build -f Dockerfile.new -t bots-edi:dev .

# Or use docker-compose
docker-compose build
```

### Run Container Locally

```bash
# Run webserver
docker run -p 8080:8080 \
  -e DB_HOST=host.docker.internal \
  -e DB_NAME=botsedi_dev \
  -e DB_USER=botsedi \
  -e DB_PASSWORD=devpassword \
  -v $(pwd)/test-data:/home/bots/.bots \
  bots-edi:dev webserver

# Run engine
docker run \
  -e DB_HOST=host.docker.internal \
  -v $(pwd)/test-data:/home/bots/.bots \
  bots-edi:dev engine --new
```

### Docker Compose Development

```bash
# Start all services
docker-compose up

# Start specific service
docker-compose up webserver

# View logs
docker-compose logs -f webserver

# Stop services
docker-compose down
```

### Local Kubernetes Testing

#### Using k3d

```bash
# Create cluster
k3d cluster create bots-dev

# Build and load image
docker build -t bots-edi:dev .
k3d image import bots-edi:dev -c bots-dev

# Deploy
kubectl apply -k k3s/overlays/dev/

# Port forward
kubectl port-forward -n edi-dev svc/bots-webserver-dev 8080:8080
```

#### Using minikube

```bash
# Start minikube
minikube start

# Use minikube's Docker daemon
eval $(minikube docker-env)

# Build image
docker build -t bots-edi:dev .

# Deploy
kubectl apply -k k3s/overlays/dev/

# Access service
minikube service bots-webserver-dev -n edi-dev
```

## Testing

### Running Unit Tests

```bash
cd bots/tests

# Run all tests
python -m pytest

# Run specific test file
python -m pytest unitnode.py

# Run with coverage
python -m pytest --cov=bots --cov-report=html

# Original test runner
python utilsunit.py
```

### Health Check Testing

```bash
# Test web health endpoints
python scripts/healthcheck.py --check live --config-dir bots_config
python scripts/healthcheck.py --check ready --config-dir bots_config

# Test in container
docker run bots-edi:dev python /opt/bots/scripts/healthcheck.py --check live
```

### Integration Testing

```bash
# Test database initialization
python scripts/init-database.py --verify-only

# Test engine processing
python bots-engine.py --new

# Test job queue
python bots-jobqueueserver.py &
# ... send test job ...
```

### Container Testing

```bash
# Test container builds
docker build -f Dockerfile.new -t bots-edi:test .

# Test entrypoint
docker run --rm bots-edi:test webserver --help
docker run --rm bots-edi:test engine --help

# Test health checks
docker run --rm bots-edi:test \
  python /opt/bots/scripts/healthcheck.py --check startup
```

### Kubernetes Manifest Validation

```bash
# Validate with dry-run
kubectl apply -k k3s/overlays/dev/ --dry-run=client

# Build manifests
kustomize build k3s/overlays/dev/ > /tmp/dev-manifest.yaml

# Validate with kubeval (if installed)
kubeval /tmp/dev-manifest.yaml
```

## Code Structure

```
bots_edi/
├── bots/                          # Main application
│   ├── bots/                      # Django app & core logic
│   │   ├── admin.py              # Admin interface
│   │   ├── models.py             # Database models
│   │   ├── views.py              # Web views
│   │   ├── engine.py             # EDI processing engine
│   │   ├── inmessage.py          # Input message handling
│   │   ├── outmessage.py         # Output message handling
│   │   ├── transform.py          # Message transformation
│   │   ├── grammar.py            # EDI grammar handling
│   │   └── healthcheck.py        # Health check endpoints
│   ├── requirements/             # Python dependencies
│   └── tests/                    # Unit tests
├── scripts/                       # Utility scripts
│   ├── init-database.py          # DB initialization
│   ├── healthcheck.py            # CLI health checks
│   ├── run-webserver.sh          # Service wrappers
│   └── ...
├── bots_config/                   # Configuration
│   ├── bots.ini                  # Main config
│   └── settings.py               # Django settings
├── bots-grammars/                 # EDI format grammars
│   ├── edifact/                  # EDIFACT definitions
│   ├── x12/                      # X12 definitions
│   └── xml/                      # XML schemas
├── bots-plugins/                  # Example plugins
├── k3s/                          # Kubernetes manifests
│   ├── base/                     # Base resources
│   ├── deployments/              # Service deployments
│   ├── jobs/                     # Jobs & CronJobs
│   ├── overlays/                 # Environment overlays
│   └── secrets/                  # Secret templates
├── docs/                          # Documentation
├── Dockerfile.new                 # Production Dockerfile
├── entrypoint.new.sh             # Container entrypoint
└── docker-compose.yml            # Local development compose
```

### Key Components

#### Engine (bots/bots/engine.py)
- Processes EDI transactions
- Transforms between formats
- Handles routing and communication

#### Transform (bots/bots/transform.py)
- Core transformation logic
- Mapping engine
- Grammar-based translation

#### Grammar (bots/bots/grammar.py)
- EDI format definitions
- Message structure validation
- Field mapping rules

#### Models (bots/bots/models.py)
- Database schema (Django ORM)
- Routes, Channels, Translations
- Transactions and partners

## Making Changes

### Feature Development Workflow

1. **Create feature branch**
   ```bash
   git checkout -b feature/my-new-feature
   ```

2. **Make changes**
   - Follow PEP 8 style guide
   - Add docstrings to functions
   - Update tests

3. **Test locally**
   ```bash
   python -m pytest
   python scripts/healthcheck.py --check startup
   ```

4. **Test in container**
   ```bash
   docker build -t bots-edi:test .
   docker run --rm bots-edi:test python -m pytest
   ```

5. **Commit changes**
   ```bash
   git add .
   git commit -m "feat: add new feature"
   ```

6. **Push and create PR**
   ```bash
   git push origin feature/my-new-feature
   ```

### Coding Standards

#### Python Style
- Follow PEP 8
- Use 4 spaces for indentation
- Maximum line length: 100 characters
- Use descriptive variable names

#### Django Best Practices
- Use Django ORM for database queries
- Implement proper form validation
- Use class-based views where appropriate
- Add migrations for model changes

#### Container Best Practices
- Keep images small (multi-stage builds)
- Run as non-root user
- Use explicit tags, not :latest
- Pin dependency versions

#### Kubernetes Best Practices
- Set resource requests and limits
- Implement health checks
- Use ConfigMaps for configuration
- Use Secrets for sensitive data
- Add labels for organization

### Adding New EDI Formats

1. **Create grammar file**
   ```bash
   mkdir bots-grammars/myformat
   touch bots-grammars/myformat/myformat.py
   ```

2. **Define message structure**
   ```python
   structure = [
       {ID: 'header', MIN: 1, MAX: 1, LEVEL: [
           {ID: 'field1', MIN: 1, MAX: 1},
           {ID: 'field2', MIN: 0, MAX: 1},
       ]},
   ]
   ```

3. **Add envelope handling**
   ```python
   def envelope(ta_info):
       # Implementation
       pass
   ```

4. **Test the grammar**
   ```bash
   python tests/unitgrammar.py
   ```

## Building Images

### Production Build

```bash
# Build multi-stage image
docker build -f Dockerfile.new -t harbor.pminc.me/priv/bots-edi:v1.0.0 .

# Tag for registry
docker tag bots-edi:v1.0.0 harbor.pminc.me/priv/bots-edi:latest

# Push to registry
docker push harbor.pminc.me/priv/bots-edi:v1.0.0
docker push harbor.pminc.me/priv/bots-edi:latest
```

### Multi-Platform Builds

```bash
# Build for multiple architectures
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t harbor.pminc.me/priv/bots-edi:v1.0.0 \
  --push \
  -f Dockerfile.new .
```

### Build Arguments

```bash
# Custom Python version
docker build --build-arg PYTHON_VERSION=3.12 -t bots-edi:py312 .

# Development build with debug tools
docker build --target development -t bots-edi:dev-debug .
```

## Debugging

### Debug Django Application

```bash
# Run with debug mode
cd bots
DEBUG=True python manage.py runserver 0.0.0.0:8080

# Use Django shell
python manage.py shell

# Enable SQL logging
python manage.py runserver --verbosity 3
```

### Debug Container

```bash
# Run with shell
docker run -it --rm bots-edi:dev shell

# Override entrypoint
docker run -it --rm --entrypoint /bin/bash bots-edi:dev

# Inspect running container
docker exec -it <container-id> /bin/bash

# View logs
docker logs <container-id> --tail 100 -f
```

### Debug Kubernetes Pod

```bash
# Get shell in pod
kubectl exec -it -n edi deployment/bots-webserver -- /bin/bash

# View logs
kubectl logs -n edi deployment/bots-webserver --tail=100 -f

# Debug CrashLoopBackOff
kubectl logs -n edi <pod-name> --previous

# Describe pod for events
kubectl describe pod -n edi <pod-name>

# Port forward for local access
kubectl port-forward -n edi pod/<pod-name> 8080:8080
```

### Common Issues

#### Import Errors
```bash
# Check Python path
python -c "import sys; print('\n'.join(sys.path))"

# Reinstall dependencies
pip install --force-reinstall -r requirements/base.txt
```

#### Database Connection
```bash
# Test connection
python -c "import MySQLdb; conn = MySQLdb.connect(host='localhost', user='botsedi', passwd='password', db='botsedi_dev'); print('Connected')"

# Check Django settings
python manage.py diffsettings
```

#### Permission Issues (Container)
```bash
# Check file ownership
docker run --rm bots-edi:dev ls -la /home/bots/.bots

# Fix permissions
docker run --rm --user root bots-edi:dev chown -R bots:bots /home/bots/.bots
```

## Performance Profiling

### Profile Engine

```bash
# Use built-in profiler
python scripts/profile-engine.py

# Or use cProfile
python -m cProfile -o engine.prof bots/bots-engine.py --new

# Visualize results
python -m pstats engine.prof
```

### Monitor Resource Usage

```bash
# Container resources
docker stats

# Kubernetes resources
kubectl top pods -n edi
kubectl top nodes
```

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for contribution guidelines.

Key points:
- Create feature branches
- Write tests for new features
- Update documentation
- Follow coding standards
- Submit PRs with clear descriptions

## Additional Resources

- [Kubernetes Deployment Guide](kubernetes-deployment.md)
- [Architecture Documentation](architecture.md)
- [Operations Runbook](operations-runbook.md)
- [Official Bots Documentation](https://bots.readthedocs.io)
- [Django Documentation](https://docs.djangoproject.com/)

## Getting Help

- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions
- **Commercial Support**: EDI Intelligentsia - https://www.edi-intelligentsia.com

## License

Bots EDI is licensed under GNU GENERAL PUBLIC LICENSE Version 3.
