# Copyright (c) 2026 Atul Namdeo (GitHub: @atulnamdeo61-a11y). All Rights Reserved.
# Proprietary and Personal Academic Project. Strictly NOT Open-Source Software.

import os
import json
import logging
import requests
from flask import current_app
from collections import Counter
from sqlalchemy import func
from app.extensions import db
from app.models.book import Book
from app.models.book_loan import BookLoan
from app.models.category import Category
from app.models.user import User
from app.models.student_preference import StudentPreference

logger = logging.getLogger(__name__)


class GeminiService:
    """Google Gemini AI Service for academic book recommendations tailored to student degree courses and topics."""

    # Models supported on Gemini Pro & Gemini Developer API
    SUPPORTED_MODELS = [
        ('gemini-3.5-flash-lite', 'Gemini 3.5 Flash Lite (Ultra-fast & Highly Responsive)'),
        ('gemini-3.5-flash', 'Gemini 3.5 Flash (Advanced Reasoning)'),
        ('gemini-3.6-flash', 'Gemini 3.6 Flash (Latest High-Throughput Flash)'),
        ('gemini-pro-latest', 'Gemini Pro Latest (Gemini Pro Flagship Model)'),
        ('gemini-3.1-pro-preview', 'Gemini 3.1 Pro Preview (Deep Curriculum & Syllabus Analysis)'),
        ('gemini-flash-latest', 'Gemini Flash Latest'),
        ('gemini-flash-lite-latest', 'Gemini Flash Lite Latest'),
        ('gemini-3.7-flash', 'Gemini 3.7 Flash'),
        ('gemini-3.8-flash', 'Gemini 3.8 Flash'),
        ('gemini-3-flash-preview', 'Gemini 3 Flash Preview'),
        ('gemini-2.5-flash-lite', 'Gemini 2.5 Flash Lite'),
    ]

    CASCADE_MODELS = [
        'gemini-3.5-flash-lite',
        'gemini-3.5-flash',
        'gemini-3.6-flash',
        'gemini-pro-latest',
        'gemini-3.1-pro-preview',
        'gemini-flash-latest',
        'gemini-flash-lite-latest',
        'gemini-3.7-flash',
        'gemini-3.8-flash',
        'gemini-3-flash-preview',
        'gemini-2.5-flash-lite'
    ]

    # Academic curriculum course keywords and syllabus mappings
    CURRICULUM_MAPPINGS = {
        'MCA': {
            'keywords': ['algorithms', 'data structures', 'java', 'operating system', 'networks', 'software', 'database', 'ai', 'artificial intelligence', 'cloud', 'architecture'],
            'focus': 'Master of Computer Applications (Advanced Computing, System Architecture, Enterprise Software & AI)',
            'core_title': 'MCA Core Syllabus'
        },
        'BCA': {
            'keywords': ['c programming', 'programming', 'database', 'web', 'data structures', 'networks', 'operating system', 'java', 'python'],
            'focus': 'Bachelor of Computer Applications (Core Programming, Relational Databases, Web & Networking Fundamentals)',
            'core_title': 'BCA Foundation Syllabus'
        },
        'B.Tech': {
            'keywords': ['algorithms', 'operating system', 'microelectronic', 'circuits', 'networks', 'mechanical', 'design', 'engineering', 'machine learning', 'data structures'],
            'focus': 'Bachelor of Technology (Engineering Foundations, Hardware-Software Systems, Applied Mathematics & Systems Design)',
            'core_title': 'B.Tech Engineering Core'
        },
        'M.Tech': {
            'keywords': ['deep learning', 'artificial intelligence', 'advanced algorithms', 'distributed systems', 'microelectronic', 'research', 'neural'],
            'focus': 'Master of Technology (Advanced Research, Deep Learning, Complex Systems & Design Optimization)',
            'core_title': 'M.Tech Postgraduate Core'
        },
        'MBA': {
            'keywords': ['management', 'leadership', 'analytics', 'strategy', 'finance', 'marketing', 'humanities'],
            'focus': 'Master of Business Administration (Strategic Management, Information Systems & Organizational Leadership)',
            'core_title': 'MBA Management Core'
        },
        'B.Sc': {
            'keywords': ['programming', 'computer science', 'c programming', 'algorithms', 'mathematics', 'statistics'],
            'focus': 'Bachelor of Science (Computer Science / IT Fundamentals and Applied Theory)',
            'core_title': 'B.Sc Academic Foundation'
        }
    }

    @classmethod
    def get_api_key(cls) -> str:
        """Fetch configured Gemini API Key from Flask config or environment."""
        try:
            key = current_app.config.get('GEMINI_API_KEY')
            if key and key.strip():
                return key.strip()
        except RuntimeError:
            pass
        return os.getenv('GEMINI_API_KEY', '').strip()

    @classmethod
    def is_configured(cls) -> bool:
        """Check if Gemini API key is configured."""
        return bool(cls.get_api_key())

    @classmethod
    def get_configured_model(cls) -> str:
        """Fetch preferred model name from config."""
        try:
            model = current_app.config.get('GEMINI_MODEL')
            if model and model.strip():
                return model.strip()
        except RuntimeError:
            pass
        return os.getenv('GEMINI_MODEL', 'gemini-3.5-flash-lite').strip()

    @classmethod
    def recommend_books_for_student(cls, student_id: int, course: str = None, limit: int = 6):
        """
        Produce course-aligned and preference-tuned book recommendations for a student.
        Uses Google Gemini AI if configured with automatic model cascade, falling back to
        the local curriculum recommendation engine if offline or rate-limited.
        """
        student = db.session.get(User, student_id)
        if not student:
            return []

        # Determine effective course (MCA, BCA, B.Tech, etc.)
        effective_course = (course or student.effective_course or 'MCA').strip()

        # 1. Fetch student explicit category preferences
        prefs = StudentPreference.query.filter_by(student_id=student_id).all()
        pref_categories = [p.category.name for p in prefs if p.category]
        pref_category_ids = {p.category_id for p in prefs}

        # 2. Fetch borrowing history
        history_loans = BookLoan.query.filter_by(student_id=student_id).all()
        borrowed_book_ids = {l.book_id for l in history_loans}
        borrowed_titles = [l.book.title for l in history_loans if l.book][:5]

        # 3. Active loans to exclude
        active_loans = BookLoan.query.filter_by(student_id=student_id, status=BookLoan.STATUS_ACTIVE).all()
        active_book_ids = {l.book_id for l in active_loans}

        # 4. Fetch available candidate books from catalog
        candidate_books = Book.query.filter(
            Book.is_active == True,
            Book.available_copies > 0,
            ~Book.id.in_(active_book_ids) if active_book_ids else True
        ).all()

        if not candidate_books:
            return []

        # Try Google Gemini AI first if configured
        api_key = cls.get_api_key()
        if api_key:
            ai_recommendations = cls._call_gemini_api(
                api_key=api_key,
                student=student,
                course=effective_course,
                pref_categories=pref_categories,
                borrowed_titles=borrowed_titles,
                candidate_books=candidate_books,
                limit=limit
            )
            if ai_recommendations:
                return ai_recommendations

        # Fallback to Curriculum-Aware Local Algorithmic Engine
        return cls._curriculum_algorithmic_fallback(
            student=student,
            course=effective_course,
            pref_category_ids=pref_category_ids,
            borrowed_book_ids=borrowed_book_ids,
            candidate_books=candidate_books,
            limit=limit
        )

    @classmethod
    def _call_gemini_api(cls, api_key: str, student, course: str, pref_categories: list,
                          borrowed_titles: list, candidate_books: list, limit: int):
        """Call Google Gemini Generative Language API with failover model cascade."""
        catalog_summary = []
        books_by_id = {}
        for b in candidate_books:
            books_by_id[b.id] = b
            catalog_summary.append({
                'id': b.id,
                'title': b.title,
                'author': b.author,
                'category': b.category.name if b.category else 'General',
                'description': (b.description or '')[:120],
                'shelf': b.shelf_location or 'Main Stack',
                'copies_available': b.available_copies
            })

        course_info = cls._get_course_metadata(course)
        prompt = (
            f"You are the Chief Academic Advisory Librarian for an accredited university.\n"
            f"Your job is to recommend academic books for a student based on their current degree program and interests.\n\n"
            f"STUDENT PROFILE:\n"
            f"- Name: {student.full_name}\n"
            f"- Degree / Course of Study: {course} ({course_info['focus']})\n"
            f"- Chosen Topic Interests: {', '.join(pref_categories) if pref_categories else 'General Computer Science & Engineering'}\n"
            f"- Previously Borrowed Books: {', '.join(borrowed_titles) if borrowed_titles else 'None yet (new semester)'}\n\n"
            f"AVAILABLE LIBRARY CATALOG:\n"
            f"{json.dumps(catalog_summary, indent=2)}\n\n"
            f"INSTRUCTIONS:\n"
            f"Select up to {limit} books from the AVAILABLE CATALOG that are most essential and relevant for a student pursuing {course}.\n"
            f"Prioritize syllabus alignment, core degree requirements, and practical skill development.\n"
            f"Respond ONLY with a valid JSON array of objects. Do not wrap in markdown or prose. Each object MUST have:\n"
            f"[\n"
            f"  {{\n"
            f"    \"book_id\": <integer matching catalog id>,\n"
            f"    \"curriculum_fit\": \"<concise label, e.g. '{course} Core Syllabus', '{course} Recommended Elective', 'Industry Foundation'>\",\n"
            f"    \"reason\": \"<1-2 sentences personalized explanation of why this book is critical for a {course} student>\",\n"
            f"    \"score\": <number from 8.0 to 10.0>\n"
            f"  }}\n"
            f"]"
        )

        # Primary model and cascade models
        primary_model = cls.get_configured_model()
        models_to_try = [primary_model] + [m for m in cls.CASCADE_MODELS if m != primary_model]

        for model in models_to_try:
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            payload = {
                'contents': [{'parts': [{'text': prompt}]}],
                'generationConfig': {
                    'temperature': 0.2,
                    'responseMimeType': 'application/json'
                }
            }

            try:
                resp = requests.post(endpoint, json=payload, timeout=7)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get('candidates', [])
                    if candidates and 'content' in candidates[0]:
                        raw_text = candidates[0]['content']['parts'][0]['text'].strip()
                        # Clean potential code blocks if any
                        if raw_text.startswith('```'):
                            lines = raw_text.split('\n')
                            if lines[0].startswith('```'):
                                lines = lines[1:]
                            if lines and lines[-1].startswith('```'):
                                lines = lines[:-1]
                            raw_text = '\n'.join(lines).strip()

                        parsed = json.loads(raw_text)
                        if isinstance(parsed, list) and len(parsed) > 0:
                            results = []
                            seen_ids = set()
                            for item in parsed:
                                b_id = item.get('book_id')
                                if b_id in books_by_id and b_id not in seen_ids:
                                    seen_ids.add(b_id)
                                    results.append({
                                        'book': books_by_id[b_id],
                                        'reason': item.get('reason', f"Curriculum recommended title for {course} students."),
                                        'fit_level': item.get('curriculum_fit', f"{course} Core Syllabus"),
                                        'score': float(item.get('score', 9.5)),
                                        'ai_powered': True,
                                        'engine': f'Google Gemini AI ({model})'
                                    })
                            if results:
                                return results[:limit]

                elif resp.status_code in (404, 429, 503):
                    logger.warning(f"Gemini model {model} returned HTTP {resp.status_code}, trying next model.")
                    continue
                else:
                    logger.warning(f"Gemini API returned status {resp.status_code}: {resp.text[:200]}")
            except Exception as e:
                logger.warning(f"Error calling Gemini model {model}: {e}")
                continue

        return None

    @classmethod
    def _curriculum_algorithmic_fallback(cls, student, course: str, pref_category_ids: set,
                                         borrowed_book_ids: set, candidate_books: list, limit: int):
        """Intelligent local curriculum-aware recommendation engine when offline or Gemini is unconfigured."""
        course_meta = cls._get_course_metadata(course)
        course_keywords = course_meta['keywords']
        core_title = course_meta['core_title']

        # Popularity map across library
        pop_query = db.session.query(
            BookLoan.book_id,
            func.count(BookLoan.id).label('loan_count')
        ).group_by(BookLoan.book_id).all()
        popularity_map = {b_id: count for b_id, count in pop_query}

        scored = []
        for book in candidate_books:
            score = 5.0
            reasons = []
            fit_level = f"{course} Recommended"

            b_title_lower = book.title.lower()
            b_desc_lower = (book.description or '').lower()
            b_cat_lower = (book.category.name if book.category else '').lower()
            combined_text = f"{b_title_lower} {b_desc_lower} {b_cat_lower}"

            # 1. Course keyword match boost
            kw_hits = [kw for kw in course_keywords if kw in combined_text]
            if kw_hits:
                score += len(kw_hits) * 3.0
                fit_level = core_title
                matched_topic = kw_hits[0].title()
                reasons.append(f"Curriculum alignment for {course}: Key textbook covering {matched_topic} syllabus.")

            # 2. Preference match boost
            if book.category_id in pref_category_ids:
                score += 4.5
                cat_name = book.category.name if book.category else 'your preferred topics'
                if not reasons:
                    reasons.append(f"Matches your chosen academic interest in {cat_name}.")

            # 3. Variety penalty for already borrowed books
            if book.id in borrowed_book_ids:
                score -= 3.0

            # 4. Popularity bonus
            pop = popularity_map.get(book.id, 0)
            score += min(pop * 0.4, 2.0)

            if not reasons:
                if pop > 0:
                    reasons.append(f"Frequently borrowed reference for {course} coursework ({pop} loans).")
                else:
                    reasons.append(f"Recommended reference volume for {course} students.")

            scored.append({
                'book': book,
                'reason': reasons[0],
                'fit_level': fit_level,
                'score': score,
                'ai_powered': False,
                'engine': 'Curriculum Academic Engine'
            })

        # Sort descending by score, then book title
        scored.sort(key=lambda x: (x['score'], x['book'].title), reverse=True)
        return scored[:limit]

    @classmethod
    def _get_course_metadata(cls, course_name: str) -> dict:
        """Resolve keywords and curriculum focus for given course string."""
        if not course_name:
            return cls.CURRICULUM_MAPPINGS['MCA']

        clean = course_name.upper()
        for key, meta in cls.CURRICULUM_MAPPINGS.items():
            if key.upper() in clean:
                return meta

        # Generic default
        return {
            'keywords': ['programming', 'computer', 'algorithms', 'engineering', 'science', 'systems'],
            'focus': f'{course_name} Academic Syllabus and Professional Technical Training',
            'core_title': f'{course_name} Core Syllabus'
        }
