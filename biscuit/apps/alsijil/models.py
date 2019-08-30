from django.db import models
from django.utils.translation import ugettext_lazy as _

from biscuit.core.mixins import SchoolRelated


class PersonalNote(SchoolRelated):
    person = models.ForeignKey('core.Person', models.CASCADE)

    week = models.IntegerField()
    lesson_period = models.ForeignKey('chronos.LessonPeriod', models.CASCADE)

    absent = models.BooleanField(default=False)
    late = models.IntegerField(default=0)
    excused = models.BooleanField(default=False)

    remarks = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = [['school', 'lesson_period', 'week', 'person']]
        ordering = ['lesson_period__lesson__date_start', 'week', 'lesson_period__period__weekday', 'lesson_period__period__period', 'person__last_name', 'person__first_name']


class LessonDocumentation(SchoolRelated):
    week = models.IntegerField()
    lesson_period = models.ForeignKey('chronos.LessonPeriod', models.CASCADE, related_name='documentations')

    topic = models.CharField(verbose_name=_('Lesson topic'), max_length=200, blank=True)
    homework = models.CharField(verbose_name=_('Homework'), max_length=200, blank=True)

    class Meta:
        unique_together = [['school', 'lesson_period', 'week']]
        ordering = ['lesson_period__lesson__date_start', 'week', 'lesson_period__period__weekday', 'lesson_period__period__period']
