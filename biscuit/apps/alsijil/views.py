from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _

from biscuit.apps.chronos.models import LessonPeriod
from biscuit.apps.chronos.util import current_lesson_periods, current_week


@login_required
def lesson(request, week=None, period_id=None):
    context = {}

    if week and period_id:
        lesson_period = LessonPeriod.objects.get(pk=period_id)
        wanted_week = week
    else:
        lesson_period = current_lesson_periods().filter(
            lesson__teachers=request.user.person).first()
        wanted_week = current_week()

    context['lesson_period'] = lesson_period
    context['week'] = wanted_week

    return render(request, 'alsijil/lesson.html', context)
