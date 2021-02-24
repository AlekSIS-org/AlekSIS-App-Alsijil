# Generated by Django 3.1.5 on 2021-01-10 15:48

import aleksis.apps.chronos.util.date
import django.contrib.sites.managers
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('chronos', '0004_substitution_extra_lesson_year'),
        ('alsijil', '0009_group_roles'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='lessondocumentation',
            options={'ordering': ['year', 'week', 'lesson_period__period__weekday', 'lesson_period__period__period'], 'verbose_name': 'Lesson documentation', 'verbose_name_plural': 'Lesson documentations'},
        ),
        migrations.AlterModelOptions(
            name='personalnote',
            options={'ordering': ['year', 'week', 'lesson_period__period__weekday', 'lesson_period__period__period', 'person__last_name', 'person__first_name'], 'verbose_name': 'Personal note', 'verbose_name_plural': 'Personal notes'},
        ),
        migrations.AddField(
            model_name='lessondocumentation',
            name='event',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='documentations', to='chronos.event'),
        ),
        migrations.AddField(
            model_name='lessondocumentation',
            name='extra_lesson',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='documentations', to='chronos.extralesson'),
        ),
        migrations.AddField(
            model_name='personalnote',
            name='event',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='personal_notes', to='chronos.event'),
        ),
        migrations.AddField(
            model_name='personalnote',
            name='extra_lesson',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='personal_notes', to='chronos.extralesson'),
        ),
        migrations.AlterField(
            model_name='lessondocumentation',
            name='lesson_period',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='documentations', to='chronos.lessonperiod'),
        ),
        migrations.AlterField(
            model_name='lessondocumentation',
            name='week',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='lessondocumentation',
            name='year',
            field=models.IntegerField(blank=True, default=aleksis.apps.chronos.util.date.get_current_year, null=True, verbose_name='Year'),
        ),
        migrations.AlterField(
            model_name='personalnote',
            name='lesson_period',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='personal_notes', to='chronos.lessonperiod'),
        ),
        migrations.AlterField(
            model_name='personalnote',
            name='week',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='personalnote',
            name='year',
            field=models.IntegerField(blank=True, default=aleksis.apps.chronos.util.date.get_current_year, null=True, verbose_name='Year'),
        ),
        migrations.AlterUniqueTogether(
            name='lessondocumentation',
            unique_together=set(),
        ),
        migrations.AlterUniqueTogether(
            name='personalnote',
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name='lessondocumentation',
            constraint=models.CheckConstraint(check=models.Q(models.Q(('event__isnull', True), ('extra_lesson__isnull', True), ('lesson_period__isnull', False), ('week__isnull', False), ('year__isnull', False)), models.Q(('event__isnull', False), ('extra_lesson__isnull', True), ('lesson_period__isnull', True), ('week__isnull', True), ('year__isnull', True)), models.Q(('event__isnull', True), ('extra_lesson__isnull', False), ('lesson_period__isnull', True), ('week__isnull', True), ('year__isnull', True)), _connector='OR'), name='one_relation_only_lesson_documentation'),
        ),
        migrations.AddConstraint(
            model_name='personalnote',
            constraint=models.CheckConstraint(check=models.Q(models.Q(('event__isnull', True), ('extra_lesson__isnull', True), ('lesson_period__isnull', False), ('week__isnull', False), ('year__isnull', False)), models.Q(('event__isnull', False), ('extra_lesson__isnull', True), ('lesson_period__isnull', True), ('week__isnull', True), ('year__isnull', True)), models.Q(('event__isnull', True), ('extra_lesson__isnull', False), ('lesson_period__isnull', True), ('week__isnull', True), ('year__isnull', True)), _connector='OR'), name='one_relation_only_personal_note'),
        ),
    ]