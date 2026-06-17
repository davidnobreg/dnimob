from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admin', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='logentry',
            name='action_time',
            field=models.DateTimeField(auto_now=True, verbose_name='action time'),
        ),
    ]
