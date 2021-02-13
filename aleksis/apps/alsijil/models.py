from datetime import date
from typing import Optional, Union

from django.db import models
from django.db.models.constraints import CheckConstraint
from django.db.models.query_utils import Q
from django.utils.formats import date_format
from django.utils.translation import gettext_lazy as _

from calendarweek import CalendarWeek

from aleksis.apps.alsijil.data_checks import (
    ExcusesWithoutAbsences,
    LessonDocumentationOnHolidaysDataCheck,
    NoGroupsOfPersonsSetInPersonalNotesDataCheck,
    NoPersonalNotesInCancelledLessonsDataCheck,
    PersonalNoteOnHolidaysDataCheck,
)
from aleksis.apps.alsijil.managers import PersonalNoteManager
from aleksis.apps.chronos.mixins import WeekRelatedMixin
from aleksis.apps.chronos.models import Event, ExtraLesson, LessonPeriod
from aleksis.core.mixins import ExtensibleModel
from aleksis.core.models import SchoolTerm
from aleksis.core.util.core_helpers import get_site_preferences


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
    @property
    def register_object(self) -> Union[LessonPeriod, Event, ExtraLesson]:
        if self.lesson_period:
            return self.lesson_period
        elif self.event:
            return self.event
        else:
            return self.extra_lesson

    @property
    def calendar_week(self) -> CalendarWeek:
        if self.lesson_period:
            return CalendarWeek(week=self.week, year=self.year,)
        elif self.extra_lesson:
            return self.extra_lesson.calendar_week
        else:
            return CalendarWeek.from_date(self.register_object.date_start)

    @property
    def school_term(self) -> SchoolTerm:
        if self.lesson_period:
            return self.lesson_period.lesson.validity.school_term
        else:
            return self.register_object.school_term

    @property
    def date(self) -> Optional[date]:
        if self.lesson_period:
            return super().date
        elif self.extra_lesson:
            return self.extra_lesson.date
        return None

    @property
    def date_formatted(self) -> str:
        return (
            date_format(self.date)
            if self.date
            else f"{self.event.date_start}–{self.event.date_end}"
        )

    def get_absolute_url(self) -> str:
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

    objects = PersonalNoteManager()

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
    late = models.IntegerField(default=0)
    excused = models.BooleanField(default=False)
    excuse_type = models.ForeignKey(
        ExcuseType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Excuse type"),
    )

    remarks = models.CharField(max_length=200, blank=True)

    extra_marks = models.ManyToManyField(
        "ExtraMark", null=True, blank=True, verbose_name=_("Extra marks")
    )

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
        return super().get_absolute_url() + "#personal-notes"

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
            )
        ]


class LessonDocumentation(RegisterObjectRelatedMixin, ExtensibleModel):
    """A documentation on a single lesson period.

    Non-personal, includes the topic and homework of the lesson.
    """

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
        following_periods = LessonPeriod.objects.filter(
            lesson=self.lesson_period.lesson,
            period__weekday=self.lesson_period.period.weekday,
            period__period__gt=self.lesson_period.period.period,
        )
        for period in following_periods:
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
                lesson_documentation.save()

    def __str__(self):
        return f"{self.lesson_period}, {self.date_formatted}"

    def save(self, *args, **kwargs):
        if (
            get_site_preferences()["alsijil__carry_over"]
            and (self.topic or self.homework or self.group_note)
            and self.lesson_period
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
            )
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


class AlsijilGlobalPermissions(ExtensibleModel):
    class Meta:
        managed = False
        permissions = (
            ("view_week", _("Can view week overview")),
            ("register_absence", _("Can register absence")),
            ("list_personal_note_filters", _("Can list all personal note filters")),
        )
