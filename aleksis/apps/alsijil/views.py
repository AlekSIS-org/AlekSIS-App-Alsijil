from datetime import date, datetime, timedelta
from typing import Optional

from django.core.exceptions import PermissionDenied
from django.db.models import Count, Exists, F, OuterRef, Q, Subquery, Sum
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.translation import ugettext as _

from calendarweek import CalendarWeek
from django_tables2 import RequestConfig, SingleTableView
from reversion.views import RevisionMixin
from rules.contrib.views import PermissionRequiredMixin

from aleksis.apps.chronos.managers import TimetableType
from aleksis.apps.chronos.models import LessonPeriod, LessonSubstitution
from aleksis.apps.chronos.util.chronos_helpers import get_el_by_pk
from aleksis.core.mixins import AdvancedCreateView, AdvancedDeleteView, AdvancedEditView
from aleksis.core.models import Group, Person, SchoolTerm
from aleksis.core.util import messages

from .forms import (
    ExcuseTypeForm,
    LessonDocumentationForm,
    PersonalNoteFilterForm,
    PersonalNoteFormSet,
    RegisterAbsenceForm,
    SelectForm,
)
from .models import ExcuseType, LessonDocumentation, PersonalNoteFilter
from .tables import ExcuseTypeTable, PersonalNoteFilterTable


def lesson(
    request: HttpRequest,
    year: Optional[int] = None,
    week: Optional[int] = None,
    period_id: Optional[int] = None,
) -> HttpResponse:
    context = {}

    if year and week and period_id:
        # Get a specific lesson period if provided in URL
        wanted_week = CalendarWeek(year=year, week=week)
        lesson_period = LessonPeriod.objects.annotate_week(wanted_week).get(
            pk=period_id
        )
    else:
        # Determine current lesson by current date and time
        lesson_period = (
            LessonPeriod.objects.at_time().filter_teacher(request.user.person).first()
        )
        wanted_week = CalendarWeek()

        if lesson_period:
            return redirect(
                "lesson_by_week_and_period",
                wanted_week.year,
                wanted_week.week,
                lesson_period.pk,
            )
        else:
            raise Http404(
                _(
                    "You either selected an invalid lesson or "
                    "there is currently no lesson in progress."
                )
            )

    if (
        datetime.combine(
            wanted_week[lesson_period.period.weekday], lesson_period.period.time_start,
        )
        > datetime.now()
        and not request.user.is_superuser
    ):
        raise PermissionDenied(
            _(
                "You are not allowed to create a lesson documentation for a lesson in the future."
            )
        )

    context["lesson_period"] = lesson_period
    context["week"] = wanted_week
    context["day"] = wanted_week[lesson_period.period.weekday]

    # Create or get lesson documentation object; can be empty when first opening lesson
    lesson_documentation = lesson_period.get_or_create_lesson_documentation(wanted_week)
    lesson_documentation_form = LessonDocumentationForm(
        request.POST or None,
        instance=lesson_documentation,
        prefix="lesson_documentation",
    )

    # Create a formset that holds all personal notes for all persons in this lesson
    persons_qs = lesson_period.get_personal_notes(wanted_week)
    personal_note_formset = PersonalNoteFormSet(
        request.POST or None, queryset=persons_qs, prefix="personal_notes"
    )

    if request.method == "POST":
        if lesson_documentation_form.is_valid():
            lesson_documentation_form.save()

            messages.success(request, _("The lesson documentation has been saved."))

        substitution = lesson_period.get_substitution()
        if not getattr(substitution, "cancelled", False):
            if personal_note_formset.is_valid():
                instances = personal_note_formset.save()

                # Iterate over personal notes and carry changed absences to following lessons
                for instance in instances:
                    instance.person.mark_absent(
                        wanted_week[lesson_period.period.weekday],
                        lesson_period.period.period + 1,
                        instance.absent,
                        instance.excused,
                        instance.excuse_type,
                    )

            messages.success(request, _("The personal notes have been saved."))

            # Regenerate form here to ensure that programmatically changed data will be shown correctly
            personal_note_formset = PersonalNoteFormSet(
                None, queryset=persons_qs, prefix="personal_notes"
            )

    context["lesson_documentation"] = lesson_documentation
    context["lesson_documentation_form"] = lesson_documentation_form
    context["personal_note_formset"] = personal_note_formset

    return render(request, "alsijil/class_register/lesson.html", context)


