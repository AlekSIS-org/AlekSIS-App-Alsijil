from contextlib import nullcontext
from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

from django.core.exceptions import PermissionDenied
from django.db.models import Count, Exists, FilteredRelation, OuterRef, Prefetch, Q, Sum
from django.db.models.expressions import Case, When
from django.db.models.functions import Extract
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import ugettext as _
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.generic import DetailView

import reversion
from calendarweek import CalendarWeek
from django_tables2 import RequestConfig, SingleTableView
from guardian.core import ObjectPermissionChecker
from guardian.shortcuts import get_objects_for_user
from reversion.views import RevisionMixin
from rules.contrib.views import PermissionRequiredMixin, permission_required

from aleksis.apps.chronos.managers import TimetableType
from aleksis.apps.chronos.models import Event, ExtraLesson, Holiday, LessonPeriod, TimePeriod
from aleksis.apps.chronos.util.build import build_weekdays
from aleksis.apps.chronos.util.date import get_weeks_for_year, week_weekday_to_date
from aleksis.core.mixins import (
    AdvancedCreateView,
    AdvancedDeleteView,
    AdvancedEditView,
    SuccessNextMixin,
)
from aleksis.core.models import Group, Person, SchoolTerm
from aleksis.core.util import messages
from aleksis.core.util.core_helpers import get_site_preferences, objectgetter_optional
from aleksis.core.util.pdf import render_pdf
from aleksis.core.util.predicates import check_global_permission

from .filters import PersonalNoteFilter
from .forms import (
    AssignGroupRoleForm,
    ExcuseTypeForm,
    ExtraMarkForm,
    FilterRegisterObjectForm,
    GroupRoleAssignmentEditForm,
    GroupRoleForm,
    LessonDocumentationForm,
    PersonalNoteFormSet,
    PersonOverviewForm,
    RegisterAbsenceForm,
    RegisterObjectActionForm,
    SelectForm,
)
from .models import (
    ExcuseType,
    ExtraMark,
    GroupRole,
    GroupRoleAssignment,
    LessonDocumentation,
    PersonalNote,
)
from .tables import (
    ExcuseTypeTable,
    ExtraMarkTable,
    GroupRoleTable,
    PersonalNoteTable,
    RegisterObjectSelectTable,
    RegisterObjectTable,
)
from .util.alsijil_helpers import (
    annotate_documentations,
    generate_list_of_all_register_objects,
    get_register_object_by_pk,
    get_timetable_instance_by_pk,
    register_objects_sorter,
)


