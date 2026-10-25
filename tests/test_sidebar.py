import re

import pytest

from conftest import db, Customer, Invoice, meta_csrf


def _active_tooltips(html):
    """Tooltip labels of the sidebar links that carry the `active` class."""
    return set(re.findall(r'class="nav-link active"[^>]*data-tooltip="([^"]+)"', html))


@pytest.mark.parametrize('path,expected', [
    ('/dashboard', {'Dashboard'}),
    ('/reports', {'Reports'}),
    ('/reports/sales', {'Reports'}),
    ('/reports/low-stock', {'Low Stock'}),
    ('/quotations', {'Quotations'}),
    ('/customers', {'Customers'}),
    ('/products', {'Products'}),
    ('/suppliers', {'Suppliers'}),
    ('/purchase-orders', {'Purchases'}),
    ('/users', {'Users'}),
    ('/settings', {'Settings'}),
    ('/audit-logs', {'Audit Logs'}),
    ('/backup', {'Backup'}),
])
def test_single_sidebar_item_active(app, admin_login, path, expected):
    resp = admin_login.get(path)
    assert resp.status_code == 200
    active = _active_tooltips(resp.get_data(as_text=True))
    assert active == expected


def test_customer_ledger_highlights_customers_only(app, admin_login, make_customer):
    c = make_customer()
    resp = admin_login.get(f'/customers/{c.id}/ledger')
    assert resp.status_code == 200
    assert _active_tooltips(resp.get_data(as_text=True)) == {'Customers'}


def test_invoice_history_highlights_invoice_history_only(app, admin_login, make_invoice):
    inv = make_invoice()
    resp = admin_login.get('/invoices')
    assert resp.status_code == 200
    assert _active_tooltips(resp.get_data(as_text=True)) == {'Invoice History'}


def test_edit_invoice_page_highlights_invoice_history_only(app, admin_login, make_invoice):
    inv = make_invoice(status='draft')
    resp = admin_login.get(f'/invoices/{inv.id}/edit')
    assert resp.status_code == 200
    assert _active_tooltips(resp.get_data(as_text=True)) == {'Invoice History'}


def test_new_invoice_page_highlights_new_invoice_only(app, admin_login):
    resp = admin_login.get('/invoices/create')
    assert resp.status_code == 200
    assert _active_tooltips(resp.get_data(as_text=True)) == {'New Invoice'}
