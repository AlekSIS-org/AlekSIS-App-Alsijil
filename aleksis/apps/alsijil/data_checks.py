import logging

from django.contrib.contenttypes.models import ContentType
from django.db.models import F
from django.utils.translation import gettext as _

import reversion
from calendarweek import CalendarWeek

from aleksis.core.util.core_helpers import celery_optional


class SolveOption:
    name: str = "default"
    verbose_name: str = ""

    @classmethod
    def solve(cls, check_result: "DataCheckResult"):
        pass


class IgnoreSolveOption(SolveOption):
    name = "ignore"
    verbose_name = _("Ignore problem")

    @classmethod
    def solve(cls, check_result: "DataCheckResult"):
        check_result.solved = True
        check_result.save()


class DataCheck:
    name: str = ""
    verbose_name: str = ""
    problem_name: str = ""

    solve_options = {IgnoreSolveOption.name: IgnoreSolveOption}

    @classmethod
    def check_data(cls):
        pass

    @classmethod
    def solve(cls, check_result: "DataCheckResult", solve_option: str = "default"):
        with reversion.create_revision():
            cls.solve_options[solve_option].solve(check_result)


class DeleteRelatedObjectSolveOption(SolveOption):
    name = "delete"
    verbose_name = _("Delete object")

    @classmethod
    def solve(cls, check_result: "DataCheckResult"):
        check_result.related_object.delete()
        check_result.delete()


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
        from .models import PersonalNote, DataCheckResult

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


DATA_CHECKS = [NoPersonalNotesInCancelledLessonsDataCheck]
DATA_CHECKS_BY_NAME = {check.name: check for check in DATA_CHECKS}
DATA_CHECKS_CHOICES = [(check.name, check.verbose_name) for check in DATA_CHECKS]


@celery_optional
def check_data():
    for check in DATA_CHECKS:
        logging.info(f"Run check: {check.verbose_name}")
        check.check_data()
