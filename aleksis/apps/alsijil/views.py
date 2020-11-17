from datetime import date, datetime, timedelta
from typing import Optional

from django.core.exceptions import PermissionDenied
from django.db.models import Count, Exists, OuterRef, Prefetch, Q, Subquery, Sum
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.translation import ugettext as _
from django.views.generic import DetailView

import reversion
from calendarweek import CalendarWeek
from django_tables2 import SingleTableView
from reversion.views import RevisionMixin
from rules.contrib.views import PermissionRequiredMixin, permission_required

from aleksis.apps.chronos.managers import TimetableType
from aleksis.apps.chronos.models import LessonPeriod, TimePeriod
from aleksis.apps.chronos.util.date import get_weeks_for_year, week_weekday_to_date
from aleksis.core.mixins import AdvancedCreateView, AdvancedDeleteView, AdvancedEditView
from aleksis.core.models import Group, Person, SchoolTerm
from aleksis.core.util import messages
from aleksis.core.util.core_helpers import get_site_preferences, objectgetter_optional

from .forms import (
    ExcuseTypeForm,
    ExtraMarkForm,
    LessonDocumentationForm,
    PersonalNoteFormSet,
    RegisterAbsenceForm,
    SelectForm,
)
from .models import ExcuseType, ExtraMark, LessonDocumentation, PersonalNote
from .tables import ExcuseTypeTable, ExtraMarkTable
from .util.alsijil_helpers import get_lesson_period_by_pk, get_timetable_instance_by_pk


@permission_required("alsijil.view_lesson", fn=get_lesson_period_by_pk)
def lesson(
    request: HttpRequest,
    year: Optional[int] = None,
    week: Optional[int] = None,
    period_id: Optional[int] = None,
) -> HttpResponse:
    context = {}

    lesson_period = get_lesson_period_by_pk(request, year, week, period_id)

    if period_id:
        wanted_week = CalendarWeek(year=year, week=week)
    elif hasattr(request, "user") and hasattr(request.user, "person"):
        wanted_week = CalendarWeek()
    else:
        wanted_week = None

    if not all((year, week, period_id)):
        if lesson_period:
            return redirect(
                "lesson_by_week_and_period", wanted_week.year, wanted_week.week, lesson_period.pk,
            )
        else:
            raise Http404(
                _(
                    "You either selected an invalid lesson or "
                    "there is currently no lesson in progress."
                )
            )

    date_of_lesson = week_weekday_to_date(wanted_week, lesson_period.period.weekday)

    if (
        date_of_lesson < lesson_period.lesson.validity.date_start
        or date_of_lesson > lesson_period.lesson.validity.date_end
    ):
        return HttpResponseNotFound()

    if (
        datetime.combine(
            wanted_week[lesson_period.period.weekday], lesson_period.period.time_start,
        )
        > datetime.now()
        and not (
            get_site_preferences()["alsijil__open_periods_same_day"]
            and wanted_week[lesson_period.period.weekday] <= datetime.now().date()
        )
        and not request.user.is_superuser
    ):
        raise PermissionDenied(
            _("You are not allowed to create a lesson documentation for a lesson in the future.")
        )

    next_lesson = request.user.person.next_lesson(lesson_period, date_of_lesson)
    prev_lesson = request.user.person.previous_lesson(lesson_period, date_of_lesson)

    context["lesson_period"] = lesson_period
    context["week"] = wanted_week
    context["day"] = wanted_week[lesson_period.period.weekday]
    context["next_lesson_person"] = next_lesson
    context["prev_lesson_person"] = prev_lesson

    # Create or get lesson documentation object; can be empty when first opening lesson
    lesson_documentation = lesson_period.get_or_create_lesson_documentation(wanted_week)
    lesson_documentation_form = LessonDocumentationForm(
        request.POST or None, instance=lesson_documentation, prefix="lesson_documentation",
    )

    # Create a formset that holds all personal notes for all persons in this lesson
    if not request.user.has_perm("alsijil.view_lesson_personalnote", lesson_period):
        persons = Person.objects.filter(pk=request.user.person.pk)
    else:
        persons = Person.objects.all()

    persons_qs = lesson_period.get_personal_notes(persons, wanted_week)
    personal_note_formset = PersonalNoteFormSet(
        request.POST or None, queryset=persons_qs, prefix="personal_notes"
    )

    if request.method == "POST":
        if lesson_documentation_form.is_valid() and request.user.has_perm(
            "alsijil.edit_lessondocumentation", lesson_period
        ):
            lesson_documentation_form.save()

            messages.success(request, _("The lesson documentation has been saved."))

        substitution = lesson_period.get_substitution()
        if (
            not getattr(substitution, "cancelled", False)
            or not get_site_preferences()["alsijil__block_personal_notes_for_cancelled"]
        ):
            if personal_note_formset.is_valid() and request.user.has_perm(
                "alsijil.edit_lesson_personalnote", lesson_period
            ):
                with reversion.create_revision():
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

            # Regenerate form here to ensure that programmatically
            # changed data will be shown correctly
            personal_note_formset = PersonalNoteFormSet(
                None, queryset=persons_qs, prefix="personal_notes"
            )

    context["lesson_documentation"] = lesson_documentation
    context["lesson_documentation_form"] = lesson_documentation_form
    context["personal_note_formset"] = personal_note_formset
    context["prev_lesson"] = lesson_period.prev
    context["next_lesson"] = lesson_period.next

    return render(request, "alsijil/class_register/lesson.html", context)


