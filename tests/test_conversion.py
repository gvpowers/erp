from datetime import date, timedelta

from conftest import (
    db, Invoice, Product, Quotation, StockMovement, meta_csrf,
)


def _post(client, path, **data):
    return client.post(path, data=data, follow_redirects=True)


def _convert(client, qid, csrf):
    return _post(client, f'/quotations/{qid}/convert', csrf_token=csrf)


def test_convert_requires_accepted_status(app, admin_login, make_quotation):
    q = make_quotation(status='draft')
    csrf = meta_csrf(admin_login)
    resp = _convert(admin_login, q.id, csrf)
    assert resp.status_code == 200
    assert Invoice.query.count() == 0
    assert db.session.get(Quotation, q.id).status == 'draft'


def test_convert_creates_invoice_and_marks_converted(app, admin_login, make_quotation):
    q = make_quotation(status='accepted')
    csrf = meta_csrf(admin_login)
    resp = _convert(admin_login, q.id, csrf)
    assert resp.status_code == 200
    inv = Invoice.query.first()
    assert inv is not None
    assert inv.quotation_id == q.id
    assert inv.invoice_number.startswith('INV-')
    assert inv.status == 'completed'
    assert inv.payment_status == 'due'
    assert float(inv.amount_paid) == 0.0
    assert inv.balance_due == inv.grand_total
    assert db.session.get(Quotation, q.id).status == 'converted'
    assert len(db.session.get(Quotation, q.id).converted_invoices) == 1


def test_convert_deducts_stock_and_records_movement(app, admin_login, make_quotation, make_product):
    p = make_product(stock=50)
    q = make_quotation(status='accepted',
                       items=[{'product_id': p.id, 'name': p.name, 'qty': 2, 'price': 100, 'gst_rate': 18}])
    csrf = meta_csrf(admin_login)
    _convert(admin_login, q.id, csrf)
    p = db.session.get(Product, p.id)
    assert p.stock_quantity == 48
    mv = StockMovement.query.filter_by(product_id=p.id, movement_type='sale').first()
    assert mv is not None and mv.quantity == -2 and mv.reference_type == 'invoice'


def test_duplicate_conversion_blocked(app, admin_login, make_quotation):
    q = make_quotation(status='accepted')
    csrf = meta_csrf(admin_login)
    _convert(admin_login, q.id, csrf)
    assert Invoice.query.count() == 1
    _convert(admin_login, q.id, csrf)
    assert Invoice.query.count() == 1


def test_convert_insufficient_stock_blocked(app, admin_login, make_quotation, make_product):
    p = make_product(stock=1)
    q = make_quotation(status='accepted',
                       items=[{'product_id': p.id, 'name': p.name, 'qty': 5, 'price': 100, 'gst_rate': 18}])
    csrf = meta_csrf(admin_login)
    resp = _convert(admin_login, q.id, csrf)
    assert resp.status_code == 200
    assert 'Insufficient stock' in resp.get_data(as_text=True)
    assert Invoice.query.count() == 0
    assert db.session.get(Quotation, q.id).status == 'accepted'


def test_quotation_status_transitions(app, admin_login, make_quotation):
    q = make_quotation(status='draft')
    csrf = meta_csrf(admin_login)
    for new_status in ('sent', 'accepted', 'rejected'):
        resp = _post(admin_login, f'/quotations/{q.id}/status', status=new_status, csrf_token=csrf)
        assert resp.status_code == 200
        assert db.session.get(Quotation, q.id).status == new_status
    resp = _post(admin_login, f'/quotations/{q.id}/status', status='draft', csrf_token=csrf)
    assert db.session.get(Quotation, q.id).status == 'draft'


def test_invalid_status_value_rejected(app, admin_login, make_quotation):
    q = make_quotation(status='draft')
    csrf = meta_csrf(admin_login)
    resp = _post(admin_login, f'/quotations/{q.id}/status', status='hacked', csrf_token=csrf)
    assert resp.status_code == 200
    assert db.session.get(Quotation, q.id).status == 'draft'


def test_rejected_quotation_cannot_convert(app, admin_login, make_quotation):
    q = make_quotation(status='rejected')
    csrf = meta_csrf(admin_login)
    _convert(admin_login, q.id, csrf)
    assert Invoice.query.count() == 0


def test_overdue_quotation_auto_expires(app, admin_login, make_quotation):
    q = make_quotation(status='sent', valid_until=date.today() - timedelta(days=1))
    resp = admin_login.get('/quotations')
    assert resp.status_code == 200
    assert db.session.get(Quotation, q.id).status == 'expired'


def test_converted_quotation_status_route_blocked(app, admin_login, make_quotation):
    q = make_quotation(status='accepted')
    csrf = meta_csrf(admin_login)
    _convert(admin_login, q.id, csrf)
    resp = _post(admin_login, f'/quotations/{q.id}/status', status='draft', csrf_token=csrf)
    assert resp.status_code == 200
    assert db.session.get(Quotation, q.id).status == 'converted'
