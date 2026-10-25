"""
GV Powers ERP - Logging Configuration
Production-grade logging: daily, error, invoice, security logs.
"""

import os
import logging
import logging.handlers


def setup_logging(base_dir: str):
    """Configure all application loggers."""
    log_dir = os.path.join(base_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    daily = logging.handlers.TimedRotatingFileHandler(
        os.path.join(log_dir, "daily.log"), when="midnight", interval=1, backupCount=90,
    )
    daily.setFormatter(fmt)
    daily.setLevel(logging.INFO)

    error = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, "error.log"), maxBytes=5 * 1024 * 1024, backupCount=10,
    )
    error.setFormatter(fmt)
    error.setLevel(logging.ERROR)

    invoice = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, "invoice.log"), maxBytes=5 * 1024 * 1024, backupCount=10,
    )
    invoice.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    invoice.setLevel(logging.INFO)

    security = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, "security.log"), maxBytes=5 * 1024 * 1024, backupCount=10,
    )
    security.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    security.setLevel(logging.WARNING)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(daily)
    root.addHandler(error)

    logging.getLogger("invoice").addHandler(invoice)
    logging.getLogger("invoice").setLevel(logging.INFO)
    logging.getLogger("security").addHandler(security)
    logging.getLogger("security").setLevel(logging.WARNING)
