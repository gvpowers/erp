# GV Powers ERP

Enterprise Resource Planning System for **GV Powers** - Solar Panels, Inverters, Batteries, UPS, RO Systems, Hardware & Electrical.

## Features

- **Invoicing** - GST-compliant invoices with 3-copy PDF (Customer/Owner/GST Tax)
- **Quotations** - Create, convert to invoice
- **Customers** - Full CRM with GSTIN/PAN validation
- **Products** - Inventory with SKU, barcode, HSN, stock tracking
- **Suppliers** - Supplier management
- **Purchase Orders** - PO creation, status tracking, stock auto-update
- **Reports** - Sales, GST, Inventory, Profit, Customer reports
- **Exports** - Excel (.xlsx) and CSV exports
- **Indian GST** - CGST/SGST/IGST, intra/inter-state, round-off
- **Audit Trail** - Complete audit logging
- **Backup** - PostgreSQL backup/restore
- **Multi-user** - Admin and Sales roles

## Tech Stack

- Python 3.10+
- Flask 3.1
- PostgreSQL (production) / SQLite (development)
- SQLAlchemy + Flask-Migrate
- ReportLab (PDF generation)
- Gunicorn + Nginx (production)
- Cloudflare Tunnel (optional)

## Installation

### 1. Clone Repository

```bash
git clone https://github.com/your-org/gv-powers-erp.git
cd gv-powers-erp
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
# Edit .env with your settings
```

### 5. Database Setup

```bash
# PostgreSQL (production)
sudo -u postgres createdb gv_powers_erp
# Update DATABASE_URL in .env

# Run migrations
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

### 6. Run Development Server

```bash
flask run
# or
python app.py
```

Default login: `gvpowers@admin` / `admin@gvpowerssalem`

## Production Deployment

### 1. Server Setup (Ubuntu)

```bash
sudo apt update && sudo apt install python3-pip python3-venv postgresql nginx certbot
```

### 2. Clone & Setup

```bash
cd /opt
sudo git clone https://your-org/gv-powers-erp.git
cd gv-powers-erp
sudo python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
nano .env  # Set production secrets
```

### 4. Database

```bash
sudo -u postgres createdb gv_powers_erp
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'your-password';"
flask db upgrade
```

### 5. Gunicorn

```bash
# Test
gunicorn wsgi:application -c gunicorn.conf.py

# systemd service
sudo cp gvpowers.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable gvpowers
sudo systemctl start gvpowers
```

### 6. Nginx

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /opt/gv-powers-erp/static/;
        expires 30d;
    }
}
```

### 7. SSL & Cloudflare Tunnel

```bash
# Option A: Certbot
sudo certbot --nginx -d your-domain.com

# Option B: Cloudflare Tunnel
cloudflared tunnel --url http://localhost:8000
```

## One Command Deploy

After initial setup, deployment is:

```bash
git pull
pip install -r requirements.txt
flask db upgrade
sudo systemctl restart gvpowers
```

## Project Structure

```
gv-powers-erp/
├── app.py              # Entry point (~110 lines)
├── config.py           # Configuration classes
├── wsgi.py             # Gunicorn entry point
├── gunicorn.conf.py    # Gunicorn config
├── gvpowers.service    # systemd service
├── requirements.txt    # Dependencies
├── .env.example        # Environment template
├── .gitignore          # Git ignore rules
├── README.md           # This file
│
├── models/             # SQLAlchemy models
│   ├── user.py         # User model
│   ├── customer.py     # Customer model
│   ├── product.py      # Product, Category, StockMovement
│   ├── supplier.py     # Supplier model
│   ├── invoice.py      # Invoice, InvoiceItem, Payment
│   ├── quotation.py    # Quotation, QuotationItem
│   ├── purchase.py     # PurchaseOrder, PurchaseItem
│   ├── settings.py     # Settings, GSTMaster
│   └── audit.py        # AuditLog, Notification
│
├── routes/             # Route handlers
│   ├── auth.py         # Login, logout, index
│   ├── admin.py        # Dashboard, users, settings, backup
│   ├── customers.py    # Customer CRUD + API
│   ├── products.py     # Product CRUD + categories
│   ├── suppliers.py    # Supplier CRUD + purchase orders
│   ├── inventory.py    # Stock management
│   ├── billing.py      # Invoices, PDF, payments
│   ├── quotations.py   # Quotations
│   ├── reports.py      # Reports + exports
│   └── api.py          # Search, notifications API
│
├── services/           # Business logic
│   ├── gst_service.py  # GST calculations
│   ├── invoice_pdf_service.py  # PDF generation
│   ├── backup_service.py       # Backup/restore
│   ├── audit_service.py        # Audit logging
│   └── seed.py                 # Database seeding
│
├── utils/              # Utility functions
│   ├── __init__.py     # GST, validation, number generators
│   └── logging_config.py  # Logging setup
│
├── templates/          # Jinja2 templates
├── static/             # CSS, JS, images
├── migrations/         # Alembic migrations
├── logs/               # Application logs
├── backups/            # Database backups
├── uploads/            # User uploads
├── exports/            # Generated reports
└── pdf/                # Generated PDFs
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Redirect to dashboard or new invoice |
| `POST /login` | User login |
| `GET /dashboard` | Admin dashboard |
| `GET /invoices/new` | New invoice form |
| `POST /invoices/create` | Create invoice |
| `GET /invoices` | Invoice history |
| `GET /invoices/<id>` | Invoice preview |
| `GET /invoices/<id>/pdf/<type>` | Download PDF (owner/customer/gst) |
| `POST /invoices/<id>/payment` | Record payment |
| `GET /quotations` | Quotation list |
| `GET /reports` | Reports hub |
| `GET /api/search` | Global search (Ctrl+K) |

## License

Commercial - GV Powers
