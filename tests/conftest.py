import os
import re
import sys
import threading

import pytest

_BASE = os.path.dirname(os.path.abspath(__file__))
_PROJECT = os.path.dirname(_BASE)
sys.path.insert(0, _PROJECT)

os.environ['FLASK_ENV'] = 'development'
os.environ['TESTING'] = '1'
os.environ['SECRET_KEY'] = 'test-secret-key'
os.environ['DATABASE_URL'] = 'sqlite:///' + os.path.join(_BASE, 'test_app.db')

from app import (  # noqa: E402
    create_app, db, User, Customer, Product, Category, Supplier, Invoice,
    InvoiceItem, Quotation, QuotationItem, PurchaseOrder, PurchaseItem,
    Payment, StockMovement, Notification, InvoiceSequence, _seed_database,
    _ensure_default_settings, _ensure_product_columns, _ensure_payment_columns,
    _ensure_invoice_sequence_columns, generate_invoice_number,
    generate_quotation_number, generate_purchase_order_number,
    _run_low_stock_check, _low_stock_suggested_qty,
)
from datetime import date, timedelta  # noqa: E402
from decimal import Decimal  # noqa: E402


@pytest.fixture(scope='session')
def app():
    yield create_app()


@pytest.fixture(autouse=True)
def _app_ctx(app):
    """Push an app context for the whole test.

    Flask-Login stores the current user on the application context ``g``, so a
    session-wide context would leak login state across tests. A fresh context
    per test keeps every test isolated.
    """
    with app.app_context():
        yield


@pytest.fixture(autouse=True)
def reset_db(app, _app_ctx):
    """Fully reset the temp database before every test (fresh seed each time)."""
    db.session.remove()
    db.drop_all()
    db.create_all()
    _ensure_product_columns()
    _ensure_payment_columns()
    _ensure_invoice_sequence_columns()
    _seed_database()
    _ensure_default_settings()
    yield
    db.session.remove()


@pytest.fixture
def client(app):
    with app.test_client() as c:
        yield c


def _csrf(client, path='/login'):
    page = client.get(path)
    match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', page.get_data(as_text=True))
    return match.group(1) if match else None


def meta_csrf(client, path='/dashboard'):
    page = client.get(path)
    match = re.search(r'name="csrf-token" content="([^"]+)"', page.get_data(as_text=True))
    return match.group(1) if match else None


def _ensure_user(username, password, role, email, full_name):
    """The app no longer seeds users, so tests create the accounts they need."""
    u = User.query.filter_by(username=username).first()
    if not u:
        u = User(username=username, email=email, full_name=full_name, role=role, is_active=True)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
    return u


@pytest.fixture
def admin_login(client, app):
    _ensure_user('gvpowers@admin', 'admin@gvpowerssalem', 'admin', 'admin@gvpowers.in', 'Administrator')
    token = _csrf(client)
    client.post('/login', data={'username': 'gvpowers@admin', 'password': 'admin@gvpowerssalem', 'csrf_token': token})
    return client


@pytest.fixture
def sales_login(client, app):
    _ensure_user('gvpowers@sales', 'sales@gvpowerssalem', 'sales', 'sales@gvpowers.in', 'Sales User')
    token = _csrf(client)
    client.post('/login', data={'username': 'gvpowers@sales', 'password': 'sales@gvpowerssalem', 'csrf_token': token})
    return client


@pytest.fixture
def make_customer(app):
    def _make(name='Test Customer', **kw):
        c = Customer(name=name, mobile=kw.get('mobile', '9876543210'),
                     email=kw.get('email', 'cust@test.in'), address='Test Address',
                     state=kw.get('state', 'Tamil Nadu'), state_code=kw.get('state_code', 33),
                     gstin=kw.get('gstin', '33ABCDE1234F1Z5'))
        db.session.add(c)
        db.session.commit()
        return c
    return _make


