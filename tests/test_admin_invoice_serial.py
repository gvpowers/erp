"""Admin manual invoice serial number tests."""
import json
from datetime import date, timedelta

from conftest import db, Invoice, User, meta_csrf
import app as app_module
from app import peek_next_invoice_number

TARGET = date.today() + timedelta(days=140)
TARGET_STR = TARGET.isoformat()
TARGET_PREFIX = 'INV-' + TARGET.strftime('%d%m%Y') + '-'
TODAY_PREFIX = 'INV-' + date.today().strftime('%d%m%Y') + '-'
NEXT_NUMBER_URL = '/api/invoices/next-number'
CREATE_URL = '/invoices/create'


def _payload(customer, product, invoice_date, qty=1, price=100, invoice_serial=None):
    payload = {
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
    if invoice_serial is not None:
        payload['invoice_serial'] = invoice_serial
    return payload


def _csrf(client):
    return meta_csrf(client, CREATE_URL)


def _create(client, payload, expected=200):
    resp = client.post(CREATE_URL, json=payload,
                       headers={'X-CSRFToken': _csrf(client)})
    assert resp.status_code == expected, resp.get_data(as_text=True)
    return resp


def _invoice_from_response(resp):
    data = resp.get_json()
    assert data['success'] is True
    return db.session.get(Invoice, int(data['redirect'].rstrip('/').split('/')[-1]))


def _preview(client, d=TARGET, serial=None):
    params = {'date': d.isoformat()}
    if serial is not None:
        params['serial'] = serial
    return client.get(NEXT_NUMBER_URL, query_string=params)


def test_admin_manual_serial_pads_and_advances_auto(
        app, admin_login, make_customer, make_product):
    c = make_customer()
    p = make_product(stock=50)

    inv1 = _invoice_from_response(_create(
        admin_login, _payload(c, p, TARGET_STR, invoice_serial='1')))
    assert inv1.invoice_number == TARGET_PREFIX + '001'
    assert inv1.invoice_date == TARGET

    preview = _preview(admin_login)
    assert preview.status_code == 200
    assert preview.get_json()['invoice_number'] == TARGET_PREFIX + '002'
    assert preview.get_json()['serial'] == '002'

    inv2 = _invoice_from_response(_create(
        admin_login, _payload(c, p, TARGET_STR, invoice_serial='2')))
    assert inv2.invoice_number == TARGET_PREFIX + '002'
    assert _preview(admin_login).get_json()['invoice_number'] == TARGET_PREFIX + '003'
    assert Invoice.query.count() == 2


def test_serial_field_is_present_for_admin(app, admin_login):
    admin_body = admin_login.get(CREATE_URL).get_data(as_text=True)
    assert 'id="invoiceSerialInput"' in admin_body
    assert 'Invoice Serial Number' in admin_body
    assert 'inv-grid--4' in admin_body


def test_serial_field_is_absent_for_sales(app, sales_login):
    sales_body = sales_login.get(CREATE_URL).get_data(as_text=True)
    assert 'invoiceSerialInput' not in sales_body
    assert 'Invoice Serial Number' not in sales_body
    assert 'invoice_serial' not in sales_body


def test_preview_preserves_manual_serial_across_dates(app, admin_login):
    other = TARGET + timedelta(days=1)
    first = _preview(admin_login, TARGET, '5')
    assert first.status_code == 200
    assert first.get_json()['invoice_number'] == TARGET_PREFIX + '005'

    second = _preview(admin_login, other, '5')
    assert second.status_code == 200
    assert second.get_json()['invoice_number'] == (
        'INV-' + other.strftime('%d%m%Y') + '-005')


def test_duplicate_manual_serial_is_rejected_without_overwriting(
        app, admin_login, make_customer, make_product):
    c = make_customer()
    p = make_product(stock=50)
    first = _invoice_from_response(_create(
        admin_login, _payload(c, p, TARGET_STR, invoice_serial='5')))
    original_number = first.invoice_number
    count = Invoice.query.count()

    resp = _create(admin_login, _payload(c, p, TARGET_STR, invoice_serial='5'),
                   expected=400)
    data = resp.get_json()
    assert 'already exists' in data['error'].lower()
    assert data['invoice_number'] == original_number
    assert Invoice.query.count() == count
    assert db.session.get(Invoice, first.id).invoice_number == original_number

    preview = _preview(admin_login, TARGET, '5')
    assert preview.status_code == 409
    assert preview.get_json()['duplicate'] is True
    assert preview.get_json()['invoice_number'] == original_number


def test_invalid_manual_serial_is_rejected(
        app, admin_login, make_customer, make_product):
    c = make_customer()
    p = make_product(stock=50)
    before = peek_next_invoice_number(TARGET)

    for value in ['abc', '0', '1000', '1.5']:
        resp = _create(admin_login,
                       _payload(c, p, TARGET_STR, invoice_serial=value),
                       expected=400)
        assert 'serial' in resp.get_json()['error'].lower()
        assert Invoice.query.count() == 0
        assert peek_next_invoice_number(TARGET) == before

    for value in ['abc', '0', '1000']:
        assert _preview(admin_login, TARGET, value).status_code == 400


def test_manual_serial_never_recycles_or_decreases_sequence(
        app, admin_login, make_customer, make_product):
    c = make_customer()
    p = make_product(stock=50)

    first = _invoice_from_response(_create(
        admin_login, _payload(c, p, TARGET_STR, invoice_serial='10')))
    assert first.invoice_number == TARGET_PREFIX + '010'

    gap = _invoice_from_response(_create(
        admin_login, _payload(c, p, TARGET_STR, invoice_serial='5')))
    assert gap.invoice_number == TARGET_PREFIX + '005'

    assert _preview(admin_login).get_json()['invoice_number'] == TARGET_PREFIX + '011'
    auto = _invoice_from_response(_create(
        admin_login, _payload(c, p, TARGET_STR)))
    assert auto.invoice_number == TARGET_PREFIX + '011'


def test_sales_cannot_choose_serial_and_keeps_auto_numbering(
        app, sales_login, make_customer, make_product):
    c = make_customer()
    p = make_product(stock=50)

    resp = _create(sales_login,
                   _payload(c, p, TARGET_STR, invoice_serial='1'),
                   expected=403)
    assert 'admin' in resp.get_json()['error'].lower()
    assert Invoice.query.count() == 0

    assert sales_login.get(NEXT_NUMBER_URL,
                           query_string={'date': TARGET_STR, 'serial': '1'}).status_code == 403

    inv = _invoice_from_response(_create(
        sales_login, _payload(c, p, TARGET_STR)))
    assert inv.invoice_number.startswith(TODAY_PREFIX)
    assert not inv.invoice_number.startswith(TARGET_PREFIX)


def test_manual_serial_is_consistent_in_views_prints_pdfs_and_portal(
        app, admin_login, make_customer, make_product, monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, 'INVOICE_PORTAL_DATA_DIR', str(tmp_path))
    captured = {}

    def capture_email(inv, manifest):
        captured['invoice_number'] = inv.invoice_number
        captured['manifest'] = manifest

    monkeypatch.setattr(app_module, '_queue_invoice_customer_email', capture_email)

    c = make_customer()
    p = make_product(stock=50)
    inv = _invoice_from_response(_create(
        admin_login, _payload(c, p, TARGET_STR, invoice_serial='3')))
    number = inv.invoice_number
    assert number == TARGET_PREFIX + '003'

    assert number in admin_login.get('/invoices').get_data(as_text=True)
    assert number in admin_login.get(f'/invoices/{inv.id}').get_data(as_text=True)
    for copy_type in ['owner', 'customer', 'gst']:
        body = admin_login.get(f'/invoices/{inv.id}/print/{copy_type}').get_data(as_text=True)
        assert number in body
        pdf = admin_login.get(f'/invoices/{inv.id}/pdf/{copy_type}')
        assert pdf.status_code == 200
        assert number in pdf.headers.get('Content-Disposition', '')

    assert app_module._invoice_qr_data_uri(inv).startswith('data:image/png;base64,')

    manifest_path = tmp_path / f'{inv.public_token}.json'
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    assert manifest['invoice_number'] == number
    assert captured['invoice_number'] == number
    assert captured['manifest']['invoice_number'] == number


def test_admin_can_change_invoice_serial_on_edit(
        app, admin_login, make_customer, make_product):
    c = make_customer()
    p = make_product(stock=50)
    inv = _invoice_from_response(_create(
        admin_login, _payload(c, p, TARGET_STR, invoice_serial='4')))
    assert inv.invoice_number == TARGET_PREFIX + '004'

    body = admin_login.get(f'/invoices/{inv.id}/edit').get_data(as_text=True)
    assert 'invoiceSerialInput' in body
    assert 'Invoice Serial Number' in body
    assert 'value="004"' in body

    resp = admin_login.post(
        f'/invoices/{inv.id}/edit',
        json=_payload(c, p, TARGET_STR, invoice_serial='9'),
        headers={'X-CSRFToken': _csrf(admin_login)},
    )
    assert resp.get_json()['success'] is True
    inv = db.session.get(Invoice, inv.id)
    assert inv.invoice_number == TARGET_PREFIX + '009'
    assert TARGET_PREFIX + '009' in admin_login.get(f'/invoices/{inv.id}').get_data(as_text=True)


def test_admin_edit_serial_validates_duplicates_and_invalid_values(
        app, admin_login, make_customer, make_product):
    c = make_customer()
    p = make_product(stock=50)
    first = _invoice_from_response(_create(
        admin_login, _payload(c, p, TARGET_STR, invoice_serial='4')))
    second = _invoice_from_response(_create(
        admin_login, _payload(c, p, TARGET_STR, invoice_serial='5')))

    resp = admin_login.post(
        f'/invoices/{second.id}/edit',
        json=_payload(c, p, TARGET_STR, invoice_serial='4'),
        headers={'X-CSRFToken': _csrf(admin_login)},
    )
    assert resp.status_code == 400
    assert 'already exists' in resp.get_json()['error'].lower()
    assert db.session.get(Invoice, second.id).invoice_number == TARGET_PREFIX + '005'

    for value in ['abc', '0', '1000']:
        resp = admin_login.post(
            f'/invoices/{second.id}/edit',
            json=_payload(c, p, TARGET_STR, invoice_serial=value),
            headers={'X-CSRFToken': _csrf(admin_login)},
        )
        assert resp.status_code == 400
        assert 'serial' in resp.get_json()['error'].lower()
    assert db.session.get(Invoice, second.id).invoice_number == TARGET_PREFIX + '005'
    assert first.invoice_number == TARGET_PREFIX + '004'


def test_sales_cannot_change_serial_on_edit(app, sales_login, make_invoice):
    sales = User.query.filter_by(username='gvpowers@sales').one()
    inv = make_invoice(status='draft', created_by=sales.id)
    before = inv.invoice_number

    resp = sales_login.post(
        f'/invoices/{inv.id}/edit',
        json={
            'customer_name': inv.customer_name,
            'customer_state': 'Tamil Nadu',
            'customer_state_code': 33,
            'payment_method': 'cash',
            'invoice_date': inv.invoice_date.isoformat(),
            'invoice_serial': '9',
            'items': [{'product_name': 'Item A', 'qty': 1, 'price': 200,
                       'discount': 0, 'gst_rate': 18}],
        },
        headers={'X-CSRFToken': _csrf(sales_login)},
    )
    assert resp.status_code == 403
    assert 'admin' in resp.get_json()['error'].lower()
    assert db.session.get(Invoice, inv.id).invoice_number == before


def test_existing_invoices_remain_accessible(app, admin_login, make_invoice):
    inv = make_invoice()
    number = inv.invoice_number

    assert number in admin_login.get(f'/invoices/{inv.id}').get_data(as_text=True)
    assert number in admin_login.get('/invoices').get_data(as_text=True)
    for copy_type in ['owner', 'customer', 'gst']:
        assert number in admin_login.get(
            f'/invoices/{inv.id}/print/{copy_type}').get_data(as_text=True)
        pdf = admin_login.get(f'/invoices/{inv.id}/pdf/{copy_type}')
        assert pdf.status_code == 200
        assert number in pdf.headers.get('Content-Disposition', '')
