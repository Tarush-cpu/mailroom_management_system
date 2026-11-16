import sqlite3
import os
from datetime import datetime, timedelta
import random
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mailroom.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Users Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT,
        role TEXT NOT NULL DEFAULT 'resident', -- 'admin', 'staff', 'resident'
        unit_or_dept TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Storage Bins Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS storage_bins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bin_code TEXT UNIQUE NOT NULL,
        zone TEXT NOT NULL, -- e.g., 'Zone A (Boxes)', 'Zone B (Envelopes)', 'Zone C (Lockers)'
        capacity INTEGER DEFAULT 10,
        notes TEXT
    )
    ''')

    # Packages Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS packages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tracking_number TEXT UNIQUE NOT NULL,
        courier_name TEXT NOT NULL,
        recipient_name TEXT NOT NULL,
        recipient_email TEXT,
        recipient_phone TEXT,
        recipient_unit TEXT NOT NULL,
        storage_bin TEXT NOT NULL,
        package_type TEXT DEFAULT 'Box', -- Box, Envelope, Fragile, Perishable, Heavy
        weight TEXT,
        status TEXT NOT NULL DEFAULT 'Ready for Pickup', -- 'Ready for Pickup', 'Collected', 'Returned'
        arrival_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        collected_date TIMESTAMP,
        pickup_code TEXT NOT NULL, -- 6-digit verification code
        logged_by_id INTEGER,
        handed_by_id INTEGER,
        recipient_notes TEXT,
        handover_notes TEXT,
        collected_by_name TEXT,
        signature_data TEXT,
        FOREIGN KEY (logged_by_id) REFERENCES users (id),
        FOREIGN KEY (handed_by_id) REFERENCES users (id)
    )
    ''')

    # Activity Logs Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS activity_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        package_id INTEGER,
        action TEXT NOT NULL, -- Intake, Handover, Edit, Search, Return
        performed_by_name TEXT NOT NULL,
        performed_by_role TEXT NOT NULL,
        details TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (package_id) REFERENCES packages (id) ON DELETE SET NULL
    )
    ''')

    conn.commit()

    # Check if demo data needs to be seeded
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]

    if user_count == 0:
        seed_data(conn)

    conn.close()

def seed_data(conn):
    cursor = conn.cursor()
    
    # 1. Seed Users
    users = [
        ('admin', generate_password_hash('admin123'), 'Alexander Vance', 'admin@mailroom.local', '+1 (555) 010-8800', 'admin', 'Facility Management'),
        ('staff', generate_password_hash('staff123'), 'David Ramirez', 'staff@mailroom.local', '+1 (555) 014-9922', 'staff', 'Mailroom Desk 1'),
        ('john_doe', generate_password_hash('user123'), 'John Doe', 'john.doe@example.com', '+1 (555) 234-5678', 'resident', 'Unit 402'),
        ('sarah_m', generate_password_hash('user123'), 'Sarah Miller', 'sarah.m@example.com', '+1 (555) 345-6789', 'resident', 'Unit 305'),
        ('alex_corp', generate_password_hash('user123'), 'Dr. Alex Chen', 'alex.chen@biolabs.com', '+1 (555) 456-7890', 'resident', 'Suite 801 - Biotech'),
        ('emily_rose', generate_password_hash('user123'), 'Emily Rose', 'emily.r@example.com', '+1 (555) 567-8901', 'resident', 'Unit 114')
    ]

    cursor.executemany('''
    INSERT INTO users (username, password_hash, full_name, email, phone, role, unit_or_dept)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', users)

    # 2. Seed Storage Bins
    bins = [
        ('Rack A-1', 'Zone A (Main Shelf)', 15, 'Standard packages and parcels'),
        ('Rack A-2', 'Zone A (Main Shelf)', 15, 'Medium boxes'),
        ('Rack B-1', 'Zone B (Envelopes)', 25, 'Letters, documents, and soft flyers'),
        ('Rack B-2', 'Zone B (Envelopes)', 25, 'Passports, legal documents & folders'),
        ('Shelf C-3', 'Zone C (Fragile Items)', 10, 'Glassware and delicate electronics'),
        ('Locker 04', 'Zone D (Secure Lockers)', 5, 'High-value laptops and devices'),
        ('Locker 05', 'Zone D (Secure Lockers)', 5, 'Valuables & priority mail'),
        ('Bay OS-1', 'Zone E (Oversized Bay)', 8, 'Furniture, appliances and monitors'),
        ('Cooler F-1', 'Zone F (Perishables)', 6, 'Refrigerated food/medicine deliveries')
    ]

    cursor.executemany('''
    INSERT INTO storage_bins (bin_code, zone, capacity, notes)
    VALUES (?, ?, ?, ?)
    ''', bins)

    now = datetime.now()

    # 3. Seed Packages
    packages = [
        (
            'TRK-AMZ-98214', 'Amazon Logistics', 'John Doe', 'john.doe@example.com', '+1 (555) 234-5678', 'Unit 402',
            'Rack A-1', 'Box', '1.4 kg', 'Ready for Pickup',
            (now - timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S'), None, '849201', 2, None,
            'Left with Front Desk Security. Signature required.', None, None, None
        ),
        (
            'TRK-FDX-44129', 'FedEx Express', 'John Doe', 'john.doe@example.com', '+1 (555) 234-5678', 'Unit 402',
            'Rack B-1', 'Envelope', '0.2 kg', 'Collected',
            (now - timedelta(days=1, hours=4)).strftime('%Y-%m-%d %H:%M:%S'),
            (now - timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S'),
            '318492', 2, 2, 'Confidential bank letter', 'Verified with Resident ID badge', 'John Doe', 'SIG_VERIFIED_STAFF'
        ),
        (
            'TRK-DHL-77218', 'DHL Express', 'Sarah Miller', 'sarah.m@example.com', '+1 (555) 345-6789', 'Unit 305',
            'Shelf C-3', 'Fragile', '2.8 kg', 'Ready for Pickup',
            (now - timedelta(hours=6)).strftime('%Y-%m-%d %H:%M:%S'), None, '551930', 2, None,
            'Imported glassware from Germany. Handle with extreme care.', None, None, None
        ),
        (
            'TRK-UPS-60312', 'UPS Ground', 'Dr. Alex Chen', 'alex.chen@biolabs.com', '+1 (555) 456-7890', 'Suite 801 - Biotech',
            'Cooler F-1', 'Perishable', '3.5 kg', 'Ready for Pickup',
            (now - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S'), None, '729104', 2, None,
            'Refrigerated laboratory reagents (keep below 4°C). Alerted tenant immediately.', None, None, None
        ),
        (
            'TRK-BLU-10943', 'Blue Dart', 'Emily Rose', 'emily.r@example.com', '+1 (555) 567-8901', 'Unit 114',
            'Rack A-2', 'Box', '0.9 kg', 'Ready for Pickup',
            (now - timedelta(hours=28)).strftime('%Y-%m-%d %H:%M:%S'), None, '492817', 2, None,
            'Footwear box from Nike official store.', None, None, None
        ),
        (
            'TRK-AMZ-33201', 'Amazon Logistics', 'Dr. Alex Chen', 'alex.chen@biolabs.com', '+1 (555) 456-7890', 'Suite 801 - Biotech',
            'Bay OS-1', 'Heavy', '18.2 kg', 'Collected',
            (now - timedelta(days=2, hours=5)).strftime('%Y-%m-%d %H:%M:%S'),
            (now - timedelta(days=1, hours=2)).strftime('%Y-%m-%d %H:%M:%S'),
            '902184', 2, 1, 'Ergonomic Standing Desk Frame', 'Tenant picked up with lab trolley', 'Alex Chen', 'SIG_VERIFIED_STAFF'
        ),
        (
            'TRK-USPS-88210', 'USPS Priority', 'Sarah Miller', 'sarah.m@example.com', '+1 (555) 345-6789', 'Unit 305',
            'Locker 04', 'Box', '1.1 kg', 'Ready for Pickup',
            (now - timedelta(hours=50)).strftime('%Y-%m-%d %H:%M:%S'), None, '662019', 2, None,
            'Electronics (Apple Store package) - Priority Mail', None, None, None
        ),
        (
            'TRK-DTD-55291', 'DTDC Express', 'Michael Vance', 'm.vance@example.com', '+1 (555) 998-1122', 'Unit 201',
            'Rack A-1', 'Box', '1.7 kg', 'Collected',
            (now - timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S'),
            (now - timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S'),
            '118274', 2, 2, 'Books and study materials', 'Collected by roommate with authorization note', 'Marcus Vance', 'SIG_VERIFIED_STAFF'
        ),
        (
            'TRK-AMZ-77114', 'Amazon Logistics', 'John Doe', 'john.doe@example.com', '+1 (555) 234-5678', 'Unit 402',
            'Rack B-2', 'Envelope', '0.3 kg', 'Ready for Pickup',
            (now - timedelta(minutes=45)).strftime('%Y-%m-%d %H:%M:%S'), None, '283746', 2, None,
            'Replacement credit card / documents', None, None, None
        )
    ]

    cursor.executemany('''
    INSERT INTO packages (
        tracking_number, courier_name, recipient_name, recipient_email, recipient_phone, recipient_unit,
        storage_bin, package_type, weight, status, arrival_date, collected_date, pickup_code,
        logged_by_id, handed_by_id, recipient_notes, handover_notes, collected_by_name, signature_data
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', packages)

    # 4. Seed Activity Logs
    logs = [
        (1, 'Intake', 'David Ramirez', 'Staff', 'Registered package TRK-AMZ-98214 from Amazon Logistics. Allocated to Rack A-1.', (now - timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')),
        (2, 'Intake', 'David Ramirez', 'Staff', 'Registered package TRK-FDX-44129 from FedEx Express. Allocated to Rack B-1.', (now - timedelta(days=1, hours=4)).strftime('%Y-%m-%d %H:%M:%S')),
        (2, 'Handover', 'David Ramirez', 'Staff', 'Package TRK-FDX-44129 handed over to John Doe. OTP code 318492 verified.', (now - timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')),
        (3, 'Intake', 'David Ramirez', 'Staff', 'Registered package TRK-DHL-77218 from DHL Express. Marked Fragile, stored in Shelf C-3.', (now - timedelta(hours=6)).strftime('%Y-%m-%d %H:%M:%S')),
        (4, 'Intake', 'David Ramirez', 'Staff', 'Registered urgent perishable TRK-UPS-60312 for Dr. Alex Chen. Placed in Cooler F-1.', (now - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')),
        (5, 'Intake', 'David Ramirez', 'Staff', 'Registered package TRK-BLU-10943 from Blue Dart. Allocated to Rack A-2.', (now - timedelta(hours=28)).strftime('%Y-%m-%d %H:%M:%S')),
        (6, 'Intake', 'David Ramirez', 'Staff', 'Registered heavy item TRK-AMZ-33201 (18.2 kg). Allocated to Bay OS-1.', (now - timedelta(days=2, hours=5)).strftime('%Y-%m-%d %H:%M:%S')),
        (6, 'Handover', 'Alexander Vance', 'Admin', 'Heavy package TRK-AMZ-33201 handed over to Alex Chen with trolley assistance.', (now - timedelta(days=1, hours=2)).strftime('%Y-%m-%d %H:%M:%S')),
        (7, 'Intake', 'David Ramirez', 'Staff', 'Registered priority package TRK-USPS-88210 into secure Locker 04.', (now - timedelta(hours=50)).strftime('%Y-%m-%d %H:%M:%S')),
        (9, 'Intake', 'David Ramirez', 'Staff', 'Registered envelope TRK-AMZ-77114 into Rack B-2.', (now - timedelta(minutes=45)).strftime('%Y-%m-%d %H:%M:%S'))
    ]

    cursor.executemany('''
    INSERT INTO activity_logs (package_id, action, performed_by_name, performed_by_role, details, timestamp)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', logs)

    conn.commit()

if __name__ == '__main__':
    init_db()
    print("Database initialized and seeded successfully.")
