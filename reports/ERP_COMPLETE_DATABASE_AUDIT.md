# GV POWERS ERP - Complete Database Audit

**Generated:** 2026-10-31T09:09:07.992246+05:30 (local) / 2026-10-31T03:39:07.992237+00:00 (UTC)
**Auditor:** opencode
**Scope:** Candidate SQLite backup, current local SQLite database, source configuration, backups, and deployment artifacts.
**Replacement status:** NOT PERFORMED. Audit only. No database rows, passwords, invoices, payments, stock, backups, or files were modified.

## Executive Summary

The candidate backup is structurally healthy: `integrity_check=ok`, `quick_check=ok`, `foreign_key_check=[]`, no orphan rows, no duplicate business keys, and its columns/indexes match the current SQLAlchemy models. A temporary copy started successfully with the application, rendered the canonical invoice template, and served the authenticated admin pages tested.

However, the backup is **not safe to install blindly**:

- The production server was not accessed from this Windows workspace; no service stop, copy, restore, or restart was possible.
- The repository service unit and `.env.example` point to PostgreSQL at `/opt/gv_powers_erp`, while the candidate is SQLite and its own audit log points to `/home/kaml/erp-new/backups/database/`.
- The candidate is not a newer copy of the local live database: it contains different business data, and the local live database has later activity.
- Two invoices are marked paid for a total of INR 1,020,055.00 and have `amount_paid` set, but `payments` has zero rows. The customer ledger would show INR 1,020,055.00 outstanding while invoices show INR 0.00 due.
- The admin password hash matches the application's fallback default password.
- No `.env` exists in the workspace; production secret/API-key configuration cannot be verified.

## File Identity

| Item | Candidate | Local live |
|---|---|---|
| Path | `C:\Users\kamle\PycharmProjects\gvpowers\erp\backups\gv_powers_erp_20261031_031122.sql.db` | `C:\Users\kamle\PycharmProjects\gvpowers\erp\instance\app.db` |
| Size | 167,936 bytes | 167,936 bytes |
| File modified | 2026-10-31T08:41:31.514030+05:30 | 2026-10-31T08:54:51.701311+05:30 |
| SHA-256 | `A4B6382B3F6258D1F34EA876023D831F4E848E3EDE20583DD2613C03EB708C8E` | `EB1EFF0EE865D4E28A99411FACA2BB56FD6B21F4D80C2E796AEB0579C2F575F1` |
| SQLite integrity | `ok` | `ok` |
| Quick check | `ok` | `ok` |
| Foreign-key check | `[]` | `[]` |
| Encoding / journal | UTF-8 / delete | UTF-8 / delete |
| Page count / freelist | 41 / 0 | 41 / 0 |

The candidate contains an audit event showing its production creation path:

`Backup: /home/kaml/erp-new/backups/database/gv_powers_erp_20261031_031122.sql.db` at `2026-10-31 03:11:22.103013` (UTC).

The local live database has login activity at `2026-10-31 03:23:02` (UTC). Its business data is nevertheless a different dataset, not a newer version of the candidate.

## Table Inventory

| Table | Candidate rows | Local live rows | Candidate minus live |
|---|---:|---:|---:|
| audit_logs | 43 | 7 | 36 |
| backup_events | 0 | 0 | 0 |
| categories | 0 | 0 | 0 |
| customers | 2 | 1 | 1 |
| gst_master | 0 | 0 | 0 |
| invoice_items | 8 | 0 | 8 |
| invoice_sequences | 2 | 0 | 2 |
| invoices | 2 | 0 | 2 |
| notifications | 3 | 0 | 3 |
| payments | 0 | 0 | 0 |
| products | 8 | 2 | 6 |
| purchase_items | 0 | 0 | 0 |
| purchase_orders | 0 | 0 | 0 |
| quotation_items | 0 | 0 | 0 |
| quotations | 0 | 0 | 0 |
| settings | 0 | 0 | 0 |
| stock_movements | 19 | 0 | 19 |
| suppliers | 0 | 0 | 0 |
| users | 1 | 1 | 0 |

