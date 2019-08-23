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
        super().__init__(*args, **kwargs)
        self.fields['person_name'].initial = str(self.instance.person)


PersonalNoteFormSet = forms.modelformset_factory(
    PersonalNote, form=PersonalNoteForm)
