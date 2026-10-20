import click
from datetime import date, datetime, timedelta
from flask.cli import with_appcontext
from app.extensions import db
from app.models.user import User
from app.models.category import Category
from app.models.book import Book
from app.models.book_request import BookRequest
from app.models.book_loan import BookLoan
from app.models.fine import Fine, FinePayment
from app.models.student_preference import StudentPreference
from app.models.audit_log import AuditLog
from app.services.qr_service import QRService
from app.services.fine_service import calculate_fine_for_loan


@click.command('init-db')
@with_appcontext
def init_db_command():
    """Create all database tables."""
    db.create_all()
    click.echo("[OK] Database tables initialized successfully.")


@click.command('create-admin')
@click.option('--name', prompt='Admin Full Name', default='System Administrator', help='Full name of administrator')
@click.option('--email', prompt='Admin Email', default='admin@college.edu', help='Email of administrator')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='Admin password')
@with_appcontext
def create_admin_command(name, email, password):
    """Create initial administrator user."""
    db.create_all()
    existing = User.query.filter(User.email.ilike(email.strip())).first()
    if existing:
        click.echo(f"Error: User with email '{email}' already exists.")
        return

    admin = User(
        full_name=name.strip(),
        email=email.strip().lower(),
        role='admin',
        is_active=True
    )
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    click.echo(f"[OK] Initial Administrator created successfully: {admin.email}")


