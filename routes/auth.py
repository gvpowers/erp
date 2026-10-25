"""
GV Powers ERP - Auth Routes
Login, logout, index redirect.
"""

from datetime import datetime
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user

from models import db, User
from services.audit_service import log_audit


def register(app):

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            if current_user.is_admin:
                return redirect(url_for("dashboard"))
            return redirect(url_for("new_invoice"))
        return redirect(url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("index"))
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            remember = request.form.get("remember", False)
            user = User.query.filter_by(username=username).first()
            if user and user.check_password(password) and user.is_active:
                login_user(user, remember=bool(remember))
                user.last_login = datetime.utcnow()
                db.session.commit()
                log_audit("login", f"User {user.username} logged in")
                flash("Welcome back!", "success")
                if user.is_admin:
                    return redirect(url_for("dashboard"))
                return redirect(url_for("new_invoice"))
            flash("Invalid credentials.", "danger")
        return render_template("auth/login.html")

    @app.route("/logout", methods=["GET", "POST"])
    @login_required
    def logout():
        log_audit("logout", f"User {current_user.username} logged out")
        logout_user()
        flash("Logged out successfully.", "info")
        return redirect(url_for("login"))
