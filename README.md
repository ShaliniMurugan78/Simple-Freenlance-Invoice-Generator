# Smart Freelance Invoice & Financial Management Platform

An end-to-end, production-quality financial and billing management web application designed for freelancers, independent contractors, consultants, and digital studios.

Built as a **Final-Year B.Tech Artificial Intelligence and Data Science Placement Portfolio Project**, this application solves real-world freelance business challenges: professional invoice generation, automated payment and due-date tracking, multi-currency support, receipt scanning via Optical Character Recognition (OCR), AI-assisted service description drafting, QR-code cryptographic invoice verification, and deterministic rule-based business insights.

---

## 🚀 Key Highlights & Architectural Principles

1. **Deterministic Financial Accuracy**: All core financial calculations (subtotals, multi-tier discounts, taxes/GST, grand totals, payment records, and net income) are 100% deterministic and validated both on the client and server side.
2. **Restrained, Professional Accounting UI/UX**: Designed to look like high-end business software (e.g., Stripe / Linear / QuickBooks) rather than a generic AI dashboard. Uses subtle borders, clean typography, responsive layouts, and zero visual clutter.
3. **Multi-Template Printable Engine**: Features 3 distinct A4-optimized invoice designs (**Classic**, **Modern**, and **Minimal**) with `@media print` support and PDF readiness.
4. **AI Invoice Description Assistant**: Synthesizes structured, professional line-item deliverables from raw service titles with tone selection (`Professional`, `Simple`, `Detailed`), powered by Groq / Gemini / OpenAI with offline fallback.
5. **Direct UPI Payment QR Code & Integrity Verification**: Every invoice features an instant UPI Scan-to-Pay QR code (for Google Pay, PhonePe, Paytm, BHIM) and public cryptographic verification (`/verify/<inv_no>/<token>`) backed by SHA-256 integrity checksums.
6. **Realized Net Income & Smart Business Insights**: Transparent formula: `Net Income = Total Settled (Paid) Revenue - Total Expenses`. Rule-based insight engine analyzes late payment behaviors, top revenue drivers, and expense growth trends.

---

## 🛠 Technology Stack

- **Backend**: Python 3.11, Flask (Application Factory pattern, Blueprints)
- **Database**: SQLite3 (Thread-safe connection pooling, foreign keys, performance indexes, timestamped `.db` backup export)
- **Frontend**: Semantic HTML5, Vanilla CSS Design System (`main.css`), A4 Print Layout (`print.css`), Vanilla Modern JavaScript (`ES6+`)
- **QR Code Engine**: `qrcode`, `Pillow` (Inline Base64 Data URI)
- **OCR Engine**: `pytesseract`, `Pillow` image filter pipelines
- **AI Integration**: REST API integration for LLMs (Gemini / OpenAI compatible) with graceful fallback template engine
- **Testing**: Python `unittest` suite (18 test cases covering all modules)

---

## 📁 System Architecture & Directory Structure

