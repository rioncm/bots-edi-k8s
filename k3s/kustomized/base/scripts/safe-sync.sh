- -c
- |
set -e

echo "[INFO] Mappings sync worker starting..."
echo "[INFO] Watching: /signal/update"
echo "[INFO] Source: /git/current/"
echo "[INFO] Target: /mappings/"
echo "[INFO] Environment: ${BOTSENV}"

# Target directory within PVC
TARGET_DIR="/mappings/env/${BOTSENV}/usersys/mappings/git"

# Function to perform sync
sync_mappings() {
echo "[SYNC] Update detected at $(date)"

# Ensure target directory exists
mkdir -p "${TARGET_DIR}"

# Check if source has content
if [ ! -d "/git/current" ]; then
    echo "[ERROR] Source directory /git/current not found"
    return 1
fi

# Count files to sync
FILE_COUNT=$(find /git/current -type f -name "*.py" | wc -l)
echo "[SYNC] Found ${FILE_COUNT} mapping files"

if [ "${FILE_COUNT}" -eq 0 ]; then
    echo "[WARN] No .py files found in repository"
    return 0
fi

# Perform atomic copy using rsync-style approach
# Copy to temp directory first, then move
TEMP_DIR="${TARGET_DIR}.tmp.$$"
mkdir -p "${TEMP_DIR}"

echo "[SYNC] Copying to temporary location..."
cp -r /git/current/. "${TEMP_DIR}/"

# Atomic swap
echo "[SYNC] Performing atomic swap..."
rm -rf "${TARGET_DIR}.old" 2>/dev/null || true
if [ -d "${TARGET_DIR}" ]; then
    mv "${TARGET_DIR}" "${TARGET_DIR}.old"
fi
mv "${TEMP_DIR}" "${TARGET_DIR}"
rm -rf "${TARGET_DIR}.old"

# Set permissions
chmod -R u+rwX,g+rX "${TARGET_DIR}"

echo "[SYNC] ✓ Sync complete at $(date)"
echo "[SYNC] Files synced:"
find "${TARGET_DIR}" -type f -name "*.py" | sed 's|'"${TARGET_DIR}"'/||' | sort
echo "[SYNC] ---"
}

# Initial sync on startup
echo "[INFO] Performing initial sync..."
while [ ! -f "${SIGNAL_FILE}" ]; do
echo "[INFO] Waiting for initial git-sync..."
sleep 2
done
sync_mappings

# Watch for updates
echo "[INFO] Watching for updates (signal file: ${SIGNAL_FILE})"
LAST_MTIME=$(stat -c %Y "${SIGNAL_FILE}" 2>/dev/null || echo "0")

while true; do
sleep 5

if [ -f "${SIGNAL_FILE}" ]; then
    CURRENT_MTIME=$(stat -c %Y "${SIGNAL_FILE}" 2>/dev/null || echo "0")
    
    if [ "${CURRENT_MTIME}" != "${LAST_MTIME}" ]; then
    sync_mappings
    LAST_MTIME="${CURRENT_MTIME}"
    fi
fi
done