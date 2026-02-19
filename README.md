# OPNsense Tools

A collection of shell scripts for managing OPNsense firewalls safely.

---

## bin/opnsense-rollback.sh

A safety net for applying risky firewall changes. It schedules an automatic config restore so that if you lose access after a bad rule, the firewall rolls itself back without manual intervention.

### How it works

1. Backs up `/conf/config.xml` with a timestamp
2. Schedules a background process to restore the backup after a timeout
3. Apply your changes in the OPNsense UI
4. If the change is good — cancel the rollback manually
5. If you lose access — do nothing, the rollback fires automatically and restores connectivity

### Usage

```sh
opnsense-rollback.sh <mode> [timeout_seconds]
opnsense-rollback.sh --cancel
opnsense-rollback.sh --status
```

**Modes:**

| Mode | Reload command | Use when you changed |
|---|---|---|
| `filter` | `configctl filter reload` | Firewall rules, aliases |
| `nat` | `configctl filter reload` | Port forwards, 1:1 NAT, outbound NAT |
| `interface` | `configctl interface reconfigure` | Interface IPs, gateways |
| `all` | `/usr/local/etc/rc.reload_all` | Multiple areas, VLANs, WAN failover |

Timeout defaults to **300 seconds** (5 minutes) if not specified.

### Example

```sh
# 1. Schedule the rollback safety net FIRST
opnsense-rollback.sh filter 120

# 2. Apply your firewall changes in the OPNsense UI

# 3. Test that you can still reach the firewall / your services

# 4a. Everything is fine — cancel the rollback:
opnsense-rollback.sh --cancel

# 4b. Lost access — do nothing. The rollback fires automatically after 120s.
```

### Requirements

- OPNsense (FreeBSD-based)
- Must be run as root
- POSIX `/bin/sh` — no bash required

### Files created at runtime

| Path | Purpose |
|---|---|
| `/var/run/fw-safe-test.pid` | PID of the scheduled rollback process |
| `/var/log/fw-safe-test.log` | Audit log of all actions |
| `/root/fw-rollback.sh` | Generated rollback script (overwritten each run) |
| `/conf/config-backup-<timestamp>.xml` | Config snapshot taken before each test |

> **Note:** Backup files in `/conf` are not automatically cleaned up. Remove old `config-backup-*.xml` files periodically.

---

## License

MIT
