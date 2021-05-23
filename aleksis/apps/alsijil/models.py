from datetime import date
from typing import Optional, Union
from urllib.parse import urlparse

from django.db import models
from django.db.models.constraints import CheckConstraint
from django.db.models.query_utils import Q
from django.utils.formats import date_format
from django.utils.translation import gettext_lazy as _

from calendarweek import CalendarWeek
from colorfield.fields import ColorField

from aleksis.apps.alsijil.data_checks import (
    ExcusesWithoutAbsences,
    LessonDocumentationOnHolidaysDataCheck,
    NoGroupsOfPersonsSetInPersonalNotesDataCheck,
    NoPersonalNotesInCancelledLessonsDataCheck,
    PersonalNoteOnHolidaysDataCheck,
)
from aleksis.apps.alsijil.managers import (
    GroupRoleAssignmentManager,
    GroupRoleAssignmentQuerySet,
    GroupRoleManager,
    GroupRoleQuerySet,
    LessonDocumentationManager,
    LessonDocumentationQuerySet,
    PersonalNoteManager,
    PersonalNoteQuerySet,
)
from aleksis.apps.chronos.managers import GroupPropertiesMixin
from aleksis.apps.chronos.mixins import WeekRelatedMixin
from aleksis.apps.chronos.models import Event, ExtraLesson, LessonPeriod, TimePeriod
from aleksis.core.mixins import ExtensibleModel, GlobalPermissionModel
from aleksis.core.models import SchoolTerm
from aleksis.core.util.core_helpers import get_site_preferences
from aleksis.core.util.model_helpers import ICONS


def isidentifier(value: str) -> bool:
    return value.isidentifier()


class ExcuseType(ExtensibleModel):
    """An type of excuse.

    Can be used to count different types of absences separately.
    """

    short_name = models.CharField(max_length=255, unique=True, verbose_name=_("Short name"))
    name = models.CharField(max_length=255, unique=True, verbose_name=_("Name"))

    def __str__(self):
        return f"{self.name} ({self.short_name})"

    @property
    def count_label(self):
        return f"{self.short_name}_count"

    class Meta:
        ordering = ["name"]
        verbose_name = _("Excuse type")
        verbose_name_plural = _("Excuse types")
        constraints = [
            models.UniqueConstraint(
                fields=("site_id", "short_name"), name="unique_excuse_short_name"
            ),
            models.UniqueConstraint(fields=("site_id", "name"), name="unique_excuse_name"),
        ]


lesson_related_constraint_q = (
    Q(
        lesson_period__isnull=False,
        event__isnull=True,
        extra_lesson__isnull=True,
        week__isnull=False,
        year__isnull=False,
    )
    | Q(
        lesson_period__isnull=True,
        event__isnull=False,
        extra_lesson__isnull=True,
        week__isnull=True,
        year__isnull=True,
    )
    | Q(
        lesson_period__isnull=True,
        event__isnull=True,
        extra_lesson__isnull=False,
        week__isnull=True,
        year__isnull=True,
    )
)


class RegisterObjectRelatedMixin(WeekRelatedMixin):
    """Mixin with common API for lesson documentations and personal notes."""

    @property
    def register_object(
        self: Union["LessonDocumentation", "PersonalNote"]
    ) -> Union[LessonPeriod, Event, ExtraLesson]:
        """Get the object related to this lesson documentation or personal note."""
        if self.lesson_period:
            return self.lesson_period
        elif self.event:
            return self.event
        else:
            return self.extra_lesson

    @property
    def calendar_week(self: Union["LessonDocumentation", "PersonalNote"]) -> CalendarWeek:
        """Get the calendar week of this lesson documentation or personal note.

        .. note::

            As events can be longer than one week,
            this will return the week of the start date for events.
        """
        if self.lesson_period:
            return CalendarWeek(week=self.week, year=self.year)
        elif self.extra_lesson:
            return self.extra_lesson.calendar_week
        else:
            return CalendarWeek.from_date(self.register_object.date_start)

    @property
    def school_term(self: Union["LessonDocumentation", "PersonalNote"]) -> SchoolTerm:
        """Get the school term of the related register object."""
        if self.lesson_period:
            return self.lesson_period.lesson.validity.school_term
        else:
            return self.register_object.school_term

    @property
    def date(self: Union["LessonDocumentation", "PersonalNote"]) -> Optional[date]:
        """Get the date of this lesson documentation or personal note.

        :: warning::

            As events can be longer than one day,
            this will return `None` for events.
        """
        if self.lesson_period:
            return super().date
        elif self.extra_lesson:
            return self.extra_lesson.date
        return None

    @property
    def date_formatted(self: Union["LessonDocumentation", "PersonalNote"]) -> str:
        """Get a formatted version of the date of this object.

        Lesson periods, extra lessons: formatted date
        Events: formatted date range
        """
        return (
            date_format(self.date)
            if self.date
            else f"{date_format(self.event.date_start)}–{date_format(self.event.date_end)}"
        )

    @property
    def period(self: Union["LessonDocumentation", "PersonalNote"]) -> TimePeriod:
        """Get the date of this lesson documentation or personal note.

        :: warning::

            As events can be longer than one day,
            this will return `None` for events.
        """
        if self.event:
            return self.event.period_from
        else:
            return self.register_object.period

    @property
    def period_formatted(self: Union["LessonDocumentation", "PersonalNote"]) -> str:
        """Get a formatted version of the period of this object.

        Lesson periods, extra lessons: formatted period
        Events: formatted period range
        """
        return (
            f"{self.period.period}."
            if not self.event
            else f"{self.event.period_from.period}.–{self.event.period_to.period}."
        )

    def get_absolute_url(self: Union["LessonDocumentation", "PersonalNote"]) -> str:
        """Get the absolute url of the detail view for the related register object."""
        return self.register_object.get_alsijil_url(self.calendar_week)


