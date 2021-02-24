from typing import List, Optional, Union

from django.db.models.expressions import Exists, OuterRef
from django.db.models.query import Prefetch, QuerySet
from django.db.models.query_utils import Q
from django.http import HttpRequest

from calendarweek import CalendarWeek

from aleksis.apps.alsijil.models import LessonDocumentation
from aleksis.apps.chronos.models import Event, ExtraLesson, LessonPeriod
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
