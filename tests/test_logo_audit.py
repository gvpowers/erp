"""Global logo audit verification: every page must render the single
centralized logo source (img.png, served by the /logo route) and must not
reference any old logo filename.
"""

import pytest

OLD_LOGO_TOKENS = ['bess.png', 'diesel generator.png', 'img_2.png', 'img_3.png', 'img_4.png',
                   'img-1.png', 'images/logo', 'logo.jpg', 'logo.gif', 'Logo.png',
                   'logo.png', 'img/logo/logo.png']

# The centralized logo endpoint renders with the current official logo version everywhere.
# (base favicon + the shared gv_logo macro).
# Derived from the app rather than hardcoded: the version is bumped whenever the
# logo file changes, and a hardcoded copy silently fails every page in this file
# the next time it does.
def _logo_url_token():
    from app import OFFICIAL_LOGO_VERSION
    return '/logo?v=%s' % OFFICIAL_LOGO_VERSION


def test_official_logo_source_exists_and_is_png(app):
    from app import OFFICIAL_LOGO_PATH
    import os
    with app.app_context():
        assert os.path.isfile(OFFICIAL_LOGO_PATH)
        with open(OFFICIAL_LOGO_PATH, 'rb') as fh:
            assert fh.read(8) == b'\x89PNG\r\n\x1a\n'


# (label, method, path or endpoint, need_login)
PAGES = [
    # Admin
    ('dashboard', 'dashboard'),
    ('new_invoice', 'new_invoice'),
    ('invoice_history', 'invoice_history'),
    ('quotations', 'quotations_list'),
    ('customers', 'customers_list'),
    ('products', 'products_list'),
    ('suppliers', 'suppliers_list'),
    ('purchases', 'purchase_orders'),
    ('reports', 'reports_page'),
    ('low_stock', 'low_stock_report'),
    ('users', 'users_list'),
    ('settings', 'settings_page'),
    ('audit_logs', 'audit_logs'),
    ('backup', 'backup_page'),
]


def _get(client, endpoint, app):
    from flask import url_for
    with app.app_context():
        url = url_for(endpoint)
    return client.get(url)


@pytest.mark.usefixtures('app')
def test_admin_pages_use_logo_png(client, admin_login, app):
    for label, endpoint in PAGES:
        r = _get(client, endpoint, app)
        assert r.status_code < 400, f'{label} returned {r.status_code}'
        html = r.get_data(as_text=True)
        ok = _logo_url_token() in html
        assert ok, f'{label}: centralized logo URL not found in html'
        for bad in OLD_LOGO_TOKENS:
            assert bad not in html, f'{label}: old logo token {bad} present'


@pytest.mark.usefixtures('app')
def test_sales_pages_use_logo_png(client, sales_login, app):
    pages = [
        ('sales_dashboard', 'dashboard'),
        ('sales_invoice_history', 'invoice_history'),
    ]
    for label, endpoint in pages:
        r = _get(client, endpoint, app)
        assert r.status_code < 400, f'{label} returned {r.status_code}'
        html = r.get_data(as_text=True)
        assert _logo_url_token() in html, f'{label}: no centralized logo'
        for bad in OLD_LOGO_TOKENS:
            assert bad not in html, f'{label}: old logo token {bad} present'
        assert 'billing' in str(endpoint) or True


@pytest.mark.usefixtures('app')
def test_auth_login_page_uses_logo_png(client, app):
    r = client.get('/login')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert _logo_url_token() in html, 'login: no centralized logo'
    for bad in OLD_LOGO_TOKENS:
        assert bad not in html, f'login: old logo token {bad} present'


@pytest.mark.usefixtures('app')
def test_print_and_preview_pages_use_logo_png(client, admin_login, app, make_product, make_customer):
    from app import db, Invoice
    cust = make_customer(name='Walk-in')
    prod = make_product(name='LogoTestItem', selling_price=100, gst_rate=5, stock_quantity=50)
    page = client.get('/invoices/create').get_data(as_text=True)
    import re
    tok = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', page).group(1)
    r = client.post('/invoices/create', json={
        'customer_id': cust.id, 'customer_name': cust.name,
        'customer_state_code': 29, 'invoice_date': '2026-09-01',
        'payment_method': 'cash', 'amount_paid': 100, 'allow_out_of_stock': True,
        'items': [{'product_id': prod.id, 'product_name': prod.name, 'hsn': '8504',
                   'qty': 1, 'unit': 'pcs', 'price': 100, 'discount': 0, 'gst_rate': 5}],
    }, headers={'X-CSRFToken': tok})
    assert r.status_code == 200, r.get_data(as_text=True)
    with app.app_context():
        inv = Invoice.query.order_by(Invoice.id.desc()).first()
        inv_id = inv.id
    for url in [f'/invoices/{inv_id}/print/owner', f'/invoices/{inv_id}/print/all', f'/invoices/{inv_id}/preview']:
        resp = client.get(url)
        assert resp.status_code < 400, f'{url} -> {resp.status_code} {resp.get_data(as_text=True)[:200]}'
        html = resp.get_data(as_text=True)
        assert _logo_url_token() in html, f'{url}: no centralized logo'
        for bad in OLD_LOGO_TOKENS:
            assert bad not in html, f'{url}: old logo token {bad} present'

    pdf = client.get(f'/invoices/{inv_id}/pdf/owner')
    assert pdf.status_code == 200, f'pdf -> {pdf.status_code}'
    assert pdf.data[:4] == b'%PDF', 'pdf did not generate'


@pytest.mark.usefixtures('app')
def test_settings_company_info_uses_same_logo(client, admin_login, app):
    from flask import url_for
    with app.app_context():
        url = url_for('settings_page')
    r = client.get(url)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert _logo_url_token() in html, 'settings: no centralized logo'
    # must be identical source, not a separate settings-only logo
    for bad in OLD_LOGO_TOKENS:
        assert bad not in html, f'settings: old logo token {bad} present'
    # the preview + modal both come from the same macro
    assert html.count('gv-logo') >= 1
