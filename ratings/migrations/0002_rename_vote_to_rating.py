# Generated migration for vote to rating refactor
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def convert_vote_data(apps, schema_editor):
    """Convert old vote choices to new rating levels."""
    # Get the model using the old name since it's the same table
    db_alias = schema_editor.connection.alias

    # Run raw SQL to update the data
    with schema_editor.connection.cursor() as cursor:
        # Convert old values to new values
        cursor.execute("""
            UPDATE votes_vote
            SET choice = CASE
                WHEN choice = 'no' THEN 'disliked'
                WHEN choice = 'meh' THEN 'okay'
                WHEN choice = 'yes' THEN 'liked'
                WHEN choice = 'no_answer' THEN 'no_rating'
                ELSE choice
            END
        """)


def reverse_convert_vote_data(apps, schema_editor):
    """Reverse conversion for rollback."""
    db_alias = schema_editor.connection.alias

    with schema_editor.connection.cursor() as cursor:
        cursor.execute("""
            UPDATE votes_vote
            SET choice = CASE
                WHEN choice = 'disliked' THEN 'no'
                WHEN choice = 'okay' THEN 'meh'
                WHEN choice = 'liked' THEN 'yes'
                WHEN choice = 'no_rating' THEN 'no_answer'
                ELSE choice
            END
        """)


class Migration(migrations.Migration):

    dependencies = [
        ('ratings', '0001_initial'),
        ('catalog', '0006_attribute_64_movies_to_qtrinh2'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Step 1: Update the field choices (no column rename - use db_column instead)
        migrations.AlterField(
            model_name='vote',
            name='choice',
            field=models.CharField(
                choices=[
                    ('loved', '🤩 Loved it'),
                    ('liked', '🙂 Liked it'),
                    ('okay', '😐 It was okay'),
                    ('disliked', '😕 Disliked it'),
                    ('hated', '😡 Hated it'),
                    ('no_rating', '⏭️ Not yet rated')
                ],
                default='no_rating',
                max_length=10,
                db_column='choice'
            ),
        ),
        # Step 2: Convert the data
        migrations.RunPython(convert_vote_data, reverse_convert_vote_data),
        # Step 3: Update related_name references
        migrations.AlterField(
            model_name='vote',
            name='item',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='ratings',
                to='catalog.item'
            ),
        ),
        migrations.AlterField(
            model_name='vote',
            name='user',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='ratings',
                to=settings.AUTH_USER_MODEL
            ),
        ),
        # Step 4: Rename the model (this updates Django's state but not the DB table)
        migrations.RenameModel(
            old_name='Vote',
            new_name='Rating',
        ),
        # Step 5: Now rename the field in Django's state (column stays 'choice' via db_column)
        migrations.RenameField(
            model_name='rating',
            old_name='choice',
            new_name='rating',
        ),
    ]
