from datetime import date, datetime, timedelta
from typing import Optional

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Exists, OuterRef, Q, Sum
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import ugettext as _

from django_tables2 import RequestConfig

from biscuit.apps.chronos.models import LessonPeriod
from biscuit.apps.chronos.util import CalendarWeek
from biscuit.core.models import Group, Person, School
from biscuit.core.decorators import admin_required
from biscuit.core.util import messages

from .forms import LessonDocumentationForm, PersonalNoteFormSet, RegisterAbsenceForm, SelectForm, PersonalNoteFilterForm
from .models import LessonDocumentation, PersonalNoteFilter
from .tables import PersonalNoteFilterTable


@login_required
def lesson(request: HttpRequest, year: Optional[int] = None, week: Optional[int] = None, period_id: Optional[int] = None) -> HttpResponse:
    context = {}

    if year and week and period_id:
        # Get a specific lesson period if provided in URL
        lesson_period = LessonPeriod.objects.get(pk=period_id)
        wanted_week = CalendarWeek(year=year, week=week)
    else:
        # Determine current lesson by current date and time
        lesson_period = LessonPeriod.objects.at_time().filter_teacher(request.user.person).first()
        wanted_week = CalendarWeek()

        if lesson_period:
            return redirect('lesson_by_week_and_period', wanted_week.year, wanted_week.week, lesson_period.pk)
        else:
            raise Http404(_('You either selected an invalid lesson or there is currently no lesson in progress.'))

    if datetime.combine(wanted_week[lesson_period.period.weekday - 1], lesson_period.period.time_start) > datetime.now() and not request.user.is_superuser:
        raise PermissionDenied(_('You are not allowed to create a lesson documentation for a lesson in the future.'))

    context['lesson_period'] = lesson_period
    context['week'] = wanted_week
    context['day'] = wanted_week[lesson_period.period.weekday - 1]

    # Create or get lesson documentation object; can be empty when first opening lesson
    lesson_documentation, created = LessonDocumentation.objects.get_or_create(
        lesson_period=lesson_period, week=wanted_week.week)
    lesson_documentation_form = LessonDocumentationForm(
        request.POST or None, instance=lesson_documentation, prefix='leson_documentation')


    # Create a formset that holds all personal notes for all persons in this lesson
    persons_qs = lesson_period.get_personal_notes(wanted_week)
    personal_note_formset = PersonalNoteFormSet(
        request.POST or None, queryset=persons_qs, prefix='personal_notes')

    if request.method == 'POST':
        if lesson_documentation_form.is_valid():
            lesson_documentation_form.save()

        if personal_note_formset.is_valid():
            instances = personal_note_formset.save()

            # Iterate over personal notes and carry changed absences to following lessons
            for instance in instances:
                instance.person.mark_absent(
                    wanted_week[lesson_period.period.weekday-1],
                    lesson_period.period.period+1,
                    instance.absent,
                    instance.excused
                )

    context['lesson_documentation'] = lesson_documentation
    context['lesson_documentation_form'] = lesson_documentation_form
    context['personal_note_formset'] = personal_note_formset

    return render(request, 'alsijil/lesson.html', context)


