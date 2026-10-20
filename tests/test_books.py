import pytest
from app.models.book import Book
from app.services.qr_service import QRService


def login_as_admin(client):
    return client.post('/auth/login', data={
        'email': 'admin@test.edu',
        'password': 'AdminPass123'
    }, follow_redirects=True)


def test_book_catalog_display_and_search(client, seed_test_data):
    """Test public catalog search returns matching titles."""
    res = client.get('/books/?q=Python')
    assert res.status_code == 200
    assert b'Python Programming Mastery' in res.data
    assert b'Discrete Mathematics' not in res.data


def test_book_category_filtering(client, seed_test_data):
    """Test category filtering displays only books within that category."""
    cat_math_id = seed_test_data['cat_math'].id
    res = client.get(f'/books/?category={cat_math_id}')
    assert res.status_code == 200
    assert b'Discrete Mathematics' in res.data
    assert b'Python Programming Mastery' not in res.data


def test_admin_can_create_book(client, seed_test_data, app):
    """Test book creation via admin form."""
    login_as_admin(client)
    cat_cs_id = seed_test_data['cat_cs'].id

    res = client.post('/admin/books/new', data={
        'title': 'Compilers: Principles and Techniques',
        'author': 'Aho, Lam, Sethi, Ullman',
        'isbn': '978-0321486813',
        'category_id': cat_cs_id,
        'publisher': 'Pearson',
        'publication_year': 2006,
        'shelf_location': 'CS-09',
        'total_copies': 4,
        'available_copies': 4,
        'description': 'Dragon book for compiler design.'
    }, follow_redirects=True)

    assert res.status_code == 200
    with app.app_context():
        book = Book.query.filter_by(isbn='978-0321486813').first()
        assert book is not None
        assert book.title == 'Compilers: Principles and Techniques'
        assert book.available_copies == 4
        assert book.qr_code_path is not None


def test_invalid_available_copies_rejected(client, seed_test_data):
    """Available copies exceeding total copies must fail validation."""
    login_as_admin(client)
    cat_cs_id = seed_test_data['cat_cs'].id

    res = client.post('/admin/books/new', data={
        'title': 'Invalid Copies Book',
        'author': 'Author X',
        'isbn': '978-9999999999',
        'category_id': cat_cs_id,
        'total_copies': 2,
        'available_copies': 5  # Invalid: 5 > 2
    })

    assert res.status_code == 200
    assert b'Available copies cannot exceed total copies' in res.data


def test_qr_code_generation_service(app, seed_test_data):
    """Test QRService generates QR PNG and updates book model."""
    with app.app_context():
        book = seed_test_data['book1']
        qr_path = QRService.generate_qr_for_book(book)
        assert qr_path.startswith('qrcodes/book_')
        assert book.qr_code_path == qr_path
