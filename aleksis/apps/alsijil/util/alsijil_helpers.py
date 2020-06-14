from typing import Optional

from django.db.models import Count, Exists, OuterRef, Q, Sum
from django.http import HttpRequest, HttpResponseNotFound
from django.shortcuts import get_object_or_404

from calendarweek import CalendarWeek

from aleksis.apps.chronos.managers import TimetableType
from aleksis.apps.chronos.models import LessonPeriod
from aleksis.apps.chronos.util.chronos_helpers import get_el_by_pk
from ..models import LessonDocumentation


def get_lesson_period_by_pk(
    request: HttpRequest,
    year: Optional[int] = None,
    week: Optional[int] = None,
    period_id: Optional[int] = None,
):
    if period_id:
        lesson_period = LessonPeriod.objects.get(pk=period_id)
        wanted_week = CalendarWeek(year=year, week=week)
    elif hasattr(request, "user") and hasattr(request.user, "person"):
        if request.user.person.lessons_as_teacher.exists():
            lesson_period = LessonPeriod.objects.at_time().filter_teacher(request.user.person).first()
        else:
            lesson_period = LessonPeriod.objects.at_time().filter_participant(request.user.person).first()
        wanted_week = CalendarWeek()
    else:
        lesson_period = wanted_week = None
    return lesson_period, wanted_week


def get_lesson_periods_by_pk(
    request: HttpRequest,
    year: Optional[int] = None,
    week: Optional[int] = None,
    type_: Optional[str] = None,
    id_: Optional[int] = None,
):
    if year and week:
        wanted_week = CalendarWeek(year=year, week=week)
    else:
        wanted_week = CalendarWeek()

    lesson_periods = LessonPeriod.objects.annotate(
        has_documentation=Exists(
            LessonDocumentation.objects.filter(
                ~Q(topic__exact=""), lesson_period=OuterRef("pk"), week=wanted_week.week
            )
        )
    ).in_week(wanted_week)

    if type_ and id_:
        instance = get_el_by_pk(request, type_, id_)

        if isinstance(instance, HttpResponseNotFound):
            return HttpResponseNotFound()

        type_ = TimetableType.from_string(type_)

        lesson_periods = lesson_periods.filter_from_type(type_, instance)
    elif hasattr(request, "user") and hasattr(request.user, "person"):
        instance = request.user.person
        if request.user.person.lessons_as_teacher.exists():
            lesson_periods = lesson_periods.filter_teacher(request.user.person)
            type_ = TimetableType.TEACHER
        else:
            lesson_periods = lesson_periods.filter_participant(request.user.person)
    else:
        lesson_periods = None
    return lesson_periods, wanted_week, type_, instance