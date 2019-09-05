from django.apps import AppConfig
from django.utils.translation import ugettext as _


class AlsijilConfig(AppConfig):
    name = 'biscuit.apps.alsijil'
    verbose_name = 'BiscuIT - Alsijil (' + _('Class register') + ')'
