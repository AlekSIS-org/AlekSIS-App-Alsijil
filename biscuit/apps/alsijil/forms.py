from django import forms
from django.utils.translation import ugettext_lazy as _

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
        kwargs.update(initial={'person_name': str(kwargs['instance'].person)})
        super().__init__(*args, **kwargs)


PersonalNoteFormSet = forms.modelformset_factory(
    PersonalNote, form=PersonalNoteForm)