## Findings

| ID | Severity | Area | Finding |
|---|---|---|---|
| BLK-01 | BLOCKER | Deployment access | Production server was not accessed |
| BLK-02 | BLOCKER | Database engine / deployment path | SQLite candidate vs PostgreSQL service configuration |
| CRIT-01 | CRITICAL | Security | Default admin password is still in use |
| CRIT-02 | CRITICAL | Financial data | Paid invoices have no payment rows |
| HIGH-01 | HIGH | Freshness / replacement safety | Candidate is not a newer copy of the local live database |
| HIGH-02 | HIGH | Backup/archive | Remote archive sync is not evidenced |
| MED-01 | MEDIUM | Invoice totals | Invoice 2 has a 0.02 line-total rounding variance |
| MED-02 | MEDIUM | GST data quality | Customer GSTIN fails the application checksum validator |
| MED-03 | MEDIUM | Inventory valuation | All product purchase prices are zero |
| MED-04 | MEDIUM | Security configuration | No .env in local workspace; insecure fallbacks apply locally |
| LOW-01 | LOW | Admin identity | Admin email is not a valid email address |
| LOW-02 | LOW | Low-stock alerts | Low-stock alert metadata is incomplete |
| INFO-01 | INFO | Database integrity | Core integrity checks passed |
| INFO-02 | INFO | Application compatibility | Candidate schema matches the app models |

### BLK-01 - Production not accessed

The workspace is Windows (`C:\Users\kamle\PycharmProjects\gvpowers`). It has no `systemctl`, no Nginx configuration, and no verified production connection. The target described by the owner is Linux (`/home/kaml/erp-new`, `erp.service`, Gunicorn, Nginx, Cloudflare, `erp.gvpowers.in`), but that host was not accessible. No production changes were attempted.

### BLK-02 - SQLite candidate vs PostgreSQL service configuration

- Candidate: SQLite 3 database.
- `erp/gvpowers.service`: `WorkingDirectory=/opt/gv_powers_erp`, `Wants=postgresql.service`, `EnvironmentFile=/opt/gv_powers_erp/.env`.
- `erp/.env.example`: `DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/gv_powers_erp`.
- Candidate audit log: `/home/kaml/erp-new/backups/database/...`.

The actual production unit and `DATABASE_URL` must be confirmed. If production uses PostgreSQL, this SQLite file is not a drop-in database restore and must not be copied over the PostgreSQL data directory or used as a PostgreSQL dump.

### CRIT-01 - Default admin password still in use

The candidate admin password hash matches the application fallback `ADMIN_PASSWORD`. The local live database also matches. The password was not changed. This is a critical credential risk because the fallback is present in source and may be publicly known.

### CRIT-02 - Paid invoices without payment records

Candidate invoices:

| Invoice | Amount paid | Payment rows | Payment sum | Balance due |
|---|---:|---:|---:|---:|
| `INV-29092026-001` | 659,000.00 | 0 | 0.00 | 0.00 |
| `INV-30102026-001` | 361,055.00 | 0 | 0.00 | 0.00 |

The invoice totals and `amount_paid` fields are internally consistent, but the Payment table is empty. The customer ledger computes credits only from `payments`, so it reports a closing balance of INR 1,020,055.00, while the invoices report zero due. This is an existing reporting/data-model inconsistency. Per the owner's rules, no payment records were created or altered.

### HIGH-01 - Candidate and local live are different datasets

The candidate has 2 invoices, 2 customers, 8 products, 19 stock movements, and 43 audit logs. The local live database has 0 invoices, 1 customer, 2 products, 0 stock movements, and 7 audit logs. The customer and product IDs overlap but describe different records, so this is not a safe incremental update.

### HIGH-02 - Remote archive not evidenced

