#!/bin/bash
# Enhanced entrypoint for Bots-EDI containers
# Supports multiple service types: webserver, engine, jobqueueserver, dirmonitor
#
# Usage:
#   /entrypoint.sh webserver [args]
#   /entrypoint.sh engine [args]
#   /entrypoint.sh jobqueueserver [args]
#   /entrypoint.sh dirmonitor [args]

set -e

# Configuration
BOTSENV="${BOTSENV:-default}"
BOTS_DATA_DIR="/home/bots/.bots"
ENV_DIR="${BOTS_DATA_DIR}/env/${BOTSENV}"
CONFIG_DIR="${ENV_DIR}/config"
BOTSSYS_DIR="${ENV_DIR}/botssys"
USERSYS_DIR="${ENV_DIR}/usersys"
GRAMMARS_DIR="${BOTSSYS_DIR}/grammars"
SEED_USERSYS_DIR="/usr/local/bots/plugins/usersys"
SEED_GRAMMARS_DIR="/usr/local/bots/grammars"

# Colors for logging
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Initialize Bots environment
initialize_environment() {
    log_info "Initializing Bots environment: ${BOTSENV}"
    
    # Check and create environment base directory
    log_info "Ensuring environment directory exists: $ENV_DIR"
    if ! mkdir -p "$ENV_DIR" 2>/dev/null; then
        log_error "Failed to create environment directory: $ENV_DIR"
        log_error "Base directory: ${BOTS_DATA_DIR}"
        log_error "Directory exists: $([ -d "${BOTS_DATA_DIR}" ] && echo 'yes' || echo 'no')"
        log_error "Directory permissions: $(ls -ld "${BOTS_DATA_DIR}" 2>&1)"
        log_error "Current user: $(id)"
        log_error "Check PVC mount and fsGroup in pod securityContext"
        exit 1
    fi
    
    # Create environment directories
    if [ ! -d "$CONFIG_DIR" ]; then
        log_info "Creating config directory: $CONFIG_DIR"
        mkdir -p "$CONFIG_DIR" || {
            log_error "Failed to create config directory: $CONFIG_DIR"
            exit 1
        }
    fi
    
    if [ ! -d "$BOTSSYS_DIR" ]; then
        log_info "Creating botssys directory: $BOTSSYS_DIR"
        mkdir -p "$BOTSSYS_DIR" || {
            log_error "Failed to create botssys directory: $BOTSSYS_DIR"
            exit 1
        }
    fi
    
    # Copy configuration files if provided via /config mount
    if [ -f /config/settings.py ]; then
        log_info "Copying settings.py to $CONFIG_DIR"
        cp /config/settings.py "$CONFIG_DIR/settings.py"
    fi
    
    if [ -f /config/bots.ini ]; then
        log_info "Copying bots.ini to $CONFIG_DIR"
        cp /config/bots.ini "$CONFIG_DIR/bots.ini"
    fi
    
    # Ensure usersys is a real directory on the PVC (not a symlink to /opt)
    if [ -L "${ENV_DIR}/usersys" ]; then
        log_warn "Removing usersys symlink to enforce PVC-backed directory"
        rm -f "${ENV_DIR}/usersys"
    fi
    if [ ! -d "$USERSYS_DIR" ]; then
        log_info "Creating usersys directory: $USERSYS_DIR"
        mkdir -p "$USERSYS_DIR" || {
            log_error "Failed to create usersys directory: $USERSYS_DIR"
            exit 1
        }
    fi
    if [ -d "$SEED_USERSYS_DIR" ]; then
        if ! find "$USERSYS_DIR" -mindepth 1 -maxdepth 1 \
            ! -name '.filebrowser' ! -name 'fb' -print -quit | grep -q .; then
            log_info "Seeding usersys from image defaults"
            cp -R "$SEED_USERSYS_DIR/." "$USERSYS_DIR/"
        fi
    fi
    
    # Ensure grammars live on the PVC (not a symlink to /opt)
    if [ -L "${BOTSSYS_DIR}/grammars" ]; then
        log_warn "Removing grammars symlink to enforce PVC-backed directory"
        rm -f "${BOTSSYS_DIR}/grammars"
    fi
    if [ ! -d "$GRAMMARS_DIR" ]; then
        log_info "Creating grammars directory: $GRAMMARS_DIR"
        mkdir -p "$GRAMMARS_DIR" || {
            log_error "Failed to create grammars directory: $GRAMMARS_DIR"
            exit 1
        }
    fi
    if [ -d "$SEED_GRAMMARS_DIR" ] && [ -z "$(ls -A "$GRAMMARS_DIR" 2>/dev/null)" ]; then
        log_info "Seeding grammars from image defaults"
        cp -R "$SEED_GRAMMARS_DIR/." "$GRAMMARS_DIR/"
    fi
    
    log_success "Environment initialized: $ENV_DIR"
}