@permission_required("alsijil.view_week", fn=get_timetable_instance_by_pk)
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

    instance = get_timetable_instance_by_pk(request, year, week, type_, id_)

    lesson_periods = LessonPeriod.objects.in_week(wanted_week).prefetch_related(
        "lesson__groups__members",
        "lesson__groups__parent_groups",
        "lesson__groups__parent_groups__owners",
    )

    lesson_periods_query_exists = True
    if type_ and id_:
        if isinstance(instance, HttpResponseNotFound):
            return HttpResponseNotFound()

        type_ = TimetableType.from_string(type_)

        lesson_periods = lesson_periods.filter_from_type(type_, instance)
    elif hasattr(request, "user") and hasattr(request.user, "person"):
        if request.user.person.lessons_as_teacher.exists():
            lesson_periods = lesson_periods.filter_teacher(request.user.person)
            type_ = TimetableType.TEACHER
        else:
            lesson_periods = lesson_periods.filter_participant(request.user.person)
    else:
        lesson_periods_query_exists = False
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

    if type_ == TimetableType.GROUP:
        group = instance
    else:
        group = None

    extra_marks = ExtraMark.objects.all()

    if lesson_periods_query_exists:
        lesson_periods_pk = list(lesson_periods.values_list("pk", flat=True))
        lesson_periods = (
            LessonPeriod.objects.prefetch_related(
                Prefetch(
                    "documentations",
                    queryset=LessonDocumentation.objects.filter(
                        week=wanted_week.week, year=wanted_week.year
                    ),
                )
            )
            .filter(pk__in=lesson_periods_pk)
            .annotate_week(wanted_week)
            .annotate(
                has_documentation=Exists(
                    LessonDocumentation.objects.filter(
                        ~Q(topic__exact=""),
                        lesson_period=OuterRef("pk"),
                        week=wanted_week.week,
                        year=wanted_week.year,
                    )
                )
            )
            .order_by("period__weekday", "period__period")
        )
    else:
        lesson_periods_pk = []

    if lesson_periods_pk:
        # Aggregate all personal notes for this group and week
        persons_qs = Person.objects.filter(is_active=True)

        if not request.user.has_perm("alsijil.view_week_personalnote", instance):
            persons_qs = persons_qs.filter(pk=request.user.person.pk)
        elif group:
            persons_qs = persons_qs.filter(member_of=group)
        else:
            persons_qs = persons_qs.filter(member_of__lessons__lesson_periods__in=lesson_periods_pk)

        persons_qs = (
            persons_qs.distinct()
            .prefetch_related(
                Prefetch(
                    "personal_notes",
                    queryset=PersonalNote.objects.filter(
                        week=wanted_week.week,
                        year=wanted_week.year,
                        lesson_period__in=lesson_periods_pk,
                    ),
                ),
                "member_of__owners",
            )
            .annotate(
                absences_count=Count(
                    "personal_notes",
                    filter=Q(
                        personal_notes__lesson_period__in=lesson_periods_pk,
                        personal_notes__week=wanted_week.week,
                        personal_notes__year=wanted_week.year,
                        personal_notes__absent=True,
                    ),
                    distinct=True,
                ),
                unexcused_count=Count(
                    "personal_notes",
                    filter=Q(
                        personal_notes__lesson_period__in=lesson_periods_pk,
                        personal_notes__week=wanted_week.week,
                        personal_notes__year=wanted_week.year,
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
                        personal_notes__year=wanted_week.year,
                    )
                    .distinct()
                    .annotate(tardiness_sum=Sum("personal_notes__late"))
                    .values("tardiness_sum")
                ),
                tardiness_count=Count(
                    "personal_notes",
                    filter=Q(
                        personal_notes__lesson_period__in=lesson_periods_pk,
                        personal_notes__week=wanted_week.week,
                        personal_notes__year=wanted_week.year,
                    )
                    & ~Q(personal_notes__late=0),
                    distinct=True,
                ),
            )
        )

        for extra_mark in extra_marks:
            persons_qs = persons_qs.annotate(
                **{
                    extra_mark.count_label: Count(
                        "personal_notes",
                        filter=Q(
                            personal_notes__lesson_period__in=lesson_periods_pk,
                            personal_notes__week=wanted_week.week,
                            personal_notes__year=wanted_week.year,
                            personal_notes__extra_marks=extra_mark,
                        ),
                        distinct=True,
                    )
                }
            )

        persons = []
        for person in persons_qs:
            persons.append({"person": person, "personal_notes": list(person.personal_notes.all())})
    else:
        persons = None

    context["extra_marks"] = extra_marks
    context["week"] = wanted_week
    context["weeks"] = get_weeks_for_year(year=wanted_week.year)
    context["lesson_periods"] = lesson_periods
    context["persons"] = persons
    context["group"] = group
    context["select_form"] = select_form
    context["instance"] = instance

    week_prev = wanted_week - 1
    week_next = wanted_week + 1
    args_prev = [week_prev.year, week_prev.week]
    args_next = [week_next.year, week_next.week]
    args_dest = []
    if type_ and id_:
        args_prev += [type_.value, id_]
        args_next += [type_.value, id_]
        args_dest += [type_.value, id_]

    context["week_select"] = {
        "year": wanted_week.year,
        "dest": reverse("week_view_placeholders", args=args_dest),
    }

    context["url_prev"] = reverse("week_view_by_week", args=args_prev)
    context["url_next"] = reverse("week_view_by_week", args=args_next)

    return render(request, "alsijil/class_register/week_view.html", context)


