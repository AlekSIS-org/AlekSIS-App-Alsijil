from django.db import models
from django.utils.formats import date_format
from django.utils.translation import gettext_lazy as _

from calendarweek import CalendarWeek

from aleksis.apps.alsijil.managers import PersonalNoteManager
from aleksis.apps.chronos.mixins import WeekRelatedMixin
from aleksis.apps.chronos.models import LessonPeriod
from aleksis.apps.chronos.util.date import get_current_year
from aleksis.core.mixins import ExtensibleModel
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


class PersonalNote(ExtensibleModel, WeekRelatedMixin):
    """A personal note about a single person.

    Used in the class register to note absences, excuses
    and remarks about a student in a single lesson period.
    """

    objects = PersonalNoteManager()

    person = models.ForeignKey("core.Person", models.CASCADE, related_name="personal_notes")
    groups_of_person = models.ManyToManyField("core.Group", related_name="+")

    week = models.IntegerField()
    year = models.IntegerField(verbose_name=_("Year"), default=get_current_year)

    lesson_period = models.ForeignKey(
        "chronos.LessonPeriod", models.CASCADE, related_name="personal_notes"
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

    def __str__(self):
        return f"{date_format(self.date)}, {self.lesson_period}, {self.person}"

    class Meta:
        verbose_name = _("Personal note")
        verbose_name_plural = _("Personal notes")
        unique_together = [["lesson_period", "week", "person"]]
        ordering = [
            "year",
            "week",
            "lesson_period__period__weekday",
            "lesson_period__period__period",
            "person__last_name",
            "person__first_name",
        ]


class LessonDocumentation(ExtensibleModel, WeekRelatedMixin):
    """A documentation on a single lesson period.

    Non-personal, includes the topic and homework of the lesson.
    """

    week = models.IntegerField()
    year = models.IntegerField(verbose_name=_("Year"), default=get_current_year)

    lesson_period = models.ForeignKey(
        "chronos.LessonPeriod", models.CASCADE, related_name="documentations"
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

    def save(self, *args, **kwargs):
        if get_site_preferences()["alsijil__carry_over"] and (
            self.topic or self.homework or self.group_note
        ):
            self._carry_over_data()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _("Lesson documentation")
        verbose_name_plural = _("Lesson documentations")
        unique_together = [["lesson_period", "week"]]
        ordering = [
            "year",
            "week",
            "lesson_period__period__weekday",
            "lesson_period__period__period",
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
