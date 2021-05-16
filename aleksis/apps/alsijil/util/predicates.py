from typing import Any, Union

from django.contrib.auth.models import User

from rules import predicate

from aleksis.apps.chronos.models import Event, ExtraLesson, LessonPeriod
from aleksis.core.models import Group, Person
from aleksis.core.util.predicates import check_object_permission

from ..models import PersonalNote


@predicate
def is_none(user: User, obj: Any) -> bool:
    """Predicate that checks if the provided object is None-like."""
    return not bool(obj)


@predicate
def is_lesson_teacher(user: User, obj: Union[LessonPeriod, Event, ExtraLesson]) -> bool:
    """Predicate for teachers of a lesson.

    Checks whether the person linked to the user is a teacher in the register object.
    If the register object is a lesson period and has a substitution linked,
    this will **only** check if the person is one of the substitution teachers.
    """
    if obj:
        return user.person in obj.get_teachers().all()
    return False


@predicate
def is_lesson_original_teacher(user: User, obj: Union[LessonPeriod, Event, ExtraLesson]) -> bool:
    """Predicate for teachers of a lesson.

    Checks whether the person linked to the user is a teacher in the register object.
    If the register object is a lesson period and has a substitution linked,
    this will **also** check if the person is one of the substitution teachers.
    """
    if obj:
        if isinstance(obj, LessonPeriod) and user.person in obj.lesson.teachers.all():
            return True
        return user.person in obj.get_teachers().all()
    return False


@predicate
def is_lesson_participant(user: User, obj: LessonPeriod) -> bool:
    """Predicate for participants of a lesson.

    Checks whether the person linked to the user is a member in
    the groups linked to the given LessonPeriod.
    """
    if hasattr(obj, "lesson") or hasattr(obj, "groups"):
        for group in obj.get_groups().all():
            if user.person in list(group.members.all()):
                return True
    return False


@predicate
def is_lesson_parent_group_owner(user: User, obj: LessonPeriod) -> bool:
    """
    Predicate for parent group owners of a lesson.

    Checks whether the person linked to the user is the owner of
    any parent groups of any groups of the given LessonPeriods lesson.
    """
    if hasattr(obj, "lesson") or hasattr(obj, "groups"):
        for group in obj.get_groups().all():
            for parent_group in group.parent_groups.all():
                if user.person in list(parent_group.owners.all()):
                    return True
    return False


@predicate
def is_group_owner(user: User, obj: Union[Group, Person]) -> bool:
    """Predicate for group owners of a given group.

    Checks whether the person linked to the user is the owner of the given group.
    If there isn't provided a group, it will return `False`.
    """
    if isinstance(obj, Group):
        if user.person in obj.owners.all():
            return True

    return False


@predicate
def is_person_group_owner(user: User, obj: Person) -> bool:
    """
    Predicate for group owners of any group.

    Checks whether the person linked to the user is
    the owner of any group of the given person.
    """
    if obj:
        for group in use_prefetched(obj, "member_of"):
            if user.person in use_prefetched(group, "owners"):
                return True
        return False
    return False


def use_prefetched(obj, attr):
    prefetched_attr = f"{attr}_prefetched"
    if hasattr(obj, prefetched_attr):
        return getattr(obj, prefetched_attr)
    return getattr(obj, attr).all()


@predicate
def is_person_primary_group_owner(user: User, obj: Person) -> bool:
    """
    Predicate for group owners of the person's primary group.

    Checks whether the person linked to the user is
    the owner of the primary group of the given person.
    """
    if obj.primary_group:
        return user.person in use_prefetched(obj.primary_group, "owners")
    return False


def has_person_group_object_perm(perm: str):
    """Predicate builder for permissions on a set of member groups.

    Checks whether a user has a permission on any group of a person.
    """
    name = f"has_person_group_object_perm:{perm}"

    @predicate(name)
    def fn(user: User, obj: Person) -> bool:
        groups = use_prefetched(obj, "member_of")
        for group in groups:
            if check_object_permission(user, perm, group, checker_obj=obj):
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
        if user.person in obj.members.all():
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
            groups = obj.lesson.groups.all()
            for group in groups:
                if check_object_permission(user, perm, group, checker_obj=obj):
                    return True
        return False

    return fn


def has_personal_note_group_perm(perm: str):
    """Predicate builder for permissions on personal notes.

    Checks whether a user has a permission on any group of a person of a PersonalNote.
    """
    name = f"has_personal_note_person_or_group_perm:{perm}"

    @predicate(name)
    def fn(user: User, obj: PersonalNote) -> bool:
        if hasattr(obj, "person"):
            groups = obj.person.member_of.all()
            for group in groups:
                if check_object_permission(user, perm, group, checker_obj=obj):
                    return True
        return False

    return fn


@predicate
def is_own_personal_note(user: User, obj: PersonalNote) -> bool:
    """Predicate for users referred to in a personal note.

    Checks whether the user referred to in a PersonalNote is the active user.
    """
    if hasattr(obj, "person") and obj.person is user.person:
        return True
    return False


@predicate
def is_personal_note_lesson_teacher(user: User, obj: PersonalNote) -> bool:
    """Predicate for teachers of a register object linked to a personal note.

    Checks whether the person linked to the user is a teacher
    in the register object linked to the personal note.
    If the register object is a lesson period and has a substitution linked,
    this will **only** check if the person is one of the substitution teachers.
    """
    if hasattr(obj, "register_object"):
        return user.person in obj.register_object.get_teachers().all()
    return False


@predicate
def is_personal_note_lesson_original_teacher(user: User, obj: PersonalNote) -> bool:
    """Predicate for teachers of a register object linked to a personal note.

    Checks whether the person linked to the user is a teacher
    in the register object linked to the personal note.
    If the register object is a lesson period and has a substitution linked,
    this will **also** check if the person is one of the substitution teachers.
    """
    if hasattr(obj, "register_object"):
        if (
            isinstance(obj.register_object, LessonPeriod)
            and user.person in obj.lesson_period.lesson.teachers.all()
        ):
            return True

        return user.person in obj.register_object.get_teachers().all()
    return False


@predicate
def is_personal_note_lesson_parent_group_owner(user: User, obj: PersonalNote) -> bool:
    """
    Predicate for parent group owners of a lesson referred to in the lesson of a personal note.

    Checks whether the person linked to the user is the owner of
    any parent groups of any groups of the given LessonPeriod lesson of the given PersonalNote.
    """
    if hasattr(obj, "register_object"):
        for group in obj.register_object.get_groups().all():
            for parent_group in group.parent_groups.all():
                if user.person in list(parent_group.owners.all()):
                    return True
    return False


@predicate
def is_teacher(user: User, obj: Person) -> bool:
    """Predicate which checks if the provided object is a teacher."""
    return user.person.is_teacher


@predicate
def is_group_role_assignment_group_owner(user: User, obj: Union[Group, Person]) -> bool:
    """Predicate for group owners of a group role assignment.

    Checks whether the person linked to the user is the owner of the groups
    linked to the given group role assignment.
    If there isn't provided a group role assignment, it will return `False`.
    """
    if obj:
        for group in obj.groups.all():
            if user.person in list(group.owners.all()):
                return True
    return False


@predicate
def is_owner_of_any_group(user: User, obj):
    """Predicate which checks if the person is group owner of any group."""
    return Group.objects.filter(owners=user.person).exists()
