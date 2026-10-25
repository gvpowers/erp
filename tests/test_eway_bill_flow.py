"""E-Way Bill number must survive the whole pipeline: form payload -> route ->
model/DB -> canonical invoice template -> preview / print / PDF / all copies."""
import re

import pytest


def _post_create(client, eway):
    """POST to the real /invoices/create route exactly as the New Invoice form does."""
    token = re.search(r'name="csrf-token" content="([^"]+)"',
                      client.get('/invoices/create').get_data(as_text=True)).group(1)
    payload = {
        'customer_id': None,
        'customer_name': 'test customer',
        'customer_mobile': '9876543210',
        'customer_email': '',
        'customer_address': 'Test Address',
        'customer_state': 'Tamil Nadu',
        'customer_state_code': 33,
        'customer_gstin': '',
        'payment_method': 'cash',
        'payment_reference': '',
        'eway_bill_number': eway,
        'amount_paid': 0,
        'notes': '',
        'terms': '',
        'invoice_date': '',
        'due_date': '',
        'allow_out_of_stock': True,
        'items': [{'product_id': None, 'product_name': 'test product', 'hsn': '8504',
                   'qty': 1, 'unit': 'NOS', 'price': 100, 'discount': 0, 'gst_rate': 18}],
    }
    resp = client.post('/invoices/create', json=payload,
                       headers={'X-CSRFToken': token, 'X-CSRF-Token': token})
    assert resp.get_json().get('success'), resp.get_data(as_text=True)[:800]
    return int(re.search(r'/invoices/(\d+)', resp.get_json()['redirect']).group(1))


@pytest.mark.parametrize('client_fixture', ['admin_login', 'sales_login'])
def test_eway_bill_saved_and_rendered(request, client_fixture, make_invoice):
    """A user-entered E-Way Bill No. is persisted and shown below Invoice No."""
    client = request.getfixturevalue(client_fixture)
    make_invoice()  # unrelated existing invoice must stay untouched

    inv_id = _post_create(client, '123456789012')

    from app import Invoice
    inv = Invoice.query.get(inv_id)
    assert inv.eway_bill_number == '123456789012'

    for url in ('/invoices/%d/preview' % inv_id,
                '/invoices/%d' % inv_id,
                '/invoices/%d/print/customer' % inv_id,
                '/invoices/%d/print/owner' % inv_id,
                '/invoices/%d/print/gst' % inv_id,
                '/invoices/%d/print/all' % inv_id):
        html = client.get(url).get_data(as_text=True)
        assert '123456789012' in html, 'E-Way Bill missing from %s' % url
        assert 'E-Way Bill No.' in html, 'label missing from %s' % url
        # positioned directly below Invoice No.
        assert re.search(r'Invoice No\..*?123456789012.*?Invoice Date', html, re.S), \
            'wrong position in %s' % url

    for copy in ('customer', 'owner', 'gst'):
        pdf = client.get('/invoices/%d/pdf/%s' % (inv_id, copy))
        assert pdf.status_code == 200
        assert _pdf_has_text(pdf.data, '123456789012'), \
            'E-Way Bill missing from %s PDF' % copy


def test_eway_bill_blank_creates_no_row(request, admin_login, make_invoice):
    """An empty E-Way Bill field stores NULL and renders no row at all."""
    inv_id = _post_create(admin_login, '')

    from app import Invoice
    inv = Invoice.query.get(inv_id)
    assert not inv.eway_bill_number

    html = admin_login.get('/invoices/%d/preview' % inv_id).get_data(as_text=True)
    assert 'E-Way Bill No.' not in html
    assert not re.search(r'Invoice No\..*?E-Way Bill', html, re.S)


def test_eway_bill_whitespace_only_creates_no_row(request, admin_login):
    """Whitespace-only input is treated as empty, not as a value."""
    inv_id = _post_create(admin_login, '   ')

    from app import Invoice
    assert not Invoice.query.get(inv_id).eway_bill_number
    assert 'E-Way Bill No.' not in admin_login.get(
        '/invoices/%d/preview' % inv_id).get_data(as_text=True)


def test_form_payload_includes_eway_field(admin_login):
    """Regression guard: the JS payload builder must send the field."""
    html = admin_login.get('/invoices/create').get_data(as_text=True)
    payload = html[html.index('const payload = {'):]
    payload = payload[:payload.index('const btn =')]
    assert 'eway_bill_number' in payload
    assert 'ewayBillNumber' in payload


def _pdf_has_text(data, needle):
    try:
        import pymupdf
        doc = pymupdf.open(stream=data, filetype='pdf')
        return needle in ''.join(p.get_text() for p in doc)
    except Exception:
        return False
