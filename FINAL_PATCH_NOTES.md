# GV POWERS ERP — Final Safe Patch

This package preserves the existing project contents and adds only the final requested safeguards.

## Preserved requirements

- Admin username: `gvpowers@admin`
- Admin password default in application code: `admin@gvpowerssalem`
- Optional E-Way Bill number on New Invoice for Admin/Sales
- E-Way Bill number directly below Invoice No. in the canonical invoice
- Small QR directly below the TAX INVOICE / copy label
- QR URL format: `https://invoice.gvpowers.in/<random-token>`
- Separate invoice portal using the existing file-based integration
- Official GV POWERS Invoice Portal wording
- Admin / Owner, Customer and GST Tax copies use the canonical invoice

## Final additive change

An additive print CSS override was appended to `static/css/invoice.css` so Chrome does not push the tiny `This is a computer-generated invoice.` footer onto a separate page when the signature block still fits on page 1.

The existing signature block remains protected from splitting. No invoice font sizes, invoice structure, QR placement, E-Way Bill placement, or existing application modules were removed.

## Verification

Run without needing Flask dependencies:

```bash
python scripts/verify_final_invoice_requirements.py
```

Then, after installing the normal ERP requirements, run the existing test suite:

```bash
python -m pytest -q
```

For an existing production PostgreSQL database, run the existing one-time Admin migration after deployment:

```bash
export ADMIN_USERNAME='gvpowers@admin'
export ADMIN_PASSWORD='admin@gvpowerssalem'
python scripts/set_admin_credentials.py
```
