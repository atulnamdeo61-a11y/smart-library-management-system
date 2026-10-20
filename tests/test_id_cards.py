import pytest
from app.extensions import db
from app.models.user import User
from app.models.id_card import StudentIdCard


def login_user(client, email, password):
    """Helper to log in a user."""
    client.post('/auth/logout', follow_redirects=True)
    return client.post('/auth/login', data={
        'email': email,
        'password': password
    }, follow_redirects=True)


def test_student_request_id_card_workflow(client, seed_test_data):
    """Test student can request an ID card with details and receives a pending application with UPI QR."""
    # Login as student1
    login_user(client, 'student1@test.edu', 'StudentPass123')

    # View ID card page initially
    res = client.get('/student/id-card')
    assert res.status_code == 200
    assert b'Apply for Student Library ID Card' in res.data

    # Submit application
    post_res = client.post('/student/id-card', data={
        'course_branch': 'B.Tech Computer Science',
        'academic_year': '2024-2028',
        'blood_group': 'O+',
        'dob': '2004-05-15',
        'emergency_contact': '9876543210',
        'address': 'Boys Hostel Block A, Room 102'
    }, follow_redirects=True)

    assert post_res.status_code == 200
    assert b'Your Student ID Card application was created' in post_res.data
    assert b'Scan to Pay ID Card Fee' in post_res.data

    # Verify DB record
    card = StudentIdCard.query.filter_by(roll_number='S001').first()
    assert card is not None
    assert card.status == StudentIdCard.STATUS_PENDING
    assert card.payment_status == StudentIdCard.PAYMENT_PENDING
    assert card.course_branch == 'B.Tech Computer Science'
    assert card.blood_group == 'O+'
    assert card.upi_qr_path is not None


def test_student_submit_upi_payment(client, seed_test_data):
    """Test student submits 12-digit UPI UTR transaction reference."""
    login_user(client, 'student1@test.edu', 'StudentPass123')

    # Submit ID Card request first
    client.post('/student/id-card', data={
        'course_branch': 'B.Tech IT',
        'academic_year': '2023-2027',
    }, follow_redirects=True)

    # Submit payment reference
    pay_res = client.post('/student/id-card/pay', data={
        'utr_reference': '429381729012'
    }, follow_redirects=True)

    assert pay_res.status_code == 200
    assert b'Application Queued for Approval' in pay_res.data

    # Verify DB payment update
    card = StudentIdCard.query.filter_by(roll_number='S001').first()
    assert card.payment_status == StudentIdCard.PAYMENT_PAID
    assert card.payment_reference == '429381729012'
    assert card.paid_at is not None


def test_librarian_review_and_approve_id_card(client, seed_test_data):
    """Test librarian can view pending cards and approve student application."""
    # 1. Student creates and pays
    login_user(client, 'student1@test.edu', 'StudentPass123')
    client.post('/student/id-card', data={
        'course_branch': 'Mechanical Engineering',
        'academic_year': '2024-2028',
    }, follow_redirects=True)
    client.post('/student/id-card/pay', data={'utr_reference': '998877665544'}, follow_redirects=True)

    # 2. Login as Librarian
    login_user(client, 'librarian@test.edu', 'LibPass123')

    # View list
    res = client.get('/librarian/id-cards')
    assert res.status_code == 200
    assert b'Mechanical Engineering' in res.data
    assert b'998877665544' in res.data

    # Approve card
    card = StudentIdCard.query.filter_by(roll_number='S001').first()
    approve_res = client.post(f'/librarian/id-cards/{card.id}/approve', data={
        'validity_years': '3'
    }, follow_redirects=True)

    assert approve_res.status_code == 200
    assert b'approved and issued successfully' in approve_res.data

    # Verify approved state and generated circulation QR
    db.session.refresh(card)
    assert card.status == StudentIdCard.STATUS_APPROVED
    assert card.issue_date is not None
    assert card.expiry_date is not None
    assert card.qr_code_path is not None