@permission_required("alsijil.view_full_register", fn=objectgetter_optional(Group, None, False))
def full_register_group(request: HttpRequest, id_: int) -> HttpResponse:
    context = {}

    group = get_object_or_404(Group, pk=id_)

    # Get all lesson periods for the selected group
    lesson_periods = (
        LessonPeriod.objects.filter_group(group)
        .distinct()
        .prefetch_related(
            "documentations",
            "personal_notes",
            "personal_notes__excuse_type",
            "personal_notes__extra_marks",
            "personal_notes__person",
            "personal_notes__groups_of_person",
        )
    )

    weeks = CalendarWeek.weeks_within(group.school_term.date_start, group.school_term.date_end,)

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
                        lambda d: d.week == week.week and d.year == week.year,
                        lesson_period.documentations.all(),
                    )
                )
                notes = list(
                    filter(
                        lambda d: d.week == week.week and d.year == week.year,
                        lesson_period.personal_notes.all(),
                    )
                )
                substitution = lesson_period.get_substitution(week)

                periods_by_day.setdefault(day, []).append(
                    (lesson_period, documentations, notes, substitution)
                )

    persons = Person.objects.prefetch_related(
        "personal_notes",
        "personal_notes__excuse_type",
        "personal_notes__extra_marks",
        "personal_notes__lesson_period__lesson__subject",
        "personal_notes__lesson_period__substitutions",
        "personal_notes__lesson_period__substitutions__subject",
        "personal_notes__lesson_period__substitutions__teachers",
        "personal_notes__lesson_period__lesson__teachers",
        "personal_notes__lesson_period__period",
    )
    persons = group.generate_person_list_with_class_register_statistics(persons)

    context["school_term"] = group.school_term
    context["persons"] = persons
    context["excuse_types"] = ExcuseType.objects.all()
    context["extra_marks"] = ExtraMark.objects.all()
    context["group"] = group
    context["weeks"] = weeks
    context["periods_by_day"] = periods_by_day
    context["lesson_periods"] = lesson_periods
    context["today"] = date.today()
    context["lessons"] = (
        group.lessons.all()
        .select_related("validity", "subject")
        .prefetch_related("teachers", "lesson_periods")
    )
    context["child_groups"] = group.child_groups.all().prefetch_related(
        "lessons",
        "lessons__validity",
        "lessons__subject",
        "lessons__teachers",
        "lessons__lesson_periods",
    )
    return render(request, "alsijil/print/full_register.html", context)


