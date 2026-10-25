from datetime import date, timedelta

from conftest import db, Invoice


def test_dashboard_all_ranges_render(app, admin_login, make_customer, make_invoice):
    for rng in ('7d', '30d', 'month', 'fy'):
        resp = admin_login.get(f'/dashboard?range={rng}')
        body = resp.get_data(as_text=True)
        assert resp.status_code == 200, rng
        for section in ('Sales in Period', 'Collections in Period', 'Opening Balance',
                        'Quick Actions', 'Outstanding Customers', 'Recent Activity'):
            assert section in body, (rng, section)


def test_dashboard_default_range_is_month(app, admin_login):
    resp = admin_login.get('/dashboard')
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert 'This Month' in body


def test_dashboard_lists_outstanding_customers(app, admin_login, make_customer, make_invoice):
    c = make_customer('Due Customer')
    make_invoice(customer=c, products=[{'name': 'X', 'qty': 1, 'price': 500, 'gst_rate': 18}])
    body = admin_login.get('/dashboard').get_data(as_text=True)
    assert 'Due Customer' in body


def test_dashboard_opening_balance_uses_day_before_from(app, admin_login, make_customer, make_invoice):
    c = make_customer('Opening Customer')
    inv = make_invoice(customer=c, invoice_date=date.today().replace(day=1) - timedelta(days=5))
    body = admin_login.get('/dashboard?range=month').get_data(as_text=True)
    expected = 'Rs. %s' % format(int(inv.grand_total), ',')
    assert expected + '.00' in body


def test_dashboard_sales_role_uses_sales_view(app, sales_login):
    resp = sales_login.get('/dashboard')
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'Recent Invoices' in body
    assert 'Sales in Period' not in body


def test_dashboard_requires_login(app, client):
    resp = client.get('/dashboard')
    assert resp.status_code == 302