def test_librarian_reject_id_card(client, seed_test_data):
    """Test librarian can reject an application with remarks."""
    login_user(client, 'student2@test.edu', 'StudentPass123')
    client.post('/student/id-card', data={
        'course_branch': 'Civil Engineering',
        'academic_year': '2024-2028',
    }, follow_redirects=True)

    # Login as Librarian and reject
    login_user(client, 'librarian@test.edu', 'LibPass123')
    card = StudentIdCard.query.filter_by(roll_number='S002').first()

    reject_res = client.post(f'/librarian/id-cards/{card.id}/reject', data={
        'rejection_remarks': 'Invalid admission batch specified.'
    }, follow_redirects=True)

    assert reject_res.status_code == 200
    assert b'was rejected' in reject_res.data

    db.session.refresh(card)
    assert card.status == StudentIdCard.STATUS_REJECTED
    assert card.rejection_remarks == 'Invalid admission batch specified.'

    # Student views rejection remarks and re-apply option
    login_user(client, 'student2@test.edu', 'StudentPass123')
    stu_res = client.get('/student/id-card')
    assert b'ID Card Application Rejected' in stu_res.data
    assert b'Invalid admission batch specified.' in stu_res.data
    assert b'Re-submit Application' in stu_res.data


def test_staff_direct_issue_id_card(client, seed_test_data):
    """Test staff (librarian or admin) can directly generate an ID card for any student."""
    login_user(client, 'librarian@test.edu', 'LibPass123')

    # View direct issue form
    form_res = client.get('/librarian/id-cards/new')
    assert form_res.status_code == 200
    assert b'Issue Student Library ID Card' in form_res.data

    # Submit direct issuance
    student1 = seed_test_data['student1']
    issue_res = client.post('/librarian/id-cards/new', data={
        'student_id': student1.id,
        'course_branch': 'Electrical Engineering',
        'academic_year': '2024-2028',
        'blood_group': 'B+',
        'payment_status': 'Paid',
        'payment_method': 'Cash',
        'payment_reference': 'COUNTER-CASH-001',
        'validity_years': '4'
    }, follow_redirects=True)

    assert issue_res.status_code == 200
    assert b'created and approved successfully' in issue_res.data

    # Check database
    card = StudentIdCard.query.filter_by(student_id=student1.id).first()
    assert card is not None
    assert card.status == StudentIdCard.STATUS_APPROVED
    assert card.course_branch == 'Electrical Engineering'
    assert card.payment_method == 'Cash'
    assert card.qr_code_path is not None


def test_admin_id_card_management_and_settings(client, seed_test_data):
    """Test admin has full ID card management capability and can update fee & UPI settings."""
    login_user(client, 'admin@test.edu', 'AdminPass123')

    # 1. Update settings
    settings_res = client.post('/admin/settings', data={
        'borrow_days': '21',
        'fine_rate': '3.00',
        'max_loans': '5',
        'id_card_fee': '75.00',
        'upi_id': 'college@icici',
        'upi_payee_name': 'Imperial College Library'
    }, follow_redirects=True)

    assert settings_res.status_code == 200
    assert b'System configuration rules updated successfully' in settings_res.data

    # 2. Access Admin ID cards list
    admin_cards_res = client.get('/admin/id-cards')
    assert admin_cards_res.status_code == 200
    assert b'Library ID Cards Management' in admin_cards_res.data

    # 3. Direct issue by Admin
    student2 = seed_test_data['student2']
    admin_issue_res = client.post('/admin/id-cards/new', data={
        'student_id': student2.id,
        'course_branch': 'Robotics & AI',
        'academic_year': '2025-2029',
        'blood_group': 'AB+',
        'payment_status': 'Waived',
        'payment_method': 'Direct Staff Issue',
        'validity_years': '4'
    }, follow_redirects=True)

    assert admin_issue_res.status_code == 200
    assert b'created and approved successfully' in admin_issue_res.data

    card = StudentIdCard.query.filter_by(student_id=student2.id).first()
    assert card.status == StudentIdCard.STATUS_APPROVED
    assert card.course_branch == 'Robotics & AI'
    assert card.payment_status == 'Waived'


def test_student_print_approved_card(client, seed_test_data):
    """Test approved student can access the printable CR80 ID card layout."""
    # Create approved card directly
    student1 = seed_test_data['student1']
    card = StudentIdCard(
        student_id=student1.id,
        roll_number='S001',
        course_branch='Data Science',
        academic_year='2024-2028',
        card_number=StudentIdCard.generate_card_number('S001'),
        status=StudentIdCard.STATUS_APPROVED
    )
    card.approve(staff_user_id=seed_test_data['librarian'].id)
    db.session.add(card)
    db.session.commit()

    # Login as student1 and view print page
    login_user(client, 'student1@test.edu', 'StudentPass123')
    print_res = client.get('/student/id-card/print')
    assert print_res.status_code == 200
    assert b'SMART COLLEGE LIBRARY' in print_res.data
    assert b'STUDENT IDENTITY CARD' in print_res.data
    assert b'Data Science' in print_res.data
    assert b'Circulation Counter Access' in print_res.data