@permission_required("alsijil.view_register_object_rule", fn=get_register_object_by_pk)  # FIXME
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
            return redirect(
                "lesson_period", wanted_week.year, wanted_week.week, register_object.pk,
            )
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
    back_url = reverse(
        "lesson_period", args=[wanted_week.year, wanted_week.week, register_object.pk]
    )
    context["back_url"] = back_url

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
        # Group roles
        show_group_roles = request.user.person.preferences[
            "alsijil__group_roles_in_lesson_view"
        ] and request.user.has_perm(
            "alsijil.view_assigned_grouproles_for_register_object_rule", register_object
        )
        if show_group_roles:
            groups = register_object.get_groups().all()
            group_roles = GroupRole.objects.with_assignments(date_of_lesson, groups)
            context["group_roles"] = group_roles

        # Create or get lesson documentation object; can be empty when first opening lesson
        lesson_documentation = register_object.get_or_create_lesson_documentation(wanted_week)
        lesson_documentation_form = LessonDocumentationForm(
            request.POST or None, instance=lesson_documentation, prefix="lesson_documentation",
        )

        # Prefetch object permissions for all related groups of the register object
        # because the object permissions are checked for all groups of the register object
        # That has to be set as an attribute of the register object,
        # so that the permission system can use the prefetched data.
        checker = ObjectPermissionChecker(request.user)
        checker.prefetch_perms(register_object.get_groups().all())
        register_object.set_object_permission_checker(checker)

        # Create a formset that holds all personal notes for all persons in this lesson
        if not request.user.has_perm(
            "alsijil.view_register_object_personalnote_rule", register_object
        ):
            persons = Person.objects.filter(pk=request.user.person.pk)
        else:
            persons = Person.objects.all()

        persons_qs = register_object.get_personal_notes(persons, wanted_week)

        # Annotate group roles
        if show_group_roles:
            persons_qs = persons_qs.prefetch_related(
                Prefetch(
                    "person__group_roles",
                    queryset=GroupRoleAssignment.objects.on_day(date_of_lesson).for_groups(groups),
                ),
            )

        personal_note_formset = PersonalNoteFormSet(
            request.POST or None, queryset=persons_qs, prefix="personal_notes"
        )

        if request.method == "POST":
            if lesson_documentation_form.is_valid() and request.user.has_perm(
                "alsijil.edit_lessondocumentation_rule", register_object
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
                    "alsijil.edit_register_object_personalnote_rule", register_object
                ):
                    with reversion.create_revision():
                        reversion.set_user(request.user)
                        instances = personal_note_formset.save()

                    if (not isinstance(register_object, Event)) and get_site_preferences()[
                        "alsijil__carry_over_personal_notes"
                    ]:
                        # Iterate over personal notes
                        # and carry changed absences to following lessons
                        with reversion.create_revision():
                            reversion.set_user(request.user)
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

        back_url = request.GET.get("back", "")
        back_url_is_safe = url_has_allowed_host_and_scheme(
            url=back_url, allowed_hosts={request.get_host()}, require_https=request.is_secure(),
        )
        if back_url_is_safe:
            context["back_to_week_url"] = back_url
        else:
            context["back_to_week_url"] = reverse(
                "week_view_by_week",
                args=[
                    lesson_documentation.calendar_week.year,
                    lesson_documentation.calendar_week.week,
                    "group",
                    register_object.get_groups().all()[0].pk,
                ],
            )
        context["lesson_documentation"] = lesson_documentation
        context["lesson_documentation_form"] = lesson_documentation_form
        context["personal_note_formset"] = personal_note_formset

    return render(request, "alsijil/class_register/lesson.html", context)