```
smart_invoice/
├── app/
│   ├── __init__.py                # Flask application factory & Jinja filters
│   ├── config.py                  # Environment config & constants
│   ├── database/
│   │   ├── db.py                  # SQLite helpers, backup creator & demo seeder
│   │   └── schema.sql             # SQL schema, foreign keys & indexes
│   ├── services/
│   │   ├── calculation_service.py # Deterministic math, taxes, discounts, net income
│   │   ├── invoice_service.py     # Sequential numbering (INV-001), document hash, CSV
│   │   ├── insight_service.py     # Rule-based business analytics engine
│   │   ├── ocr_service.py         # Receipt image preprocessing & field parser
│   │   ├── qr_service.py          # Verification token generator & QR builder
│   │   └── ai_service.py          # AI description assistant & fallback engine
│   ├── routes/
│   │   ├── main.py                # Dashboard with business overview & insights
│   │   ├── invoices.py            # Invoice CRUD, templates, payment reminders, CSV
│   │   ├── clients.py             # Client CRUD, ledger, payment history
│   │   ├── expenses.py            # Expense CRUD, category filters, receipt upload
│   │   ├── ai.py                  # AI assistant API endpoints
│   │   ├── verification.py        # Public verification (/verify/<inv_no>/<token>)
│   │   └── settings.py            # Business profile, logo upload, backup download
│   ├── templates/
│   │   ├── base.html              # Shell layout with responsive navigation & modals
│   │   ├── home.html              # Concise business overview & smart insights
│   │   ├── invoices/
│   │   │   ├── index.html         # Invoices list with search, status filters & CSV
│   │   │   ├── form.html          # Invoice creator/editor with live math & AI modal
│   │   │   ├── view.html          # Invoice viewer with template switcher & actions
│   │   │   └── templates/
│   │   │       ├── classic.html   # Corporate letterhead template
│   │   │       ├── modern.html    # Modern banner template
│   │   │       └── minimal.html   # Clean typographic template
│   │   ├── clients/
│   │   │   ├── index.html         # Client directory & lifetime metrics
│   │   │   ├── form.html          # Client form
│   │   │   └── view.html          # Client ledger & payment history
│   │   ├── expenses/
│   │   │   ├── index.html         # Expense table & category breakdown
│   │   │   └── form.html          # Expense form & OCR scanner modal
│   │   ├── settings/
│   │   │   └── index.html         # Profile, logo manager, DB backup, demo seed
│   │   └── verification/
│   │       ├── public.html        # Public verification badge & SHA-256 hash check
│   │       └── invalid.html       # Invalid verification notice
│   └── static/
│       ├── css/
│       │   ├── main.css           # Professional accounting design system
│       │   └── print.css          # A4-optimized print stylesheet
│       ├── js/
│       │   ├── app.js             # General UX helpers (modals, confirmation alerts)
│       │   ├── invoice_calc.js    # Client-side live math & dynamic line items
│       │   ├── receipt_scanner.js # OCR upload, preview & field autofill
│       │   └── ai_assistant.js    # AI prompt modal & tone injection
│       └── uploads/               # Logos and receipt images
├── tests/
│   ├── __init__.py
│   ├── test_calculations.py       # Math, discount, tax, currency tests
│   ├── test_invoices.py           # Numbering, status transitions, HTTP CRUD
│   ├── test_clients.py            # Client ledger, delete protection
│   ├── test_expenses.py           # Expense CRUD, CSV export
│   ├── test_insights.py           # Rule-based insight triggers
│   ├── test_verification.py       # QR tokens, SHA-256 checksums
│   └── test_ai_and_ocr.py         # AI & OCR heuristic fallback tests
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
└── run.py
```

---

## 🗄 Database Schema Design

- `freelancer_profile`: Business Name, Owner Name, Email, Phone, Address, Website, Tax ID, Logo Path, Default Currency, Default Tax %, Default Payment Terms, Default Template.
- `clients`: ID, Name, Company Name, Email, Phone, Address, Tax Number, Notes, Timestamps.
- `invoices`: ID, Invoice Number (`UNIQUE`), Client ID (`FK`), Invoice Date, Due Date, Currency, Subtotal, Discount %, Discount Amount, Tax %, Tax Amount, Total, Status (`Draft`, `Pending`, `Paid`, `Overdue`, `Cancelled`), Payment Terms, Notes, Template, Verification Token (`UNIQUE`), Document Hash (SHA-256), Paid Date, Timestamps.
- `invoice_items`: ID, Invoice ID (`FK CASCADE`), Description, Hours, Hourly Rate, Amount, Sort Order.
- `expenses`: ID, Date, Description, Merchant, Category, Amount, Currency, Payment Method, Receipt Path, Notes, Timestamps.
- `payment_records`: ID, Invoice ID (`FK CASCADE`), Amount, Payment Date, Payment Method, Notes, Timestamps.
- `activity_logs`: ID, Action, Entity Type, Entity ID, Description, Created At.

---

## 💻 Installation & Setup

### 1. Prerequisites
- Python 3.10+ installed
- *(Optional)* Tesseract OCR installed on your system if you want local hardware OCR execution (e.g. `C:\Program Files\Tesseract-OCR\tesseract.exe`). The system includes a built-in fallback parser if not installed.

