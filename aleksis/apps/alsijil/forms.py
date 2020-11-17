from datetime import datetime

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.utils.translation import gettext_lazy as _

from django_global_request.middleware import get_request
from django_select2.forms import Select2Widget
from guardian.shortcuts import get_objects_for_user
from material import Fieldset, Layout, Row

from aleksis.apps.chronos.managers import TimetableType
from aleksis.apps.chronos.models import TimePeriod
from aleksis.core.models import Group, Person
from aleksis.core.util.predicates import check_global_permission

from .models import ExcuseType, ExtraMark, LessonDocumentation, PersonalNote


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

    def __init__(self, *args, **kwargs):
        self.request = get_request()
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
        self.request = get_request()
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