def test_authorization_restrictions(client, seed_test_data):
    """Test students cannot access staff ID card routes and unauthenticated users are redirected."""
    # Unauthenticated redirect
    res = client.get('/student/id-card')
    assert res.status_code == 302
    assert '/auth/login' in res.headers['Location']

    # Student trying staff routes gets 403 Forbidden
    login_user(client, 'student1@test.edu', 'StudentPass123')
    lib_res = client.get('/librarian/id-cards')
    assert lib_res.status_code == 403

    admin_res = client.get('/admin/id-cards')
    assert admin_res.status_code == 403

    # Ensure an approved card exists before staff print test
    student1 = seed_test_data['student1']
    existing_approved = StudentIdCard.query.filter_by(student_id=student1.id, status=StudentIdCard.STATUS_APPROVED).first()
    if not existing_approved:
        card = StudentIdCard(
            student_id=student1.id,
            roll_number='S001',
            course_branch='Data Science',
            academic_year='2024-2028',
            card_number=StudentIdCard.generate_card_number('S001'),
            status=StudentIdCard.STATUS_APPROVED
        )
        card.approve(staff_user_id=seed_test_data['librarian'].id)
        db.session.add(card)
        db.session.commit()

    # Staff (Admin and Librarian) can access print view without 403 Forbidden
    login_user(client, 'admin@test.edu', 'AdminPass123')
    staff_print_res = client.get('/student/id-card/print')
    assert staff_print_res.status_code == 200
    assert b'SMART COLLEGE LIBRARY' in staff_print_res.data


def test_librarian_request_staff_id_card(client, seed_test_data):
    """Test librarian requests a staff ID card with waived fee and status queued for Admin approval."""
    librarian = seed_test_data['librarian']
    login_user(client, librarian.email, 'LibPass123')

    # View my-id-card application page
    get_res = client.get('/librarian/my-id-card')
    assert get_res.status_code == 200
    assert b'Request Official Librarian ID Card' in get_res.data
    assert b'Security Governance:' in get_res.data

    # Submit staff application
    post_res = client.post('/librarian/my-id-card', data={
        'staff_code': 'LIB-TEST-001',
        'designation': 'Assistant Librarian',
        'department': 'Central Library - Cataloging Division',
        'blood_group': 'B+',
        'dob': '1990-08-20',
        'emergency_contact': '9876501234',
        'address': 'Staff Quarters Q-14, North Campus'
    }, follow_redirects=True)

    assert post_res.status_code == 200
    assert b'Staff Library ID Card application submitted! As per library policy, it is queued for Administrator approval.' in post_res.data
    assert b'Staff ID Card Queued for Admin Approval' in post_res.data

    # Verify database state
    card = StudentIdCard.query.filter_by(student_id=librarian.id).first()
    assert card is not None
    assert card.status == StudentIdCard.STATUS_PENDING
    assert card.payment_status == 'Waived'
    assert card.fee_amount == 0.0
    assert card.roll_number == 'LIB-TEST-001'
    assert card.academic_year == 'Assistant Librarian'
    assert card.course_branch == 'Central Library - Cataloging Division'


