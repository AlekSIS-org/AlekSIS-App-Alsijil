from datetime import date, datetime
from typing import Optional, Sequence, Union

from django.db.models import Case, ExpressionWrapper, F, Func, QuerySet, Value, When
from django.db.models.fields import DateField
from django.db.models.functions import Concat
from django.db.models.query import Prefetch
from django.db.models.query_utils import Q
from django.utils.translation import gettext as _

from calendarweek import CalendarWeek

from aleksis.apps.chronos.managers import DateRangeQuerySetMixin
from aleksis.core.managers import CurrentSiteManagerWithoutMigrations


class RegisterObjectRelatedQuerySet(QuerySet):
    """Common queryset for personal notes and lesson documentations with shared API."""

    def _get_weekday_to_date(self, weekday_name, year_name="year", week_name="week"):
        """Get a ORM function which converts a weekday, a week and a year to a date."""
        return ExpressionWrapper(
            Func(
                Concat(F(year_name), F(week_name)),
                Value("IYYYIW"),
                output_field=DateField(),
                function="TO_DATE",
            )
            + F(weekday_name),
            output_field=DateField(),
        )

    def annotate_day(self) -> QuerySet:
        """Annotate every personal note/lesson documentation with the real date.

        Attribute name: ``day``

        .. note::
            For events, this will annotate ``None``.
        """
        return self.annotate(
            day=Case(
                When(
                    lesson_period__isnull=False,
                    then=self._get_weekday_to_date("lesson_period__period__weekday"),
                ),
                When(
                    extra_lesson__isnull=False,
                    then=self._get_weekday_to_date(
                        "extra_lesson__period__weekday", "extra_lesson__year", "extra_lesson__week"
                    ),
                ),
            )
        )

    def annotate_date_range(self) -> QuerySet:
        """Annotate every personal note/lesson documentation with the real date.

        Attribute names: ``day_start``, ``day_end``

        .. note::
            For lesson periods and extra lessons,
            this will annotate the same date for start and end day.
        """
        return self.annotate_day().annotate(
            day_start=Case(
                When(day__isnull=False, then="day"),
                When(day__isnull=True, then="event__date_start"),
            ),
            day_end=Case(
                When(day__isnull=False, then="day"), When(day__isnull=True, then="event__date_end"),
            ),
        )

    def annotate_subject(self) -> QuerySet:
        """Annotate lesson documentations with the subjects."""
        return self.annotate(
            subject=Case(
                When(lesson_period__isnull=False, then="lesson_period__lesson__subject__name",),
                When(extra_lesson__isnull=False, then="extra_lesson__subject__name",),
                default=Value(_("Event")),
            )
        )


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
                "event",
                "extra_lesson",
                "extra_lesson__subject",
            )
            .prefetch_related("extra_marks")
        )


class PersonalNoteQuerySet(RegisterObjectRelatedQuerySet, QuerySet):
    def not_empty(self):
        """Get all not empty personal notes."""
        return self.filter(
            ~Q(remarks="") | Q(absent=True) | ~Q(late=0) | Q(extra_marks__isnull=False)
        )


class LessonDocumentationManager(CurrentSiteManagerWithoutMigrations):
    pass


class LessonDocumentationQuerySet(RegisterObjectRelatedQuerySet, QuerySet):
    def not_empty(self):
        """Get all not empty lesson documentations."""
        return self.filter(~Q(topic="") | ~Q(group_note="") | ~Q(homework=""))


class GroupRoleManager(CurrentSiteManagerWithoutMigrations):
    pass


class GroupRoleQuerySet(QuerySet):
    def with_assignments(
        self, time_ref: Union[date, CalendarWeek], groups: Sequence["Group"]
    ) -> QuerySet:
        from aleksis.apps.alsijil.models import GroupRoleAssignment

        if isinstance(time_ref, CalendarWeek):
            qs = GroupRoleAssignment.objects.in_week(time_ref)
        else:
            qs = GroupRoleAssignment.objects.on_day(time_ref)

        qs = qs.for_groups(groups).distinct()
        return self.prefetch_related(Prefetch("assignments", queryset=qs,))


class GroupRoleAssignmentManager(CurrentSiteManagerWithoutMigrations):
    pass


class GroupRoleAssignmentQuerySet(DateRangeQuerySetMixin, QuerySet):
    def within_dates(self, start: date, end: date):
        """Filter for all role assignments within a date range."""
        return self.filter(
            Q(date_start__lte=end) & (Q(date_end__gte=start) | Q(date_end__isnull=True))
        )

    def at_time(self, when: Optional[datetime] = None):
        """Filter for role assignments assigned at a certain point in time."""
        now = when or datetime.now()

        return self.on_day(now.date())

    def for_groups(self, groups: Sequence["Group"]):
        """Filter all role assignments for a sequence of groups."""
        qs = self
        for group in groups:
            qs = qs.for_group(group)
        return qs

    def for_group(self, group: "Group"):
        """Filter all role assignments for a group."""
        return self.filter(Q(groups=group) | Q(groups__child_groups=group))