@permission_required("alsijil.view_week_rule", fn=get_timetable_instance_by_pk)
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
        extra_lessons = extra_lessons.filter_from_type(type_, instance)

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
        back_url = reverse(
            "week_view_by_week", args=[wanted_week.year, wanted_week.week, type_.value, instance.pk]
        )
    else:
        initial = {}
        back_url = reverse("week_view_by_week", args=[wanted_week.year, wanted_week.week])
    context["back_url"] = back_url
    select_form = SelectForm(request, request.POST or None, initial=initial)

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

    # Group roles
    show_group_roles = (
        group
        and request.user.person.preferences["alsijil__group_roles_in_week_view"]
        and request.user.has_perm("alsijil.view_assigned_grouproles_rule", group)
    )
    if show_group_roles:
        group_roles = GroupRole.objects.with_assignments(wanted_week, [group])
        context["group_roles"] = group_roles
        group_roles_persons = GroupRoleAssignment.objects.in_week(wanted_week).for_group(group)

    extra_marks = ExtraMark.objects.all()

    if query_exists:
        lesson_periods_pk = list(lesson_periods.values_list("pk", flat=True))
        lesson_periods = annotate_documentations(LessonPeriod, wanted_week, lesson_periods_pk)

        events_pk = [event.pk for event in events]
        events = annotate_documentations(Event, wanted_week, events_pk)

        extra_lessons_pk = list(extra_lessons.values_list("pk", flat=True))
        extra_lessons = annotate_documentations(ExtraLesson, wanted_week, extra_lessons_pk)
        groups = Group.objects.filter(
            Q(lessons__lesson_periods__in=lesson_periods_pk)
            | Q(events__in=events_pk)
            | Q(extra_lessons__in=extra_lessons_pk)
        )
    else:
        lesson_periods_pk = []
        events_pk = []
        extra_lessons_pk = []

    if lesson_periods_pk or events_pk or extra_lessons_pk:
        # Aggregate all personal notes for this group and week
        persons_qs = Person.objects.filter(is_active=True)

        if not request.user.has_perm("alsijil.view_week_personalnote_rule", instance):
            persons_qs = persons_qs.filter(pk=request.user.person.pk)
        elif group:
            persons_qs = persons_qs.filter(member_of=group)
        else:
            persons_qs = persons_qs.filter(member_of__in=groups)

        # Prefetch object permissions for persons and groups the persons are members of
        # because the object permissions are checked for both persons and groups
        checker = ObjectPermissionChecker(request.user)
        checker.prefetch_perms(persons_qs.prefetch_related(None))
        checker.prefetch_perms(groups)

        prefetched_personal_notes = list(
            PersonalNote.objects.filter(  #
                Q(event__in=events_pk)
                | Q(
                    week=wanted_week.week,
                    year=wanted_week.year,
                    lesson_period__in=lesson_periods_pk,
                )
                | Q(extra_lesson__in=extra_lessons_pk)
            ).filter(~Q(remarks=""))
        )
        persons_qs = (
            persons_qs.select_related("primary_group")
            .prefetch_related(
                Prefetch(
                    "primary_group__owners",
                    queryset=Person.objects.filter(pk=request.user.person.pk),
                    to_attr="owners_prefetched",
                ),
                Prefetch("member_of", queryset=groups, to_attr="member_of_prefetched"),
            )
            .annotate(
                filtered_personal_notes=FilteredRelation(
                    "personal_notes",
                    condition=(
                        Q(personal_notes__event__in=events_pk)
                        | Q(
                            personal_notes__week=wanted_week.week,
                            personal_notes__year=wanted_week.year,
                            personal_notes__lesson_period__in=lesson_periods_pk,
                        )
                        | Q(personal_notes__extra_lesson__in=extra_lessons_pk)
                    ),
                )
            )
        )

        persons_qs = persons_qs.annotate(
            absences_count=Count(
                "filtered_personal_notes", filter=Q(filtered_personal_notes__absent=True),
            ),
            unexcused_count=Count(
                "filtered_personal_notes",
                filter=Q(
                    filtered_personal_notes__absent=True, filtered_personal_notes__excused=False
                ),
            ),
            tardiness_sum=Sum("filtered_personal_notes__late"),
            tardiness_count=Count(
                "filtered_personal_notes", filter=Q(filtered_personal_notes__late__gt=0),
            ),
        )

        for extra_mark in extra_marks:
            persons_qs = persons_qs.annotate(
                **{
                    extra_mark.count_label: Count(
                        "filtered_personal_notes",
                        filter=Q(filtered_personal_notes__extra_marks=extra_mark),
                    )
                }
            )

        persons = []
        for person in persons_qs:
            personal_notes = []
            for note in filter(lambda note: note.person_id == person.pk, prefetched_personal_notes):
                if note.lesson_period:
                    note.lesson_period.annotate_week(wanted_week)
                personal_notes.append(note)
            person.set_object_permission_checker(checker)
            person_dict = {"person": person, "personal_notes": personal_notes}
            if show_group_roles:
                person_dict["group_roles"] = filter(
                    lambda role: role.person_id == person.pk, group_roles_persons
                )
            persons.append(person_dict)
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
        register_object.weekday = register_object.period.weekday
        regrouped_objects.setdefault(register_object.period.weekday, [])
        regrouped_objects[register_object.period.weekday].append(register_object)

    for event in events:
        weekday_from = event.get_start_weekday(wanted_week)
        weekday_to = event.get_end_weekday(wanted_week)

        for weekday in range(weekday_from, weekday_to + 1):
            # Make a copy in order to keep the annotation only on this weekday
            event_copy = deepcopy(event)
            event_copy.annotate_day(wanted_week[weekday])
            event_copy.weekday = weekday

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


