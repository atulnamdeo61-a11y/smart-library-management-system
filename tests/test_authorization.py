import pytest


def login_as(client, email, password):
    """Helper to log in a test client."""
    return client.post('/auth/login', data={
        'email': email,
        'password': password
    }, follow_redirects=True)


def test_unauthenticated_user_redirected_to_login(client):
    """Verify unauthenticated user cannot access protected routes."""
    res = client.get('/student/dashboard', follow_redirects=False)
    assert res.status_code == 302
    assert '/auth/login' in res.headers['Location']

    res_admin = client.get('/admin/dashboard', follow_redirects=False)
    assert res_admin.status_code == 302
    assert '/auth/login' in res_admin.headers['Location']


def test_student_cannot_access_admin_dashboard(client, seed_test_data):
    """Students attempting to access /admin routes must receive 403 Forbidden."""
    login_as(client, 'student1@test.edu', 'StudentPass123')
    res = client.get('/admin/dashboard')
    assert res.status_code == 403


def test_student_cannot_access_librarian_operations(client, seed_test_data):
    """Students attempting to access /librarian routes must receive 403 Forbidden."""
    login_as(client, 'student1@test.edu', 'StudentPass123')
    res = client.get('/librarian/dashboard')
    assert res.status_code == 403


def test_librarian_cannot_access_admin_settings(client, seed_test_data):
    """Librarians cannot access restricted admin settings."""
    login_as(client, 'librarian@test.edu', 'LibPass123')
    res = client.get('/admin/settings')
    assert res.status_code == 403


def test_admin_can_access_admin_dashboard(client, seed_test_data):
    """Admin has full authorization to access administrative dashboard."""
    login_as(client, 'admin@test.edu', 'AdminPass123')
    res = client.get('/admin/dashboard')
    assert res.status_code == 200
    assert b'Library Administration' in res.data
