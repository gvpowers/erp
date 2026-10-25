"""
GV Powers ERP - API Routes
Global search (Ctrl+K), notifications.
"""

from flask import jsonify, request, url_for
from flask_login import login_required, current_user
from sqlalchemy import or_

from models import db, Customer, Product, Invoice, Supplier, Quotation, Notification


def register(app):

    @app.route("/api/search")
    @login_required
    def global_search():
        q = request.args.get("q", "").strip()
        if len(q) < 2:
            return jsonify([])

        results = []

        customers = Customer.query.filter(
            or_(Customer.name.ilike(f"%{q}%"), Customer.mobile.ilike(f"%{q}%"))
        ).limit(5).all()
        for c in customers:
            results.append({
                "type": "customer", "id": c.id, "title": c.name,
                "subtitle": c.mobile or "", "url": url_for("customer_profile", cid=c.id),
            })

        products = Product.query.filter(
            or_(Product.name.ilike(f"%{q}%"), Product.sku.ilike(f"%{q}%"),
                Product.barcode.ilike(f"%{q}%"), Product.hsn.ilike(f"%{q}%")),
            Product.is_active == True,
        ).limit(5).all()
        for p in products:
            results.append({
                "type": "product", "id": p.id, "title": p.name,
                "subtitle": f"SKU: {p.sku or 'N/A'} | Stock: {p.current_stock}",
                "url": url_for("products_list", q=p.name),
            })

        invoices = Invoice.query.filter(
            or_(Invoice.invoice_number.ilike(f"%{q}%"), Invoice.customer_name.ilike(f"%{q}%"))
        ).limit(5).all()
        for inv in invoices:
            results.append({
                "type": "invoice", "id": inv.id, "title": inv.invoice_number,
                "subtitle": f"{inv.customer_name or 'N/A'} | Rs.{inv.grand_total:.2f}",
                "url": url_for("invoice_preview", inv_id=inv.id),
            })

        suppliers = Supplier.query.filter(
            or_(Supplier.name.ilike(f"%{q}%"), Supplier.mobile.ilike(f"%{q}%"))
        ).limit(3).all()
        for s in suppliers:
            results.append({
                "type": "supplier", "id": s.id, "title": s.name,
                "subtitle": s.mobile or "", "url": url_for("suppliers_list", q=s.name),
            })

        quotations = Quotation.query.filter(
            Quotation.quotation_number.ilike(f"%{q}%")
        ).limit(3).all()
        for qt in quotations:
            results.append({
                "type": "quotation", "id": qt.id, "title": qt.quotation_number,
                "subtitle": f"{qt.customer_name or 'N/A'} | Rs.{qt.grand_total:.2f}",
                "url": url_for("quotation_preview", qid=qt.id),
            })

        return jsonify(results)

    @app.route("/api/notifications")
    @login_required
    def api_notifications():
        notifs = Notification.query.filter_by(user_id=current_user.id).order_by(
            db.desc(Notification.created_at)
        ).limit(20).all()
        return jsonify([{
            "id": n.id, "title": n.title, "message": n.message,
            "type": n.notification_type, "is_read": n.is_read,
            "created_at": n.created_at.isoformat(),
        } for n in notifs])

    @app.route("/api/notifications/read", methods=["POST"])
    @login_required
    def mark_notifications_read():
        Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
        db.session.commit()
        return jsonify({"success": True})

    @app.route("/api/notifications/unread-count")
    @login_required
    def api_notification_count():
        count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        return jsonify({"count": count})
