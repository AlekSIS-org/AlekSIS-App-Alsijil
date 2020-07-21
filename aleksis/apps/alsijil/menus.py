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
                    "url": "lesson",
                    "icon": "alarm",
                    "validators": [
                        (
                            "aleksis.core.util.predicates.permission_validator",
                            "alsijil.view_lesson_menu",
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
                            "alsijil.view_week_menu",
                        ),
                    ],
                },
                {
                    "name": _("Register absence"),
                    "url": "register_absence",
                    "icon": "rate_review",
                    "validators": [
                        (
                            "aleksis.core.util.predicates.permission_validator",
                            "alsijil.view_register_absence",
                        ),
                    ],
                },
                {
                    "name": _("Personal note filters"),
                    "url": "list_personal_note_filters",
                    "icon": "filter_list",
                    "validators": [
                        (
                            "aleksis.core.util.predicates.permission_validator",
                            "alsijil.view_personal_note_filters",
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
                            "alsijil.view_excusetypes",
                        ),
                    ],
                },
            ],
        }
    ]
}