def week_view(
    request: HttpRequest,
    year: Optional[int] = None,
    week: Optional[int] = None,
    type_: Optional[str] = None,
    id_: Optional[int] = None,
) -> HttpResponse:
    context = {}

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

    group = None
    if type_ and id_:
        instance = get_el_by_pk(request, type_, id_)

        if isinstance(instance, HttpResponseNotFound):
            return HttpResponseNotFound()

        type_ = TimetableType.from_string(type_)

        if type_ == TimetableType.GROUP:
            group = instance

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
                return redirect(
                    "week_view_by_week",
                    wanted_week.year,
                    wanted_week.week,
                    select_form.cleaned_data["type_"].value,
                    select_form.cleaned_data["instance"].pk,
                )

    if lesson_periods:
        # Aggregate all personal notes for this group and week
        lesson_periods_pk = list(lesson_periods.values_list("pk", flat=True))

        persons_qs = Person.objects.filter(is_active=True)

        if group:
            persons_qs = persons_qs.filter(member_of=group)
        else:
            persons_qs = persons_qs.filter(
                member_of__lessons__lesson_periods__in=lesson_periods_pk
            )

        persons_qs = (
            persons_qs.distinct()
            .prefetch_related("personal_notes")
            .annotate(
                absences_count=Count(
                    "personal_notes",
                    filter=Q(
                        personal_notes__lesson_period__in=lesson_periods_pk,
                        personal_notes__week=wanted_week.week,
                        personal_notes__absent=True,
                    ),
                    distinct=True,
                ),
                unexcused_count=Count(
                    "personal_notes",
                    filter=Q(
                        personal_notes__lesson_period__in=lesson_periods_pk,
                        personal_notes__week=wanted_week.week,
                        personal_notes__absent=True,
                        personal_notes__excused=False,
                    ),
                    distinct=True,
                ),
                tardiness_sum=Subquery(
                    Person.objects.filter(
                        pk=OuterRef("pk"),
                        personal_notes__lesson_period__in=lesson_periods_pk,
                        personal_notes__week=wanted_week.week,
                    )
                    .distinct()
                    .annotate(tardiness_sum=Sum("personal_notes__late"))
                    .values("tardiness_sum")
                ),
            )
        )

        persons = []
        for person in persons_qs:
            persons.append(
                {
                    "person": person,
                    "personal_notes": person.personal_notes.filter(
                        week=wanted_week.week, lesson_period__in=lesson_periods_pk
                    ),
                }
            )
    else:
        persons = None

    # Resort lesson periods manually because an union queryset doesn't support order_by
    lesson_periods = sorted(
        lesson_periods, key=lambda x: (x.period.weekday, x.period.period)
    )

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

    return render(request, "alsijil/class_register/week_view.html", context)


