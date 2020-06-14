from rules import add_perm

from aleksis.core.util.predicates import (
    has_any_object,
    has_global_perm,
    has_object_perm,
    has_person,
)

from .util.predicates import has_lesson_perm, has_week_perm

# View lesson
view_lesson_predicate = has_person & (
    has_global_perm("chronos.view_lesson_period") | has_lesson_perm("chronos.view_lesson_period")
)
add_perm("alsijil.view_lesson", view_lesson_predicate)

# View week overview
view_week_predicate = has_person & (
    has_global_perm("alsijil.view_week") | has_week_perm("alsijil")
)
add_perm("alsijil.view_week", view_week_predicate)

# Register absence
register_absence_predicate = has_person & (
    has_global_perm("alsijil.register_absence")
)
add_perm("alsijil.register_absence", register_absence_predicate)

# List all personal note filters
list_personal_note_filters_predicate = has_person & has_global_perm("alsijil.list_personal_note_filters")
add_perm("alsijil.list_personal_note_filters", list_personal_note_filters_predicate)

# Edit personal note filter
edit_personal_note_filter_predicate = has_person & (
    has_global_perm("alsijil.change_personal_note_filter")
    | has_object_perm("alsijil.change_personal_note_filter")
)
add_perm("alsijil.edit_personal_note_filter", edit_personal_note_filter_predicate)

# Delete personal note filter
delete_personal_note_filter_predicate = has_person & (
    has_global_perm("alsijil.delete_personal_note_filter")
    | has_object_perm("alsijil.delete_personal_note_filter")
)
add_perm("alsijil.delete_personal_note_filter", delete_personal_note_filter_predicate)
