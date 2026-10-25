"""
GV Powers ERP - Invoice PDF Service (legacy compatibility shim).

The monolithic application (app.py) is now the single source of truth for
invoice PDF generation. This module only re-exports the canonical functions so
any legacy/backup entry points keep working unchanged.

It intentionally carries NO hardcoded company data: no PAN, no bank details and
no QR codes. Company identity always comes from the live application config
(current_app.config['COMPANY']).
"""


def generate_invoice_pdf(invoice, copy_type="customer", company=None):
    """Generate an invoice PDF for the given copy type (owner/customer/gst)."""
    from app import generate_invoice_pdf as _gen
    return _gen(invoice, copy_type, company)


def generate_owner_copy(invoice, company=None):
    from app import generate_owner_copy as _gen
    return _gen(invoice, company)


def generate_customer_copy(invoice, company=None):
    from app import generate_customer_copy as _gen
    return _gen(invoice, company)


def generate_gst_copy(invoice, company=None):
    from app import generate_gst_copy as _gen
    return _gen(invoice, company)


def amount_to_words(amount):
    from app import amount_to_words as _aw
    return _aw(amount)


# Kept for backwards compatibility. Prefer the live application config.
COMPANY = {}


__all__ = [
    "generate_invoice_pdf",
    "generate_owner_copy",
    "generate_customer_copy",
    "generate_gst_copy",
    "amount_to_words",
    "COMPANY",
]
