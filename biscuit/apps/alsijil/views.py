from typing import Optional

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils.translation import ugettext as _

from biscuit.apps.chronos.models import Lesson, LessonPeriod
from biscuit.apps.chronos.util import current_lesson_periods, current_week

from .forms import LessonDocumentationForm, PersonalNoteFormSet
from .models import LessonDocumentation, PersonalNote


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
        lesson_documentation_form = LessonDocumentationForm(request.POST or None, instance=lesson_documentation, prefix='leson_documentation')

        # Create all missing personal notes about members of all groups in lesson
        for group in lesson_period.lesson.groups.all():
            for person in group.members.all():
                note, created = PersonalNote.objects.get_or_create(person=person, lesson_period=lesson_period,
                                                                   week=wanted_week)

        # Create a formset that holds all personal notes for all persons in this lesson
        persons_qs = PersonalNote.objects.filter(lesson_period=lesson_period, week=wanted_week)
        personal_note_formset = PersonalNoteFormSet(request.POST or None, queryset=persons_qs, prefix='personal_notes')

        if request.method == 'POST':
            if request.POST.get('action', None) == 'lesson_documentation':
                # Save the lesson documentation
                if lesson_documentation_form.is_valid():
                    lesson_documentation_form.save()
            elif request.POST.get('action', None) == 'personal_notes':
                # Save all personal notes
                if personal_note_formset.is_valid():
                    personal_note_formset.save()

        context['lesson_documentation_form'] = lesson_documentation_form
        context['personal_note_formset'] = personal_note_formset

    return render(request, 'alsijil/lesson.html', context)


@login_required
def group_week(request: HttpRequest, week: Optional[int] = None) -> HttpResponse:
    context = {}

    wanted_week = week or current_week()
    week_start = week_days(wanted_week)[0]
    week_end = week_days(wanted_week)[-1]

    if request.GET,get('group_id', None):
        # Use requested group
        group = Group.objects.get(pk=request.GET['group_id'])
    elif hasattr(request, 'user') and hasattr(request.user, 'person'):
        # Try to select group from owned groups of user
        group = request.user.person.owner_of.first()
    else:
        group = None

    lesson_periods = LessonPeriod.objects.none()

    if group:
        for lesson in group.lessons.filter(date_start__lte=week_start, date_end__gte=week_end):
            qs = lesson.periods

            # Get number of filled-in documentations
            qs.annotate(Count('documentations',
                              filter=Q(documentations__week=wanted_week,
                                       documentations__topic__regex=r'.+'))

            # Combine the lesson periods of all lessons
            lesson_periods = lesson.periods.union(lesson_periods)

    context['week'] = wanted_week
    context['group'] = group
    context['lesson_periods'] = lesson_periods

    return render(request, 'alsijil/group_week.html', context)
