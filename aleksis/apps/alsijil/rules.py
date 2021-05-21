from rules import add_perm

from aleksis.core.models import Group
from aleksis.core.util.predicates import (
    has_any_object,
    has_global_perm,
    has_object_perm,
    has_person,
    is_current_person,
    is_site_preference_set,
)

from .util.predicates import (
    has_lesson_group_object_perm,
    has_person_group_object_perm,
    has_personal_note_group_perm,
    is_group_member,
    is_group_owner,
    is_group_role_assignment_group_owner,
    is_lesson_original_teacher,
    is_lesson_parent_group_owner,
    is_lesson_participant,
    is_lesson_teacher,
    is_none,
    is_own_personal_note,
    is_owner_of_any_group,
    is_person_group_owner,
    is_person_primary_group_owner,
    is_personal_note_lesson_original_teacher,
    is_personal_note_lesson_parent_group_owner,
    is_personal_note_lesson_teacher,
    is_teacher,
)

# View lesson
view_register_object_predicate = has_person & (
    is_none  # View is opened as "Current lesson"
    | is_lesson_teacher
    | is_lesson_original_teacher
    | is_lesson_participant
    | is_lesson_parent_group_owner
    | has_global_perm("alsijil.view_lesson")
    | has_lesson_group_object_perm("core.view_week_class_register_group")
)
add_perm("alsijil.view_register_object_rule", view_register_object_predicate)

# View lesson in menu
add_perm("alsijil.view_lesson_menu_rule", has_person)

# View lesson personal notes
view_lesson_personal_notes_predicate = view_register_object_predicate & (
    ~is_lesson_participant
    | is_lesson_teacher
    | is_lesson_original_teacher
    | has_global_perm("alsijil.view_personalnote")
    | has_lesson_group_object_perm("core.view_personalnote_group")
)
add_perm("alsijil.view_register_object_personalnote_rule", view_lesson_personal_notes_predicate)

# Edit personal note
edit_lesson_personal_note_predicate = view_lesson_personal_notes_predicate & (
    is_lesson_teacher
    | (
        is_lesson_original_teacher
        & is_site_preference_set("alsijil", "edit_lesson_documentation_as_original_teacher")
    )
    | has_global_perm("alsijil.change_personalnote")
    | has_lesson_group_object_perm("core.edit_personalnote_group")
)
add_perm("alsijil.edit_register_object_personalnote_rule", edit_lesson_personal_note_predicate)

# View personal note
view_personal_note_predicate = has_person & (
    (is_own_personal_note & is_site_preference_set("alsijil", "view_own_personal_notes"))
    | is_personal_note_lesson_teacher
    | is_personal_note_lesson_original_teacher
    | is_personal_note_lesson_parent_group_owner
    | has_global_perm("alsijil.view_personalnote")
    | has_personal_note_group_perm("core.view_personalnote_group")
)
add_perm("alsijil.view_personalnote_rule", view_personal_note_predicate)

# Edit personal note
edit_personal_note_predicate = view_personal_note_predicate & (
    ~is_own_personal_note
    & ~(
        is_personal_note_lesson_original_teacher
        | ~is_site_preference_set("alsijil", "edit_lesson_documentation_as_original_teacher")
    )
    | has_global_perm("alsijil.view_personalnote")
    | has_personal_note_group_perm("core.edit_personalnote_group")
)
add_perm("alsijil.edit_personalnote_rule", edit_personal_note_predicate)

# View lesson documentation
view_lesson_documentation_predicate = view_register_object_predicate
add_perm("alsijil.view_lessondocumentation_rule", view_lesson_documentation_predicate)

# Edit lesson documentation
edit_lesson_documentation_predicate = view_register_object_predicate & (
    is_lesson_teacher
    | (
        is_lesson_original_teacher
        & is_site_preference_set("alsijil", "edit_lesson_documentation_as_original_teacher")
    )
    | has_global_perm("alsijil.change_lessondocumentation")
    | has_lesson_group_object_perm("core.edit_lessondocumentation_group")
)
add_perm("alsijil.edit_lessondocumentation_rule", edit_lesson_documentation_predicate)

