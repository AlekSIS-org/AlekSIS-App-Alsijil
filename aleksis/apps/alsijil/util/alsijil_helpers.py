from operator import itemgetter
from typing import Any, Dict, List, Optional, Union

from django.db.models.expressions import Exists, OuterRef
from django.db.models.query import Prefetch, QuerySet
from django.db.models.query_utils import Q
from django.http import HttpRequest
from django.utils.formats import date_format
from django.utils.translation import gettext as _

from calendarweek import CalendarWeek

from aleksis.apps.alsijil.forms import FilterRegisterObjectForm
from aleksis.apps.alsijil.models import LessonDocumentation
from aleksis.apps.chronos.models import (
    Event,
    ExtraLesson,
    Holiday,
    LessonPeriod,
    LessonSubstitution,
)
from aleksis.apps.chronos.util.chronos_helpers import get_el_by_pk
from aleksis.core.models import SchoolTerm


def get_register_object_by_pk(
    request: HttpRequest,
    model: Optional[str] = None,
    year: Optional[int] = None,
    week: Optional[int] = None,
    id_: Optional[int] = None,
) -> Optional[Union[LessonPeriod, Event, ExtraLesson]]:
    """Get register object either by given object_id or by time and current person."""
    wanted_week = CalendarWeek(year=year, week=week)
    if id_ and model == "lesson":
        register_object = LessonPeriod.objects.annotate_week(wanted_week).get(pk=id_)
    elif id_ and model == "event":
        register_object = Event.objects.get(pk=id_)
    elif id_ and model == "extra_lesson":
        register_object = ExtraLesson.objects.get(pk=id_)
    elif hasattr(request, "user") and hasattr(request.user, "person"):
        if request.user.person.lessons_as_teacher.exists():
            register_object = (
                LessonPeriod.objects.at_time().filter_teacher(request.user.person).first()
            )
        else:
            register_object = (
                LessonPeriod.objects.at_time().filter_participant(request.user.person).first()
            )
    else:
        register_object = None
    return register_object


def get_timetable_instance_by_pk(
    request: HttpRequest,
    year: Optional[int] = None,
    week: Optional[int] = None,
    type_: Optional[str] = None,
    id_: Optional[int] = None,
):
    """Get timetable object (teacher, room or group) by given type and id or the current person."""
    if type_ and id_:
        return get_el_by_pk(request, type_, id_)
    elif hasattr(request, "user") and hasattr(request.user, "person"):
        return request.user.person


def annotate_documentations(
    klass: Union[Event, LessonPeriod, ExtraLesson], wanted_week: CalendarWeek, pks: List[int]
) -> QuerySet:
    """Return an annotated queryset of all provided register objects."""
    if isinstance(klass, LessonPeriod):
        prefetch = Prefetch(
            "documentations",
            queryset=LessonDocumentation.objects.filter(
                week=wanted_week.week, year=wanted_week.year
            ),
        )
    else:
        prefetch = Prefetch("documentations")
    instances = klass.objects.prefetch_related(prefetch).filter(pk__in=pks)

    if klass == LessonPeriod:
        instances = instances.annotate_week(wanted_week)
    elif klass in (LessonPeriod, ExtraLesson):
        instances = instances.order_by("period__weekday", "period__period")
    else:
        instances = instances.order_by("period_from__weekday", "period_from__period")

    instances = instances.annotate(
        has_documentation=Exists(
            LessonDocumentation.objects.filter(
                ~Q(topic__exact=""), week=wanted_week.week, year=wanted_week.year,
            ).filter(**{klass.label_: OuterRef("pk")})
        )
    )

    return instances


def register_objects_sorter(register_object: Union[LessonPeriod, Event, ExtraLesson]) -> int:
    """Sort key for sorted/sort for sorting a list of class register objects.

    This will sort the objects by the start period.
    """
    if hasattr(register_object, "period"):
        return register_object.period.period
    elif isinstance(register_object, Event):
        return register_object.period_from_on_day
    else:
        return 0


