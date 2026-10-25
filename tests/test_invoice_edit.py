from datetime import date
from decimal import Decimal

import pytest

from conftest import (
    db, User, Invoice, InvoiceItem, Product, Customer,
    StockMovement, Payment, meta_csrf,
)
from app import AuditLog


def _csrf(client):
    return meta_csrf(client, '/dashboard')


def _payload(customer, product, qty=5, price=100, gst_rate=18, amount_paid=0,
             customer_id=None, due_date=None):
    return {
        'customer_id': customer_id if customer_id is not None else customer.id,
        'customer_name': customer.name,
        'customer_mobile': customer.mobile,
        'customer_state': customer.state,
        'customer_state_code': customer.state_code,
        'customer_gstin': customer.gstin,
        'payment_method': 'cash',
        'amount_paid': amount_paid,
        'invoice_date': date.today().isoformat(),
        'due_date': due_date or '',
        'items': [{
            'product_id': product.id, 'product_name': product.name, 'hsn': '8504',
            'qty': qty, 'unit': 'pcs', 'price': price, 'discount': 0, 'gst_rate': gst_rate,
        }],
    }


def _create(client, csrf, payload):
    resp = client.post('/invoices/create', json=payload,
                       headers={'X-CSRFToken': csrf})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data['success'] is True
    return db.session.get(Invoice, data['redirect'].rstrip('/').split('/')[-1])


def _edit(client, iid, csrf, payload):
    return client.post(f'/invoices/{iid}/edit', json=payload,
                       headers={'X-CSRFToken': csrf})


def _movements(product_id):
    return [(m.movement_type, m.quantity, m.reference_type)
            for m in StockMovement.query.filter_by(product_id=product_id)
                        .order_by(StockMovement.id).all()]


def test_admin_can_edit_completed_invoice(app, admin_login, make_customer, make_product):
    """Bug fix: admins must be able to edit finalized (completed) invoices."""
    c = make_customer()
    p = make_product(stock=50)
    csrf = _csrf(admin_login)
    inv = _create(admin_login, csrf, _payload(c, p, qty=5))
    assert inv.status == 'completed'
    assert inv.grand_total == Decimal('590')

    resp = admin_login.get(f'/invoices/{inv.id}/edit')
    assert resp.status_code == 200
    assert 'Edit Invoice' in resp.get_data(as_text=True)

    r = _edit(admin_login, inv.id, csrf, _payload(c, p, qty=3))
    assert r.status_code == 200
    assert r.get_json()['success'] is True

    inv = db.session.get(Invoice, inv.id)
    assert inv.grand_total == Decimal('354')
    assert inv.status == 'completed'


def test_edit_recalculates_totals_and_updates_stock(app, admin_login, make_customer, make_product):
    c = make_customer()
    p = make_product(stock=50)
    csrf = _csrf(admin_login)
    inv = _create(admin_login, csrf, _payload(c, p, qty=5))

    assert db.session.get(Product, p.id).stock_quantity == 45
    assert _movements(p.id) == [('sale', -5, 'invoice')]

    r = _edit(admin_login, inv.id, csrf, _payload(c, p, qty=3))
    assert r.status_code == 200
    assert r.get_json()['success'] is True

    inv = db.session.get(Invoice, inv.id)
    assert inv.grand_total == Decimal('354')
    assert inv.subtotal == Decimal('300')
    assert inv.total_taxable == Decimal('300')
    assert inv.amount_paid == Decimal('0')
    assert inv.balance_due == Decimal('354')
    assert inv.payment_status == 'due'
    assert db.session.get(Product, p.id).stock_quantity == 47
    assert _movements(p.id) == [('sale', -5, 'invoice'), ('return', 2, 'invoice')]


