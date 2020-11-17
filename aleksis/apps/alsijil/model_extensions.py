from datetime import date
from typing import Dict, Iterable, Iterator, Optional, Union

from django.db.models import Exists, OuterRef, Q, QuerySet
from django.db.models.aggregates import Count, Sum
from django.utils.translation import gettext as _

import reversion
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
    to_period: Optional[int] = None,
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

    if to_period:
        lesson_periods = lesson_periods.filter(period__period__lte=to_period)

    # Create and update all personal notes for the discovered lesson periods
    for lesson_period in lesson_periods:
        sub = lesson_period.get_substitution()
        if sub and sub.cancelled:
            continue

        with reversion.create_revision():
            personal_note, created = (
                PersonalNote.objects.select_related(None)
                .prefetch_related(None)
                .update_or_create(
                    person=self,
                    lesson_period=lesson_period,
                    week=wanted_week.week,
                    year=wanted_week.year,
                    defaults={"absent": absent, "excused": excused, "excuse_type": excuse_type,},
                )
            )
            personal_note.groups_of_person.set(self.member_of.all())

            if remarks:
                if personal_note.remarks:
                    personal_note.remarks += "; %s" % remarks
                else:
                    personal_note.remarks = remarks
                personal_note.save()


@LessonPeriod.method
def get_personal_notes(self, persons: QuerySet, wanted_week: CalendarWeek):
    """Get all personal notes for that lesson in a specified week.

    Returns all linked `PersonalNote` objects, filtered by the given weeek,
    creating those objects that haven't been created yet.

    ..note:: Only available when AlekSIS-App-Alsijil is installed.

    :Date: 2019-11-09
    :Authors:
        - Dominik George <dominik.george@teckids.org>
    """
    # Find all persons in the associated groups that do not yet have a personal note for this lesson
    missing_persons = persons.annotate(
        no_personal_notes=~Exists(
            PersonalNote.objects.filter(
                week=wanted_week.week,
                year=wanted_week.year,
                lesson_period=self,
                person__pk=OuterRef("pk"),
            )
        )
    ).filter(
        member_of__in=Group.objects.filter(pk__in=self.lesson.groups.all()),
        is_active=True,
        no_personal_notes=True,
    )

    # Create all missing personal notes
    new_personal_notes = [
        PersonalNote(
            person=person, lesson_period=self, week=wanted_week.week, year=wanted_week.year,
        )
        for person in missing_persons
    ]
    PersonalNote.objects.bulk_create(new_personal_notes)

    for personal_note in new_personal_notes:
        personal_note.groups_of_person.set(personal_note.person.member_of.all())

    return (
        PersonalNote.objects.filter(
            lesson_period=self, week=wanted_week.week, year=wanted_week.year, person__in=persons,
        )
        .select_related(None)
        .prefetch_related(None)
        .select_related("person", "excuse_type")
        .prefetch_related("extra_marks")
    )


# Dynamically add extra permissions to Group and Person models in core
# Note: requires migrate afterwards
Group.add_permission(
    "view_week_class_register_group", _("Can view week overview of group class register"),
)
Group.add_permission(
    "view_lesson_class_register_group", _("Can view lesson overview of group class register"),
)
Group.add_permission("view_personalnote_group", _("Can view all personal notes of a group"))
Group.add_permission("edit_personalnote_group", _("Can edit all personal notes of a group"))
Group.add_permission(
    "view_lessondocumentation_group", _("Can view all lesson documentation of a group")
)
Group.add_permission(
    "edit_lessondocumentation_group", _("Can edit all lesson documentation of a group")
)
Group.add_permission("view_full_register_group", _("Can view full register of a group"))
Group.add_permission(
    "register_absence_group", _("Can register an absence for all members of a group")
)
Person.add_permission("register_absence_person", _("Can register an absence for a person"))


@LessonPeriod.method
def get_lesson_documentation(
    self, week: Optional[CalendarWeek] = None
) -> Union[LessonDocumentation, None]:
    """Get lesson documentation object for this lesson."""
    if not week:
        week = self.week
    # Use all to make effect of prefetched data
    doc_filter = filter(
        lambda d: d.week == week.week and d.year == week.year, self.documentations.all(),
    )
    try:
        return next(doc_filter)
    except StopIteration:
        return None


@LessonPeriod.method
def get_or_create_lesson_documentation(
    self, week: Optional[CalendarWeek] = None
) -> LessonDocumentation:
    """Get or create lesson documentation object for this lesson."""
    if not week:
        week = self.week
    lesson_documentation, created = LessonDocumentation.objects.get_or_create(
        lesson_period=self, week=week.week, year=week.year
    )
    return lesson_documentation


@LessonPeriod.method
def get_absences(self, week: Optional[CalendarWeek] = None) -> Iterator:
    """Get all personal notes of absent persons for this lesson."""
    if not week:
        week = self.week

    return filter(
        lambda p: p.week == week.week and p.year == week.year and p.absent,
        self.personal_notes.all(),
    )


@LessonPeriod.method
def get_excused_absences(self, week: Optional[CalendarWeek] = None) -> QuerySet:
    """Get all personal notes of excused absent persons for this lesson."""
    if not week:
        week = self.week
    return self.personal_notes.filter(week=week.week, year=week.year, absent=True, excused=True)