class PersonalNote(RegisterObjectRelatedMixin, ExtensibleModel):
    """A personal note about a single person.

    Used in the class register to note absences, excuses
    and remarks about a student in a single lesson period.
    """

    data_checks = [
        NoPersonalNotesInCancelledLessonsDataCheck,
        NoGroupsOfPersonsSetInPersonalNotesDataCheck,
        PersonalNoteOnHolidaysDataCheck,
        ExcusesWithoutAbsences,
    ]

    objects = PersonalNoteManager.from_queryset(PersonalNoteQuerySet)()

    person = models.ForeignKey("core.Person", models.CASCADE, related_name="personal_notes")
    groups_of_person = models.ManyToManyField("core.Group", related_name="+")

    week = models.IntegerField(blank=True, null=True)
    year = models.IntegerField(verbose_name=_("Year"), blank=True, null=True)

    lesson_period = models.ForeignKey(
        "chronos.LessonPeriod", models.CASCADE, related_name="personal_notes", blank=True, null=True
    )
    event = models.ForeignKey(
        "chronos.Event", models.CASCADE, related_name="personal_notes", blank=True, null=True
    )
    extra_lesson = models.ForeignKey(
        "chronos.ExtraLesson", models.CASCADE, related_name="personal_notes", blank=True, null=True
    )

    absent = models.BooleanField(default=False)
    late = models.PositiveSmallIntegerField(default=0)
    excused = models.BooleanField(default=False)
    excuse_type = models.ForeignKey(
        ExcuseType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Excuse type"),
    )

    remarks = models.CharField(max_length=200, blank=True)

    extra_marks = models.ManyToManyField("ExtraMark", blank=True, verbose_name=_("Extra marks"))

    def save(self, *args, **kwargs):
        if self.excuse_type:
            self.excused = True
        if not self.absent:
            self.excused = False
            self.excuse_type = None
        super().save(*args, **kwargs)

    def reset_values(self):
        """Reset all saved data to default values.

        .. warning ::

            This won't save the data, please execute ``save`` extra.
        """
        defaults = PersonalNote()

        self.absent = defaults.absent
        self.late = defaults.late
        self.excused = defaults.excused
        self.excuse_type = defaults.excuse_type
        self.remarks = defaults.remarks
        self.extra_marks.clear()

    def __str__(self) -> str:
        return f"{self.date_formatted}, {self.lesson_period}, {self.person}"

    def get_absolute_url(self) -> str:
        """Get the absolute url of the detail view for the related register object."""
        return urlparse(super().get_absolute_url())._replace(fragment="personal-notes").geturl()

    class Meta:
        verbose_name = _("Personal note")
        verbose_name_plural = _("Personal notes")
        ordering = [
            "year",
            "week",
            "lesson_period__period__weekday",
            "lesson_period__period__period",
            "person__last_name",
            "person__first_name",
        ]
        constraints = [
            CheckConstraint(
                check=lesson_related_constraint_q, name="one_relation_only_personal_note"
            ),
            models.UniqueConstraint(
                fields=("lesson_period", "week", "year", "event", "extra_lesson"),
                name="unique_personal_note_per_object",
            ),
        ]


