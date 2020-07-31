# Generated by Django 3.0.8 on 2020-07-22 17:29

from django.db import migrations, models


def add_groups(apps, schema_editor):
    PersonalNote = apps.get_model("alsijil", "PersonalNote")

    db_alias = schema_editor.connection.alias

    for personal_note in PersonalNote.objects.using(db_alias).all():
        groups = list(personal_note.person.member_of.using(db_alias).all())
        personal_note.groups_of_person.set(groups)
        personal_note.save()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_drop_image_cropping"),
        ("alsijil", "0002_excuse_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="personalnote",
            name="groups_of_person",
            field=models.ManyToManyField(
                related_name="_personalnote_groups_of_person_+", to="core.Group"
            ),
        ),
        migrations.RunPython(add_groups),
    ]
