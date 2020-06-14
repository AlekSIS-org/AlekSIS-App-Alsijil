from django.contrib.auth.models import User

from rules import predicate

from aleksis.core.models import Group, Person
from aleksis.core.util.predicates import check_object_permission


def has_lesson_perm(perm: str):
    """Build predicate which checks whether the user is allowed to access the requested lesson notes."""
    name = f"has_lesson_perm:{perm}"

    @predicate(name)
    def fn(user: User, obj: tuple) -> bool:
        if (user.person in obj[0].lesson.teachers) or (set(user.person.member_of).intersection(set(obj[0].lesson.groups))):
            return True
        return check_object_permission(user, perm, obj)

    return fn


@predicate
def has_week_perm(perm: str):
    """Build predicate which checks whether the user is allowed to access the week overview."""
    name = f"has_week_perm:{perm}"

    @predicate(name)
    def fn(user: User, obj: tuple) -> bool:
        if (user.person in obj[0].lesson.teachers) or (set(user.person.member_of).intersection(set(obj[0].lesson.groups))):
            return True
        return check_object_permission(user, perm, obj)

    return fn
