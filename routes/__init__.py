"""
GV Powers ERP - Routes Package
Registers all route modules with the Flask app.
Endpoint names are preserved for template compatibility.
"""

from .auth import register as register_auth
from .admin import register as register_admin
from .customers import register as register_customers
from .products import register as register_products
from .suppliers import register as register_suppliers
from .billing import register as register_billing
from .purchases import register as register_purchases
from .quotations import register as register_quotations
from .reports import register as register_reports
from .api import register as register_api


def register_routes(app):
    """Register all route modules with the Flask app."""
    register_auth(app)
    register_admin(app)
    register_customers(app)
    register_products(app)
    register_suppliers(app)
    register_billing(app)
    register_purchases(app)
    register_quotations(app)
    register_reports(app)
    register_api(app)
