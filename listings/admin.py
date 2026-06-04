from django.contrib import admin

from .models import CarMake, CarModel, Listing


@admin.register(CarMake)
class CarMakeAdmin(admin.ModelAdmin):
	search_fields = ("name",)


@admin.register(CarModel)
class CarModelAdmin(admin.ModelAdmin):
	list_display = ("name", "car_make")
	list_filter = ("car_make",)
	search_fields = ("name", "car_make__name")


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
	list_display = (
		"car_make",
		"car_model",
		"owner",
		"price",
		"year",
		"is_approved",
		"created",
	)
	list_filter = ("is_approved", "car_make", "fuel_type", "created")
	search_fields = (
		"car_make__name",
		"car_model__name",
		"owner__username",
		"owner__name",
	)
	list_editable = ("is_approved",)
	readonly_fields = ("created",)
	actions = ("approve_listings", "unapprove_listings")

	@admin.action(description="Approve selected listings")
	def approve_listings(self, request, queryset):
		updated = queryset.update(is_approved=True)
		self.message_user(request, f"{updated} listing(s) approved.")

	@admin.action(description="Unapprove selected listings")
	def unapprove_listings(self, request, queryset):
		updated = queryset.update(is_approved=False)
		self.message_user(request, f"{updated} listing(s) unapproved.")