@permission_required("alsijil.view_my_students")
def my_students(request: HttpRequest) -> HttpResponse:
    context = {}
    relevant_groups = (
        request.user.person.get_owner_groups_with_lessons()
        .annotate(has_parents=Exists(Group.objects.filter(child_groups=OuterRef("pk"))))
        .filter(members__isnull=False)
        .order_by("has_parents", "name")
        .prefetch_related("members")
        .distinct()
    )

    new_groups = []
    for group in relevant_groups:
        persons = group.generate_person_list_with_class_register_statistics()
        new_groups.append((group, persons))

    context["groups"] = new_groups
    context["excuse_types"] = ExcuseType.objects.all()
    context["extra_marks"] = ExtraMark.objects.all()
    return render(request, "alsijil/class_register/persons.html", context)


@permission_required("alsijil.view_my_groups",)
def my_groups(request: HttpRequest) -> HttpResponse:
    context = {}
    context["groups"] = request.user.person.get_owner_groups_with_lessons().annotate(
        students_count=Count("members")
    )
    return render(request, "alsijil/class_register/groups.html", context)


class StudentsList(PermissionRequiredMixin, DetailView):
    model = Group
    template_name = "alsijil/class_register/students_list.html"
    permission_required = "alsijil.view_students_list"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["group"] = self.object
        context["persons"] = self.object.generate_person_list_with_class_register_statistics()
        context["extra_marks"] = ExtraMark.objects.all()
        context["excuse_types"] = ExcuseType.objects.all()
        return context


