from django.utils.translation import gettext as _

MENUS = {
    'NAV_MENU_CORE': [
        {
            'name': _('Class register'),
            'url': '#',
            'root': True,
            'submenu': [
                {
                    'name': _('Current lesson'),
                    'url': 'lesson',
                    'validators': ['menu_generator.validators.is_authenticated']
                }
            ]
        }
    ]
}
