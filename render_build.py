# Copyright (c) 2026 Atul Namdeo (GitHub: @atulnamdeo61-a11y). All Rights Reserved.
# Proprietary and Personal Academic Project. Strictly NOT Open-Source Software.

import os
import sys
from app import create_app
from app.extensions import db
from app.models.category import Category
from app.models.book import Book

print("=== Render Build: Initializing Application Database ===")
app = create_app(os.getenv('FLASK_CONFIG', 'default'))

with app.app_context():
    # 1. Create all database tables (PostgreSQL or SQLite)
    db.create_all()
    print("[OK] Database tables created / verified successfully.")

    # 2. Check if the database has seed data (e.g. fresh Render deployment)
    cat_count = Category.query.count()
    book_count = Book.query.count()
    print(f"[INFO] Current catalog status: {cat_count} categories, {book_count} books.")

    if cat_count == 0 or book_count == 0:
        print("[INFO] Empty database detected. Seeding academic catalog...")
        try:
            from click.testing import CliRunner
            from app.cli import seed_data_command
            runner = CliRunner()
            result = runner.invoke(seed_data_command, obj={})
            print(result.output)
            print("[OK] Seed process completed successfully.")
        except Exception as err:
            print(f"[WARN] Automatic seed warning: {err}")
    else:
        print("[INFO] Existing catalog preserved.")

print("=== Render Build Completed Successfully ===")
