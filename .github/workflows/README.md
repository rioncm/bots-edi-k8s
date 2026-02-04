# GitHub Workflows

This directory contains automated CI/CD workflows for the Bots-EDI containerization project.

## Workflows

### build-and-push.yml

**Trigger:** Tags (`v*.*.*`), main branch pushes, manual dispatch

**Purpose:** Build and publish multi-arch container images to Docker Hub and GitHub Container Registry.

**Features:**
- Multi-architecture builds (amd64, arm64)
- Pushes to both GHCR and Docker Hub
- Vulnerability scanning with Trivy
- SBOM generation
- Automated GitHub releases with container info

**Required Secrets:**
- `DOCKERHUB_USERNAME` - Docker Hub username
- `DOCKERHUB_TOKEN` - Docker Hub access token (create at https://hub.docker.com/settings/security)
- `GITHUB_TOKEN` - Automatically provided by GitHub Actions

### ci.yml

**Trigger:** Pull requests and pushes to main/develop branches

**Purpose:** Continuous integration testing for all changes.

**Jobs:**
1. **Lint** - Code style and quality checks
2. **Build** - Build container image (no push)
3. **Test** - Run health checks and unit tests with MySQL
4. **Security** - Vulnerability and secret scanning

**Features:**
- Python linting (Ruff, Pylint)
- Dockerfile linting (Hadolint)
- YAML validation
- Container vulnerability scanning
- Database integration tests
- Secret detection (TruffleHog)

**Optional Secrets:**
- `SNYK_TOKEN` - For enhanced vulnerability scanning (optional)

### lint.yml

**Trigger:** Pull requests that modify code, YAML, or Dockerfiles

**Purpose:** Fast feedback on code quality issues.

**Checks:**
- Dockerfile best practices (Hadolint)
- Python code quality (Ruff, Pylint)
- YAML syntax and style (yamllint)
- Markdown formatting (markdownlint)
- Broken links in documentation

## Setup Instructions

### 1. Configure Docker Hub

1. Create Docker Hub access token:
   - Go to https://hub.docker.com/settings/security
   - Click "New Access Token"
   - Name: `github-actions`
   - Permissions: Read & Write

2. Add secrets to GitHub repository:
   - Go to repository Settings → Secrets and variables → Actions
   - Add `DOCKERHUB_USERNAME` (your Docker Hub username)
   - Add `DOCKERHUB_TOKEN` (the token from step 1)

### 2. Enable GitHub Container Registry

GHCR is enabled automatically for public repositories. For private repositories:

1. Go to repository Settings → Actions → General
2. Under "Workflow permissions", ensure "Read and write permissions" is selected

### 3. (Optional) Configure Snyk

For enhanced security scanning:

1. Sign up at https://snyk.io
2. Get API token from Account Settings
3. Add `SNYK_TOKEN` secret to GitHub repository

### 4. Create First Release

To trigger the build-and-push workflow:

```bash
# Tag a release
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

The workflow will:
1. Build multi-arch images
2. Push to both registries
3. Scan for vulnerabilities
4. Create GitHub release with container info

## Using the Published Images

### From GitHub Container Registry (recommended for GitHub users)

```bash
# Pull latest
docker pull ghcr.io/YOUR_ORG/bots_edi:latest

# Pull specific version
docker pull ghcr.io/YOUR_ORG/bots_edi:v1.0.0

# Use in Kubernetes
image: ghcr.io/YOUR_ORG/bots_edi:v1.0.0
```

### From Docker Hub

```bash
# Pull latest
docker pull YOUR_DOCKERHUB_USERNAME/bots-edi:latest

# Pull specific version
docker pull YOUR_DOCKERHUB_USERNAME/bots-edi:v1.0.0
```

## Workflow Status Badges

Add to your README.md:

```markdown
[![Build and Push](https://github.com/YOUR_ORG/bots_edi/actions/workflows/build-and-push.yml/badge.svg)](https://github.com/YOUR_ORG/bots_edi/actions/workflows/build-and-push.yml)
[![CI](https://github.com/YOUR_ORG/bots_edi/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_ORG/bots_edi/actions/workflows/ci.yml)
```

## Troubleshooting

### Build Fails: Permission Denied

**Solution:** Ensure workflow has write permissions:
- Settings → Actions → General → Workflow permissions
- Select "Read and write permissions"

### Docker Hub Push Fails

**Solution:** Verify secrets are set correctly:
- Settings → Secrets and variables → Actions
- Check `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` exist

### Multi-arch Build Slow

This is normal. ARM64 builds can take 30-60 minutes due to emulation.

**Optimization:** Use GitHub-hosted larger runners (if available) or self-hosted ARM runners.

### Trivy Scan Failures

Non-critical vulnerabilities won't fail the build. To make them fail:

```yaml
- name: Run Trivy vulnerability scanner
  uses: aquasecurity/trivy-action@master
  with:
    exit-code: '1'  # Change from '0' to '1'
    severity: 'CRITICAL,HIGH'
```

## Customization

### Change Image Registries

Edit `build-and-push.yml`:

```yaml
env:
  REGISTRY_GHCR: ghcr.io
  REGISTRY_DOCKERHUB: docker.io
  # Add custom registry:
  REGISTRY_CUSTOM: registry.example.com
```

### Modify Platforms

Edit `build-and-push.yml`:

```yaml
platforms: linux/amd64,linux/arm64,linux/arm/v7  # Add arm/v7
```

### Adjust Test Database

Edit `ci.yml` services section to use PostgreSQL instead of MySQL:

```yaml
services:
  postgres:
    image: postgres:15
    env:
      POSTGRES_PASSWORD: testpass
      POSTGRES_DB: botsedi_test
    ports:
      - 5432:5432
```

## Best Practices

1. **Tag Releases Properly**: Use semantic versioning (v1.0.0, v1.1.0, etc.)
2. **Monitor Build Times**: Multi-arch builds are slow; consider limiting to amd64 for development
3. **Review Security Scans**: Check Trivy results regularly
4. **Update Dependencies**: Keep GitHub Actions up to date
5. **Use Branch Protection**: Require CI to pass before merging PRs

## Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Docker Build Push Action](https://github.com/docker/build-push-action)
- [GitHub Container Registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Trivy Security Scanner](https://github.com/aquasecurity/trivy)
