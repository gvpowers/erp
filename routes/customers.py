"""
GV Powers ERP - Customer Routes
CRUD + search API.
"""

from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import login_required, current_user
from sqlalchemy import desc, or_

from models import db, Customer, Invoice
from services.audit_service import log_audit


def register(app):

    @app.route("/customers")
    @login_required
    def customers_list():
        search = request.args.get("q", "").strip()
        query = Customer.query
        if search:
            query = query.filter(
                or_(
                    Customer.name.ilike(f"%{search}%"),
                    Customer.mobile.ilike(f"%{search}%"),
                    Customer.email.ilike(f"%{search}%"),
                )
            )
        customers = query.order_by(desc(Customer.created_at)).all()
        return render_template("customers/customers.html", customers=customers, search=search)

    @app.route("/customers/create", methods=["POST"])
    @login_required
    def create_customer():
        name = request.form.get("name", "").strip()
        mobile = request.form.get("mobile", "").strip()
        if not name:
            flash("Customer name is required.", "danger")
            return redirect(url_for("customers_list"))
        if mobile:
            existing = Customer.query.filter_by(mobile=mobile).first()
            if existing:
                flash("Customer with this mobile already exists.", "warning")
                return redirect(url_for("customers_list"))
        customer = Customer(
            name=name,
            mobile=mobile,
            email=request.form.get("email", "").strip(),
            address=request.form.get("address", "").strip(),
            city=request.form.get("city", "").strip(),
            state=request.form.get("state", "").strip(),
            state_code=int(request.form.get("state_code") or 29),
            gstin=request.form.get("gstin", "").strip(),
            pan=request.form.get("pan", "").strip(),
            customer_type=request.form.get("customer_type", "B2C"),
        )
        db.session.add(customer)
        db.session.commit()
        log_audit("create_customer", f"Created customer: {customer.name}")
        flash(f"Customer '{customer.name}' created.", "success")
        return redirect(url_for("customers_list"))

    @app.route("/customers/<int:cid>/edit", methods=["POST"])
    @login_required
    def edit_customer(cid):
        if not current_user.is_admin:
            abort(403)
        customer = db.session.get(Customer, cid)
        if not customer:
            abort(404)
        customer.name = (request.form.get("name", "") or customer.name or "").strip()
        customer.mobile = (request.form.get("mobile", "") or customer.mobile or "").strip()
        customer.email = (request.form.get("email", "") or customer.email or "").strip()
        customer.address = (request.form.get("address", "") or customer.address or "").strip()
        customer.city = (request.form.get("city", "") or customer.city or "").strip()
        customer.state = (request.form.get("state", "") or customer.state or "").strip()
        customer.state_code = int(request.form.get("state_code") or customer.state_code or 29)
        customer.gstin = (request.form.get("gstin", "") or customer.gstin or "").strip()
        customer.pan = (request.form.get("pan", "") or customer.pan or "").strip()
        customer.customer_type = request.form.get("customer_type", customer.customer_type)
        db.session.commit()
        log_audit("edit_customer", f"Edited customer: {customer.name}")
        flash("Customer updated.", "success")
        return redirect(url_for("customers_list"))

    @app.route("/customers/<int:cid>/delete", methods=["POST"])
    @login_required
    def delete_customer(cid):
        if not current_user.is_admin:
            abort(403)
        customer = db.session.get(Customer, cid)
        if customer:
            log_audit("delete_customer", f"Deleted customer: {customer.name}")
            db.session.delete(customer)
            db.session.commit()
            flash("Customer deleted.", "success")
        return redirect(url_for("customers_list"))

    @app.route("/customers/<int:cid>")
    @login_required
    def customer_profile(cid):
        customer = db.session.get(Customer, cid)
        if not customer:
            abort(404)
        invoices = Invoice.query.filter_by(customer_id=cid).order_by(desc(Invoice.created_at)).all()
        return render_template("customers/customer_profile.html", customer=customer, invoices=invoices)

    @app.route("/api/customers/search")
    @login_required
    def api_customer_search():
        q = request.args.get("q", "").strip()
        if len(q) < 1:
            return jsonify([])
        customers = Customer.query.filter(
            or_(
                Customer.name.ilike(f"%{q}%"),
                Customer.mobile.ilike(f"%{q}%"),
            )
        ).limit(10).all()
        return jsonify([{
            "id": c.id, "name": c.name, "mobile": c.mobile, "email": c.email,
            "address": c.address, "city": c.city, "state": c.state,
            "state_code": c.state_code, "gstin": c.gstin,
        } for c in customers])

    @app.route("/api/customers/<int:cid>")
    @login_required
    def api_customer_detail(cid):
        customer = db.session.get(Customer, cid)
        if not customer:
            return jsonify({"error": "Customer not found"}), 404
        return jsonify({
            "id": customer.id, "name": customer.name, "mobile": customer.mobile,
            "email": customer.email, "address": customer.address, "city": customer.city,
            "state": customer.state, "state_code": customer.state_code,
            "gstin": customer.gstin, "pan": customer.pan,
            "customer_type": customer.customer_type,
        })
