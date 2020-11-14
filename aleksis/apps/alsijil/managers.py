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
