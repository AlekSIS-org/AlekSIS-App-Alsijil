# Generated by Django 2.2.5 on 2019-11-20 14:21

import django.db.models.deletion
from django.db import migrations, models

import aleksis.apps.alsijil.models
import aleksis.core.util.core_helpers


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_activity_notification"),
        ("alsijil", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PersonalNoteFilter",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "identifier",
                    models.CharField(
                        max_length=30,
                        validators=[aleksis.apps.alsijil.models.isidentifier],
                        verbose_name="Identifier",
                    ),
                ),
                (
                    "description",
                    models.CharField(
                        blank=True, max_length=60, verbose_name="Description"
                    ),
                ),
                (
                    "regex",
                    models.CharField(max_length=100, verbose_name="Match expression"),
                ),
                (
                    "school",
                    models.ForeignKey(
                        default=1,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="core.School",
                    ),
                ),
            ],
            options={
                "ordering": ["identifier"],
                "unique_together": {
                    ("school", "regex"),
                    ("school", "description"),
                    ("school", "identifier"),
                },
            },
        ),
    ]