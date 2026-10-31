# GV POWERS ERP - Rollback Instructions

**Generated:** 2026-10-31T09:09:07.992246+05:30
**Current status:** No replacement was performed. There is nothing to roll back yet.
**Important:** These commands are for the Linux production server only. Do not run them on the Windows workspace. Confirm the actual service unit and database engine first.

## Preconditions

- Owner-approved maintenance window.
- Verified production unit: `erp.service` or `gvpowers.service`.
- Verified production database path and engine.
- A fresh production backup with a recorded SHA-256.
- Candidate path: `/home/kaml/erp-new/backups/database/gv_powers_erp_20261031_031122.sql.db` (reported; verify on server).
- Candidate SHA-256: `A4B6382B3F6258D1F34EA876023D831F4E848E3EDE20583DD2613C03EB708C8E`.

If production is PostgreSQL, stop: this SQLite candidate is not compatible. Use `pg_dump`/`pg_restore` and a PostgreSQL-specific rollback plan instead.

## SQLite Pre-Change Snapshot

```bash
set -eu
UNIT="erp.service"                 # verify: gvpowers.service may be the real unit
DB="/home/kaml/erp-new/instance/app.db"   # verify actual path
CAND="/home/kaml/erp-new/backups/database/gv_powers_erp_20261031_031122.sql.db"
STAMP="$(date +%Y%m%d_%H%M%S)"
ROLLBACK="/home/kaml/erp-new/backups/database/pre_restore_${STAMP}.db"

sudo systemctl stop "$UNIT"
# Prefer SQLite's consistent backup API over a raw copy:
sqlite3 "$DB" ".backup '$ROLLBACK'"
sha256sum "$DB" "$ROLLBACK" "$CAND"
```

If `sqlite3` is unavailable, use the application's Python environment and `sqlite3.Connection.backup`; do not use a raw `cp` while the service is running.

## Install Candidate

```bash
sudo install -o www-data -g www-data -m 640 "$CAND" "$DB"
sudo -u www-data sqlite3 "$DB" "PRAGMA integrity_check; PRAGMA foreign_key_check;"
sudo systemctl start "$UNIT"
sudo systemctl status "$UNIT" --no-pager
```

Verify:

- Login with the intended account (do not embed passwords in shell history).
- Dashboard loads.
- `/invoices` shows the expected 2 invoices.
- Invoice detail and print pages load.
- Customer and product pages load.
- No new errors in the service log.
- The default admin password is rotated only after explicit approval.

## Rollback

If any check fails:

```bash
sudo systemctl stop "$UNIT"
sudo install -o www-data -g www-data -m 640 "$ROLLBACK" "$DB"
sudo -u www-data sqlite3 "$DB" "PRAGMA integrity_check; PRAGMA foreign_key_check;"
sudo systemctl start "$UNIT"
sudo systemctl status "$UNIT" --no-pager
```

Do not delete `$ROLLBACK` or the candidate. Preserve both for investigation.

## PostgreSQL Branch

If the real production `DATABASE_URL` starts with `postgresql://`:

1. Do not copy any SQLite file.
2. Take a `pg_dump` custom-format backup.
3. Convert/validate the candidate's data into PostgreSQL only through an approved migration, not by file replacement.
4. Roll back with `pg_restore` into a clean database and restart the service.

## Post-Rollback Verification

- `systemctl status` is active.
- Application returns a login page or authenticated dashboard without 5xx.
- `PRAGMA integrity_check` = `ok` (SQLite) or database connection test succeeds (PostgreSQL).
- Table counts match the pre-change record.
- No invoice/payment data was changed during the failed attempt.
