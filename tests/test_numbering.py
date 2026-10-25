import re
from datetime import date

from conftest import (
    db, Invoice, Quotation, PurchaseOrder, InvoiceSequence,
    generate_invoice_number, generate_quotation_number,
    generate_purchase_order_number,
)


INV_RE = re.compile(r'^INV-\d{8}-\d{3}$')
QTN_RE = re.compile(r'^QTN-\d{8}-\d{3}$')
PO_RE = re.compile(r'^PO-\d{8}-\d{3}$')


def test_invoice_number_format(app):
    num = generate_invoice_number()
    assert INV_RE.match(num)


def test_quotation_number_format(app):
    num = generate_quotation_number()
    assert QTN_RE.match(num)


def test_purchase_order_number_format(app):
    num = generate_purchase_order_number()
    assert PO_RE.match(num)


def test_invoice_number_uses_today(app):
    num = generate_invoice_number()
    assert num == 'INV-%s-001' % date.today().strftime('%d%m%Y')


def test_sequential_numbers_within_day(app):
    first = generate_invoice_number()
    second = generate_invoice_number()
    assert first.endswith('-001') and second.endswith('-002')
    assert first != second


def test_gap_never_recycled(app):
    a = generate_invoice_number()
    b = generate_invoice_number()
    c = generate_invoice_number()
    nums = {a, b, c}
    assert len(nums) == 3
    seq = InvoiceSequence.query.filter_by(
        seq_key='INV-%s-' % date.today().strftime('%d%m%Y')).first()
    assert seq is not None and seq.last_value >= 3
    nxt = generate_invoice_number()
    assert nxt.endswith('-004')
    assert nxt not in nums


def test_legacy_numbers_seed_sequence(app):
    num = generate_invoice_number(dt=date(2025, 1, 10))
    assert num == 'INV-10012025-001'
    legacy = db.session.get(Invoice, 0)
    assert legacy is None
    num2 = generate_invoice_number(dt=date(2025, 1, 10))
    assert num2 == 'INV-10012025-002'


def test_manual_legacy_row_seeds_higher(app):
    old = 'INV-%s-042' % date.today().strftime('%d%m%Y')
    db.session.add(Invoice(invoice_number=old, customer_name='Legacy', invoice_date=date.today()))
    db.session.commit()
    num = generate_invoice_number()
    assert num == 'INV-%s-043' % date.today().strftime('%d%m%Y')


def test_concurrent_invoice_numbers_all_unique(app, concurrent_numbers):
    results = concurrent_numbers(10)
    assert len(results) == 10
    assert len(set(results)) == 10
    assert all(INV_RE.match(n) for n in results)
    day = date.today().strftime('%d%m%Y')
    seq_nums = sorted(int(n.split('-')[-1]) for n in results if n.startswith('INV-%s-' % day))
    assert seq_nums == list(range(1, 11))
