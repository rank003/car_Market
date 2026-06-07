from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('listings', '0004_auto_add_choice_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='listing',
            name='car_type',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='listings.cartype'),
        ),
    ]
