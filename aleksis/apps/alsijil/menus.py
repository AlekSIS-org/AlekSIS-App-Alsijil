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
                    "name": _("My groups"),
                    "url": "my_groups",
                    "icon": "people",
                    "validators": [
                        (
                            "aleksis.core.util.predicates.permission_validator",
                            "alsijil.view_my_groups",
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
                            "alsijil.view_person_overview_menu",
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
                            "alsijil.view_my_students",
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
                {
                    "name": _("Extra marks"),
                    "url": "extra_marks",
                    "icon": "label",
                    "validators": [
                        (
                            "aleksis.core.util.predicates.permission_validator",
                            "alsijil.view_extramarks",
                        ),
                    ],
                },
            ],
        }
    ]
}
