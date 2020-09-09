from django import template

import datetime

register = template.Library()


@register.filter("to_time")
def get_time_from_minutes(minutes: int) -> datetime.timedelta:
    """Get a time object from a number of minutes."""
    delta = datetime.timedelta(minutes=minutes)
    time_obj = (datetime.datetime.min + delta).time()

    return time_obj
