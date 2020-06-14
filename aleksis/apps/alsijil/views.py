from datetime import date, datetime, timedelta
from typing import Optional

from aleksis.apps.chronos.managers import TimetableType
from aleksis.apps.chronos.util.chronos_helpers import get_el_by_pk
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Exists, OuterRef, Q, Sum
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import ugettext as _

from calendarweek import CalendarWeek
from django_tables2 import RequestConfig
from rules.contrib.views import permission_required

from aleksis.apps.chronos.models import LessonPeriod
from aleksis.core.models import Group, Person, SchoolYear
from aleksis.core.util import messages
from aleksis.core.util.core_helpers import objectgetter_optional
from .forms import (
    LessonDocumentationForm,
    PersonalNoteFilterForm,
    PersonalNoteFormSet,
    RegisterAbsenceForm,
    SelectForm,
)
from .models import LessonDocumentation, PersonalNoteFilter
from .tables import PersonalNoteFilterTable
from .util.alsijil_helpers import get_lesson_period_by_pk, get_lesson_periods_by_pk


@permission_required("alsijil.view_lesson", fn=get_lesson_period_by_pk)
def lesson(
    request: HttpRequest,
    year: Optional[int] = None,
    week: Optional[int] = None,
    period_id: Optional[int] = None,
) -> HttpResponse:
    context = {}

    lesson_period, wanted_week = get_lesson_period_by_pk(request, year, week, period_id)

    if not (year and week and period_id):
        if lesson_period:
            return redirect(
                "lesson_by_week_and_period", wanted_week.year, wanted_week.week, lesson_period.pk,
            )
        else:
            raise Http404(
                _(
                    "You either selected an invalid lesson or there is currently no lesson in progress."
                )
            )

    if (
        datetime.combine(
            wanted_week[lesson_period.period.weekday - 1], lesson_period.period.time_start,
        )
        > datetime.now()
        and not request.user.is_superuser
    ):
        raise PermissionDenied(
            _("You are not allowed to create a lesson documentation for a lesson in the future.")
        )

    context["lesson_period"] = lesson_period
    context["week"] = wanted_week
    context["day"] = wanted_week[lesson_period.period.weekday - 1]

    # Create or get lesson documentation object; can be empty when first opening lesson
    lesson_documentation, created = LessonDocumentation.objects.get_or_create(
        lesson_period=lesson_period, week=wanted_week.week
    )
    lesson_documentation_form = LessonDocumentationForm(
        request.POST or None, instance=lesson_documentation, prefix="lesson_documentation",
    )

    # Create a formset that holds all personal notes for all persons in this lesson
    persons_qs = lesson_period.get_personal_notes(wanted_week)
    personal_note_formset = PersonalNoteFormSet(
        request.POST or None, queryset=persons_qs, prefix="personal_notes"
    )

    if request.method == "POST":
        if lesson_documentation_form.is_valid():
            lesson_documentation_form.save()

        if personal_note_formset.is_valid():
            instances = personal_note_formset.save()

            # Iterate over personal notes and carry changed absences to following lessons
            for instance in instances:
                instance.person.mark_absent(
                    wanted_week[lesson_period.period.weekday - 1],
                    lesson_period.period.period + 1,
                    instance.absent,
                    instance.excused,
                )

    context["lesson_documentation"] = lesson_documentation
    context["lesson_documentation_form"] = lesson_documentation_form
    context["personal_note_formset"] = personal_note_formset

    return render(request, "alsijil/lesson.html", context)


