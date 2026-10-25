"""
GV Powers ERP - Billing Routes
Invoice creation, history, preview, PDF, payments, cancel/delete.
"""

import json
import io
from datetime import datetime, date
from flask import (
    render_template, request, redirect, url_for, flash,
    send_file, abort, jsonify, session, current_app,
)
from flask_login import login_required, current_user
from sqlalchemy import desc, or_

from models import (
    db, User, Customer, Product, Invoice, InvoiceItem,
    Payment, StockMovement, Notification, Settings,
)
from services.audit_service import log_audit, get_setting
from utils import generate_invoice_number, amount_to_words


def register(app):

    @app.route("/invoices/new")
    @login_required
    def new_invoice():
        if not current_user.has_permission("create_invoice"):
            abort(403)
        inv_number = generate_invoice_number()
        settings_terms = get_setting("invoice_terms", "1. Goods once sold will not be returned.\n2. Subject to local jurisdiction.")
        quotation_data = None
        if "quotation_convert" in session:
            raw = session.pop("quotation_convert")
            try:
                quotation_data = json.loads(raw) if isinstance(raw, str) else raw
            except (json.JSONDecodeError, TypeError):
                quotation_data = None
        return render_template("billing/new_invoice.html", invoice_number=inv_number,
                               terms=settings_terms, today=date.today(),
                               quotation_data=quotation_data)

    @app.route("/invoices/create", methods=["POST"])
    @login_required
    def create_invoice():
        if not current_user.has_permission("create_invoice"):
            abort(403)

        from services import calculate_gst
        company_state_code = current_app.config["COMPANY_STATE_CODE"]

        data = request.get_json() if request.is_json else None
        if data is None:
            data = request.form.to_dict(flat=False)
            for k, v in data.items():
                if isinstance(v, list) and len(v) == 1:
                    data[k] = v[0]

        allow_out_of_stock = data.get("allow_out_of_stock", False)
        if isinstance(allow_out_of_stock, str):
            allow_out_of_stock = allow_out_of_stock.lower() in ("true", "1", "yes")

        customer_id = data.get("customer_id")
        customer_name = (data.get("customer_name") or "").strip()
        customer_mobile = (data.get("customer_mobile") or "").strip()
        customer_address = (data.get("customer_address") or "").strip()
        customer_state = (data.get("customer_state") or current_app.config["COMPANY_STATE"]).strip()
        customer_state_code = int(data.get("customer_state_code") or company_state_code)
        customer_gstin = (data.get("customer_gstin") or "").strip()
        payment_method = data.get("payment_method") or "cash"
        payment_reference = (data.get("payment_reference") or "").strip()
        notes = (data.get("notes") or "").strip()
        terms = (data.get("terms") or "").strip()
        invoice_date_str = data.get("invoice_date", date.today().isoformat())
        due_date_str = data.get("due_date")
        items_raw = data.get("items", [])

        if isinstance(invoice_date_str, str):
            try:
                inv_date = datetime.strptime(invoice_date_str, "%Y-%m-%d").date()
            except ValueError:
                inv_date = date.today()
        else:
            inv_date = date.today()

        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                due_date = None

        if not customer_name:
            return jsonify({"error": "Customer name is required"}), 400
        if not items_raw:
            return jsonify({"error": "At least one item is required"}), 400

        if isinstance(items_raw, str):
            try:
                items_raw = json.loads(items_raw)
            except json.JSONDecodeError:
                items_raw = []

        customer_email = data.get("customer_email", "").strip()

        customer = None
        if customer_id:
            customer = db.session.get(Customer, int(customer_id))
        elif customer_mobile:
            customer = Customer.query.filter_by(mobile=customer_mobile).first()

        if not customer:
            customer = Customer(
                name=customer_name, mobile=customer_mobile, email=customer_email,
                address=customer_address, state=customer_state,
                state_code=customer_state_code, gstin=customer_gstin,
            )
            db.session.add(customer)
            db.session.flush()
        elif customer_email and not customer.email:
            customer.email = customer_email

        invoice = Invoice(
            invoice_number=generate_invoice_number(),
            customer_id=customer.id, user_id=current_user.id,
            invoice_date=inv_date, due_date=due_date, status="confirmed",
            customer_name=customer_name or customer.name,
            customer_mobile=customer_mobile or customer.mobile,
            customer_address=customer_address or customer.address,
            customer_state=customer_state or customer.state,
            customer_state_code=customer_state_code,
            customer_gstin=customer_gstin or customer.gstin,
            payment_method=payment_method, payment_reference=payment_reference,
            notes=notes, terms=terms,
        )

        gst_items = []
        for item_data in items_raw:
            product = None
            pid = item_data.get("product_id")
            if pid:
                product = db.session.get(Product, int(pid))

            qty = int(item_data.get("qty", 1))
            price = float(item_data.get("price", 0))
            discount = float(item_data.get("discount", 0))
            gst_rate = float(item_data.get("gst_rate", 18))

            if product and not current_user.has_permission("edit_price"):
                price = product.selling_price

            gst_items.append({"qty": qty, "price": price, "discount": discount, "gst_rate": gst_rate})

            item = InvoiceItem(
                product_id=product.id if product else None,
                product_name=product.name if product else item_data.get("product_name", ""),
                hsn=product.hsn if product else item_data.get("hsn", ""),
                qty=qty, unit=product.unit if product else item_data.get("unit", "Pcs"),
                price=price, discount=discount, gst_rate=gst_rate,
            )
            invoice.items.append(item)

            if product:
                if product.current_stock < qty:
                    if not allow_out_of_stock:
                        if request.is_json:
                            return jsonify({"error": f"Insufficient stock for {product.name}. Available: {product.current_stock}"}), 400
                        flash(f"Insufficient stock for {product.name}. Available: {product.current_stock}", "danger")
                        return redirect(url_for("new_invoice"))
                    else:
                        flash(f"Warning: Only {product.current_stock} units available for {product.name}. Selling {qty} units will result in negative stock.", "warning")
                product.current_stock -= qty
                product.last_sale = datetime.utcnow()
                movement = StockMovement(
                    product_id=product.id, movement_type="sale", quantity=-qty,
                    reference_type="invoice", notes=f"Sale via {invoice.invoice_number}",
                    user_id=current_user.id,
                )
                db.session.add(movement)

        gst_result = calculate_gst(customer_state_code, gst_items, company_state_code)

        for i, item in enumerate(invoice.items):
            gi = gst_items[i]
            item.taxable_value = gi.get("taxable_value", 0)
            item.cgst = gi.get("cgst", 0)
            item.sgst = gi.get("sgst", 0)
            item.igst = gi.get("igst", 0)
            item.total = gi.get("total", 0)

        invoice.subtotal = sum(i.price * i.qty for i in invoice.items)
        invoice.total_discount = gst_result["total_discount"]
        invoice.total_taxable = gst_result["total_taxable"]
        invoice.total_cgst = gst_result["total_cgst"]
        invoice.total_sgst = gst_result["total_sgst"]
        invoice.total_igst = gst_result["total_igst"]
        invoice.round_off = gst_result["round_off"]
        invoice.grand_total = gst_result["grand_total"]
        invoice.is_intra_state = gst_result["is_intra_state"]

        if payment_method and payment_method != "none":
            amount_paid_str = data.get("amount_paid")
            try:
                invoice.amount_paid = float(amount_paid_str) if amount_paid_str not in (None, "") else 0.0
            except (ValueError, TypeError):
                invoice.amount_paid = 0.0
            invoice.amount_paid = min(invoice.amount_paid, invoice.grand_total)

        db.session.add(invoice)
        db.session.commit()

        if payment_method and payment_method != "none" and invoice.amount_paid > 0:
            payment = Payment(
                invoice_id=invoice.id, amount=invoice.amount_paid,
                payment_method=payment_method, reference_number=payment_reference,
                user_id=current_user.id,
            )
            db.session.add(payment)
            db.session.commit()

        log_audit("create_invoice", f"Invoice {invoice.invoice_number} created for {invoice.customer_name} - Rs.{invoice.grand_total}")

        notif = Notification(
            user_id=current_user.id, title="Invoice Generated",
            message=f"Invoice {invoice.invoice_number} for Rs.{invoice.grand_total:.2f}",
            notification_type="success",
        )
        db.session.add(notif)
        db.session.commit()

        if request.is_json:
            return jsonify({
                "success": True, "invoice_id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "redirect": url_for("invoice_preview", inv_id=invoice.id),
            })
        return redirect(url_for("invoice_preview", inv_id=invoice.id))

    @app.route("/invoices")
    @login_required
    def invoice_history():
        page = request.args.get("page", 1, type=int)
        status = request.args.get("status", "")
        search = request.args.get("q", "").strip()
        payment_status = request.args.get("payment_status", "")
        date_from = request.args.get("date_from", "")
        date_to = request.args.get("date_to", "")
        sales_person_id = request.args.get("sales_person", "")

        base_query = Invoice.query
        if not current_user.is_admin:
            base_query = base_query.filter_by(user_id=current_user.id)

        if status:
            base_query = base_query.filter(Invoice.status == status)
        if search:
            base_query = base_query.filter(
                or_(
                    Invoice.invoice_number.ilike(f"%{search}%"),
                    Invoice.customer_name.ilike(f"%{search}%"),
                    Invoice.customer_mobile.ilike(f"%{search}%"),
                    Invoice.customer_gstin.ilike(f"%{search}%"),
                )
            )
        if date_from:
            try:
                base_query = base_query.filter(Invoice.invoice_date >= datetime.strptime(date_from, "%Y-%m-%d").date())
            except ValueError:
                pass
        if date_to:
            try:
                base_query = base_query.filter(Invoice.invoice_date <= datetime.strptime(date_to, "%Y-%m-%d").date())
            except ValueError:
                pass
        if sales_person_id:
            try:
                base_query = base_query.filter(Invoice.user_id == int(sales_person_id))
            except ValueError:
                pass

        stats_query = base_query
        total_invoices = stats_query.count()
        revenue_row = stats_query.with_entities(
            db.func.coalesce(db.func.sum(Invoice.grand_total), 0.0)
        ).first()
        total_revenue = revenue_row[0] if revenue_row else 0.0
        paid_count = stats_query.filter(
            Invoice.status != "cancelled",
            Invoice.amount_paid >= Invoice.grand_total - 0.01
        ).count()
        pending_row = stats_query.filter(
            Invoice.status != "cancelled",
            Invoice.grand_total > Invoice.amount_paid + 0.01
        ).with_entities(db.func.coalesce(db.func.sum(Invoice.grand_total - Invoice.amount_paid), 0.0)).first()
        total_pending = pending_row[0] if pending_row else 0.0

        if payment_status == "paid":
            base_query = base_query.filter(Invoice.status != "cancelled").filter(Invoice.amount_paid >= Invoice.grand_total - 0.01)
        elif payment_status == "pending":
            base_query = base_query.filter(Invoice.status != "cancelled").filter(Invoice.amount_paid < 0.01)
        elif payment_status == "partial":
            base_query = base_query.filter(Invoice.status != "cancelled").filter(Invoice.amount_paid > 0.01, Invoice.amount_paid < Invoice.grand_total - 0.01)

        sales_users = User.query.filter(User.role.in_(["admin", "sales"]), User.is_active == True).order_by(User.full_name).all()
        invoices = base_query.order_by(desc(Invoice.created_at)).paginate(page=page, per_page=25)

        return render_template(
            "sales/invoice_history.html",
            invoices=invoices, search=search, status=status,
            payment_status=payment_status, date_from=date_from,
            date_to=date_to, sales_person_id=sales_person_id,
            sales_users=sales_users,
            stats={"total": total_invoices, "revenue": total_revenue, "pending": total_pending, "paid_count": paid_count},
            today=date.today(),
        )

    @app.route("/invoices/<int:inv_id>")
    @login_required
    def invoice_preview(inv_id):
        invoice = db.session.get(Invoice, inv_id)
        if not invoice:
            abort(404)
        return render_template("billing/invoice_preview.html", invoice=invoice,
                               amount_words=amount_to_words(invoice.grand_total))

    @app.route("/invoices/<int:inv_id>/print")
    @login_required
    def print_invoice(inv_id):
        invoice = db.session.get(Invoice, inv_id)
        if not invoice:
            abort(404)
        company = current_app.config.get("COMPANY", {})
        return render_template("billing/print_invoice.html", invoice=invoice,
                               amount_words=amount_to_words(invoice.grand_total),
                               copy_label="INVOICE", company=company)

    @app.route("/invoices/<int:inv_id>/cancel", methods=["POST"])
    @login_required
    def cancel_invoice(inv_id):
        if not current_user.has_permission("cancel_invoice"):
            abort(403)
        invoice = db.session.get(Invoice, inv_id)
        if invoice and invoice.status != "cancelled":
            invoice.status = "cancelled"
            invoice.amount_paid = 0.0
            for item in invoice.items:
                if item.product_id:
                    product = db.session.get(Product, item.product_id)
                    if product:
                        product.current_stock += item.qty
                        movement = StockMovement(
                            product_id=product.id, movement_type="return",
                            quantity=item.qty, reference_type="invoice_cancel",
                            reference_id=invoice.id,
                            notes=f"Cancelled invoice {invoice.invoice_number}",
                            user_id=current_user.id,
                        )
                        db.session.add(movement)
            Payment.query.filter_by(invoice_id=invoice.id).delete()
            db.session.commit()
            log_audit("cancel_invoice", f"Cancelled invoice: {invoice.invoice_number}")
            flash("Invoice cancelled, stock restored, and payments cleared.", "warning")
        return redirect(url_for("invoice_preview", inv_id=inv_id))

    @app.route("/invoices/<int:inv_id>/delete", methods=["POST"])
    @login_required
    def delete_invoice(inv_id):
        if not current_user.has_permission("delete_invoice"):
            abort(403)
        invoice = db.session.get(Invoice, inv_id)
        if invoice and invoice.status != "cancelled":
            for item in invoice.items:
                if item.product_id:
                    product = db.session.get(Product, item.product_id)
                    if product:
                        product.current_stock += item.qty
                        movement = StockMovement(
                            product_id=product.id, movement_type="return",
                            quantity=item.qty, reference_type="invoice_delete",
                            reference_id=invoice.id,
                            notes=f"Deleted invoice {invoice.invoice_number}",
                            user_id=current_user.id,
                        )
                        db.session.add(movement)
            log_audit("delete_invoice", f"Deleted invoice: {invoice.invoice_number}")
            db.session.delete(invoice)
            db.session.commit()
            flash("Invoice deleted and stock restored.", "success")
        return redirect(url_for("invoice_history"))

    @app.route("/invoices/<int:inv_id>/payment", methods=["POST"])
    @login_required
    def add_payment(inv_id):
        invoice = db.session.get(Invoice, inv_id)
        if not invoice:
            abort(404)
        try:
            amount = float(request.form.get("amount", 0) or 0)
        except (ValueError, TypeError):
            amount = 0.0
        method = request.form.get("payment_method", "cash")
        reference = (request.form.get("reference_number", "") or "").strip()
        balance = invoice.grand_total - invoice.amount_paid
        if amount <= 0:
            flash("Invalid payment amount.", "danger")
        elif amount > balance + 0.01:
            flash(f"Amount exceeds balance due of Rs.{balance:.2f}.", "danger")
        else:
            payment = Payment(
                invoice_id=invoice.id, amount=amount,
                payment_method=method, reference_number=reference,
                user_id=current_user.id,
            )
            invoice.amount_paid += amount
            if invoice.amount_paid >= invoice.grand_total - 0.01:
                invoice.status = "paid"
                invoice.amount_paid = invoice.grand_total
            db.session.add(payment)
            db.session.commit()
            log_audit("add_payment", f"Payment of Rs.{amount} for {invoice.invoice_number}")
            flash(f"Payment of Rs.{amount:.2f} recorded.", "success")
        return redirect(url_for("invoice_preview", inv_id=inv_id))

    @app.route("/api/invoices/<int:inv_id>/payment", methods=["POST"])
    @login_required
    def api_add_payment(inv_id):
        invoice = db.session.get(Invoice, inv_id)
        if not invoice:
            return jsonify({"error": "Invoice not found"}), 404
        data = request.get_json(silent=True) or {}
        try:
            amount = float(data.get("amount", 0) or 0)
        except (ValueError, TypeError):
            amount = 0.0
        method = data.get("payment_method", "cash")
        reference = (data.get("payment_reference", "") or "").strip()
        balance = invoice.grand_total - invoice.amount_paid
        if amount <= 0:
            return jsonify({"error": "Invalid payment amount"}), 400
        if amount > balance + 0.01:
            return jsonify({"error": f"Amount exceeds balance due of Rs.{balance:.2f}"}), 400
        payment = Payment(
            invoice_id=invoice.id, amount=amount,
            payment_method=method, reference_number=reference,
            user_id=current_user.id,
        )
        invoice.amount_paid += amount
        if invoice.amount_paid >= invoice.grand_total - 0.01:
            invoice.status = "paid"
            invoice.amount_paid = invoice.grand_total
        db.session.add(payment)
        db.session.commit()
        log_audit("add_payment", f"Payment of Rs.{amount} for {invoice.invoice_number}")
        return jsonify({"success": True, "message": f"Payment of Rs.{amount:.2f} recorded."})

    @app.route("/api/invoices/<int:inv_id>/cancel", methods=["POST"])
    @login_required
    def api_cancel_invoice(inv_id):
        if not current_user.has_permission("cancel_invoice"):
            return jsonify({"error": "Permission denied"}), 403
        invoice = db.session.get(Invoice, inv_id)
        if not invoice:
            return jsonify({"error": "Invoice not found"}), 404
        if invoice.status != "cancelled":
            invoice.status = "cancelled"
            invoice.amount_paid = 0.0
            for item in invoice.items:
                if item.product_id:
                    product = db.session.get(Product, item.product_id)
                    if product:
                        product.current_stock += item.qty
                        movement = StockMovement(
                            product_id=product.id, movement_type="return",
                            quantity=item.qty, reference_type="invoice_cancel",
                            reference_id=invoice.id,
                            notes=f"Cancelled invoice {invoice.invoice_number}",
                            user_id=current_user.id,
                        )
                        db.session.add(movement)
            Payment.query.filter_by(invoice_id=invoice.id).delete()
            db.session.commit()
            log_audit("cancel_invoice", f"Cancelled invoice: {invoice.invoice_number}")
        return jsonify({"success": True, "message": "Invoice cancelled."})

    # ------------------------------------------------------------------
    # PDF GENERATION
    # ------------------------------------------------------------------

    @app.route("/invoices/<int:inv_id>/pdf/<copy_type>")
    @login_required
    def download_invoice_pdf(inv_id, copy_type):
        invoice = db.session.get(Invoice, inv_id)
        if not invoice:
            abort(404)
        if copy_type not in ("owner", "customer", "gst"):
            abort(400)

        from services.invoice_pdf_service import generate_invoice_pdf, COMPANY as PDF_COMPANY

        settings_company = PDF_COMPANY.copy()
        for key, setting_key in [("name", "company_name"), ("gstin", "company_gstin"), ("address", "company_address")]:
            val = get_setting(setting_key)
            if val:
                settings_company[key] = val

        pdf_buf = generate_invoice_pdf(invoice, copy_type, settings_company)

        copy_labels = {"owner": "Owner", "customer": "Customer", "gst": "GST_Tax"}
        filename = f"{invoice.invoice_number}_{copy_labels[copy_type]}_Copy.pdf"

        log_audit("download_pdf", f"Downloaded {copy_type} copy PDF for {invoice.invoice_number}")

        return send_file(pdf_buf, mimetype="application/pdf", as_attachment=True, download_name=filename)

    @app.route("/invoices/<int:inv_id>/pdf/all")
    @login_required
    def download_all_pdfs(inv_id):
        invoice = db.session.get(Invoice, inv_id)
        if not invoice:
            abort(404)

        from services.invoice_pdf_service import generate_owner_copy, generate_customer_copy, generate_gst_copy, COMPANY as PDF_COMPANY
        from PyPDF2 import PdfReader, PdfWriter

        settings_company = PDF_COMPANY.copy()
        for key, setting_key in [("name", "company_name"), ("gstin", "company_gstin"), ("address", "company_address")]:
            val = get_setting(setting_key)
            if val:
                settings_company[key] = val

        buf = io.BytesIO()
        writer = PdfWriter()
        for ct_fn in [generate_owner_copy, generate_customer_copy, generate_gst_copy]:
            pdf_buf = ct_fn(invoice, settings_company)
            reader = PdfReader(pdf_buf)
            for page in reader.pages:
                writer.add_page(page)
        writer.write(buf)
        buf.seek(0)

        log_audit("download_all_pdfs", f"Downloaded all 3 PDFs for {invoice.invoice_number}")

        return send_file(buf, mimetype="application/pdf", as_attachment=True,
                         download_name=f"{invoice.invoice_number}_All_Copies.pdf")

    @app.route("/invoices/<int:inv_id>/print/<copy_type>")
    @login_required
    def print_invoice_pdf(inv_id, copy_type):
        invoice = db.session.get(Invoice, inv_id)
        if not invoice:
            abort(404)
        if copy_type not in ("owner", "customer", "gst"):
            abort(400)

        from services.invoice_pdf_service import generate_invoice_pdf, COMPANY as PDF_COMPANY

        settings_company = PDF_COMPANY.copy()
        for key, setting_key in [("name", "company_name"), ("gstin", "company_gstin"), ("address", "company_address")]:
            val = get_setting(setting_key)
            if val:
                settings_company[key] = val

        pdf_buf = generate_invoice_pdf(invoice, copy_type, settings_company)
        log_audit("print_pdf", f"Printed {copy_type} copy PDF for {invoice.invoice_number}")

        return send_file(pdf_buf, mimetype="application/pdf", as_attachment=False)

    @app.route("/invoices/<int:inv_id>/email", methods=["POST"])
    @login_required
    def email_invoice(inv_id):
        invoice = db.session.get(Invoice, inv_id)
        if not invoice:
            if request.is_json:
                return jsonify({"error": "Invoice not found"}), 404
            flash("Invoice not found.", "danger")
            return redirect(url_for("invoice_history"))

        data = request.get_json() if request.is_json else None
        recipient = ""
        if data:
            recipient = (data.get("email") or "").strip()
        else:
            recipient = (request.form.get("email") or "").strip()

        if not recipient:
            if invoice.customer_id:
                customer = db.session.get(Customer, invoice.customer_id)
                if customer:
                    recipient = customer.email or ""

        if not recipient:
            msg = "No email address found for this customer."
            if request.is_json:
                return jsonify({"error": msg}), 400
            flash(msg, "danger")
            return redirect(url_for("invoice_preview", inv_id=inv_id))

        log_audit("email_invoice", f"Emailed invoice {invoice.invoice_number} to {recipient}")

        if request.is_json:
            return jsonify({"success": True, "message": f"Invoice {invoice.invoice_number} sent to {recipient}"})

        flash(f"Invoice {invoice.invoice_number} emailed to {recipient}.", "success")
        return redirect(url_for("invoice_preview", inv_id=inv_id))