def test_edit_product_replacement_restores_and_deducts_stock(app, admin_login, make_customer, make_product):
    c = make_customer()
    a = make_product(name='Product A', stock=50)
    b = make_product(name='Product B', stock=20)
    csrf = _csrf(admin_login)
    inv = _create(admin_login, csrf, _payload(c, a, qty=2))

    payload = _payload(c, b, qty=3)
    payload['items'][0]['product_id'] = b.id
    payload['items'][0]['product_name'] = b.name
    r = _edit(admin_login, inv.id, csrf, payload)
    assert r.status_code == 200
    assert r.get_json()['success'] is True

    assert db.session.get(Product, a.id).stock_quantity == 50
    assert db.session.get(Product, b.id).stock_quantity == 17
    inv = db.session.get(Invoice, inv.id)
    items = InvoiceItem.query.filter_by(invoice_id=inv.id).all()
    assert len(items) == 1
    assert items[0].product_id == b.id
    assert items[0].qty == 3
    assert _movements(a.id) == [('sale', -2, 'invoice'), ('return', 2, 'invoice')]
    assert _movements(b.id) == [('sale', -3, 'invoice')]


def test_edit_preserves_existing_payments(app, admin_login, make_customer, make_product):
    c = make_customer()
    p = make_product(stock=50)
    csrf = _csrf(admin_login)
    inv = _create(admin_login, csrf, _payload(c, p, qty=10, price=3000, amount_paid=20000))
    assert inv.grand_total == Decimal('35400')
    assert inv.payment_status == 'partial'

    # Attempting to lower the total below the amount already received must be rejected.
    r = _edit(admin_login, inv.id, csrf, _payload(c, p, qty=1, price=1000, amount_paid=20000))
    assert r.status_code == 400
    err = r.get_json()['error']
    assert 'less than the amount already received' in err
    inv = db.session.get(Invoice, inv.id)
    assert inv.grand_total == Decimal('35400')
    assert inv.amount_paid == Decimal('20000')

    # Successful edit keeps amount_paid (and ignores any client-supplied amount_paid).
    r = _edit(admin_login, inv.id, csrf, _payload(c, p, qty=10, price=2500, amount_paid=0))
    assert r.status_code == 200
    assert r.get_json()['success'] is True
    inv = db.session.get(Invoice, inv.id)
    assert inv.grand_total == Decimal('29500')
    assert inv.amount_paid == Decimal('20000')
    assert inv.balance_due == Decimal('9500')
    assert inv.payment_status == 'partial'


def test_edit_rejects_no_items(app, admin_login, make_customer, make_product):
    c = make_customer()
    p = make_product(stock=50)
    csrf = _csrf(admin_login)
    inv = _create(admin_login, csrf, _payload(c, p, qty=2))

    payload = _payload(c, p, qty=2)
    payload['items'] = []
    r = _edit(admin_login, inv.id, csrf, payload)
    assert r.status_code == 400
    assert 'at least one item' in r.get_json()['error']
    assert db.session.get(Invoice, inv.id).grand_total == Decimal('236')


def test_edit_blocks_insufficient_stock(app, admin_login, make_customer, make_product):
    c = make_customer()
    p = make_product(stock=50)
    csrf = _csrf(admin_login)
    inv = _create(admin_login, csrf, _payload(c, p, qty=5))
    assert db.session.get(Product, p.id).stock_quantity == 45

    r = _edit(admin_login, inv.id, csrf, _payload(c, p, qty=100))
    assert r.status_code == 400
    assert 'insufficient stock' in r.get_json()['error']
    assert db.session.get(Product, p.id).stock_quantity == 45
    assert db.session.get(Invoice, inv.id).grand_total == Decimal('590')


def test_edit_invoice_number_unchanged(app, admin_login, make_customer, make_product):
    c = make_customer()
    p = make_product(stock=50)
    csrf = _csrf(admin_login)
    inv = _create(admin_login, csrf, _payload(c, p, qty=5))
    num = inv.invoice_number
    iid = inv.id

    r = _edit(admin_login, iid, csrf, _payload(c, p, qty=4))
    assert r.get_json()['success'] is True
    inv = db.session.get(Invoice, iid)
    assert inv.id == iid
    assert inv.invoice_number == num
    assert Invoice.query.count() == 1


