import os
import io
import csv
import random
import string
from datetime import datetime, timedelta
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, jsonify, send_file, Response
)
from werkzeug.security import check_password_hash, generate_password_hash
import qrcode

from database import get_db_connection, init_db
from auth import login_required, staff_required, admin_required, get_current_user

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'courier-mailroom-secret-key-2026')

# Ensure DB is initialized on start
with app.app_context():
    init_db()

def generate_pickup_code():
    """Generates a random 6-digit numeric pickup code."""
    return f"{random.randint(100000, 999999)}"

def generate_tracking_id(carrier="TRK"):
    """Generates a standardized tracking ID."""
    prefix_map = {
        'Amazon Logistics': 'AMZ',
        'FedEx Express': 'FDX',
        'DHL Express': 'DHL',
        'UPS Ground': 'UPS',
        'Blue Dart': 'BLU',
        'DTDC Express': 'DTD',
        'USPS Priority': 'USPS',
        'India Post': 'INP'
    }
    code = prefix_map.get(carrier, 'TRK')
    rand_chars = ''.join(random.choices(string.digits, k=6))
    return f"TRK-{code}-{rand_chars}"

@app.context_processor
def inject_global_data():
    """Injects user information and pending package counts into all templates."""
    current_user = get_current_user()
    pending_count = 0
    resident_pending_count = 0
    if current_user:
        conn = get_db_connection()
        try:
            pending_count = conn.execute(
                "SELECT COUNT(*) FROM packages WHERE status = 'Ready for Pickup'"
            ).fetchone()[0]
            if current_user['role'] == 'resident':
                # Match by email, name or unit
                resident_pending_count = conn.execute(
                    """SELECT COUNT(*) FROM packages 
                       WHERE status = 'Ready for Pickup' 
                       AND (LOWER(recipient_email) = LOWER(?) OR LOWER(recipient_name) = LOWER(?) OR LOWER(recipient_unit) = LOWER(?))""",
                    (current_user['email'], current_user['full_name'], current_user['unit_or_dept'] or '')
                ).fetchone()[0]
        except Exception:
            pass
        finally:
            conn.close()
    return {
        'current_user': current_user,
        'global_pending_count': pending_count,
        'resident_pending_count': resident_pending_count,
        'now': datetime.now()
    }

# -------------------------------------------------------------
# Public & Landing Routes
# -------------------------------------------------------------

@app.route('/')
def index():
    conn = get_db_connection()
    stats = {
        'total': conn.execute("SELECT COUNT(*) FROM packages").fetchone()[0],
        'pending': conn.execute("SELECT COUNT(*) FROM packages WHERE status = 'Ready for Pickup'").fetchone()[0],
        'collected': conn.execute("SELECT COUNT(*) FROM packages WHERE status = 'Collected'").fetchone()[0],
        'today': conn.execute("SELECT COUNT(*) FROM packages WHERE DATE(arrival_date) = DATE('now')").fetchone()[0]
    }
    recent_packages = conn.execute("""
        SELECT * FROM packages 
        ORDER BY arrival_date DESC LIMIT 5
    """).fetchall()
    conn.close()
    return render_template('index.html', stats=stats, recent_packages=recent_packages)

