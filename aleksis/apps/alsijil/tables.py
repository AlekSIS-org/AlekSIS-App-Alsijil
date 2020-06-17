from django.utils.translation import gettext_lazy as _

import django_tables2 as tables
from django_tables2.utils import A


class PersonalNoteFilterTable(tables.Table):
    class Meta:
        attrs = {"class": "highlight"}

    identifier = tables.Column()
    description = tables.Column()
    regex = tables.Column()
    edit_filter = tables.LinkColumn(
        "edit_personal_note_filter",
        args=[A("id")],
        text=_("Edit"),
        attrs={"a": {"class": "btn-flat waves-effect waves-orange"}},
    )