@permission_required(
    "alsijil.view_full_register_rule", fn=objectgetter_optional(Group, None, False)
)
def full_register_group(request: HttpRequest, id_: int) -> HttpResponse:
    context = {}

    group = get_object_or_404(Group, pk=id_)
    groups_q = (
        Q(lesson_period__lesson__groups=group)
        | Q(lesson_period__lesson__groups__parent_groups=group)
        | Q(extra_lesson__groups=group)
        | Q(extra_lesson__groups__parent_groups=group)
        | Q(event__groups=group)
        | Q(event__groups__parent_groups=group)
    )
    personal_notes = (
        PersonalNote.objects.select_related("lesson_period")
        .prefetch_related(
            "lesson_period__substitutions", "lesson_period__lesson__teachers", "groups_of_person"
        )
        .not_empty()
        .filter(groups_q)
    )
    documentations = (
        LessonDocumentation.objects.select_related("lesson_period").not_empty().filter(groups_q)
    )

    # Get all lesson periods for the selected group
    lesson_periods = LessonPeriod.objects.filter_group(group).distinct()
    events = Event.objects.filter_group(group).distinct()
    extra_lessons = ExtraLesson.objects.filter_group(group).distinct()
    weeks = CalendarWeek.weeks_within(group.school_term.date_start, group.school_term.date_end)

    register_objects_by_day = {}
    for extra_lesson in extra_lessons:
        day = extra_lesson.date
        register_objects_by_day.setdefault(day, []).append(
            (
                extra_lesson,
                list(filter(lambda d: d.extra_lesson == extra_lesson, documentations)),
                list(filter(lambda d: d.extra_lesson == extra_lesson, personal_notes)),
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
                    list(filter(lambda d: d.event == event, documentations)),
                    list(filter(lambda d: d.event == event, personal_notes)),
                    None,
                )
            )

    weeks = CalendarWeek.weeks_within(group.school_term.date_start, group.school_term.date_end,)

    for lesson_period in lesson_periods:
        for week in weeks:
            day = week[lesson_period.period.weekday]

            if (
                lesson_period.lesson.validity.date_start
                <= day
                <= lesson_period.lesson.validity.date_end
            ):
                filtered_documentations = list(
                    filter(
                        lambda d: d.week == week.week
                        and d.year == week.year
                        and d.lesson_period == lesson_period,
                        documentations,
                    )
                )
                filtered_personal_notes = list(
                    filter(
                        lambda d: d.week == week.week
                        and d.year == week.year
                        and d.lesson_period == lesson_period,
                        personal_notes,
                    )
                )
                substitution = lesson_period.get_substitution(week)

                register_objects_by_day.setdefault(day, []).append(
                    (lesson_period, filtered_documentations, filtered_personal_notes, substitution)
                )

    persons = group.members.prefetch_related(None).select_related(None)
    persons = group.generate_person_list_with_class_register_statistics(persons)

    prefetched_persons = []
    for person in persons:
        person.filtered_notes = list(filter(lambda d: d.person == person, personal_notes))
        prefetched_persons.append(person)

    context["school_term"] = group.school_term
    context["persons"] = prefetched_persons
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
    return render_pdf(request, "alsijil/print/full_register.html", context)


@permission_required("alsijil.view_my_students_rule")
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

    # Prefetch object permissions for persons and groups the persons are members of
    # because the object permissions are checked for both persons and groups
    all_persons = Person.objects.filter(member_of__in=relevant_groups)
    checker = ObjectPermissionChecker(request.user)
    checker.prefetch_perms(relevant_groups)
    checker.prefetch_perms(all_persons)

    new_groups = []
    for group in relevant_groups:
        persons = group.generate_person_list_with_class_register_statistics(
            group.members.prefetch_related(
                "primary_group__owners",
                Prefetch("member_of", queryset=relevant_groups, to_attr="member_of_prefetched"),
            )
        )
        persons_for_group = []
        for person in persons:
            person.set_object_permission_checker(checker)
            persons_for_group.append(person)
        new_groups.append((group, persons_for_group))

    context["groups"] = new_groups
    context["excuse_types"] = ExcuseType.objects.all()
    context["extra_marks"] = ExtraMark.objects.all()
    return render(request, "alsijil/class_register/persons.html", context)


