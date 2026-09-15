# InvoiceIQ

InvoiceIQ is a Django-based invoice and expense intelligence platform. It combines document extraction, deterministic financial validation, vendor analytics, risk indicators, and a portfolio-ready finance dashboard.

## Features

- Django and Django REST Framework
- Session authentication with registration and protected, user-scoped data
- Vendor, invoice, line item, expense, and anomaly models
- PDF/image upload with a PyMuPDF first path and OCR fallback service
- Decimal-safe subtotal, tax, and total validation
- User-scoped invoice, vendor, and expense API endpoints
- Dark financial analytics dashboard with Chart.js
- Django admin configuration for operational review
- Structured line-item extraction and rule-based expense classification
- Multi-signal duplicate scoring and Isolation Forest outlier detection
- Read-only AI assistant with optional OpenAI-compatible explanations
- Demo data command for portfolio screenshots
- User-scoped upload, analyze, analytics, and anomaly APIs

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open `http://127.0.0.1:8000/`, create an account, and upload an invoice. For PostgreSQL, set `DATABASE_URL` and adapt the database configuration before deployment; SQLite remains the local zero-setup default.

Copy `.env.example` to `.env` for local configuration. Set a unique `SECRET_KEY` and use a PostgreSQL URL such as `postgresql://user:password@localhost:5432/invoiceiq` when deploying with PostgreSQL. Never commit `.env` or production credentials.

Scanned-document OCR also requires the Tesseract executable installed on the host and available on `PATH`; PyMuPDF handles digital PDFs without it. Set `TESSERACT_CMD` and configure `pytesseract.pytesseract.tesseract_cmd` in a deployment-specific startup hook when Tesseract is installed outside `PATH`.

To populate a portfolio workspace:

```powershell
python manage.py seed_demo_data --username demo --reset
```

The command creates 12 vendors, 63 invoices, categorized expenses, and duplicate, unusual-amount, and calculation alerts. The demo login password is `demo-password` when the user is created by the command.

## AI pipeline

```mermaid
flowchart LR
    A[Upload] --> B[PyMuPDF text extraction]
    B -->|Insufficient text| C[OpenCV and Tesseract OCR]
    B --> D[Structured field and line-item parser]
    C --> D
    D --> E[Decimal validation]
    E --> F[Duplicate scoring]
    F --> G[Anomaly and risk engine]
    G --> H[Dashboard, APIs, and read-only assistant]
```

The assistant maps supported questions to fixed, user-scoped ORM queries. It never executes generated SQL. When `LLM_API_KEY` and `LLM_BASE_URL` are configured, the optional LLM adapter can explain an already-computed result without changing the query or database.

## API endpoints

- `POST /api/invoices/upload/`
- `GET /api/invoices/`
- `POST /api/invoices/<id>/analyze/`
- `GET /api/invoices/<id>/`
- `GET /api/vendors/`
- `GET /api/expenses/`
- `GET /api/analytics/monthly/`
- `GET /api/analytics/categories/`
- `GET /api/analytics/vendors/`
- `GET /api/anomalies/`
- `POST /api/ai/query/`

## Architecture

```mermaid
flowchart LR
    A[Upload PDF or image] --> B[Text extraction]
    B --> C[OCR fallback]
    C --> D[Structured extraction adapter]
    D --> E[Decimal validation]
    E --> F[(PostgreSQL or SQLite)]
    F --> G[Dashboard and DRF API]
    F --> H[Risk and analytics services]
```

## Testing

```powershell
python manage.py check
python manage.py test
```

The test suite covers user isolation, upload validation, OCR failure states, structured extraction, line-item classification, risk scoring, analytics APIs, assistant safety, and demo-data seeding.
