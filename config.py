"""
GV Powers ERP - Configuration
Environment-based config for Development and Production.
"""

import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/gv_powers_erp",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 10,
        "max_overflow": 20,
    }

    SESSION_TYPE = "sqlalchemy"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    BASE_DIR = BASE_DIR
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    BACKUP_FOLDER = os.path.join(BASE_DIR, "backups", "database")
    PDF_FOLDER = os.path.join(BASE_DIR, "pdf")
    EXPORT_FOLDER = os.path.join(BASE_DIR, "exports")
    LOG_FOLDER = os.path.join(BASE_DIR, "logs")
    INVOICE_PORTAL_BASE_URL = os.getenv("INVOICE_PORTAL_BASE_URL", "https://invoice.gvpowers.in").rstrip("/")
    INVOICE_PORTAL_DATA_DIR = os.getenv("INVOICE_PORTAL_DATA_DIR", os.path.join(BASE_DIR, "invoice_portal_data"))

    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_SIZE", 16 * 1024 * 1024))

    COMPANY_NAME = os.getenv("COMPANY_NAME", "GV Powers")
    COMPANY_TAGLINE = os.getenv("COMPANY_TAGLINE", "Powering A Better Tomorrow")
    COMPANY_SERVICES = os.getenv(
        "COMPANY_SERVICES",
        "Solar Energy | UPS Systems | Inverters | RO Solutions | Electricals",
    )
    COMPANY_GSTIN = os.getenv("COMPANY_GSTIN", "33AGEPV1534G2ZJ")
    COMPANY_STATE = os.getenv("COMPANY_STATE", "Tamil Nadu")
    COMPANY_STATE_CODE = int(os.getenv("COMPANY_STATE_CODE", "33"))
    COMPANY_ADDRESS = os.getenv("COMPANY_ADDRESS", "No. 10, Kadharkhan Street, Opp. Railway Junction, Salem - 636005, Tamil Nadu")
    COMPANY_PHONE = os.getenv("COMPANY_PHONE", "+91 98940 79090")
    COMPANY_MOBILE = os.getenv("COMPANY_MOBILE", "+91 98940 79095")
    COMPANY_EMAIL = os.getenv("COMPANY_EMAIL", "gvpowerssalem@gmail.com")
    COMPANY_WEBSITE = os.getenv("COMPANY_WEBSITE", "https://gvpowers.in")

    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "gvpowers@admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin@gvpowerssalem")
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")

    GST_RATES = [0, 5, 12, 18, 28]

    @property
    def COMPANY(self):
        return {
            "name": self.COMPANY_NAME,
            "tagline": self.COMPANY_TAGLINE,
            "services": self.COMPANY_SERVICES,
            "gstin": self.COMPANY_GSTIN,
            "state": self.COMPANY_STATE,
            "state_code": self.COMPANY_STATE_CODE,
            "address": self.COMPANY_ADDRESS,
            "phone": self.COMPANY_PHONE,
            "email": self.COMPANY_EMAIL,
            "website": self.COMPANY_WEBSITE,
        }


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(BASE_DIR, "instance", "app.db"),
    )
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 10,
        "max_overflow": 20,
    }


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def get_config():
    env = os.getenv("FLASK_ENV", "development")
    return config_by_name.get(env, DevelopmentConfig)
