"""
GV Powers ERP - WSGI Entry Point
Use this file for Gunicorn / uWSGI deployment.

Usage:
    gunicorn wsgi:application -w 4 -b 0.0.0.0:8000
"""

from app import create_app

application = create_app()

if __name__ == "__main__":
    application.run()
