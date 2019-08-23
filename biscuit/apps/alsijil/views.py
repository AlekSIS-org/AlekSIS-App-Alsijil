from typing import Optional

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils.translation import ugettext as _

from biscuit.apps.chronos.models import LessonPeriod
from biscuit.apps.chronos.util import current_lesson_periods, current_week

from .forms import LessonDocumentationForm
from .models import LessonDocumentation


@login_required
def lesson(request: HttpRequest, week: Optional[int] = None, period_id: Optional[int] = None) -> HttpResponse:
    context = {}

    if week and period_id:
        # Get a specific lesson period if provided in URL
        lesson_period = LessonPeriod.objects.get(pk=period_id)
        wanted_week = week
    else:
        # Determine current lesson by current date and time
        lesson_period = current_lesson_periods().filter(
            lesson__teachers=request.user.person).first()
        wanted_week = current_week()

    context['lesson_period'] = lesson_period
    context['week'] = wanted_week

    if lesson_period:
        # Create or get lesson documentation object; can be empty when first opening lesson
        lesson_documentation, created = LessonDocumentation.objects.get_or_create(lesson_period=lesson_period, week=wanted_week)
        lesson_documentation_form = LessonDocumentationForm(request.POST or None, instance=lesson_documentation)

        if request.method == 'POST':
            if request.POST.get('action', None) == 'lesson_documentation':
                # Save the lesson documentation
                if lesson_documentation_form.is_valid():
                    lesson_documentation_form.save()

        context['lesson_documentation_form'] = lesson_documentation_form

    return render(request, 'alsijil/lesson.html', context)