@pytest.fixture
def make_product(app):
    def _make(name='Test Product', sku=None, stock=50, min_stock=5, selling=100.0,
              purchase=60.0, gst_rate=18, **kw):
        p = Product(name=name, sku=sku or name.replace(' ', '_').upper(),
                    stock_quantity=stock, min_stock=min_stock, max_stock=kw.get('max_stock', 100),
                    selling_price=Decimal(str(selling)), purchase_price=Decimal(str(purchase)),
                    gst_rate=Decimal(str(gst_rate)), hsn='8504', is_active=True)
        db.session.add(p)
        db.session.commit()
        return p
    return _make


@pytest.fixture
def make_quotation(app, make_customer):
    def _make(customer=None, status='draft', valid_until=None, items=None, **kw):
        c = customer or make_customer('Quote Customer')
        qd = kw.get('quotation_date', date.today())
        q = Quotation(quotation_number=generate_quotation_number(), customer_id=c.id,
                      customer_name=c.name, customer_state=c.state, customer_state_code=c.state_code,
                      quotation_date=qd, valid_until=valid_until, status=status,
                      is_intra_state=True, created_by=1)
        db.session.add(q)
        db.session.flush()
        sub = Decimal('0'); tt = Decimal('0'); tc = Decimal('0'); ts = Decimal('0')
        for it in (items or [{'name': 'Widget', 'qty': 2, 'price': 100, 'gst_rate': 18}]):
            rate = Decimal(str(it['price'])); qty = int(it['qty']); gr = Decimal(str(it.get('gst_rate', 18)))
            taxable = (rate * qty).quantize(Decimal('0.01'))
            gst = taxable * gr / Decimal('100')
            half = (gst / Decimal('2')).quantize(Decimal('0.01'))
            line_total = (taxable + gst).quantize(Decimal('1'))
            db.session.add(QuotationItem(quotation_id=q.id, product_id=it.get('product_id'),
                                         product_name=it['name'], qty=qty, price=rate,
                                         gst_rate=gr, taxable_value=taxable,
                                         cgst=half, sgst=half, total=line_total))
            sub += rate * qty; tt += taxable; tc += half; ts += half
        q.subtotal = sub; q.total_taxable = tt; q.total_cgst = tc; q.total_sgst = ts
        q.grand_total = (tt + tc + ts).quantize(Decimal('1'))
        db.session.commit()
        return q
    return _make


@pytest.fixture
def make_invoice(app, make_customer, make_product):
    def _make(customer=None, products=None, invoice_date=None, status='confirmed',
              amount_paid=0, **kw):
        c = customer or make_customer('Inv Customer')
        inv = Invoice(invoice_number=generate_invoice_number(), customer_id=c.id,
                      customer_name=c.name, customer_state=c.state,
                      customer_state_code=c.state_code,
                      invoice_date=invoice_date or date.today(),
                      status=status, payment_status='due', is_intra_state=True,
                      amount_paid=Decimal(str(amount_paid)), created_by=1)
        db.session.add(inv)
        db.session.flush()
        total = Decimal('0')
        for item in (products or [{'product': None, 'name': 'Item A', 'qty': 1, 'price': 200, 'gst_rate': 18}]):
            rate = Decimal(str(item['price'])); qty = int(item['qty'])
            gst = rate * qty * Decimal(str(item.get('gst_rate', 18))) / Decimal('100')
            lt = (rate * qty + gst).quantize(Decimal('0.01'))
            db.session.add(InvoiceItem(invoice_id=inv.id, product_id=(item['product'].id if item.get('product') else None),
                                       product_name=item['name'], qty=qty, price=rate,
                                       gst_rate=item.get('gst_rate', 18),
                                       taxable_value=rate * qty, total=lt))
            total += lt
        inv.subtotal = total; inv.grand_total = total.quantize(Decimal('1'))
        inv.balance_due = Decimal(str(amount_paid) or 0)
        inv.balance_due = (inv.grand_total - inv.amount_paid).quantize(Decimal('0.01'))
        db.session.commit()
        return inv
    return _make


@pytest.fixture
def concurrent_numbers(app):
    """Run 10 threads that each allocate an invoice number (used for race tests)."""
    def _run(count=10):
        results = []
        barrier = threading.Barrier(count)

        def worker():
            barrier.wait()
            with app.app_context():
                results.append(generate_invoice_number())

        threads = [threading.Thread(target=worker) for _ in range(count)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        return results
    return _run
