from django.db import models
from django.utils.translation import gettext_lazy as _

from aleksis.core.mixins import ExtensibleModel


def isidentifier(value: str) -> bool:
    return value.isidentifier()


class PersonalNote(ExtensibleModel):
    """A personal note about a single person.

    Used in the class register to note absences, excuses
    and remarks about a student in a single lesson period.
    """

    person = models.ForeignKey(
        "core.Person", models.CASCADE, related_name="personal_notes"
    )

    week = models.IntegerField()
    lesson_period = models.ForeignKey(
        "chronos.LessonPeriod", models.CASCADE, related_name="personal_notes"
    )

    absent = models.BooleanField(default=False)
    late = models.IntegerField(default=0)
    excused = models.BooleanField(default=False)

    remarks = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = _("Personal note")
        verbose_name_plural = _("Personal notes")
        unique_together = [["lesson_period", "week", "person"]]
        ordering = [
            "lesson_period__lesson__date_start",
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

    class Meta:
        verbose_name = _("Lesson documentation")
        verbose_name_plural = _("Lesson documentations")
        unique_together = [["lesson_period", "week"]]
        ordering = [
            "lesson_period__lesson__date_start",
            "week",
            "lesson_period__period__weekday",
            "lesson_period__period__period",
        ]


class PersonalNoteFilter(ExtensibleModel):
    """A filter definition that can generate statistics on personal note texts."""

    identifier = models.CharField(
        verbose_name=_("Identifier"),
        max_length=30,
        validators=[isidentifier],
        unique=True,
    )
    description = models.CharField(
        verbose_name=_("Description"), max_length=60, blank=True, unique=True
    )

    regex = models.CharField(
        verbose_name=_("Match expression"), max_length=100, unique=True
    )

    class Meta:
        verbose_name = _("Personal note filter")
        verbose_name_plural = _("Personal note filters")
        ordering = ["identifier"]
