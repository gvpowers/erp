# GV Powers ERP — Implementation Report

## 1. Overview

Five requested features were implemented in the production monolith `app.py`
(plus its Jinja templates), backed by a 38-test pytest suite. All features are
smoke- and boot-verified; the development database was cleaned of all smoke
artifacts after verification.

Deployment entry point (`wsgi.py`) imports cleanly and every new route returns
`200` under an admin session.

## 2. Files changed

| File | Change |
| --- | --- |
| `app.py` | All backend logic for the five features (see sections below) |
| `templates/quotations/quotation_preview.html` | Convert button, status badge, converted banner, alert chip |
| `templates/quotations/quotation_form.html` | Status/expiry hint text |
| `templates/quotations/quotation_detail.html` | Status actions (Accept/Reject/Convert/Expire) |
| `templates/invoices/invoice_detail.html` | "From quotation" link when `quotation_id` is set |
| `templates/customers/customer_ledger.html` | **New** — ledger page (filters, KPI cards, running balance, exports) |
| `templates/customers/customer_profile.html` | "View Ledger" button in profile header |
| `templates/admin/dashboard.html` | Range switcher, quick actions, 12 KPI cards, outstanding customers, recent activity, chart |
| `templates/reports/low_stock_report.html` | **New** — low-stock report page (prefill-PO modal, export buttons) |
| `templates/products/products.html` | Low-stock badge + "Low Stock" stock filter option |
| `templates/layouts/admin_layout.html` | Sidebar link to `/reports/low-stock`; low-stock alert count |
| `tests/conftest.py` + `tests/test_*.py` (6 files) | **New** — pytest suite, 38 tests |
| `requirements.txt` | Added `pytest==8.3.5` |

## 3. Feature 1 — Quotation → Invoice conversion

- `POST /quotations/<int:qid>/convert` (`app.py:3755`, `convert_quotation_to_invoice` at `:3757`).
- Guards: only `ACCEPTED` quotations convert; already-converted is blocked;
  insufficient stock rolls back (`IntegrityError` handled); expiry auto-blocks.
- Converts line items with GST, computes `grand_total`, deducts stock and
  records `_record_movement('sale', -qty, 'invoice', inv.id)`; finalized invoice
  is `status='completed'`, `payment_status='due'`, `balance_due=grand_total`.
- Sets `qt.status='converted'`, writes the invoice number into `qt.invoice_number`.
- Deduplication enforced at DB level: `Invoice.quotation_id` + unique index
  `ix_invoices_quotation_id`.
- `POST /quotations/<int:qid>/status` (`:3828`): draft → accepted/rejected;
  `POST /quotations/<int:qid>/expire`: marks overdue quotations expired.
- Preview page shows status-aware actions; invoice detail shows the source
  quotation link. E2E smoke test passed (convert → stock → movement → banner).

## 4. Feature 2 — Customer Ledger

- Helpers `_customer_ledger_data(cid, from_date, to_date)` (`app.py:2450`) and
  `_parse_ledger_dates()` (`:2517`).
- Semantics: opening balance = sum of non-cancelled invoices dated before `from`
  minus payments received before `from` (filtered on `Payment.payment_date`);
  entries = payments (credit) + invoices (debit) in range, excluding cancelled;
  closing = opening + net movement. All arithmetic is `Decimal` (quantized to
  0.01) to avoid float drift.
- Routes: `GET /customers/<int:cid>/ledger` (`:2525`), `GET /customers/<int:cid>/ledger/export/<fmt>` (`:2540`, fmt = `csv`/`excel`/`pdf`), `GET /api/v1/customers/<int:cid>/ledger` (`:2589`).
- `templates/customers/customer_ledger.html`: date filters, 4 KPI cards, running
  balance table with running total and open/total/closing rows, print + export buttons.
- "View Ledger" button added to `customer_profile.html`. Smoke tests confirmed
  page/JSON/CSV/Excel/PDF all return 200.

## 5. Feature 3 — Concurrency-safe numbering

- New `InvoiceSequence` model + `invoice_sequences` table; `_ensure_invoice_sequence_columns`
  backfills counters from legacy rows on startup so existing numbers are never reused.
- `_allocate_sequence(prefix, model)` does an atomic `UPDATE ... RETURNING`
  (`db.session.execute` with `execution_options(synchronize_session=False)`) then
  commits immediately, then seeds from any higher legacy rows.
- All number generation moved to the new engines: invoices, quotations, POs,
  credit notes, purchase credit notes, debit notes, pro-forma invoices, service invoices.
- Verified by `test_concurrent_invoice_numbers_all_unique` (10 threads, all numbers distinct).

## 6. Feature 4 — Advanced Dashboard

- `GET /dashboard` (`app.py:2089`): range switcher `?range=7d|30d|month|fy`
  (default `month`); KPI queries for sales, collections, opening balance
  (as of day before range start), invoice count, plus totals for customers,
  products, revenue, outstanding, and counts for pending / fully-paid / low-stock.
- Outstanding-customers query (join invoices, `balance_due > 0`, not cancelled,
  ordered by due, top 10) and an 8-item recent-activity feed (latest invoices,
  quotations, payments).
