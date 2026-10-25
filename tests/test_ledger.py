from datetime import date, timedelta
from decimal import Decimal

from conftest import (
    db, Invoice, Payment, meta_csrf,
)


def _setup_ledger(make_customer, make_invoice, payment_date=None):
    c = make_customer('Ledger Customer')
    inv_a = make_invoice(customer=c, invoice_date=date.today() - timedelta(days=10),
                         products=[{'name': 'A', 'qty': 1, 'price': 1000, 'gst_rate': 18}])
    inv_b = make_invoice(customer=c, invoice_date=date.today() - timedelta(days=2),
                         products=[{'name': 'B', 'qty': 1, 'price': 2000, 'gst_rate': 18}])
    db.session.add(Payment(invoice_id=inv_a.id, customer_id=c.id,
                           payment_date=payment_date or (date.today() - timedelta(days=1)),
                           amount=Decimal('300.00'), payment_method='upi', reference_number='REF-LED'))
    db.session.commit()
    return c, inv_a, inv_b


def test_ledger_page_lists_entries(app, admin_login, make_customer, make_invoice):
    c, _, _ = _setup_ledger(make_customer, make_invoice)
    resp = admin_login.get(f'/customers/{c.id}/ledger')
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert 'Opening Balance' in body and 'Closing Balance' in body
    assert 'Invoice' in body and 'Payment' in body


def test_ledger_json_api(app, admin_login, make_customer, make_invoice):
    c, inv_a, inv_b = _setup_ledger(make_customer, make_invoice)
    resp = admin_login.get(f'/api/v1/customers/{c.id}/ledger')
    js = resp.get_json()
    assert resp.status_code == 200 and js['success'] is True
    assert Decimal(js['opening']) == 0
    assert Decimal(js['total_debit']) == inv_a.grand_total + inv_b.grand_total
    assert Decimal(js['total_credit']) == Decimal('300.00')
    assert Decimal(js['closing']) == inv_a.grand_total + inv_b.grand_total - Decimal('300.00')
    types = {e['type'] for e in js['entries']}
    assert types == {'invoice', 'payment'}


def test_ledger_exports(app, admin_login, make_customer, make_invoice):
    c, _, _ = _setup_ledger(make_customer, make_invoice)
    for fmt, mime in [('csv', 'text/csv'), ('excel', 'spreadsheet'), ('pdf', 'application/pdf')]:
        resp = admin_login.get(f'/customers/{c.id}/ledger/export/{fmt}')
        assert resp.status_code == 200
        assert 'attachment' in (resp.headers.get('Content-Disposition') or '')


def test_ledger_opening_balance_for_range(app, admin_login, make_customer, make_invoice):
    c, inv_a, inv_b = _setup_ledger(make_customer, make_invoice)
    from_date = (date.today() - timedelta(days=5)).isoformat()
    resp = admin_login.get(f'/api/v1/customers/{c.id}/ledger?from={from_date}')
    js = resp.get_json()
    assert Decimal(js['opening']) == inv_a.grand_total
    assert Decimal(js['total_debit']) == inv_b.grand_total
    assert Decimal(js['closing']) == inv_a.grand_total + inv_b.grand_total - Decimal('300.00')


def test_ledger_excludes_cancelled_invoices(app, admin_login, make_customer, make_invoice):
    c, inv_a, inv_b = _setup_ledger(make_customer, make_invoice)
    inv_b.status = 'cancelled'
    db.session.commit()
    resp = admin_login.get(f'/api/v1/customers/{c.id}/ledger')
    js = resp.get_json()
    refs = {e['reference'] for e in js['entries']}
    assert inv_b.invoice_number not in refs
    assert Decimal(js['closing']) == inv_a.grand_total - Decimal('300.00')


def test_ledger_requires_login(app, client, make_customer, make_invoice):
    c, _, _ = _setup_ledger(make_customer, make_invoice)
    resp = client.get(f'/customers/{c.id}/ledger')
    assert resp.status_code == 302
    assert '/login' in resp.headers.get('Location', '')
