import pytest
from app.extensions import db
from app.models.student_preference import StudentPreference
from app.services.recommendation_service import RecommendationService


def test_recommendations_fallback_for_new_student(app, seed_test_data):
    """Students without prior history or preferences receive popular/available books as fallback."""
    with app.app_context():
        student = seed_test_data['student2']
        recs = RecommendationService.get_recommendations_for_student(student.id, limit=5)
        assert len(recs) > 0
        titles = [r['book'].title for r in recs]
        assert 'Python Programming Mastery' in titles
        # Each recommendation must provide a transparent reason
        assert all('reason' in r for r in recs)


def test_recommendations_influenced_by_category_preference(app, seed_test_data):
    """Setting student preferences boosts books in that category to the top."""
    with app.app_context():
        student = seed_test_data['student1']
        cat_math = seed_test_data['cat_math']

        # Student sets preference for Mathematics
        pref = StudentPreference(student_id=student.id, category_id=cat_math.id)
        db.session.add(pref)
        db.session.commit()

        recs = RecommendationService.get_recommendations_for_student(student.id, limit=5)
        assert len(recs) > 0
        # Discrete Mathematics should now be ranked top with preference reason
        top_rec = recs[0]
        assert top_rec['book'].title == 'Discrete Mathematics'
        assert 'interest in Mathematics' in top_rec['reason']