@permission_required("alsijil.view_week", fn=get_lesson_periods_by_pk)
def week_view(
    request: HttpRequest, year: Optional[int] = None, week: Optional[int] = None, type_: Optional[str] = None, id_: Optional[int] = None
) -> HttpResponse:
    context = {}

    lesson_periods, wanted_week, type_, instance = get_lesson_periods_by_pk(request, year, week, type_, id_)

    # Add a form to filter the view
    if type_:
        initial = {type_.value: instance}
    else:
        initial = {}
    select_form = SelectForm(request.POST or None, initial=initial)

    if request.method == "POST":
        if select_form.is_valid():
            if "type_" not in select_form.cleaned_data:
                return redirect("week_view_by_week", wanted_week.year, wanted_week.week)
            else:
                return redirect("week_view_by_week", wanted_week.year, wanted_week.week,
                                select_form.cleaned_data["type_"].value, select_form.cleaned_data["instance"].pk)

    if type_ == TimetableType.GROUP:
        group = instance
    else:
        group = None

    if lesson_periods:
        # Aggregate all personal notes for this group and week
        lesson_periods_pk = lesson_periods.values_list("pk", flat=True)
        persons = (
            Person.objects.filter(is_active=True)
            .filter(member_of__lessons__lesson_periods__in=lesson_periods_pk)
            .distinct()
            .prefetch_related("personal_notes")
            .annotate(
                absences_count=Count(
                    "personal_notes__absent",
                    filter=Q(
                        personal_notes__lesson_period__in=lesson_periods_pk,
                        personal_notes__week=wanted_week.week,
                        personal_notes__absent=True,
                    ),
                ),
                unexcused_count=Count(
                    "personal_notes__absent",
                    filter=Q(
                        personal_notes__lesson_period__in=lesson_periods_pk,
                        personal_notes__week=wanted_week.week,
                        personal_notes__absent=True,
                        personal_notes__excused=False,
                    ),
                ),
                tardiness_sum=Sum(
                    "personal_notes__late",
                    filter=Q(
                        personal_notes__lesson_period__in=lesson_periods_pk,
                        personal_notes__week=wanted_week.week,
                    ),
                ),
            )
        )
    else:
        persons = None

    # Resort lesson periods manually because an union queryset doesn't support order_by
    lesson_periods = sorted(lesson_periods, key=lambda x: (x.period.weekday, x.period.period))

    context["week"] = wanted_week
    context["lesson_periods"] = lesson_periods
    context["persons"] = persons
    context["group"] = group
    context["select_form"] = select_form
    context["instance"] = instance

    week_prev = wanted_week - 1
    week_next = wanted_week + 1
    context["url_prev"] = "%s?%s" % (
        reverse("week_view_by_week", args=[week_prev.year, week_prev.week]),
        request.GET.urlencode(),
    )
    context["url_next"] = "%s?%s" % (
        reverse("week_view_by_week", args=[week_next.year, week_next.week]),
        request.GET.urlencode(),
    )

    return render(request, "alsijil/week_view.html", context)


@permission_required("alsijil.full_register_group", fn=objectgetter_optional(Group, None, False))
def full_register_group(request: HttpRequest, id_: int) -> HttpResponse:
    context = {}

    group = get_object_or_404(Group, pk=id_)

    # Get all lesson periods for the selected group
    lesson_periods = (
        LessonPeriod.objects.filter_group(group)
            .distinct()
            .prefetch_related("documentations", "personal_notes")
    )

    weeks = CalendarWeek.weeks_within(
        SchoolYear.current.date_start,
        SchoolYear.current.date_end,
    )

    periods_by_day = {}
    for lesson_period in lesson_periods:
        for week in weeks:
            day = week[lesson_period.period.weekday - 1]

            if lesson_period.lesson.date_start <= day <= lesson_period.lesson.date_end:
                documentations = list(
                    filter(lambda d: d.week == week.week, lesson_period.documentations.all(),)
                )
                notes = list(
                    filter(lambda d: d.week == week.week, lesson_period.personal_notes.all(),)
                )
                substitution = lesson_period.get_substitution(week.week)

                periods_by_day.setdefault(day, []).append(
                    (lesson_period, documentations, notes, substitution)
                )

    persons = group.members.annotate(
        absences_count=Count("personal_notes__absent", filter=Q(personal_notes__absent=True)),
        unexcused=Count(
            "personal_notes__absent",
            filter=Q(personal_notes__absent=True, personal_notes__excused=False),
        ),
        tardiness=Sum("personal_notes__late"),
    )

    # FIXME Move to manager
    personal_note_filters = PersonalNoteFilter.objects.all()
    for personal_note_filter in personal_note_filters:
        persons = persons.annotate(
            **{
                "_personal_notes_with_%s"
                % personal_note_filter.identifier: Count(
                    "personal_notes__remarks",
                    filter=Q(personal_notes__remarks__iregex=personal_note_filter.regex),
                )
            }
        )

    context["persons"] = persons
    context["personal_note_filters"] = personal_note_filters
    context["group"] = group
    context["weeks"] = weeks
    context["periods_by_day"] = periods_by_day
    context["today"] = date.today()

    return render(request, "alsijil/print/full_register.html", context)


