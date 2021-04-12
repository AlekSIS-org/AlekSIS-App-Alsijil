# Generated by Django 3.1.7 on 2021-03-21 17:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chronos', '0004_substitution_extra_lesson_year'),
        ('alsijil', '0011_tardiness_positive'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='lessondocumentation',
            unique_together={('lesson_period', 'week', 'year', 'event', 'extra_lesson')},
        ),
        migrations.AlterUniqueTogether(
            name='personalnote',
            unique_together={('lesson_period', 'week', 'year', 'event', 'extra_lesson')},
        ),
    ]