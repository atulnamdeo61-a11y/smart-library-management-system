import io
from app.extensions import db
from app.models.user import User
from app.models.password_reset_otp import PasswordResetOTP


def test_student_registration_success(client, app):
    """Test valid student registration creates an active student account."""
    res = client.post('/auth/register', data={
        'full_name': 'Ananya Roy',
        'email': 'ananya.roy@test.edu',
        'student_id': 'CS2026999',
        'phone': '9876543210',
        'password': 'SecurePass123',
        'confirm_password': 'SecurePass123'
    }, follow_redirects=True)

    assert res.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email='ananya.roy@test.edu').first()
        assert user is not None
        assert user.full_name == 'Ananya Roy'
        assert user.role == 'student'
        assert user.is_active is True
        assert user.password_hash != 'SecurePass123'
        assert user.check_password('SecurePass123') is True


def test_duplicate_email_registration_rejected(client, seed_test_data):
    """Test duplicate email registration is rejected with validation message."""
    res = client.post('/auth/register', data={
        'full_name': 'Duplicate User',
        'email': 'student1@test.edu',  # Already in seed_test_data
        'student_id': 'NEW999',
        'phone': '9876543210',
        'password': 'Password123',
        'confirm_password': 'Password123'
    })

    assert res.status_code == 200
    assert b'already registered' in res.data


def test_invalid_login_rejected(client, seed_test_data):
    """Test invalid password or unknown email displays error and denies login."""
    res = client.post('/auth/login', data={
        'email': 'student1@test.edu',
        'password': 'WrongPasswordXYZ'
    }, follow_redirects=True)

    assert res.status_code == 200
    assert b'Invalid email or password' in res.data


def test_passwords_are_securely_hashed(app):
    """Test Werkzeug password hashing verification."""
    with app.app_context():
        user = User(full_name='Hash Tester', email='hash@test.edu', role='student')
        user.set_password('MyPlaintextPassword')

        assert user.password_hash != 'MyPlaintextPassword'
        assert user.password_hash.startswith(('scrypt:', 'pbkdf2:'))
        assert user.check_password('MyPlaintextPassword') is True
        assert user.check_password('NotMyPassword') is False


def test_registration_cannot_set_admin_role(client, app):
    """Verify security rule: Public registration forces role='student' even if role tampering is attempted."""
    res = client.post('/auth/register', data={
        'full_name': 'Hacker Attempt',
        'email': 'hacker@test.edu',
        'student_id': 'HK001',
        'role': 'admin',  # Attempting to escalate role
        'password': 'Pass123456',
        'confirm_password': 'Pass123456'
    }, follow_redirects=True)

    assert res.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email='hacker@test.edu').first()
        assert user is not None
        assert user.role == 'student'  # Strictly remains student


def test_edit_profile_for_all_account_types(client, app, seed_test_data):
    """Verify students, librarians, and admins can edit their profile info."""
    roles = [
        ('student1@test.edu', 'StudentPass123', 'Updated Student One', '9111111111'),
        ('librarian@test.edu', 'LibPass123', 'Updated Librarian Staff', '9222222222'),
        ('admin@test.edu', 'AdminPass123', 'Updated Super Admin', '9333333333'),
    ]

    for email, password, new_name, new_phone in roles:
        # Login
        client.get('/auth/logout', follow_redirects=True)
        login_res = client.post('/auth/login', data={'email': email, 'password': password}, follow_redirects=True)
        assert login_res.status_code == 200

        # View Profile
        view_res = client.get('/auth/profile')
        assert view_res.status_code == 200
        assert b"Account Settings" in view_res.data

        # Post Profile Changes
        edit_res = client.post('/auth/profile', data={
            'full_name': new_name,
            'email': email,
            'phone': new_phone,
            'submit_profile': '1'
        }, follow_redirects=True)
        assert edit_res.status_code == 200
        assert b"updated successfully" in edit_res.data

        # Verify DB persisted changes
        with app.app_context():
            u = User.query.filter_by(email=email).first()
            assert u.full_name == new_name
            assert u.phone == new_phone


def test_change_password_for_all_account_types(client, app, seed_test_data):
    """Verify students, librarians, and admins can change passwords and authenticate with new passwords."""
    roles = [
        ('student2@test.edu', 'StudentPass123', 'NewStudentPass456'),
        ('librarian@test.edu', 'LibPass123', 'NewLibrarianPass456'),
        ('admin@test.edu', 'AdminPass123', 'NewAdminPass456'),
    ]

    for email, old_pass, new_pass in roles:
        # Login
        client.get('/auth/logout', follow_redirects=True)
        client.post('/auth/login', data={'email': email, 'password': old_pass}, follow_redirects=True)

        # 1. Attempt with incorrect current password
        bad_res = client.post('/auth/change-password', data={
            'current_password': 'WrongPassword999',
            'new_password': new_pass,
            'confirm_new_password': new_pass
        }, follow_redirects=True)
        assert b"Current password is incorrect" in bad_res.data

        # 2. Attempt with matching new password as current password
        same_res = client.post('/auth/change-password', data={
            'current_password': old_pass,
            'new_password': old_pass,
            'confirm_new_password': old_pass
        }, follow_redirects=True)
        assert b"different from your current password" in same_res.data

        # 3. Successful change
        good_res = client.post('/auth/change-password', data={
            'current_password': old_pass,
            'new_password': new_pass,
            'confirm_new_password': new_pass
        }, follow_redirects=True)
        assert good_res.status_code == 200
        assert b"password has been changed successfully" in good_res.data

        # 4. Verify login with NEW password succeeds
        client.get('/auth/logout', follow_redirects=True)
        relogin_res = client.post('/auth/login', data={'email': email, 'password': new_pass}, follow_redirects=True)
        assert relogin_res.status_code == 200
        assert b"Welcome back" in relogin_res.data


