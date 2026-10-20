import pytest
from datetime import date, timedelta
from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.category import Category
from app.models.book import Book
from app.models.book_loan import BookLoan
from app.models.fine import Fine
from app.models.student_preference import StudentPreference
from app.models.password_reset_otp import PasswordResetOTP
from app.models.id_card import StudentIdCard


@pytest.fixture
def app():
    """Create application configured for testing with isolated in-memory DB."""
    app = create_app('testing')
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False,
        'SERVER_NAME': 'localhost'
    })

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Test HTTP client."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """CLI test runner."""
    return app.test_cli_runner()


@pytest.fixture
def seed_test_data(app):
    """Seed baseline test entities into the in-memory database."""
    # 1. Users
    admin = User(full_name='Test Admin', email='admin@test.edu', role='admin', is_active=True)
    admin.set_password('AdminPass123')

    librarian = User(full_name='Test Librarian', email='librarian@test.edu', role='librarian', is_active=True)
    librarian.set_password('LibPass123')

    student1 = User(full_name='Student One', email='student1@test.edu', student_id='S001', role='student', is_active=True)
    student1.set_password('StudentPass123')

    student2 = User(full_name='Student Two', email='student2@test.edu', student_id='S002', role='student', is_active=True)
    student2.set_password('StudentPass123')

    db.session.add_all([admin, librarian, student1, student2])
    db.session.flush()

    # 2. Categories
    cat_cs = Category(name='Computer Science', description='CS studies')
    cat_math = Category(name='Mathematics', description='Math studies')
    db.session.add_all([cat_cs, cat_math])
    db.session.flush()

    # 3. Books
    book1 = Book(
        isbn='978-1111111111',
        title='Python Programming Mastery',
        author='Guido van Rossum',
        category_id=cat_cs.id,
        total_copies=3,
        available_copies=3,
        shelf_location='CS-1',
        is_active=True
    )
    book2 = Book(
        isbn='978-2222222222',
        title='Discrete Mathematics',
        author='Kenneth Rosen',
        category_id=cat_math.id,
        total_copies=2,
        available_copies=2,
        shelf_location='MATH-1',
        is_active=True
    )
    book_unavailable = Book(
        isbn='978-3333333333',
        title='Rare Manuscript',
        author='Ancient Scholar',
        category_id=cat_cs.id,
        total_copies=1,
        available_copies=0,
        shelf_location='VAULT-1',
        is_active=True
    )
    db.session.add_all([book1, book2, book_unavailable])
    db.session.commit()

    return {
        'admin': admin,
        'librarian': librarian,
        'student1': student1,
        'student2': student2,
        'cat_cs': cat_cs,
        'cat_math': cat_math,
        'book1': book1,
        'book2': book2,
        'book_unavailable': book_unavailable
    }
