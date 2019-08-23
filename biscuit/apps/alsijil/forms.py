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
        fields = ['person__last_name', 'person__first_name', 'absent', 'late', 'excused', 'remarks']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['person__last_name'].widget.attrs['readonly'] = True
        self.fields['person__first_name'].widget.attrs['readonly'] = True

    def clean_person__last_name(self):
        return self.instance.person__last_name
    def clean_person__first_name(self):
        return self.instance.person__first_name


PersonalNoteFormSet = forms.modelformset_factory(
    PersonalNote, form=PersonalNoteForm)
