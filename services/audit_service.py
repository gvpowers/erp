"""
GV Powers ERP - Audit & Settings Service
"""

from flask import request, current_app
from flask_login import current_user


def log_audit(action: str, details: str = "", user_id: int = None):
    """Log an audit entry to the database."""
    from models import db, AuditLog

    try:
        uid = user_id or (current_user.id if current_user.is_authenticated else None)
        entry = AuditLog(
            user_id=uid,
            action=action,
            details=details,
            ip_address=request.remote_addr,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()


def get_setting(key: str, default=None):
    """Get a setting value by key."""
    from models import Settings
    s = Settings.query.filter_by(key=key).first()
    return s.value if s else default


def set_setting(key: str, value: str):
    """Set a setting value by key (create or update)."""
    from models import db, Settings
    s = Settings.query.filter_by(key=key).first()
    if s:
        s.value = value
    else:
        s = Settings(key=key, value=value)
        db.session.add(s)
    db.session.commit()
