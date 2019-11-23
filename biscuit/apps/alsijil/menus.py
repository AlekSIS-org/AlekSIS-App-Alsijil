from django.utils.translation import ugettext_lazy as _

MENUS = {
    'NAV_MENU_CORE': [
        {
            'name': _('Class register'),
            'url': '#',
            'root': True,
            'validators': ['menu_generator.validators.is_authenticated', 'biscuit.core.util.core_helpers.has_person'],
            'submenu': [
                {
                    'name': _('Current lesson'),
                    'url': 'lesson',
                    'validators': ['menu_generator.validators.is_authenticated']
                },
                {
                    'name': _('Current week'),
                    'url': 'week_view',
                    'validators': ['menu_generator.validators.is_authenticated']
                },
                {
                    'name': _('Register absence'),
                    'url': 'register_absence',
                    'validators': ['menu_generator.validators.is_superuser']
                },
                {
                    'name': _('Personal note filters'),
                    'url': 'list_personal_note_filters',
                    'validators': ['menu_generator.validators.is_superuser']
                }
            ]
        }
    ]
}
