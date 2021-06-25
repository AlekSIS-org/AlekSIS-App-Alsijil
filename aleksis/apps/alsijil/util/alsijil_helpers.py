from datetime import date
from operator import itemgetter
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

from django.db.models.expressions import Exists, OuterRef
from django.db.models.query import Prefetch, QuerySet
from django.db.models.query_utils import Q
from django.http import HttpRequest
from django.utils.formats import date_format
from django.utils.translation import gettext as _

from calendarweek import CalendarWeek

from aleksis.apps.alsijil.forms import FilterRegisterObjectForm
from aleksis.apps.alsijil.models import LessonDocumentation
from aleksis.apps.chronos.models import Event, ExtraLesson, Holiday, LessonPeriod
from aleksis.apps.chronos.util.chronos_helpers import get_el_by_pk


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


def _filter_register_objects_by_dict(
    filter_dict: Dict[str, Any],
    register_objects: QuerySet[Union[LessonPeriod, Event, ExtraLesson]],
    label_: str,
) -> QuerySet[Union[LessonPeriod, Event, ExtraLesson]]:
    """Filter register objects by a dictionary generated through ``FilterRegisterObjectForm``."""
    if label_ == LessonPeriod.label_:
        register_objects = register_objects.filter(
            lesson__validity__school_term=filter_dict.get("school_term")
        )
    else:
        register_objects = register_objects.filter(school_term=filter_dict.get("school_term"))
    register_objects = register_objects.distinct()

    if (
        filter_dict.get("date_start")
        and filter_dict.get("date_end")
        and label_ != LessonPeriod.label_
    ):
        register_objects = register_objects.within_dates(
            filter_dict.get("date_start"), filter_dict.get("date_end")
        )

    if filter_dict.get("person"):
        if label_ == LessonPeriod.label_:
            register_objects = register_objects.filter(
                Q(lesson__teachers=filter_dict.get("person"))
                | Q(substitutions__teachers=filter_dict.get("person"))
            )
        else:
            register_objects = register_objects.filter_teacher(filter_dict.get("person"))

    if filter_dict.get("group"):
        register_objects = register_objects.filter_group(filter_dict.get("group"))

    if filter_dict.get("groups"):
        register_objects = register_objects.filter_groups(filter_dict.get("groups"))

    if filter_dict.get("subject"):
        if label_ == LessonPeriod.label_:
            register_objects = register_objects.filter(
                Q(lesson__subject=filter_dict.get("subject"))
                | Q(substitutions__subject=filter_dict.get("subject"))
            )
        elif label_ == Event.label_:
            # As events have no subject, we exclude them at all
            register_objects = register_objects.none()
        else:
            register_objects = register_objects.filter(subject=filter_dict.get("subject"))

    return register_objects


def _generate_dicts_for_lesson_periods(
    filter_dict: Dict[str, Any],
    lesson_periods: QuerySet[LessonPeriod],
    documentations: Optional[Iterable[LessonDocumentation]] = None,
    holiday_days: Optional[Sequence[date]] = None,
) -> List[Dict[str, Any]]:
    """Generate a list of dicts for use with ``RegisterObjectTable``."""
    if not holiday_days:
        holiday_days = []
    lesson_periods = list(lesson_periods)
    date_start = lesson_periods[0].lesson.validity.date_start
    date_end = lesson_periods[-1].lesson.validity.date_end
    if (
        filter_dict["filter_date"]
        and filter_dict.get("date_start") > date_start
        and filter_dict.get("date_start") < date_end
    ):
        date_start = filter_dict.get("date_start")
    if (
        filter_dict["filter_date"]
        and filter_dict.get("date_end") < date_end
        and filter_dict.get("date_end") > date_start
    ):
        date_end = filter_dict.get("date_end")
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
            ) and (
                not filter_dict.get("filter_date")
                or (filter_dict.get("date_start") <= day <= filter_dict.get("date_end"))
            ):
                sub = lesson_period.get_substitution()

                # Skip lesson period if the person isn't a teacher
                # or substitution teacher of this lesson period
                if filter_dict.get("person") and (
                    filter_dict.get("person") not in lesson_period.lesson.teachers.all() and not sub
                ):
                    continue

                teachers = lesson_period.teacher_names
                if (
                    filter_dict.get("subject")
                    and filter_dict.get("subject") != lesson_period.get_subject()
                ):
                    continue

                # Filter matching documentations and annotate if they exist
                filtered_documentations = list(
                    filter(
                        lambda d: d.week == week.week
                        and d.year == week.year
                        and d.lesson_period_id == lesson_period.pk,
                        documentations
                        if documentations is not None
                        else lesson_period.documentations.all(),
                    )
                )
                has_documentation = bool(filtered_documentations)

                if filter_dict.get(
                    "has_documentation"
                ) is not None and has_documentation != filter_dict.get("has_documentation"):
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
                    "subject": lesson_period.get_subject().name,
                }
                if has_documentation:
                    doc = filtered_documentations[0]
                    entry["topic"] = doc.topic
                    entry["homework"] = doc.homework
                    entry["group_note"] = doc.group_note
                register_objects.append(entry)
    return register_objects