- Chart data: daily buckets when range ≤ 62 days, monthly otherwise
  (SQL `extract`), exposed to the template as `chart_data`.
- `templates/admin/dashboard.html`: 7D/30D/Month/FY buttons, quick-actions strip,
  12 KPI cards, Outstanding Customers + Recent Activity cards, chart script.
- Sales-role users are routed to the existing sales dashboard view.
- Verified: all 4 ranges render 200; opening balance test asserts `Rs. 1,180.00`
  is included in the range-day opening (payment on day 1 not counted in opening).

## 7. Feature 5 — Low-stock notifications

- Product columns: `min_stock`, `low_stock_alert_active`, `last_low_stock_notification_at`.
- `_run_low_stock_check()` (`app.py:2662`) + `_low_stock_suggested_qty()` (`:2655`):
  emits notifications to `admin`/`manager` roles, deduplicated via
  `low_stock_alert_active` and a 24h window; auto-resolves when stock recovers
  above `min_stock`. Triggered from dashboard, invoice creation, conversion,
  and PO create/receive.
- Report: `GET /reports/low-stock` (`:4220`) → `templates/reports/low_stock_report.html`
  (low-stock + out-of-stock products, suggested qty, prefill-PO modal).
- Exports: `GET /reports/export/<fmt>/low_stock` (`:4557`) for csv/excel/pdf.
- UI: sidebar link, dashboard alert count, product list badge/filter.

## 8. Database changes (migration)

Run once after deploying the updated `app.py` (idempotent):

```
python -c "from app import create_app; from app import db; a=create_app(); a.app_context().push(); db.create_all(); from app import _ensure_invoice_sequence_columns; _ensure_invoice_sequence_columns()"
```

Or simply start the app — startup calls `_ensure_invoice_sequence_columns()`,
which creates the `invoice_sequences` table, adds missing Product/Invoice columns
on SQLite, and backfills sequence counters.

## 9. Tests

```
python -m pytest tests -v          # from GV_POWERS_ERP
# 71 passed
```

- `test_numbering.py` — format, per-day sequencing, gap never recycled, legacy
  seeding, 10-thread concurrency uniqueness.
- `test_conversion.py` — accepted-only guard, invoice creation, stock/movement,
  duplicate blocked, insufficient stock, status transitions, expiry.
- `test_ledger.py` — page/JSON/exports, opening balance boundary, cancelled exclusion, auth.
- `test_lowstock.py` — notification, dedup, auto-resolve, suggested-qty formula,
  report/export routes, admin-only guard.
- `test_dashboard.py` — all ranges render, default month, outstanding customers,
  opening-balance boundary, sales role view, auth.
- `test_sidebar.py` — **new** — exactly-one-active sidebar link across 13 pages;
  regression for the Reports/Low-Stock double-highlight.
- `test_invoice_edit.py` — **new** — admin edits finalized invoices; server-side
  recalculation; stock delta & product replacement; payment preservation;
  insufficient-stock / no-items rejection; audit trail; sales role permissions.
- `test_sidebar_scroll.py` — **new** — regression for Bug 3: app.js ships the
  sidebar scroll save/restore (`pagehide`/`pageshow`), authenticated pages render
  the scrollable `.sidebar-nav`, and the login page does not (so stale positions
  are cleared on login).

## 10. Bug fixes applied (2026-08)

### Bug 1 — Sidebar highlights both `Reports` and `Low Stock` on `/reports/low-stock`

- **Root cause:** `templates/layouts/admin_layout.html` used a substring test
  `'report' in request.endpoint` for the Reports link, which also matched the
  `low_stock_report` endpoint.
- **Fix:** Reports link now uses an explicit endpoint whitelist
  (`reports_page, sales_report, payments_report, outstanding_report, gst_report,
  inventory_report, profit_report, customer_report, report_export`). Low Stock
  keeps its exact `==` match. While auditing, two more latent misses were fixed:
  `customer_ledger` added to the Customers tuple and `edit_invoice` to the
  Invoice History tuple; Purchases link now also matches `purchase_orders` (the
  actual endpoint, since `/purchases` redirects there).
- **Tests:** `tests/test_sidebar.py` asserts each of 13 pages highlights exactly
  one nav item, including `/reports/low-stock` → Low Stock only.

### Bug 2 — Admin could not edit invoices

- **Root causes:**
  1. `templates/sales/invoice_history.html` gated `Edit Invoice` on
     `editable` (non-cancelled AND draft-or-pending), disabling it for completed
     invoices even for admins.
  2. Backend `_jinv_editable` blocked edit on `payment_status == 'paid'`
     invoices regardless of role (that helper also guards Delete, so it was kept).
  3. `billing/new_invoice.html` ignored `edit_mode` entirely — it always POSTed
     to `/invoices/create` and rendered a blank form, so the existing edit
     workflow was effectively broken (opening the editor and saving would have
     created a duplicate invoice).
