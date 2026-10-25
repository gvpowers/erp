"""
GV Powers ERP - Admin Routes
Dashboard, users, profile, settings, audit logs, backup.
"""

import os
import shutil
import subprocess
from datetime import datetime, date
from collections import defaultdict

from flask import (
    render_template, request, redirect, url_for, flash,
    send_file, abort, jsonify, current_app,
)
from flask_login import login_required, current_user
from sqlalchemy import func, desc

from models import (
    db, User, Customer, Product, Category, Supplier,
    Invoice, InvoiceItem, PurchaseOrder, Settings, AuditLog, Notification, GSTMaster,
)
from models import StockMovement
from services.audit_service import log_audit, get_setting, set_setting


def register(app):

    # ------------------------------------------------------------------
    # DASHBOARD
    # ------------------------------------------------------------------

    @app.route("/dashboard")
    @login_required
    def dashboard():
        if not current_user.is_admin:
            return redirect(url_for("new_invoice"))
        today = date.today()
        month_start = today.replace(day=1)

        total_sales = db.session.query(func.coalesce(func.sum(Invoice.grand_total), 0)).filter(
            Invoice.invoice_date == today, Invoice.status != "cancelled"
        ).scalar()
        monthly_sales = db.session.query(func.coalesce(func.sum(Invoice.grand_total), 0)).filter(
            Invoice.invoice_date >= month_start, Invoice.status != "cancelled"
        ).scalar()
        total_customers = Customer.query.count()
        total_products = Product.query.count()
        total_invoices = Invoice.query.filter(Invoice.status != "cancelled").count()
        low_stock_count = Product.query.filter(
            Product.current_stock <= Product.min_stock, Product.is_active == True
        ).count()
        total_revenue = db.session.query(func.coalesce(func.sum(Invoice.grand_total), 0)).filter(
            Invoice.status != "cancelled"
        ).scalar()

        recent_invoices = Invoice.query.order_by(desc(Invoice.created_at)).limit(10).all()

        monthly_data = []
        for i in range(11, -1, -1):
            m = today.month - i
            y = today.year
            while m <= 0:
                m += 12
                y -= 1
            ms = date(y, m, 1)
            me = date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)
            val = db.session.query(func.coalesce(func.sum(Invoice.grand_total), 0)).filter(
                Invoice.invoice_date >= ms, Invoice.invoice_date < me,
                Invoice.status != "cancelled"
            ).scalar()
            monthly_data.append({"month": ms.strftime("%b"), "total": float(val)})

        top_products = db.session.query(
            InvoiceItem.product_name, func.sum(InvoiceItem.qty).label("total_qty")
        ).join(Invoice).filter(
            Invoice.status != "cancelled"
        ).group_by(InvoiceItem.product_name).order_by(desc("total_qty")).limit(5).all()

        return render_template("admin/dashboard.html",
                               total_sales=float(total_sales),
                               today_sales=float(total_sales),
                               monthly_sales=float(monthly_sales),
                               total_customers=total_customers,
                               total_products=total_products,
                               total_invoices=total_invoices,
                               low_stock_count=low_stock_count,
                               low_stock_alerts=low_stock_count,
                               total_revenue=float(total_revenue),
                               recent_invoices=recent_invoices,
                               monthly_data=monthly_data,
                               top_products=top_products,
                               now_date=today.strftime("%d %B %Y"))

    # ------------------------------------------------------------------
    # USERS
    # ------------------------------------------------------------------

    @app.route("/users")
    @login_required
    def users_list():
        if not current_user.is_admin:
            abort(403)
        users = User.query.order_by(User.created_at.desc()).all()
        return render_template("admin/users.html", users=users)

    @app.route("/users/create", methods=["POST"])
    @login_required
    def create_user():
        if not current_user.is_admin:
            abort(403)
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        full_name = request.form.get("full_name", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "sales")

        if not username or not full_name or not password:
            flash("Username, full name, and password are required.", "danger")
            return redirect(url_for("users_list"))

        if User.query.filter_by(username=username).first():
            flash("Username already exists.", "danger")
            return redirect(url_for("users_list"))

        if email and User.query.filter_by(email=email).first():
            flash("Email already exists.", "danger")
            return redirect(url_for("users_list"))

        user = User(username=username, email=email or None, full_name=full_name, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        log_audit("create_user", f"Created user: {username} ({role})")
        flash(f"User '{username}' created successfully.", "success")
        return redirect(url_for("users_list"))

    @app.route("/users/<int:user_id>/toggle", methods=["POST"])
    @login_required
    def toggle_user(user_id):
        if not current_user.is_admin:
            abort(403)
        user = db.session.get(User, user_id)
        if user and user.id != current_user.id:
            user.is_active = not user.is_active
            db.session.commit()
            status = "activated" if user.is_active else "deactivated"
            log_audit("toggle_user", f"User {user.username} {status}")
            flash(f"User {user.username} {status}.", "success")
        return redirect(url_for("users_list"))

    @app.route("/users/<int:user_id>/delete", methods=["POST"])
    @login_required
    def delete_user(user_id):
        if not current_user.is_admin:
            abort(403)
        user = db.session.get(User, user_id)
        if user and user.id != current_user.id:
            if user.is_admin:
                admin_count = User.query.filter_by(role="admin", is_active=True).count()
                if admin_count <= 1:
                    flash("Cannot delete the last admin user.", "danger")
                    return redirect(url_for("users_list"))
            log_audit("delete_user", f"Deleted user: {user.username}")
            db.session.delete(user)
            db.session.commit()
            flash("User deleted.", "success")
        return redirect(url_for("users_list"))

    @app.route("/users/<int:user_id>/edit", methods=["POST"])
    @login_required
    def edit_user(user_id):
        if not current_user.is_admin:
            abort(403)
        user = db.session.get(User, user_id)
        if not user:
            abort(404)
        user.full_name = (request.form.get("full_name", "") or user.full_name or "").strip()
        new_email = (request.form.get("email", "") or "").strip() or None
        if new_email and new_email != user.email:
            existing = User.query.filter_by(email=new_email).first()
            if existing and existing.id != user.id:
                flash("Email already in use by another user.", "danger")
                return redirect(url_for("users_list"))
        user.email = new_email
        user.role = request.form.get("role", user.role)
        password = request.form.get("password", "").strip()
        if password:
            user.set_password(password)
        db.session.commit()
        log_audit("edit_user", f"Edited user: {user.username}")
        flash("User updated.", "success")
        return redirect(url_for("users_list"))

    @app.route("/profile", methods=["GET", "POST"])
    @login_required
    def profile():
        if request.method == "POST":
            current_user.full_name = (request.form.get("full_name", "") or current_user.full_name or "").strip()
            current_user.email = (request.form.get("email", "") or current_user.email or "").strip()
            new_pass = request.form.get("new_password", "").strip()
            if new_pass:
                current_pass = request.form.get("current_password", "")
                if current_user.check_password(current_pass):
                    current_user.set_password(new_pass)
                    flash("Password updated.", "success")
                else:
                    flash("Current password is incorrect.", "danger")
                    return render_template("admin/profile.html")
            db.session.commit()
            flash("Profile updated.", "success")
        return render_template("admin/profile.html")

    # ------------------------------------------------------------------
    # SETTINGS
    # ------------------------------------------------------------------

    @app.route("/settings", methods=["GET", "POST"])
    @login_required
    def settings_page():
        if not current_user.is_admin:
            abort(403)
        if request.method == "POST":
            keys = [
                "company_name", "gstin", "state", "state_code",
                "address", "phone", "email",
                "invoice_terms", "quotation_terms", "default_gst_rate",
                "theme",
            ]
            for key in keys:
                val = request.form.get(key)
                if val is not None:
                    set_setting(key, val.strip())
            theme_val = request.form.get("theme")
            if theme_val:
                current_user.theme = theme_val
            log_audit("update_settings", "System settings updated")
            flash("Settings updated successfully.", "success")
            return redirect(url_for("settings_page"))

        settings = {s.key: s.value for s in Settings.query.all()}
        return render_template("admin/settings.html", settings=settings)

    @app.route("/settings/theme", methods=["POST"])
    @login_required
    def change_theme():
        if not current_user.is_admin:
            abort(403)
        theme = request.form.get("theme", "dark")
        current_user.theme = theme
        set_setting("theme", theme)
        db.session.commit()
        return jsonify({"success": True, "theme": theme})

    # ------------------------------------------------------------------
    # AUDIT LOGS
    # ------------------------------------------------------------------

    @app.route("/audit-logs")
    @login_required
    def audit_logs():
        if not current_user.is_admin:
            abort(403)
        page = request.args.get("page", 1, type=int)
        action_filter = request.args.get("action", "")
        query = AuditLog.query
        if action_filter:
            query = query.filter(AuditLog.action.ilike(f"%{action_filter}%"))
        logs = query.order_by(desc(AuditLog.created_at)).paginate(page=page, per_page=50)
        return render_template("admin/audit_logs.html", logs=logs, action_filter=action_filter)

    # ------------------------------------------------------------------
    # BACKUP & RESTORE
    # ------------------------------------------------------------------

    @app.route("/backup")
    @login_required
    def backup_page():
        if not current_user.is_admin:
            abort(403)
        backups = []
        backup_dir = current_app.config["BACKUP_FOLDER"]
        if os.path.exists(backup_dir):
            for f in sorted(os.listdir(backup_dir), reverse=True):
                path = os.path.join(backup_dir, f)
                backups.append({
                    "name": f,
                    "size": os.path.getsize(path),
                    "date": datetime.fromtimestamp(os.path.getmtime(path)),
                })
        return render_template("admin/backup.html", backups=backups)

    @app.route("/backup/create", methods=["POST"])
    @login_required
    def create_backup():
        if not current_user.is_admin:
            abort(403)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        db_uri = current_app.config["SQLALCHEMY_DATABASE_URI"]
        backup_dir = current_app.config["BACKUP_FOLDER"]
        os.makedirs(backup_dir, exist_ok=True)

        if "sqlite" in db_uri:
            db_path = db_uri.replace("sqlite:///", "")
            if not os.path.isabs(db_path):
                db_path = os.path.join(current_app.config["BASE_DIR"], db_path)
            backup_name = f"backup_{timestamp}.db"
            backup_path = os.path.join(backup_dir, backup_name)
            shutil.copy2(db_path, backup_path)
        else:
            backup_name = f"backup_{timestamp}.sql"
            backup_path = os.path.join(backup_dir, backup_name)
            try:
                with open(backup_path, "w") as f:
                    subprocess.run(
                        ["pg_dump", db_uri],
                        stdout=f, stderr=subprocess.PIPE, timeout=120, check=False,
                    )
            except Exception as e:
                flash(f"Backup failed: {e}", "danger")
                return redirect(url_for("backup_page"))

        log_audit("create_backup", f"Backup created: {backup_name}")
        notif = Notification(
            user_id=current_user.id,
            title="Backup Completed",
            message=f"Backup {backup_name} created successfully.",
            notification_type="success",
        )
        db.session.add(notif)
        db.session.commit()
        flash(f"Backup '{backup_name}' created.", "success")
        return redirect(url_for("backup_page"))

    @app.route("/backup/download/<filename>")
    @login_required
    def download_backup(filename):
        if not current_user.is_admin:
            abort(403)
        safe_name = os.path.basename(filename)
        path = os.path.join(current_app.config["BACKUP_FOLDER"], safe_name)
        if os.path.exists(path):
            return send_file(path, as_attachment=True)
        abort(404)

    @app.route("/backup/restore", methods=["POST"])
    @login_required
    def restore_backup():
        if not current_user.is_admin:
            abort(403)
        filename = request.form.get("filename", "")
        safe_name = os.path.basename(filename)
        path = os.path.join(current_app.config["BACKUP_FOLDER"], safe_name)
        if not os.path.exists(path):
            flash("Backup file not found.", "danger")
            return redirect(url_for("backup_page"))
        db_uri = current_app.config["SQLALCHEMY_DATABASE_URI"]
        if "sqlite" in db_uri:
            db_path = db_uri.replace("sqlite:///", "")
            if not os.path.isabs(db_path):
                db_path = os.path.join(current_app.config["BASE_DIR"], db_path)
            shutil.copy2(path, db_path)
        else:
            try:
                subprocess.run(
                    ["psql", db_uri, "-f", path],
                    capture_output=True, timeout=120, check=False,
                )
            except Exception as e:
                flash(f"Restore failed: {e}", "danger")
                return redirect(url_for("backup_page"))
        log_audit("restore_backup", f"Restored from: {filename}")
        flash(f"Restored from '{filename}'. Please restart the application.", "warning")
        return redirect(url_for("backup_page"))
