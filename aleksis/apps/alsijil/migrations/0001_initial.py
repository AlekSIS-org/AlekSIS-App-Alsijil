# Generated by Django 3.0.6 on 2020-05-29 10:29

import django.contrib.postgres.fields.jsonb
import django.contrib.sites.managers
import django.db.models.deletion
from django.db import migrations, models

import aleksis.apps.alsijil.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("core", "0001_initial"),
        ("chronos", "0001_initial"),
        ("sites", "0002_alter_domain_unique"),
    ]

    operations = [
        migrations.CreateModel(
            name="PersonalNoteFilter",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "extended_data",
                    django.contrib.postgres.fields.jsonb.JSONField(
                        default=dict, editable=False
                    ),
                ),
                (
                    "identifier",
                    models.CharField(
                        max_length=30,
                        unique=True,
                        validators=[aleksis.apps.alsijil.models.isidentifier],
                        verbose_name="Identifier",
                    ),
                ),
                (
                    "description",
                    models.CharField(
                        blank=True,
                        max_length=60,
                        unique=True,
                        verbose_name="Description",
                    ),
                ),
                (
                    "regex",
                    models.CharField(
                        max_length=100, unique=True, verbose_name="Match expression"
                    ),
                ),
                (
                    "site",
                    models.ForeignKey(
                        default=1,
                        editable=False,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="sites.Site",
                    ),
                ),
            ],
            options={
                "verbose_name": "Personal note filter",
                "verbose_name_plural": "Personal note filters",
                "ordering": ["identifier"],
            },
            managers=[("objects", django.contrib.sites.managers.CurrentSiteManager()),],
        ),
        migrations.CreateModel(
            name="PersonalNote",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "extended_data",
                    django.contrib.postgres.fields.jsonb.JSONField(
                        default=dict, editable=False
                    ),
                ),
                ("week", models.IntegerField()),
                ("absent", models.BooleanField(default=False)),
                ("late", models.IntegerField(default=0)),
                ("excused", models.BooleanField(default=False)),
                ("remarks", models.CharField(blank=True, max_length=200)),
                (
                    "lesson_period",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="personal_notes",
                        to="chronos.LessonPeriod",
                    ),
                ),
                (
                    "person",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="personal_notes",
                        to="core.Person",
                    ),
                ),
                (
                    "site",
                    models.ForeignKey(
                        default=1,
                        editable=False,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="sites.Site",
                    ),
                ),
            ],
            options={
                "verbose_name": "Personal note",
                "verbose_name_plural": "Personal notes",
                "ordering": [
                    "lesson_period__lesson__date_start",
                    "week",
                    "lesson_period__period__weekday",
                    "lesson_period__period__period",
                    "person__last_name",
                    "person__first_name",
                ],
                "unique_together": {("lesson_period", "week", "person")},
            },
            managers=[("objects", django.contrib.sites.managers.CurrentSiteManager()),],
        ),
        migrations.CreateModel(
            name="LessonDocumentation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "extended_data",
                    django.contrib.postgres.fields.jsonb.JSONField(
                        default=dict, editable=False
                    ),
                ),
                ("week", models.IntegerField()),
                (
                    "topic",
                    models.CharField(
                        blank=True, max_length=200, verbose_name="Lesson topic"
                    ),
                ),
                (
                    "homework",
                    models.CharField(
                        blank=True, max_length=200, verbose_name="Homework"
                    ),
                ),
                (
                    "lesson_period",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="documentations",
                        to="chronos.LessonPeriod",
                    ),
                ),
                (
                    "site",
                    models.ForeignKey(
                        default=1,
                        editable=False,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="sites.Site",
                    ),
                ),
            ],
            options={
                "verbose_name": "Lesson documentation",
                "verbose_name_plural": "Lesson documentations",
                "ordering": [
                    "lesson_period__lesson__date_start",
                    "week",
                    "lesson_period__period__weekday",
                    "lesson_period__period__period",
                ],
                "unique_together": {("lesson_period", "week")},
            },
            managers=[("objects", django.contrib.sites.managers.CurrentSiteManager()),],
        ),
    ]
