# GV POWERS Invoice Portal + E-Way Bill / QR Update

## What changed

1. New Invoice (Admin + Sales) has an optional **E-Way Bill No.** card between Payment and Actions.
2. E-Way Bill No. is stored on the invoice.
3. Canonical invoice shows E-Way Bill No. directly below Invoice No. inside Invoice Details.
4. Every invoice gets a cryptographically random public token.
5. A small QR is generated automatically and placed below **TAX INVOICE** and the copy label in all three canonical copies.
6. QR URL format is exactly `https://invoice.gvpowers.in/<random-token>`.
7. ERP publishes the customer-copy PDF + JSON manifest to a shared folder. No public request accesses the ERP database.
8. `invoice_portal/` is a separate Flask customer-facing app for `invoice.gvpowers.in`.

## No ERP-to-portal API

This implementation uses a shared filesystem, not an API. The ERP writes files into `INVOICE_PORTAL_DATA_DIR`; the invoice portal only reads those files. This assumes both services run on the same Ubuntu server or on a shared mounted filesystem.

## Production setup

Example shared directory:

```bash
sudo mkdir -p /opt/gvpowers-invoice/data
sudo chown -R kaml:kaml /opt/gvpowers-invoice
```

ERP environment:

```env
INVOICE_PORTAL_BASE_URL=https://invoice.gvpowers.in
INVOICE_PORTAL_DATA_DIR=/opt/gvpowers-invoice/data
```

Invoice portal environment:

```env
INVOICE_PORTAL_DATA_DIR=/opt/gvpowers-invoice/data
PORT=5012
```

The portal service example is `invoice_portal/gvpowers-invoice.service`.

Cloudflare Tunnel should route:

```text
invoice.gvpowers.in -> http://127.0.0.1:5012
```

## Customer flow

```text
ERP -> create invoice -> random token -> QR -> invoice.gvpowers.in/<token>
                                            -> View Invoice
                                            -> Download Invoice
```

The QR is a **GV POWERS private invoice-access QR**. It is not the digitally signed GST/IRP e-invoice QR. If an official GST e-invoice QR is required for a transaction, that remains a separate GST/IRP process.
