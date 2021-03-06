# Generated by Django 3.0.9 on 2020-08-15 09:39

from django.db import migrations, models

import aleksis.apps.chronos.util.date


def migrate_data(apps, schema_editor):
    PersonalNote = apps.get_model("alsijil", "PersonalNote")
    LessonDocumentation = apps.get_model("alsijil", "LessonDocumentation")

    db_alias = schema_editor.connection.alias

    for note in PersonalNote.objects.using(db_alias).all():
        year = note.lesson_period.lesson.validity.date_start.year
        if note.week < int(
            note.lesson_period.lesson.validity.date_start.strftime("%V")
        ):
            year += 1
        note.year = year
        note.save()

    for doc in LessonDocumentation.objects.using(db_alias).all():
        year = doc.lesson_period.lesson.validity.date_start.year
        if doc.week < int(doc.lesson_period.lesson.validity.date_start.strftime("%V")):
            year += 1
        doc.year = year
        doc.save()


class Migration(migrations.Migration):

    dependencies = [
        ("alsijil", "0006_delete_personal_notes_filter"),
    ]

    operations = [
        migrations.AddField(
            model_name="lessondocumentation",
            name="year",
            field=models.IntegerField(
                default=aleksis.apps.chronos.util.date.get_current_year,
                verbose_name="Year",
            ),
        ),
        migrations.AddField(
            model_name="personalnote",
            name="year",
            field=models.IntegerField(
                default=aleksis.apps.chronos.util.date.get_current_year,
                verbose_name="Year",
            ),
        ),
        migrations.RunPython(migrate_data),
    ]
