from datetime import datetime

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.utils.translation import gettext_lazy as _

from django_select2.forms import Select2Widget
from material import Layout, Row

from aleksis.core.util.core_helpers import queryset_rules_filter
from aleksis.apps.chronos.managers import TimetableType
from aleksis.core.models import Group, Person

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
        queryset=Person.objects.annotate(
            lessons_count=Count("lessons_as_teacher")
        ).filter(lessons_count__gt=0),
        label=_("Teacher"),
        required=False,
        widget=Select2Widget,
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
        super().__init__(*args, **kwargs)
        self.fields["group"].queryset = (
            Group.objects.for_current_school_term_or_all()
            .annotate(lessons_count=Count("lessons"))
            .filter(lessons_count__gt=0)
        )


PersonalNoteFormSet = forms.modelformset_factory(
    PersonalNote, form=PersonalNoteForm, max_num=0, extra=0
)


class RegisterAbsenceForm(forms.Form):
    layout = Layout(
        Row("date_start", "date_end"),
        Row("from_period"),
        Row("absent", "excused"),
        Row("person"),
        Row("remarks"),
    )
    date_start = forms.DateField(label=_("Start date"), initial=datetime.today)
    date_end = forms.DateField(label=_("End date"), initial=datetime.today)
    from_period = forms.IntegerField(label=_("From period"), initial=0, min_value=0)
    person = forms.ModelChoiceField(
        label=_("Person"), queryset=Person.objects.all(), widget=Select2Widget
    )
    absent = forms.BooleanField(label=_("Absent"), initial=True, required=False)
    excused = forms.BooleanField(label=_("Excused"), initial=True, required=False)
    remarks = forms.CharField(label=_("Remarks"), max_length=30, required=False)

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request")
        super().__init__(*args, **kwargs)
        self.fields["person"].queryset = queryset_rules_filter(self.request, Person.objects.all(),
                                                               "core.register_absence")


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
