from conftest import (
    db, Product, Notification, User,
    _run_low_stock_check, _low_stock_suggested_qty, meta_csrf,
)


def test_low_stock_notification_created(app, make_product):
    p = make_product(stock=3, min_stock=5)
    _run_low_stock_check()
    p = db.session.get(Product, p.id)
    assert p.low_stock_alert_active is True
    assert p.last_low_stock_notification_at is not None
    admins = User.query.filter(User.role.in_(['admin', 'manager'])).count()
    alerts = Notification.query.filter_by(title='Low stock alert').all()
    assert len(alerts) == admins
    assert all('Suggested purchase' in (n.message or '') for n in alerts)


def test_low_stock_check_deduplicates(app, make_product):
    p = make_product(stock=3, min_stock=5)
    _run_low_stock_check()
    _run_low_stock_check()
    assert Notification.query.filter_by(title='Low stock alert').count() == 2
    assert db.session.get(Product, p.id).low_stock_alert_active is True


def test_low_stock_resolves_after_restock(app, make_product):
    p = make_product(stock=3, min_stock=5)
    _run_low_stock_check()
    p = db.session.get(Product, p.id)
    p.stock_quantity = 10
    db.session.commit()
    before = Notification.query.filter_by(title='Low stock alert').count()
    _run_low_stock_check()
    assert db.session.get(Product, p.id).low_stock_alert_active is False
    assert Notification.query.filter_by(title='Low stock alert').count() == before


def test_low_stock_suggested_qty_formula(app, make_product):
    p = make_product(stock=3, min_stock=5)
    assert _low_stock_suggested_qty(p) == 7
    p2 = make_product(name='Well Stocked', sku='WELL_STOCKED', stock=20, min_stock=5)
    assert _low_stock_suggested_qty(p2) == 1


def test_low_stock_report_route(app, admin_login, make_product):
    make_product(stock=3, min_stock=5)
    resp = admin_login.get('/reports/low-stock')
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert 'Low Stock Items' in body
    assert 'Suggested Reorder Qty' in body


def test_low_stock_export_routes(app, admin_login, make_product):
    make_product(stock=3, min_stock=5)
    for fmt, mime in [('csv', 'text/csv'), ('excel', 'spreadsheet'), ('pdf', 'application/pdf')]:
        resp = admin_login.get(f'/reports/export/{fmt}/low_stock')
        assert resp.status_code == 200
        assert 'attachment' in (resp.headers.get('Content-Disposition') or '')


def test_low_stock_report_requires_admin(app, sales_login, make_product):
    make_product(stock=3, min_stock=5)
    resp = sales_login.get('/reports/low-stock')
    assert resp.status_code == 302
