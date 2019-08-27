from django.utils.translation import ugettext_lazy as _

MENUS = {
    'NAV_MENU_CORE': [
        {
            'name': _('Class register'),
            'url': '#',
            'root': True,
            'validators': ['menu_generator.validators.is_authenticated'],
            'submenu': [
                {
                    'name': _('Current lesson'),
                    'url': 'lesson',
                    'validators': ['menu_generator.validators.is_authenticated']
                },
                {
                    'name': _('Current week'),
                    'url': 'group_week',
                    'validators': ['menu_generator.validators.is_authenticated']
                }
            ]
        }
    ]
}
