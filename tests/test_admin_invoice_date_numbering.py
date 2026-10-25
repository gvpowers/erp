"""Admin New Invoice: the invoice number follows the selected invoice date.

Covers the Admin-only preview endpoint, date-based sequence allocation,
sequences seeded from existing invoices, repeated previews not consuming
numbers, Sales keeping the existing today-based behaviour, and invalid-date
handling that leaves the form data intact.
"""
from datetime import date, timedelta

from conftest import db, Invoice, InvoiceSequence, User, meta_csrf
from app import peek_next_invoice_number

# A date that is guaranteed to differ from "today" so Sales' legacy behaviour
# (numbers always use today's date) can be distinguished from Admin's.
TARGET = date.today() + timedelta(days=120)
TARGET_STR = TARGET.isoformat()
TARGET_PREFIX = 'INV-' + TARGET.strftime('%d%m%Y') + '-'
TODAY_PREFIX = 'INV-' + date.today().strftime('%d%m%Y') + '-'
NEXT_NUMBER_URL = '/api/invoices/next-number'


def _payload(customer, product, invoice_date, qty=1, price=100):
    return {
        'customer_id': customer.id,
        'customer_name': customer.name,
        'customer_mobile': customer.mobile,
        'customer_state': customer.state,
        'customer_state_code': customer.state_code,
        'customer_gstin': customer.gstin,
        'payment_method': 'cash',
        'amount_paid': 0,
        'invoice_date': invoice_date,
        'due_date': '',
        'items': [{
            'product_id': product.id, 'product_name': product.name, 'hsn': '8504',
            'qty': qty, 'unit': 'pcs', 'price': price, 'discount': 0, 'gst_rate': 18,
        }],
    }


def _preview(client, d=TARGET):
    resp = client.get(NEXT_NUMBER_URL, query_string={'date': d.isoformat()})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data['success'] is True
    return data['invoice_number']


def _create(client, payload):
    resp = client.post('/invoices/create', json=payload,
                       headers={'X-CSRFToken': meta_csrf(client, '/invoices/create')})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data['success'] is True
    return db.session.get(Invoice, int(data['redirect'].rstrip('/').split('/')[-1]))


def test_admin_preview_uses_selected_date_without_consuming(app, admin_login):
    for _ in range(5):
        assert _preview(admin_login) == TARGET_PREFIX + '001'
    assert InvoiceSequence.query.filter_by(seq_key=TARGET_PREFIX).first() is None
    assert Invoice.query.count() == 0


def test_admin_saves_date_based_number_consistent_across_views(
        app, admin_login, make_customer, make_product):
    c = make_customer()
    p = make_product(stock=50)
    preview = _preview(admin_login)

    inv = _create(admin_login, _payload(c, p, TARGET_STR))
    assert inv.invoice_number == preview
    assert inv.invoice_number == TARGET_PREFIX + '001'
    assert inv.invoice_date == TARGET

    # Preview after saving shows the next number for the same date.
    assert _preview(admin_login) == TARGET_PREFIX + '002'

    # The saved number is what preview/history/print/PDF all use.
    body = admin_login.get('/invoices/%d' % inv.id).get_data(as_text=True)
    assert inv.invoice_number in body
    body = admin_login.get('/invoices').get_data(as_text=True)
    assert inv.invoice_number in body
    body = admin_login.get('/invoices/%d/print/owner' % inv.id).get_data(as_text=True)
    assert inv.invoice_number in body
    pdf = admin_login.get('/invoices/%d/pdf/owner' % inv.id)
    assert pdf.status_code == 200
    assert inv.invoice_number in pdf.headers.get('Content-Disposition', '')

    second = _create(admin_login, _payload(c, p, TARGET_STR, qty=2))
    assert second.invoice_number == TARGET_PREFIX + '002'
    assert {inv.invoice_number, second.invoice_number} == {
        TARGET_PREFIX + '001', TARGET_PREFIX + '002'}
    assert Invoice.query.count() == 2


def test_existing_invoices_for_date_seed_the_sequence(
        app, admin_login, sales_login, make_customer, make_product):
    # Simulate an already-issued invoice for the selected date (e.g. created by
    # Sales in another session). It must be counted even without a sequence row.
    sales = User.query.filter_by(username='gvpowers@sales').one()
    db.session.add(Invoice(invoice_number=TARGET_PREFIX + '007',
                           customer_name='Existing Sale', invoice_date=TARGET,
                           created_by=sales.id))
    db.session.commit()

    assert _preview(admin_login) == TARGET_PREFIX + '008'
    c = make_customer()
    p = make_product(stock=50)
    inv = _create(admin_login, _payload(c, p, TARGET_STR))
    assert inv.invoice_number == TARGET_PREFIX + '008'


def test_repeated_date_changes_do_not_consume_numbers(
        app, admin_login, make_customer, make_product):
    other = date.today() + timedelta(days=121)
    for _ in range(4):
        _preview(admin_login, TARGET)
        _preview(admin_login, other)
    assert InvoiceSequence.query.filter_by(seq_key=TARGET_PREFIX).first() is None
    assert InvoiceSequence.query.filter_by(
        seq_key='INV-' + other.strftime('%d%m%Y') + '-').first() is None

    c = make_customer()
    p = make_product(stock=50)
    inv = _create(admin_login, _payload(c, p, TARGET_STR))
    assert inv.invoice_number == TARGET_PREFIX + '001'


def test_sales_gets_403_from_preview_and_keeps_existing_behaviour(
        app, sales_login, make_customer, make_product):
    resp = sales_login.get(NEXT_NUMBER_URL, query_string={'date': TARGET_STR})
    assert resp.status_code == 403
    assert resp.get_json()['success'] is False

    c = make_customer()
    p = make_product(stock=50)
    inv = _create(sales_login, _payload(c, p, TARGET_STR))
    assert inv.invoice_date == TARGET
    # Sales' invoice numbering is unchanged: it still uses today's date.
    assert inv.invoice_number.startswith(TODAY_PREFIX)
    assert not inv.invoice_number.startswith(TARGET_PREFIX)


def test_invalid_date_is_rejected_without_consuming_number(
        app, admin_login, make_customer, make_product):
    before = _preview(admin_login)

    resp = admin_login.get(NEXT_NUMBER_URL, query_string={'date': 'not-a-date'})
    assert resp.status_code == 400
    assert resp.get_json()['success'] is False

    resp = admin_login.get(NEXT_NUMBER_URL)
    assert resp.status_code == 400

    c = make_customer()
    p = make_product(stock=50)
    resp = admin_login.post('/invoices/create',
                            json=_payload(c, p, 'not-a-date'),
                            headers={'X-CSRFToken': meta_csrf(admin_login, '/invoices/create')})
    assert resp.status_code == 400
    assert resp.get_json()['success'] is False
    assert Invoice.query.count() == 0
    assert _preview(admin_login) == before
    assert peek_next_invoice_number(TARGET) == before


def test_auto_update_script_is_present_for_admin(app, admin_login):
    admin_body = admin_login.get('/invoices/create').get_data(as_text=True)
    assert 'invoiceNumberInput' in admin_body
    assert 'refreshInvoiceNumber' in admin_body
    assert NEXT_NUMBER_URL in admin_body


def test_auto_update_script_is_absent_for_sales(app, sales_login):
    sales_body = sales_login.get('/invoices/create').get_data(as_text=True)
    assert 'invoiceNumberInput' in sales_body  # shared layout field
    assert 'refreshInvoiceNumber' not in sales_body
    assert NEXT_NUMBER_URL not in sales_body