@permission_required("alsijil.view_my_groups_rule",)
def my_groups(request: HttpRequest) -> HttpResponse:
    context = {}
    context["groups"] = request.user.person.get_owner_groups_with_lessons().annotate(
        students_count=Count("members", distinct=True)
    )
    return render(request, "alsijil/class_register/groups.html", context)


class StudentsList(PermissionRequiredMixin, DetailView):
    model = Group
    template_name = "alsijil/class_register/students_list.html"
    permission_required = "alsijil.view_students_list_rule"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["group"] = self.object
        context["persons"] = self.object.generate_person_list_with_class_register_statistics()
        context["extra_marks"] = ExtraMark.objects.all()
        context["excuse_types"] = ExcuseType.objects.all()
        return context


@permission_required(
    "alsijil.view_person_overview_rule",
    fn=objectgetter_optional(
        Person.objects.prefetch_related("member_of__owners"), "request.user.person", True
    ),
)
def overview_person(request: HttpRequest, id_: Optional[int] = None) -> HttpResponse:
    context = {}
    person = objectgetter_optional(
        Person.objects.prefetch_related("member_of__owners"),
        default="request.user.person",
        default_eval=True,
    )(request, id_)
    context["person"] = person

    person_personal_notes = (
        person.personal_notes.all()
        .prefetch_related(
            "lesson_period__lesson__groups",
            "lesson_period__lesson__teachers",
            "lesson_period__substitutions",
        )
        .annotate_date_range()
    )

    # Prefetch object permissions for groups the person is a member of
    # because the object permissions are checked for all groups the person is a member of
    # That has to be set as an attribute of the register object,
    # so that the permission system can use the prefetched data.
    checker = ObjectPermissionChecker(request.user)
    checker.prefetch_perms(Group.objects.filter(members=person))
    person.set_object_permission_checker(checker)

    if request.user.has_perm("alsijil.view_person_overview_personalnote_rule", person):
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
        allowed_personal_notes.not_empty()
        .filter(Q(absent=True) | Q(late__gt=0) | ~Q(remarks="") | Q(extra_marks__isnull=False))
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
            order_groups=Case(
                When(event__isnull=False, then="event__groups"),
                When(extra_lesson__isnull=False, then="extra_lesson__groups"),
                When(lesson_period__isnull=False, then="lesson_period__lesson__groups"),
            ),
            order_teachers=Case(
                When(event__isnull=False, then="event__teachers"),
                When(extra_lesson__isnull=False, then="extra_lesson__teachers"),
                When(lesson_period__isnull=False, then="lesson_period__lesson__teachers"),
            ),
        )
        .order_by(
            "-school_term_start", "-order_year", "-order_week", "-order_weekday", "order_period",
        )
        .annotate_date_range()
        .annotate_subject()
    )

    personal_note_filter_object = PersonalNoteFilter(request.GET, queryset=personal_notes)
    filtered_personal_notes = personal_note_filter_object.qs
    context["personal_note_filter_form"] = personal_note_filter_object.form

    used_filters = list(personal_note_filter_object.data.values())
    context["num_filters"] = (
        len(used_filters) - used_filters.count("") - used_filters.count("unknown")
    )

    personal_notes_list = []
    for note in personal_notes:
        note.set_object_permission_checker(checker)
        personal_notes_list.append(note)
    context["personal_notes"] = personal_notes_list
    context["excuse_types"] = ExcuseType.objects.all()

    form = PersonOverviewForm(request, request.POST or None, queryset=allowed_personal_notes)
    if request.method == "POST":
        if form.is_valid():
            with reversion.create_revision():
                reversion.set_user(request.user)
                form.execute()
            person.refresh_from_db()
    context["action_form"] = form

    table = PersonalNoteTable(filtered_personal_notes)
    RequestConfig(request, paginate={"per_page": 20}).configure(table)
    context["personal_notes_table"] = table

    extra_marks = ExtraMark.objects.all()
    excuse_types = ExcuseType.objects.all()
    if request.user.has_perm("alsijil.view_person_statistics_personalnote_rule", person):
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

    # Build filter with own form and logic as django-filter can't work with different models
    if request.user.person.preferences["alsijil__default_lesson_documentation_filter"]:
        default_documentation = False
    else:
        default_documentation = None

    filter_form = FilterRegisterObjectForm(
        request, request.GET or None, for_person=True, default_documentation=default_documentation
    )
    filter_dict = (
        filter_form.cleaned_data
        if filter_form.is_valid()
        else {"has_documentation": default_documentation}
    )
    filter_dict["person"] = person
    context["filter_form"] = filter_form

    register_objects = generate_list_of_all_register_objects(filter_dict)
    if register_objects:
        table = RegisterObjectTable(register_objects)
        items_per_page = request.user.person.preferences[
            "alsijil__register_objects_table_items_per_page"
        ]
        RequestConfig(request, paginate={"per_page": items_per_page}).configure(table)
        context["register_object_table"] = table
    return render(request, "alsijil/class_register/person.html", context)


