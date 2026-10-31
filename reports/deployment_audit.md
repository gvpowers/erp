# GV POWERS ERP - Deployment Audit

**Generated:** 2026-10-31T09:09:07.992246+05:30
**Target reported by owner:** `/home/kaml/erp-new`, `erp.service`, Gunicorn, Nginx, Cloudflare Tunnel, `erp.gvpowers.in`.
**Actual audit environment:** Windows workspace `C:\Users\kamle\PycharmProjects\gvpowers`.

## Result

**Deployment/replacement: BLOCKED.** No production access, no service control, and an unresolved database-engine/path mismatch.

## Evidence

| Item | Finding |
|---|---|
| Workspace OS | Windows `win32`; PowerShell 5.1. |
| Production shell tools | `systemctl`, `nginx`, and production service control unavailable. |
| Repo service unit | `erp/gvpowers.service`: `WorkingDirectory=/opt/gv_powers_erp`, `Wants=postgresql.service`, `EnvironmentFile=/opt/gv_powers_erp/.env`. |
| Owner-reported path | `/home/kaml/erp-new`. |
| Candidate audit-log path | `/home/kaml/erp-new/backups/database/gv_powers_erp_20261031_031122.sql.db`. |
| Candidate database | SQLite, 167,936 bytes, integrity OK. |
| Production DB config | Not verifiable. `.env.example` uses PostgreSQL; local app defaults to SQLite development. |
| Local app processes | Four `app.py` processes were initially observed, with PID 15064 listening on `127.0.0.1:5000`; by the later recheck, no `app.py` process or port 5000 listener remained. |
| Local live DB | `C:\Users\kamle\PycharmProjects\gvpowers\erp\instance\app.db`, 167,936 bytes, SHA-256 `EB1EFF0EE865D4E28A99411FACA2BB56FD6B21F4D80C2E796AEB0579C2F575F1`. |
| Candidate DB | `C:\Users\kamle\PycharmProjects\gvpowers\erp\backups\gv_powers_erp_20261031_031122.sql.db`, 167,936 bytes, SHA-256 `A4B6382B3F6258D1F34EA876023D831F4E848E3EDE20583DD2613C03EB708C8E`. |
| Gunicorn config | `bind=0.0.0.0:8000`, gthread, timeout 120, preload_app=True, logs under `logs/`. |
| Nginx | No Nginx config in the workspace; not verified. |
| Cloudflare | No tunnel configuration in the workspace; not verified. |
| Reports location | `C:\Users\kamle\PycharmProjects\gvpowers\erp\reports` |

## Critical Deployment Findings

1. **Database-engine ambiguity.** A SQLite file cannot be dropped into a PostgreSQL deployment. If the real production `DATABASE_URL` is PostgreSQL, this candidate is not a valid restore artifact. If production is SQLite, the actual file path and service unit must be confirmed.
2. **Deployment-path drift.** The repo service unit says `/opt/gv_powers_erp`; the candidate's own audit log says `/home/kaml/erp-new`. Do not assume either path is the live service.
3. **Freshness not proven.** The candidate snapshot is from `2026-10-31 03:11:22` (its audit log). The local live database has activity at `2026-10-31 03:23:02`, but different data. The current production database was not available to compare.
4. **No remote archive evidence.** Candidate `backup_events` and `settings` are empty; confirm the backup API environment variables on the server.
5. **No production health check.** Gunicorn/Nginx/Cloudflare/TLS/DNS were not reachable or authenticated from this environment.

## Candidate vs Local Live

| Table | Candidate | Local live |
|---|---:|---:|
| users | 1 | 1 |
| customers | 2 | 1 |
| products | 8 | 2 |
| invoices | 2 | 0 |
| invoice_items | 8 | 0 |
| payments | 0 | 0 |
| stock_movements | 19 | 0 |
| audit_logs | 43 | 7 |
| backup_events | 0 | 0 |

The local live database is not a superset of the candidate and the candidate is not a newer copy of the local live database. They are separate datasets.

## Safe Deployment Sequence (Future, Server-Side Only)

1. Confirm the active unit (`systemctl status erp.service` or `gvpowers.service`) and its `WorkingDirectory`/`EnvironmentFile`.
2. Confirm the real `DATABASE_URL`. If PostgreSQL, stop and use a PostgreSQL backup/restore procedure; do not use this SQLite file.
3. Take a consistent production backup; record size/SHA-256; keep it outside the web root.
4. Stop the service and confirm no process holds the SQLite file.
5. Snapshot and compare the current production DB against the candidate; identify production-only rows.
6. Obtain owner approval for the default-password rotation and payment-ledger mismatch.
7. Install the candidate only if the engine/path and row-delta review pass.
8. Start the service, verify integrity, table counts, login, invoice pages, dashboard, and reports.
9. Keep the pre-change DB and candidate for rollback.

## Not Verified

- Actual production unit name and path.
- Actual production database engine and URL.
- Nginx reverse proxy, TLS, HSTS, and Cloudflare tunnel.
- Production backup API delivery.
- Production file permissions and ownership.
- Production health/HTTP status.
