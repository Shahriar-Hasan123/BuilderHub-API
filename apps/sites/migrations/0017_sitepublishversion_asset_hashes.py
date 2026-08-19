from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sites", "0016_remove_siteimage_device_siteimage_image_type_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="sitepublishversion",
            name="asset_hashes",
            field=models.JSONField(
                default=dict,
                help_text="Mapping of editable asset paths to their content hashes.",
            ),
        ),
    ]