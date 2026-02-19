from django.db import migrations, models


def migrate_poster_url(apps, schema_editor):
    """
    Split the single poster_url field into image_source_url and image_local_url.
    - Local URLs (starting with /media/) go to image_local_url
    - External URLs (starting with http) go to image_source_url
    """
    Item = apps.get_model('catalog', 'Item')
    for item in Item.objects.exclude(poster_url=''):
        if item.poster_url.startswith('/media/'):
            item.image_local_url = item.poster_url
        else:
            item.image_source_url = item.poster_url
        item.save()


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0009_item_years_running'),
    ]

    operations = [
        migrations.AddField(
            model_name='item',
            name='image_source_url',
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name='item',
            name='image_local_url',
            field=models.URLField(blank=True),
        ),
        migrations.RunPython(migrate_poster_url, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='item',
            name='poster_url',
        ),
    ]