class LessonDocumentation(RegisterObjectRelatedMixin, ExtensibleModel):
    """A documentation on a single lesson period.

    Non-personal, includes the topic and homework of the lesson.
    """

    objects = LessonDocumentationManager.from_queryset(LessonDocumentationQuerySet)()

    data_checks = [LessonDocumentationOnHolidaysDataCheck]

    week = models.IntegerField(blank=True, null=True)
    year = models.IntegerField(verbose_name=_("Year"), blank=True, null=True)

    lesson_period = models.ForeignKey(
        "chronos.LessonPeriod", models.CASCADE, related_name="documentations", blank=True, null=True
    )
    event = models.ForeignKey(
        "chronos.Event", models.CASCADE, related_name="documentations", blank=True, null=True
    )
    extra_lesson = models.ForeignKey(
        "chronos.ExtraLesson", models.CASCADE, related_name="documentations", blank=True, null=True
    )

    topic = models.CharField(verbose_name=_("Lesson topic"), max_length=200, blank=True)
    homework = models.CharField(verbose_name=_("Homework"), max_length=200, blank=True)
    group_note = models.CharField(verbose_name=_("Group note"), max_length=200, blank=True)

    def _carry_over_data(self):
        """Carry over data to directly adjacent periods in this lesson if data is not already set.

        Can be deactivated using site preference ``alsijil__carry_over``.
        """
        all_periods_of_lesson = LessonPeriod.objects.filter(
            lesson=self.lesson_period.lesson, period__weekday=self.lesson_period.period.weekday,
        )
        for period in all_periods_of_lesson:
            lesson_documentation = period.get_or_create_lesson_documentation(
                CalendarWeek(week=self.week, year=self.year)
            )

            changed = False

            if not lesson_documentation.topic:
                lesson_documentation.topic = self.topic
                changed = True

            if not lesson_documentation.homework:
                lesson_documentation.homework = self.homework
                changed = True

            if not lesson_documentation.group_note:
                lesson_documentation.group_note = self.group_note
                changed = True

            if changed:
                lesson_documentation.save(carry_over=False)

    def __str__(self) -> str:
        return f"{self.lesson_period}, {self.date_formatted}"

    def save(self, carry_over=True, *args, **kwargs):
        if (
            get_site_preferences()["alsijil__carry_over"]
            and (self.topic or self.homework or self.group_note)
            and self.lesson_period
            and carry_over
        ):
            self._carry_over_data()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _("Lesson documentation")
        verbose_name_plural = _("Lesson documentations")
        ordering = [
            "year",
            "week",
            "lesson_period__period__weekday",
            "lesson_period__period__period",
        ]
        constraints = [
            CheckConstraint(
                check=lesson_related_constraint_q, name="one_relation_only_lesson_documentation",
            ),
            models.UniqueConstraint(
                fields=("lesson_period", "week", "year", "event", "extra_lesson"),
                name="unique_documentation_per_object",
            ),
        ]


class ExtraMark(ExtensibleModel):
    """A model for extra marks.

    Can be used for lesson-based counting of things (like forgotten homework).
    """

    short_name = models.CharField(max_length=255, unique=True, verbose_name=_("Short name"))
    name = models.CharField(max_length=255, unique=True, verbose_name=_("Name"))

    def __str__(self):
        return f"{self.name}"

    @property
    def count_label(self):
        return f"{self.short_name}_count"

    class Meta:
        ordering = ["short_name"]
        verbose_name = _("Extra mark")
        verbose_name_plural = _("Extra marks")
        constraints = [
            models.UniqueConstraint(
                fields=("site_id", "short_name"), name="unique_mark_short_name"
            ),
            models.UniqueConstraint(fields=("site_id", "name"), name="unique_mark_name"),
        ]


class GroupRole(ExtensibleModel):
    objects = GroupRoleManager.from_queryset(GroupRoleQuerySet)()

    name = models.CharField(max_length=255, verbose_name=_("Name"))
    icon = models.CharField(max_length=50, blank=True, choices=ICONS, verbose_name=_("Icon"))
    colour = ColorField(blank=True, verbose_name=_("Colour"))

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Group role")
        verbose_name_plural = _("Group roles")
        constraints = [
            models.UniqueConstraint(fields=("site_id", "name"), name="unique_role_per_site"),
        ]


class GroupRoleAssignment(GroupPropertiesMixin, ExtensibleModel):
    objects = GroupRoleAssignmentManager.from_queryset(GroupRoleAssignmentQuerySet)()

    role = models.ForeignKey(
        GroupRole,
        on_delete=models.CASCADE,
        related_name="assignments",
        verbose_name=_("Group role"),
    )
    person = models.ForeignKey(
        "core.Person",
        on_delete=models.CASCADE,
        related_name="group_roles",
        verbose_name=_("Assigned person"),
    )
    groups = models.ManyToManyField(
        "core.Group", related_name="group_roles", verbose_name=_("Groups"),
    )
    date_start = models.DateField(verbose_name=_("Start date"))
    date_end = models.DateField(
        blank=True,
        null=True,
        verbose_name=_("End date"),
        help_text=_("Can be left empty if end date is not clear yet"),
    )

    def __str__(self):
        date_end = date_format(self.date_end) if self.date_end else "?"
        return f"{self.role}: {self.person}, {date_format(self.date_start)}–{date_end}"

    @property
    def date_range(self) -> str:
        if not self.date_end:
            return f"{date_format(self.date_start)}–?"
        else:
            return f"{date_format(self.date_start)}–{date_format(self.date_end)}"

    class Meta:
        verbose_name = _("Group role assignment")
        verbose_name_plural = _("Group role assignments")


class AlsijilGlobalPermissions(GlobalPermissionModel):
    class Meta:
        managed = False
        permissions = (
            ("view_week", _("Can view week overview")),
            ("register_absence", _("Can register absence")),
            ("list_personal_note_filters", _("Can list all personal note filters")),
        )
