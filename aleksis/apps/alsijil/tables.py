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


class ExcuseTypeTable(tables.Table):
    class Meta:
        attrs = {"class": "highlight"}

    name = tables.LinkColumn("edit_excuse_type", args=[A("id")])
    short_name = tables.Column()
    edit = tables.LinkColumn(
        "edit_excuse_type",
        args=[A("id")],
        text=_("Edit"),
        attrs={"a": {"class": "btn-flat waves-effect waves-orange orange-text"}},
    )
    delete = tables.LinkColumn(
        "delete_excuse_type",
        args=[A("id")],
        text=_("Delete"),
        attrs={"a": {"class": "btn-flat waves-effect waves-red red-text"}},
    )

    def before_render(self, request):
        if not request.user.has_perm("alsijil.edit_excusetype"):
            self.columns.hide("edit")
        if not request.user.has_perm("alsijil.delete_excusetype"):
            self.columns.hide("delete")
