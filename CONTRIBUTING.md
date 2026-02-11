# Contributing to Bots EDI

Thank you for your interest in contributing to Bots EDI! This document provides guidelines for contributing to the project.

## Code of Conduct

Be respectful and inclusive. We're all here to make EDI processing better.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally
3. **Set up development environment** (see [docs/development.md](docs/development.md))
4. **Create a feature branch** from `develop`
5. **Make your changes**
6. **Test thoroughly**
7. **Submit a pull request**

## Development Workflow

### Branch Strategy

- `master` / `main` - Stable releases only
- `develop` - Main development branch
- `feature/*` - New features
- `bugfix/*` - Bug fixes
- `hotfix/*` - Urgent production fixes

### Creating a Feature Branch

```bash
git checkout develop
git pull origin develop
git checkout -b feature/my-awesome-feature
```

### Making Changes

1. **Write clean code**:
   - Follow PEP 8 for Python code
   - Use meaningful variable/function names
   - Add docstrings to functions
   - Keep functions small and focused

2. **Add tests**:
   - Unit tests for new functions
   - Integration tests for workflows
   - Place tests in `bots/tests/`

3. **Update documentation**:
   - Update relevant `.md` files in `docs/`
   - Add docstrings to new code
   - Update `README.rst` if needed

4. **Commit messages**:
   ```
   type(scope): brief description
   
   Longer description if needed.
   
   Closes #123
   ```
   
   Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

### Testing

Run tests before committing:

```bash
# Unit tests
cd bots/tests
python -m pytest

# Health checks
python scripts/healthcheck.py --check startup --config-dir bots_config

# Container build
docker build -f Dockerfile.new -t bots-edi:test .

# Kubernetes manifest validation
kubectl apply -k k3s/overlays/dev/ --dry-run=client
```

### Submitting Pull Requests

1. **Push your branch** to your fork:
   ```bash
   git push origin feature/my-awesome-feature
   ```

2. **Create Pull Request** on GitHub:
   - Title: Clear, concise description
   - Description: What, why, how
   - Reference related issues
   - Include test results

3. **Respond to feedback**:
   - Address reviewer comments
   - Push additional commits as needed
   - Mark conversations as resolved

4. **Squash commits** (if requested):
   ```bash
   git rebase -i develop
   ```

## What to Contribute

### High Priority

- **Bug fixes**: Especially critical issues
- **Documentation improvements**: Clarifications, examples
- **Test coverage**: Unit tests, integration tests
- **Performance improvements**: Profiling, optimization
- **Container improvements**: Build optimization, security

### Welcome Contributions

- **New EDI formats**: Additional grammar definitions
- **Integration examples**: Partner-specific mappings
- **UI enhancements**: Better UX, visualizations
- **API improvements**: REST API expansion
- **Monitoring**: Prometheus metrics, dashboards

### Please Discuss First

- **Major architecture changes**: Open an issue first
- **Breaking changes**: Requires consensus
- **New dependencies**: Justify the addition
- **Removal of features**: Explain use cases

## Coding Standards

### Python

```python
# Good
def process_edi_message(message: str, grammar: dict) -> dict:
    """
    Process an EDI message using the specified grammar.
    
    Args:
        message: Raw EDI message string
        grammar: Grammar definition dictionary
        
    Returns:
        Parsed message as dictionary
        
    Raises:
        EDIParseError: If message format is invalid
    """
    if not message:
        raise ValueError("Message cannot be empty")
    
    # Process message
    result = parse_with_grammar(message, grammar)
    return result

# Bad
def proc(m, g):
    r = parse_with_grammar(m, g)
    return r
```

### Django Models

```python
class Transaction(models.Model):
    """EDI transaction record."""
    
    message_id = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'bots_transaction'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Transaction {self.message_id}"
```

### Dockerfile

```dockerfile
# Good
FROM python:3.11-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

FROM python:3.11-slim
COPY --from=builder /wheels /wheels
RUN pip install --no-index --find-links=/wheels -r requirements.txt
USER 1000
```

### Kubernetes Manifests

```yaml
# Good
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bots-webserver
  labels:
    app: bots-edi
    component: webserver
    version: v1.0.0
spec:
  replicas: 3
  selector:
    matchLabels:
      app: bots-edi
      component: webserver
  template:
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
      containers:
      - name: webserver
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 1Gi
```

