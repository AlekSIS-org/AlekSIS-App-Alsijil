from datetime import datetime

from django import forms
from django.db.models import Count
from django.utils.translation import ugettext_lazy as _

from django_select2.forms import Select2Widget

from aleksis.apps.chronos.models import Room
from aleksis.core.models import Group, Person

from .models import LessonDocumentation, PersonalNote, PersonalNoteFilter


class LessonDocumentationForm(forms.ModelForm):
    class Meta:
        model = LessonDocumentation
        fields = ["topic", "homework"]


class PersonalNoteForm(forms.ModelForm):
    class Meta:
        model = PersonalNote
        fields = ["absent", "late", "excused", "remarks"]

    person_name = forms.CharField(disabled=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["person_name"].widget.attrs.update(
            {"class": "alsijil-lesson-personal-note-name"}
        )

        if self.instance and getattr(self.instance, "person", None):
            self.fields["person_name"].initial = str(self.instance.person)


class SelectForm(forms.Form):
    group = forms.ModelChoiceField(
        queryset=Group.objects.annotate(lessons_count=Count("lessons")).filter(lessons_count__gt=0),
        label=_("Group"),
        required=False,
        widget=Select2Widget,
    )
    teacher = forms.ModelChoiceField(
        queryset=Person.objects.annotate(lessons_count=Count("lessons_as_teacher")).filter(
            lessons_count__gt=0
        ),
        label=_("Teacher"),
        required=False,
        widget=Select2Widget,
    )
    room = forms.ModelChoiceField(
        queryset=Room.objects.annotate(lessons_count=Count("lesson_periods")).filter(
            lessons_count__gt=0
        ),
        label=_("Room"),
        required=False,
        widget=Select2Widget,
    )


PersonalNoteFormSet = forms.modelformset_factory(
    PersonalNote, form=PersonalNoteForm, max_num=0, extra=0
)


class RegisterAbsenceForm(forms.Form):
    date_start = forms.DateField(
        label=_("Start date"), widget=forms.SelectDateWidget, initial=datetime.today
    )
    date_end = forms.DateField(
        label=_("End date"), widget=forms.SelectDateWidget, initial=datetime.today
    )
    from_period = forms.IntegerField(label=_("From period"), initial=0, min_value=0)
    person = forms.ModelChoiceField(
        label=_("Person"), queryset=Person.objects.all(), widget=Select2Widget
    )
    absent = forms.BooleanField(label=_("Absent"), initial=True, required=False)
    excused = forms.BooleanField(label=_("Excused"), initial=True, required=False)
    remarks = forms.CharField(label=_("Remarks"), max_length=30, required=False)


class PersonalNoteFilterForm(forms.ModelForm):
    class Meta:
        model = PersonalNoteFilter
        fields = ["identifier", "description", "regex"]
