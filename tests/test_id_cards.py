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
    assert b'Student Library ID Cards' in admin_cards_res.data

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