Candidate `backup_events` has 0 rows and `settings` has 0 rows. The only backup evidence inside the database is the local `backup_created` audit event. Production environment variables may configure the remote archive, but that cannot be verified from this workspace. Confirm `BACKUP_API_URL`, `BACKUP_API_KEY`, and the backup server delivery status on the production host.

### MED-01 - Invoice 2 rounding variance

`INV-30102026-001`: line totals sum to 361,055.22; taxable + CGST + SGST is 361,055.24; the stored grand total is 361,055.00 after round-off of -0.24. The aggregate invoice totals are correct, but the line-level sum is 0.02 lower. No historical data was changed.

### MED-02 - GSTIN validation

Candidate customer 1 GSTIN `33AELFS8595R1ZR` returns `False` from the application's own `validate_gstIN()` checksum validator. This may be a data-entry issue or a validator issue; it should be verified against the GST portal before using it on new tax documents. No GSTIN was changed.

### MED-03 - Zero purchase prices

All 8 candidate products have `purchase_price=0.00`. Inventory value and profit reports that depend on purchase cost will be misleading. Purchase costs were not invented or changed.

### MED-04 - Local configuration and secret fallbacks

No `.env` exists at the project root or in `erp`. The application therefore uses its fallback `SECRET_KEY` and default admin credentials in this workspace. The production `.env` is not accessible, so production secret strength is unverified.

### LOW-01 - Admin email invalid

Candidate admin email is `gvpowers@admin`, which is not a valid email address. This may affect email workflows. It was not changed.

### LOW-02 - Low-stock alert metadata

All 8 candidate products are at or below `min_stock`, but only 3 have `low_stock_alert_active=1` and matching notifications. Five low-stock products have no active alert metadata. A normal dashboard low-stock check after restore may create additional notifications; that behavior was not triggered on the original candidate.

### INFO-01 / INFO-02 - Integrity and compatibility

- No orphan rows were found in the checked relationships.
- No duplicate business keys were found in the checked tables.
- Every product's `stock_quantity` matches the sum of its stock movements.
- Candidate columns and indexes match the model schema; `schema_version=29` versus local live `30` is not a table/column mismatch.
- A temporary candidate copy was started with the app: schema hash and row counts were unchanged, the canonical invoice template rendered, and `/invoices`, `/products`, `/customers`, `/reports`, `/settings`, and `/backup` returned HTTP 200 for an authenticated admin test session.

## Replacement Readiness

**Status: BLOCKED.** Do not replace any database yet.

Required gates before any production write:

1. Confirm the actual production host, unit file, working directory, and database engine (`DATABASE_URL`).
2. If production is PostgreSQL, stop: this SQLite candidate is not compatible.
3. Take a production-side consistent snapshot and record its SHA-256; do not rely on the candidate as the only backup.
4. Compare current production rows against the candidate and identify all production-only records.
5. Obtain owner approval for the default-password rotation and the payment-ledger inconsistency.
6. Schedule a maintenance window; stop the service; preserve the existing DB; install only after the delta review; restart and verify.
7. Keep the pre-restore database and candidate unchanged for rollback.

## What Was Not Done

- No production service was stopped or started.
- No production or local database was replaced.
- No invoice, payment, customer, product, stock, audit, or settings row was modified.
- No password was reset.
- No backup was deleted or overwritten.
- No financial record was "repaired" or backfilled.
- No purchase prices, GSTINs, or low-stock alerts were invented.
- No claim is made that the candidate is the latest production database.

## Report Map

- `database_health.json` - machine-readable audit and findings.
- `table_inventory.csv` - per-table counts and schema inventory.
- `invoice_audit.csv` - invoice reconciliation details.
- `inventory_audit.csv` - product stock/movement reconciliation.
- `security_audit.md` - credentials, configuration, and data-exposure review.
- `deployment_audit.md` - environment, service, and deployment findings.
- `rollback_instructions.md` - server-side rollback procedure for a future approved restore.
