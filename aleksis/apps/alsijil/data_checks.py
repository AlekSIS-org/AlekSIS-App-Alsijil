import logging

from django.db.models import F
from django.db.models.query_utils import Q
from django.utils.translation import gettext as _

from aleksis.core.data_checks import DataCheck, IgnoreSolveOption, SolveOption


class DeleteRelatedObjectSolveOption(SolveOption):
    name = "delete"
    verbose_name = _("Delete object")

    @classmethod
    def solve(cls, check_result: "DataCheckResult"):
        check_result.related_object.delete()
        check_result.delete()


class SetGroupsWithCurrentGroupsSolveOption(SolveOption):
    name = "set_groups_of_person"
    verbose_name = _("Set current groups")

    @classmethod
    def solve(cls, check_result: "DataCheckResult"):
        person = check_result.related_object.person
        check_result.related_object.groups_of_person.set(person.member_of.all())
        check_result.delete()


class ResetPersonalNoteSolveOption(SolveOption):
    name = "reset_personal_note"
    verbose_name = _("Reset personal note to defaults")

    @classmethod
    def solve(cls, check_result: "DataCheckResult"):
        note = check_result.related_object
        note.reset_values()
        note.save()
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
        from .models import PersonalNote

        personal_notes = (
            PersonalNote.objects.not_empty()
            .filter(
                lesson_period__substitutions__cancelled=True,
                lesson_period__substitutions__week=F("week"),
                lesson_period__substitutions__year=F("year"),
            )
            .prefetch_related("lesson_period", "lesson_period__substitutions")
        )

        for note in personal_notes:
            logging.info(f"Check personal note {note}")
            cls.register_result(note)


class NoGroupsOfPersonsSetInPersonalNotesDataCheck(DataCheck):
    name = "no_groups_of_persons_set_in_personal_notes"
    verbose_name = _("Ensure that 'groups_of_person' is set for every personal note")
    problem_name = _("The personal note has no group in 'groups_of_person'.")
    solve_options = {
        SetGroupsWithCurrentGroupsSolveOption.name: SetGroupsWithCurrentGroupsSolveOption,
        DeleteRelatedObjectSolveOption.name: DeleteRelatedObjectSolveOption,
        IgnoreSolveOption.name: IgnoreSolveOption,
    }

    @classmethod
    def check_data(cls):
        from .models import PersonalNote

        personal_notes = PersonalNote.objects.filter(groups_of_person__isnull=True)

        for note in personal_notes:
            logging.info(f"Check personal note {note}")
            cls.register_result(note)


class LessonDocumentationOnHolidaysDataCheck(DataCheck):
    """Checks for lesson documentation objects on holidays.

    This ignores empty lesson documentation as they are created by default.
    """

    name = "lesson_documentation_on_holidays"
    verbose_name = _("Ensure that there are no filled out lesson documentations on holidays")
    problem_name = _("The lesson documentation is on holidays.")
    solve_options = {
        DeleteRelatedObjectSolveOption.name: DeleteRelatedObjectSolveOption,
        IgnoreSolveOption.name: IgnoreSolveOption,
    }

    @classmethod
    def check_data(cls):
        from aleksis.apps.chronos.models import Holiday

        from .models import LessonDocumentation

        holidays = Holiday.objects.all()

        documentations = LessonDocumentation.objects.not_empty().annotate_date_range()

        q = Q()
        for holiday in holidays:
            q = q | Q(day_end__gte=holiday.date_start, day_start__lte=holiday.date_end)
        documentations = documentations.filter(q)

        for doc in documentations:
            logging.info(f"Lesson documentation {doc} is on holidays")
            cls.register_result(doc)


class PersonalNoteOnHolidaysDataCheck(DataCheck):
    """Checks for personal note objects on holidays.

    This ignores empty personal notes as they are created by default.
    """

    name = "personal_note_on_holidays"
    verbose_name = _("Ensure that there are no filled out personal notes on holidays")
    problem_name = _("The personal note is on holidays.")
    solve_options = {
        DeleteRelatedObjectSolveOption.name: DeleteRelatedObjectSolveOption,
        IgnoreSolveOption.name: IgnoreSolveOption,
    }

    @classmethod
    def check_data(cls):
        from aleksis.apps.chronos.models import Holiday

        from .models import PersonalNote

        holidays = Holiday.objects.all()

        personal_notes = PersonalNote.objects.not_empty().annotate_date_range()

        q = Q()
        for holiday in holidays:
            q = q | Q(day_end__gte=holiday.date_start, day_start__lte=holiday.date_end)
        personal_notes = personal_notes.filter(q)

        for note in personal_notes:
            logging.info(f"Personal note {note} is on holidays")
            cls.register_result(note)


class ExcusesWithoutAbsences(DataCheck):
    name = "excuses_without_absences"
    verbose_name = _("Ensure that there are no excused personal notes without an absence")
    problem_name = _("The personal note is marked as excused, but not as absent.")
    solve_options = {
        ResetPersonalNoteSolveOption.name: ResetPersonalNoteSolveOption,
        IgnoreSolveOption.name: IgnoreSolveOption,
    }

    @classmethod
    def check_data(cls):
        from .models import PersonalNote

        personal_notes = PersonalNote.objects.filter(excused=True, absent=False)

        for note in personal_notes:
            logging.info(f"Check personal note {note}")
            cls.register_result(note)
