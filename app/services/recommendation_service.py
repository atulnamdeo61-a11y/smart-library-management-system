from collections import Counter
from sqlalchemy import func
from app.extensions import db
from app.models.book import Book
from app.models.book_loan import BookLoan
from app.models.category import Category
from app.models.student_preference import StudentPreference


class RecommendationService:
    @classmethod
    def get_recommendations_for_student(cls, student_id, limit=6):
        """
        Produce explainable book recommendations for a student.
        Returns a list of dicts: {'book': Book, 'reason': str, 'score': float}
        """
        # 1. Fetch student's explicit category preferences
        prefs = StudentPreference.query.filter_by(student_id=student_id).all()
        pref_category_ids = {p.category_id for p in prefs}

        # 2. Fetch student's borrowing history categories
        history_loans = BookLoan.query.filter_by(student_id=student_id).all()
        borrowed_book_ids = {loan.book_id for loan in history_loans}
        
        history_cat_counter = Counter()
        for loan in history_loans:
            if loan.book and loan.book.category_id:
                history_cat_counter[loan.book.category_id] += 1

        # 3. Currently active loans to strictly exclude from recommendations
        active_loans = BookLoan.query.filter_by(
            student_id=student_id,
            status=BookLoan.STATUS_ACTIVE
        ).all()
        active_book_ids = {l.book_id for l in active_loans}

        # 4. Get popular books popularity map (loan counts across all users)
        pop_query = db.session.query(
            BookLoan.book_id,
            func.count(BookLoan.id).label('loan_count')
        ).group_by(BookLoan.book_id).all()
        popularity_map = {b_id: count for b_id, count in pop_query}

        # Categories map for reasons
        categories_map = {c.id: c.name for c in Category.query.all()}

        # 5. Query candidate available active books
        candidate_books = Book.query.filter(
            Book.is_active == True,
            Book.available_copies > 0,
            ~Book.id.in_(active_book_ids) if active_book_ids else True
        ).all()

        scored_results = []
        has_personalized_signals = bool(pref_category_ids or history_cat_counter)

        for book in candidate_books:
            score = 0.0
            reasons = []

            # Preference match
            if book.category_id in pref_category_ids:
                score += 5.0
                cat_name = categories_map.get(book.category_id, "your favorite topics")
                reasons.append(f"Matches your chosen interest in {cat_name}")

            # Borrowing history category match
            hist_count = history_cat_counter.get(book.category_id, 0)
            if hist_count > 0:
                score += hist_count * 2.5
                cat_name = categories_map.get(book.category_id, "this topic")
                if not reasons:
                    reasons.append(f"Because you frequently read books in {cat_name}")

            # Deprioritize books already read before (to introduce variety)
            if book.id in borrowed_book_ids:
                score -= 3.0

            # General popularity boost
            pop_score = popularity_map.get(book.id, 0)
            score += min(pop_score * 0.5, 3.0)

            if not reasons:
                if pop_score > 0:
                    reasons.append(f"Popular choice in library ({pop_score} borrows)")
                else:
                    reasons.append("Featured reading in the college library")

            scored_results.append({
                'book': book,
                'score': score,
                'reason': reasons[0]
            })

        # Sort descending by score, then book title
        scored_results.sort(key=lambda x: (x['score'], x['book'].title), reverse=True)

        return scored_results[:limit]
