from typing import Sequence

from django.contrib import messages
from django.contrib.humanize.templatetags.humanize import apnumber
from django.http import HttpRequest
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from aleksis.core.models import Notification


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

    for teacher, items in grouped_by_teachers.items():
        title = _(
            f"{request.user.person.addressing_name} wants you to check some class register entries."
        )
        msg = _("Please check if the following class register entries are complete and correct:\n")

        # Add one line for each entry to check
        for entry in items:
            reg_object = entry["register_object"]
            date = entry["date"]
            msg += f"- {reg_object} ({date})\n"

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
            f"We have successfully sent notifications to "
            f"{apnumber(count_teachers)} persons for {apnumber(count_items)} lessons."
        ),
    )


send_request_to_check_entry.short_description = _("Notify teacher to check data")
