"""Regression tests: invoice numbers must only be consumed on successful save.

Covers: opening/refreshing the New Invoice page, validation failures, save
rollback, quotation-conversion rollback, form submissions, and PDF copies all
sharing the one saved invoice number.
"""
import re
from datetime import date

from conftest import db, Invoice, meta_csrf
import app as app_module
from app import peek_next_invoice_number, generate_invoice_number


def _payload(customer, product, qty=1, price=100, amount_paid=0):
    return {
        'customer_id': customer.id,
        'customer_name': customer.name,
        'customer_mobile': customer.mobile,
        'customer_state': customer.state,
        'customer_state_code': customer.state_code,
        'customer_gstin': customer.gstin,
        'payment_method': 'cash',
        'amount_paid': amount_paid,
        'invoice_date': date.today().isoformat(),
        'due_date': '',
        'items': [{
            'product_id': product.id, 'product_name': product.name, 'hsn': '8504',
            'qty': qty, 'unit': 'pcs', 'price': price, 'discount': 0, 'gst_rate': 18,
        }],
    }


def _preview_number(client):
    resp = client.get('/invoices/create')
    assert resp.status_code == 200
    m = re.search(r'id="invoiceNumber">([^<]+)</span>', resp.get_data(as_text=True))
    assert m, 'invoice number preview missing on the page'
    return m.group(1)


def _next_of(num):
    return '%s%03d' % (num[:-3], int(num[-3:]) + 1)


def test_peek_matches_next_allocated_number(app):
    assert peek_next_invoice_number() == generate_invoice_number()


def test_new_invoice_page_does_not_reserve_number(app, admin_login, make_customer, make_product):
    c = make_customer()
    p = make_product(stock=50)
    previews = {_preview_number(admin_login) for _ in range(5)}
    assert len(previews) == 1, f'opening the form advanced the number: {previews}'
    expected = next(iter(previews))
    assert peek_next_invoice_number() == expected

    resp = admin_login.post('/invoices/create', json=_payload(c, p),
                            headers={'X-CSRFToken': meta_csrf(admin_login)})
    assert resp.status_code == 200
    inv = Invoice.query.order_by(Invoice.id.desc()).first()
    assert inv.invoice_number == expected
    # Form now previews the NEXT number, still without consuming it.
    assert _preview_number(admin_login) == _next_of(expected)


def test_validation_failure_does_not_consume_number(app, admin_login, make_customer, make_product):
    c = make_customer()
    p = make_product(stock=1)
    before = peek_next_invoice_number()
    resp = admin_login.post('/invoices/create', json=_payload(c, p, qty=5),
                            headers={'X-CSRFToken': meta_csrf(admin_login)})
    assert resp.status_code == 400
    assert Invoice.query.count() == 0
    assert peek_next_invoice_number() == before
    assert generate_invoice_number() == before


def test_failed_save_rolls_back_invoice_number(app, admin_login, monkeypatch, make_customer, make_product):
    c = make_customer()
    p = make_product(stock=50)
    before = peek_next_invoice_number()

    def boom(data):
        raise RuntimeError('boom')

    monkeypatch.setattr(app_module, '_resolve_customer', boom)
    resp = admin_login.post('/invoices/create', json=_payload(c, p),
                            headers={'X-CSRFToken': meta_csrf(admin_login)})
    assert resp.status_code == 400
    assert Invoice.query.count() == 0
    monkeypatch.undo()
    # The failed save must not have consumed the number.
    assert peek_next_invoice_number() == before
    assert generate_invoice_number() == before


def test_form_post_creates_completed_invoice(app, admin_login, make_customer, make_product):
    c = make_customer()
    p = make_product(stock=50)
    resp = admin_login.post('/invoices/create', data={
        'customer_id': c.id,
        'customer_name': c.name,
        'customer_mobile': c.mobile,
        'customer_state': c.state,
        'customer_state_code': c.state_code,
        'customer_gstin': c.gstin,
        'payment_method': 'cash',
        'amount_paid': '0',
        'invoice_date': date.today().isoformat(),
        'due_date': '',
        'product_name[]': [p.name],
        'product_id[]': [p.id],
        'qty[]': [1],
        'rate[]': ['100'],
        'discount[]': ['0'],
        'gst_rate[]': ['18'],
        'hsn[]': ['8504'],
        'csrf_token': meta_csrf(admin_login),
    }, follow_redirects=True)
    assert resp.status_code == 200
    inv = Invoice.query.order_by(Invoice.id.desc()).first()
    assert inv is not None and inv.status == 'completed'
    assert inv.invoice_number.startswith('INV-')


def test_quotation_conversion_failure_does_not_consume_number(app, admin_login, monkeypatch,
                                                              make_quotation, make_product):
    p = make_product(stock=50)
    q = make_quotation(status='accepted',
                       items=[{'product_id': p.id, 'name': p.name, 'qty': 1, 'price': 100, 'gst_rate': 18}])
    before = peek_next_invoice_number()

    def boom(*a, **k):
        raise RuntimeError('boom')

    monkeypatch.setattr(app_module, '_record_movement', boom)
    resp = admin_login.post(f'/quotations/{q.id}/convert',
                            data={'csrf_token': meta_csrf(admin_login)},
                            follow_redirects=True)
    assert resp.status_code == 200
    assert Invoice.query.count() == 0
    monkeypatch.undo()
    assert peek_next_invoice_number() == before


def test_pdf_copies_share_saved_invoice_number(app, admin_login, make_invoice):
    inv = make_invoice()
    count = Invoice.query.count()
    for ct in ['owner', 'customer', 'gst']:
        resp = admin_login.get(f'/invoices/{inv.id}/pdf/{ct}')
        assert resp.status_code == 200
        assert inv.invoice_number in resp.headers.get('Content-Disposition', '')
    assert Invoice.query.count() == count
