from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Optional

from django.core.exceptions import PermissionDenied
from django.db.models import Count, Exists, OuterRef, Prefetch, Q, Subquery, Sum
from django.db.models.expressions import Case, When
from django.db.models.functions import Extract
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from django.views.decorators.cache import never_cache
from django.views.generic import DetailView

import reversion
from calendarweek import CalendarWeek
from django_tables2 import SingleTableView
from reversion.views import RevisionMixin
from rules.contrib.views import PermissionRequiredMixin, permission_required

from aleksis.apps.chronos.managers import TimetableType
from aleksis.apps.chronos.models import Event, ExtraLesson, Holiday, LessonPeriod, TimePeriod
from aleksis.apps.chronos.util.build import build_weekdays
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
from .models import ExcuseType, ExtraMark, PersonalNote
from .tables import ExcuseTypeTable, ExtraMarkTable
from .util.alsijil_helpers import (
    annotate_documentations,
    get_register_object_by_pk,
    get_timetable_instance_by_pk,
    register_objects_sorter,
)


@permission_required("alsijil.view_register_object", fn=get_register_object_by_pk)  # FIXME
def register_object(
    request: HttpRequest,
    model: Optional[str] = None,
    year: Optional[int] = None,
    week: Optional[int] = None,
    id_: Optional[int] = None,
) -> HttpResponse:
    context = {}

    register_object = get_register_object_by_pk(request, model, year, week, id_)

    if id_ and model == "lesson":
        wanted_week = CalendarWeek(year=year, week=week)
    elif id_ and model == "extra_lesson":
        wanted_week = register_object.calendar_week
    elif hasattr(request, "user") and hasattr(request.user, "person"):
        wanted_week = CalendarWeek()
    else:
        wanted_week = None

    if not all((year, week, id_)):
        if register_object and model == "lesson":
            return redirect("lesson", wanted_week.year, wanted_week.week, register_object.pk,)
        elif not register_object:
            raise Http404(
                _(
                    "You either selected an invalid lesson or "
                    "there is currently no lesson in progress."
                )
            )

    date_of_lesson = (
        week_weekday_to_date(wanted_week, register_object.period.weekday)
        if not isinstance(register_object, Event)
        else register_object.date_start
    )
    start_time = (
        register_object.period.time_start
        if not isinstance(register_object, Event)
        else register_object.period_from.time_start
    )

    if isinstance(register_object, Event):
        register_object.annotate_day(date_of_lesson)
    if isinstance(register_object, LessonPeriod) and (
        date_of_lesson < register_object.lesson.validity.date_start
        or date_of_lesson > register_object.lesson.validity.date_end
    ):
        return HttpResponseNotFound()

    if (
        datetime.combine(date_of_lesson, start_time) > datetime.now()
        and not (
            get_site_preferences()["alsijil__open_periods_same_day"]
            and date_of_lesson <= datetime.now().date()
        )
        and not request.user.is_superuser
    ):
        raise PermissionDenied(
            _("You are not allowed to create a lesson documentation for a lesson in the future.")
        )

    holiday = Holiday.on_day(date_of_lesson)
    blocked_because_holidays = (
        holiday is not None and not get_site_preferences()["alsijil__allow_entries_in_holidays"]
    )
    context["blocked_because_holidays"] = blocked_because_holidays
    context["holiday"] = holiday

    next_lesson = (
        request.user.person.next_lesson(register_object, date_of_lesson)
        if isinstance(register_object, LessonPeriod)
        else None
    )
    prev_lesson = (
        request.user.person.previous_lesson(register_object, date_of_lesson)
        if isinstance(register_object, LessonPeriod)
        else None
    )

    context["register_object"] = register_object
    context["week"] = wanted_week
    context["day"] = date_of_lesson
    context["next_lesson_person"] = next_lesson
    context["prev_lesson_person"] = prev_lesson
    context["prev_lesson"] = (
        register_object.prev if isinstance(register_object, LessonPeriod) else None
    )
    context["next_lesson"] = (
        register_object.next if isinstance(register_object, LessonPeriod) else None
    )

    if not blocked_because_holidays:

        # Create or get lesson documentation object; can be empty when first opening lesson
        lesson_documentation = register_object.get_or_create_lesson_documentation(wanted_week)
        lesson_documentation_form = LessonDocumentationForm(
            request.POST or None, instance=lesson_documentation, prefix="lesson_documentation",
        )

        # Create a formset that holds all personal notes for all persons in this lesson
        if not request.user.has_perm("alsijil.view_register_object_personalnote", register_object):
            persons = Person.objects.filter(pk=request.user.person.pk)
        else:
            persons = Person.objects.all()

        persons_qs = register_object.get_personal_notes(persons, wanted_week)
        personal_note_formset = PersonalNoteFormSet(
            request.POST or None, queryset=persons_qs, prefix="personal_notes"
        )

        if request.method == "POST":
            if lesson_documentation_form.is_valid() and request.user.has_perm(
                "alsijil.edit_lessondocumentation", register_object
            ):
                with reversion.create_revision():
                    reversion.set_user(request.user)
                    lesson_documentation_form.save()

                messages.success(request, _("The lesson documentation has been saved."))

            substitution = (
                register_object.get_substitution()
                if isinstance(register_object, LessonPeriod)
                else None
            )
            if (
                not getattr(substitution, "cancelled", False)
                or not get_site_preferences()["alsijil__block_personal_notes_for_cancelled"]
            ):
                if personal_note_formset.is_valid() and request.user.has_perm(
                    "alsijil.edit_register_object_personalnote", register_object
                ):
                    with reversion.create_revision():
                        reversion.set_user(request.user)
                        instances = personal_note_formset.save()

                    if not isinstance(register_object, Event):
                        # Iterate over personal notes
                        # and carry changed absences to following lessons
                        for instance in instances:
                            instance.person.mark_absent(
                                wanted_week[register_object.period.weekday],
                                register_object.period.period + 1,
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
    events = Event.objects.in_week(wanted_week)
    extra_lessons = ExtraLesson.objects.in_week(wanted_week)

    query_exists = True
    if type_ and id_:
        if isinstance(instance, HttpResponseNotFound):
            return HttpResponseNotFound()

        type_ = TimetableType.from_string(type_)

        lesson_periods = lesson_periods.filter_from_type(type_, instance)
        events = events.filter_from_type(type_, instance)
        extra_lessons = extra_lessons.filter_from_Type(type_, instance)

    elif hasattr(request, "user") and hasattr(request.user, "person"):
        if request.user.person.lessons_as_teacher.exists():
            lesson_periods = lesson_periods.filter_teacher(request.user.person)
            events = events.filter_teacher(request.user.person)
            extra_lessons = extra_lessons.filter_teacher(request.user.person)

            type_ = TimetableType.TEACHER
        else:
            lesson_periods = lesson_periods.filter_participant(request.user.person)
            events = events.filter_participant(request.user.person)
            extra_lessons = extra_lessons.filter_participant(request.user.person)

    else:
        query_exists = False
        lesson_periods = None
        events = None
        extra_lessons = None

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

    if query_exists:
        lesson_periods_pk = list(lesson_periods.values_list("pk", flat=True))
        lesson_periods = annotate_documentations(LessonPeriod, wanted_week, lesson_periods_pk)

        events_pk = list(events.values_list("pk", flat=True))
        events = annotate_documentations(Event, wanted_week, events_pk)

        extra_lessons_pk = list(extra_lessons.values_list("pk", flat=True))
        extra_lessons = annotate_documentations(ExtraLesson, wanted_week, extra_lessons_pk)
    else:
        lesson_periods_pk = []
        events_pk = []
        extra_lessons_pk = []

    if lesson_periods_pk or events_pk or extra_lessons_pk:
        # Aggregate all personal notes for this group and week
        persons_qs = Person.objects.filter(is_active=True)

        if not request.user.has_perm("alsijil.view_week_personalnote", instance):
            persons_qs = persons_qs.filter(pk=request.user.person.pk)
        elif group:
            persons_qs = persons_qs.filter(member_of=group)
        else:
            persons_qs = persons_qs.filter(
                Q(member_of__lessons__lesson_periods__in=lesson_periods_pk)
                | Q(member_of__events__in=events_pk)
                | Q(member_of__extra_lessons__in=extra_lessons_pk)
            )

        personal_notes_q = (
            Q(
                personal_notes__week=wanted_week.week,
                personal_notes__year=wanted_week.year,
                personal_notes__lesson_period__in=lesson_periods_pk,
            )
            | Q(
                personal_notes__event__date_start__lte=wanted_week[6],
                personal_notes__event__date_end__gte=wanted_week[0],
                personal_notes__event__in=events_pk,
            )
            | Q(
                personal_notes__extra_lesson__week=wanted_week.week,
                personal_notes__extra_lesson__year=wanted_week.year,
                personal_notes__extra_lesson__in=extra_lessons_pk,
            )
        )

        persons_qs = (
            persons_qs.distinct()
            .prefetch_related(
                Prefetch(
                    "personal_notes",
                    queryset=PersonalNote.objects.filter(
                        Q(
                            week=wanted_week.week,
                            year=wanted_week.year,
                            lesson_period__in=lesson_periods_pk,
                        )
                        | Q(
                            event__date_start__lte=wanted_week[6],
                            event__date_end__gte=wanted_week[0],
                            event__in=events_pk,
                        )
                        | Q(
                            extra_lesson__week=wanted_week.week,
                            extra_lesson__year=wanted_week.year,
                            extra_lesson__in=extra_lessons_pk,
                        )
                    ),
                ),
                "member_of__owners",
            )
            .annotate(
                absences_count=Count(
                    "personal_notes",
                    filter=personal_notes_q & Q(personal_notes__absent=True,),
                    distinct=True,
                ),
                unexcused_count=Count(
                    "personal_notes",
                    filter=personal_notes_q
                    & Q(personal_notes__absent=True, personal_notes__excused=False,),
                    distinct=True,
                ),
                tardiness_sum=Subquery(
                    Person.objects.filter(personal_notes_q)
                    .filter(pk=OuterRef("pk"),)
                    .distinct()
                    .annotate(tardiness_sum=Sum("personal_notes__late"))
                    .values("tardiness_sum")
                ),
                tardiness_count=Count(
                    "personal_notes",
                    filter=personal_notes_q & ~Q(personal_notes__late=0),
                    distinct=True,
                ),
            )
        )

        for extra_mark in extra_marks:
            persons_qs = persons_qs.annotate(
                **{
                    extra_mark.count_label: Count(
                        "personal_notes",
                        filter=personal_notes_q & Q(personal_notes__extra_marks=extra_mark,),
                        distinct=True,
                    )
                }
            )

        persons = []
        for person in persons_qs:
            personal_notes = []
            for note in person.personal_notes.all():
                if note.lesson_period:
                    note.lesson_period.annotate_week(wanted_week)
                personal_notes.append(note)
            persons.append({"person": person, "personal_notes": personal_notes})
    else:
        persons = None

    context["extra_marks"] = extra_marks
    context["week"] = wanted_week
    context["weeks"] = get_weeks_for_year(year=wanted_week.year)

    context["lesson_periods"] = lesson_periods
    context["events"] = events
    context["extra_lessons"] = extra_lessons

    context["persons"] = persons
    context["group"] = group
    context["select_form"] = select_form
    context["instance"] = instance
    context["weekdays"] = build_weekdays(TimePeriod.WEEKDAY_CHOICES, wanted_week)

    regrouped_objects = {}

    for register_object in list(lesson_periods) + list(extra_lessons):
        regrouped_objects.setdefault(register_object.period.weekday, [])
        regrouped_objects[register_object.period.weekday].append(register_object)

    for event in events:
        weekday_from = event.get_start_weekday(wanted_week)
        weekday_to = event.get_end_weekday(wanted_week)
        print(weekday_from, weekday_to)

        for weekday in range(weekday_from, weekday_to + 1):
            # Make a copy in order to keep the annotation only on this weekday
            event_copy = deepcopy(event)
            event_copy.annotate_day(wanted_week[weekday])

            regrouped_objects.setdefault(weekday, [])
            regrouped_objects[weekday].append(event_copy)

    # Sort register objects
    for weekday in regrouped_objects.keys():
        to_sort = regrouped_objects[weekday]
        regrouped_objects[weekday] = sorted(to_sort, key=register_objects_sorter)
    context["regrouped_objects"] = regrouped_objects

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
    events = (
        Event.objects.filter_group(group)
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
    extra_lessons = (
        ExtraLesson.objects.filter_group(group)
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
    weeks = CalendarWeek.weeks_within(group.school_term.date_start, group.school_term.date_end)

    register_objects_by_day = {}
    for extra_lesson in extra_lessons:
        day = extra_lesson.date
        register_objects_by_day.setdefault(day, []).append(
            (
                extra_lesson,
                list(extra_lesson.documentations.all()),
                list(extra_lesson.personal_notes.all()),
                None,
            )
        )

    for event in events:
        day_number = (event.date_end - event.date_start).days + 1
        for i in range(day_number):
            day = event.date_start + timedelta(days=i)
            event_copy = deepcopy(event)
            event_copy.annotate_day(day)
            register_objects_by_day.setdefault(day, []).append(
                (
                    event_copy,
                    list(event_copy.documentations.all()),
                    list(event_copy.personal_notes.all()),
                    None,
                )
            )

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

                register_objects_by_day.setdefault(day, []).append(
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
    context["register_objects_by_day"] = register_objects_by_day
    context["register_objects"] = list(lesson_periods) + list(events) + list(extra_lessons)
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
        students_count=Count("members", distinct=True)
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

                        notes = person.personal_notes.filter(absent=True, excused=False,).filter(
                            Q(
                                week=date.isocalendar()[1],
                                lesson_period__period__weekday=date.weekday(),
                                lesson_period__lesson__validity__date_start__lte=date,
                                lesson_period__lesson__validity__date_end__gte=date,
                            )
                            | Q(
                                extra_lesson__week=date.isocalendar()[1],
                                extra_lesson__period__weekday=date.weekday(),
                            )
                        )
                        for note in notes:
                            note.excused = True
                            note.excuse_type = excuse_type
                            with reversion.create_revision():
                                reversion.set_user(request.user)
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
                                reversion.set_user(request.user)
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
            Q(lesson_period__lesson__groups__owners=request.user.person)
            | Q(extra_lesson__groups__owners=request.user.person)
            | Q(event__groups__owners=request.user.person)
        )

    unexcused_absences = allowed_personal_notes.filter(absent=True, excused=False)
    context["unexcused_absences"] = unexcused_absences

    personal_notes = (
        allowed_personal_notes.filter(
            Q(absent=True) | Q(late__gt=0) | ~Q(remarks="") | Q(extra_marks__isnull=False)
        )
        .annotate(
            school_term_start=Case(
                When(event__isnull=False, then="event__school_term__date_start"),
                When(extra_lesson__isnull=False, then="extra_lesson__school_term__date_start"),
                When(
                    lesson_period__isnull=False,
                    then="lesson_period__lesson__validity__school_term__date_start",
                ),
            ),
            order_year=Case(
                When(event__isnull=False, then=Extract("event__date_start", "year")),
                When(extra_lesson__isnull=False, then="extra_lesson__year"),
                When(lesson_period__isnull=False, then="year"),
            ),
            order_week=Case(
                When(event__isnull=False, then=Extract("event__date_start", "week")),
                When(extra_lesson__isnull=False, then="extra_lesson__week"),
                When(lesson_period__isnull=False, then="week"),
            ),
            order_weekday=Case(
                When(event__isnull=False, then="event__period_from__weekday"),
                When(extra_lesson__isnull=False, then="extra_lesson__period__weekday"),
                When(lesson_period__isnull=False, then="lesson_period__period__weekday"),
            ),
            order_period=Case(
                When(event__isnull=False, then="event__period_from__period"),
                When(extra_lesson__isnull=False, then="extra_lesson__period__period"),
                When(lesson_period__isnull=False, then="lesson_period__period__period"),
            ),
        )
        .order_by(
            "-school_term_start", "-order_year", "-order_week", "-order_weekday", "order_period",
        )
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
            personal_notes = PersonalNote.objects.filter(person=person,).filter(
                Q(lesson_period__lesson__validity__school_term=school_term)
                | Q(extra_lesson__school_term=school_term)
                | Q(event__school_term=school_term)
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


@never_cache
@permission_required("alsijil.register_absence", fn=objectgetter_optional(Person))
def register_absence(request: HttpRequest, id_: int) -> HttpResponse:
    context = {}

    person = get_object_or_404(Person, pk=id_)

    register_absence_form = RegisterAbsenceForm(request.POST or None)

    if request.method == "POST" and register_absence_form.is_valid():
        confirmed = request.POST.get("confirmed", "0") == "1"

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
        affected_count = 0
        delta = end_date - start_date
        for i in range(delta.days + 1):
            from_period_on_day = from_period if i == 0 else TimePeriod.period_min
            to_period_on_day = to_period if i == delta.days else TimePeriod.period_max
            day = start_date + timedelta(days=i)

            # Skip holidays if activated
            if not get_site_preferences()["alsijil__allow_entries_in_holidays"]:
                holiday = Holiday.on_day(day)
                if holiday:
                    continue

            affected_count += person.mark_absent(
                day,
                from_period_on_day,
                absent,
                excused,
                excuse_type,
                remarks,
                to_period_on_day,
                dry_run=not confirmed,
            )

        if not confirmed:
            # Show confirmation page
            context = {}
            context["affected_lessons"] = affected_count
            context["person"] = person
            context["form_data"] = register_absence_form.cleaned_data
            context["form"] = register_absence_form
            return render(request, "alsijil/absences/register_confirm.html", context)
        else:
            messages.success(request, _("The absence has been saved."))
            return redirect("overview_person", person.pk)

    context["person"] = person
    context["register_absence_form"] = register_absence_form

    return render(request, "alsijil/absences/register.html", context)


@method_decorator(never_cache, name="dispatch")
class DeletePersonalNoteView(PermissionRequiredMixin, DetailView):
    model = PersonalNote
    template_name = "core/pages/delete.html"
    permission_required = "alsijil.edit_personalnote"

    def post(self, request, *args, **kwargs):
        note = self.get_object()
        with reversion.create_revision():
            reversion.set_user(request.user)
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


@method_decorator(never_cache, name="dispatch")
class ExtraMarkCreateView(PermissionRequiredMixin, AdvancedCreateView):
    """Create view for extra marks."""

    model = ExtraMark
    form_class = ExtraMarkForm
    permission_required = "alsijil.create_extramark"
    template_name = "alsijil/extra_mark/create.html"
    success_url = reverse_lazy("extra_marks")
    success_message = _("The extra mark has been created.")


@method_decorator(never_cache, name="dispatch")
class ExtraMarkEditView(PermissionRequiredMixin, AdvancedEditView):
    """Edit view for extra marks."""

    model = ExtraMark
    form_class = ExtraMarkForm
    permission_required = "alsijil.edit_extramark"
    template_name = "alsijil/extra_mark/edit.html"
    success_url = reverse_lazy("extra_marks")
    success_message = _("The extra mark has been saved.")


@method_decorator(never_cache, name="dispatch")
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


@method_decorator(never_cache, name="dispatch")
class ExcuseTypeCreateView(PermissionRequiredMixin, AdvancedCreateView):
    """Create view for excuse types."""

    model = ExcuseType
    form_class = ExcuseTypeForm
    permission_required = "alsijil.add_excusetype"
    template_name = "alsijil/excuse_type/create.html"
    success_url = reverse_lazy("excuse_types")
    success_message = _("The excuse type has been created.")


@method_decorator(never_cache, name="dispatch")
class ExcuseTypeEditView(PermissionRequiredMixin, AdvancedEditView):
    """Edit view for excuse types."""

    model = ExcuseType
    form_class = ExcuseTypeForm
    permission_required = "alsijil.edit_excusetype"
    template_name = "alsijil/excuse_type/edit.html"
    success_url = reverse_lazy("excuse_types")
    success_message = _("The excuse type has been saved.")


@method_decorator(never_cache, "dispatch")
class ExcuseTypeDeleteView(PermissionRequiredMixin, RevisionMixin, AdvancedDeleteView):
    """Delete view for excuse types."""

    model = ExcuseType
    permission_required = "alsijil.delete_excusetype"
    template_name = "core/pages/delete.html"
    success_url = reverse_lazy("excuse_types")
    success_message = _("The excuse type has been deleted.")