# Initialize database if needed
initialize_database() {
    log_info "Checking database initialization..."
    
    # Check if DB_INIT_SKIP is set (for when init-job handles this)
    if [ "${DB_INIT_SKIP:-false}" = "true" ]; then
        log_info "Skipping database initialization (DB_INIT_SKIP=true)"
        return 0
    fi
    
    # Run database initialization script
    if [ -f /usr/local/bots/scripts/init-database.py ]; then
        log_info "Running database initialization..."
        python /usr/local/bots/scripts/init-database.py --config-dir "$CONFIG_DIR" || {
            log_warn "Database initialization failed (may already be initialized)"
        }
    else
        log_warn "Database initialization script not found"
    fi
}

# Signal handlers for graceful shutdown
shutdown() {
    log_info "Received shutdown signal, gracefully stopping..."
    
    # Send SIGTERM to child process
    if [ -n "$CHILD_PID" ]; then
        kill -TERM "$CHILD_PID" 2>/dev/null || true
        wait "$CHILD_PID" 2>/dev/null || true
    fi
    
    log_success "Shutdown complete"
    exit 0
}

# Trap signals
trap shutdown SIGTERM SIGINT

# Main execution
main() {
    log_info "==================================================="
    log_info "Bots-EDI Container Entrypoint"
    log_info "==================================================="
    log_info "Environment: ${BOTSENV}"
    log_info "Config Dir: ${CONFIG_DIR}"
    log_info "Botssys Dir: ${BOTSSYS_DIR}"
    log_info "==================================================="
    
    # Initialize environment
    initialize_environment
    
    # Get service type (first argument)
    SERVICE_TYPE="${1:-}"
    shift || true  # Remove first arg, keep rest
    
    # Handle service type
    case "$SERVICE_TYPE" in
        webserver)
            log_info "Starting Bots webserver..."
            
            # Initialize database for webserver (first start)
            initialize_database
            
            # Start webserver
            log_info "Starting bots-webserver on port 8080..."
            exec bots-webserver -c"$CONFIG_DIR" "$@" &
            CHILD_PID=$!
            wait $CHILD_PID
            ;;
            
        engine)
            log_info "Starting Bots engine..."
            
            # Engine doesn't need DB init (webserver or init-job handles it)
            
            # Start engine
            log_info "Running bots-engine..."
            exec bots-engine -c"$CONFIG_DIR" "$@" &
            CHILD_PID=$!
            wait $CHILD_PID
            ;;
            
        jobqueueserver|jobqueue)
            log_info "Starting Bots job queue server..."
            
            # Start jobqueue server
            log_info "Running bots-jobqueueserver..."
            exec bots-jobqueueserver -c"$CONFIG_DIR" "$@" &
            CHILD_PID=$!
            wait $CHILD_PID
            ;;
            
        dirmonitor)
            log_info "Starting Bots directory monitor..."
            
            # Start directory monitor
            log_info "Running bots-dirmonitor..."
            exec bots-dirmonitor -c"$CONFIG_DIR" "$@" &
            CHILD_PID=$!
            wait $CHILD_PID
            ;;
            
        init-db|initdb)
            log_info "Running database initialization only..."
            initialize_database
            log_success "Database initialization complete"
            exit 0
            ;;
            
        shell|bash)
            log_info "Starting interactive shell..."
            exec /bin/bash
            ;;
            
        *)
            if [ -z "$SERVICE_TYPE" ]; then
                log_error "No service type specified"
                log_info "Usage: $0 <service-type> [args]"
                log_info "Service types: webserver, engine, jobqueueserver, dirmonitor, init-db, shell"
                exit 1
            else
                log_info "Executing custom command: $SERVICE_TYPE $*"
                exec "$SERVICE_TYPE" "$@" &
                CHILD_PID=$!
                wait $CHILD_PID
            fi
            ;;
    esac
}

# Run main
main "$@"
