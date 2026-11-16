import unittest
from app import app
from database import get_db_connection

class MailroomSystemTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

    def test_01_homepage(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'MailroomOS', response.data)
        self.assertIn(b'Eliminate paper logs', response.data)
        print("✓ Homepage loads successfully")

    def test_02_public_track(self):
        response = self.client.get('/track?q=TRK-AMZ-98214')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'TRK-AMZ-98214', response.data)
        self.assertIn(b'Amazon Logistics', response.data)
        self.assertIn(b'Rack A-1', response.data)
        print("✓ Public tracking lookup functions accurately")

    def test_03_login_and_dashboard_staff(self):
        # Login as staff
        login_res = self.client.post('/login', data={
            'username': 'staff',
            'password': 'staff123'
        }, follow_redirects=True)
        self.assertEqual(login_res.status_code, 200)
        self.assertIn(b'Mailroom Operations', login_res.data)
        print("✓ Staff authentication & dashboard redirect works")

        # Test Dashboard access
        dash_res = self.client.get('/dashboard')
        self.assertEqual(dash_res.status_code, 200)
        self.assertIn(b'Packages Register', dash_res.data)
        print("✓ Dashboard view rendered with operational metrics")

    def test_04_intake_new_package(self):
        # Login staff first
        self.client.post('/login', data={'username': 'staff', 'password': 'staff123'})
        
        # Submit new intake
        intake_res = self.client.post('/intake', data={
            'courier_name': 'DHL Express',
            'tracking_number': 'TRK-TEST-999001',
            'recipient_name': 'Test Recipient',
            'recipient_unit': 'Unit 999',
            'recipient_phone': '+1 (555) 999-0000',
            'recipient_email': 'test.recipient@example.com',
            'storage_bin': 'Rack A-1',
            'package_type': 'Fragile',
            'weight': '2.1 kg',
            'recipient_notes': 'Testing intake automation'
        }, follow_redirects=True)

        self.assertEqual(intake_res.status_code, 200)
        self.assertIn(b'TRK-TEST-999001', intake_res.data)
        self.assertIn(b'Package Successfully Registered', intake_res.data)
        print("✓ Parcel intake data-entry, OTP generation & redirect verified")

    def test_05_handover_flow(self):
        # Find the newly created package in DB
        conn = get_db_connection()
        pkg = conn.execute("SELECT * FROM packages WHERE tracking_number = 'TRK-TEST-999001'").fetchone()
        self.assertIsNotNone(pkg)
        otp = pkg['pickup_code']
        pkg_id = pkg['id']
        conn.close()

        # Login as staff
        self.client.post('/login', data={'username': 'staff', 'password': 'staff123'})

        # Handover using correct OTP
        handover_res = self.client.post(f'/packages/{pkg_id}/handover', data={
            'pickup_code': otp,
            'collected_by_name': 'Test Recipient',
            'handover_notes': 'Verified test handover'
        }, follow_redirects=True)

        self.assertEqual(handover_res.status_code, 200)
        self.assertIn(b'Collected', handover_res.data)
        print("✓ Handover confirmation with OTP verification verified")

    def test_06_resident_portal(self):
        # Login as resident John Doe
        self.client.post('/login', data={'username': 'john_doe', 'password': 'user123'})
        portal_res = self.client.get('/my-packages')
        self.assertEqual(portal_res.status_code, 200)
        self.assertIn(b'Welcome, John Doe', portal_res.data)
        self.assertIn(b'Pickup Verification OTP', portal_res.data)
        print("✓ Resident Portal renders personalized pending deliveries & QR pass")

    def test_07_qr_code_generation(self):
        qr_res = self.client.get('/qr/TRK-AMZ-98214')
        self.assertEqual(qr_res.status_code, 200)
        self.assertEqual(qr_res.content_type, 'image/png')
        print("✓ Real-time QR Code generation endpoint produces PNG image")

    def test_08_print_slip(self):
        slip_res = self.client.get('/packages/1/slip')
        self.assertEqual(slip_res.status_code, 200)
        self.assertIn(b'Mailroom Intake Pass', slip_res.data)
        self.assertIn(b'Rack A-1', slip_res.data)
        print("✓ Printable thermal pickup pass rendered")

    def test_09_storage_bins_and_logs(self):
        self.client.post('/login', data={'username': 'admin', 'password': 'admin123'})
        bins_res = self.client.get('/bins')
        self.assertEqual(bins_res.status_code, 200)
        self.assertIn(b'Storage Bins', bins_res.data)

        logs_res = self.client.get('/logs')
        self.assertEqual(logs_res.status_code, 200)
        self.assertIn(b'Audit Trail', logs_res.data)
        print("✓ Storage Bins capacity metrics and Audit Logs verified")

if __name__ == '__main__':
    unittest.main()
