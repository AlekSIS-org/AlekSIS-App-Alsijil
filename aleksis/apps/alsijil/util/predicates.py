from typing import Union

from django.contrib.auth.models import User

from rules import predicate

from aleksis.apps.chronos.models import LessonPeriod
from aleksis.core.models import Group, Person
from aleksis.core.util.predicates import check_object_permission


@predicate
def is_lesson_teacher(user: User, obj: LessonPeriod) -> bool:
    """Predicate which checks whether the person linked to the user is a teacher in the lesson linked to the given LessonPeriod."""
    return user.person in obj.lesson.teachers

@predicate
def is_lesson_participant(user: User, obj: LessonPeriod) -> bool:
    """Predicate which checks whether the person linked to the user is a member in the groups linked to the given LessonPeriod."""
    return obj.lesson.groups.filter(members=user.person).exists()

@predicate
def is_lesson_parent_group_owner(user: User, obj: LessonPeriod) -> bool:
    """Predicate which checks whether the person linked to the user is the owner of any parent groups of any groups of the given LessonPeriods lesson."""
    return obj.lesson.groups.filter(parent_groups__owners=user.person).exists()

@predicate
def is_group_owner(user: User, obj: Union[Group, Person]) -> bool:
    """Predicate which checks whether the person linked to the user is the owner of the given group."""
    if isinstance(obj, Group):
        if obj.owners.filter(pk=user.person.pk).exists():
            return True

    return False

@predicate
def is_person_group_owner(user: User, obj: Person) -> bool:
    """Predicate which checks whether the person linked to the user is the owner of any group of the given person."""
    return obj.filter(member_of__owners=user.person).exists()

@predicate
def has_person_group_object_perm(perm: str):
    """Predicate which checks whether a user has a permission on any group of a person."""
    name = f"has_person_group_object_perm:{perm}"

    @predicate(name)
    def fn(user: User, obj: Person) -> bool:
        for group in obj.member_of.all():
            if check_object_permission(user, perm, group):
                return True
        return False

    return fn

@predicate
def is_group_member(user: User, obj: Union[Group, Person]) -> bool:
    """Predicate which checks whether the person linked to the user is a member of the given group."""
    if isinstance(obj, Group):
        if obj.members.filter(pk=user.person.pk).exists():
            return True

    return False


def has_lesson_group_object_perm(perm: str):
    """Build predicate which checks whether a user has a permission on any group of a LessonPeriod."""
    name = f"has_lesson_group_object_perm:{perm}"

    @predicate(name)
    def fn(user: User, obj: LessonPeriod) -> bool:
        for group in obj.lesson.groups.all():
            if check_object_permission(user, perm, group):
                return True
        return False

    return fn