# View week overview
view_week_predicate = has_person & (
    is_current_person
    | is_group_member
    | is_group_owner
    | has_global_perm("alsijil.view_week")
    | has_object_perm("core.view_week_class_register_group")
)
add_perm("alsijil.view_week_rule", view_week_predicate)

# View week overview in menu
add_perm("alsijil.view_week_menu_rule", has_person)

# View week personal notes
view_week_personal_notes_predicate = has_person & (
    (is_current_person & is_teacher)
    | is_group_owner
    | has_global_perm("alsijil.view_personalnote")
    | has_object_perm("core.view_personalnote_group")
)
add_perm("alsijil.view_week_personalnote_rule", view_week_personal_notes_predicate)

# Register absence
register_absence_predicate = has_person & (
    (
        is_person_primary_group_owner
        & is_site_preference_set("alsijil", "register_absence_as_primary_group_owner")
    )
    | has_global_perm("alsijil.register_absence")
    | has_object_perm("core.register_absence_person")
    | has_person_group_object_perm("core.register_absence_group")
)
add_perm("alsijil.register_absence_rule", register_absence_predicate)

# View full register for group
view_full_register_predicate = has_person & (
    is_group_owner
    | has_global_perm("alsijil.view_full_register")
    | has_object_perm("core.view_full_register_group")
)
add_perm("alsijil.view_full_register_rule", view_full_register_predicate)

# View students list
view_my_students_predicate = has_person & is_teacher
add_perm("alsijil.view_my_students_rule", view_my_students_predicate)

# View groups list
view_my_groups_predicate = has_person & is_teacher
add_perm("alsijil.view_my_groups_rule", view_my_groups_predicate)

# View students list
view_students_list_predicate = view_my_groups_predicate & (
    is_group_owner
    | has_global_perm("alsijil.view_personalnote")
    | has_object_perm("core.view_personalnote_group")
)
add_perm("alsijil.view_students_list_rule", view_students_list_predicate)

# View person overview
view_person_overview_predicate = has_person & (
    (is_current_person & is_site_preference_set("alsijil", "view_own_personal_notes"))
    | is_person_group_owner
)
add_perm("alsijil.view_person_overview_rule", view_person_overview_predicate)

# View person overview
view_person_overview_menu_predicate = has_person
add_perm("alsijil.view_person_overview_menu_rule", view_person_overview_menu_predicate)

# View person overview personal notes
view_person_overview_personal_notes_predicate = view_person_overview_predicate & (
    (is_current_person & is_site_preference_set("alsijil", "view_own_personal_notes"))
    | is_person_primary_group_owner
    | has_global_perm("alsijil.view_personalnote")
    | has_person_group_object_perm("core.view_personalnote_group")
)
add_perm(
    "alsijil.view_person_overview_personalnote_rule", view_person_overview_personal_notes_predicate,
)

# Edit person overview personal notes
edit_person_overview_personal_notes_predicate = view_person_overview_personal_notes_predicate & (
    ~is_current_person
    | has_global_perm("alsijil.edit_personalnote")
    | has_person_group_object_perm("core.edit_personalnote_group")
)
add_perm(
    "alsijil.edit_person_overview_personalnote_rule", edit_person_overview_personal_notes_predicate,
)

# View person statistics on personal notes
view_person_statistics_personal_notes_predicate = view_person_overview_personal_notes_predicate
add_perm(
    "alsijil.view_person_statistics_personalnote_rule",
    view_person_statistics_personal_notes_predicate,
)

# View excuse type list
view_excusetypes_predicate = has_person & has_global_perm("alsijil.view_excusetype")
add_perm("alsijil.view_excusetypes_rule", view_excusetypes_predicate)

# Add excuse type
add_excusetype_predicate = view_excusetypes_predicate & has_global_perm("alsijil.add_excusetype")
add_perm("alsijil.add_excusetype_rule", add_excusetype_predicate)

# Edit excuse type
edit_excusetype_predicate = view_excusetypes_predicate & has_global_perm(
    "alsijil.change_excusetype"
)
add_perm("alsijil.edit_excusetype_rule", edit_excusetype_predicate)

