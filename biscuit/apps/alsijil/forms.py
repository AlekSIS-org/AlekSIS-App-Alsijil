from django import forms
from django.utils.translation import ugettext_lazy as _

from biscuit.core.models import Group

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
        self.fields['person_name'].widget.attrs.update({'class':'alsijil-lesson-personal-note-name'})
        try:
            self.fields['person_name'].initial = str(self.instance.person)
        except:
            pass


class SelectForm(forms.Form):
    group = forms.ModelChoiceField(
        queryset=Group.objects.annotate(lessons_count=Count('lessons')).filter(lessons_count__gt=0),
        label=_('Group'), required=False)


PersonalNoteFormSet = forms.modelformset_factory(
    PersonalNote, form=PersonalNoteForm, max_num=0, extra=0)