@permission_required(
    "alsijil.view_person_overview", fn=objectgetter_optional(Person, "request.user.person", True),
)
def overview_person(request: HttpRequest, id_: Optional[int] = None) -> HttpResponse:
    context = {}
    person = objectgetter_optional(Person, default="request.user.person", default_eval=True)(
        request, id_
    )
    context["person"] = person

    if request.method == "POST":
        if request.POST.get("excuse_type"):
            # Get excuse type
            excuse_type = request.POST["excuse_type"]
            found = False
            if excuse_type == "e":
                excuse_type = None
                found = True
            else:
                try:
                    excuse_type = ExcuseType.objects.get(pk=int(excuse_type))
                    found = True
                except (ExcuseType.DoesNotExist, ValueError):
                    pass

            if found:
                if request.POST.get("date"):
                    # Mark absences on date as excused
                    try:
                        date = datetime.strptime(request.POST["date"], "%Y-%m-%d").date()

                        if not request.user.has_perm(
                            "alsijil.edit_person_overview_personalnote", person
                        ):
                            raise PermissionDenied()

                        notes = person.personal_notes.filter(
                            week=date.isocalendar()[1],
                            lesson_period__period__weekday=date.weekday(),
                            lesson_period__lesson__validity__date_start__lte=date,
                            lesson_period__lesson__validity__date_end__gte=date,
                            absent=True,
                            excused=False,
                        )
                        for note in notes:
                            note.excused = True
                            note.excuse_type = excuse_type
                            with reversion.create_revision():
                                note.save()

                        messages.success(request, _("The absences have been marked as excused."))
                    except ValueError:
                        pass
                elif request.POST.get("personal_note"):
                    # Mark specific absence as excused
                    try:
                        note = PersonalNote.objects.get(pk=int(request.POST["personal_note"]))
                        if not request.user.has_perm("alsijil.edit_personalnote", note):
                            raise PermissionDenied()
                        if note.absent:
                            note.excused = True
                            note.excuse_type = excuse_type
                            with reversion.create_revision():
                                note.save()
                            messages.success(request, _("The absence has been marked as excused."))
                    except (PersonalNote.DoesNotExist, ValueError):
                        pass

                person.refresh_from_db()

    person_personal_notes = person.personal_notes.all().prefetch_related(
        "lesson_period__lesson__groups",
        "lesson_period__lesson__teachers",
        "lesson_period__substitutions",
    )

    if request.user.has_perm("alsijil.view_person_overview_personalnote", person):
        allowed_personal_notes = person_personal_notes.all()
    else:
        allowed_personal_notes = person_personal_notes.filter(
            lesson_period__lesson__groups__owners=request.user.person
        )

    unexcused_absences = allowed_personal_notes.filter(absent=True, excused=False)
    context["unexcused_absences"] = unexcused_absences

    personal_notes = allowed_personal_notes.filter(
        Q(absent=True) | Q(late__gt=0) | ~Q(remarks="") | Q(extra_marks__isnull=False)
    ).order_by(
        "-lesson_period__lesson__validity__date_start",
        "-week",
        "lesson_period__period__weekday",
        "lesson_period__period__period",
    )
    context["personal_notes"] = personal_notes
    context["excuse_types"] = ExcuseType.objects.all()

    extra_marks = ExtraMark.objects.all()
    excuse_types = ExcuseType.objects.all()
    if request.user.has_perm("alsijil.view_person_statistics_personalnote", person):
        school_terms = SchoolTerm.objects.all().order_by("-date_start")
        stats = []
        for school_term in school_terms:
            stat = {}
            personal_notes = PersonalNote.objects.filter(
                person=person, lesson_period__lesson__validity__school_term=school_term
            )

            if not personal_notes.exists():
                continue

            stat.update(
                personal_notes.filter(absent=True).aggregate(absences_count=Count("absent"))
            )
            stat.update(
                personal_notes.filter(
                    absent=True, excused=True, excuse_type__isnull=True
                ).aggregate(excused=Count("absent"))
            )
            stat.update(
                personal_notes.filter(absent=True, excused=False).aggregate(
                    unexcused=Count("absent")
                )
            )
            stat.update(personal_notes.aggregate(tardiness=Sum("late")))
            stat.update(personal_notes.filter(~Q(late=0)).aggregate(tardiness_count=Count("late")))

            for extra_mark in extra_marks:
                stat.update(
                    personal_notes.filter(extra_marks=extra_mark).aggregate(
                        **{extra_mark.count_label: Count("pk")}
                    )
                )

            for excuse_type in excuse_types:
                stat.update(
                    personal_notes.filter(absent=True, excuse_type=excuse_type).aggregate(
                        **{excuse_type.count_label: Count("absent")}
                    )
                )

            stats.append((school_term, stat))
        context["stats"] = stats

    context["excuse_types"] = excuse_types
    context["extra_marks"] = extra_marks

    return render(request, "alsijil/class_register/person.html", context)


