from collections import OrderedDict
from datetime import timedelta
from typing import Optional

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Exists, F, OuterRef, Q, Sum
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import ugettext as _
from django.views.decorators.cache import cache_page

from biscuit.apps.chronos.models import LessonPeriod, TimePeriod
from biscuit.apps.chronos.util import CalendarWeek, current_lesson_periods
from biscuit.core.models import Group, Person

from .forms import LessonDocumentationForm, PersonalNoteFormSet, SelectForm
from .models import LessonDocumentation, PersonalNote


@login_required
def lesson(request: HttpRequest, year: Optional[int] = None, week: Optional[int] = None, period_id: Optional[int] = None) -> HttpResponse:
    context = {}

    if year and week and period_id:
        # Get a specific lesson period if provided in URL
        lesson_period = LessonPeriod.objects.get(pk=period_id)
        wanted_week = CalendarWeek(year=year, week=week)
    else:
        # Determine current lesson by current date and time
        lesson_period = current_lesson_periods().filter(
            Q(substitutions__teachers=request.user.person) | Q(lesson__teachers=request.user.person)).first()
        wanted_week = CalendarWeek()

    if not lesson_period:
        raise Http404(_('You either selected an invalid lesson or there is currently no lesson in progress.'))

    context['lesson_period'] = lesson_period
    context['week'] = wanted_week
    context['day'] = wanted_week[lesson_period.period.weekday - 1]

    # Create or get lesson documentation object; can be empty when first opening lesson
    lesson_documentation, created = LessonDocumentation.objects.get_or_create(
        lesson_period=lesson_period, week=wanted_week.week)
    lesson_documentation_form = LessonDocumentationForm(
        request.POST or None, instance=lesson_documentation, prefix='leson_documentation')

    # Find all persons in the associated groups that do not yet have a personal note for this lesson
    missing_persons = Person.objects.annotate(
        no_personal_notes=~Exists(PersonalNote.objects.filter(
            week=wanted_week.week,
            lesson_period=lesson_period,
            person__pk=OuterRef('pk')
        ))
    ).filter(
        member_of__in=Group.objects.filter(pk__in=lesson_period.lesson.groups.all()),
        is_active=True,
        no_personal_notes=True
    )

    # Create all missing personal notes
    PersonalNote.objects.bulk_create([
        PersonalNote(person=person, lesson_period=lesson_period,
                     week=wanted_week.week) for person in missing_persons  # FIXME Respect year as well
    ])

    # Create a formset that holds all personal notes for all persons in this lesson
    persons_qs = PersonalNote.objects.select_related('person').filter(
        lesson_period=lesson_period, week=wanted_week.week)  # FIXME Respect year as well
    personal_note_formset = PersonalNoteFormSet(
        request.POST or None, queryset=persons_qs, prefix='personal_notes')

    if request.method == 'POST':
        if lesson_documentation_form.is_valid():
            lesson_documentation_form.save()
        if personal_note_formset.is_valid():
            personal_note_formset.save()

    context['lesson_documentation'] = lesson_documentation
    context['lesson_documentation_form'] = lesson_documentation_form
    context['personal_note_formset'] = personal_note_formset

    return render(request, 'alsijil/lesson.html', context)


@login_required
def group_week(request: HttpRequest, year: Optional[int] = None, week: Optional[int] = None) -> HttpResponse:
    context = {}

    if year and week:
        wanted_week = CalendarWeek(year=year, week=week)
    else:
        wanted_week = CalendarWeek()

    if request.GET.get('group', None):
        # Use requested group
        group = Group.objects.get(pk=request.GET['group'])
    elif hasattr(request, 'user') and hasattr(request.user, 'person'):
        # Try to select group from owned groups of user
        group = request.user.person.owner_of.first()
    else:
        group = None

    if group:
        # Get all lesson periods for the selected group
        lesson_periods = LessonPeriod.objects.annotate(
            has_documentation=Exists(LessonDocumentation.objects.filter(
                ~Q(topic__exact=''),
                lesson_period=OuterRef('pk'),
                week=wanted_week.week
            ))
        ).filter(
            lesson__date_start__lte=wanted_week[0] + timedelta(days=1) * F('period__weekday') - 1,
            lesson__date_end__gte=wanted_week[0] + timedelta(days=1) * F('period__weekday') - 1
        ).select_related(
            'lesson', 'lesson__subject', 'period', 'room'
        ).prefetch_related(
            'lesson__groups', 'lesson__teachers', 'substitutions'
        ).extra(
            select={'_week': wanted_week.week}
        ).filter(
            Q(lesson__groups=group) | Q(lesson__groups__parent_groups=group)
        ).distinct()

        # Aggregate all personal notes for this group and week
        persons = Person.objects.filter(
            is_active=True
        ).filter(
            Q(member_of=group) | Q(member_of__parent_groups=group)
        ).distinct().prefetch_related(
            'personal_notes'
        ).annotate(
            absences=Count('personal_notes__absent', filter=Q(
                personal_notes__lesson_period__in=lesson_periods,
                personal_notes__week=wanted_week.week,
                personal_notes__absent=True
            )),
            unexcused=Count('personal_notes__absent', filter=Q(
                personal_notes__lesson_period__in=lesson_periods,
                personal_notes__week=wanted_week.week,
                personal_notes__absent=True,
                personal_notes__excused=False
            )),
            tardiness=Sum('personal_notes__late', filter=Q(
                personal_notes__lesson_period__in=lesson_periods,
                personal_notes__week=wanted_week.week
            ))
        )
    else:
        lesson_periods = None
        persons = None

    # Add a form to filter the view
    select_form = SelectForm(request.GET or None)



    context['current_head'] = str(wanted_week)
    context['week'] = wanted_week
    context['group'] = group
    context['lesson_periods'] = lesson_periods
    context['persons'] = persons
    context['select_form'] = select_form

    week_prev = wanted_week - 1
    week_next = wanted_week + 1
    context['url_prev'] = '%s?%s' % (reverse('group_week_by_week', args=[week_prev.year, week_prev.week]), request.GET.urlencode())
    context['url_next'] = '%s?%s' % (reverse('group_week_by_week', args=[week_next.year, week_next.week]), request.GET.urlencode())


    return render(request, 'alsijil/group_week.html', context)