def full_register_group(request: HttpRequest, id_: int) -> HttpResponse:
    context = {}

    group = get_object_or_404(Group, pk=id_)

    # Get all lesson periods for the selected group
    lesson_periods = (
        LessonPeriod.objects.filter_group(group)
        .distinct()
        .prefetch_related("documentations", "personal_notes")
    )

    current_school_term = SchoolTerm.current

    if not current_school_term:
        return HttpResponseNotFound(_("There is no current school term."))

    weeks = CalendarWeek.weeks_within(
        current_school_term.date_start, current_school_term.date_end,
    )

    periods_by_day = {}
    for lesson_period in lesson_periods:
        for week in weeks:
            day = week[lesson_period.period.weekday]

            if (
                lesson_period.lesson.validity.date_start
                <= day
                <= lesson_period.lesson.validity.date_end
            ):
                documentations = list(
                    filter(
                        lambda d: d.week == week.week,
                        lesson_period.documentations.all(),
                    )
                )
                notes = list(
                    filter(
                        lambda d: d.week == week.week,
                        lesson_period.personal_notes.all(),
                    )
                )
                substitution = lesson_period.get_substitution(week.week)

                periods_by_day.setdefault(day, []).append(
                    (lesson_period, documentations, notes, substitution)
                )

    persons = group.members.annotate(
        absences_count=Count(
            "personal_notes__absent",
            filter=Q(personal_notes__absent=True)
            & ~Q(
                personal_notes__lesson_period__substitutions=Subquery(
                    LessonSubstitution.objects.filter(
                        lesson_period__pk=OuterRef("personal_notes__lesson_period__pk"),
                        cancelled=True,
                        week=OuterRef("personal_notes__week"),
                    ).values("pk")
                )
            ),
        ),
        excused=Count(
            "personal_notes__absent",
            filter=Q(
                personal_notes__absent=True,
                personal_notes__excused=True,
                personal_notes__excuse_type__isnull=True,
            ),
        ),
        unexcused=Count(
            "personal_notes__absent",
            filter=Q(personal_notes__absent=True, personal_notes__excused=False),
        ),
        tardiness=Sum("personal_notes__late"),
    )

    for excuse_type in ExcuseType.objects.all():
        persons = persons.annotate(
            **{
                excuse_type.count_label: Count(
                    "personal_notes__absent",
                    filter=Q(
                        personal_notes__absent=True,
                        personal_notes__excuse_type=excuse_type,
                    ),
                )
            }
        )

    # FIXME Move to manager
    personal_note_filters = PersonalNoteFilter.objects.all()
    for personal_note_filter in personal_note_filters:
        persons = persons.annotate(
            **{
                "_personal_notes_with_%s"
                % personal_note_filter.identifier: Count(
                    "personal_notes__remarks",
                    filter=Q(
                        personal_notes__remarks__iregex=personal_note_filter.regex
                    ),
                )
            }
        )

    context["school_term"] = current_school_term
    context["persons"] = persons
    context["personal_note_filters"] = personal_note_filters
    context["excuse_types"] = ExcuseType.objects.all()
    context["group"] = group
    context["weeks"] = weeks
    context["periods_by_day"] = periods_by_day
    context["today"] = date.today()

    return render(request, "alsijil/print/full_register.html", context)


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

    return render(request, "alsijil/absences/register.html", context)


def list_personal_note_filters(request: HttpRequest) -> HttpResponse:
    context = {}

    personal_note_filters = PersonalNoteFilter.objects.all()

    # Prepare table
    personal_note_filters_table = PersonalNoteFilterTable(personal_note_filters)
    RequestConfig(request).configure(personal_note_filters_table)

    context["personal_note_filters_table"] = personal_note_filters_table

    return render(request, "alsijil/personal_note_filter/list.html", context)


def edit_personal_note_filter(
    request: HttpRequest, id_: Optional["int"] = None
) -> HttpResponse:
    context = {}

    if id_:
        personal_note_filter = PersonalNoteFilter.objects.get(id=id_)
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

    return render(request, "alsijil/personal_note_filter/manage.html", context)


def delete_personal_note_filter(request: HttpRequest, id_: int) -> HttpResponse:
    context = {}

    personal_note_filter = get_object_or_404(PersonalNoteFilter, pk=id_)

    PersonalNoteFilter.objects.filter(pk=id_).delete()

    messages.success(request, _("The filter has been deleted."))

    context["personal_note_filter"] = personal_note_filter
    return redirect("list_personal_note_filters")


class ExcuseTypeListView(SingleTableView, PermissionRequiredMixin):
    """Table of all excuse types."""

    model = ExcuseType
    table_class = ExcuseTypeTable
    permission_required = "core.view_excusetype"
    template_name = "alsijil/excuse_type/list.html"


class ExcuseTypeCreateView(AdvancedCreateView, PermissionRequiredMixin):
    """Create view for excuse types."""

    model = ExcuseType
    form_class = ExcuseTypeForm
    permission_required = "core.create_excusetype"
    template_name = "alsijil/excuse_type/create.html"
    success_url = reverse_lazy("excuse_types")
    success_message = _("The excuse type has been created.")


class ExcuseTypeEditView(AdvancedEditView, PermissionRequiredMixin):
    """Edit view for excuse types."""

    model = ExcuseType
    form_class = ExcuseTypeForm
    permission_required = "core.edit_excusetype"
    template_name = "alsijil/excuse_type/edit.html"
    success_url = reverse_lazy("excuse_types")
    success_message = _("The excuse type has been saved.")


class ExcuseTypeDeleteView(AdvancedDeleteView, PermissionRequiredMixin, RevisionMixin):
    """Delete view for excuse types"""

    model = ExcuseType
    permission_required = "core.delete_excusetype"
    template_name = "core/pages/delete.html"
    success_url = reverse_lazy("excuse_types")
    success_message = _("The excuse type has been deleted.")
