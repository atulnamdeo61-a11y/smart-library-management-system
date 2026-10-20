import pytest
from app.extensions import db
from app.models.student_preference import StudentPreference
from app.services.recommendation_service import RecommendationService


def login_user(client, email, password):
    """Helper to log in a user."""
    client.post('/auth/logout', follow_redirects=True)
    return client.post('/auth/login', data={
        'email': email,
        'password': password
    }, follow_redirects=True)


def test_recommendations_fallback_for_new_student(app, seed_test_data):
    """Students without prior history or preferences receive popular/available books as fallback."""
    with app.app_context():
        student = seed_test_data['student2']
        recs = RecommendationService.get_recommendations_for_student(student.id, limit=5)
        assert len(recs) > 0
        titles = [r['book'].title for r in recs]
        assert 'Python Programming Mastery' in titles
        # Each recommendation must provide a transparent reason and fit level
        assert all('reason' in r and len(r['reason']) > 0 for r in recs)
        assert all('fit_level' in r for r in recs)


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
        top_rec = recs[0]
        assert top_rec['book'].title == 'Discrete Mathematics'
        assert len(top_rec['reason']) > 0


def test_course_specific_recommendations_mca_bca_btech(app, seed_test_data):
    """Recommendations tailor book suggestions according to degree program (MCA, BCA, B.Tech)."""
    with app.app_context():
        student = seed_test_data['student1']

        # MCA
        mca_recs = RecommendationService.get_recommendations_for_student(student.id, course='MCA', limit=4)
        assert len(mca_recs) > 0
        assert all('book' in r and 'reason' in r and 'fit_level' in r for r in mca_recs)

        # BCA
        bca_recs = RecommendationService.get_recommendations_for_student(student.id, course='BCA', limit=4)
        assert len(bca_recs) > 0
        assert all('book' in r and 'reason' in r and 'fit_level' in r for r in bca_recs)

        # B.Tech
        btech_recs = RecommendationService.get_recommendations_for_student(student.id, course='B.Tech Computer Science', limit=4)
        assert len(btech_recs) > 0
        assert all('book' in r and 'reason' in r and 'fit_level' in r for r in btech_recs)


def test_student_recommendations_web_route(client, seed_test_data):
    """Test web endpoint /student/recommendations supports dynamic course switching."""
    student = seed_test_data['student1']
    login_user(client, student.email, 'StudentPass123')

    # View default recommendations
    res = client.get('/student/recommendations')
    assert res.status_code == 200
    assert b'Course-Tailored Academic Recommendations' in res.data
    assert b'Powered by Google Gemini AI' in res.data

    # Switch to MCA
    res_mca = client.get('/student/recommendations?course=MCA')
    assert res_mca.status_code == 200
    assert b'Recommended for MCA' in res_mca.data

    # Switch to BCA
    res_bca = client.get('/student/recommendations?course=BCA')
    assert res_bca.status_code == 200
    assert b'Recommended for BCA' in res_bca.data

    # Switch to B.Tech
    res_btech = client.get('/student/recommendations?course=B.Tech Computer Science')
    assert res_btech.status_code == 200
    assert b'Recommended for B.Tech Computer Science' in res_btech.data


def test_student_update_course_in_preferences(client, seed_test_data):
    """Test student can choose and update their current degree course in preferences."""
    student = seed_test_data['student1']
    cat_math = seed_test_data['cat_math']
    login_user(client, student.email, 'StudentPass123')

    # Post course update
    post_res = client.post('/student/preferences', data={
        'course': 'MCA',
        'category_ids': [cat_math.id]
    }, follow_redirects=True)

    assert post_res.status_code == 200
    assert b'Your course (MCA) and reading interests were saved successfully!' in post_res.data

    # Verify user record updated
    db.session.refresh(student)
    assert student.course == 'MCA'
    assert student.effective_course == 'MCA'
