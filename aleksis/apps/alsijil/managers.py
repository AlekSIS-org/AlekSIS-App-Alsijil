from django.db.models import QuerySet
from django.db.models.query_utils import Q

from aleksis.core.managers import CurrentSiteManagerWithoutMigrations


class PersonalNoteManager(CurrentSiteManagerWithoutMigrations):
    """Manager adding specific methods to personal notes."""

    def get_queryset(self):
        """Ensure all related lesson and person data are loaded as well."""
        return (
            super()
            .get_queryset()
            .select_related(
                "person",
                "excuse_type",
                "lesson_period",
                "lesson_period__lesson",
                "lesson_period__lesson__subject",
                "lesson_period__period",
                "lesson_period__lesson__validity",
                "lesson_period__lesson__validity__school_term",
            )
            .prefetch_related("extra_marks")
        )


class PersonalNoteQuerySet(QuerySet):
    def not_empty(self):
        """Get all not empty personal notes."""
        return self.filter(
            ~Q(remarks="") | Q(absent=True) | ~Q(late=0) | Q(extra_marks__isnull=False)
        )


class LessonDocumentationManager(CurrentSiteManagerWithoutMigrations):
    pass


class LessonDocumentationQuerySet(QuerySet):
    def not_empty(self):
        """Get all not empty lesson documentations."""
        return self.filter(~Q(topic="") | ~Q(group_note="") | ~Q(homework=""))
