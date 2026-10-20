# Copyright (c) 2026 Atul Namdeo (GitHub: @atulnamdeo61-a11y). All Rights Reserved.
# Proprietary and Personal Academic Project. Strictly NOT Open-Source Software.

from app.services.gemini_service import GeminiService


class RecommendationService:
    """Service facade providing personalized and course-aware book recommendations."""

    @classmethod
    def get_recommendations_for_student(cls, student_id: int, limit: int = 6, course: str = None):
        """
        Produce explainable, course-tailored book recommendations for a student.
        Integrates Google Gemini AI with failover to local curriculum rules.
        Returns a list of dicts: {'book': Book, 'reason': str, 'score': float, 'fit_level': str, 'ai_powered': bool, 'engine': str}
        """
        return GeminiService.recommend_books_for_student(
            student_id=student_id,
            course=course,
            limit=limit
        )

    @classmethod
    def is_ai_enabled(cls) -> bool:
        """Check if Google Gemini AI is actively configured."""
        return GeminiService.is_configured()

    @classmethod
    def get_active_model(cls) -> str:
        """Return currently configured Gemini model name."""
        return GeminiService.get_configured_model()