# Delete excuse type
delete_excusetype_predicate = view_excusetypes_predicate & has_global_perm(
    "alsijil.delete_excusetype"
)
add_perm("alsijil.delete_excusetype_rule", delete_excusetype_predicate)

# View extra mark list
view_extramarks_predicate = has_person & has_global_perm("alsijil.view_extramark")
add_perm("alsijil.view_extramarks_rule", view_extramarks_predicate)

# Add extra mark
add_extramark_predicate = view_extramarks_predicate & has_global_perm("alsijil.add_extramark")
add_perm("alsijil.add_extramark_rule", add_extramark_predicate)

# Edit extra mark
edit_extramark_predicate = view_extramarks_predicate & has_global_perm("alsijil.change_extramark")
add_perm("alsijil.edit_extramark_rule", edit_extramark_predicate)

# Delete extra mark
delete_extramark_predicate = view_extramarks_predicate & has_global_perm("alsijil.delete_extramark")
add_perm("alsijil.delete_extramark_rule", delete_extramark_predicate)

# View group role list
view_group_roles_predicate = has_person & has_global_perm("alsijil.view_grouprole")
add_perm("alsijil.view_grouproles_rule", view_group_roles_predicate)

# Add group role
add_group_role_predicate = view_group_roles_predicate & has_global_perm("alsijil.add_grouprole")
add_perm("alsijil.add_grouprole_rule", add_group_role_predicate)

# Edit group role
edit_group_role_predicate = view_group_roles_predicate & has_global_perm("alsijil.change_grouprole")
add_perm("alsijil.edit_grouprole_rule", edit_group_role_predicate)

# Delete group role
delete_group_role_predicate = view_group_roles_predicate & has_global_perm(
    "alsijil.delete_grouprole"
)
add_perm("alsijil.delete_grouprole_rule", delete_group_role_predicate)

view_assigned_group_roles_predicate = has_person & (
    is_group_owner
    | has_global_perm("alsijil.assign_grouprole")
    | has_object_perm("core.assign_grouprole")
)
add_perm("alsijil.view_assigned_grouproles_rule", view_assigned_group_roles_predicate)

view_assigned_group_roles_register_object_predicate = has_person & (
    is_lesson_teacher
    | is_lesson_original_teacher
    | is_lesson_parent_group_owner
    | has_global_perm("alsijil.assign_grouprole")
)
add_perm(
    "alsijil.view_assigned_grouproles_for_register_object",
    view_assigned_group_roles_register_object_predicate,
)

assign_group_role_person_predicate = has_person & (
    is_person_group_owner | has_global_perm("alsijil.assign_grouprole")
)
add_perm("alsijil.assign_grouprole_to_person_rule", assign_group_role_person_predicate)

assign_group_role_for_multiple_predicate = has_person & (
    is_owner_of_any_group | has_global_perm("alsijil.assign_grouprole")
)
add_perm("alsijil.assign_grouprole_for_multiple_rule", assign_group_role_for_multiple_predicate)

assign_group_role_group_predicate = view_assigned_group_roles_predicate
add_perm("alsijil.assign_grouprole_for_group_rule", assign_group_role_group_predicate)

edit_group_role_assignment_predicate = has_person & (
    has_global_perm("alsijil.assign_grouprole") | is_group_role_assignment_group_owner
)
add_perm("alsijil.edit_grouproleassignment_rule", edit_group_role_assignment_predicate)

stop_group_role_assignment_predicate = edit_group_role_assignment_predicate
add_perm("alsijil.stop_grouproleassignment_rule", stop_group_role_assignment_predicate)

delete_group_role_assignment_predicate = has_person & (
    has_global_perm("alsijil.assign_grouprole") | is_group_role_assignment_group_owner
)
add_perm("alsijil.delete_grouproleassignment_rule", delete_group_role_assignment_predicate)

view_register_objects_list_predicate = has_person & (
    has_any_object("core.view_full_register_group", Group)
    | has_global_perm("core.view_full_register")
)
add_perm("alsijil.view_register_objects_list_rule", view_register_objects_list_predicate)
