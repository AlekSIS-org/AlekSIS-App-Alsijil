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
    """Get LessonPeriod object either by given object_id or by time and current person."""
    if period_id:
        lesson_period = LessonPeriod.objects.get(pk=period_id)
    elif hasattr(request, "user") and hasattr(request.user, "person"):
        if request.user.person.lessons_as_teacher.exists():
            lesson_period = LessonPeriod.objects.at_time().filter_teacher(request.user.person).first()
        else:
            lesson_period = LessonPeriod.objects.at_time().filter_participant(request.user.person).first()
    else:
        lesson_period = None
    return lesson_period


def get_instance_by_pk(
    request: HttpRequest,
    year: Optional[int] = None,
    week: Optional[int] = None,
    type_: Optional[str] = None,
    id_: Optional[int] = None,
):
    """Get Instance object by given type and id or the current person."""
    if type_ and id_:
        return get_el_by_pk(request, type_, id_)
    elif hasattr(request, "user") and hasattr(request.user, "person"):
        return request.user.person