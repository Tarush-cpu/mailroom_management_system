📦 MailroomOS — Courier & Mailroom Management System

A digital, audit-ready Courier & Mailroom Management System engineered for gated residential communities, university hostels, corporate facilities, and industrial complexes. It eliminates manual paper registers, prevents misplaced packages, and provides transparent, real-time parcel intake and handover verification.

🚀 Key Highlights & Features
🎨 Modern Frontend: Built with Tailwind CSS, Lucide Icons, and Alpine.js. Features glassmorphism navigation, dynamic status badges, smooth transitions, responsive drawer menus, and printable thermal slips.
🔐 Two-Tier Role-Based Access Control:
Admin / Staff Role: Comprehensive operations dashboard, rapid parcel intake with smart courier presets, storage bin capacity tracking, CSV export, and tamper-proof audit trails.
Resident / Recipient Role: Personalized portal displaying pending arrivals, digital pickup passes with QR code, and 6-digit secure handover OTPs.
⚡ Rapid Parcel Intake Console: Pre-configured carrier chips (Amazon, FedEx, DHL, UPS, Blue Dart, DTDC, USPS), barcode/tracking generator, recipient auto-complete, and automated OTP generation.
📍 Smart Shelf & Bin Allocation: Visual rack management (Zone A Boxes, Zone B Envelopes, Zone C Fragile, Zone D Lockers, Zone E Oversized, Zone F Cold Storage) with live occupancy bars.
🛡️ 2-Step Handover Verification: Ensures packages are only released upon entering the resident's 6-digit OTP or verified staff confirmation.
🔍 Public Tracking Hero: Residents can track any parcel by Tracking ID (e.g., TRK-AMZ-98214) or Unit Number (Unit 402) without needing to log in.
🖨️ Printable Pickup Slips & QR Codes: Instant thermal printer/paper receipt layout with QR code for quick scanning and rack label attachment.
📜 Complete Audit Trail: Tracks who registered each parcel, who released it, timestamps, and notes.
🛠️ Technology Stack
Layer	Technologies
Backend	Python 3, Flask Web Framework
Database	SQLite 3 (mailroom.db) with Foreign Keys & Auto-seeding
Security	Werkzeug password hashing (PBKDF2/SHA256), Session-based RBAC
Frontend	HTML5, Tailwind CSS (via CDN), Alpine.js, Lucide Icons
QR Generation	qrcode Python library with live dynamic PNG streaming
🔑 Demo Accounts & Pre-configured Credentials

The login page includes 1-click auto-fill buttons for fast evaluation:

Role	Username	Password	Purpose
Admin	admin	admin123	Full facility management & config
Staff	staff	staff123	Mailroom desk attendant & intake
Resident	john_doe	user123	Resident of Unit 402 with pending deliveries
Resident	sarah_m	user123	Resident of Unit 305
Corporate Tenant	alex_corp	user123	Dr. Alex Chen (Suite 801 - Biotech)
📁 Project Directory Structure
text
mailroom_system/
├── app.py                  # Main Flask application & routes
├── database.py             # SQLite schema, connections, and demo seeder
├── auth.py                 # RBAC decorators and session management
├── test_system.py          # Automated test suite (9 test cases)
├── mailroom.db             # Local SQLite database
├── templates/
│   ├── base.html           # Core layout, navbar, search modal, footer
│   ├── index.html          # Public landing page & live parcel stream
│   ├── login.html          # Authentication with 1-click demo fillers
│   ├── register.html       # Resident registration
│   ├── dashboard.html      # Staff mailroom dashboard & handover modal
│   ├── intake.html         # Rapid parcel intake form
│   ├── package_detail.html # Lifecycle timeline, audit trail, QR pass
│   ├── resident_portal.html# Personalized resident view & OTP passes
│   ├── public_track.html   # Public tracking lookup with timeline
│   ├── storage_bins.html   # Shelf & locker capacity manager
│   ├── activity_logs.html  # Full mailroom audit trail
│   ├── edit_package.html   # Edit parcel details
│   └── print_slip.html     # Thermal printer pickup pass
└── README.md               # Documentation & user guide
🏃 Running the Application
1. Launch the Server
bash
python app.py

The server starts by default at http://127.0.0.1:5000.

2. Run the Test Suite
bash
python test_system.py
🌟 Sample Deliveries for Instant Testing
Tracking ID: TRK-AMZ-98214 (Ready for Pickup • Rack A-1 • John Doe • Unit 402)
Tracking ID: TRK-DHL-77218 (Ready for Pickup • Shelf C-3 • Sarah Miller • Unit 305)
Tracking ID: TRK-UPS-60312 (Ready for Pickup • Cooler F-1 • Dr. Alex Chen • Suite 801)
Tracking ID: TRK-FDX-44129 (Collected • Handed over to John Doe)
