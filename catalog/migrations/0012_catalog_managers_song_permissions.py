from django.db import migrations


def add_song_permissions_to_catalog_managers(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')

    group = Group.objects.filter(name='Catalog Managers').first()
    if not group:
        return

    # Add full CRUD on Song and SongUpvote
    ct_music = ContentType.objects.filter(
        app_label='catalog', model__in=['song', 'songupvote']
    )
    perms = Permission.objects.filter(content_type__in=ct_music)
    group.permissions.add(*perms)


def remove_song_permissions_from_catalog_managers(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')

    group = Group.objects.filter(name='Catalog Managers').first()
    if not group:
        return

    ct_music = ContentType.objects.filter(
        app_label='catalog', model__in=['song', 'songupvote']
    )
    perms = Permission.objects.filter(content_type__in=ct_music)
    group.permissions.remove(*perms)


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0011_item_musicbrainz_id_song_songupvote'),
        ('contenttypes', '0002_remove_content_type_name'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(
            add_song_permissions_to_catalog_managers,
            remove_song_permissions_from_catalog_managers,
        ),
    ]