@permission_required("alsijil.register_absence", fn=objectgetter_optional(Person))
def register_absence(request: HttpRequest, id_: int) -> HttpResponse:
    context = {}

    person = get_object_or_404(Person, pk=id_)

    register_absence_form = RegisterAbsenceForm(request.POST or None)

    if request.method == "POST" and register_absence_form.is_valid():
        # Get data from form
        # person = register_absence_form.cleaned_data["person"]
        start_date = register_absence_form.cleaned_data["date_start"]
        end_date = register_absence_form.cleaned_data["date_end"]
        from_period = register_absence_form.cleaned_data["from_period"]
        to_period = register_absence_form.cleaned_data["to_period"]
        absent = register_absence_form.cleaned_data["absent"]
        excused = register_absence_form.cleaned_data["excused"]
        excuse_type = register_absence_form.cleaned_data["excuse_type"]
        remarks = register_absence_form.cleaned_data["remarks"]

        # Mark person as absent
        delta = end_date - start_date
        for i in range(delta.days + 1):
            from_period_on_day = from_period if i == 0 else TimePeriod.period_min
            to_period_on_day = to_period if i == delta.days else TimePeriod.period_max
            day = start_date + timedelta(days=i)

            person.mark_absent(
                day, from_period_on_day, absent, excused, excuse_type, remarks, to_period_on_day,
            )

        messages.success(request, _("The absence has been saved."))
        return redirect("overview_person", person.pk)

    context["person"] = person
    context["register_absence_form"] = register_absence_form

    return render(request, "alsijil/absences/register.html", context)


class DeletePersonalNoteView(PermissionRequiredMixin, DetailView):
    model = PersonalNote
    template_name = "core/pages/delete.html"
    permission_required = "alsijil.edit_personalnote"

    def post(self, request, *args, **kwargs):
        note = self.get_object()
        with reversion.create_revision():
            note.reset_values()
            note.save()
        messages.success(request, _("The personal note has been deleted."))
        return redirect("overview_person", note.person.pk)


class ExtraMarkListView(PermissionRequiredMixin, SingleTableView):
    """Table of all extra marks."""

    model = ExtraMark
    table_class = ExtraMarkTable
    permission_required = "alsijil.view_extramark"
    template_name = "alsijil/extra_mark/list.html"


class ExtraMarkCreateView(PermissionRequiredMixin, AdvancedCreateView):
    """Create view for extra marks."""

    model = ExtraMark
    form_class = ExtraMarkForm
    permission_required = "alsijil.create_extramark"
    template_name = "alsijil/extra_mark/create.html"
    success_url = reverse_lazy("extra_marks")
    success_message = _("The extra mark has been created.")


class ExtraMarkEditView(PermissionRequiredMixin, AdvancedEditView):
    """Edit view for extra marks."""

    model = ExtraMark
    form_class = ExtraMarkForm
    permission_required = "alsijil.edit_extramark"
    template_name = "alsijil/extra_mark/edit.html"
    success_url = reverse_lazy("extra_marks")
    success_message = _("The extra mark has been saved.")


class ExtraMarkDeleteView(PermissionRequiredMixin, RevisionMixin, AdvancedDeleteView):
    """Delete view for extra marks."""

    model = ExtraMark
    permission_required = "alsijil.delete_extramark"
    template_name = "core/pages/delete.html"
    success_url = reverse_lazy("extra_marks")
    success_message = _("The extra mark has been deleted.")


class ExcuseTypeListView(PermissionRequiredMixin, SingleTableView):
    """Table of all excuse types."""

    model = ExcuseType
    table_class = ExcuseTypeTable
    permission_required = "alsijil.view_excusetypes"
    template_name = "alsijil/excuse_type/list.html"


class ExcuseTypeCreateView(PermissionRequiredMixin, AdvancedCreateView):
    """Create view for excuse types."""

    model = ExcuseType
    form_class = ExcuseTypeForm
    permission_required = "alsijil.add_excusetype"
    template_name = "alsijil/excuse_type/create.html"
    success_url = reverse_lazy("excuse_types")
    success_message = _("The excuse type has been created.")


class ExcuseTypeEditView(PermissionRequiredMixin, AdvancedEditView):
    """Edit view for excuse types."""

    model = ExcuseType
    form_class = ExcuseTypeForm
    permission_required = "alsijil.edit_excusetype"
    template_name = "alsijil/excuse_type/edit.html"
    success_url = reverse_lazy("excuse_types")
    success_message = _("The excuse type has been saved.")


class ExcuseTypeDeleteView(PermissionRequiredMixin, RevisionMixin, AdvancedDeleteView):
    """Delete view for excuse types."""

    model = ExcuseType
    permission_required = "alsijil.delete_excusetype"
    template_name = "core/pages/delete.html"
    success_url = reverse_lazy("excuse_types")
    success_message = _("The excuse type has been deleted.")
