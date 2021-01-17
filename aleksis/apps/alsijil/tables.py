from django.template.loader import render_to_string
<<<<<<< HEAD
=======
from django.urls import reverse
>>>>>>> 48d6587... Create a basic table for all PersonalNotes of an user
from django.utils.translation import gettext_lazy as _

import django_tables2 as tables
from django_tables2.utils import A

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
class PersonalNoteTable(tables.Table):
    lesson_period_lesson = tables.Column(verbose_name=_("Lesson"), accessor=A("lesson_period"))
    # lesson_period_teacher = tables.Column(verbose_name=_("Teacher"), accessor=A("lesson_period__get_teacher_names"))
    personal_note_date = tables.Column(verbose_name=_("Date"), accessor=A("date"))
    lesson_period_period = tables.Column(verbose_name=_("Period"), accessor=A("lesson_period__period__period"))
    # lesson_period_subject = tables.Column(verbose_name=_("Subject"), accessor=A("lesson_period__get_subject__name"))
    absent = tables.Column(attrs={"td": {"class": "material-icons"}})
    excused = tables.Column(verbose_name=_("Excuse"))
    extra_marks = tables.Column(verbose_name="Extra marks", accessor=A("extra_marks__all"))

    def render_lesson_period_period(self, value):
        return str(value) + "."

    def render_lesson_period_lesson(self, value, record):
        teachers = value.get_teacher_names()
        subject = value.get_subject().name
        pk = value.pk
        week = record.week
        year = record.year

        url = reverse("lesson_by_week_and_period", args=[year, week, pk])

        context = dict(subject=subject, teachers=teachers, url=url)

        return render_to_string("alsijil/partials/personal_note_link.html", context)

    def render_absent(self, value):
        return "check" if value else "clear"

    def render_excused(self, value, record):
        if record.absent:
            absent_badge = render_to_string("components/materialize-chips.html",
                                            dict(content="Absent", classes="red white-text"))
            if value:
                context = dict(content=_("Excused"), classes="green white-text")
                badge = render_to_string("components/materialize-chips.html", context)
                if record.excuse_type:
                    context = dict(content=record.excuse_type.short_name, classes="green white-text")
                    badge = render_to_string("components/materialize-chips.html", context)
            else:
                badge = ""
            return absent_badge + badge
        else:
            return ""

    def render_excuse_type(self, value):
        if value:
            content = value.short_name
            context = dict(content=content, classes="green white-text")
            return render_to_string("components/materialize-chips.html", context)
        else:
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
                content = extra_mark.short_name
                badges += render_to_string("components/materialize-chips.html", context=dict(content=content))
            return badges
        else:
            return "–"

    class Meta:
        model = PersonalNote
        sequence = (
            "year", "week", "personal_note_date", "lesson_period_period", "lesson_period_lesson",
            "absent", "excused", "late", "extra_marks", "remarks")
        exclude = ("site", "id", "extended_data", "person", "lesson_period", "excuse_type")
        template_name = "django_tables2/materialize.html"
