"""Dependency-free source verification for the final GV POWERS invoice package.

This script does not import Flask, touch the database, or modify any files.
It checks the source package for the agreed fixed requirements before deployment.
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
CONFIG = (ROOT / "config.py").read_text(encoding="utf-8")
INVOICE = (ROOT / "templates/invoices/standard_invoice.html").read_text(encoding="utf-8")
NEW_INVOICE = (ROOT / "templates/billing/new_invoice.html").read_text(encoding="utf-8")
CSS = (ROOT / "static/css/invoice.css").read_text(encoding="utf-8")
PORTAL = (ROOT / "invoice_portal/templates/invoice.html").read_text(encoding="utf-8")

checks = [
    ("Admin username in app defaults", 'os.getenv("ADMIN_USERNAME", "gvpowers@admin")' in APP),
    ("Admin password in app defaults", 'os.getenv("ADMIN_PASSWORD", "admin@gvpowerssalem")' in APP),
    ("Admin username in config defaults", 'os.getenv("ADMIN_USERNAME", "gvpowers@admin")' in CONFIG),
    ("Admin password in config defaults", 'os.getenv("ADMIN_PASSWORD", "admin@gvpowerssalem")' in CONFIG),
    ("E-Way Bill model field", "eway_bill_number = db.Column" in APP),
    ("E-Way Bill saved on create", "data.get('eway_bill_number')" in APP),
    ("E-Way Bill shown below Invoice No.", bool(re.search(r"Invoice No\..*?\{\% if invoice\.eway_bill_number \%\}.*?E-Way Bill No\.", INVOICE, re.S))),
    ("E-Way Bill input exists", 'id="ewayBillNumber"' in NEW_INVOICE),
    ("QR uses invoice portal URL", "INVOICE_PORTAL_BASE_URL" in APP and "invoice.gvpowers.in" in APP),
    ("QR is generated from public URL", "qr.add_data(url)" in APP),
    ("Official invoice portal wording", "Officially Generated GV POWERS Invoice" in PORTAL),
    ("Print A4 declaration", "size: A4 portrait" in CSS),
    ("Print footer safety override", ".gvp-bottom" in CSS and "page-break-inside: auto" in CSS),
]

failed = [name for name, ok in checks if not ok]
for name, ok in checks:
    print(f"[{'OK' if ok else 'FAIL'}] {name}")

if failed:
    print("\nFAILED CHECKS:")
    for name in failed:
        print(f" - {name}")
    sys.exit(1)

print("\nAll final invoice/E-Way Bill/QR/admin source checks passed.")
print("Admin defaults: gvpowers@admin / admin@gvpowerssalem")
print("Invoice portal: https://invoice.gvpowers.in/<random-token>")
