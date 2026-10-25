"""
GV Powers ERP - Product Routes
CRUD, search API, categories, stock management.
Products serve as the single stock master.
"""

import os
import secrets
import uuid
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, abort, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy import desc, or_

from models import db, Product, Category, Supplier, StockMovement
from services.audit_service import log_audit


def register(app):

    @app.route("/products")
    @login_required
    def products_list():
        search = request.args.get("q", "").strip()
        category_id = request.args.get("category", type=int)
        stock_filter = request.args.get("stock", "")
        query = Product.query
        if search:
            query = query.filter(
                or_(
                    Product.name.ilike(f"%{search}%"),
                    Product.sku.ilike(f"%{search}%"),
                    Product.barcode.ilike(f"%{search}%"),
                    Product.hsn.ilike(f"%{search}%"),
                    Product.brand.ilike(f"%{search}%"),
                )
            )
        if category_id:
            query = query.filter_by(category_id=category_id)
        if stock_filter == "out_of_stock":
            query = query.filter(Product.current_stock <= 0)
        elif stock_filter == "low_stock":
            query = query.filter(Product.current_stock <= Product.min_stock, Product.current_stock > 0)
        elif stock_filter == "in_stock":
            query = query.filter(Product.current_stock > Product.min_stock)
        products = query.order_by(desc(Product.created_at)).all()
        categories = Category.query.order_by(Category.name).all()
        suppliers = Supplier.query.order_by(Supplier.name).all()
        return render_template("products/products.html", products=products,
                               categories=categories, suppliers=suppliers, search=search,
                               selected_category=category_id, stock_filter=stock_filter)

    @app.route("/products/create", methods=["POST"])
    @login_required
    def create_product():
        if not current_user.is_admin:
            abort(403)
        name = request.form.get("name", "").strip()
        if not name:
            flash("Product name is required.", "danger")
            return redirect(url_for("products_list"))

        sku = request.form.get("sku", "").strip()
        if sku and Product.query.filter_by(sku=sku).first():
            flash("SKU already exists.", "danger")
            return redirect(url_for("products_list"))

        barcode = request.form.get("barcode", "").strip()
        if barcode and Product.query.filter_by(barcode=barcode).first():
            flash("Barcode already exists.", "danger")
            return redirect(url_for("products_list"))

        product = Product(
            name=name,
            sku=sku or str(uuid.uuid4())[:8].upper(),
            barcode=barcode,
            hsn=request.form.get("hsn", "").strip(),
            brand=request.form.get("brand", "").strip(),
            category_id=request.form.get("category_id", type=int),
            supplier_id=request.form.get("supplier_id", type=int),
            unit=request.form.get("unit", "Pcs"),
            purchase_price=float(request.form.get("purchase_price", 0) or 0),
            selling_price=float(request.form.get("selling_price", 0) or 0),
            gst_rate=float(request.form.get("gst_rate", 18) or 18),
            current_stock=int(request.form.get("opening_stock", 0) or 0),
            min_stock=int(request.form.get("min_stock", 5) or 5),
            max_stock=int(request.form.get("max_stock", 500) or 500),
            location=request.form.get("location", "").strip(),
            warehouse=request.form.get("warehouse", "").strip(),
            warranty=request.form.get("warranty", "").strip(),
            description=request.form.get("description", "").strip(),
        )

        image = request.files.get("image")
        if image and image.filename:
            ext = os.path.splitext(image.filename)[1].lower()
            filename = f"product_{secrets.token_hex(8)}{ext}"
            upload_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "products")
            os.makedirs(upload_dir, exist_ok=True)
            image.save(os.path.join(upload_dir, filename))
            product.image = filename

        db.session.add(product)
        db.session.commit()
        log_audit("create_product", f"Created product: {product.name} (SKU: {product.sku})")
        flash(f"Product '{product.name}' created.", "success")
        return redirect(url_for("products_list"))

    @app.route("/products/<int:pid>/edit", methods=["POST"])
    @login_required
    def edit_product(pid):
        if not current_user.is_admin:
            abort(403)
        product = db.session.get(Product, pid)
        if not product:
            abort(404)
        product.name = (request.form.get("name", "") or product.name or "").strip()
        product.sku = (request.form.get("sku", "") or product.sku or "").strip()
        product.barcode = (request.form.get("barcode", "") or product.barcode or "").strip()
        product.hsn = (request.form.get("hsn", "") or product.hsn or "").strip()
        product.brand = (request.form.get("brand", "") or product.brand or "").strip()
        product.category_id = request.form.get("category_id", product.category_id, type=int)
        product.supplier_id = request.form.get("supplier_id", product.supplier_id, type=int)
        product.unit = request.form.get("unit", product.unit)
        product.purchase_price = float(request.form.get("purchase_price", product.purchase_price) or 0)
        product.selling_price = float(request.form.get("selling_price", product.selling_price) or 0)
        product.gst_rate = float(request.form.get("gst_rate", product.gst_rate) or 18)
        product.min_stock = int(request.form.get("min_stock", product.min_stock) or 5)
        product.max_stock = int(request.form.get("max_stock", product.max_stock) or 500)
        product.location = (request.form.get("location", "") or product.location or "").strip()
        product.warehouse = (request.form.get("warehouse", "") or product.warehouse or "").strip()
        product.warranty = (request.form.get("warranty", "") or product.warranty or "").strip()
        product.description = (request.form.get("description", "") or product.description or "").strip()

        image = request.files.get("image")
        if image and image.filename:
            ext = os.path.splitext(image.filename)[1].lower()
            filename = f"product_{secrets.token_hex(8)}{ext}"
            upload_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "products")
            os.makedirs(upload_dir, exist_ok=True)
            image.save(os.path.join(upload_dir, filename))
            product.image = filename

        db.session.commit()
        log_audit("edit_product", f"Edited product: {product.name}")
        flash("Product updated.", "success")
        return redirect(url_for("products_list"))

    @app.route("/products/<int:pid>/delete", methods=["POST"])
    @login_required
    def delete_product(pid):
        if not current_user.is_admin:
            abort(403)
        product = db.session.get(Product, pid)
        if product:
            if StockMovement.query.filter_by(product_id=pid).first():
                flash("Cannot delete product with stock movement history. Deactivate it instead.", "danger")
                return redirect(url_for("products_list"))
            log_audit("delete_product", f"Deleted product: {product.name}")
            db.session.delete(product)
            db.session.commit()
            flash("Product deleted.", "success")
        return redirect(url_for("products_list"))

    @app.route("/products/<int:pid>")
    @login_required
    def product_profile(pid):
        product = db.session.get(Product, pid)
        if not product:
            abort(404)
        movements = StockMovement.query.filter_by(product_id=pid).order_by(desc(StockMovement.created_at)).limit(100).all()
        categories = Category.query.order_by(Category.name).all()
        suppliers = Supplier.query.order_by(Supplier.name).all()
        return render_template("products/product_profile.html", product=product,
                               movements=movements, categories=categories, suppliers=suppliers)

    @app.route("/products/bulk-delete", methods=["POST"])
    @login_required
    def bulk_delete_products():
        if not current_user.is_admin:
            abort(403)
        data = request.get_json() if request.is_json else None
        ids = data.get("ids", []) if data else request.form.getlist("ids")
        deleted = 0
        skipped = 0
        if ids:
            for pid in ids:
                try:
                    pid_int = int(pid)
                except (ValueError, TypeError):
                    continue
                product = db.session.get(Product, pid_int)
                if product:
                    if StockMovement.query.filter_by(product_id=pid_int).first():
                        skipped += 1
                        continue
                    log_audit("delete_product", f"Bulk deleted product: {product.name}")
                    db.session.delete(product)
                    deleted += 1
            db.session.commit()
            if deleted:
                flash(f"Deleted {deleted} products." + (f" Skipped {skipped} with stock history." if skipped else ""), "success")
        return jsonify({"success": True, "deleted": deleted}) if request.is_json else redirect(url_for("products_list"))

    # ------------------------------------------------------------------
    # STOCK MANAGEMENT
    # ------------------------------------------------------------------

    @app.route("/products/<int:pid>/add-stock", methods=["POST"])
    @login_required
    def add_stock(pid):
        if not current_user.is_admin:
            abort(403)
        product = db.session.get(Product, pid)
        if not product:
            abort(404)
        try:
            quantity = int(request.form.get("quantity") or 0)
        except (ValueError, TypeError):
            quantity = 0
        if quantity <= 0:
            flash("Quantity must be greater than zero.", "danger")
            return redirect(url_for("product_profile", pid=pid))
        purchase_cost = float(request.form.get("purchase_cost") or 0)
        supplier = (request.form.get("supplier", "") or "").strip()
        purchase_date_str = request.form.get("purchase_date", "")
        remarks = (request.form.get("remarks", "") or "").strip()
        try:
            purchase_date = datetime.strptime(purchase_date_str, "%Y-%m-%d").date() if purchase_date_str else datetime.utcnow().date()
        except (ValueError, TypeError):
            purchase_date = datetime.utcnow().date()
        product.current_stock += quantity
        product.last_purchase = datetime.utcnow()
        if purchase_cost > 0:
            product.purchase_price = purchase_cost
        movement = StockMovement(
            product_id=product.id,
            movement_type="purchase",
            quantity=quantity,
            reference_type="purchase",
            reference_id=None,
            notes=f"Supplier: {supplier} | Purchase Date: {purchase_date} | Remarks: {remarks}" if remarks else f"Supplier: {supplier} | Purchase Date: {purchase_date}",
            user_id=current_user.id,
        )
        db.session.add(movement)
        db.session.commit()
        log_audit("add_stock", f"Added {quantity} units to {product.name}. New stock: {product.current_stock}")
        flash(f"Added {quantity} units to '{product.name}'. New stock: {product.current_stock}", "success")
        return redirect(url_for("product_profile", pid=pid))

    @app.route("/products/<int:pid>/remove-stock", methods=["POST"])
    @login_required
    def remove_stock(pid):
        if not current_user.is_admin:
            abort(403)
        product = db.session.get(Product, pid)
        if not product:
            abort(404)
        try:
            quantity = int(request.form.get("quantity") or 0)
        except (ValueError, TypeError):
            quantity = 0
        if quantity <= 0:
            flash("Quantity must be greater than zero.", "danger")
            return redirect(url_for("product_profile", pid=pid))
        reason = (request.form.get("reason", "") or "").strip()
        remarks = (request.form.get("remarks", "") or "").strip()
        if quantity > product.current_stock:
            flash(f"Insufficient Stock. Available: {product.current_stock}, Requested: {quantity}", "danger")
            return redirect(url_for("product_profile", pid=pid))
        product.current_stock -= quantity
        movement = StockMovement(
            product_id=product.id,
            movement_type=reason if reason else "adjustment",
            quantity=-quantity,
            reference_type="stock_removal",
            notes=f"Reason: {reason} | Remarks: {remarks}" if remarks else f"Reason: {reason}",
            user_id=current_user.id,
        )
        db.session.add(movement)
        db.session.commit()
        log_audit("remove_stock", f"Removed {quantity} units from {product.name}. Reason: {reason}. New stock: {product.current_stock}")
        flash(f"Removed {quantity} units from '{product.name}'. New stock: {product.current_stock}", "success")
        return redirect(url_for("product_profile", pid=pid))

    @app.route("/products/<int:pid>/delete-stock", methods=["POST"])
    @login_required
    def delete_stock(pid):
        if not current_user.is_admin:
            abort(403)
        product = db.session.get(Product, pid)
        if not product:
            abort(404)
        if product.current_stock == 0:
            flash("Stock is already zero.", "warning")
            return redirect(url_for("product_profile", pid=pid))
        old_stock = product.current_stock
        product.current_stock = 0
        movement = StockMovement(
            product_id=product.id,
            movement_type="reset",
            quantity=-old_stock,
            reference_type="stock_reset",
            notes=f"Stock reset to zero by {current_user.full_name}. Previous stock: {old_stock}",
            user_id=current_user.id,
        )
        db.session.add(movement)
        db.session.commit()
        log_audit("delete_stock", f"Reset stock for {product.name} from {old_stock} to 0")
        flash(f"Stock for '{product.name}' has been reset to 0.", "success")
        return redirect(url_for("product_profile", pid=pid))

    @app.route("/products/<int:pid>/stock-history")
    @login_required
    def stock_history(pid):
        product = db.session.get(Product, pid)
        if not product:
            abort(404)
        movements = StockMovement.query.filter_by(product_id=pid).order_by(desc(StockMovement.created_at)).all()
        return jsonify([{
            "id": m.id,
            "date": m.created_at.isoformat() if m.created_at else "",
            "type": m.movement_type,
            "quantity": m.quantity,
            "reference_type": m.reference_type,
            "reference_id": m.reference_id,
            "notes": m.notes,
            "user": m.user.username if m.user else "",
            "balance_after": product.current_stock,
        } for m in movements])

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    @app.route("/api/products/search")
    @login_required
    def api_product_search():
        q = request.args.get("q", "").strip()
        allow_out_of_stock = request.args.get("allow_out_of_stock", "").strip().lower() == "true"
        if len(q) < 1:
            return jsonify([])
        query = Product.query.filter(
            or_(
                Product.name.ilike(f"%{q}%"),
                Product.sku.ilike(f"%{q}%"),
                Product.barcode.ilike(f"%{q}%"),
                Product.hsn.ilike(f"%{q}%"),
                Product.brand.ilike(f"%{q}%"),
            ),
            Product.is_active == True,
        )
        if not allow_out_of_stock:
            query = query.filter(Product.current_stock > 0)
        products = query.limit(20).all()
        return jsonify([{
            "id": p.id, "name": p.name, "sku": p.sku, "barcode": p.barcode,
            "hsn": p.hsn, "brand": p.brand, "unit": p.unit,
            "purchase_price": p.purchase_price, "selling_price": p.selling_price,
            "gst_rate": p.gst_rate, "current_stock": p.current_stock,
            "min_stock": p.min_stock, "max_stock": p.max_stock,
            "location": p.location, "status": p.status,
            "image": p.image, "category": p.category.name if p.category else "",
        } for p in products])

    # ------------------------------------------------------------------
    # CATEGORIES
    # ------------------------------------------------------------------

    @app.route("/categories/create", methods=["POST"])
    @login_required
    def create_category():
        if not current_user.is_admin:
            abort(403)
        name = request.form.get("name", "").strip()
        if name:
            if not Category.query.filter_by(name=name).first():
                cat = Category(name=name, description=request.form.get("description", "").strip())
                db.session.add(cat)
                db.session.commit()
                flash(f"Category '{name}' created.", "success")
            else:
                flash("Category already exists.", "warning")
        return redirect(url_for("products_list"))

    @app.route("/categories/<int:cat_id>/edit", methods=["POST"])
    @login_required
    def edit_category(cat_id):
        if not current_user.is_admin:
            abort(403)
        cat = db.session.get(Category, cat_id)
        if not cat:
            abort(404)
        name = (request.form.get("name", "") or "").strip()
        if name:
            cat.name = name
            cat.description = (request.form.get("description", "") or "").strip()
            db.session.commit()
            flash("Category updated.", "success")
        return redirect(url_for("products_list"))

    @app.route("/categories/<int:cat_id>/delete", methods=["POST"])
    @login_required
    def delete_category(cat_id):
        if not current_user.is_admin:
            abort(403)
        cat = db.session.get(Category, cat_id)
        if cat:
            Product.query.filter_by(category_id=cat.id).update({"category_id": None})
            db.session.delete(cat)
            db.session.commit()
            flash("Category deleted.", "success")
        return redirect(url_for("products_list"))