- **Changes (`app.py` + templates):**
  - New `_inv_editable_for_user(inv)` (`app.py:3289`): admins may edit any
    non-cancelled invoice (including paid/completed); other roles keep the
    original draft-or-(pending/due) rule. Cancelled invoices remain immutable.
  - Rewritten `POST /invoices/<int:iid>/edit` (`edit_invoice`, `app.py:3323`):
    parses JSON or legacy form arrays; requires ≥1 item; computes the net
    old→new stock delta per product and rejects insufficient stock *before* any
    mutation; recalculates every total server-side via `GSTService.calculate_gst`
    (same formulas as create); refuses to lower `grand_total` below the amount
    already received; applies stock deltas (sale/return) with `_record_movement`;
    rebuilds `InvoiceItem`s; updates customer purchase aggregates on
    customer/amount change; runs `_set_payment_state(inv, amount_paid)` to keep
    `amount_paid`/`balance_due`/`payment_status` consistent; commits and writes
    an `invoice_updated` audit log. `amount_paid` is never taken from the client.
  - `GET /invoices/<int:iid>/edit` now passes a JSON `invoice_data` payload so
    the form is prefilled (customer, dates, payment method, notes, items).
  - `billing/new_invoice.html`: edit-mode awareness — heading/status/button,
    prefilled fields and items, read-only `Amount Paid`, submit to the edit
    endpoint, "Invoice updated successfully!" toast, success redirect.
  - `invoice_history.html`: new `can_edit` (admin OR draft/pending/due) gates the
    Edit link; the stricter `editable` still governs Cancel/Delete.
- **Tests:** `tests/test_invoice_edit.py` (14 tests): totals recalc (5→3 units =
  590→354), stock delta (+2 return), product replacement (A restored, B
  deducted), payment preserved across edits + rejected when total < paid, empty
  items rejected, insufficient stock rejected, invoice number/id unchanged,
  customer aggregate corrected, audit log written, sales cannot touch paid
  invoices / others' invoices, sales still edits own drafts.

### Bonus fix — empty ledger crash

- The ledger helper `_customer_ledger_data` crashed with
  `'int' object has no attribute 'quantize'` when a customer had no entries in
  the filtered range (bare `sum(...)` returned `0`). Fixed at `app.py:2507` by
  seeding `Decimal('0')` in the `sum()` calls.

### Bug 3 — Sidebar scroll position resets on navigation

- **Root cause:** navigation is a plain full-page reload (no SPA/Turbo). The
  scroll container is `.sidebar-nav` (`.sidebar` itself is `overflow: hidden`;
  only the inner nav has `overflow-y: auto`). The existing handler in
  `static/js/app.js` saved on every `scroll` event and restored once at
  `DOMContentLoaded`, but it had no save-before-navigation path, no
  Back/Forward (BFCache) restore, no guard against a corrupt value, and it never
  cleared stale state — so after logging out/in on the same tab an old position
  could reappear.
- **Fix (`static/js/app.js`):**
  - Save the position three ways: throttled `scroll` listener (≈120 ms), a
    capture-phase click handler on sidebar `<a>` links that saves synchronously
    right before navigation, and a `pagehide` fallback that also covers refresh,
    Back/Forward and form submits (Logout).
  - Restore on `DOMContentLoaded` and again on `pageshow` (fires on BFCache
    restores where `DOMContentLoaded` does not re-fire), guarded with
    `Number.isFinite` and `pos > 0`.
  - Pages with no `.sidebar-nav` (login, error, print templates) remove the key,
    so a fresh login never restores a previous session's offset.
- **Cache-busting:** `templates/base.html` loads `js/app.js?v=2.0` so browsers
  pick up the new script (matches the existing `?v=` convention on other assets).
- **Tests:** `tests/test_sidebar_scroll.py` (3 tests). Scroll behavior itself is
  browser-side; final verification is the manual smoke below.

## 11. Verification performed

- Full pytest suite green (71/71).
- Boot check via `wsgi.application` with an admin session: dashboard (all ranges),
  customers, customer profile, ledger page + 3 export formats, products, invoices,
  quotations, purchase-orders, low-stock report + 3 exports, settings, reports,
  users — all `200`.
- Sidebar smoke check on the live app: `/reports` → only `Reports` active,
  `/reports/low-stock` → only `Low Stock` active, `/dashboard` → `Dashboard`.
- Edit smoke check on the live app: `GET /invoices/1/edit` renders the editor
  prefilled with the real invoice (`INV-14082026-001`, product `ertertertet`);
  `GET /invoices/create` still renders the New Invoice form (no regression).
- Development DB returned to pre-smoke state: smoke user, customer, product,
  test quotations/invoices/payments/notifications/movements/sequences and their
  audit trail removed (2 real invoices for `kaml` untouched). Bug-fix
  verification used only GET requests against the dev DB; the full edit flow was
  exercised exclusively against the disposable test database.
- Sidebar-scroll smoke (browser, manual): scroll the sidebar down → click
  Reports → Low Stock → Settings → Audit Logs (sidebar stays scrolled, only the
  clicked item is active) → refresh (position retained) → Back/Forward (no jump).
  Logging out then back in starts with the sidebar at the top.
