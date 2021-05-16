from datetime import datetime, timedelta
from typing import Optional, Sequence

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.http import HttpRequest
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from django_select2.forms import ModelSelect2MultipleWidget, ModelSelect2Widget, Select2Widget
from guardian.shortcuts import get_objects_for_user
from material import Fieldset, Layout, Row

from aleksis.apps.chronos.managers import TimetableType
from aleksis.apps.chronos.models import Subject, TimePeriod
from aleksis.core.forms import ActionForm, ListActionForm
from aleksis.core.models import Group, Person, SchoolTerm
from aleksis.core.util.core_helpers import get_site_preferences
from aleksis.core.util.predicates import check_global_permission

from .actions import (
    delete_personal_note,
    mark_as_excuse_type_generator,
    mark_as_excused,
    mark_as_unexcused,
    send_request_to_check_entry,
)
from .models import (
    ExcuseType,
    ExtraMark,
    GroupRole,
    GroupRoleAssignment,
    LessonDocumentation,
    PersonalNote,
)


class LessonDocumentationForm(forms.ModelForm):
    class Meta:
        model = LessonDocumentation
        fields = ["topic", "homework", "group_note"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["homework"].label = _("Homework for the next lesson")


class PersonalNoteForm(forms.ModelForm):
    class Meta:
        model = PersonalNote
        fields = ["absent", "late", "excused", "excuse_type", "extra_marks", "remarks"]

    person_name = forms.CharField(disabled=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["person_name"].widget.attrs.update(
            {"class": "alsijil-lesson-personal-note-name"}
        )
        self.fields["person_name"].widget = forms.HiddenInput()

        if self.instance and getattr(self.instance, "person", None):
            self.fields["person_name"].initial = str(self.instance.person)


class SelectForm(forms.Form):
    layout = Layout(Row("group", "teacher"))

    group = forms.ModelChoiceField(
        queryset=None, label=_("Group"), required=False, widget=Select2Widget,
    )
    teacher = forms.ModelChoiceField(
        queryset=None, label=_("Teacher"), required=False, widget=Select2Widget,
    )

    def clean(self) -> dict:
        data = super().clean()

        if data.get("group") and not data.get("teacher"):
            type_ = TimetableType.GROUP
            instance = data["group"]
        elif data.get("teacher") and not data.get("group"):
            type_ = TimetableType.TEACHER
            instance = data["teacher"]
        elif not data.get("teacher") and not data.get("group"):
            return data
        else:
            raise ValidationError(_("You can't select a group and a teacher both."))

        data["type_"] = type_
        data["instance"] = instance
        return data

    def __init__(self, request, *args, **kwargs):
        self.request = request
        super().__init__(*args, **kwargs)

        person = self.request.user.person

        group_qs = Group.get_groups_with_lessons()

        # Filter selectable groups by permissions
        if not check_global_permission(self.request.user, "alsijil.view_week"):
            # 1) All groups the user is allowed to see the week view by object permissions
            # 2) All groups the user is a member of an owner of
            group_qs = (
                group_qs.filter(
                    pk__in=get_objects_for_user(
                        self.request.user, "core.view_week_class_register_group", Group
                    ).values_list("pk", flat=True)
                )
            ).union(group_qs.filter(Q(members=person) | Q(owners=person)))

        # Flatten query by filtering groups by pk
        self.fields["group"].queryset = Group.objects.filter(
            pk__in=list(group_qs.values_list("pk", flat=True))
        )

        teacher_qs = Person.objects.annotate(lessons_count=Count("lessons_as_teacher")).filter(
            lessons_count__gt=0
        )

        # Filter selectable teachers by permissions
        if not check_global_permission(self.request.user, "alsijil.view_week"):
            # If the user hasn't the global permission,
            # the user is only allowed to see his own person
            teacher_qs = teacher_qs.filter(pk=person.pk)

        self.fields["teacher"].queryset = teacher_qs


PersonalNoteFormSet = forms.modelformset_factory(
    PersonalNote, form=PersonalNoteForm, max_num=0, extra=0
)


class RegisterAbsenceForm(forms.Form):
    layout = Layout(
        Fieldset("", Row("date_start", "date_end"), Row("from_period", "to_period")),
        Fieldset("", Row("absent", "excused"), Row("excuse_type"), Row("remarks")),
    )
    date_start = forms.DateField(label=_("Start date"), initial=datetime.today)
    date_end = forms.DateField(label=_("End date"), initial=datetime.today)
    from_period = forms.ChoiceField(label=_("Start period"))
    to_period = forms.ChoiceField(label=_("End period"))
    absent = forms.BooleanField(label=_("Absent"), initial=True, required=False)
    excused = forms.BooleanField(label=_("Excused"), initial=True, required=False)
    excuse_type = forms.ModelChoiceField(
        label=_("Excuse type"),
        queryset=ExcuseType.objects.all(),
        widget=Select2Widget,
        required=False,
    )
    remarks = forms.CharField(label=_("Remarks"), max_length=30, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        period_choices = TimePeriod.period_choices

        self.fields["from_period"].choices = period_choices
        self.fields["to_period"].choices = period_choices
        self.fields["from_period"].initial = TimePeriod.period_min
        self.fields["to_period"].initial = TimePeriod.period_max


class ExtraMarkForm(forms.ModelForm):
    layout = Layout("short_name", "name")

    class Meta:
        model = ExtraMark
        fields = ["short_name", "name"]


class ExcuseTypeForm(forms.ModelForm):
    layout = Layout("short_name", "name")

    class Meta:
        model = ExcuseType
        fields = ["short_name", "name"]


class PersonOverviewForm(ActionForm):
    def get_actions(self):
        return (
            [mark_as_excused, mark_as_unexcused]
            + [
                mark_as_excuse_type_generator(excuse_type)
                for excuse_type in ExcuseType.objects.all()
            ]
            + [delete_personal_note]
        )


class GroupRoleForm(forms.ModelForm):
    layout = Layout("name", "icon", "colour")

    class Meta:
        model = GroupRole
        fields = ["name", "icon", "colour"]


class AssignGroupRoleForm(forms.ModelForm):
    layout_base = ["groups", "person", "role", Row("date_start", "date_end")]

    groups = forms.ModelMultipleChoiceField(
        label=_("Group"),
        required=True,
        queryset=Group.objects.all(),
        widget=ModelSelect2MultipleWidget(
            model=Group,
            search_fields=["name__icontains", "short_name__icontains"],
            attrs={"data-minimum-input-length": 0, "class": "browser-default",},
        ),
    )
    person = forms.ModelChoiceField(
        label=_("Person"),
        required=True,
        queryset=Person.objects.all(),
        widget=ModelSelect2Widget(
            model=Person,
            search_fields=[
                "first_name__icontains",
                "last_name__icontains",
                "short_name__icontains",
            ],
            attrs={"data-minimum-input-length": 0, "class": "browser-default"},
        ),
    )

    def __init__(self, request, *args, **kwargs):
        self.request = request
        initial = kwargs.get("initial", {})

        # Build layout with or without groups field
        base_layout = self.layout_base[:]
        if "groups" in initial:
            base_layout.remove("groups")
        self.layout = Layout(*base_layout)

        super().__init__(*args, **kwargs)

        if "groups" in initial:
            self.fields["groups"].required = False

        # Filter persons and groups by permissions
        if not self.request.user.has_perm("alsijil.assign_grouprole"):  # Global permission
            persons = Person.objects
            if initial.get("groups"):
                persons = persons.filter(member_of__in=initial["groups"])
            if get_site_preferences()["alsijil__group_owners_can_assign_roles_to_parents"]:
                persons = persons.filter(
                    Q(member_of__owners=self.request.user.person)
                    | Q(children__member_of__owners=self.request.user.person)
                )
            else:
                persons = persons.filter(member_of__owners=self.request.user.person)
            self.fields["person"].queryset = persons

            if "groups" not in initial:
                groups = Group.objects.for_current_school_term_or_all().filter(
                    owners=self.request.user.person
                )
                self.fields["groups"].queryset = groups

    def clean_groups(self):
        """Ensure that only permitted groups are used."""
        return self.initial["groups"] if "groups" in self.initial else self.cleaned_data["groups"]

    class Meta:
        model = GroupRoleAssignment
        fields = ["groups", "person", "role", "date_start", "date_end"]


class GroupRoleAssignmentEditForm(forms.ModelForm):
    class Meta:
        model = GroupRoleAssignment
        fields = ["date_start", "date_end"]


class FilterRegisterObjectForm(forms.Form):
    """Form for filtering register objects in ``RegisterObjectTable``."""

    layout = Layout(
        Row("school_term", "date_start", "date_end"), Row("has_documentation", "group", "subject")
    )
    school_term = forms.ModelChoiceField(queryset=None, label=_("School term"))
    has_documentation = forms.NullBooleanField(label=_("Has lesson documentation"))
    group = forms.ModelChoiceField(queryset=None, label=_("Group"), required=False)
    subject = forms.ModelChoiceField(queryset=None, label=_("Subject"), required=False)
    date_start = forms.DateField(label=_("Start date"))
    date_end = forms.DateField(label=_("End date"))

    @classmethod
    def get_initial(cls, has_documentation: Optional[bool] = None):
        date_end = timezone.now().date()
        date_start = date_end - timedelta(days=30)
        return {
            "school_term": SchoolTerm.current,
            "date_start": date_start,
            "date_end": date_end,
            "has_documentation": has_documentation,
        }

    def __init__(
        self,
        request: HttpRequest,
        *args,
        for_person: bool = True,
        default_documentation: Optional[bool] = None,
        groups: Optional[Sequence[Group]] = None,
        **kwargs
    ):
        self.request = request
        person = self.request.user.person

        kwargs["initial"] = self.get_initial(has_documentation=default_documentation)
        super().__init__(*args, **kwargs)

        self.fields["school_term"].queryset = SchoolTerm.objects.all()

        if not groups and for_person:
            groups = Group.objects.filter(
                Q(lessons__teachers=person)
                | Q(lessons__lesson_periods__substitutions__teachers=person)
                | Q(events__teachers=person)
                | Q(extra_lessons__teachers=person)
            )
        elif not for_person:
            groups = Group.objects.all()
        self.fields["group"].queryset = groups

        # Filter subjects by selectable groups
        subject_qs = Subject.objects.filter(
            Q(lessons__groups__in=groups) | Q(extra_lessons__groups__in=groups)
        ).distinct()
        self.fields["subject"].queryset = subject_qs


class RegisterObjectActionForm(ListActionForm):
    """Action form for managing register objects for use with ``RegisterObjectTable``."""

    actions = [send_request_to_check_entry]