@never_cache
@permission_required("alsijil.register_absence_rule", fn=objectgetter_optional(Person))
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

            with reversion.create_revision() if confirmed else nullcontext():
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
    permission_required = "alsijil.edit_personalnote_rule"

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
    permission_required = "alsijil.view_extramarks_rule"
    template_name = "alsijil/extra_mark/list.html"


@method_decorator(never_cache, name="dispatch")
class ExtraMarkCreateView(PermissionRequiredMixin, AdvancedCreateView):
    """Create view for extra marks."""

    model = ExtraMark
    form_class = ExtraMarkForm
    permission_required = "alsijil.add_extramark_rule"
    template_name = "alsijil/extra_mark/create.html"
    success_url = reverse_lazy("extra_marks")
    success_message = _("The extra mark has been created.")


@method_decorator(never_cache, name="dispatch")
class ExtraMarkEditView(PermissionRequiredMixin, AdvancedEditView):
    """Edit view for extra marks."""

    model = ExtraMark
    form_class = ExtraMarkForm
    permission_required = "alsijil.edit_extramark_rule"
    template_name = "alsijil/extra_mark/edit.html"
    success_url = reverse_lazy("extra_marks")
    success_message = _("The extra mark has been saved.")


@method_decorator(never_cache, name="dispatch")
class ExtraMarkDeleteView(PermissionRequiredMixin, RevisionMixin, AdvancedDeleteView):
    """Delete view for extra marks."""

    model = ExtraMark
    permission_required = "alsijil.delete_extramark_rule"
    template_name = "core/pages/delete.html"
    success_url = reverse_lazy("extra_marks")
    success_message = _("The extra mark has been deleted.")


class ExcuseTypeListView(PermissionRequiredMixin, SingleTableView):
    """Table of all excuse types."""

    model = ExcuseType
    table_class = ExcuseTypeTable
    permission_required = "alsijil.view_excusetypes_rule"
    template_name = "alsijil/excuse_type/list.html"


@method_decorator(never_cache, name="dispatch")
class ExcuseTypeCreateView(PermissionRequiredMixin, AdvancedCreateView):
    """Create view for excuse types."""

    model = ExcuseType
    form_class = ExcuseTypeForm
    permission_required = "alsijil.add_excusetype_rule"
    template_name = "alsijil/excuse_type/create.html"
    success_url = reverse_lazy("excuse_types")
    success_message = _("The excuse type has been created.")