@login_required
def week_view(request: HttpRequest, year: Optional[int] = None, week: Optional[int] = None) -> HttpResponse:
    context = {}

    if year and week:
        wanted_week = CalendarWeek(year=year, week=week)
    else:
        wanted_week = CalendarWeek()

    lesson_periods = LessonPeriod.objects.annotate(
        has_documentation=Exists(LessonDocumentation.objects.filter(
            ~Q(topic__exact=''),
            lesson_period=OuterRef('pk'),
            week=wanted_week.week
        ))
    ).in_week(wanted_week)

    group = None  # FIXME workaround for #38
    if request.GET.get('group', None) or request.GET.get('teacher', None) or request.GET.get('room', None):
        lesson_periods = lesson_periods.filter_from_query(request.GET)
        if 'group' in request.GET and request.GET['group']:
            group = Group.objects.get(pk=request.GET['group'])
        else:
            group = None
    elif hasattr(request, 'user') and hasattr(request.user, 'person'):
        group = request.user.person.owner_of.first()
        if group:
            lesson_periods = lesson_periods.filter_group(group)
        elif request.user.person.lessons_as_teacher.exists():
            lesson_periods = lesson_periods.filter_teacher(request.user.person)
        else:
            lesson_periods = lesson_periods.filter_participant(request.user.person)
    else:
        lesson_periods = None

    if lesson_periods:
        # Aggregate all personal notes for this group and week
        persons = Person.objects.filter(
            is_active=True
        ).filter(
            member_of__lessons__lesson_periods__in=lesson_periods
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
        persons = None

    # Add a form to filter the view
    select_form = SelectForm(request.GET or None)

    context['current_head'] = str(wanted_week)
    context['week'] = wanted_week
    context['lesson_periods'] = lesson_periods
    context['persons'] = persons
    context['group'] = group
    context['select_form'] = select_form

    week_prev = wanted_week - 1
    week_next = wanted_week + 1
    context['url_prev'] = '%s?%s' % (reverse('week_view_by_week', args=[week_prev.year, week_prev.week]), request.GET.urlencode())
    context['url_next'] = '%s?%s' % (reverse('week_view_by_week', args=[week_next.year, week_next.week]), request.GET.urlencode())

    return render(request, 'alsijil/week_view.html', context)


@login_required
def full_register_group(request: HttpRequest, id_: int) -> HttpResponse:
    context = {}

    group = get_object_or_404(Group, pk=id_)

    # Get all lesson periods for the selected group
    lesson_periods = LessonPeriod.objects.filter_group(
        group
    ).distinct().prefetch_related(
        'documentations', 'personal_notes'
    )

    weeks = CalendarWeek.weeks_within(School.objects.first().current_term.date_start, School.objects.first().current_term.date_end)
    periods_by_day = {}
    for lesson_period in lesson_periods:
        for week in weeks:
            day = week[lesson_period.period.weekday - 1]

            if lesson_period.lesson.date_start <= day and lesson_period.lesson.date_end >= day:
                documentations = list(filter(lambda d: d.week == week.week, lesson_period.documentations.all()))
                notes = list(filter(lambda d: d.week == week.week, lesson_period.personal_notes.all()))
                substitution = lesson_period.get_substitution(week.week)

                periods_by_day.setdefault(day, []).append((lesson_period, documentations, notes, substitution))

    persons = group.members.annotate(
        absences=Count('personal_notes__absent', filter=Q(
            personal_notes__absent=True
        )),
        unexcused=Count('personal_notes__absent', filter=Q(
            personal_notes__absent=True,
            personal_notes__excused=False
        )),
        tardiness=Sum('personal_notes__late')
    )

    # FIXME Move to manager
    personal_note_filters = PersonalNoteFilter.objects.all()
    for personal_note_filter in personal_note_filters:
        persons = persons.annotate(
            **{'_personal_notes_with_%s' % personal_note_filter.identifier: Count(
                'personal_notes__remarks',
                filter=Q(personal_notes__remarks__iregex=personal_note_filter.regex)
            )}
        )

    context['persons'] = persons
    context['personal_note_filters'] = personal_note_filters
    context['group'] = group
    context['weeks'] = weeks
    context['periods_by_day'] = periods_by_day
    context['today'] = date.today()
    context['school'] School.objects.first()

    return render(request, 'alsijil/print/full_register.html', context)


@admin_required
def register_absence(request: HttpRequest) -> HttpResponse:
    context = {}

    register_absence_form = RegisterAbsenceForm(request.POST or None)

    if request.method == 'POST':
        if register_absence_form.is_valid():
            # Get data from form
            person = register_absence_form.cleaned_data['person']
            start_date = register_absence_form.cleaned_data['date_start']
            end_date = register_absence_form.cleaned_data['date_end']
            from_period = register_absence_form.cleaned_data['from_period']
            absent = register_absence_form.cleaned_data['absent']
            excused = register_absence_form.cleaned_data['excused']
            remarks = register_absence_form.cleaned_data['remarks']

            # Mark person as absent
            delta = end_date - start_date
            for i in range(delta.days+1):
                from_period = from_period if i == 0 else 0
                day = start_date + timedelta(days=i)
                person.mark_absent(day, from_period, absent, excused, remarks)

            messages.success(request, _('The absence has been saved.'))
            return redirect('index')

    context['register_absence_form'] = register_absence_form

    return render(request, 'alsijil/register_absence.html', context)


def list_personal_note_filters(request: HttpRequest) -> HttpResponse:
    context = {}

    personal_note_filters = PersonalNoteFilter.objects.all()

    # Prepare table
    personal_note_filters_table = PersonalNoteFilterTable(personal_note_filters)
    RequestConfig(request).configure(personal_note_filters_table)

    context['personal_note_filters_table'] = personal_note_filters_table

    return render(request, 'alsijil/personal_note_filters.html', context)


def edit_personal_note_filter(request: HttpRequest, id: Optional['int'] = None) -> HttpResponse:
    context = {}

    if id:
        personal_note_filter = PersonalNoteFilter.objects.get(id=id)
        context['personal_note_filter'] = personal_note_filter
        personal_note_filter_form = PersonalNoteFilterForm(
            request.POST or None, instance=personal_note_filter)
    else:
        personal_note_filter_form = PersonalNoteFilterForm(
            request.POST or None)
    
    if request.method == 'POST':
        if personal_note_filter_form.is_valid():
            personal_note_filter_form.save(commit=True)

            messages.success(request, _('The filter has been saved'))
            return redirect('list_personal_note_filters')

    context['personal_note_filter_form'] = personal_note_filter_form

    return render(request, 'alsijil/manage_personal_note_filter.html', context)

@admin_required
def delete_personal_note_filter(request: HttpRequest, id_: int) -> HttpResponse:
    context = {}

    personal_note_filter = get_object_or_404(PersonalNoteFilter, pk=id_)

    PersonalNoteFilter.objects.filter(pk=id_).delete()
    
    messages.success(request, _('The filter has been deleted.'))

    context['personal_note_filter'] = personal_note_filter
    return redirect('list_personal_note_filters')
