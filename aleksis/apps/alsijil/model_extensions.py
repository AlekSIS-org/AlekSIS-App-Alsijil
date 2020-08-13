from datetime import date
from typing import Dict, Optional, Union

from django.db.models import Exists, OuterRef, QuerySet

from calendarweek import CalendarWeek

from aleksis.apps.chronos.models import LessonPeriod
from aleksis.core.models import Group, Person

from .models import ExcuseType, ExtraMark, LessonDocumentation, PersonalNote


@Person.method
def mark_absent(
    self,
    day: date,
    from_period: int = 0,
    absent: bool = True,
    excused: bool = False,
    excuse_type: Optional[ExcuseType] = None,
    remarks: str = "",
):
    """Mark a person absent for all lessons in a day, optionally starting with a selected period number.

    This function creates `PersonalNote` objects for every `LessonPeriod` the person
    participates in on the selected day and marks them as absent/excused.

    ..note:: Only available when AlekSIS-App-Alsijil is installed.

    :Date: 2019-11-10
    :Authors:
        - Dominik George <dominik.george@teckids.org>
    """
    wanted_week = CalendarWeek.from_date(day)

    # Get all lessons of this person on the specified day
    lesson_periods = (
        self.lesson_periods_as_participant.on_day(day)
        .filter(period__period__gte=from_period)
        .annotate_week(wanted_week)
    )

    # Create and update all personal notes for the discovered lesson periods
    for lesson_period in lesson_periods:
        sub = lesson_period.get_substitution()
        if sub:
            if sub.is_cancelled:
                continue

        personal_note, created = PersonalNote.objects.update_or_create(
            person=self,
            lesson_period=lesson_period,
            week=wanted_week.week,
            defaults={"absent": absent, "excused": excused, "excuse_type": excuse_type},
        )
        personal_note.groups_of_person.set(self.member_of.all())

        if remarks:
            if personal_note.remarks:
                personal_note.remarks += "; %s" % remarks
            else:
                personal_note.remarks = remarks
            personal_note.save()


@LessonPeriod.method
def get_personal_notes(self, wanted_week: CalendarWeek):
    """Get all personal notes for that lesson in a specified week.

    Returns all linked `PersonalNote` objects, filtered by the given weeek,
    creating those objects that haven't been created yet.

    ..note:: Only available when AlekSIS-App-Alsijil is installed.

    :Date: 2019-11-09
    :Authors:
        - Dominik George <dominik.george@teckids.org>
    """
    # Find all persons in the associated groups that do not yet have a personal note for this lesson
    missing_persons = Person.objects.annotate(
        no_personal_notes=~Exists(
            PersonalNote.objects.filter(
                week=wanted_week.week, lesson_period=self, person__pk=OuterRef("pk")
            )
        )
    ).filter(
        member_of__in=Group.objects.filter(pk__in=self.lesson.groups.all()),
        is_active=True,
        no_personal_notes=True,
    )

    # Create all missing personal notes
    new_personal_notes = [
        PersonalNote(person=person, lesson_period=self, week=wanted_week.week)
        for person in missing_persons
    ]
    PersonalNote.objects.bulk_create(new_personal_notes)

    for personal_note in new_personal_notes:
        personal_note.groups_of_person.set(personal_note.person.member_of.all())

    return PersonalNote.objects.select_related("person").filter(
        lesson_period=self, week=wanted_week.week
    )


@LessonPeriod.method
def get_lesson_documentation(
    self, week: Optional[CalendarWeek] = None
) -> Union[LessonDocumentation, None]:
    """Get lesson documentation object for this lesson."""
    if not week:
        week = self.week
    try:
        return LessonDocumentation.objects.get(lesson_period=self, week=week.week)
    except LessonDocumentation.DoesNotExist:
        return None


@LessonPeriod.method
def get_or_create_lesson_documentation(
    self, week: Optional[CalendarWeek] = None
) -> LessonDocumentation:
    """Get or create lesson documentation object for this lesson."""
    if not week:
        week = self.week
    lesson_documentation, created = LessonDocumentation.objects.get_or_create(
        lesson_period=self, week=week.week
    )
    return lesson_documentation


@LessonPeriod.method
def get_absences(self, week: Optional[CalendarWeek] = None) -> QuerySet:
    """Get all personal notes of absent persons for this lesson."""
    if not week:
        week = self.week
    return self.personal_notes.filter(week=week.week, absent=True)


@LessonPeriod.method
def get_excused_absences(self, week: Optional[CalendarWeek] = None) -> QuerySet:
    """Get all personal notes of excused absent persons for this lesson."""
    if not week:
        week = self.week
    return self.personal_notes.filter(week=week.week, absent=True, excused=True)


@LessonPeriod.method
def get_unexcused_absences(self, week: Optional[CalendarWeek] = None) -> QuerySet:
    """Get all personal notes of unexcused absent persons for this lesson."""
    if not week:
        week = self.week
    return self.personal_notes.filter(week=week.week, absent=True, excused=False)


@LessonPeriod.method
def get_tardinesses(self, week: Optional[CalendarWeek] = None) -> QuerySet:
    """Get all personal notes of late persons for this lesson."""
    if not week:
        week = self.week
    return self.personal_notes.filter(week=week.week, late__gt=0)


@LessonPeriod.method
def get_extra_marks(
    self, week: Optional[CalendarWeek] = None
) -> Dict[ExtraMark, QuerySet]:
    """Get all statistics on extra marks for this lesson."""
    if not week:
        week = self.week

    stats = {}
    for extra_mark in ExtraMark.objects.all():
        qs = self.personal_notes.filter(week=week.week, extra_marks=extra_mark)
        if qs:
            stats[extra_mark] = qs

    return stats
