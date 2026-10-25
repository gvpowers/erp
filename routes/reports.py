"""
GV Powers ERP - Reports Routes
Sales, GST, inventory, profit, customer reports + Excel/CSV exports.
"""

import io
import csv
from datetime import datetime, date
from collections import defaultdict

from flask import render_template, request, redirect, url_for, flash, send_file, abort
from flask_login import login_required, current_user
from sqlalchemy import func, desc, extract

from models import db, Invoice, InvoiceItem, Product, Customer
from services.audit_service import log_audit


def register(app):

    @app.route("/reports")
    @login_required
    def reports_page():
        if not current_user.is_admin:
            abort(403)
        return render_template("reports/reports.html")

    @app.route("/reports/sales")
    @login_required
    def sales_report():
        if not current_user.is_admin:
            abort(403)
        start_date = request.args.get("start_date", date.today().replace(day=1).isoformat())
        end_date = request.args.get("end_date", date.today().isoformat())
        try:
            sd = datetime.strptime(start_date, "%Y-%m-%d").date()
            ed = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            sd = date.today().replace(day=1)
            ed = date.today()

        invoices = Invoice.query.filter(
            Invoice.invoice_date >= sd, Invoice.invoice_date <= ed,
            Invoice.status != "cancelled"
        ).order_by(Invoice.invoice_date).all()

        total = sum(i.grand_total for i in invoices)
        total_tax = sum(i.total_cgst + i.total_sgst + i.total_igst for i in invoices)
        total_discount = sum(i.total_discount for i in invoices)

        daily_data = defaultdict(float)
        for inv in invoices:
            daily_data[inv.invoice_date.isoformat()] += inv.grand_total

        return render_template("reports/sales_report.html",
                               invoices=invoices, total=total, total_tax=total_tax,
                               total_discount=total_discount, start_date=start_date,
                               end_date=end_date, daily_data=dict(daily_data))

    @app.route("/reports/gst")
    @login_required
    def gst_report():
        if not current_user.is_admin:
            abort(403)
        try:
            month = int(request.args.get("month", datetime.now().month))
            year = int(request.args.get("year", datetime.now().year))
        except (ValueError, TypeError):
            month = datetime.now().month
            year = datetime.now().year

        invoices = Invoice.query.filter(
            extract("month", Invoice.invoice_date) == month,
            extract("year", Invoice.invoice_date) == year,
            Invoice.status != "cancelled"
        ).all()

        intra_state_invoices = [inv for inv in invoices if inv.is_intra_state]
        inter_state_invoices = [inv for inv in invoices if not inv.is_intra_state]
        b2b_invoices = [inv for inv in invoices if inv.customer_gstin]
        b2c_invoices = [inv for inv in invoices if not inv.customer_gstin]

        total_taxable = sum(inv.total_taxable for inv in invoices)
        total_cgst = sum(inv.total_cgst for inv in invoices)
        total_sgst = sum(inv.total_sgst for inv in invoices)
        total_igst = sum(inv.total_igst for inv in invoices)

        hsn_summary = defaultdict(lambda: {"qty": 0, "taxable_value": 0.0, "cgst": 0.0, "sgst": 0.0, "igst": 0.0})
        for inv in invoices:
            for item in inv.items:
                h = item.hsn or "N/A"
                hsn_summary[h]["qty"] += item.qty
                hsn_summary[h]["taxable_value"] += item.taxable_value
                hsn_summary[h]["cgst"] += item.cgst
                hsn_summary[h]["sgst"] += item.sgst
                hsn_summary[h]["igst"] += item.igst

        return render_template("reports/gst_report.html",
                               invoices=invoices, hsn_summary=dict(hsn_summary),
                               month=month, year=year,
                               intra_state_invoices=intra_state_invoices,
                               inter_state_invoices=inter_state_invoices,
                               b2b_invoices=b2b_invoices, b2c_invoices=b2c_invoices,
                               total_taxable=total_taxable, total_cgst=total_cgst,
                               total_sgst=total_sgst, total_igst=total_igst,
                               grand_total=total_taxable + total_cgst + total_sgst + total_igst,
                               total_invoice_count=len(invoices))

    @app.route("/reports/inventory")
    @login_required
    def inventory_report():
        if not current_user.is_admin:
            abort(403)
        products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
        total_value = sum(p.current_stock * p.purchase_price for p in products)
        low_stock = [p for p in products if p.is_low_stock]
        out_of_stock = [p for p in products if p.current_stock <= 0]
        total_products = len(products)
        total_stock = sum(p.current_stock for p in products)
        low_stock_count = len(low_stock)
        out_of_stock_count = len(out_of_stock)
        never_sold = []
        category_data = []
        for cat in Category.query.order_by(Category.name).all():
            cat_products = Product.query.filter_by(category_id=cat.id, is_active=True).all()
            if cat_products:
                cat_value = sum(p.current_stock * p.purchase_price for p in cat_products)
                category_data.append({"name": cat.name, "value": round(cat_value, 2)})
        return render_template("reports/inventory_report.html",
                               products=products, total_value=total_value,
                               low_stock=low_stock, out_of_stock=out_of_stock,
                               total_products=total_products,
                               total_stock=total_stock,
                               low_stock_count=low_stock_count,
                               out_of_stock_count=out_of_stock_count,
                               never_sold=never_sold,
                               category_data=category_data)

    @app.route("/reports/profit")
    @login_required
    def profit_report():
        if not current_user.is_admin:
            abort(403)
        start_date = request.args.get("start_date", date.today().replace(day=1).isoformat())
        end_date = request.args.get("end_date", date.today().isoformat())
        try:
            sd = datetime.strptime(start_date, "%Y-%m-%d").date()
            ed = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            sd = date.today().replace(day=1)
            ed = date.today()

        invoices = Invoice.query.filter(
            Invoice.invoice_date >= sd, Invoice.invoice_date <= ed,
            Invoice.status != "cancelled"
        ).all()

        revenue = sum(i.grand_total for i in invoices)
        cost = 0.0
        invoice_costs = {}
        for inv in invoices:
            inv_cost = 0.0
            for item in inv.items:
                if item.product_id:
                    product = db.session.get(Product, item.product_id)
                    if product:
                        inv_cost += product.purchase_price * item.qty
            invoice_costs[inv.id] = inv_cost
            cost += inv_cost
        profit = revenue - cost

        return render_template("reports/profit_report.html",
                               revenue=revenue, cost=cost, profit=profit,
                               start_date=start_date, end_date=end_date,
                               invoices=invoices, invoice_costs=invoice_costs)

    @app.route("/reports/customers")
    @login_required
    def customer_report():
        if not current_user.is_admin:
            abort(403)
        customers = Customer.query.all()
        customer_data = []
        for c in customers:
            total = db.session.query(func.coalesce(func.sum(Invoice.grand_total), 0)).filter(
                Invoice.customer_id == c.id, Invoice.status != "cancelled"
            ).scalar()
            count = Invoice.query.filter_by(customer_id=c.id).filter(Invoice.status != "cancelled").count()
            customer_data.append({"customer": c, "total": float(total), "count": count})
        customer_data.sort(key=lambda x: x["total"], reverse=True)

        customer_chart_data = [
            {"customer": {"name": d["customer"].name}, "total": d["total"], "count": d["count"]}
            for d in customer_data
        ]

        return render_template("reports/customer_report.html", customer_data=customer_data,
                               customer_chart_data=customer_chart_data)

    # ------------------------------------------------------------------
    # EXPORTS
    # ------------------------------------------------------------------

    @app.route("/export/excel/<report_type>")
    @login_required
    def export_excel(report_type):
        if not current_user.is_admin:
            abort(403)
        output = io.BytesIO()
        try:
            import xlsxwriter
        except ImportError:
            flash("Excel export requires xlsxwriter. Please install it.", "danger")
            return redirect(url_for("reports_page"))
        workbook = xlsxwriter.Workbook(output)

        if report_type == "sales":
            ws = workbook.add_worksheet("Sales Report")
            headers = ["Invoice #", "Date", "Customer", "Subtotal", "Tax", "Total", "Status"]
            for col, h in enumerate(headers):
                ws.write(0, col, h)
            invoices = Invoice.query.filter(Invoice.status != "cancelled").order_by(desc(Invoice.invoice_date)).all()
            for row, inv in enumerate(invoices, 1):
                ws.write(row, 0, inv.invoice_number)
                ws.write(row, 1, str(inv.invoice_date))
                ws.write(row, 2, inv.customer_name or "")
                ws.write(row, 3, inv.total_taxable)
                ws.write(row, 4, inv.total_cgst + inv.total_sgst + inv.total_igst)
                ws.write(row, 5, inv.grand_total)
                ws.write(row, 6, inv.status)
        elif report_type == "inventory":
            ws = workbook.add_worksheet("Inventory Report")
            headers = ["Name", "SKU", "HSN", "Stock", "Min Stock", "Purchase Price", "Selling Price", "Value"]
            for col, h in enumerate(headers):
                ws.write(0, col, h)
            products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
            for row, p in enumerate(products, 1):
                ws.write(row, 0, p.name)
                ws.write(row, 1, p.sku or "")
                ws.write(row, 2, p.hsn or "")
                ws.write(row, 3, p.current_stock)
                ws.write(row, 4, p.min_stock)
                ws.write(row, 5, p.purchase_price)
                ws.write(row, 6, p.selling_price)
                ws.write(row, 7, p.current_stock * p.purchase_price)
        elif report_type == "customers":
            ws = workbook.add_worksheet("Customer Report")
            headers = ["Name", "Mobile", "Email", "City", "Total Purchases", "Invoices"]
            for col, h in enumerate(headers):
                ws.write(0, col, h)
            customers = Customer.query.all()
            for row, c in enumerate(customers, 1):
                total = db.session.query(func.coalesce(func.sum(Invoice.grand_total), 0)).filter(
                    Invoice.customer_id == c.id, Invoice.status != "cancelled"
                ).scalar()
                count = Invoice.query.filter_by(customer_id=c.id).filter(Invoice.status != "cancelled").count()
                ws.write(row, 0, c.name)
                ws.write(row, 1, c.mobile or "")
                ws.write(row, 2, c.email or "")
                ws.write(row, 3, c.city or "")
                ws.write(row, 4, float(total))
                ws.write(row, 5, count)
        else:
            abort(404)

        workbook.close()
        output.seek(0)
        log_audit("export_excel", f"Exported {report_type} report as Excel")
        return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         as_attachment=True, download_name=f"{report_type}_report_{date.today().isoformat()}.xlsx")

    @app.route("/export/csv/<report_type>")
    @login_required
    def export_csv(report_type):
        if not current_user.is_admin:
            abort(403)
        output = io.StringIO()
        writer = csv.writer(output)

        if report_type == "sales":
            writer.writerow(["Invoice #", "Date", "Customer", "Mobile", "Subtotal", "Tax", "Discount", "Total", "Status"])
            invoices = Invoice.query.filter(Invoice.status != "cancelled").order_by(desc(Invoice.invoice_date)).all()
            for inv in invoices:
                writer.writerow([
                    inv.invoice_number, str(inv.invoice_date), inv.customer_name or "",
                    inv.customer_mobile or "", f"{inv.total_taxable:.2f}",
                    f"{inv.total_cgst + inv.total_sgst + inv.total_igst:.2f}",
                    f"{inv.total_discount:.2f}", f"{inv.grand_total:.2f}", inv.status,
                ])
        elif report_type == "inventory":
            writer.writerow(["Name", "SKU", "Barcode", "HSN", "Brand", "Stock", "Min", "Max", "Purchase", "Selling", "GST%"])
            for p in Product.query.filter_by(is_active=True).order_by(Product.name).all():
                writer.writerow([p.name, p.sku or "", p.barcode or "", p.hsn or "", p.brand or "",
                               p.current_stock, p.min_stock, p.max_stock,
                               f"{p.purchase_price:.2f}", f"{p.selling_price:.2f}", p.gst_rate])
        else:
            abort(404)

        output.seek(0)
        log_audit("export_csv", f"Exported {report_type} report as CSV")
        return send_file(
            io.BytesIO(output.getvalue().encode("utf-8-sig")),
            mimetype="text/csv",
            as_attachment=True,
            download_name=f"{report_type}_report_{date.today().isoformat()}.csv",
        )