## Documentation

### Markdown Style

- Use ATX-style headers (`#` not underlines)
- Include code block language: ` ```bash ` not ` ``` `
- Use relative links: `[guide](../docs/guide.md)`
- Keep line length reasonable (~100 chars)

### Code Comments

```python
# Explain WHY, not WHAT (code shows what)

# Good
# Use binary mode to preserve EDIFACT control characters
with open(filename, 'rb') as f:
    content = f.read()

# Bad
# Open file
with open(filename, 'rb') as f:
    content = f.read()
```

## Containerization Contributions

### Adding New Service Types

1. Update `entrypoint.new.sh`:
   ```bash
   myservice)
       exec python bots-myservice.py
       ;;
   ```

2. Create deployment manifest:
   ```yaml
   # k3s/deployments/myservice.yaml
   ```

3. Update documentation

### Improving Docker Build

- Multi-stage builds preferred
- Minimize layers
- Use `.dockerignore`
- Pin versions
- Run as non-root

## Kubernetes Contributions

### Adding Environment

1. Create overlay directory:
   ```bash
   mkdir -p k3s/overlays/newenv
   ```

2. Create kustomization.yaml
3. Test build:
   ```bash
   kustomize build k3s/overlays/newenv/
   ```

### Updating Manifests

- Maintain backward compatibility
- Update all overlays if needed
- Test with `--dry-run=client`
- Document breaking changes

## Testing Guidelines

### Unit Tests

```python
import unittest

class TestEDIParser(unittest.TestCase):
    def setUp(self):
        self.parser = EDIParser()
    
    def test_parse_x12_message(self):
        message = "ISA*00*..."
        result = self.parser.parse(message)
        self.assertIsNotNone(result)
        self.assertEqual(result['format'], 'x12')
    
    def test_invalid_message_raises_error(self):
        with self.assertRaises(EDIParseError):
            self.parser.parse("INVALID")
```

### Integration Tests

```python
def test_end_to_end_transformation():
    # Setup
    input_file = create_test_edi_file()
    
    # Execute
    result = process_edi_file(input_file)
    
    # Verify
    assert result.status == 'success'
    assert output_file_exists()
    assert validate_output_format()
```

### Container Tests

```bash
# Test build
docker build -f Dockerfile.new -t bots-edi:test .

# Test entrypoint
docker run --rm bots-edi:test webserver --help

# Test health checks
docker run --rm bots-edi:test python /usr/local/bots/scripts/healthcheck.py --check startup
```

## Submitting Issues

### Bug Reports

Include:
- **Environment**: OS, Python version, container runtime
- **Steps to reproduce**: Exact commands/actions
- **Expected behavior**: What should happen
- **Actual behavior**: What actually happens
- **Logs**: Relevant error messages
- **Screenshots**: If applicable

Template:
```markdown
## Description
Brief description of the bug

## Environment
- OS: Ubuntu 22.04
- Python: 3.11.2
- Kubernetes: 1.28
- Bots EDI: v4.0.0

## Steps to Reproduce
1. Deploy with `kubectl apply -k k3s/overlays/dev/`
2. Upload EDI file via web UI
3. Observe error in logs

## Expected Behavior
File should process successfully

## Actual Behavior
Error: "Grammar not found"

## Logs
```
[ERROR] Grammar 'x12_850' not found in grammar cache
```

## Screenshots
(if applicable)
```

### Feature Requests

Include:
- **Use case**: Why is this needed?
- **Proposed solution**: How should it work?
- **Alternatives**: Other approaches considered
- **Additional context**: Related issues, examples

## Release Process

(For maintainers)

1. Update version numbers
2. Update CHANGELOG.md
3. Create release branch
4. Tag release: `v4.0.0`
5. Build and push container images
6. Update documentation
7. Publish release notes

## License

By contributing, you agree that your contributions will be licensed under the GNU General Public License v3.0.

## Questions?

- **Documentation**: Check `docs/` directory
- **Discussion**: GitHub Discussions
- **Commercial Support**: https://www.edi-intelligentsia.com

## Recognition

Contributors will be acknowledged in:
- CHANGELOG.md
- Release notes
- GitHub contributors page

Thank you for contributing to Bots EDI! 🚀