@app.route('/track', methods=['GET', 'POST'])
def public_track():
    query = request.args.get('q', '').strip()
    if request.method == 'POST':
        query = request.form.get('tracking_query', '').strip()
        return redirect(url_for('public_track', q=query))

    package = None
    timeline = []
    error_msg = None

    if query:
        conn = get_db_connection()
        # Query by exact tracking number, or partial match
        package = conn.execute("""
            SELECT p.*, u.full_name as logged_by_name 
            FROM packages p 
            LEFT JOIN users u ON p.logged_by_id = u.id
            WHERE UPPER(p.tracking_number) = UPPER(?) 
               OR p.recipient_phone = ? 
               OR (UPPER(p.recipient_unit) = UPPER(?) AND p.status = 'Ready for Pickup')
            ORDER BY p.arrival_date DESC LIMIT 1
        """, (query, query, query)).fetchone()

        if package:
            # Build timeline
            timeline.append({
                'title': 'Parcel Received at Gate / Mailroom',
                'description': f"Logged by Mailroom Staff into {package['storage_bin']}",
                'timestamp': package['arrival_date'],
                'completed': True,
                'current': package['status'] == 'Ready for Pickup'
            })
            if package['status'] == 'Ready for Pickup':
                timeline.append({
                    'title': 'Ready for Resident Pickup',
                    'description': f"Available at Mailroom Front Counter ({package['storage_bin']}). Please present 6-digit OTP or Photo ID.",
                    'timestamp': package['arrival_date'],
                    'completed': True,
                    'current': True
                })
                timeline.append({
                    'title': 'Collected by Recipient',
                    'description': 'Awaiting handover confirmation at counter.',
                    'timestamp': None,
                    'completed': False,
                    'current': False
                })
            elif package['status'] == 'Collected':
                timeline.append({
                    'title': 'Ready for Resident Pickup',
                    'description': f"Processed in {package['storage_bin']}",
                    'timestamp': package['arrival_date'],
                    'completed': True,
                    'current': False
                })
                timeline.append({
                    'title': 'Handed Over & Collected',
                    'description': f"Handed to {package['collected_by_name'] or package['recipient_name']} with verified confirmation.",
                    'timestamp': package['collected_date'],
                    'completed': True,
                    'current': True
                })
        else:
            error_msg = f"No delivery found matching '{query}'. Please verify your Tracking ID or Unit Number."
        conn.close()

    return render_template('public_track.html', query=query, package=package, timeline=timeline, error_msg=error_msg)

