from django.utils.translation import gettext as _

from dynamic_preferences.preferences import Section
from dynamic_preferences.types import BooleanPreference

from aleksis.core.registries import site_preferences_registry

alsijil = Section("alsijil", verbose_name=_("Class register"))


@site_preferences_registry.register
class BlockPersonalNotesForCancelled(BooleanPreference):
    section = alsijil
    name = "block_personal_notes_for_cancelled"
    default = True
    verbose_name = _("Block adding personal notes for cancelled lessons")


@site_preferences_registry.register
class TakeOverDataForDoubleLessons(BooleanPreference):
    section = alsijil
    name = "take_over_double"
    default = True
    verbose_name = _(
        "Take over data from first lesson for second lesson in double lessons"
    )
    help_text = _(
        "This will take over data only if the data in the second lesson are empty."
    )
