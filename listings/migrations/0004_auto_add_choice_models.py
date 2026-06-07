# Generated migration: Add choice models for consistent dropdown data

from django.db import migrations, models
import django.db.models.deletion

def create_initial_choices(apps, schema_editor):
    """Populate choice tables with common/standard values."""
    FuelType = apps.get_model('listings', 'FuelType')
    TransmissionType = apps.get_model('listings', 'TransmissionType')
    EngineSize = apps.get_model('listings', 'EngineSize')
    SeatCount = apps.get_model('listings', 'SeatCount')
    TorqueValue = apps.get_model('listings', 'TorqueValue')
    CarType = apps.get_model('listings', 'CarType')

    # Fuel Types
    fuel_types = ['Petrol', 'Diesel', 'Hybrid', 'Electric', 'LPG', 'Other']
    for fuel in fuel_types:
        FuelType.objects.get_or_create(name=fuel)

    # Transmission Types
    transmissions = ['Manual', 'Automatic', 'CVT', 'Semi-Automatic']
    for trans in transmissions:
        TransmissionType.objects.get_or_create(name=trans)

    # Engine Sizes
    engine_sizes = ['1.0L', '1.2L', '1.4L', '1.5L', '1.6L', '1.8L', '2.0L', '2.2L', '2.4L', '3.0L', '3.5L', '5.0L', '5.7L']
    for size in engine_sizes:
        EngineSize.objects.get_or_create(name=size)

    # Seat Counts
    seat_counts = [2, 4, 5, 6, 7, 8, 9]
    for count in seat_counts:
        SeatCount.objects.get_or_create(count=count)

    # Torque Values
    torque_values = ['100 Nm', '120 Nm', '150 Nm', '170 Nm', '200 Nm', '220 Nm', '250 Nm', '280 Nm', '300 Nm', '320 Nm', '350 Nm', '400+ Nm']
    for torque in torque_values:
        TorqueValue.objects.get_or_create(name=torque)

    # Car Types
    car_types = ['Sedan', 'SUV', 'Coupe', 'Hatchback', 'Wagon', 'Convertible', 'Pickup Truck', 'Minivan', 'Crossover', 'Sports Car']
    for car_type in car_types:
        CarType.objects.get_or_create(name=car_type)

def reverse_choices(apps, schema_editor):
    """Delete all choice data."""
    FuelType = apps.get_model('listings', 'FuelType')
    TransmissionType = apps.get_model('listings', 'TransmissionType')
    EngineSize = apps.get_model('listings', 'EngineSize')
    SeatCount = apps.get_model('listings', 'SeatCount')
    TorqueValue = apps.get_model('listings', 'TorqueValue')
    CarType = apps.get_model('listings', 'CarType')

    FuelType.objects.all().delete()
    TransmissionType.objects.all().delete()
    EngineSize.objects.all().delete()
    SeatCount.objects.all().delete()
    TorqueValue.objects.all().delete()
    CarType.objects.all().delete()

class Migration(migrations.Migration):

    dependencies = [
        ('listings', '0003_listing_is_approved'),
    ]

    operations = [
        migrations.CreateModel(
            name='FuelType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='TransmissionType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='EngineSize',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, unique=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='SeatCount',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('count', models.IntegerField(unique=True)),
            ],
            options={
                'ordering': ['count'],
            },
        ),
        migrations.CreateModel(
            name='TorqueValue',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='CarType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.RunPython(create_initial_choices, reverse_choices),
    ]