@method_decorator(never_cache, name="dispatch")
class ExcuseTypeEditView(PermissionRequiredMixin, AdvancedEditView):
    """Edit view for excuse types."""

    model = ExcuseType
    form_class = ExcuseTypeForm
    permission_required = "alsijil.edit_excusetype_rule"
    template_name = "alsijil/excuse_type/edit.html"
    success_url = reverse_lazy("excuse_types")
    success_message = _("The excuse type has been saved.")


@method_decorator(never_cache, "dispatch")
class ExcuseTypeDeleteView(PermissionRequiredMixin, RevisionMixin, AdvancedDeleteView):
    """Delete view for excuse types."""

    model = ExcuseType
    permission_required = "alsijil.delete_excusetype_rule"
    template_name = "core/pages/delete.html"
    success_url = reverse_lazy("excuse_types")
    success_message = _("The excuse type has been deleted.")


class GroupRoleListView(PermissionRequiredMixin, SingleTableView):
    """Table of all group roles."""

    model = GroupRole
    table_class = GroupRoleTable
    permission_required = "alsijil.view_grouproles_rule"
    template_name = "alsijil/group_role/list.html"


@method_decorator(never_cache, name="dispatch")
class GroupRoleCreateView(PermissionRequiredMixin, AdvancedCreateView):
    """Create view for group roles."""

    model = GroupRole
    form_class = GroupRoleForm
    permission_required = "alsijil.add_grouprole_rule"
    template_name = "alsijil/group_role/create.html"
    success_url = reverse_lazy("group_roles")
    success_message = _("The group role has been created.")


@method_decorator(never_cache, name="dispatch")
class GroupRoleEditView(PermissionRequiredMixin, AdvancedEditView):
    """Edit view for group roles."""

    model = GroupRole
    form_class = GroupRoleForm
    permission_required = "alsijil.edit_grouprole_rule"
    template_name = "alsijil/group_role/edit.html"
    success_url = reverse_lazy("group_roles")
    success_message = _("The group role has been saved.")


@method_decorator(never_cache, "dispatch")
class GroupRoleDeleteView(PermissionRequiredMixin, RevisionMixin, AdvancedDeleteView):
    """Delete view for group roles."""

    model = GroupRole
    permission_required = "alsijil.delete_grouprole_rule"
    template_name = "core/pages/delete.html"
    success_url = reverse_lazy("group_roles")
    success_message = _("The group role has been deleted.")


class AssignedGroupRolesView(PermissionRequiredMixin, DetailView):
    permission_required = "alsijil.view_assigned_grouproles_rule"
    model = Group
    template_name = "alsijil/group_role/assigned_list.html"

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data()

        today = timezone.now().date()
        context["today"] = today

        self.roles = GroupRole.objects.with_assignments(today, [self.object])
        context["roles"] = self.roles
        assignments = (
            GroupRoleAssignment.objects.filter(
                Q(groups=self.object) | Q(groups__child_groups=self.object)
            )
            .distinct()
            .order_by("-date_start")
        )
        context["assignments"] = assignments
        return context


@method_decorator(never_cache, name="dispatch")
class AssignGroupRoleView(PermissionRequiredMixin, SuccessNextMixin, AdvancedCreateView):
    model = GroupRoleAssignment
    form_class = AssignGroupRoleForm
    permission_required = "alsijil.assign_grouprole_for_group_rule"
    template_name = "alsijil/group_role/assign.html"
    success_message = _("The group role has been assigned.")

    def get_success_url(self) -> str:
        return reverse("assigned_group_roles", args=[self.group.pk])

    def get_permission_object(self):
        self.group = get_object_or_404(Group, pk=self.kwargs.get("pk"))
        try:
            self.role = GroupRole.objects.get(pk=self.kwargs.get("role_pk"))
        except GroupRole.DoesNotExist:
            self.role = None
        return self.group

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        kwargs["initial"] = {"role": self.role, "groups": [self.group]}
        return kwargs

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["role"] = self.role
        context["group"] = self.group
        return context


