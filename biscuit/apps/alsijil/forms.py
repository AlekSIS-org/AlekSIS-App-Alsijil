from django import forms
from django.db.models import Count
from django.utils.translation import ugettext_lazy as _

from biscuit.apps.chronos.models import Room
from biscuit.core.models import Group, Person

from .models import LessonDocumentation, PersonalNote


class LessonDocumentationForm(forms.ModelForm):
    class Meta:
        model = LessonDocumentation
        fields = ['topic', 'homework']


class PersonalNoteForm(forms.ModelForm):
    class Meta:
        model = PersonalNote
        fields = ['absent', 'late', 'excused', 'remarks']

    person_name = forms.CharField(disabled=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['person_name'].widget.attrs.update(
            {'class': 'alsijil-lesson-personal-note-name'})

        if self.instance and getattr(self.instance, 'person', None):
            self.fields['person_name'].initial = str(self.instance.person)


class SelectForm(forms.Form):
    group = forms.ModelChoiceField(
        queryset=Group.objects.annotate(lessons_count=Count('lessons')).filter(lessons_count__gt=0),
        label=_('Group'), required=False)
    teacher = forms.ModelChoiceField(
        queryset=Person.objects.annotate(lessons_count=Count(
            'lessons')).filter(lessons_count__gt=0),
        label=_('Teacher'), required=False)
    room = forms.ModelChoiceField(
        queryset=Room.objects.annotate(lessons_count=Count(
            'lesson_periods')).filter(lessons_count__gt=0),
        label=_('Room'), required=False)


PersonalNoteFormSet = forms.modelformset_factory(
    PersonalNote, form=PersonalNoteForm, max_num=0, extra=0)
