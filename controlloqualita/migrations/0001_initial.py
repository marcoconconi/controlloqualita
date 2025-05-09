# Generated by Django 5.2 on 2025-04-22 13:57

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='ImportRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('identificativo_richiesta', models.CharField(help_text='Codice univoco della richiesta importata.', max_length=100, unique=True)),
                ('codice_fiscale_richiesta', models.CharField(db_index=True, max_length=16)),
                ('codice_fiscale_attuale', models.CharField(db_index=True, max_length=16)),
                ('ragione_sociale_cliente', models.CharField(blank=True, max_length=255, null=True)),
                ('servizio', models.CharField(blank=True, max_length=255, null=True)),
                ('data_evasione', models.DateField(blank=True, null=True)),
                ('operatore', models.CharField(blank=True, max_length=100, null=True)),
                ('raw_data', models.JSONField(blank=True, help_text='Tutti i campi grezzi del CSV in JSON, per future estensioni.', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
