from datetime import date
from typing import Optional

from django.db.models import Exists, OuterRef

from biscuit.apps.chronos.models import LessonPeriod
from biscuit.apps.chronos.util import CalendarWeek
from biscuit.core.models import Group, Person

from .models import PersonalNote


@Person.method
def mark_absent(self, day: date, starting_period: Optional[int] = 0, absent=True, excused=False):
    wanted_week = CalendarWeek.from_date(day)

    # Get all lessons of this person on the specified day
    lesson_periods = self.lesson_periods_as_participant.on_day(
        day
    ).filter(
        period__period__gte=starting_period
    )

    # Create and update all personal notes for the discovered lesson periods
    for lesson_period in lesson_periods:
        PersonalNote.objects.update_or_create(
            person=self,
            lesson_period=lesson_period,
            week=wanted_week.week,
            defaults={
                'absent': absent,
                'excused': excused
            }
        )


@LessonPeriod.method
def get_personal_notes(self, wanted_week: CalendarWeek):
    # Find all persons in the associated groups that do not yet have a personal note for this lesson
    missing_persons = Person.objects.annotate(
        no_personal_notes=~Exists(PersonalNote.objects.filter(
            week=wanted_week.week,
            lesson_period=self,
            person__pk=OuterRef('pk')
        ))
    ).filter(
        member_of__in=Group.objects.filter(pk__in=self.lesson.groups.all()),
        is_active=True,
        no_personal_notes=True
    )

    # Create all missing personal notes
    PersonalNote.objects.bulk_create([
        PersonalNote(person=person, lesson_period=self,
                     week=wanted_week.week) for person in missing_persons
    ])

    return PersonalNote.objects.select_related('person').filter(
        lesson_period=self, week=wanted_week.week)
