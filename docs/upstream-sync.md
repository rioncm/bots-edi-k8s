# Upstream Sync Workflow

This document outlines the process for syncing changes from the upstream Bots-EDI GitLab repositories into this containerization fork.

## Overview

This fork maintains three upstream sources:
- **bots**: Core application ([gitlab.com/bots-edi/bots](https://gitlab.com/bots-edi/bots))
- **bots-grammars**: EDI message definitions ([gitlab.com/bots-edi/bots-grammars](https://gitlab.com/bots-edi/bots-grammars))
- **bots-plugins**: Example translations ([gitlab.com/bots-edi/bots-plugins](https://gitlab.com/bots-edi/bots-plugins))

**Goal**: Keep this fork up-to-date with upstream improvements while preserving containerization enhancements.

## Initial Setup (One-Time)

### 1. Add Upstream Remotes

```bash
cd /Users/rion/VSCode/bots_edi

# Add upstream remote for main bots project
cd bots
git remote add upstream https://gitlab.com/bots-edi/bots.git
git fetch upstream

# Add upstream remote for grammars
cd ../bots-grammars
git remote add upstream https://gitlab.com/bots-edi/bots-grammars.git
git fetch upstream

# Add upstream remote for plugins
cd ../bots-plugins
git remote add upstream https://gitlab.com/bots-edi/bots-plugins.git
git fetch upstream

cd ..
```

### 2. Verify Remote Configuration

```bash
# Check bots remotes
cd bots && git remote -v
# Should show:
# origin    <your-github-fork>
# upstream  https://gitlab.com/bots-edi/bots.git

# Check grammars remotes
cd ../bots-grammars && git remote -v

# Check plugins remotes
cd ../bots-plugins && git remote -v
```

## Regular Sync Workflow

Perform this sync monthly or when significant upstream changes are released.

### Step 1: Fetch Upstream Changes

```bash
cd /Users/rion/VSCode/bots_edi

# Fetch all upstream changes
cd bots && git fetch upstream
cd ../bots-grammars && git fetch upstream
cd ../bots-plugins && git fetch upstream
cd ..
```

### Step 2: Check for Upstream Changes

```bash
# View what changed in bots
cd bots
git log HEAD..upstream/master --oneline --no-merges
git diff HEAD..upstream/master --stat

# View what changed in grammars
cd ../bots-grammars
git log HEAD..upstream/master --oneline --no-merges

# View what changed in plugins
cd ../bots-plugins
git log HEAD..upstream/master --oneline --no-merges

cd ..
```

### Step 3: Create Sync Branch

```bash
# Create a branch for upstream sync
git checkout -b sync-upstream-$(date +%Y%m%d)
```

### Step 4: Merge Bots Core

```bash
cd bots

# Option A: Merge (recommended - preserves history)
git merge upstream/master --no-ff -m "Merge upstream bots changes $(date +%Y-%m-%d)"

# Option B: Rebase (cleaner history, but more complex)
# git rebase upstream/master

cd ..
```

#### Handle Conflicts in Bots

Common conflict areas and resolution strategies:

**1. `bots/bots/management/commands/` - Our custom commands**
```bash
# Files we added (keep ours):
# - initdb.py (our custom database initialization)
# Resolution: Keep our version
git checkout --ours bots/bots/management/commands/initdb.py
```

**2. `bots/bots/healthcheck.py` - Our addition**
```bash
# This file doesn't exist upstream
# Resolution: Keep our version
git checkout --ours bots/bots/healthcheck.py
```

**3. Core files that might conflict**
```bash
# Files to carefully merge:
# - botsinit.py (we may have added type guards)
# - botsglobal.py (we may have modifications)
# - models.py (database models)

# Strategy: Manual merge, preserving both changes
# 1. Edit file to incorporate both changes
# 2. Test thoroughly
# 3. Commit
```

**4. Configuration files**
```bash
# Files that are fork-specific (keep ours):
# - bots/bots/config/settings.py (if we modified it)
# Resolution: Keep our containerization settings
```

### Step 5: Merge Grammars

```bash
cd bots-grammars

# Grammars rarely conflict - straightforward merge
git merge upstream/master --no-ff -m "Merge upstream grammars $(date +%Y-%m-%d)"

cd ..
```

### Step 6: Merge Plugins

```bash
cd bots-plugins

# Plugins rarely conflict - straightforward merge
git merge upstream/master --no-ff -m "Merge upstream plugins $(date +%Y-%m-%d)"

cd ..
```

### Step 7: Update Subproject References

Since we're treating subdirectories as part of the main project, commit all changes:

```bash
# From project root
git add bots/ bots-grammars/ bots-plugins/
git commit -m "Sync with upstream repositories $(date +%Y-%m-%d)

- Merged bots from gitlab.com/bots-edi/bots
- Merged grammars from gitlab.com/bots-edi/bots-grammars
- Merged plugins from gitlab.com/bots-edi/bots-plugins

See individual subdirectory commits for details."
```

## Testing After Sync

**Critical**: Always test after merging upstream changes.

### 1. Database Initialization

```bash
# Test database init script
conda activate botsedi
python scripts/init-database.py --config-dir bots_config --verbose
```

### 2. Health Checks

```bash
# Test all health check endpoints
export DJANGO_SETTINGS_MODULE=test_settings
python scripts/healthcheck.py --check live --config-dir bots_config
python scripts/healthcheck.py --check ready --config-dir bots_config
python scripts/healthcheck.py --check startup --config-dir bots_config
```

### 3. Container Build

```bash
# Build container image
docker build -t bots-edi:sync-test -f Dockerfile.new .

# Test container startup
docker run --rm bots-edi:sync-test /entrypoint.sh webserver --help
```

### 4. Run Unit Tests

```bash
cd bots
conda activate botsedi
export DJANGO_SETTINGS_MODULE=test_settings
python -m pytest tests/ -v
cd ..
```

### 5. Manual Smoke Test

```bash
# Start development server
python scripts/run_test_server.py

# In another terminal, test endpoints
curl http://localhost:8080/health/live
curl http://localhost:8080/health/ready

# Access web UI at http://localhost:8080
```

## Conflict Resolution Strategies

### Priority Matrix

When conflicts occur, use this priority order:

| File/Area | Strategy | Rationale |
|-----------|----------|-----------|
| Our additions (`healthcheck.py`, `initdb.py`, `scripts/`) | **Keep ours** | Containerization-specific |
| Core Python modules with minor changes | **Manual merge** | Preserve both improvements |
| Django models | **Manual merge carefully** | Database schema critical |
| Configuration files (`settings.py`, `bots.ini`) | **Keep ours** | Container-specific config |
| Tests | **Manual merge** | May need updating for our changes |
| Upstream-only files | **Take upstream** | No local modifications |

### Common Conflict Patterns

**Pattern 1: Type Guard Conflicts**

If we added type guards (`if botsglobal.ini is None`):

```python
# OURS (with type guard)
if botsglobal.ini is None:
    raise RuntimeError("botsglobal.ini not initialized")
botssys = botsglobal.ini.get('directories', 'botssys')

# THEIRS (upstream change)
botssys = botsglobal.ini.get('directories', 'botspath')  # Different key

# RESOLUTION: Keep both changes
if botsglobal.ini is None:
    raise RuntimeError("botsglobal.ini not initialized")
botssys = botsglobal.ini.get('directories', 'botspath')  # Use their key
```

**Pattern 2: Import Conflicts**

If we changed imports for Django:

```python
# OURS
from django.conf import settings as django_settings

# THEIRS
from django.conf import settings

# RESOLUTION: Keep our explicit import (better for type checking)
from django.conf import settings as django_settings
# Update references in the file
```

**Pattern 3: Health Check Integration**

If upstream adds monitoring code:

```python
# Strategy: Integrate their monitoring with our health checks
# Keep both systems, ensure they don't conflict
```

## Documenting Changes

### 1. Update CHANGELOG

```bash
cat >> CHANGELOG.md <<EOF

## [Unreleased] - $(date +%Y-%m-%d)

### Upstream Sync
- Merged changes from bots-edi/bots (commits: HASH1..HASH2)
- Merged changes from bots-edi/bots-grammars (commits: HASH1..HASH2)
- Merged changes from bots-edi/bots-plugins (commits: HASH1..HASH2)

### Compatibility Notes
- [List any breaking changes from upstream]
- [List any required configuration updates]

### Migration Steps
- [Any steps users need to take]

EOF
```

### 2. Update Documentation

If upstream changes affect our docs:

```bash
# Update relevant sections in:
- docs/development.md
- docs/configuration.md
- k3s/README.md
- README.md
```

## Merge and Release

### 1. Run Full Test Suite

```bash
# CI tests
./.github/workflows/ci.yml (locally via act, or push to branch)

# Or manual comprehensive test
python scripts/init-database.py --config-dir bots_config
python scripts/healthcheck.py --check startup --config-dir bots_config
docker build -t bots-edi:test -f Dockerfile.new .
docker run --rm bots-edi:test /entrypoint.sh webserver --help
```

### 2. Create Pull Request

```bash
git push origin sync-upstream-$(date +%Y%m%d)

# Create PR on GitHub with description:
# Title: "Sync with upstream repositories - [Date]"
# Body: Include CHANGELOG entries, testing notes, and any breaking changes
```

### 3. Review Checklist

Before merging:
- [ ] All tests pass
- [ ] Health checks work
- [ ] Container builds successfully
- [ ] Database initialization works
- [ ] No regressions in containerization features
- [ ] Documentation updated
- [ ] CHANGELOG updated
- [ ] Breaking changes documented

### 4. Merge and Tag

```bash
# Merge PR
git checkout main
git merge sync-upstream-$(date +%Y%m%d)

# Tag if significant changes
git tag -a v1.1.0 -m "Release v1.1.0 - Upstream sync $(date +%Y-%m-%d)"
git push origin main --tags
```

## Monitoring Upstream

### Subscribe to Upstream Changes

1. **Watch GitLab repositories**:
   - Go to https://gitlab.com/bots-edi/bots
   - Click "Watch" → "All Activity"
   - Repeat for grammars and plugins

2. **Check RSS feeds**:
   ```bash
   # Add to RSS reader:
   https://gitlab.com/bots-edi/bots/-/commits/master?format=atom
   https://gitlab.com/bots-edi/bots-grammars/-/commits/master?format=atom
   https://gitlab.com/bots-edi/bots-plugins/-/commits/master?format=atom
   ```

3. **Set calendar reminder**:
   - Monthly sync check (first Monday of each month)
   - Immediate sync for security releases

### Automated Monitoring (Optional)

Create a GitHub Action to check for upstream changes:

```yaml
# .github/workflows/check-upstream.yml
name: Check Upstream Changes

on:
  schedule:
    - cron: '0 9 * * 1'  # Every Monday at 9 AM
  workflow_dispatch:

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - name: Check upstream changes
        run: |
          # Fetch upstream
          git ls-remote https://gitlab.com/bots-edi/bots.git HEAD
          # Create issue if changes detected
```

## Troubleshooting

### Issue: Merge Conflict Too Complex

**Solution**: Create a fresh branch and cherry-pick specific commits:

```bash
git checkout -b upstream-selective
git cherry-pick <commit-hash>  # Pick specific upstream commits
```

### Issue: Tests Fail After Merge

**Strategy**:
1. Identify which tests fail
2. Check if tests need updating for our changes
3. Revert specific files if necessary
4. Document incompatibilities

### Issue: Container Build Fails

**Common causes**:
- New Python dependencies (update requirements)
- Path changes (update Dockerfile.new)
- New configuration needs (update entrypoint.sh)

**Solution**:
```bash
# Update requirements
pip freeze > bots/requirements/base.txt

# Test locally before committing
docker build -t bots-edi:debug -f Dockerfile.new .
```

### Issue: Database Schema Changes

**If upstream adds migrations**:

```bash
# Test migrations
python scripts/init-database.py --config-dir bots_config

# Update our initdb.py if needed
# Document in migration guide
```

## Best Practices

1. **Sync regularly**: Don't let changes pile up (monthly is good)
2. **Test thoroughly**: Containerization changes can have subtle impacts
3. **Document decisions**: Note why you resolved conflicts a certain way
4. **Keep changes minimal**: Fewer custom changes = easier syncing
5. **Communicate**: If conflicts are complex, reach out to upstream maintainers
6. **Preserve attribution**: Maintain upstream commit messages and authorship

## Emergency Hotfix from Upstream

If upstream releases a critical security fix:

```bash
# Fast-track process
git checkout -b hotfix-security
cd bots && git fetch upstream
git cherry-pick <security-fix-commit>
cd ..

# Fast test
python scripts/healthcheck.py --check ready --config-dir bots_config

# Immediate merge
git checkout main
git merge hotfix-security --no-ff
git push origin main

# Build and deploy immediately
git tag -a v1.0.1-security -m "Security hotfix from upstream"
git push origin --tags
```

## Additional Resources

- [Git Subtree Guide](https://www.atlassian.com/git/tutorials/git-subtree)
- [Syncing a Fork (GitHub Docs)](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/syncing-a-fork)
- [Resolving Merge Conflicts](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/addressing-merge-conflicts/resolving-a-merge-conflict-using-the-command-line)
- [Bots-EDI Documentation](https://bots.readthedocs.io/)
- [GitLab Bots-EDI Group](https://gitlab.com/bots-edi)

## Questions?

If you encounter issues during sync:
1. Check this document's troubleshooting section
2. Review upstream changelog/release notes
3. Consult upstream documentation
4. Ask in Bots-EDI community forums
5. Create an issue in this repository describing the conflict

---

**Last Updated**: 2026-02-04  
**Next Scheduled Sync**: [Set reminder for first Monday of next month]