@permission_required("alsijil.register_absence")
def register_absence(request: HttpRequest) -> HttpResponse:
    context = {}

    register_absence_form = RegisterAbsenceForm(request.POST or None)

    if request.method == "POST":
        if register_absence_form.is_valid():
            # Get data from form
            person = register_absence_form.cleaned_data["person"]
            start_date = register_absence_form.cleaned_data["date_start"]
            end_date = register_absence_form.cleaned_data["date_end"]
            from_period = register_absence_form.cleaned_data["from_period"]
            absent = register_absence_form.cleaned_data["absent"]
            excused = register_absence_form.cleaned_data["excused"]
            remarks = register_absence_form.cleaned_data["remarks"]

            # Mark person as absent
            delta = end_date - start_date
            for i in range(delta.days + 1):
                from_period = from_period if i == 0 else 0
                day = start_date + timedelta(days=i)
                person.mark_absent(day, from_period, absent, excused, remarks)

            messages.success(request, _("The absence has been saved."))
            return redirect("index")

    context["register_absence_form"] = register_absence_form

    return render(request, "alsijil/register_absence.html", context)


@permission_required("alsijil.list_personal_note_filters")
def list_personal_note_filters(request: HttpRequest) -> HttpResponse:
    context = {}

    personal_note_filters = PersonalNoteFilter.objects.all()

    # Prepare table
    personal_note_filters_table = PersonalNoteFilterTable(personal_note_filters)
    RequestConfig(request).configure(personal_note_filters_table)

    context["personal_note_filters_table"] = personal_note_filters_table

    return render(request, "alsijil/personal_note_filters.html", context)


@permission_required("alsijil.edit_personal_note_filter", fn=objectgetter_optional(PersonalNoteFilter, None, False))
def edit_personal_note_filter(request: HttpRequest, id: Optional["int"] = None) -> HttpResponse:
    context = {}

    if id:
        personal_note_filter = PersonalNoteFilter.objects.get(id=id)
        context["personal_note_filter"] = personal_note_filter
        personal_note_filter_form = PersonalNoteFilterForm(
            request.POST or None, instance=personal_note_filter
        )
    else:
        personal_note_filter_form = PersonalNoteFilterForm(request.POST or None)

    if request.method == "POST":
        if personal_note_filter_form.is_valid():
            personal_note_filter_form.save(commit=True)

            messages.success(request, _("The filter has been saved"))
            return redirect("list_personal_note_filters")

    context["personal_note_filter_form"] = personal_note_filter_form

    return render(request, "alsijil/manage_personal_note_filter.html", context)


@permission_required("alsijil.delete_personal_note_filter", fn=objectgetter_optional(PersonalNoteFilter, None, False))
def delete_personal_note_filter(request: HttpRequest, id_: int) -> HttpResponse:
    context = {}

    personal_note_filter = get_object_or_404(PersonalNoteFilter, pk=id_)

    PersonalNoteFilter.objects.filter(pk=id_).delete()

    messages.success(request, _("The filter has been deleted."))

    context["personal_note_filter"] = personal_note_filter
    return redirect("list_personal_note_filters")