### 2. Clone & Install Dependencies
```bash
# Clone or open project directory
cd "Simple Freelance Invoice Generator"

# Install dependencies
python -m pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Key configuration settings in `.env`:
- `SECRET_KEY`: Flask session secret key.
- `AI_API_KEY`: *(Optional)* LLM API key for AI description generation (Gemini or OpenAI). If omitted, the built-in professional template engine activates automatically.
- `TESSERACT_CMD`: *(Optional)* Path to `tesseract.exe` if installed.
- `SMTP_*`: *(Optional)* SMTP credentials for sending live payment reminder emails.

---

## 🏃 Running the Application

Start the local development server:
```bash
python run.py
```

Open your browser and navigate to:
```
http://127.0.0.1:5000
```

### 🌟 Quick Demo Portfolio Setup
On first launch, you can click **"Load Demo Seed Data"** on the Home page or in Settings. This instantly populates realistic clients (e.g., *ABC Technologies*, *Pixel Studio*, *John Designs*), issued invoices across various statuses (Paid, Pending, Overdue), itemized expenses, and business insights—perfect for placement presentations.

---

## 🧪 Running the Automated Test Suite

Execute the comprehensive unit and integration test suite:
```bash
python -m unittest discover tests/ -v
```

**Test Coverage Summary**:
- `test_calculations.py`: Subtotal, multi-rate tax/GST, discount deductions, rounding to 2 decimal places, Lakhs/Thousands currency formatting, and Net Income formula.
- `test_invoices.py`: Collision-free sequential numbering (`INV-001`, `INV-002`), overdue auto-detection on expired due dates, and template switching.
- `test_clients.py`: Client creation, ledger balances, and cascade deletion protection.
- `test_expenses.py`: Expense categorization, month-over-month comparisons, and CSV export.
- `test_insights.py`: Deterministic triggers for payment delay alerts, service revenue leaderboards, and rate trends.
- `test_verification.py`: Cryptographic token randomness, public `/verify` endpoint rendering, and SHA-256 document tamper checks.
- `test_ai_and_ocr.py`: Tone-based AI prompt generation and OCR regex heuristics.

---

## 💼 Placement Interview Demonstration Walkthrough

When presenting this project during a technical or portfolio interview:

1. **Dashboard & Financial Health**: Show the Home page overview. Explain the distinction between **Total Invoiced** vs **Settled (Paid)** revenue, and how **Realized Net Income** (`Paid Revenue - Expenses`) provides accurate cash flow insights.
2. **Invoice Creation with Live Calculations**: Create a new invoice. Demonstrate instant client-side calculations (Hours × Rate, Subtotal, Discount, Tax, Total) without page refreshes, and explain that the server deterministically validates all figures upon submission.
3. **AI Description Assistant**: Click the sparkle icon on a line item, enter a service name like `"Website Development"` or `"UI/UX Design"`, select tone (`Professional` / `Detailed`), generate the deliverable description, and insert it with 1 click.
4. **Template Switching & Print/PDF Engine**: Open an invoice, switch between **Classic**, **Modern**, and **Minimal** templates. Click **Print / PDF** to demonstrate how `@media print` eliminates app navigation and formats the document for A4 paper.
5. **QR Code & Public Verification**: Scan or click the public verification link on the invoice (`/verify/INV-001/<token>`). Explain how the unpredictable 32-character token and SHA-256 hash verify authenticity and current payment status without exposing internal database IDs or confidential client records.
6. **Expense Tracking & OCR Receipt Scanner**: Upload a receipt image, show the OCR preprocessing and regex parsing into Merchant, Date, Amount, and Category, review the data in the confirmation modal, and save the expense.
7. **Smart Business Insights Engine**: Point out the rule-based insights on the Home page, showing how late payments, revenue concentration, and spending spikes are detected transparently without opaque black-box claims.
8. **Data Portability & Database Backups**: Demonstrate 1-click CSV exports for invoices/expenses and timestamped `.db` SQLite backups in Settings.

---

## 🔒 Security Practices Implemented

- **Parameterized SQL Queries**: Complete protection against SQL injection across all database interactions.
- **Strict File Upload Validation**: Validates file extensions (`.png`, `.jpg`, `.jpeg`, `.webp`), enforces a 16MB file size ceiling, and uses `secure_filename()` to prevent path traversal.
- **Unpredictable Verification Tokens**: Uses `secrets.token_hex(16)` to prevent invoice enumeration.
- **SHA-256 Integrity Hashes**: Detects modifications to core invoice terms.
- **Safe Fallback Architectures**: External API dependencies (LLMs, OCR binaries, SMTP) never crash the application if offline or unconfigured.
