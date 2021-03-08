from typing import Callable

from django.utils.translation import gettext_lazy as _


def mark_as_excused(modeladmin, request, queryset):
    queryset.update(excused=True, excuse_type=None)


mark_as_excused.short_description = _("Mark as excused")


def mark_as_excuse_type_generator(excuse_type) -> Callable:
    def mark_as_excuse_type(modeladmin, request, queryset):
        queryset.update(excused=True, excuse_type=excuse_type)

    mark_as_excuse_type.short_description = _(f"Mark as {excuse_type.name}")

    return mark_as_excuse_type


def delete_personal_note(modeladmin, request, queryset):
    queryset.delete()

delete_personal_note.short_description = _("Delete")