from typing import Union

from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from guardian.models import UserObjectPermission

from guardian.shortcuts import get_objects_for_user
from rules import predicate

from aleksis.apps.chronos.models import LessonPeriod
from aleksis.core.models import Group, Person
from aleksis.core.util.core_helpers import get_site_preferences
from aleksis.core.util.predicates import check_object_permission

from ..models import PersonalNote


@predicate
def is_lesson_teacher(user: User, obj: LessonPeriod) -> bool:
    """Predicate for teachers of a lesson.

    Checks whether the person linked to the user is a teacher
    in the lesson or the substitution linked to the given LessonPeriod.
    """
    if obj:
        sub = obj.get_substitution()
        if sub and sub in user.person.lesson_substitutions.all():
            return True
        return user.person in obj.lesson.teachers.all()
    return True


@predicate
def is_lesson_participant(user: User, obj: LessonPeriod) -> bool:
    """Predicate for participants of a lesson.

    Checks whether the person linked to the user is a member in
    the groups linked to the given LessonPeriod.
    """
    if hasattr(obj, "lesson"):
        for group in obj.lesson.groups.all():
            if user.person in list(group.members.all()):
                return True
        return False
    return True


@predicate
def is_lesson_parent_group_owner(user: User, obj: LessonPeriod) -> bool:
    """
    Predicate for parent group owners of a lesson.

    Checks whether the person linked to the user is the owner of
    any parent groups of any groups of the given LessonPeriods lesson.
    """
    if hasattr(obj, "lesson"):
        for group in obj.lesson.groups.all():
            for parent_group in group.parent_groups.all():
                if user.person in list(parent_group.owners.all()):
                    return True
        return False
    return True


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
        return obj.member_of.filter(owners=user.person).exists()
    return False


@predicate
def is_person_primary_group_owner(user: User, obj: Person) -> bool:
    """
    Predicate for group owners of the person's primary group.

    Checks whether the person linked to the user is
    the owner of the primary group of the given person.
    """
    if obj.primary_group:
        return user.person in obj.primary_group.owners.all()
    return False


def has_person_group_object_perm(perm: str):
    """Predicate builder for permissions on a set of member groups.

    Checks whether a user has a permission on any group of a person.
    """
    name = f"has_person_group_object_perm:{perm}"

    ct = ContentType.objects.get_for_model(Group)
    permissions = Permission.objects.filter(content_type=ct, codename=perm)

    @predicate(name)
    def fn(user: User, obj: Person) -> bool:
        groups = obj.member_of.all()
        qs = UserObjectPermission.objects.filter(object_pk__in=list(groups.values_list("pk", flat=True)), content_type=ct, user=user, permission__in=permissions)
        return qs.exists()

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

    ct = ContentType.objects.get_for_model(Group)
    permissions = Permission.objects.filter(content_type=ct, codename=perm)

    @predicate(name)
    def fn(user: User, obj: LessonPeriod) -> bool:
        if hasattr(obj, "lesson"):
            groups = obj.lesson.groups.all()
            qs = UserObjectPermission.objects.filter(object_pk__in=list(groups.values_list("pk", flat=True)), content_type=ct, user=user, permission__in=permissions)
            return qs.exists()
        return False

    return fn


def has_personal_note_group_perm(perm: str):
    """Predicate builder for permissions on personal notes

    Checks whether a user has a permission on any group of a person of a PersonalNote.
    """
    name = f"has_personal_note_person_or_group_perm:{perm}"

    ct = ContentType.objects.get_for_model(Person)
    permissions = Permission.objects.filter(content_type=ct, codename=perm)

    @predicate(name)
    def fn(user: User, obj: PersonalNote) -> bool:
        if hasattr(obj, "person"):
            groups = obj.person.member_of.all()
            qs = UserObjectPermission.objects.filter(object_pk__in=list(groups.values_list("pk", flat=True)), content_type=ct, user=user, permission__in=permissions)
            return qs.exists()
        return False

    return fn


@predicate
def is_own_personal_note(user: User, obj: PersonalNote) -> bool:
    """Predicate for users referred to in a personal note

    Checks whether the user referred to in a PersonalNote is the active user.
    Is configurable via dynamic preferences.
    """
    if hasattr(obj, "person"):
        if (
            get_site_preferences()["alsijil__view_own_personal_notes"]
            and obj.person is user.person
        ):
            return True
        return False


@predicate
def is_personal_note_lesson_teacher(user: User, obj: PersonalNote) -> bool:
    """Predicate for teachers of a lesson referred to in the lesson period of a personal note.

    Checks whether the person linked to the user is a teacher
    in the lesson or the substitution linked to the LessonPeriod of the given PersonalNote.
    """
    if hasattr(obj, "lesson_period"):
        if hasattr(obj.lesson_period, "lesson"):
            sub = obj.lesson_period.get_substitution()
            if sub and user.person in Person.objects.filter(
                lesson_substitutions=obj.lesson_period.get_substitution()
            ):
                return True

            return user.person in obj.lesson_period.lesson.teachers.all()

        return False
    return False


@predicate
def is_personal_note_lesson_parent_group_owner(user: User, obj: PersonalNote) -> bool:
    """
    Predicate for parent group owners of a lesson referred to in the lesson period of a personal note.

    Checks whether the person linked to the user is the owner of
    any parent groups of any groups of the given LessonPeriod lesson of the given PersonalNote.
    """
    if hasattr(obj, "lesson_period"):
        if hasattr(obj.lesson_period, "lesson"):
            return obj.lesson_period.lesson.groups.filter(
                parent_groups__owners=user.person
            ).exists()
        return False
    return False


@predicate
def has_any_object_absence(user: User) -> bool:
    """
    Predicate which builds a query with all the persons the given users is allowed to register an absence for.
    """
    if Person.objects.filter(member_of__owners=user.person).exists():
        return True
    if get_objects_for_user(user, "core.register_absence_person", Person).exists():
        return True
    if Person.objects.filter(
        member_of__in=get_objects_for_user(user, "core.register_absence_group", Group)
    ).exists():
        return True


@predicate
def is_teacher(user: User, obj: Person) -> bool:
    """Predicate which checks if the provided object is a teacher."""
    return user.person.is_teacher
