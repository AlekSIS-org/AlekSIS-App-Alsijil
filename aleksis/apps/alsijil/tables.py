from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _

import django_tables2 as tables
from django_tables2.utils import A


class ExtraMarkTable(tables.Table):
    class Meta:
        attrs = {"class": "highlight"}

    name = tables.LinkColumn("edit_extra_mark", args=[A("id")])
    short_name = tables.Column()
    edit = tables.LinkColumn(
        "edit_extra_mark",
        args=[A("id")],
        text=_("Edit"),
        attrs={"a": {"class": "btn-flat waves-effect waves-orange orange-text"}},
    )
    delete = tables.LinkColumn(
        "delete_extra_mark",
        args=[A("id")],
        text=_("Delete"),
        attrs={"a": {"class": "btn-flat waves-effect waves-red red-text"}},
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


class GroupRoleTable(tables.Table):
    class Meta:
        attrs = {"class": "highlight"}

    name = tables.LinkColumn("edit_excuse_type", args=[A("id")])
    edit = tables.LinkColumn(
        "edit_group_role",
        args=[A("id")],
        text=_("Edit"),
        attrs={"a": {"class": "btn-flat waves-effect waves-orange orange-text"}},
    )
    delete = tables.LinkColumn(
        "delete_group_role",
        args=[A("id")],
        text=_("Delete"),
        attrs={"a": {"class": "btn-flat waves-effect waves-red red-text"}},
    )

    def render_name(self, value, record):
        context = dict(role=record)
        return render_to_string("alsijil/group_role/chip.html", context)

    def before_render(self, request):
        if not request.user.has_perm("alsijil.edit_grouprole"):
            self.columns.hide("edit")
        if not request.user.has_perm("alsijil.delete_grouprole"):
            self.columns.hide("delete")


class RegisterObjectTable(tables.Table):
    class Meta:
        attrs = {"class": "highlight responsive-table"}

    status = tables.Column(accessor="register_object")
    date = tables.Column(order_by="date_sort")
    period = tables.Column(order_by="period_sort")
    groups = tables.Column()
    subject = tables.Column()
    topic = tables.Column()
    homework = tables.Column()
    group_note = tables.Column()

    def render_status(self, value, record):
        return render_to_string(
            "alsijil/partials/lesson_status_icon.html",
            dict(
                week=record.get("week"),
                has_documentation=record.get("has_documentation", False),
                substitution=record.get("substitution"),
                register_object=value,
            ),
        )
