# Multi-stage Dockerfile for Bots-EDI
# Builds production-ready container with minimal attack surface
# Supports multiple service types: webserver, engine, jobqueueserver, dirmonitor

# =============================================================================
# Stage 1: Builder - Build dependencies and wheels
# =============================================================================
FROM python:3.11-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
      gcc \
      g++ \
      libc-dev \
      python3-dev \
      default-libmysqlclient-dev \
      libpq-dev \
      build-essential \
      pkg-config \
      git \
    && rm -rf /var/lib/apt/lists/*

# Create build directory
WORKDIR /build

# Copy requirements files
COPY bots/requirements/*.txt /build/requirements/
COPY bots_config/prod-requirements.txt /build/

# Build wheels for all dependencies (includes transitive dependencies)
RUN pip wheel --no-cache-dir --wheel-dir /wheels \
    -r requirements/base.txt \
    -r requirements/linux.txt \
    -r prod-requirements.txt

# Install extras (optional components like SFTP, Excel, PDF)
COPY bots/requirements/extras.txt /build/requirements/
RUN pip wheel --no-cache-dir --wheel-dir /wheels \
    -r requirements/extras.txt || true

# =============================================================================
# Stage 2: Runtime Base - Minimal runtime environment
# =============================================================================
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive \
    HOME=/home/bots \
    BOTSENV=default

ENV PATH="/home/bots/.local/bin:${PATH}"

# Install only runtime dependencies (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      default-libmysqlclient-dev \
      libpq5 \
      tini \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 10001 bots

# Copy wheels from builder and install
COPY --from=builder /wheels /wheels
RUN pip install --no-cache --user --no-index --find-links=/wheels /wheels/* \
    && rm -rf /wheels

# =============================================================================
# Stage 3: Production - Application code and configuration
# =============================================================================
FROM runtime AS production

USER bots
WORKDIR /home/bots

# Copy application code from local repository
COPY --chown=bots:bots bots/bots/ /opt/bots/bots/
COPY --chown=bots:bots bots/requirements/ /opt/bots/requirements/

# Copy helper scripts and management commands
COPY --chown=bots:bots scripts/init-database.py /opt/bots/scripts/
COPY --chown=bots:bots scripts/healthcheck.py /opt/bots/scripts/
COPY --chown=bots:bots scripts/run-*.sh /opt/bots/scripts/

# Copy grammars and plugins (optional, user might mount these)
COPY --chown=bots:bots bots-grammars/ /opt/bots/grammars/
COPY --chown=bots:bots bots-plugins/ /opt/bots/plugins/

# Add scripts to PATH
ENV PATH="/opt/bots/scripts:${PATH}"

# Switch to root to install entrypoint
USER root

# Copy and setup entrypoint
COPY --chown=root:root entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create config directory
RUN mkdir -p /config && chown bots:bots /config

# Copy default configuration (can be overridden by ConfigMaps)
COPY --chown=bots:bots bots_config/settings.py /config/settings.py
COPY --chown=bots:bots bots_config/bots.ini /config/bots.ini

# Switch back to bots user
USER bots

# Expose web UI port
EXPOSE 8080

# Persistent volumes for data
VOLUME ["/home/bots/.bots"]

# Health check for webserver (will be overridden by K8s probes)
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8080/health/live || exit 1

# Use tini as PID 1 for proper signal handling
ENTRYPOINT ["/usr/bin/tini", "--", "/entrypoint.sh"]

# Default to no command - specified in K8s manifests
CMD []
