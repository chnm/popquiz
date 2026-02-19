from django.db import migrations


def create_catalog_managers_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')

    group, _ = Group.objects.get_or_create(name='Catalog Managers')

    # Full CRUD on Category and Item
    ct_catalog = ContentType.objects.filter(app_label='catalog', model__in=['category', 'item'])
    perms = Permission.objects.filter(content_type__in=ct_catalog)
    group.permissions.set(perms)


def remove_catalog_managers_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name='Catalog Managers').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0007_add_item_label_to_category'),
        ('contenttypes', '0002_remove_content_type_name'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(
            create_catalog_managers_group,
            remove_catalog_managers_group,
        ),
    ]
