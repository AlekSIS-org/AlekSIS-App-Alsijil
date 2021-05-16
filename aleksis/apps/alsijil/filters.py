from django.utils.translation import gettext as _

from django_filters import CharFilter, DateFilter, FilterSet
from material import Layout, Row

from .models import PersonalNote


class PersonalNoteFilter(FilterSet):
    day_start = DateFilter(lookup_expr="gte", label=_("After"))
    day_end = DateFilter(lookup_expr="lte", label=_("Before"))
    subject = CharFilter(lookup_expr="icontains", label=_("Subject"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form.fields["late__lt"].label = _("Tardiness is lower than")
        self.form.fields["late__gt"].label = _("Tardiness is bigger than")
        self.form.layout = Layout(
            Row("subject"),
            Row("day_start", "day_end"),
            Row("absent", "excused", "excuse_type"),
            Row("late__gt", "late__lt", "extra_marks"),
        )

    class Meta:
        model = PersonalNote
        fields = {
            "excused": ["exact"],
            "late": ["lt", "gt"],
            "absent": ["exact"],
            "excuse_type": ["exact"],
            "extra_marks": ["exact"],
        }
