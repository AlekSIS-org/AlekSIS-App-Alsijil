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
                    "validators": ["menu_generator.validators.is_authenticated"],
                },
                {
                    "name": _("Current week"),
                    "url": "week_view",
                    "icon": "view_week",
                    "validators": ["menu_generator.validators.is_authenticated"],
                },
                {
                    "name": _("Register absence"),
                    "url": "register_absence",
                    "icon": "rate_review",
                    "validators": ["menu_generator.validators.is_superuser"],
                },
                {
                    "name": _("Excuse types"),
                    "url": "excuse_types",
                    "icon": "label",
                    "validators": ["menu_generator.validators.is_superuser"],
                },
                {
                    "name": _("Extra marks"),
                    "url": "extra_marks",
                    "icon": "label",
                    "validators": ["menu_generator.validators.is_superuser"],
                },
            ],
        }
    ]
}