# -------------------------------------------------------------
# Authentication Routes
# -------------------------------------------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        if session.get('role') in ['admin', 'staff']:
            return redirect(url_for('dashboard'))
        return redirect(url_for('resident_portal'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username = ? OR email = ?", (username, username)).fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            session['unit_or_dept'] = user['unit_or_dept']

            flash(f"Welcome back, {user['full_name']}!", 'success')
            next_url = request.args.get('next')
            if next_url:
                return redirect(next_url)
            if user['role'] in ['admin', 'staff']:
                return redirect(url_for('dashboard'))
            return redirect(url_for('resident_portal'))
        else:
            flash('Invalid username or password. Try one of the quick demo buttons below.', 'danger')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        unit_or_dept = request.form.get('unit_or_dept', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        role = request.form.get('role', 'resident')

        # Limit registration of staff/admin for demo ease
        if role not in ['resident', 'staff']:
            role = 'resident'

        if not full_name or not username or not email or not password:
            flash('Please fill in all required fields.', 'danger')
            return render_template('register.html')

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html')

        conn = get_db_connection()
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ? OR email = ?", (username, email)
        ).fetchone()

        if existing:
            flash('Username or Email already registered. Please log in.', 'warning')
            conn.close()
            return redirect(url_for('login'))

        pwd_hash = generate_password_hash(password)
        conn.execute("""
            INSERT INTO users (username, password_hash, full_name, email, phone, role, unit_or_dept)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (username, pwd_hash, full_name, email, phone, role, unit_or_dept))
        conn.commit()
        conn.close()

        flash('Account registered successfully! You can now log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out securely.', 'info')
    return redirect(url_for('login'))

# -------------------------------------------------------------
# Staff & Admin Mailroom Management
# -------------------------------------------------------------

@app.route('/dashboard')
@staff_required
def dashboard():
    conn = get_db_connection()

    # Metrics
    total_packages = conn.execute("SELECT COUNT(*) FROM packages").fetchone()[0]
    ready_packages = conn.execute("SELECT COUNT(*) FROM packages WHERE status = 'Ready for Pickup'").fetchone()[0]
    collected_today = conn.execute("""
        SELECT COUNT(*) FROM packages 
        WHERE status = 'Collected' AND DATE(collected_date) = DATE('now')
    """).fetchone()[0]
    
    # Overdue packages: Ready for Pickup and arrived > 48 hours ago
    overdue_cutoff = (datetime.now() - timedelta(hours=48)).strftime('%Y-%m-%d %H:%M:%S')
    overdue_packages = conn.execute("""
        SELECT COUNT(*) FROM packages 
        WHERE status = 'Ready for Pickup' AND arrival_date <= ?
    """, (overdue_cutoff,)).fetchone()[0]

    # Filters
    search_query = request.args.get('q', '').strip()
    status_filter = request.args.get('status', 'all')
    courier_filter = request.args.get('courier', 'all')
    bin_filter = request.args.get('bin', 'all')

    sql = """
        SELECT p.*, u.full_name as logged_by_name, h.full_name as handed_by_name
        FROM packages p
        LEFT JOIN users u ON p.logged_by_id = u.id
        LEFT JOIN users h ON p.handed_by_id = h.id
        WHERE 1=1
    """
    params = []

    if search_query:
        sql += """ AND (
            p.tracking_number LIKE ? OR 
            p.recipient_name LIKE ? OR 
            p.recipient_unit LIKE ? OR 
            p.recipient_phone LIKE ? OR
            p.pickup_code LIKE ?
        )"""
        pattern = f"%{search_query}%"
        params.extend([pattern, pattern, pattern, pattern, pattern])

    if status_filter != 'all':
        sql += " AND p.status = ?"
        params.append(status_filter)

    if courier_filter != 'all':
        sql += " AND p.courier_name = ?"
        params.append(courier_filter)

    if bin_filter != 'all':
        sql += " AND p.storage_bin = ?"
        params.append(bin_filter)

    sql += " ORDER BY CASE WHEN p.status = 'Ready for Pickup' THEN 0 ELSE 1 END, p.arrival_date DESC"

    packages = conn.execute(sql, params).fetchall()

    # Distinct Couriers and Bins for filter dropdowns
    couriers = conn.execute("SELECT DISTINCT courier_name FROM packages ORDER BY courier_name").fetchall()
    storage_bins = conn.execute("SELECT DISTINCT bin_code FROM storage_bins ORDER BY bin_code").fetchall()

    # Recent activity logs for dashboard sidebar
    recent_logs = conn.execute("""
        SELECT * FROM activity_logs ORDER BY timestamp DESC LIMIT 6
    """).fetchall()

    conn.close()

    return render_template(
        'dashboard.html',
        packages=packages,
        stats={
            'total': total_packages,
            'ready': ready_packages,
            'collected_today': collected_today,
            'overdue': overdue_packages
        },
        couriers=[c['courier_name'] for c in couriers],
        storage_bins=[b['bin_code'] for b in storage_bins],
        search_query=search_query,
        status_filter=status_filter,
        courier_filter=courier_filter,
        bin_filter=bin_filter
    )

@app.route('/intake', methods=['GET', 'POST'])
@staff_required
def intake():
    conn = get_db_connection()

    if request.method == 'POST':
        courier_name = request.form.get('courier_name', '').strip()
        custom_courier = request.form.get('custom_courier', '').strip()
        if custom_courier:
            courier_name = custom_courier

        tracking_number = request.form.get('tracking_number', '').strip()
        if not tracking_number:
            tracking_number = generate_tracking_id(courier_name)

        recipient_name = request.form.get('recipient_name', '').strip()
        recipient_unit = request.form.get('recipient_unit', '').strip()
        recipient_phone = request.form.get('recipient_phone', '').strip()
        recipient_email = request.form.get('recipient_email', '').strip()
        storage_bin = request.form.get('storage_bin', '').strip()
        package_type = request.form.get('package_type', 'Box')
        weight = request.form.get('weight', '').strip()
        recipient_notes = request.form.get('recipient_notes', '').strip()

        if not recipient_name or not recipient_unit or not storage_bin:
            flash('Recipient Name, Unit/Flat, and Storage Bin are required.', 'danger')
            storage_bins = conn.execute("SELECT * FROM storage_bins ORDER BY bin_code").fetchall()
            residents = conn.execute("SELECT full_name, unit_or_dept, phone, email FROM users WHERE role = 'resident' ORDER BY full_name").fetchall()
            conn.close()
            return render_template('intake.html', storage_bins=storage_bins, residents=residents)

        # Ensure tracking number uniqueness
        existing_trk = conn.execute("SELECT id FROM packages WHERE tracking_number = ?", (tracking_number,)).fetchone()
        if existing_trk:
            tracking_number = generate_tracking_id(courier_name)

        pickup_code = generate_pickup_code()
        logged_by_id = session.get('user_id')

        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO packages (
                tracking_number, courier_name, recipient_name, recipient_email, recipient_phone,
                recipient_unit, storage_bin, package_type, weight, status, arrival_date,
                pickup_code, logged_by_id, recipient_notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Ready for Pickup', datetime('now', 'localtime'), ?, ?, ?)
        """, (
            tracking_number, courier_name, recipient_name, recipient_email, recipient_phone,
            recipient_unit, storage_bin, package_type, weight, pickup_code, logged_by_id, recipient_notes
        ))
        package_id = cursor.lastrowid

        # Log activity
        user_name = session.get('full_name', 'Staff')
        user_role = session.get('role', 'staff').capitalize()
        cursor.execute("""
            INSERT INTO activity_logs (package_id, action, performed_by_name, performed_by_role, details)
            VALUES (?, 'Intake', ?, ?, ?)
        """, (
            package_id, user_name, user_role,
            f"Intake registered: {tracking_number} ({courier_name}) for {recipient_name} ({recipient_unit}) allocated to {storage_bin}."
        ))

        conn.commit()
        conn.close()

        flash(f"Package {tracking_number} successfully registered! Pickup OTP: {pickup_code}", 'success')
        return redirect(url_for('package_detail', package_id=package_id, just_added=1))

    storage_bins = conn.execute("SELECT * FROM storage_bins ORDER BY bin_code").fetchall()
    residents = conn.execute("SELECT full_name, unit_or_dept, phone, email FROM users WHERE role = 'resident' ORDER BY full_name").fetchall()
    conn.close()

    suggested_trk = generate_tracking_id("Amazon Logistics")
    return render_template('intake.html', storage_bins=storage_bins, residents=residents, suggested_trk=suggested_trk)

@app.route('/packages/<int:package_id>')
def package_detail(package_id):
    conn = get_db_connection()
    package = conn.execute("""
        SELECT p.*, u.full_name as logged_by_name, h.full_name as handed_by_name
        FROM packages p
        LEFT JOIN users u ON p.logged_by_id = u.id
        LEFT JOIN users h ON p.handed_by_id = h.id
        WHERE p.id = ?
    """, (package_id,)).fetchone()

    if not package:
        conn.close()
        flash('Package not found.', 'danger')
        return redirect(url_for('dashboard'))

    # Security check for resident view
    current_user = get_current_user()
    if current_user and current_user['role'] == 'resident':
        # Allow only if recipient name/email/unit matches
        is_owner = (
            (package['recipient_email'] and package['recipient_email'].lower() == current_user['email'].lower()) or
            package['recipient_name'].lower() == current_user['full_name'].lower() or
            (current_user['unit_or_dept'] and package['recipient_unit'].lower() == current_user['unit_or_dept'].lower())
        )
        if not is_owner:
            conn.close()
            flash('You do not have permission to view this package.', 'danger')
            return redirect(url_for('resident_portal'))

    # Activity logs for this package
    logs = conn.execute("""
        SELECT * FROM activity_logs WHERE package_id = ? ORDER BY timestamp DESC
    """, (package_id,)).fetchall()

    conn.close()
    return render_template('package_detail.html', package=package, logs=logs, just_added=request.args.get('just_added'))

@app.route('/packages/<int:package_id>/handover', methods=['POST'])
@staff_required
def handover_package(package_id):
    conn = get_db_connection()
    package = conn.execute("SELECT * FROM packages WHERE id = ?", (package_id,)).fetchone()

    if not package:
        conn.close()
        flash('Package not found.', 'danger')
        return redirect(url_for('dashboard'))

    if package['status'] == 'Collected':
        conn.close()
        flash('This package has already been marked as Collected.', 'warning')
        return redirect(url_for('package_detail', package_id=package_id))

    entered_otp = request.form.get('pickup_code', '').strip()
    collected_by = request.form.get('collected_by_name', '').strip() or package['recipient_name']
    handover_notes = request.form.get('handover_notes', '').strip()
    verify_bypass = request.form.get('bypass_otp') == '1'

    # Validate OTP if not bypassed with staff manual override
    if not verify_bypass:
        if entered_otp != package['pickup_code']:
            conn.close()
            flash(f"Invalid Pickup OTP code! Recipient's code is required for handover verification.", 'danger')
            return redirect(url_for('package_detail', package_id=package_id))

    staff_user = get_current_user()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE packages 
        SET status = 'Collected',
            collected_date = datetime('now', 'localtime'),
            handed_by_id = ?,
            collected_by_name = ?,
            handover_notes = ?,
            signature_data = 'VERIFIED_HANDOVER'
        WHERE id = ?
    """, (staff_user['id'], collected_by, handover_notes, package_id))

    # Activity Log
    cursor.execute("""
        INSERT INTO activity_logs (package_id, action, performed_by_name, performed_by_role, details)
        VALUES (?, 'Handover', ?, ?, ?)
    """, (
        package_id, staff_user['full_name'], staff_user['role'].capitalize(),
        f"Handover confirmed for {package['tracking_number']} to '{collected_by}'. Note: {handover_notes or 'Standard collection'}"
    ))

    conn.commit()
    conn.close()

    flash(f"Package {package['tracking_number']} successfully marked as Collected!", 'success')
    return redirect(url_for('package_detail', package_id=package_id))

@app.route('/packages/<int:package_id>/edit', methods=['GET', 'POST'])
@staff_required
def edit_package(package_id):
    conn = get_db_connection()
    package = conn.execute("SELECT * FROM packages WHERE id = ?", (package_id,)).fetchone()

    if not package:
        conn.close()
        flash('Package not found.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        courier_name = request.form.get('courier_name', '').strip()
        recipient_name = request.form.get('recipient_name', '').strip()
        recipient_unit = request.form.get('recipient_unit', '').strip()
        recipient_phone = request.form.get('recipient_phone', '').strip()
        recipient_email = request.form.get('recipient_email', '').strip()
        storage_bin = request.form.get('storage_bin', '').strip()
        package_type = request.form.get('package_type', 'Box')
        weight = request.form.get('weight', '').strip()
        recipient_notes = request.form.get('recipient_notes', '').strip()
        status = request.form.get('status', package['status'])

        cursor = conn.cursor()
        cursor.execute("""
            UPDATE packages 
            SET courier_name = ?, recipient_name = ?, recipient_unit = ?, recipient_phone = ?,
                recipient_email = ?, storage_bin = ?, package_type = ?, weight = ?,
                recipient_notes = ?, status = ?
            WHERE id = ?
        """, (courier_name, recipient_name, recipient_unit, recipient_phone, recipient_email,
              storage_bin, package_type, weight, recipient_notes, status, package_id))

        staff_user = get_current_user()
        cursor.execute("""
            INSERT INTO activity_logs (package_id, action, performed_by_name, performed_by_role, details)
            VALUES (?, 'Edit', ?, ?, ?)
        """, (
            package_id, staff_user['full_name'], staff_user['role'].capitalize(),
            f"Package {package['tracking_number']} details updated (Bin: {storage_bin}, Status: {status})."
        ))

        conn.commit()
        conn.close()

        flash('Package updated successfully.', 'success')
        return redirect(url_for('package_detail', package_id=package_id))

    storage_bins = conn.execute("SELECT * FROM storage_bins ORDER BY bin_code").fetchall()
    conn.close()
    return render_template('edit_package.html', package=package, storage_bins=storage_bins)

@app.route('/packages/<int:package_id>/delete', methods=['POST'])
@staff_required
def delete_package(package_id):
    conn = get_db_connection()
    package = conn.execute("SELECT * FROM packages WHERE id = ?", (package_id,)).fetchone()
    if package:
        staff_user = get_current_user()
        conn.execute("DELETE FROM activity_logs WHERE package_id = ?", (package_id,))
        conn.execute("DELETE FROM packages WHERE id = ?", (package_id,))
        conn.commit()
        flash(f"Package {package['tracking_number']} deleted from records.", 'info')
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/packages/<int:package_id>/slip')
def print_slip(package_id):
    """Printable thermal/paper pickup slip."""
    conn = get_db_connection()
    package = conn.execute("""
        SELECT p.*, u.full_name as logged_by_name 
        FROM packages p
        LEFT JOIN users u ON p.logged_by_id = u.id
        WHERE p.id = ?
    """, (package_id,)).fetchone()
    conn.close()

    if not package:
        flash('Package not found.', 'danger')
        return redirect(url_for('dashboard'))

    return render_template('print_slip.html', package=package)

# -------------------------------------------------------------
# Resident Portal
# -------------------------------------------------------------

@app.route('/my-packages')
@login_required
def resident_portal():
    current_user = get_current_user()
    conn = get_db_connection()

    # Search for resident's packages by matching email, name, or unit
    pending_packages = conn.execute("""
        SELECT * FROM packages 
        WHERE status = 'Ready for Pickup' 
          AND (LOWER(recipient_email) = LOWER(?) OR LOWER(recipient_name) = LOWER(?) OR LOWER(recipient_unit) = LOWER(?))
        ORDER BY arrival_date DESC
    """, (current_user['email'], current_user['full_name'], current_user['unit_or_dept'] or '')).fetchall()

    collected_packages = conn.execute("""
        SELECT * FROM packages 
        WHERE status = 'Collected' 
          AND (LOWER(recipient_email) = LOWER(?) OR LOWER(recipient_name) = LOWER(?) OR LOWER(recipient_unit) = LOWER(?))
        ORDER BY collected_date DESC
    """, (current_user['email'], current_user['full_name'], current_user['unit_or_dept'] or '')).fetchall()

    conn.close()

    return render_template(
        'resident_portal.html',
        pending_packages=pending_packages,
        collected_packages=collected_packages
    )

# -------------------------------------------------------------
# Storage Bins & Shelf Management
# -------------------------------------------------------------

@app.route('/bins')
@staff_required
def storage_bins():
    conn = get_db_connection()
    bins_data = conn.execute("""
        SELECT b.*, 
               COUNT(p.id) as current_occupied,
               GROUP_CONCAT(p.tracking_number, ', ') as packages_list
        FROM storage_bins b
        LEFT JOIN packages p ON b.bin_code = p.storage_bin AND p.status = 'Ready for Pickup'
        GROUP BY b.id
        ORDER BY b.zone, b.bin_code
    """).fetchall()

    conn.close()
    return render_template('storage_bins.html', bins=bins_data)

@app.route('/bins/add', methods=['POST'])
@staff_required
def add_storage_bin():
    bin_code = request.form.get('bin_code', '').strip()
    zone = request.form.get('zone', '').strip()
    capacity = int(request.form.get('capacity', 10))
    notes = request.form.get('notes', '').strip()

    if not bin_code or not zone:
        flash('Bin Code and Zone are required.', 'danger')
        return redirect(url_for('storage_bins'))

    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO storage_bins (bin_code, zone, capacity, notes)
            VALUES (?, ?, ?, ?)
        """, (bin_code, zone, capacity, notes))
        conn.commit()
        flash(f"Storage Bin {bin_code} added successfully.", 'success')
    except Exception as e:
        flash(f"Bin code '{bin_code}' already exists.", 'danger')
    finally:
        conn.close()

    return redirect(url_for('storage_bins'))

# -------------------------------------------------------------
# Audit Logs & Activity
# -------------------------------------------------------------

@app.route('/logs')
@staff_required
def activity_logs():
    conn = get_db_connection()
    action_filter = request.args.get('action', 'all')

    sql = """
        SELECT l.*, p.tracking_number, p.recipient_name, p.recipient_unit 
        FROM activity_logs l
        LEFT JOIN packages p ON l.package_id = p.id
        WHERE 1=1
    """
    params = []
    if action_filter != 'all':
        sql += " AND l.action = ?"
        params.append(action_filter)

    sql += " ORDER BY l.timestamp DESC LIMIT 100"

    logs = conn.execute(sql, params).fetchall()
    conn.close()

    return render_template('activity_logs.html', logs=logs, action_filter=action_filter)

# -------------------------------------------------------------
# QR Code Generator & Export
# -------------------------------------------------------------

@app.route('/qr/<tracking_number>')
def generate_qr(tracking_number):
    """Dynamically generates a QR code image for a package tracking ID."""
    # The QR payload contains a direct track URL
    track_url = url_for('public_track', q=tracking_number, _external=True)
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(track_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

@app.route('/export/csv')
@staff_required
def export_csv():
    """Exports all package delivery logs as a CSV download."""
    conn = get_db_connection()
    packages = conn.execute("""
        SELECT p.tracking_number, p.courier_name, p.recipient_name, p.recipient_unit,
               p.recipient_phone, p.storage_bin, p.package_type, p.weight, p.status,
               p.arrival_date, p.collected_date, p.pickup_code, p.collected_by_name,
               u.full_name as logged_by
        FROM packages p
        LEFT JOIN users u ON p.logged_by_id = u.id
        ORDER BY p.arrival_date DESC
    """).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Tracking ID', 'Courier', 'Recipient Name', 'Unit/Dept', 'Phone',
        'Storage Bin', 'Package Type', 'Weight', 'Status', 'Arrival Date',
        'Collected Date', 'Pickup OTP', 'Collected By', 'Logged By'
    ])

    for pkg in packages:
        writer.writerow([
            pkg['tracking_number'], pkg['courier_name'], pkg['recipient_name'],
            pkg['recipient_unit'], pkg['recipient_phone'], pkg['storage_bin'],
            pkg['package_type'], pkg['weight'], pkg['status'], pkg['arrival_date'],
            pkg['collected_date'] or 'N/A', pkg['pickup_code'],
            pkg['collected_by_name'] or 'N/A', pkg['logged_by'] or 'N/A'
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=mailroom_report_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"}
    )

# -------------------------------------------------------------
# JSON APIs for live dynamic lookups
# -------------------------------------------------------------

@app.route('/api/search')
def api_search():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])

    conn = get_db_connection()
    pattern = f"%{q}%"
    results = conn.execute("""
        SELECT id, tracking_number, courier_name, recipient_name, recipient_unit, storage_bin, status
        FROM packages
        WHERE tracking_number LIKE ? OR recipient_name LIKE ? OR recipient_unit LIKE ?
        LIMIT 10
    """, (pattern, pattern, pattern)).fetchall()
    conn.close()

    return jsonify([dict(r) for r in results])

if __name__ == '__main__':
    # Default local dev server
    app.run(host='127.0.0.1', port=5000, debug=True)
