from typing import Union

from django.contrib.auth.models import User

from rules import predicate

from aleksis.apps.chronos.models import LessonPeriod
from aleksis.core.models import Group, Person
from aleksis.core.util.predicates import check_object_permission


@predicate
def is_lesson_teacher(user: User, obj: LessonPeriod) -> bool:
    """Predicate for teachers of a lesson.

    Checks whether the person linked to the user is a teacher
    in the lesson or the substitution linked to the given LessonPeriod.
    """
    if hasattr(obj, "lesson"):
        return user.person in obj.lesson.teachers.all() or user.person in obj.substitutions.teachers.all()
    return True


@predicate
def is_lesson_participant(user: User, obj: LessonPeriod) -> bool:
    """Predicate for participants of a lesson.

    Checks whether the person linked to the user is a member in
    the groups linked to the given LessonPeriod.
    """
    if hasattr(obj, "lesson"):
        return obj.lesson.groups.filter(members=user.person).exists()
    return True


@predicate
def is_lesson_parent_group_owner(user: User, obj: LessonPeriod) -> bool:
    """
    Predicate for parent group owners of a lesson.

    Checks whether the person linked to the user is the owner of
    any parent groups of any groups of the given LessonPeriods lesson.
    """
    if hasattr(obj, "lesson"):
        return obj.lesson.groups.filter(parent_groups__owners=user.person).exists()
    return True


@predicate
def is_group_owner(user: User, obj: Union[Group, Person]) -> bool:
    """Predicate for group owners of a given group.

    Checks whether the person linked to the user is the owner of the given group.
    If there isn't provided a group, it will return `False`.
    """
    if isinstance(obj, Group):
        if obj.owners.filter(pk=user.person.pk).exists():
            return True

    return False


@predicate
def is_person_group_owner(user: User, obj: Person) -> bool:
    """
    Predicate for group owners of any group.

    Checks whether the person linked to the user is
    the owner of any group of the given person.
    """
    return obj.member_of.filter(owners=user.person).exists()


def has_person_group_object_perm(perm: str):
    """Predicate builder for permissions on a set of member groups.

    Checks whether a user has a permission on any group of a person.
    """
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
    """Predicate for group membership.

    Checks whether the person linked to the user is a member of the given group.
    If there isn't provided a group, it will return `False`.
    """
    if isinstance(obj, Group):
        if obj.members.filter(pk=user.person.pk).exists():
            return True

    return False


def has_lesson_group_object_perm(perm: str):
    """Predicate builder for permissions on lesson groups.

    Checks whether a user has a permission on any group of a LessonPeriod.
    """
    name = f"has_lesson_group_object_perm:{perm}"

    @predicate(name)
    def fn(user: User, obj: LessonPeriod) -> bool:
        if hasattr(obj, "lesson"):
            for group in obj.lesson.groups.all():
                if check_object_permission(user, perm, group):
                    return True
            return False
        return True

    return fn
