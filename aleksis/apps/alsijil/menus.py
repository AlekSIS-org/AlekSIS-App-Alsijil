from django.utils.translation import gettext_lazy as _

MENUS = {
    "NAV_MENU_CORE": [
        {
            "name": _("Class register"),
            "url": "#",
            "icon": "chrome_reader_mode",
            "root": True,
            "validators": [
                "menu_generator.validators.is_authenticated",
                "aleksis.core.util.core_helpers.has_person",
            ],
            "submenu": [
                {
                    "name": _("Current lesson"),
                    "url": "lesson_period",
                    "icon": "alarm",
                    "validators": [
                        (
                            "aleksis.core.util.predicates.permission_validator",
                            "alsijil.view_lesson_menu_rule",
                        ),
                    ],
                },
                {
                    "name": _("Current week"),
                    "url": "week_view",
                    "icon": "view_week",
                    "validators": [
                        (
                            "aleksis.core.util.predicates.permission_validator",
                            "alsijil.view_week_menu_rule",
                        ),
                    ],
                },
                {
                    "name": _("My groups"),
                    "url": "my_groups",
                    "icon": "people",
                    "validators": [
                        (
                            "aleksis.core.util.predicates.permission_validator",
                            "alsijil.view_my_groups_rule",
                        ),
                    ],
                },
                {
                    "name": _("My overview"),
                    "url": "overview_me",
                    "icon": "insert_chart",
                    "validators": [
                        (
                            "aleksis.core.util.predicates.permission_validator",
                            "alsijil.view_person_overview_menu_rule",
                        ),
                    ],
                },
                {
                    "name": _("My students"),
                    "url": "my_students",
                    "icon": "people",
                    "validators": [
                        (
                            "aleksis.core.util.predicates.permission_validator",
                            "alsijil.view_my_students_rule",
                        ),
                    ],
                },
                {
                    "name": _("Assign group role"),
                    "url": "assign_group_role_multiple",
                    "icon": "assignment_ind",
                    "validators": [
                        (
                            "aleksis.core.util.predicates.permission_validator",
                            "alsijil.assign_grouprole_for_multiple_rule",
                        ),
                    ],
                },
                {
                    "name": _("All lessons"),
                    "url": "all_register_objects",
                    "icon": "list",
                    "validators": [
                        (
                            "aleksis.core.util.predicates.permission_validator",
                            "alsijil.view_register_objects_list_rule",
                        ),
                    ],
                },
                {
                    "name": _("Excuse types"),
                    "url": "excuse_types",
                    "icon": "label",
                    "validators": [
                        (
                            "aleksis.core.util.predicates.permission_validator",
                            "alsijil.view_excusetypes_rule",
                        ),
                    ],
                },
                {
                    "name": _("Extra marks"),
                    "url": "extra_marks",
                    "icon": "label",
                    "validators": [
                        (
                            "aleksis.core.util.predicates.permission_validator",
                            "alsijil.view_extramarks_rule",
                        ),
                    ],
                },
                {
                    "name": _("Manage group roles"),
                    "url": "group_roles",
                    "icon": "assignment_ind",
                    "validators": [
                        (
                            "aleksis.core.util.predicates.permission_validator",
                            "alsijil.view_grouproles_rule",
                        ),
                    ],
                },
            ],
        }
    ]
}