def test_forgot_password_request_and_otp_generation(client, app, seed_test_data):
    """Verify requesting OTP generates token and handles unknown accounts properly."""
    # 1. Non-existent account rejected
    res_unknown = client.post('/auth/forgot-password', data={'email': 'ghost@test.edu'}, follow_redirects=True)
    assert b"No registered account found" in res_unknown.data

    # 2. Existing student account generates OTP
    res_valid = client.post('/auth/forgot-password', data={'email': 'student1@test.edu'}, follow_redirects=True)
    assert res_valid.status_code == 200
    assert b"Verify OTP & Reset" in res_valid.data

    with app.app_context():
        otp_record = PasswordResetOTP.query.filter_by(email='student1@test.edu').first()
        assert otp_record is not None
        assert len(otp_record.otp_code) == 6
        assert otp_record.is_used is False


def test_otp_verification_and_password_reset(client, app, seed_test_data):
    """Verify OTP verification, rejection of bad OTPs, successful password reset, and single-use enforcement."""
    # Generate OTP for admin
    client.post('/auth/forgot-password', data={'email': 'admin@test.edu'}, follow_redirects=True)

    with app.app_context():
        otp_record = PasswordResetOTP.query.filter_by(email='admin@test.edu').order_by(PasswordResetOTP.id.desc()).first()
        valid_otp = otp_record.otp_code

    # 1. Invalid OTP rejected
    res_bad_otp = client.post('/auth/reset-password', data={
        'email': 'admin@test.edu',
        'otp': '999999',
        'password': 'BrandNewAdminPass789',
        'confirm_password': 'BrandNewAdminPass789'
    })
    assert b"Invalid or expired OTP code" in res_bad_otp.data

    # 2. Mismatched passwords rejected
    res_mismatch = client.post('/auth/reset-password', data={
        'email': 'admin@test.edu',
        'otp': valid_otp,
        'password': 'BrandNewAdminPass789',
        'confirm_password': 'DifferentPassword123'
    })
    assert b"must match" in res_mismatch.data

    # 3. Successful password reset with valid OTP
    res_success = client.post('/auth/reset-password', data={
        'email': 'admin@test.edu',
        'otp': valid_otp,
        'password': 'BrandNewAdminPass789',
        'confirm_password': 'BrandNewAdminPass789'
    }, follow_redirects=True)
    assert res_success.status_code == 200
    assert b"password has been successfully reset" in res_success.data

    # 4. Verify OTP is now marked as used
    with app.app_context():
        check_otp = PasswordResetOTP.query.filter_by(email='admin@test.edu', otp_code=valid_otp).first()
        assert check_otp.is_used is True

    # 5. Attempting to reuse the exact same OTP fails
    res_reuse = client.post('/auth/reset-password', data={
        'email': 'admin@test.edu',
        'otp': valid_otp,
        'password': 'YetAnotherPassword123',
        'confirm_password': 'YetAnotherPassword123'
    })
    assert b"Invalid or expired OTP code" in res_reuse.data

    # 6. Verify logging in with the newly reset password works
    login_res = client.post('/auth/login', data={'email': 'admin@test.edu', 'password': 'BrandNewAdminPass789'}, follow_redirects=True)
    assert login_res.status_code == 200
    assert b"Welcome back" in login_res.data


def test_user_profile_image_upload_and_removal(client, app, seed_test_data):
    """Verify users can upload a custom profile picture and also remove it."""
    # Login as student
    client.get('/auth/logout', follow_redirects=True)
    client.post('/auth/login', data={'email': 'student1@test.edu', 'password': 'StudentPass123'}, follow_redirects=True)

    # 1. Upload a PNG avatar
    avatar_bytes = io.BytesIO(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")
    upload_res = client.post('/auth/profile', data={
        'full_name': 'Student One With Photo',
        'email': 'student1@test.edu',
        'phone': '9998887776',
        'profile_image': (avatar_bytes, 'my_avatar.png'),
        'submit_profile': '1'
    }, content_type='multipart/form-data', follow_redirects=True)

    assert upload_res.status_code == 200
    assert b"updated successfully" in upload_res.data

    with app.app_context():
        u = User.query.filter_by(email='student1@test.edu').first()
        assert u.profile_image is not None
        assert u.profile_image.startswith('uploads/avatars/avatar_')
        assert u.profile_image.endswith('.png')

    # 2. Check profile page renders image
    page_res = client.get('/auth/profile')
    assert b"uploads/avatars/avatar_" in page_res.data

    # 3. Remove profile image
    remove_res = client.post('/auth/profile', data={
        'full_name': 'Student One With Photo',
        'email': 'student1@test.edu',
        'phone': '9998887776',
        'remove_image': 'y',
        'submit_profile': '1'
    }, follow_redirects=True)

    assert remove_res.status_code == 200
    with app.app_context():
        u = User.query.filter_by(email='student1@test.edu').first()
        assert u.profile_image is None



