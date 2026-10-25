"""
GV Powers ERP - Supplier Routes
CRUD, profile, purchase orders.
"""

import json
from datetime import datetime, date
from flask import render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import desc, or_

from models import db, Supplier, Product, PurchaseOrder, PurchaseItem, StockMovement
from services.audit_service import log_audit


def register(app):

    @app.route("/suppliers")
    @login_required
    def suppliers_list():
        if not current_user.is_admin:
            abort(403)
        search = request.args.get("q", "").strip()
        query = Supplier.query
        if search:
            query = query.filter(
                or_(
                    Supplier.name.ilike(f"%{search}%"),
                    Supplier.mobile.ilike(f"%{search}%"),
                )
            )
        suppliers = query.order_by(desc(Supplier.created_at)).all()
        return render_template("suppliers/suppliers.html", suppliers=suppliers, search=search)

    @app.route("/suppliers/create", methods=["POST"])
    @login_required
    def create_supplier():
        if not current_user.is_admin:
            abort(403)
        name = request.form.get("name", "").strip()
        if not name:
            flash("Supplier name is required.", "danger")
            return redirect(url_for("suppliers_list"))
        supplier = Supplier(
            name=name,
            contact_person=request.form.get("contact_person", "").strip(),
            mobile=request.form.get("mobile", "").strip(),
            email=request.form.get("email", "").strip(),
            address=request.form.get("address", "").strip(),
            city=request.form.get("city", "").strip(),
            state=request.form.get("state", "").strip(),
            state_code=int(request.form.get("state_code") or 29),
            gstin=request.form.get("gstin", "").strip(),
        )
        db.session.add(supplier)
        db.session.commit()
        log_audit("create_supplier", f"Created supplier: {supplier.name}")
        flash(f"Supplier '{supplier.name}' created.", "success")
        return redirect(url_for("suppliers_list"))

    @app.route("/suppliers/<int:sid>/edit", methods=["POST"])
    @login_required
    def edit_supplier(sid):
        if not current_user.is_admin:
            abort(403)
        supplier = db.session.get(Supplier, sid)
        if not supplier:
            abort(404)
        supplier.name = (request.form.get("name", "") or supplier.name or "").strip()
        supplier.contact_person = (request.form.get("contact_person", "") or supplier.contact_person or "").strip()
        supplier.mobile = (request.form.get("mobile", "") or supplier.mobile or "").strip()
        supplier.email = (request.form.get("email", "") or supplier.email or "").strip()
        supplier.address = (request.form.get("address", "") or supplier.address or "").strip()
        supplier.city = (request.form.get("city", "") or supplier.city or "").strip()
        supplier.state = (request.form.get("state", "") or supplier.state or "").strip()
        supplier.state_code = int(request.form.get("state_code") or supplier.state_code or 29)
        supplier.gstin = (request.form.get("gstin", "") or supplier.gstin or "").strip()
        db.session.commit()
        log_audit("edit_supplier", f"Edited supplier: {supplier.name}")
        flash("Supplier updated.", "success")
        return redirect(url_for("suppliers_list"))

    @app.route("/suppliers/<int:sid>/delete", methods=["POST"])
    @login_required
    def delete_supplier(sid):
        if not current_user.is_admin:
            abort(403)
        supplier = db.session.get(Supplier, sid)
        if supplier:
            log_audit("delete_supplier", f"Deleted supplier: {supplier.name}")
            db.session.delete(supplier)
            db.session.commit()
            flash("Supplier deleted.", "success")
        return redirect(url_for("suppliers_list"))

    @app.route("/suppliers/<int:sid>")
    @login_required
    def supplier_profile(sid):
        if not current_user.is_admin:
            abort(403)
        supplier = db.session.get(Supplier, sid)
        if not supplier:
            abort(404)
        products = Product.query.filter_by(supplier_id=sid).order_by(Product.name).all()
        purchase_orders = PurchaseOrder.query.filter_by(supplier_id=sid).order_by(desc(PurchaseOrder.created_at)).all()
        return render_template("suppliers/supplier_profile.html", supplier=supplier,
                               products=products, purchase_orders=purchase_orders)

    # ------------------------------------------------------------------
    # PURCHASE ORDERS
    # ------------------------------------------------------------------

    @app.route("/purchases")
    @login_required
    def purchases_list():
        if not current_user.is_admin:
            abort(403)
        orders = PurchaseOrder.query.order_by(desc(PurchaseOrder.created_at)).all()
        suppliers = Supplier.query.order_by(Supplier.name).all()
        products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
        return render_template("suppliers/purchase_orders.html",
                               orders=orders, suppliers=suppliers, products=products)

    @app.route("/purchases/create", methods=["POST"])
    @login_required
    def create_purchase():
        if not current_user.is_admin:
            abort(403)
        supplier_id = request.form.get("supplier_id", type=int)
        order_date = request.form.get("order_date", date.today().isoformat())
        expected_date = request.form.get("expected_date")
        notes = request.form.get("notes", "").strip()
        items_json = request.form.get("items", "[]")

        try:
            items_data = json.loads(items_json)
        except json.JSONDecodeError:
            items_data = []

        from utils import generate_purchase_order_number
        order = PurchaseOrder(
            order_number=generate_purchase_order_number(),
            supplier_id=supplier_id,
            order_date=datetime.strptime(order_date, "%Y-%m-%d").date() if order_date else date.today(),
            expected_date=datetime.strptime(expected_date, "%Y-%m-%d").date() if expected_date else None,
            status="confirmed",
            notes=notes,
            user_id=current_user.id,
        )

        subtotal = 0.0
        tax = 0.0
        for item_data in items_data:
            product = db.session.get(Product, int(item_data.get("product_id", 0)))
            if not product:
                continue
            qty = int(item_data.get("qty", 1))
            price = float(item_data.get("price", product.purchase_price))
            gst_rate = float(item_data.get("gst_rate", product.gst_rate))
            item_total = qty * price
            item_tax = item_total * gst_rate / 100
            subtotal += item_total
            tax += item_tax

            pi = PurchaseItem(
                product_id=product.id,
                product_name=product.name,
                qty=qty,
                price=price,
                gst_rate=gst_rate,
                total=item_total + item_tax,
            )
            order.items.append(pi)

            product.current_stock += qty
            product.last_purchase = datetime.utcnow()
            product.purchase_price = price
            movement = StockMovement(
                product_id=product.id,
                movement_type="purchase",
                quantity=qty,
                reference_type="purchase_order",
                notes=f"Purchase via {order.order_number}",
                user_id=current_user.id,
            )
            db.session.add(movement)

        order.subtotal = subtotal
        order.tax_amount = tax
        order.grand_total = subtotal + tax

        db.session.add(order)
        db.session.commit()
        log_audit("create_purchase", f"Purchase order {order.order_number} created - Rs.{order.grand_total}")
        flash(f"Purchase order '{order.order_number}' created.", "success")
        return redirect(url_for("purchases_list"))

    @app.route("/purchases/<int:oid>/status", methods=["GET", "POST"])
    @login_required
    def update_po_status(oid):
        if not current_user.is_admin:
            abort(403)
        order = db.session.get(PurchaseOrder, oid)
        if order:
            status = request.args.get("status") or request.form.get("status", order.status)
            order.status = status
            db.session.commit()
            log_audit("update_po_status", f"Purchase order {order.order_number} status changed to {status}")
            flash("Purchase order updated.", "success")
        return redirect(url_for("purchases_list"))

    @app.route("/purchases/<int:oid>")
    @login_required
    def view_purchase_order(oid):
        if not current_user.is_admin:
            abort(403)
        order = db.session.get(PurchaseOrder, oid)
        if not order:
            abort(404)
        return render_template("suppliers/purchase_order_detail.html", order=order)

    @app.route("/purchases/<int:oid>/delete", methods=["POST"])
    @login_required
    def delete_purchase_order(oid):
        if not current_user.is_admin:
            abort(403)
        order = db.session.get(PurchaseOrder, oid)
        if order:
            if order.status == "received":
                for item in order.items:
                    product = db.session.get(Product, item.product_id) if item.product_id else None
                    if product:
                        product.current_stock = max(0, product.current_stock - item.qty)
                        movement = StockMovement(
                            product_id=product.id,
                            movement_type="return",
                            quantity=-item.qty,
                            reference_type="purchase_order",
                            notes=f"Stock reverted on PO deletion: {order.order_number}",
                            user_id=current_user.id,
                        )
                        db.session.add(movement)
            log_audit("delete_purchase_order", f"Deleted purchase order: {order.order_number}")
            db.session.delete(order)
            db.session.commit()
            flash("Purchase order deleted.", "success")
        return redirect(url_for("purchases_list"))
