#!/bin/sh

# =========================================
# OPNsense Safe Firewall Test Tool
# =========================================

PIDFILE="/var/run/fw-safe-test.pid"
BACKUPDIR="/conf"
LOGFILE="/var/log/fw-safe-test.log"
ROLLBACK_SCRIPT="/root/fw-rollback.sh"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOGFILE"
}

# =========================================
# Root check
# =========================================
if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root."
    exit 1
fi

# =========================================
# Cancel rollback
# =========================================
if [ "$1" = "--cancel" ]; then
    if [ -f "$PIDFILE" ]; then
        PID=$(cat "$PIDFILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            kill "$PID"
            rm -f "$PIDFILE"
            log "Rollback cancelled (PID $PID)."
            echo "Rollback cancelled."
        else
            rm -f "$PIDFILE"
            log "Stale PID file removed."
            echo "Stale PID file removed."
        fi
    else
        echo "No rollback scheduled."
    fi
    exit 0
fi

# =========================================
# Status check
# =========================================
if [ "$1" = "--status" ]; then
    if [ -f "$PIDFILE" ]; then
        PID=$(cat "$PIDFILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "Rollback scheduled (PID $PID)."
        else
            echo "PID file exists but process not running."
        fi
    else
        echo "No rollback scheduled."
    fi
    exit 0
fi

# =========================================
# Validate input
# =========================================

MODE="$1"
TIMEOUT="${2:-300}"

if [ -z "$MODE" ]; then
    echo ""
    echo "Usage:"
    echo "  $0 <filter|nat|interface|all> [timeout_seconds]"
    echo "  $0 --cancel"
    echo "  $0 --status"
    echo ""
    echo "Modes:"
    echo "  filter     Reload pf firewall rules only"
    echo "  nat        Reload NAT rules (same as filter; NAT is part of pf)"
    echo "  interface  Reconfigure network interfaces only"
    echo "  all        Full system reload (interfaces + filter + services)"
    echo ""
    exit 1
fi

if [ "$MODE" != "filter" ] && [ "$MODE" != "nat" ] && [ "$MODE" != "interface" ] && [ "$MODE" != "all" ]; then
    echo "Invalid mode: $MODE"
    echo "Valid modes: filter, nat, interface, or all"
    exit 1
fi

# Validate timeout is numeric
case "$TIMEOUT" in
    ''|*[!0-9]*)
        echo "Timeout must be numeric."
        exit 1
        ;;
esac

# =========================================
# Prevent duplicate scheduling
# =========================================

if [ -f "$PIDFILE" ]; then
    OLD_PID=$(cat "$PIDFILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "Rollback already scheduled (PID $OLD_PID)."
        echo "Cancel first with: $0 --cancel"
        exit 1
    else
        rm -f "$PIDFILE"
        log "Removed stale PID file."
    fi
fi

# =========================================
# Create backup
# =========================================

TIMESTAMP=$(date +%Y%m%d%H%M%S)
BACKUP="$BACKUPDIR/config-backup-$TIMESTAMP.xml"

cp /conf/config.xml "$BACKUP"
if [ $? -ne 0 ]; then
    echo "Backup failed. Aborting."
    exit 1
fi

log "Backup created: $BACKUP"

# =========================================
# Create rollback script
# =========================================

cat > "$ROLLBACK_SCRIPT" << EOF
#!/bin/sh
echo "\$(date '+%Y-%m-%d %H:%M:%S') - ROLLBACK STARTED" >> "$LOGFILE"
cp "$BACKUP" /conf/config.xml
EOF

if [ "$MODE" = "filter" ] || [ "$MODE" = "nat" ]; then
cat >> "$ROLLBACK_SCRIPT" << EOF
# NAT is part of the pf ruleset; filter reload covers both
configctl filter reload
EOF
elif [ "$MODE" = "interface" ]; then
cat >> "$ROLLBACK_SCRIPT" << EOF
configctl interface reconfigure
EOF
else
cat >> "$ROLLBACK_SCRIPT" << EOF
/usr/local/etc/rc.reload_all
EOF
fi

cat >> "$ROLLBACK_SCRIPT" << EOF
echo "\$(date '+%Y-%m-%d %H:%M:%S') - Rollback completed." >> "$LOGFILE"
rm -f "$PIDFILE"
EOF

chmod 700 "$ROLLBACK_SCRIPT"

# =========================================
# Schedule rollback
# =========================================

(
    sleep "$TIMEOUT"
    "$ROLLBACK_SCRIPT"
) &

ROLLBACK_PID=$!
echo "$ROLLBACK_PID" > "$PIDFILE"

log "Rollback scheduled in $TIMEOUT seconds (PID $ROLLBACK_PID, mode: $MODE)."

echo ""
echo "================================================="
echo "Rollback scheduled."
echo "Mode: $MODE"
echo "Timeout: $TIMEOUT seconds"
echo ""
echo "Cancel with:"
echo "  $0 --cancel"
echo ""
echo "Check status:"
echo "  $0 --status"
echo "================================================="

