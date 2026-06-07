import uuid
from django.db import models
from users.models import Profile

class CarMake(models.Model):
    name = models.CharField(max_length=200, unique=True)

    def __str__(self):
        return self.name

class CarModel(models.Model):
    name = models.CharField(max_length=200)
    car_make = models.ForeignKey(CarMake, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("name", "car_make")

    def __str__(self):
        return self.name

class FuelType(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

class TransmissionType(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

class EngineSize(models.Model):
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

class SeatCount(models.Model):
    count = models.IntegerField(unique=True)

    class Meta:
        ordering = ["count"]

    def __str__(self):
        return str(self.count)

class TorqueValue(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

class CarType(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

class Listing(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(Profile, on_delete=models.CASCADE, null=True, blank=True)
    car_make = models.ForeignKey(CarMake, on_delete=models.SET_NULL, null=True, blank=True)
    car_model = models.ForeignKey(CarModel, on_delete=models.SET_NULL, null=True, blank=True)
    mileage = models.IntegerField(null=True, blank=True)
    year = models.IntegerField(null=True, blank=True)
    engine_size = models.CharField(max_length=20, blank=True, default="")
    transmission = models.CharField(max_length=100, blank=True, default="")
    created = models.DateTimeField(null=True, blank=True)
    description = models.TextField(blank=True, default="")
    price = models.IntegerField(null=True, blank=True)
    fuel_type = models.CharField(max_length=100, blank=True, default="")
    seats = models.IntegerField(null=True, blank=True)
    torque = models.IntegerField(null=True, blank=True)
    car_type = models.ForeignKey(CarType, on_delete=models.SET_NULL, null=True, blank=True)
    is_approved = models.BooleanField(default=False)
    listing_image_1 = models.CharField(max_length=255, blank=True, default="listings/default-listing-img.jpg")
    listing_image_2 = models.CharField(max_length=255, blank=True, default="listings/default-listing-img.jpg")
    listing_image_3 = models.CharField(max_length=255, blank=True, default="listings/default-listing-img.jpg")
    listing_image_4 = models.CharField(max_length=255, blank=True, default="listings/default-listing-img.jpg")
    listing_image_5 = models.CharField(max_length=255, blank=True, default="listings/default-listing-img.jpg")
    listing_image_6 = models.CharField(max_length=255, blank=True, default="listings/default-listing-img.jpg")

    def __str__(self):
        return f"{self.car_make} {self.car_model}"
    