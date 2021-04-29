from django.utils.translation import gettext as _

from django_filters import FilterSet, CharFilter, ModelMultipleChoiceFilter
from material import Layout, Row

from .models import ExcuseType, PersonalNote


class PersonalNoteFilter(FilterSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form.layout = Layout(
            # TODO: Row with day (lt and gt) and subject (char search),
            Row("absent", "excused", "excuse_type"),
            Row("late__lt", "late__gt", "extra_marks")
        )

    class Meta:
        model = PersonalNote
        fields = {
            "excused": ["exact"],
            "late": ["lt", "gt"],
            "absent": ['exact'],
            "excuse_type": ["exact"],
            "extra_marks": ["exact"],
            # TODO: "date??": ['lt', 'gt'],
            # TODO: "subject??": "exact",
        }
