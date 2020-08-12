from django.db import models
from django.utils.translation import gettext_lazy as _

from calendarweek import CalendarWeek

from aleksis.apps.chronos.models import LessonPeriod
from aleksis.core.mixins import ExtensibleModel
from aleksis.core.util.core_helpers import get_site_preferences


def isidentifier(value: str) -> bool:
    return value.isidentifier()


class ExcuseType(ExtensibleModel):
    """An type of excuse.

    Can be used to count different types of absences separately.
    """

    short_name = models.CharField(
        max_length=255, unique=True, verbose_name=_("Short name")
    )
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


class PersonalNote(ExtensibleModel):
    """A personal note about a single person.

    Used in the class register to note absences, excuses
    and remarks about a student in a single lesson period.
    """

    person = models.ForeignKey(
        "core.Person", models.CASCADE, related_name="personal_notes"
    )
    groups_of_person = models.ManyToManyField("core.Group", related_name="+")

    week = models.IntegerField()
    lesson_period = models.ForeignKey(
        "chronos.LessonPeriod", models.CASCADE, related_name="personal_notes"
    )

    absent = models.BooleanField(default=False)
    late = models.IntegerField(default=0)
    excused = models.BooleanField(default=False)
    excuse_type = models.ForeignKey(
        ExcuseType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Excuse type"),
    )

    remarks = models.CharField(max_length=200, blank=True)

    extra_marks = models.ManyToManyField(
        "ExtraMark", null=True, blank=True, verbose_name=_("Extra marks")
    )

    def save(self, *args, **kwargs):
        if self.excuse_type:
            self.excused = True
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _("Personal note")
        verbose_name_plural = _("Personal notes")
        unique_together = [["lesson_period", "week", "person"]]
        ordering = [
            "lesson_period__lesson__validity__date_start",
            "week",
            "lesson_period__period__weekday",
            "lesson_period__period__period",
            "person__last_name",
            "person__first_name",
        ]


class LessonDocumentation(ExtensibleModel):
    """A documentation on a single lesson period.

    Non-personal, includes the topic and homework of the lesson.
    """

    week = models.IntegerField()
    lesson_period = models.ForeignKey(
        "chronos.LessonPeriod", models.CASCADE, related_name="documentations"
    )

    topic = models.CharField(verbose_name=_("Lesson topic"), max_length=200, blank=True)
    homework = models.CharField(verbose_name=_("Homework"), max_length=200, blank=True)
    group_note = models.CharField(
        verbose_name=_("Group note"), max_length=200, blank=True
    )

    def _carry_over_data(self):
        """Carry over data to the next lesson, if exists and data are not already set.

        Can be deactivated using site preference ``alsijil__carry_over``.
        """
        if get_site_preferences()["alsijil__carry_over"] and (
            self.topic or self.homework or self.group_note
        ):
            try:
                second_period = LessonPeriod.objects.get(
                    lesson=self.lesson_period.lesson,
                    period__weekday=self.lesson_period.period.weekday,
                    period__period=self.lesson_period.period.period + 1,
                )
                lesson_documentation = second_period.get_or_create_lesson_documentation(
                    CalendarWeek(
                        week=self.week,
                        year=self.lesson_period.lesson.get_year(self.week),
                    )
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
            except LessonPeriod.DoesNotExist:
                # Do nothing if it's a single period
                pass

    def save(self, *args, **kwargs):
        self._carry_over_data()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _("Lesson documentation")
        verbose_name_plural = _("Lesson documentations")
        unique_together = [["lesson_period", "week"]]
        ordering = [
            "lesson_period__lesson__validity__date_start",
            "week",
            "lesson_period__period__weekday",
            "lesson_period__period__period",
        ]


class ExtraMark(ExtensibleModel):
    """A model for extra marks.

    Can be used for lesson-based counting of things (like forgotten homework).
    """

    short_name = models.CharField(
        max_length=255, unique=True, verbose_name=_("Short name")
    )
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
