from typing import Callable, Sequence

from django.contrib import messages
from django.contrib.humanize.templatetags.humanize import apnumber
from django.http import HttpRequest
from django.template.loader import get_template
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from aleksis.core.models import Notification


def mark_as_excused(modeladmin, request, queryset):
    queryset.update(excused=True, excuse_type=None)


mark_as_excused.short_description = _("Mark as excused")


def mark_as_unexcused(modeladmin, request, queryset):
    queryset.update(excused=False, excuse_type=None)


mark_as_unexcused.short_description = _("Mark as unexcused")


def mark_as_excuse_type_generator(excuse_type) -> Callable:
    def mark_as_excuse_type(modeladmin, request, queryset):
        queryset.update(excused=True, excuse_type=excuse_type)

    mark_as_excuse_type.short_description = _(f"Mark as {excuse_type.name}")
    mark_as_excuse_type.__name__ = f"mark_as_excuse_type_{excuse_type.short_name}"

    return mark_as_excuse_type


def delete_personal_note(modeladmin, request, queryset):
    queryset.delete()


delete_personal_note.short_description = _("Delete")


def send_request_to_check_entry(modeladmin, request: HttpRequest, selected_items: Sequence[dict]):
    """Send notifications to the teachers of the selected register objects.

    Action for use with ``RegisterObjectTable`` and ``RegisterObjectActionForm``.
    """
    # Group class register entries by teachers so each teacher gets just one notification
    grouped_by_teachers = {}
    for entry in selected_items:
        teachers = entry["register_object"].get_teachers().all()
        for teacher in teachers:
            grouped_by_teachers.setdefault(teacher, [])
            grouped_by_teachers[teacher].append(entry)

    template = get_template("alsijil/notifications/check.html")
    for teacher, items in grouped_by_teachers.items():
        msg = template.render({"items": items})

        title = _("{} asks you to check some class register entries.").format(
            request.user.person.addressing_name
        )

        n = Notification(
            title=title,
            description=msg,
            sender=request.user.person.addressing_name,
            recipient=teacher,
            link=request.build_absolute_uri(reverse("overview_me")),
        )
        n.save()

    count_teachers = len(grouped_by_teachers.keys())
    count_items = len(selected_items)
    messages.success(
        request,
        _(
            "We have successfully sent notifications to "
            "{count_teachers} persons for {count_items} lessons."
        ).format(count_teachers=apnumber(count_teachers), count_items=apnumber(count_items)),
    )


send_request_to_check_entry.short_description = _("Ask teacher to check data")
