"""
GV Powers ERP - Quotation Routes
CRUD, convert to invoice.
"""

import json
from datetime import datetime, date
from flask import render_template, request, redirect, url_for, flash, session, current_app, abort, jsonify
from flask_login import login_required, current_user
from sqlalchemy import desc

from models import db, Customer, Product, Quotation, QuotationItem
from services.audit_service import log_audit
from utils import generate_quotation_number


def register(app):

    @app.route("/quotations")
    @login_required
    def quotations_list():
        query = Quotation.query
        if not current_user.is_admin:
            query = query.filter_by(user_id=current_user.id)
        quotations = query.order_by(desc(Quotation.created_at)).all()
        return render_template("quotations/quotations.html", quotations=quotations)

    @app.route("/quotations/new")
    @login_required
    def new_quotation():
        qtn_number = generate_quotation_number()
        return render_template("quotations/new_quotation.html",
                               quotation_number=qtn_number, today=date.today())

    @app.route("/quotations/create", methods=["POST"])
    @login_required
    def create_quotation():
        from services import calculate_gst
        company_state_code = current_app.config["COMPANY_STATE_CODE"]

        data = request.get_json() if request.is_json else request.form.to_dict(flat=False)
        if not request.is_json:
            for k, v in data.items():
                if isinstance(v, list) and len(v) == 1:
                    data[k] = v[0]

        customer_name = (data.get("customer_name") or "").strip()
        customer_mobile = (data.get("customer_mobile") or "").strip()
        customer_address = (data.get("customer_address") or "").strip()
        customer_state_code = int(data.get("customer_state_code") or company_state_code)
        customer_state = (data.get("customer_state") or current_app.config["COMPANY_STATE"]).strip()
        customer_gstin = (data.get("customer_gstin") or "").strip()
        items_raw = data.get("items", [])
        valid_until = data.get("valid_until")
        notes = (data.get("notes") or "").strip()
        terms = (data.get("terms") or "").strip()

        if isinstance(items_raw, str):
            try:
                items_raw = json.loads(items_raw)
            except json.JSONDecodeError:
                items_raw = []

        customer_id = data.get("customer_id")
        customer = None
        if customer_id:
            customer = db.session.get(Customer, int(customer_id))

        quotation = Quotation(
            quotation_number=generate_quotation_number(),
            customer_id=customer.id if customer else None,
            customer_name=customer_name,
            customer_mobile=customer_mobile,
            customer_address=customer_address,
            customer_state=customer_state,
            customer_state_code=customer_state_code,
            customer_gstin=customer_gstin,
            valid_until=datetime.strptime(valid_until, "%Y-%m-%d").date() if valid_until else None,
            notes=notes, terms=terms,
            user_id=current_user.id, status="draft",
        )

        gst_items = []
        for item_data in items_raw:
            product = None
            pid = item_data.get("product_id")
            if pid:
                product = db.session.get(Product, int(pid)) if pid else None
            qty = int(item_data.get("qty", 1))
            price = float(item_data.get("price", 0))
            discount = float(item_data.get("discount", 0))
            gst_rate = float(item_data.get("gst_rate", 18))

            gst_items.append({"qty": qty, "price": price, "discount": discount, "gst_rate": gst_rate})

            qi = QuotationItem(
                product_id=product.id if product else None,
                product_name=product.name if product else item_data.get("product_name", ""),
                hsn=product.hsn if product else item_data.get("hsn", ""),
                qty=qty, unit=product.unit if product else item_data.get("unit", "Pcs"),
                price=price, discount=discount, gst_rate=gst_rate,
            )
            quotation.items.append(qi)

        gst_result = calculate_gst(customer_state_code, gst_items, company_state_code)
        for i, qi in enumerate(quotation.items):
            gi = gst_items[i]
            qi.taxable_value = gi.get("taxable_value", 0)
            qi.cgst = gi.get("cgst", 0)
            qi.sgst = gi.get("sgst", 0)
            qi.igst = gi.get("igst", 0)
            qi.total = gi.get("total", 0)

        quotation.subtotal = sum(i.price * i.qty for i in quotation.items)
        quotation.total_discount = gst_result["total_discount"]
        quotation.total_taxable = gst_result["total_taxable"]
        quotation.total_cgst = gst_result["total_cgst"]
        quotation.total_sgst = gst_result["total_sgst"]
        quotation.total_igst = gst_result["total_igst"]
        quotation.round_off = gst_result["round_off"]
        quotation.grand_total = gst_result["grand_total"]

        db.session.add(quotation)
        db.session.commit()
        log_audit("create_quotation", f"Quotation {quotation.quotation_number} created")
        flash(f"Quotation '{quotation.quotation_number}' created.", "success")

        if request.is_json:
            return jsonify({"success": True, "quotation_id": quotation.id,
                            "redirect": url_for("quotation_preview", qid=quotation.id)})
        return redirect(url_for("quotation_preview", qid=quotation.id))

    @app.route("/quotations/<int:qid>")
    @login_required
    def quotation_preview(qid):
        quotation = db.session.get(Quotation, qid)
        if not quotation:
            abort(404)
        return render_template("quotations/quotation_preview.html", quotation=quotation)

    @app.route("/quotations/<int:qid>/convert", methods=["POST"])
    @login_required
    def convert_quotation_to_invoice(qid):
        from models import Product
        company_state_code = current_app.config["COMPANY_STATE_CODE"]
        quotation = db.session.get(Quotation, qid)
        if not quotation:
            abort(404)
        quotation.status = "converted"
        db.session.commit()
        quotation_data = {
            "customer_name": quotation.customer_name or "",
            "customer_mobile": quotation.customer_mobile or "",
            "customer_id": quotation.customer_id,
            "customer_state": quotation.customer_state or "",
            "customer_state_code": quotation.customer_state_code or company_state_code,
            "customer_gstin": quotation.customer_gstin or "",
            "customer_address": quotation.customer_address or "",
            "items": [],
        }
        for qi in quotation.items:
            quotation_data["items"].append({
                "product_id": qi.product_id,
                "product_name": qi.product_name,
                "hsn": qi.hsn or "",
                "qty": qi.qty, "unit": qi.unit,
                "price": qi.price, "discount": qi.discount, "gst_rate": qi.gst_rate,
            })
        session["quotation_convert"] = json.dumps(quotation_data)
        flash("Quotation converted. Items loaded into new invoice.", "success")
        return redirect(url_for("new_invoice"))
