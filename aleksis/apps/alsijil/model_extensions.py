from datetime import date
from typing import Dict, Iterable, Iterator, Optional, Union

from django.db.models import Exists, FilteredRelation, OuterRef, Q, QuerySet
from django.db.models.aggregates import Count, Sum
from django.urls import reverse
from django.utils.translation import gettext as _

from calendarweek import CalendarWeek

from aleksis.apps.alsijil.managers import PersonalNoteQuerySet
from aleksis.apps.chronos.models import Event, ExtraLesson, LessonPeriod
from aleksis.core.models import Group, Person

from .models import ExcuseType, ExtraMark, LessonDocumentation, PersonalNote


def alsijil_url(
    self: Union[LessonPeriod, Event, ExtraLesson], week: Optional[CalendarWeek] = None
) -> str:
    """Build URL for the detail page of register objects.

    Works with `LessonPeriod`, `Event` and `ExtraLesson`.

    On `LessonPeriod` objects, it will work with annotated or passed weeks.
    """
    if isinstance(self, LessonPeriod):
        week = week or self.week
        return reverse("lesson_period", args=[week.year, week.week, self.pk])
    else:
        return reverse(self.label_, args=[self.pk])


LessonPeriod.property_(alsijil_url)
LessonPeriod.method(alsijil_url, "get_alsijil_url")
Event.property_(alsijil_url)
Event.method(alsijil_url, "get_alsijil_url")
ExtraLesson.property_(alsijil_url)
ExtraLesson.method(alsijil_url, "get_alsijil_url")


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
    dry_run: bool = False,
):
    """Mark a person absent for all lessons in a day, optionally starting with a selected period number.

    This function creates `PersonalNote` objects for every `LessonPeriod` and `ExtraLesson`
    the person participates in on the selected day and marks them as absent/excused.

    :param dry_run: With this activated, the function won't change any data
        and just return the count of affected lessons

    :return: Count of affected lesson periods

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
    extra_lessons = (
        ExtraLesson.objects.filter(groups__members=self)
        .on_day(day)
        .filter(period__period__gte=from_period)
    )

    if to_period:
        lesson_periods = lesson_periods.filter(period__period__lte=to_period)
        extra_lessons = extra_lessons.filter(period__period__lte=to_period)

    # Create and update all personal notes for the discovered lesson periods
    if not dry_run:
        for register_object in list(lesson_periods) + list(extra_lessons):
            if isinstance(register_object, LessonPeriod):
                sub = register_object.get_substitution()
                q_attrs = dict(
                    week=wanted_week.week, year=wanted_week.year, lesson_period=register_object
                )
            else:
                sub = None
                q_attrs = dict(extra_lesson=register_object)

            if sub and sub.cancelled:
                continue

            personal_note, created = (
                PersonalNote.objects.select_related(None)
                .prefetch_related(None)
                .update_or_create(
                    person=self,
                    defaults={"absent": absent, "excused": excused, "excuse_type": excuse_type,},
                    **q_attrs,
                )
            )
            personal_note.groups_of_person.set(self.member_of.all())

            if remarks:
                if personal_note.remarks:
                    personal_note.remarks += "; %s" % remarks
                else:
                    personal_note.remarks = remarks
                personal_note.save()

    return lesson_periods.count() + extra_lessons.count()


def get_personal_notes(
    self, persons: QuerySet, wanted_week: Optional[CalendarWeek] = None
) -> PersonalNoteQuerySet:
    """Get all personal notes for that register object in a specified week.

    The week is optional for extra lessons and events as they have own date information.

    Returns all linked `PersonalNote` objects,
    filtered by the given week for `LessonPeriod` objects,
    creating those objects that haven't been created yet.

    ..note:: Only available when AlekSIS-App-Alsijil is installed.

    :Date: 2019-11-09
    :Authors:
        - Dominik George <dominik.george@teckids.org>
    """
    # Find all persons in the associated groups that do not yet have a personal note for this lesson
    if isinstance(self, LessonPeriod):
        q_attrs = dict(week=wanted_week.week, year=wanted_week.year, lesson_period=self)
    elif isinstance(self, Event):
        q_attrs = dict(event=self)
    else:
        q_attrs = dict(extra_lesson=self)

    missing_persons = persons.annotate(
        no_personal_notes=~Exists(PersonalNote.objects.filter(person__pk=OuterRef("pk"), **q_attrs))
    ).filter(
        member_of__in=Group.objects.filter(pk__in=self.get_groups().all()),
        is_active=True,
        no_personal_notes=True,
    )

    # Create all missing personal notes
    new_personal_notes = [PersonalNote(person=person, **q_attrs,) for person in missing_persons]
    PersonalNote.objects.bulk_create(new_personal_notes)

    for personal_note in new_personal_notes:
        personal_note.groups_of_person.set(personal_note.person.member_of.all())

    return (
        PersonalNote.objects.filter(**q_attrs, person__in=persons)
        .select_related(None)
        .prefetch_related(None)
        .select_related("person", "excuse_type")
        .prefetch_related("extra_marks")
    )


LessonPeriod.method(get_personal_notes)
Event.method(get_personal_notes)
ExtraLesson.method(get_personal_notes)

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


def get_lesson_documentation_single(
    self, week: Optional[CalendarWeek] = None
) -> Union[LessonDocumentation, None]:
    """Get lesson documentation object for this event/extra lesson."""
    if self.documentations.exists():
        return self.documentations.all()[0]
    return None


Event.method(get_lesson_documentation_single, "get_lesson_documentation")
ExtraLesson.method(get_lesson_documentation_single, "get_lesson_documentation")


@LessonPeriod.method
def get_or_create_lesson_documentation(
    self, week: Optional[CalendarWeek] = None
) -> LessonDocumentation:
    """Get or create lesson documentation object for this lesson."""
    if not week:
        week = self.week
    lesson_documentation, __ = LessonDocumentation.objects.get_or_create(
        lesson_period=self, week=week.week, year=week.year
    )
    return lesson_documentation


def get_or_create_lesson_documentation_single(
    self, week: Optional[CalendarWeek] = None
) -> LessonDocumentation:
    """Get or create lesson documentation object for this event/extra lesson."""
    lesson_documentation, created = LessonDocumentation.objects.get_or_create(**{self.label_: self})
    return lesson_documentation


Event.method(get_or_create_lesson_documentation_single, "get_or_create_lesson_documentation")
ExtraLesson.method(get_or_create_lesson_documentation_single, "get_or_create_lesson_documentation")


@LessonPeriod.method
def get_absences(self, week: Optional[CalendarWeek] = None) -> Iterator:
    """Get all personal notes of absent persons for this lesson."""
    if not week:
        week = self.week

    return filter(
        lambda p: p.week == week.week and p.year == week.year and p.absent,
        self.personal_notes.all(),
    )


def get_absences_simple(self, week: Optional[CalendarWeek] = None) -> Iterator:
    """Get all personal notes of absent persons for this event/extra lesson."""
    return filter(lambda p: p.absent, self.personal_notes.all())


Event.method(get_absences_simple, "get_absences")
ExtraLesson.method(get_absences_simple, "get_absences")


@LessonPeriod.method
def get_excused_absences(self, week: Optional[CalendarWeek] = None) -> QuerySet:
    """Get all personal notes of excused absent persons for this lesson."""
    if not week:
        week = self.week
    return self.personal_notes.filter(week=week.week, year=week.year, absent=True, excused=True)


def get_excused_absences_simple(self, week: Optional[CalendarWeek] = None) -> QuerySet:
    """Get all personal notes of excused absent persons for this event/extra lesson."""
    return self.personal_notes.filter(absent=True, excused=True)


Event.method(get_excused_absences_simple, "get_excused_absences")
ExtraLesson.method(get_excused_absences_simple, "get_excused_absences")


@LessonPeriod.method
def get_unexcused_absences(self, week: Optional[CalendarWeek] = None) -> QuerySet:
    """Get all personal notes of unexcused absent persons for this lesson."""
    if not week:
        week = self.week
    return self.personal_notes.filter(week=week.week, year=week.year, absent=True, excused=False)


def get_unexcused_absences_simple(self, week: Optional[CalendarWeek] = None) -> QuerySet:
    """Get all personal notes of unexcused absent persons for this event/extra lesson."""
    return self.personal_notes.filter(absent=True, excused=False)


Event.method(get_unexcused_absences_simple, "get_unexcused_absences")
ExtraLesson.method(get_unexcused_absences_simple, "get_unexcused_absences")


@LessonPeriod.method
def get_tardinesses(self, week: Optional[CalendarWeek] = None) -> QuerySet:
    """Get all personal notes of late persons for this lesson."""
    if not week:
        week = self.week
    return self.personal_notes.filter(week=week.week, year=week.year, late__gt=0)


def get_tardinesses_simple(self, week: Optional[CalendarWeek] = None) -> QuerySet:
    """Get all personal notes of late persons for this event/extra lesson."""
    return self.personal_notes.filter(late__gt=0)


Event.method(get_tardinesses_simple, "get_tardinesses")
ExtraLesson.method(get_tardinesses_simple, "get_tardinesses")


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


def get_extra_marks_simple(self, week: Optional[CalendarWeek] = None) -> Dict[ExtraMark, QuerySet]:
    """Get all statistics on extra marks for this event/extra lesson."""
    stats = {}
    for extra_mark in ExtraMark.objects.all():
        qs = self.personal_notes.filter(extra_marks=extra_mark)
        if qs:
            stats[extra_mark] = qs

    return stats


Event.method(get_extra_marks_simple, "get_extra_marks")
ExtraLesson.method(get_extra_marks_simple, "get_extra_marks")


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
    if persons is None:
        persons = self.members.all()

    lesson_periods = LessonPeriod.objects.filter(
        lesson__validity__school_term=self.school_term
    ).filter(Q(lesson__groups=self) | Q(lesson__groups__parent_groups=self))
    extra_lessons = ExtraLesson.objects.filter(school_term=self.school_term).filter(
        Q(groups=self) | Q(groups__parent_groups=self)
    )
    events = Event.objects.filter(school_term=self.school_term).filter(
        Q(groups=self) | Q(groups__parent_groups=self)
    )

    persons = persons.select_related("primary_group", "primary_group__school_term").order_by(
        "last_name", "first_name"
    )
    persons = persons.annotate(
        filtered_personal_notes=FilteredRelation(
            "personal_notes",
            condition=(
                Q(personal_notes__event__in=events)
                | Q(personal_notes__lesson_period__in=lesson_periods)
                | Q(personal_notes__extra_lesson__in=extra_lessons)
            ),
        )
    ).annotate(
        absences_count=Count(
            "filtered_personal_notes", filter=Q(filtered_personal_notes__absent=True),
        ),
        excused=Count(
            "filtered_personal_notes",
            filter=Q(
                filtered_personal_notes__absent=True,
                filtered_personal_notes__excused=True,
                filtered_personal_notes__excuse_type__isnull=True,
            ),
        ),
        unexcused=Count(
            "filtered_personal_notes",
            filter=Q(filtered_personal_notes__absent=True, filtered_personal_notes__excused=False),
        ),
        tardiness=Sum("filtered_personal_notes__late"),
        tardiness_count=Count(
            "filtered_personal_notes", filter=Q(filtered_personal_notes__late__gt=0),
        ),
    )

    for extra_mark in ExtraMark.objects.all():
        persons = persons.annotate(
            **{
                extra_mark.count_label: Count(
                    "filtered_personal_notes",
                    filter=Q(filtered_personal_notes__extra_marks=extra_mark),
                )
            }
        )

    for excuse_type in ExcuseType.objects.all():
        persons = persons.annotate(
            **{
                excuse_type.count_label: Count(
                    "filtered_personal_notes__absent",
                    filter=Q(
                        filtered_personal_notes__absent=True,
                        filtered_personal_notes__excuse_type=excuse_type,
                    ),
                )
            }
        )

    return persons