@LessonPeriod.method
def get_unexcused_absences(self, week: Optional[CalendarWeek] = None) -> QuerySet:
    """Get all personal notes of unexcused absent persons for this lesson."""
    if not week:
        week = self.week
    return self.personal_notes.filter(week=week.week, year=week.year, absent=True, excused=False)


@LessonPeriod.method
def get_tardinesses(self, week: Optional[CalendarWeek] = None) -> QuerySet:
    """Get all personal notes of late persons for this lesson."""
    if not week:
        week = self.week
    return self.personal_notes.filter(week=week.week, year=week.year, late__gt=0)


@LessonPeriod.method
def get_extra_marks(self, week: Optional[CalendarWeek] = None) -> Dict[ExtraMark, QuerySet]:
    """Get all statistics on extra marks for this lesson."""
    if not week:
        week = self.week

    stats = {}
    for extra_mark in ExtraMark.objects.all():
        qs = self.personal_notes.filter(week=week.week, year=week.year, extra_marks=extra_mark)
        if qs:
            stats[extra_mark] = qs

    return stats


@Group.class_method
def get_groups_with_lessons(cls: Group):
    """Get all groups which have related lessons or child groups with related lessons."""
    group_pks = (
        cls.objects.for_current_school_term_or_all()
        .annotate(lessons_count=Count("lessons"))
        .filter(lessons_count__gt=0)
        .values_list("pk", flat=True)
    )
    groups = cls.objects.filter(Q(child_groups__pk__in=group_pks) | Q(pk__in=group_pks)).distinct()

    return groups


@Person.method
def get_owner_groups_with_lessons(self: Person):
    """Get all groups the person is an owner of and which have related lessons.

    Groups which have child groups with related lessons are also included.
    """
    return Group.get_groups_with_lessons().filter(owners=self).distinct()


@Group.method
def generate_person_list_with_class_register_statistics(
    self: Group, persons: Optional[Iterable] = None
) -> QuerySet:
    """Get with class register statistics annotated list of all members."""
    persons = persons or self.members.all()
    persons = persons.filter(
        personal_notes__groups_of_person=self,
        personal_notes__lesson_period__lesson__validity__school_term=self.school_term,
    ).annotate(
        absences_count=Count(
            "personal_notes__absent",
            filter=Q(
                personal_notes__absent=True,
                personal_notes__lesson_period__lesson__validity__school_term=self.school_term,
            )
            & (
                Q(personal_notes__lesson_period__lesson__groups=self)
                | Q(personal_notes__lesson_period__lesson__groups__parent_groups=self)
            ),
        ),
        excused=Count(
            "personal_notes__absent",
            filter=Q(
                personal_notes__absent=True,
                personal_notes__excused=True,
                personal_notes__excuse_type__isnull=True,
                personal_notes__lesson_period__lesson__validity__school_term=self.school_term,
            )
            & (
                Q(personal_notes__lesson_period__lesson__groups=self)
                | Q(personal_notes__lesson_period__lesson__groups__parent_groups=self)
            ),
        ),
        unexcused=Count(
            "personal_notes__absent",
            filter=Q(
                personal_notes__absent=True,
                personal_notes__excused=False,
                personal_notes__lesson_period__lesson__validity__school_term=self.school_term,
            )
            & (
                Q(personal_notes__lesson_period__lesson__groups=self)
                | Q(personal_notes__lesson_period__lesson__groups__parent_groups=self)
            ),
        ),
        tardiness=Sum(
            "personal_notes__late",
            filter=(
                Q(personal_notes__lesson_period__lesson__groups=self)
                | Q(personal_notes__lesson_period__lesson__groups__parent_groups=self)
            ),
        ),
        tardiness_count=Count(
            "personal_notes",
            filter=~Q(personal_notes__late=0)
            & Q(personal_notes__lesson_period__lesson__validity__school_term=self.school_term,)
            & (
                Q(personal_notes__lesson_period__lesson__groups=self)
                | Q(personal_notes__lesson_period__lesson__groups__parent_groups=self)
            ),
        ),
    )

    for extra_mark in ExtraMark.objects.all():
        persons = persons.annotate(
            **{
                extra_mark.count_label: Count(
                    "personal_notes",
                    filter=Q(
                        personal_notes__extra_marks=extra_mark,
                        personal_notes__lesson_period__lesson__validity__school_term=self.school_term,  # noqa
                    )
                    & (
                        Q(personal_notes__lesson_period__lesson__groups=self)
                        | Q(personal_notes__lesson_period__lesson__groups__parent_groups=self)
                    ),
                )
            }
        )

    for excuse_type in ExcuseType.objects.all():
        persons = persons.annotate(
            **{
                excuse_type.count_label: Count(
                    "personal_notes__absent",
                    filter=Q(
                        personal_notes__absent=True,
                        personal_notes__excuse_type=excuse_type,
                        personal_notes__lesson_period__lesson__validity__school_term=self.school_term,  # noqa
                    )
                    & (
                        Q(personal_notes__lesson_period__lesson__groups=self)
                        | Q(personal_notes__lesson_period__lesson__groups__parent_groups=self)
                    ),
                )
            }
        )

    return persons