def _generate_dicts_for_events_and_extra_lessons(
    filter_dict: Dict[str, Any],
    register_objects_start: Sequence[Union[Event, ExtraLesson]],
    documentations: Optional[Iterable[LessonDocumentation]] = None,
) -> List[Dict[str, Any]]:
    """Generate a list of dicts for use with ``RegisterObjectTable``."""
    register_objects = []
    for register_object in register_objects_start:
        filtered_documentations = list(
            filter(
                lambda d: getattr(d, f"{register_object.label_}_id") == register_object.pk,
                documentations
                if documentations is not None
                else register_object.documentations.all(),
            )
        )
        has_documentation = bool(filtered_documentations)

        if filter_dict.get(
            "has_documentation"
        ) is not None and has_documentation != filter_dict.get("has_documentation"):
            continue

        if isinstance(register_object, ExtraLesson):
            day = date_format(register_object.day)
            day_sort = register_object.day
            period = f"{register_object.period.period}."
            period_sort = register_object.period.period
        else:
            register_object.annotate_day(register_object.date_end)
            day = (
                f"{date_format(register_object.date_start)}"
                f"–{date_format(register_object.date_end)}"
            )
            day_sort = register_object.date_start
            period = f"{register_object.period_from.period}.–{register_object.period_to.period}."
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

    return register_objects


def generate_list_of_all_register_objects(filter_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate a list of all register objects.

    This list can be filtered using ``filter_dict``. The following keys are supported:
    - ``school_term`` (defaults to the current school term)
    - ``date_start`` and ``date_end`` (defaults to the last thirty days)
    - ``groups`` and/or ``groups``
    - ``person``
    - ``subject``
    """
    # Always force a value for school term, start and end date so that queries won't get too big
    initial_filter_data = FilterRegisterObjectForm.get_initial()
    filter_dict["school_term"] = filter_dict.get("school_term", initial_filter_data["school_term"])

    # If there is not school year at all, there are definitely no data.
    if not filter_dict["school_term"]:
        return []

    filter_dict["date_start"] = filter_dict.get("date_start", initial_filter_data["date_start"])
    filter_dict["date_end"] = filter_dict.get("date_end", initial_filter_data["date_end"])
    filter_dict["filter_date"] = bool(filter_dict.get("date_start")) and bool(
        filter_dict.get("date_end")
    )

    # Get all holidays in the selected school term to sort all data in holidays out
    holidays = Holiday.objects.within_dates(
        filter_dict["school_term"].date_start, filter_dict["school_term"].date_end
    )
    holiday_days = holidays.get_all_days()

    lesson_periods = _filter_register_objects_by_dict(
        filter_dict,
        LessonPeriod.objects.order_by("lesson__validity__date_start"),
        LessonPeriod.label_,
    )
    events = _filter_register_objects_by_dict(
        filter_dict, Event.objects.exclude_holidays(holidays), Event.label_
    )
    extra_lessons = _filter_register_objects_by_dict(
        filter_dict, ExtraLesson.objects.exclude_holidays(holidays), ExtraLesson.label_
    )

    # Prefetch documentations for all register objects and substitutions for all lesson periods
    # in order to prevent extra queries
    documentations = LessonDocumentation.objects.not_empty().filter(
        Q(event__in=events)
        | Q(extra_lesson__in=extra_lessons)
        | Q(lesson_period__in=lesson_periods)
    )

    if lesson_periods:
        register_objects = _generate_dicts_for_lesson_periods(
            filter_dict, lesson_periods, documentations, holiday_days
        )
        register_objects += _generate_dicts_for_events_and_extra_lessons(
            filter_dict, list(events) + list(extra_lessons), documentations
        )

        # Sort table entries by date and period and configure table
        register_objects = sorted(register_objects, key=itemgetter("date_sort", "period_sort"))
        return register_objects
    return []
