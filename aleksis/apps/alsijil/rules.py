from rules import add_perm

from aleksis.core.util.predicates import (
    has_global_perm,
    has_object_perm,
    has_person,
    is_current_person,
)

from .util.predicates import (
    has_any_object_absence,
    has_lesson_group_object_perm,
    has_person_group_object_perm,
    has_personal_note_group_perm,
    is_group_member,
    is_group_owner,
    is_lesson_parent_group_owner,
    is_lesson_participant,
    is_lesson_teacher,
    is_own_personal_note,
    is_person_group_owner,
    is_personal_note_lesson_parent_group_owner,
    is_personal_note_lesson_teacher,
)

# View lesson
view_lesson_predicate = has_person & (
    has_global_perm("alsijil.view_lesson")
    | is_lesson_teacher
    | is_lesson_participant
    | is_lesson_parent_group_owner
    | has_lesson_group_object_perm("core.view_week_class_register_group")
)
add_perm("alsijil.view_lesson", view_lesson_predicate)

# View lesson in menu
add_perm("alsijil.view_lesson_menu", has_person)

# View personal note
view_personal_note_predicate = has_person & (
    has_global_perm("alsijil.view_personalnote")
    | has_personal_note_group_perm("core.view_personalnote_group")
    | is_personal_note_lesson_teacher
    | is_own_personal_note
    | is_personal_note_lesson_parent_group_owner
)
add_perm("alsijil.view_personalnote", view_personal_note_predicate)

# Edit personal note
edit_personal_note_predicate = has_person & (
    has_global_perm("alsijil.change_personalnote")
    | has_lesson_group_object_perm("core.edit_personalnote_group")
    | is_lesson_teacher
)
add_perm("alsijil.edit_personalnote", edit_personal_note_predicate)

# View lesson documentation
view_lesson_documentation_predicate = has_person & (
    has_global_perm("alsijil.view_lessondocumentation")
    | has_lesson_group_object_perm("core.view_lessondocumentation_group")
    | is_lesson_teacher
    | is_lesson_parent_group_owner
    | is_lesson_participant
)
add_perm("alsijil.view_lessondocumentation", view_lesson_documentation_predicate)

# Edit lesson documentation
edit_lesson_documentation_predicate = has_person & (
    has_global_perm("alsijil.change_lessondocumentation")
    | has_lesson_group_object_perm("core.edit_lessondocumentation_group")
    | is_lesson_teacher
)
add_perm("alsijil.edit_lessondocumentation", edit_lesson_documentation_predicate)

# View week overview
view_week_predicate = has_person & (
    has_global_perm("alsijil.view_week")
    | has_object_perm("core.view_week_class_register_group")
    | is_group_member
    | is_group_owner
    | is_current_person
)
add_perm("alsijil.view_week", view_week_predicate)

# View week overview in menu
add_perm("alsijil.view_week_menu", has_person)

# View week personal notes
view_week_personal_notes_predicate = has_person & (
    has_global_perm("alsijil.view_personalnote")
    | has_object_perm("core.view_personalnote_group")
    | is_group_owner
)
add_perm("alsijil.view_week_personalnote", view_week_personal_notes_predicate)

# View register absence page
view_register_absence_predicate = has_person & (
    has_global_perm("alsijil.register_absence") | has_any_object_absence
)
add_perm("alsijil.view_register_absence", view_register_absence_predicate)

# Register absence
register_absence_predicate = has_person & (
    has_global_perm("alsijil.register_absence")
    | has_person_group_object_perm("core.register_absence_group")
    | has_object_perm("core.register_absence_person")
    | is_person_group_owner
)
add_perm("alsijil.register_absence", register_absence_predicate)

# View full register for group
view_full_register_predicate = has_person & (
    has_global_perm("alsijil.view_full_register")
    | has_object_perm("core.view_full_register_group")
    | is_group_owner
)
add_perm("alsijil.view_full_register", view_full_register_predicate)

# View excuse type list
view_excusetypes_predicate = has_person & has_global_perm("alsijil.view_excusetype")
add_perm("alsijil.view_excusetypes", view_excusetypes_predicate)

# Add excuse type
add_excusetype_predicate = has_person & has_global_perm("alsijil.add_excusetype")
add_perm("alsijil.add_excusetype", add_excusetype_predicate)

# Edit excuse type
edit_excusetype_predicate = has_person & has_global_perm("alsijil.change_excusetype")
add_perm("alsijil.edit_excusetype", edit_excusetype_predicate)

# Delete excuse type
delete_excusetype_predicate = has_person & has_global_perm("alsijil.delete_excusetype")
add_perm("alsijil.delete_excusetype", delete_excusetype_predicate)

# View extra mark list
view_extramarks_predicate = has_person & has_global_perm("alsijil.view_extramark")
add_perm("alsijil.view_extramarks", view_extramarks_predicate)

# Add extra mark
add_extramark_predicate = has_person & has_global_perm("alsijil.add_extramark")
add_perm("alsijil.add_extramark", add_extramark_predicate)

# Edit extra mark
edit_extramark_predicate = has_person & has_global_perm("alsijil.change_extramark")
add_perm("alsijil.edit_extramark", edit_extramark_predicate)

# Delete extra mark
delete_extramark_predicate = has_person & has_global_perm("alsijil.delete_extramark")
add_perm("alsijil.delete_extramark", delete_extramark_predicate)
