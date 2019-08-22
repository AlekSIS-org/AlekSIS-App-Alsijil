from django import forms
from django.utils.translation import ugettext_lazy as _

from .models import LessonDocumentation


class LessonDocumentationForm(forms.ModelForm):
    class Meta:
        model = LessonDocumentation
        fields = ['topic', 'homework']