@click.command('seed-data')
@with_appcontext
def seed_data_command():
    """Seed fictional academic categories, books, users, and demonstration loans."""
    db.create_all()
    click.echo("Starting database seed process...")

    # 1. Create or retrieve Admin
    admin = User.query.filter_by(email='admin@college.edu').first()
    if not admin:
        admin = User(
            full_name='Dr. R. K. Sharma',
            email='admin@college.edu',
            role='admin',
            phone='+91 98765 43210',
            is_active=True
        )
        admin.set_password('Admin@123')
        db.session.add(admin)
        click.echo("  [OK] Created Admin: admin@college.edu (Password: Admin@123)")

    # 2. Create or retrieve Librarian
    librarian = User.query.filter_by(email='librarian@college.edu').first()
    if not librarian:
        librarian = User(
            full_name='Mrs. Sunita Verma',
            email='librarian@college.edu',
            role='librarian',
            phone='+91 98765 12345',
            is_active=True
        )
        librarian.set_password('Librarian@123')
        db.session.add(librarian)
        click.echo("  [OK] Created Librarian: librarian@college.edu (Password: Librarian@123)")

    # 3. Create Demo Students
    students_data = [
        ('Aarav Patel', 'aarav.student@college.edu', 'CS2023001', '+91 98111 22233', 'Student@123'),
        ('Priya Nair', 'priya.student@college.edu', 'IT2023045', '+91 98222 33344', 'Student@123'),
        ('Rohan Gupta', 'rohan.student@college.edu', 'EC2023089', '+91 98333 44455', 'Student@123'),
    ]
    created_students = []
    for name, email, roll, phone, pwd in students_data:
        student = User.query.filter_by(email=email).first()
        if not student:
            student = User(
                full_name=name,
                email=email,
                student_id=roll,
                role='student',
                phone=phone,
                is_active=True
            )
            student.set_password(pwd)
            db.session.add(student)
            click.echo(f"  [OK] Created Student: {email} (Roll: {roll}, Password: {pwd})")
        created_students.append(student)

    db.session.flush()

    # 4. Create Academic Categories
    categories_dict = {
        'Computer Science & Engineering': 'Core computing, systems, networks, operating systems, and software engineering.',
        'Artificial Intelligence & ML': 'Machine learning algorithms, deep learning, NLP, and intelligent agents.',
        'Data Structures & Algorithms': 'Algorithm design, analysis, computational complexity, and fundamental structures.',
        'Electronics & Communication': 'Signal processing, microprocessors, embedded systems, and VLSI design.',
        'Mechanical Engineering': 'Thermodynamics, fluid mechanics, machine design, and robotics.',
        'Management & Humanities': 'Engineering economics, professional ethics, and organizational behavior.'
    }
    cat_objs = {}
    for cat_name, desc in categories_dict.items():
        cat = Category.query.filter_by(name=cat_name).first()
        if not cat:
            cat = Category(name=cat_name, description=desc)
            db.session.add(cat)
            click.echo(f"  [OK] Created Category: {cat_name}")
        cat_objs[cat_name] = cat

    db.session.flush()

    # 5. Create Sample Academic Books
    books_data = [
        {
            'isbn': '978-0131103627',
            'title': 'The C Programming Language',
            'author': 'Brian W. Kernighan, Dennis M. Ritchie',
            'publisher': 'Prentice Hall',
            'publication_year': 1988,
            'category': 'Computer Science & Engineering',
            'shelf': 'CS-Rack-01',
            'total': 5,
            'available': 4,
            'desc': 'The definitive reference guide to ANSI standard C programming written by the creators of C.'
        },
        {
            'isbn': '978-0262033848',
            'title': 'Introduction to Algorithms (CLRS)',
            'author': 'Thomas H. Cormen, Charles E. Leiserson, Ronald L. Rivest, Clifford Stein',
            'publisher': 'MIT Press',
            'publication_year': 2009,
            'category': 'Data Structures & Algorithms',
            'shelf': 'DSA-Rack-02',
            'total': 6,
            'available': 4,
            'desc': 'Comprehensive textbook covering modern algorithms, dynamic programming, and computational geometry.'
        },
        {
            'isbn': '978-0134685991',
            'title': 'Effective Java (3rd Edition)',
            'author': 'Joshua Bloch',
            'publisher': 'Addison-Wesley',
            'publication_year': 2018,
            'category': 'Computer Science & Engineering',
            'shelf': 'CS-Rack-03',
            'total': 4,
            'available': 3,
            'desc': 'Best practices and design patterns for robust, clean, and idiomatic Java software engineering.'
        },
        {
            'isbn': '978-0136042594',
            'title': 'Artificial Intelligence: A Modern Approach',
            'author': 'Stuart Russell, Peter Norvig',
            'publisher': 'Pearson',
            'publication_year': 2020,
            'category': 'Artificial Intelligence & ML',
            'shelf': 'AI-Rack-01',
            'total': 5,
            'available': 4,
            'desc': 'The leading global textbook on artificial intelligence, search algorithms, logic, and probabilistic reasoning.'
        },
        {
            'isbn': '978-0262035613',
            'title': 'Deep Learning',
            'author': 'Ian Goodfellow, Yoshua Bengio, Aaron Courville',
            'publisher': 'MIT Press',
            'publication_year': 2016,
            'category': 'Artificial Intelligence & ML',
            'shelf': 'AI-Rack-02',
            'total': 3,
            'available': 2,
            'desc': 'An introduction to a broad range of topics in deep learning covering mathematical foundations and modern architectures.'
        },
        {
            'isbn': '978-0132143011',
            'title': 'Operating System Concepts',
            'author': 'Abraham Silberschatz, Peter B. Galvin, Greg Gagne',
            'publisher': 'Wiley',
            'publication_year': 2018,
            'category': 'Computer Science & Engineering',
            'shelf': 'CS-Rack-04',
            'total': 4,
            'available': 3,
            'desc': 'Fundamental principles of processes, threads, memory management, file systems, and distributed OS.'
        },
        {
            'isbn': '978-0133594140',
            'title': 'Computer Networks (5th Edition)',
            'author': 'Andrew S. Tanenbaum, David J. Wetherall',
            'publisher': 'Pearson',
            'publication_year': 2011,
            'category': 'Computer Science & Engineering',
            'shelf': 'CS-Rack-05',
            'total': 4,
            'available': 4,
            'desc': 'Classic treatment of protocol layers from physical medium to high-level application protocols.'
        },
        {
            'isbn': '978-0198083863',
            'title': 'Microelectronic Circuits',
            'author': 'Adel S. Sedra, Kenneth C. Smith',
            'publisher': 'Oxford University Press',
            'publication_year': 2014,
            'category': 'Electronics & Communication',
            'shelf': 'EC-Rack-01',
            'total': 3,
            'available': 3,
            'desc': 'Standard textbook for semiconductor device physics, MOSFETs, BJTs, and analog integrated circuit design.'
        },
        {
            'isbn': '978-0073398204',
            'title': 'Shigley\'s Mechanical Engineering Design',
            'author': 'Richard G. Budynas, Keith J. Nisbett',
            'publisher': 'McGraw-Hill',
            'publication_year': 2014,
            'category': 'Mechanical Engineering',
            'shelf': 'ME-Rack-01',
            'total': 3,
            'available': 3,
            'desc': 'The standard in machine design education covering stress analysis, failure prevention, and power screws.'
        },
        {
            'isbn': '978-0132350884',
            'title': 'Clean Code: A Handbook of Agile Software Craftsmanship',
            'author': 'Robert C. Martin',
            'publisher': 'Prentice Hall',
            'publication_year': 2008,
            'category': 'Computer Science & Engineering',
            'shelf': 'CS-Rack-02',
            'total': 4,
            'available': 3,
            'desc': 'Principles and practices of writing clear, readable, and maintainable software.'
        }
    ]

    created_books = []
    for b_info in books_data:
        book = Book.query.filter_by(isbn=b_info['isbn']).first()
        if not book:
            book = Book(
                isbn=b_info['isbn'],
                title=b_info['title'],
                author=b_info['author'],
                publisher=b_info['publisher'],
                publication_year=b_info['publication_year'],
                category_id=cat_objs[b_info['category']].id,
                shelf_location=b_info['shelf'],
                total_copies=b_info['total'],
                available_copies=b_info['available'],
                description=b_info['desc'],
                is_active=True
            )
            db.session.add(book)
            db.session.flush()
            # Generate QR code immediately
            QRService.generate_qr_for_book(book)
            click.echo(f"  [OK] Created Book: {book.title} (QR generated)")
        created_books.append(book)

    db.session.commit()

    # 6. Set up Student Reading Preferences
    # Aarav prefers CS and AI
    student_1 = created_students[0]
    for cat_name in ['Computer Science & Engineering', 'Artificial Intelligence & ML']:
        cat = cat_objs[cat_name]
        if not StudentPreference.query.filter_by(student_id=student_1.id, category_id=cat.id).first():
            db.session.add(StudentPreference(student_id=student_1.id, category_id=cat.id))

    # Priya prefers Data Structures & Algorithms
    student_2 = created_students[1]
    dsa_cat = cat_objs['Data Structures & Algorithms']
    if not StudentPreference.query.filter_by(student_id=student_2.id, category_id=dsa_cat.id).first():
        db.session.add(StudentPreference(student_id=student_2.id, category_id=dsa_cat.id))

    db.session.commit()

    # 7. Seed Demonstration Loans & Overdues (for evaluator viva demonstration)
    # Active Loan 1: Issued 4 days ago, due in 10 days (Active, on time)
    if not BookLoan.query.filter_by(student_id=student_1.id, book_id=created_books[0].id).first():
        loan1 = BookLoan(
            student_id=student_1.id,
            book_id=created_books[0].id,
            issued_by=librarian.id,
            issue_date=date.today() - timedelta(days=4),
            due_date=date.today() + timedelta(days=10),
            status=BookLoan.STATUS_ACTIVE,
            fine_rate_snapshot=2.00
        )
        db.session.add(loan1)
        db.session.flush()
        fine1 = Fine(loan_id=loan1.id, calculated_amount=0.00, amount_paid=0.00, payment_status=Fine.STATUS_NO_FINE)
        db.session.add(fine1)

    # Active Loan 2: Issued 20 days ago, due 6 days ago (OVERDUE to demonstrate smart alerts & fines!)
    if not BookLoan.query.filter_by(student_id=student_1.id, book_id=created_books[1].id).first():
        loan2 = BookLoan(
            student_id=student_1.id,
            book_id=created_books[1].id,
            issued_by=librarian.id,
            issue_date=date.today() - timedelta(days=20),
            due_date=date.today() - timedelta(days=6),  # 6 days overdue
            status=BookLoan.STATUS_ACTIVE,
            fine_rate_snapshot=2.00
        )
        db.session.add(loan2)
        db.session.flush()
        # 6 days overdue * Rs 2 = Rs 12 fine
        fine2 = Fine(
            loan_id=loan2.id,
            calculated_amount=12.00,
            amount_paid=0.00,
            payment_status=Fine.STATUS_PENDING
        )
        db.session.add(fine2)
        click.echo("  [OK] Created Demonstration Overdue Loan (Student 1 has 6 days overdue)")

    # Historical Loan: Returned 2 days ago, was on time
    if not BookLoan.query.filter_by(student_id=student_2.id, book_id=created_books[2].id).first():
        loan3 = BookLoan(
            student_id=student_2.id,
            book_id=created_books[2].id,
            issued_by=librarian.id,
            issue_date=date.today() - timedelta(days=16),
            due_date=date.today() - timedelta(days=2),
            return_date=date.today() - timedelta(days=2),
            status=BookLoan.STATUS_RETURNED,
            fine_rate_snapshot=2.00
        )
        db.session.add(loan3)
        db.session.flush()
        fine3 = Fine(loan_id=loan3.id, calculated_amount=0.00, amount_paid=0.00, payment_status=Fine.STATUS_NO_FINE)
        db.session.add(fine3)

    # Sample Pending Request: Student 3 requested Russell & Norvig AI book
    if not BookRequest.query.filter_by(student_id=created_students[2].id, book_id=created_books[3].id).first():
        req = BookRequest(
            student_id=created_students[2].id,
            book_id=created_books[3].id,
            status=BookRequest.STATUS_PENDING,
            requested_at=datetime.utcnow() - timedelta(hours=3)
        )
        db.session.add(req)
        click.echo("  [OK] Created Demonstration Pending Borrow Request (Student 3)")

    db.session.commit()
    click.echo("[OK] Sample database seeded successfully with realistic academic data!")


def register_cli_commands(app):
    """Register all custom CLI commands with Flask application."""
    app.cli.add_command(init_db_command)
    app.cli.add_command(create_admin_command)
    app.cli.add_command(seed_data_command)