def generate_list_of_all_register_objects(filter_dict: Dict[str, Any]) -> List[dict]:
    # Get data for filtering
    initial_filter_data = FilterRegisterObjectForm.get_initial()
    # Always force a selected school term so that queries won't get to big
    filter_school_term = filter_dict.get("school_term", SchoolTerm.current)
    filter_person = filter_dict.get("person")
    should_have_documentation = filter_dict.get("has_documentation")
    filter_group = filter_dict.get("group")
    filter_groups = filter_dict.get("groups")
    filter_subject = filter_dict.get("subject")
    filter_date_start = filter_dict.get("date_start", initial_filter_data.get("date_start"))
    filter_date_end = filter_dict.get("date_end", initial_filter_data.get("date_end"))
    filter_date = filter_date_start and filter_date_end

    # Get all holidays in the selected school term to sort all data in holidays out
    holidays = Holiday.objects.within_dates(
        filter_school_term.date_start, filter_school_term.date_end
    )
    event_q = Q()
    extra_lesson_q = Q()
    holiday_days = []
    for holiday in holidays:
        event_q = event_q | Q(date_start__lte=holiday.date_end, date_end__gte=holiday.date_start)
        extra_lesson_q = extra_lesson_q | Q(day__gte=holiday.date_start, day__lte=holiday.date_end)
        holiday_days += list(holiday.get_days())

    lesson_periods = (
        LessonPeriod.objects.select_related("lesson")
        .prefetch_related("lesson__teachers", "lesson__groups")
        .filter(lesson__validity__school_term=filter_school_term)
        .distinct()
        .order_by("lesson__validity__school_term__date_start")
    )
    events = Event.objects.filter(school_term=filter_school_term).exclude(event_q).distinct()
    extra_lessons = (
        ExtraLesson.objects.annotate_day()
        .filter(school_term=filter_school_term)
        .exclude(extra_lesson_q)
        .distinct()
    )

    # Do filtering by date, by person, by group and by subject (if activated)
    if filter_date:
        events = events.within_dates(filter_date_start, filter_date_end)
        extra_lessons = extra_lessons.filter(day__gte=filter_date_start, day__lte=filter_date_end)
    if filter_person:
        lesson_periods = lesson_periods.filter(
            Q(lesson__teachers=filter_person) | Q(substitutions__teachers=filter_person)
        )
        events = events.filter_teacher(filter_person)
        extra_lessons = extra_lessons.filter_teacher(filter_person)
    if filter_group:
        lesson_periods = lesson_periods.filter_group(filter_group)
        events = events.filter_group(filter_group)
        extra_lessons = extra_lessons.filter_group(filter_group)
    if filter_groups:
        lesson_periods = lesson_periods.filter_groups(filter_groups)
        events = events.filter_groups(filter_groups)
        extra_lessons = extra_lessons.filter_groups(filter_groups)
    if filter_subject:
        lesson_periods = lesson_periods.filter(
            Q(lesson__subject=filter_subject) | Q(substitutions__subject=filter_subject)
        )
        # As events have no subject, we exclude them at all
        events = []
        extra_lessons = extra_lessons.filter(subject=filter_subject)

    # Prefetch documentations for all register objects and substitutions for all lesson periods
    # in order to prevent extra queries
    documentations = LessonDocumentation.objects.not_empty().filter(
        Q(event__in=events)
        | Q(extra_lesson__in=extra_lessons)
        | Q(lesson_period__in=lesson_periods)
    )
    substitutions = LessonSubstitution.objects.filter(lesson_period__in=lesson_periods)
    if filter_person:
        substitutions = substitutions.filter(teachers=filter_person)

    if lesson_periods:
        # Get date range for which lesson periods should be added
        date_start = lesson_periods.first().lesson.validity.school_term.date_start
        date_end = lesson_periods.last().lesson.validity.school_term.date_end
        if filter_date and filter_date_start > date_start and filter_date_start < date_end:
            date_start = filter_date_start
        if filter_date and filter_date_end < date_end and filter_date_start > date_start:
            date_end = filter_date_end
        print(date_start, date_end)
        weeks = CalendarWeek.weeks_within(date_start, date_end)

        register_objects = []
        for lesson_period in lesson_periods:
            for week in weeks:
                day = week[lesson_period.period.weekday]

                # Skip all lesson periods in holidays
                if day in holiday_days:
                    continue

                # Ensure that the lesson period is in filter range and validity range
                if (
                    lesson_period.lesson.validity.date_start
                    <= day
                    <= lesson_period.lesson.validity.date_end
                ) and (not filter_date or (filter_date_start <= day <= filter_date_end)):

                    filtered_substitutions = list(
                        filter(lambda s: s.lesson_period_id == lesson_period.id, substitutions)
                    )
                    # Skip lesson period if the person isn't a teacher
                    # or substitution teacher of this lesson period
                    if filter_person and (
                        filter_person not in lesson_period.lesson.teachers.all()
                        and not filtered_substitutions
                    ):
                        continue

                    # Annotate substitution to lesson period
                    sub = filtered_substitutions[0] if filtered_substitutions else None

                    subject = sub.subject if sub and sub.subject else lesson_period.lesson.subject
                    teachers = (
                        sub.teacher_names
                        if sub and sub.teachers.all()
                        else lesson_period.lesson.teacher_names
                    )
                    if filter_subject and filter_subject != subject:
                        continue

                    # Filter matching documentations and annotate if they exist
                    filtered_documentations = list(
                        filter(
                            lambda d: d.week == week.week
                            and d.year == week.year
                            and d.lesson_period_id == lesson_period.pk,
                            documentations,
                        )
                    )
                    has_documentation = bool(filtered_documentations)

                    if (
                        should_have_documentation is not None
                        and has_documentation != should_have_documentation
                    ):
                        continue

                    # Build table entry
                    entry = {
                        "pk": f"lesson_period_{lesson_period.pk}_{week.year}_{week.week}",
                        "week": week,
                        "has_documentation": has_documentation,
                        "substitution": sub,
                        "register_object": lesson_period,
                        "date": date_format(day),
                        "date_sort": day,
                        "period": f"{lesson_period.period.period}.",
                        "period_sort": lesson_period.period.period,
                        "groups": lesson_period.lesson.group_names,
                        "teachers": teachers,
                        "subject": subject.name,
                    }
                    if has_documentation:
                        doc = filtered_documentations[0]
                        entry["topic"] = doc.topic
                        entry["homework"] = doc.homework
                        entry["group_note"] = doc.group_note
                    register_objects.append(entry)

        for register_object in list(extra_lessons) + list(events):
            filtered_documentations = list(
                filter(
                    lambda d: getattr(d, f"{register_object.label_}_id") == register_object.pk,
                    documentations,
                )
            )
            has_documentation = bool(filtered_documentations)

            if (
                should_have_documentation is not None
                and has_documentation != should_have_documentation
            ):
                continue

            if isinstance(register_object, ExtraLesson):
                day = date_format(register_object.day)
                day_sort = register_object.day
                period = f"{register_object.period.period}."
                period_sort = register_object.period.period
            else:
                day = (
                    f"{date_format(register_object.date_start)}"
                    f"–{date_format(register_object.date_end)}"
                )
                day_sort = register_object.date_start
                period = (
                    f"{register_object.period_from.period}.–{register_object.period_to.period}."
                )
                period_sort = register_object.period_from.period

            # Build table entry
            entry = {
                "pk": f"{register_object.label_}_{register_object.pk}",
                "has_documentation": has_documentation,
                "register_object": register_object,
                "date": day,
                "date_sort": day_sort,
                "period": period,
                "period_sort": period_sort,
                "groups": register_object.group_names,
                "teachers": register_object.teacher_names,
                "subject": register_object.subject.name
                if isinstance(register_object, ExtraLesson)
                else _("Event"),
            }
            if has_documentation:
                doc = filtered_documentations[0]
                entry["topic"] = doc.topic
                entry["homework"] = doc.homework
                entry["group_note"] = doc.group_note
            register_objects.append(entry)

        # Sort table entries by date and period and configure table
        register_objects = sorted(register_objects, key=itemgetter("date_sort", "period_sort"))
        return register_objects
    return []
