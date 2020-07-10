# Generated by Django 3.0.8 on 2020-07-10 10:46

import django.contrib.postgres.fields.jsonb
import django.contrib.sites.managers
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('sites', '0002_alter_domain_unique'),
        ('alsijil', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExcuseType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('extended_data', django.contrib.postgres.fields.jsonb.JSONField(default=dict, editable=False)),
                ('short_name', models.CharField(max_length=255, unique=True, verbose_name='Short name')),
                ('name', models.CharField(max_length=255, unique=True, verbose_name='Name')),
                ('site', models.ForeignKey(default=1, editable=False, on_delete=django.db.models.deletion.CASCADE, to='sites.Site')),
            ],
            options={
                'verbose_name': 'Excuse type',
                'verbose_name_plural': 'Excuse types',
                'ordering': ['name'],
            },
            managers=[
                ('objects', django.contrib.sites.managers.CurrentSiteManager()),
            ],
        ),
        migrations.AddField(
            model_name='personalnote',
            name='excuse_type',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='alsijil.ExcuseType', verbose_name='Excuse type'),
        ),
    ]
