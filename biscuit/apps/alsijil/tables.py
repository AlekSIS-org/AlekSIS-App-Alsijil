from django.utils.translation import ugettext_lazy as _

import django_tables2 as tables
from django_tables2.utils import A


class PersonalNoteFilterTable(tables.Table):
    class Meta:
        attrs = {"class": "table table-striped table-bordered table-hover table-responsive-xl"}

    identifier = tables.Column()
    description = tables.Column()
    regex = tables.Column()
    edit_filter = tables.LinkColumn("edit_personal_note_filter", args=[A("id")], text=_("Edit"))
