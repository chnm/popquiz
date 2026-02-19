import re
from django.db import migrations, models


def backfill_years_running(apps, schema_editor):
    """
    Migrate existing TV series items that have a year range embedded in their title
    (e.g. "Breaking Bad (2008–2013)") to use the new years_running field.
    Strips the range from the title and sets the debut year correctly.
    """
    Item = apps.get_model('catalog', 'Item')
    # Match year ranges using en-dash or regular hyphen, with optional trailing space
    pattern = re.compile(r'\s*\((\d{4}[–\-]\d*\s*)\)')
    for item in Item.objects.all():
        match = pattern.search(item.title)
        if match:
            years_running = match.group(1).strip()
            # Strip the range from the title
            item.title = pattern.sub('', item.title).strip()
            item.years_running = years_running
            # Also correct the debut year if not already set
            if not item.year:
                debut = re.match(r'(\d{4})', years_running)
                if debut:
                    item.year = int(debut.group(1))
            item.save()


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0008_create_catalog_managers_group'),
    ]

    operations = [
        migrations.AddField(
            model_name='item',
            name='years_running',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.RunPython(backfill_years_running, migrations.RunPython.noop),
    ]