def test_librarian_cannot_approve_staff_id_card(client, seed_test_data):
    """Test strict governance: Librarian CANNOT approve or reject Staff / Librarian ID cards."""
    librarian = seed_test_data['librarian']

    # Create a pending staff ID card for librarian
    staff_card = StudentIdCard(
        student_id=librarian.id,
        roll_number='LIB-TEST-002',
        course_branch='Central Library',
        academic_year='Senior Librarian',
        card_number=StudentIdCard.generate_card_number('LIB-TEST-002'),
        status=StudentIdCard.STATUS_PENDING,
        payment_status='Waived',
        payment_method='Staff / Institutional',
        fee_amount=0.0
    )
    db.session.add(staff_card)
    db.session.commit()

    # Login as Librarian
    login_user(client, librarian.email, 'LibPass123')

    # Librarian tries to approve staff card
    approve_res = client.post(f'/librarian/id-cards/{staff_card.id}/approve', data={
        'validity_years': '3'
    }, follow_redirects=True)

    assert approve_res.status_code == 200
    assert b'Access Denied: Staff and Librarian ID cards can ONLY be approved by a System Administrator.' in approve_res.data

    # Card must still be pending
    db.session.refresh(staff_card)
    assert staff_card.status == StudentIdCard.STATUS_PENDING
    assert staff_card.approved_by is None

    # Librarian tries to reject staff card
    reject_res = client.post(f'/librarian/id-cards/{staff_card.id}/reject', data={
        'rejection_remarks': 'Unauthorized rejection attempt'
    }, follow_redirects=True)

    assert reject_res.status_code == 200
    assert b'Access Denied: Staff and Librarian ID cards can ONLY be rejected by a System Administrator.' in reject_res.data
    db.session.refresh(staff_card)
    assert staff_card.status == StudentIdCard.STATUS_PENDING


def test_admin_approves_staff_id_card(client, seed_test_data):
    """Test System Administrator approves Librarian staff ID card and generates valid CR80 staff credentials."""
    librarian = seed_test_data['librarian']
    admin = seed_test_data['admin']

    # Create pending staff card
    staff_card = StudentIdCard(
        student_id=librarian.id,
        roll_number='LIB-TEST-003',
        course_branch='Library Acquisition Dept',
        academic_year='Head Librarian',
        blood_group='O+',
        card_number=StudentIdCard.generate_card_number('LIB-TEST-003'),
        status=StudentIdCard.STATUS_PENDING,
        payment_status='Waived',
        payment_method='Staff / Institutional',
        fee_amount=0.0
    )
    db.session.add(staff_card)
    db.session.commit()

    # Login as Admin
    login_user(client, admin.email, 'AdminPass123')

    # Admin filters ID cards by role=staff
    filter_res = client.get('/admin/id-cards?role=staff')
    assert filter_res.status_code == 200
    assert b'LIB-TEST-003' in filter_res.data

    # Admin approves librarian's staff card
    approve_res = client.post(f'/admin/id-cards/{staff_card.id}/approve', data={
        'validity_years': '5'
    }, follow_redirects=True)

    assert approve_res.status_code == 200
    assert b'approved and issued successfully' in approve_res.data

    db.session.refresh(staff_card)
    assert staff_card.status == StudentIdCard.STATUS_APPROVED
    assert staff_card.approved_by == admin.id
    assert staff_card.issue_date is not None
    assert staff_card.expiry_date is not None
    assert staff_card.qr_code_path is not None

    # Print route displays staff layout
    print_res = client.get(f'/admin/id-cards/{staff_card.id}/print')
    assert print_res.status_code == 200
    assert b'FACULTY & LIBRARIAN IDENTITY CARD' in print_res.data
    assert b'Department' in print_res.data
    assert b'Designation' in print_res.data
    assert b'Official Staff Credential & Circulation Desk' in print_res.data


def test_admin_direct_my_id_card(client, seed_test_data):
    """Test Administrator generates and self-issues an Executive Administrator ID card."""
    admin = seed_test_data['admin']
    login_user(client, admin.email, 'AdminPass123')

    # View Admin My ID Card page
    get_res = client.get('/admin/my-id-card')
    assert get_res.status_code == 200
    assert b'Request Official Administrator ID Card' in get_res.data
    assert b'Issue Official Administrator ID Card' in get_res.data

    # Submit Admin self-issuance
    post_res = client.post('/admin/my-id-card', data={
        'staff_code': 'ADM-EXEC-001',
        'designation': 'Chief Information Officer & Library Admin',
        'department': 'Central Library Directorate',
        'blood_group': 'AB+',
        'validity_years': '5'
    }, follow_redirects=True)

    assert post_res.status_code == 200
    assert b'Administrator Library ID Card' in post_res.data
    assert b'created and approved!' in post_res.data
    assert b'Authorized Staff Card Active' in post_res.data
    assert b'ADM-EXEC-001' in post_res.data

    card = StudentIdCard.query.filter_by(student_id=admin.id).first()
    assert card is not None
    assert card.status == StudentIdCard.STATUS_APPROVED
    assert card.approved_by == admin.id
    assert card.fee_amount == 0.0
    assert card.payment_status == 'Waived'
    assert card.qr_code_path is not None

