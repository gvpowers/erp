# GV POWERS ERP - Security Audit

**Generated:** 2026-10-31T09:09:07.992246+05:30
**Scope:** Candidate SQLite backup, local live database, application configuration, authentication, and backup exposure.
**Status:** Read-only audit. No password, account, setting, or backup was changed.

## Executive Result

| Item | Result |
|---|---|
| Database integrity | Candidate: OK. Local live: OK. |
| Password hashing | `scrypt:32768:8:1` (strong, Werkzeug format). |
| Default admin password | **CRITICAL: still matches the application fallback.** |
| Password reset performed | No. |
| CSRF protection | Enabled globally via Flask-WTF. |
| Backup access | Download/delete routes require admin; delete has additional server-side gates. |
| Backup restore route | Placeholder only ("under development"). |
| Admin accounts | 1 active admin in candidate; 1 active admin in local live. |
| Admin email | Candidate: `gvpowers@admin` (invalid). Local live: `admin@gvpowers.in`. |
| `.env` in workspace | No. Only `.env.example`. |
| Production secrets | Not accessible; unverified. |
| Remote backup sync | Not evidenced in candidate (`backup_events=0`, `settings=0`). |
| PII in candidate | 2 customers, 2 invoices, 0 payments, plus audit logs and contact data. |

## Critical Findings

### 1. Default admin credentials remain active

The candidate admin password hash matches the application's fallback `ADMIN_PASSWORD`. The local live database also matches. The password value is intentionally not reproduced in this report. Rotate it through an approved change after the owner confirms the account and recovery process. Do not reset silently.

### 2. Production secret configuration is unverified

No `.env` exists in the workspace. The code falls back to `change-me-in-production` for `SECRET_KEY` and to default admin credentials. If the production service lacks a `.env` or uses the fallback, session cookies can be forged and the admin account is exposed. Verify the production `EnvironmentFile` and secret values on the server.

## Authentication and Authorization

- Login uses scrypt password hashes; this is a strong password-hashing choice.
- Login has no rate limit, lockout, CAPTCHA, or backoff in the route reviewed (`/login`). Brute-force protection is absent at the application layer; put it at the reverse proxy/WAF or add it.
- CSRF protection is applied globally; forms and AJAX use the app's CSRF helpers.
- Backup download is admin-only; backup delete is admin-only with additional before-request checks; backup restore is not implemented.
- The audit log records login/logout and business mutations. It does not include passwords or API keys.
- The candidate has one active admin and no other users. This is a single point of failure, not a vulnerability by itself.

## Data Exposure

- The candidate backup contains customer names, mobile numbers, GSTINs, invoice amounts, audit logs, and password hashes. Treat it as sensitive.
- The local file is at `C:\Users\kamle\PycharmProjects\gvpowers\erp\backups\gv_powers_erp_20261031_031122.sql.db`. Its OS ACL was not audited; production must use restrictive ownership and permissions (for example `www-data:www-data`, `0600` or `0640` according to the web user).
- The backup download route is authenticated and admin-gated, but the backup directory must never be served by Nginx as static content.
- Do not email or paste the backup into chat; it contains PII and credential material.

## Backup and Recovery

- The candidate is a local SQLite snapshot. It was created on the production path shown in its audit log.
- `backup_events` is empty and `settings` is empty; the remote archive is not verifiable from the candidate.
- The repository's `gvpowers.service` points to `/opt/gv_powers_erp` and has a PostgreSQL dependency; the candidate audit path points to `/home/kaml/erp-new`. Confirm the real production unit and database engine.
- Maintain at least one pre-change backup on the production server, outside the web root, with a verified hash.

## Data-Quality Findings With Security Relevance

- Candidate customer GSTIN `33AELFS8595R1ZR` fails the application checksum validator; verify before using it on new tax documents.
- Invoice 2 has a 0.02 line-total rounding variance; do not alter historical invoices without approval.
- All 8 products have zero purchase price; financial reporting is incomplete.
- Paid invoices have zero Payment rows; customer ledgers and payment reports are inconsistent.

## Priority Actions

1. Rotate the default admin password after owner approval.
2. Verify production `.env` and `SECRET_KEY`; remove insecure defaults.
3. Add login rate limiting or WAF protection.
4. Restrict backup file permissions and confirm the backup directory is not web-served.
5. Verify remote backup API configuration and delivery.
6. Correct the admin email only after approval.
7. Resolve the payment-ledger design gap before relying on customer statements.

## Not Tested

- Production Nginx/Cloudflare/TLS configuration.
- Production environment variables or service unit.
- Password brute-force resistance under load.
- OS-level file ACLs on the production server.
- Backup server delivery and retention.
