#!/bin/sh
set -eu


log() {
    printf '%s [filebrowser-init] %s\n' "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" "$*"
}

fail() {
    log "ERROR: $*"
    exit 1
}

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

require_env() {
    eval "val=\${$1:-}"
    [ -n "$val" ] || fail "Missing required env var: $1"
}

create_config() {
    cat > "$fb_dir/settings.json" <<EOF
{
  "port": 8081,
  "baseURL": "/",
  "address": "0.0.0.0",
  "log": "stdout",
  "database": "$fb_dir/filebrowser.db",
  "root": "$root"
}
EOF
}
env_name="${BOTSENV:-default}"
root="/home/bots/.bots/env/${env_name}"
fb_dir="${root}/.filebrowser"
data_dir="${root}/botsys/data"

require_cmd filebrowser
require_env SUPERUSER_USERNAME
require_env SUPERUSER_PASSWORD

log "Initializing filebrowser"
log "BOTSENV: ${env_name}"
log "Root: ${root}"
log "Database: ${fb_dir}/filebrowser.db"

log "Ensuring directory structure exists"
mkdir -p "$data_dir/incoming" "$data_dir/outgoing" "$data_dir/drop" "$data_dir/pickup" || fail "Failed to create fb directories"
mkdir -p "$fb_dir" || fail "Failed to create filebrowser metadata directory"

if [ ! -f "$fb_dir/filebrowser.db" ]; then
    log "Filebrowser database not found, initializing..."
    create_config
    # generate bcrypt hash
    HASHED_PASS="$(filebrowser hash "$SUPERUSER_PASSWORD")"
    filebrowser -c "$fb_dir/settings.json" --username "$SUPERUSER_USERNAME" --password "$HASHED_PASS" 

    log "Filebrowser initialization complete"
else
    log "Filebrowser database already exists, skipping initialization"
    filebrowser -c "$fb_dir/settings.json" 
fi
