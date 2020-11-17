import logging

from django.contrib.contenttypes.models import ContentType
from django.db.models import F
from django.utils.translation import gettext as _

from calendarweek import CalendarWeek

from aleksis.core.data_checks import (
    DATA_CHECK_REGISTRY,
    DataCheck,
    IgnoreSolveOption,
    SolveOption,
)


class DeleteRelatedObjectSolveOption(SolveOption):
    name = "delete"
    verbose_name = _("Delete object")

    @classmethod
    def solve(cls, check_result: "DataCheckResult"):
        check_result.related_object.delete()
        check_result.delete()


class SetGroupsOfPersonWithCurrentGroupsOfPersonSolveOption(SolveOption):
    name = "set_groups_of_person"
    verbose_name = _("Set current groups")

    @classmethod
    def solve(cls, check_result: "DataCheckResult"):
        person = check_result.related_object.person
        check_result.related_object.groups_of_person.set(person.member_of.all())
        check_result.delete()


@DATA_CHECK_REGISTRY.register
class NoPersonalNotesInCancelledLessonsDataCheck(DataCheck):
    name = "no_personal_notes_in_cancelled_lessons"
    verbose_name = _("Ensure that there are no personal notes in cancelled lessons")
    problem_name = _("The personal note is related to a cancelled lesson.")
    solve_options = {
        DeleteRelatedObjectSolveOption.name: DeleteRelatedObjectSolveOption,
        IgnoreSolveOption.name: IgnoreSolveOption,
    }

    @classmethod
    def check_data(cls):
        from aleksis.core.models import DataCheckResult
        from .models import PersonalNote

        ct = ContentType.objects.get_for_model(PersonalNote)

        personal_notes = PersonalNote.objects.filter(
            lesson_period__substitutions__cancelled=True,
            lesson_period__substitutions__week=F("week"),
            lesson_period__substitutions__year=F("year"),
        ).prefetch_related("lesson_period", "lesson_period__substitutions")

        for note in personal_notes:
            logging.info(f"Check personal note {note}")
            sub = note.lesson_period.get_substitution(
                CalendarWeek(week=note.week, year=note.year)
            )
            result = DataCheckResult.objects.get_or_create(
                check=cls.name, content_type=ct, object_id=note.id
            )


@DATA_CHECK_REGISTRY.register
class NoGroupsOfPersonsSetInPersonalNotesDataCheck(DataCheck):
    name = "no_groups_of_persons_set_in_personal_notes"
    verbose_name = _("Ensure that 'groups_of_person' is set for every personal note")
    problem_name = _("The personal note has no group in 'groups_of_person'.")
    solve_options = {
        SetGroupsOfPersonWithCurrentGroupsOfPersonSolveOption.name: SetGroupsOfPersonWithCurrentGroupsOfPersonSolveOption,
        DeleteRelatedObjectSolveOption.name: DeleteRelatedObjectSolveOption,
        IgnoreSolveOption.name: IgnoreSolveOption,
    }

    @classmethod
    def check_data(cls):
        from aleksis.core.models import DataCheckResult
        from .models import PersonalNote

        ct = ContentType.objects.get_for_model(PersonalNote)

        personal_notes = PersonalNote.objects.filter(groups_of_person__isnull=True)

        for note in personal_notes:
            logging.info(f"Check personal note {note}")
            result = DataCheckResult.objects.get_or_create(
                check=cls.name, content_type=ct, object_id=note.id
            )
