from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('parking', '0002_parkinglot_latitude_parkinglot_longitude_and_more'),
    ]

    operations = [
        # MongoDB is schemaless — no ALTER TABLE needed.
        # SeparateDatabaseAndState updates Django's model state without
        # running any SQL/collection change against the database.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name='parkinglot',
                    name='cluster_label',
                ),
            ],
            database_operations=[],
        ),
    ]
