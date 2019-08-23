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
        fields = ['person', 'absent', 'late', 'excused', 'remarks']

    def __init__(self, *args, **kwargs):
        super().__init__(*awrgs, **kwargs)
        self.fields['person'].widget.attrs['readonly'] = True

    def clean_person(self):
      return self.instance.person


PersonalNoteFormSet = forms.modelformset_factory(
    PersonalNote, form=PersonalNoteForm)
