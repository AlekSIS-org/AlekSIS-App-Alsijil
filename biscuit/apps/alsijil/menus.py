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
                    'name': _('Manage absence'),
                    'url': 'manage_absence',
                    'validators': ['menu_generator.validators.is_superuser']
                }
            ]
        }
    ]
}
