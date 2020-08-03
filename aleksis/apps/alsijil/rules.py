from rules import add_perm

from aleksis.core.models import Person
from aleksis.core.util.predicates import (
    has_any_object,
    has_global_perm,
    has_object_perm,
    has_person,
    is_current_person,
)

from .util.predicates import (
    has_lesson_group_object_perm,
    has_person_group_object_perm,
    is_group_member,
    is_group_owner,
    is_lesson_parent_group_owner,
    is_lesson_participant,
    is_lesson_teacher,
    is_person_group_owner,
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

# View lesson personal notes
view_lesson_personal_notes_predicate = has_person & (
    has_global_perm("alsijil.view_personalnote")
    | has_lesson_group_object_perm("core.view_personalnote_group")
    | is_lesson_teacher
    | is_lesson_parent_group_owner
)
add_perm("alsijil.view_lesson_personalnote", view_lesson_personal_notes_predicate)

# Edit lesson personal notes
edit_lesson_personal_notes_predicate = has_person & (
    has_global_perm("alsijil.change_personalnote")
    | has_lesson_group_object_perm("core.edit_personalnote_group")
    | is_lesson_teacher
)
add_perm("alsijil.edit_personalnote", edit_lesson_personal_notes_predicate)

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
    has_any_object("alsijil.register_absence", Person)
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
