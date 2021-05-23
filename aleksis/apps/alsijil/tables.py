from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

import django_tables2 as tables
from django_tables2.utils import A

from aleksis.apps.chronos.models import Event, LessonPeriod
from aleksis.core.util.tables import SelectColumn

from .models import PersonalNote


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
        if not request.user.has_perm("alsijil.edit_excusetype_rule"):
            self.columns.hide("edit")
        if not request.user.has_perm("alsijil.delete_excusetype_rule"):
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
        if not request.user.has_perm("alsijil.edit_grouprole_rule"):
            self.columns.hide("edit")
        if not request.user.has_perm("alsijil.delete_grouprole_rule"):
            self.columns.hide("delete")


class PersonalNoteTable(tables.Table):
    selected = SelectColumn(attrs={"input": {"name": "selected_objects"}}, accessor=A("pk"))
    date = tables.Column(
        verbose_name=_("Date"), accessor=A("date_formatted"), order_by=A("day_start")
    )
    period = tables.Column(
        verbose_name=_("Period"), accessor=A("period_formatted"), order_by=A("order_period")
    )
    groups = tables.Column(
        verbose_name=_("Groups"),
        accessor=A("register_object__group_names"),
        order_by=A("order_groups"),
    )
    teachers = tables.Column(
        verbose_name=_("Teachers"),
        accessor=A("register_object__teacher_names"),
        order_by=A("order_teachers"),
    )
    subject = tables.Column(verbose_name=_("Subject"), accessor=A("subject"))
    absent = tables.Column()
    late = tables.Column()
    excused = tables.Column(verbose_name=_("Excuse"))
    extra_marks = tables.Column(verbose_name="Extra marks", accessor=A("extra_marks__all"))

    def render_groups(self, value, record):
        if isinstance(record.register_object, LessonPeriod):
            return record.register_object.lesson.group_names
        else:
            return value

    def render_subject(self, value, record):
        if isinstance(record.register_object, Event):
            return _("Event")
        else:
            return value

    def render_absent(self, value):
        return (
            render_to_string(
                "components/materialize-chips.html",
                dict(content="Absent", classes="red white-text"),
            )
            if value
            else "–"
        )

    def render_excused(self, value, record):
        if record.absent and value:
            context = dict(content=_("Excused"), classes="green white-text")
            badge = render_to_string("components/materialize-chips.html", context)
            if record.excuse_type:
                context = dict(content=record.excuse_type.name, classes="green white-text")
                badge = render_to_string("components/materialize-chips.html", context)
            return badge
        return "–"

    def render_late(self, value):
        if value:
            content = _(f"{value}' late")
            context = dict(content=content, classes="orange white-text")
            return render_to_string("components/materialize-chips.html", context)
        else:
            return "–"

    def render_extra_marks(self, value):
        if value:
            badges = ""
            for extra_mark in value:
                content = extra_mark.name
                badges += render_to_string(
                    "components/materialize-chips.html", context=dict(content=content)
                )
            return mark_safe(badges)  # noqa
        else:
            return "–"

    class Meta:
        model = PersonalNote
        fields = ()


def _get_link(value, record):
    return record["register_object"].get_alsijil_url(record.get("week"))


class RegisterObjectTable(tables.Table):
    """Table to show all register objects in an overview.

    .. warning::
        Works only with ``generate_list_of_all_register_objects``.
    """

    class Meta:
        attrs = {"class": "highlight responsive-table"}

    status = tables.Column(accessor="register_object")
    date = tables.Column(order_by="date_sort", linkify=_get_link)
    period = tables.Column(order_by="period_sort", linkify=_get_link)
    groups = tables.Column(linkify=_get_link)
    teachers = tables.Column(linkify=_get_link)
    subject = tables.Column(linkify=_get_link)
    topic = tables.Column(linkify=_get_link)
    homework = tables.Column(linkify=_get_link)
    group_note = tables.Column(linkify=_get_link)

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


class RegisterObjectSelectTable(RegisterObjectTable):
    """Table to show all register objects with multi-select support.

    More information at ``RegisterObjectTable``
    """

    selected = SelectColumn()

    class Meta(RegisterObjectTable.Meta):
        sequence = ("selected", "...")
