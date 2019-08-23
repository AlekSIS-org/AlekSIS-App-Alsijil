from django import forms
from django.utils.translation import ugettext_lazy as _

from .models import LessonDocumentation, PersonalNote


class LessonDocumentationForm(forms.ModelForm):
    class Meta:
        model = LessonDocumentation
        fields = ['topic', 'homework']


PersonalNoteFormSet = forms.modelformset_factory(
    PersonalNote, fields=('person', 'absent', 'late', 'excused', 'remarks'))
