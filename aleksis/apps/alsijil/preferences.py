from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from dynamic_preferences.preferences import Section
from dynamic_preferences.types import BooleanPreference, IntegerPreference

from aleksis.core.registries import person_preferences_registry, site_preferences_registry

alsijil = Section("alsijil", verbose_name=_("Class register"))


@site_preferences_registry.register
class BlockPersonalNotesForCancelled(BooleanPreference):
    section = alsijil
    name = "block_personal_notes_for_cancelled"
    default = True
    verbose_name = _("Block adding personal notes for cancelled lessons")


@site_preferences_registry.register
class ViewOwnPersonalNotes(BooleanPreference):
    section = alsijil
    name = "view_own_personal_notes"
    default = True
    verbose_name = _("Allow users to view their own personal notes")


@site_preferences_registry.register
class RegisterAbsenceAsPrimaryGroupOwner(BooleanPreference):
    section = alsijil
    name = "register_absence_as_primary_group_owner"
    default = True
    verbose_name = _(
        "Allow primary group owners to register future absences for students in their groups"
    )


@site_preferences_registry.register
class EditLessonDocumentationAsOriginalTeacher(BooleanPreference):
    section = alsijil
    name = "edit_lesson_documentation_as_original_teacher"
    default = True
    verbose_name = _("Allow original teachers to edit their lessons although they are substituted")


@site_preferences_registry.register
class CarryOverDataToNextPeriods(BooleanPreference):
    section = alsijil
    name = "carry_over"
    default = True
    verbose_name = _(
        "Carry over data from first lesson period to the "
        "following lesson periods in lessons over multiple periods"
    )
    help_text = _("This will carry over data only if the data in the following periods are empty.")


@site_preferences_registry.register
class CarryOverPersonalNotesToNextPeriods(BooleanPreference):
    section = alsijil
    name = "carry_over_personal_notes"
    default = True
    verbose_name = _("Carry over personal notes to all following lesson periods on the same day.")


@site_preferences_registry.register
class AllowOpenPeriodsOnSameDay(BooleanPreference):
    section = alsijil
    name = "open_periods_same_day"
    default = False
    verbose_name = _(
        "Allow teachers to open lesson periods on the "
        "same day and not just at the beginning of the period"
    )
    help_text = _(
        "Lessons in the past are not affected by this setting, you can open them whenever you want."
    )


@site_preferences_registry.register
class AllowEntriesInHolidays(BooleanPreference):
    section = alsijil
    name = "allow_entries_in_holidays"
    default = False
    verbose_name = _("Allow teachers to add data for lessons in holidays")


@site_preferences_registry.register
class GroupOwnersCanAssignRolesToParents(BooleanPreference):
    section = alsijil
    name = "group_owners_can_assign_roles_to_parents"
    default = False
    verbose_name = _(
        "Allow group owners to assign group roles to the parents of the group's members"
    )


@person_preferences_registry.register
class ShowGroupRolesInWeekView(BooleanPreference):
    section = alsijil
    name = "group_roles_in_week_view"
    default = True
    verbose_name = _("Show assigned group roles in week view")
    help_text = _("Only week view of groups")


@person_preferences_registry.register
class ShowGroupRolesInLessonView(BooleanPreference):
    section = alsijil
    name = "group_roles_in_lesson_view"
    default = True
    verbose_name = _("Show assigned group roles in lesson view")


@person_preferences_registry.register
class RegisterObjectsTableItemsPerPage(IntegerPreference):
    """Preference how many items are shown per page in ``RegisterObjectTable``."""

    section = alsijil
    name = "register_objects_table_items_per_page"
    default = 100
    verbose_name = _("Items per page in lessons table")

    def validate(self, value):
        if value < 1:
            raise ValidationError(_("Each page must show at least one item."))


@person_preferences_registry.register
class DefaultLessonDocumentationFilter(BooleanPreference):
    section = alsijil
    name = "default_lesson_documentation_filter"
    default = True
    verbose_name = _("Filter lessons by existence of their lesson documentation on default")
