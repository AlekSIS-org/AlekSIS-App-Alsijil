from typing import List, Optional, Union

from django.db.models.expressions import Exists, OuterRef
from django.db.models.query import Prefetch, QuerySet
from django.db.models.query_utils import Q
from django.http import HttpRequest

from calendarweek import CalendarWeek

from aleksis.apps.alsijil.models import LessonDocumentation
from aleksis.apps.chronos.models import Event, ExtraLesson, LessonPeriod
from aleksis.apps.chronos.util.chronos_helpers import get_el_by_pk


def get_lesson_period_by_pk(
    request: HttpRequest,
    year: Optional[int] = None,
    week: Optional[int] = None,
    period_id: Optional[int] = None,
):
    """Get LessonPeriod object either by given object_id or by time and current person."""
    wanted_week = CalendarWeek(year=year, week=week)
    if period_id:
        lesson_period = LessonPeriod.objects.annotate_week(wanted_week).get(pk=period_id)
    elif hasattr(request, "user") and hasattr(request.user, "person"):
        if request.user.person.lessons_as_teacher.exists():
            lesson_period = (
                LessonPeriod.objects.at_time().filter_teacher(request.user.person).first()
            )
        else:
            lesson_period = (
                LessonPeriod.objects.at_time().filter_participant(request.user.person).first()
            )
    else:
        lesson_period = None
    return lesson_period


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
    instances = klass.objects.prefetch_related(
        Prefetch(
            "documentations",
            queryset=LessonDocumentation.objects.filter(
                week=wanted_week.week, year=wanted_week.year
            ),
        )
    ).filter(pk__in=pks)
    if klass == LessonPeriod:
        instances = instances.annotate_week(wanted_week)
    if klass in (LessonPeriod, ExtraLesson):
        instances = instances.order_by("period__weekday", "period__period")
    else:
        instances = instances.order_by("period_from__weekday", "period_from__period")
    args = {Event: "event", LessonPeriod: "lesson_period", ExtraLesson: "extra_lesson"}
    instances = instances.annotate(
        has_documentation=Exists(
            LessonDocumentation.objects.filter(
                ~Q(topic__exact=""), week=wanted_week.week, year=wanted_week.year,
            ).filter(**{args[klass]: OuterRef("pk")})
        )
    )

    return instances


def register_objects_sorter(register_object: Union[LessonPeriod, Event, ExtraLesson]) -> int:
    """Sort key for sorted/sort for sorting a list of class register objects."""
    if hasattr(register_object, "period"):
        return register_object.period.period
    elif isinstance(register_object, Event):
        return register_object.period_from_on_day
    else:
        return 0