@method_decorator(never_cache, name="dispatch")
class AssignGroupRoleMultipleView(PermissionRequiredMixin, SuccessNextMixin, AdvancedCreateView):
    model = GroupRoleAssignment
    form_class = AssignGroupRoleForm
    permission_required = "alsijil.assign_grouprole_for_multiple_rule"
    template_name = "alsijil/group_role/assign.html"
    success_message = _("The group role has been assigned.")

    def get_success_url(self) -> str:
        return reverse("assign_group_role_multiple")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs


@method_decorator(never_cache, name="dispatch")
class GroupRoleAssignmentEditView(PermissionRequiredMixin, SuccessNextMixin, AdvancedEditView):
    """Edit view for group role assignments."""

    model = GroupRoleAssignment
    form_class = GroupRoleAssignmentEditForm
    permission_required = "alsijil.edit_grouproleassignment_rule"
    template_name = "alsijil/group_role/edit_assignment.html"
    success_message = _("The group role assignment has been saved.")

    def get_success_url(self) -> str:
        pk = self.object.groups.first().pk
        return reverse("assigned_group_roles", args=[pk])


@method_decorator(never_cache, "dispatch")
class GroupRoleAssignmentStopView(PermissionRequiredMixin, SuccessNextMixin, DetailView):
    model = GroupRoleAssignment
    permission_required = "alsijil.stop_grouproleassignment_rule"

    def get_success_url(self) -> str:
        pk = self.object.groups.first().pk
        return reverse("assigned_group_roles", args=[pk])

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.date_end:
            self.object.date_end = timezone.now().date()
            self.object.save()
            messages.success(request, _("The group role assignment has been stopped."))
        return redirect(self.get_success_url())


@method_decorator(never_cache, "dispatch")
class GroupRoleAssignmentDeleteView(
    PermissionRequiredMixin, RevisionMixin, SuccessNextMixin, AdvancedDeleteView
):
    """Delete view for group role assignments."""

    model = GroupRoleAssignment
    permission_required = "alsijil.delete_grouproleassignment_rule"
    template_name = "core/pages/delete.html"
    success_message = _("The group role assignment has been deleted.")

    def get_success_url(self) -> str:
        pk = self.object.groups.first().pk
        return reverse("assigned_group_roles", args=[pk])


class AllRegisterObjectsView(PermissionRequiredMixin, View):
    """Provide overview of all register objects for coordinators."""

    permission_required = "alsijil.view_register_objects_list_rule"

    def get_context_data(self, request):
        context = {}
        # Filter selectable groups by permissions
        groups = Group.objects.all()
        if not check_global_permission(request.user, "alsijil.view_full_register"):
            allowed_groups = get_objects_for_user(
                self.request.user, "core.view_full_register_group", Group
            ).values_list("pk", flat=True)
            groups = groups.filter(Q(parent_groups__in=allowed_groups) | Q(pk__in=allowed_groups))

        # Build filter with own form and logic as django-filter can't work with different models
        filter_form = FilterRegisterObjectForm(
            request, request.GET or None, for_person=False, groups=groups
        )
        filter_dict = filter_form.cleaned_data if filter_form.is_valid() else {}
        filter_dict["groups"] = groups
        context["filter_form"] = filter_form

        register_objects = generate_list_of_all_register_objects(filter_dict)

        self.action_form = RegisterObjectActionForm(request, register_objects, request.POST or None)
        context["action_form"] = self.action_form

        if register_objects:
            self.table = RegisterObjectSelectTable(register_objects)
            items_per_page = request.user.person.preferences[
                "alsijil__register_objects_table_items_per_page"
            ]
            RequestConfig(request, paginate={"per_page": items_per_page}).configure(self.table)
            context["table"] = self.table
        return context

    def get(self, request: HttpRequest) -> HttpResponse:
        context = self.get_context_data(request)
        return render(request, "alsijil/class_register/all_objects.html", context)

    def post(self, request: HttpRequest):
        context = self.get_context_data(request)
        if self.action_form.is_valid():
            self.action_form.execute()
        return render(request, "alsijil/class_register/all_objects.html", context)
