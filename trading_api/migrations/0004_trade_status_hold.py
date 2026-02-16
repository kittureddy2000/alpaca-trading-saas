# Generated manually - adds 'hold' to Trade status choices

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trading_api', '0003_usersettings_active_indicators'),
    ]

    operations = [
        migrations.AlterField(
            model_name='trade',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('filled', 'Filled'),
                    ('partially_filled', 'Partially Filled'),
                    ('canceled', 'Canceled'),
                    ('rejected', 'Rejected'),
                    ('hold', 'Hold'),
                ],
                default='pending',
                max_length=20,
            ),
        ),
    ]