def test_edit_updates_customer_purchase_aggregate(app, admin_login, make_customer, make_product):
    c = make_customer()
    p = make_product(stock=50)
    csrf = _csrf(admin_login)
    inv = _create(admin_login, csrf, _payload(c, p, qty=5))
    assert db.session.get(Customer, c.id).total_purchases == Decimal('590')

    r = _edit(admin_login, inv.id, csrf, _payload(c, p, qty=3))
    assert r.get_json()['success'] is True
    assert db.session.get(Customer, c.id).total_purchases == Decimal('354')


def test_edit_logs_audit_trail(app, admin_login, make_customer, make_product):
    c = make_customer()
    p = make_product(stock=50)
    csrf = _csrf(admin_login)
    inv = _create(admin_login, csrf, _payload(c, p, qty=5))

    _edit(admin_login, inv.id, csrf, _payload(c, p, qty=2))
    entry = AuditLog.query.filter_by(action='invoice_updated', entity_id=inv.id).first()
    assert entry is not None
    assert 'invoice_updated' in entry.action
    assert '590' in (entry.details or '')
    assert '236' in (entry.details or '')


def test_sales_cannot_edit_others_completed_invoice(app, sales_login, make_invoice):
    admin = User.query.filter_by(username='gvpowers@admin').one()
    inv = make_invoice(status='completed')
    inv.created_by = admin.id
    db.session.commit()

    resp = sales_login.get(f'/invoices/{inv.id}/edit')
    assert resp.status_code == 403
    r = _edit(sales_login, inv.id, _csrf(sales_login), {})
    assert r.status_code == 403
    assert r.get_json()['success'] is False


def test_sales_cannot_edit_own_completed_invoice(app, sales_login, make_invoice):
    sales = User.query.filter_by(username='gvpowers@sales').one()
    inv = make_invoice(status='completed')
    inv.created_by = sales.id
    inv.payment_status = 'paid'
    inv.amount_paid = inv.grand_total
    inv.balance_due = Decimal('0')
    db.session.commit()

    resp = sales_login.get(f'/invoices/{inv.id}/edit')
    assert resp.status_code == 302
    assert f'/invoices/{inv.id}' in resp.headers['Location']
    r = _edit(sales_login, inv.id, _csrf(sales_login), {})
    assert r.status_code == 400
    assert 'finalized' in r.get_json()['error']


def test_sales_can_edit_own_draft_invoice(app, sales_login, make_invoice):
    sales = User.query.filter_by(username='gvpowers@sales').one()
    inv = make_invoice(status='draft')
    inv.created_by = sales.id
    db.session.commit()

    payload = {
        'customer_name': inv.customer_name,
        'customer_state': 'Tamil Nadu',
        'customer_state_code': 33,
        'payment_method': 'cash',
        'invoice_date': inv.invoice_date.isoformat(),
        'items': [{'product_name': 'Item A', 'qty': 3, 'price': 200, 'discount': 0, 'gst_rate': 18}],
    }
    r = _edit(sales_login, inv.id, _csrf(sales_login), payload)
    assert r.status_code == 200
    assert r.get_json()['success'] is True
    assert db.session.get(Invoice, inv.id).grand_total == Decimal('708')


def test_sales_edit_preserves_other_users_edit_block(app, sales_login, make_invoice):
    """A draft owned by another sales user stays off-limits to this sales user."""
    other = User.query.filter_by(username='gvpowers@admin').one()
    inv = make_invoice(status='draft')
    inv.created_by = other.id
    db.session.commit()

    resp = sales_login.get(f'/invoices/{inv.id}/edit')
    assert resp.status_code == 403
