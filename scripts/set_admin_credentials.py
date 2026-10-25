"""
One-time production admin credential migration.

Usage:
  export ADMIN_USERNAME='gvpowers@admin'
  export ADMIN_PASSWORD='admin@gvpowerssalem'
  python scripts/set_admin_credentials.py

This updates/renames the existing admin account in the current database.
It does not create a second admin when an existing admin can be migrated.
"""
import os
from app import app, db, User

username = os.getenv("ADMIN_USERNAME", "gvpowers@admin").strip()
password = os.getenv("ADMIN_PASSWORD", "admin@gvpowerssalem")
email = os.getenv("ADMIN_EMAIL", "admin@gvpowers.in").strip()

if not username or not password:
    raise SystemExit("ADMIN_USERNAME and ADMIN_PASSWORD are required.")

with app.app_context():
    target = User.query.filter_by(username=username).first()
    admins = User.query.filter_by(role="admin").order_by(User.id.asc()).all()

    if target and target.role != "admin":
        raise SystemExit(
            f"Username {username!r} already belongs to a non-admin user; "
            "refusing to overwrite it."
        )

    if target:
        admin = target
    elif admins:
        admin = admins[0]
        admin.username = username
    else:
        admin = User(
            username=username,
            email=email or "admin@gvpowers.in",
            full_name="GV Powers Administrator",
            role="admin",
            is_active=True,
        )
        db.session.add(admin)

    admin.username = username
    admin.set_password(password)
    admin.role = "admin"
    admin.is_active = True
    if not admin.email:
        admin.email = email or "admin@gvpowers.in"
    db.session.commit()

    print(f"Admin credentials updated successfully for: {admin.username}")
