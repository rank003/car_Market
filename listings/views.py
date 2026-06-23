# from django.shortcuts import get_object_or_404, render

# from .models import Listing


# def listing_list(request):
#     """Display all listings, newest first."""
#     listings = (
#         Listing.objects.select_related("car_make", "car_model", "owner")
#         .order_by("-created")
#     )
#     context = {"listings": listings}
#     return render(request, "listings.html", context)


# def listing_detail(request, listing_id):
#     """Display details for a single listing."""
#     listing = get_object_or_404(
#         Listing.objects.select_related("car_make", "car_model", "owner"),
#         pk=listing_id,
#     )
#     context = {"listing": listing}
#     return render(request, "single-listing.html", context)

import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from django.conf import settings
from django.contrib import messages
from django.contrib.messages import get_messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.files.storage import FileSystemStorage
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from users.models import Profile
from users.models import Notification
from .models import CarMake, CarModel, Listing, FuelType, TransmissionType, EngineSize, SeatCount, TorqueValue, CarType


SESSION_KEY_SELECTED_VEHICLES = "selected_vehicle_ids"
IMAGE_FIELDS = (
    "listing_image_1",
    "listing_image_2",
    "listing_image_3",
    "listing_image_4",
    "listing_image_5",
    "listing_image_6",
)
PLACEHOLDER_IMAGE = "listings_images/Placeholder_00001.png"


def _store_uploaded_image(uploaded_file) -> Optional[str]:
    if not uploaded_file:
        return None

    storage = FileSystemStorage(location=settings.MEDIA_ROOT, base_url=settings.MEDIA_URL)
    base_name, ext = os.path.splitext(uploaded_file.name)
    safe_name = f"listings/uploads/{uuid.uuid4().hex}_{base_name[:40]}{ext}"
    return storage.save(safe_name, uploaded_file)


def _listing_image_url(image_name: Optional[str]) -> str:
    if image_name:
        normalized = str(image_name).strip()
        if normalized and normalized not in {
            "listings/default-listing-img.jpg",
            "Placeholder_00001.jpg",
        }:
            candidate = os.path.join(settings.MEDIA_ROOT, normalized)
            if os.path.exists(candidate):
                return f"{settings.MEDIA_URL}{normalized}"

    return f"{settings.MEDIA_URL}{PLACEHOLDER_IMAGE}"


def _attach_primary_image_url(listing: Listing) -> Listing:
    listing.primary_image_url = _listing_image_url(listing.listing_image_1)
    return listing


def _resolve_listing_image(data: Dict[str, Any], files, field_name: str, fallback: str) -> str:
    uploaded = files.get(field_name) if files else None
    stored_name = _store_uploaded_image(uploaded)
    if stored_name:
        return stored_name

    value = (data.get(field_name) or "").strip()
    if value:
        return value

    return fallback


def _apply_listing_fields(listing: Listing, data: Dict[str, Any], files, *, keep_existing_images: bool = False) -> None:
    listing.car_make, _, listing.car_model, _ = _get_or_create_make_model(
        (data.get("car_make") or "").strip(),
        (data.get("car_model") or "").strip(),
    )
    listing.mileage = _parse_int(data, "mileage")
    listing.year = _parse_int(data, "year")
    listing.engine_size = (data.get("engine_size") or "").strip()
    listing.transmission = (data.get("transmission") or "").strip()
    listing.description = (data.get("description") or "").strip()
    listing.price = _parse_int(data, "price")
    listing.fuel_type = (data.get("fuel_type") or "").strip()
    listing.seats = _parse_int(data, "seats")
    listing.torque = _parse_torque_int(data.get("torque"))
    car_type_name = (data.get("car_type") or "").strip()
    listing.car_type = CarType.objects.filter(name__iexact=car_type_name).first() if car_type_name else None

    for field_name in IMAGE_FIELDS:
        if str(data.get(f"delete_{field_name}") or "").lower() in {"1", "true", "yes", "on"}:
            setattr(listing, field_name, "listings/default-listing-img.jpg")
            continue

        current_value = getattr(listing, field_name)
        if keep_existing_images:
            new_value = _resolve_listing_image(data, files, field_name, current_value)
        else:
            new_value = _resolve_listing_image(
                data,
                files,
                field_name,
                "listings/default-listing-img.jpg",
            )
        setattr(listing, field_name, new_value)


def _payload_from_request(request) -> Dict[str, Any]:
    if request.content_type and "application/json" in request.content_type:
        try:
            return json.loads(request.body or "{}")
        except json.JSONDecodeError:
            return {}
    return request.POST.dict()


def _parse_int(data: Dict[str, Any], key: str) -> Optional[int]:
    value = data.get(key)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_torque_int(value: Any) -> Optional[int]:
    """Parse torque from either raw integer values or labels like '150 Nm'."""
    if value in (None, ""):
        return None

    raw = str(value).strip()
    if not raw:
        return None

    try:
        return int(raw)
    except (TypeError, ValueError):
        digits = "".join(ch for ch in raw if ch.isdigit())
        if not digits:
            return None
        try:
            return int(digits)
        except (TypeError, ValueError):
            return None


def _get_choice_options() -> Dict[str, list]:
    """Retrieve all choice options for form dropdowns."""
    torque_values = []
    for item in TorqueValue.objects.values_list("name", flat=True).order_by("name"):
        parsed = _parse_torque_int(item)
        if parsed is not None:
            torque_values.append({"value": parsed, "label": item})

    return {
        "fuel_types": list(FuelType.objects.values_list("name", flat=True).order_by("name")),
        "transmission_types": list(TransmissionType.objects.values_list("name", flat=True).order_by("name")),
        "engine_sizes": list(EngineSize.objects.values_list("name", flat=True).order_by("name")),
        "seat_counts": list(SeatCount.objects.values_list("count", flat=True).order_by("count")),
        "torque_values": torque_values,
        "car_types": list(CarType.objects.values_list("name", flat=True).order_by("name")),
    }


def _get_or_create_make_model(
    make_name: str,
    model_name: str,
) -> Tuple[CarMake, bool, CarModel, bool]:
    car_make = CarMake.objects.filter(name__iexact=make_name).first()
    make_created = False
    if car_make is None:
        car_make = CarMake.objects.create(name=make_name)
        make_created = True

    car_model = CarModel.objects.filter(
        name__iexact=model_name,
        car_make=car_make,
    ).first()
    model_created = False
    if car_model is None:
        car_model = CarModel.objects.create(name=model_name, car_make=car_make)
        model_created = True

    return car_make, make_created, car_model, model_created


def _build_listing(
    data: Dict[str, Any],
    files=None,
    owner_profile: Optional[Profile] = None,
) -> Tuple[Dict[str, Any], int]:
    make_name = (data.get("car_make") or "").strip()
    model_name = (data.get("car_model") or "").strip()

    if not make_name or not model_name:
        return {
            "ok": False,
            "error": "car_make and car_model are required.",
        }, 400

    car_make, make_created, car_model, model_created = (
        _get_or_create_make_model(make_name, model_name)
    )

    owner = owner_profile
    owner_created = False
    owner_username = (data.get("owner_username") or "").strip()
    if owner is None and owner_username:
        owner = Profile.objects.filter(username=owner_username, user__isnull=False).first()
        if owner is None:
            owner, owner_created = Profile.objects.get_or_create(
                username=owner_username,
            )

    listing = Listing(owner=owner, car_make=car_make, car_model=car_model)
    _apply_listing_fields(listing, data, files, keep_existing_images=False)
    listing.save()

    return {
        "ok": True,
        "owner": {
            "id": str(owner.id) if owner else None,
            "username": owner.username if owner else None,
            "created": owner_created,
        },
        "car_make": {
            "id": car_make.id,
            "name": car_make.name,
            "created": make_created,
        },
        "car_model": {
            "id": car_model.id,
            "name": car_model.name,
            "car_make_id": car_model.car_make_id,
            "created": model_created,
        },
        "listing": {
            "id": str(listing.id),
            "owner_id": str(listing.owner_id) if listing.owner_id else None,
            "car_make_id": listing.car_make_id,
            "car_model_id": listing.car_model_id,
            "is_approved": listing.is_approved,
        },
    }, 201


def _filtered_listings(request):
    queryset = Listing.objects.select_related(
        "car_make",
        "car_model",
        "car_type",
    ).filter(is_approved=True)

    q = (request.GET.get("q") or "").strip()
    car_make = (request.GET.get("car_make") or "").strip()
    car_model = (request.GET.get("car_model") or "").strip()
    fuel_type = (request.GET.get("fuel_type") or "").strip()
    transmission = (request.GET.get("transmission") or "").strip()
    year_from = (request.GET.get("year_from") or "").strip()
    year_to = (request.GET.get("year_to") or "").strip()
    legacy_year = (request.GET.get("year") or "").strip()
    mileage_min = (request.GET.get("mileage_min") or "").strip()
    mileage_max = (request.GET.get("mileage_max") or "").strip()
    legacy_mileage = (request.GET.get("mileage") or "").strip()
    price_min = (request.GET.get("price_min") or "").strip()
    price_max = (request.GET.get("price_max") or "").strip()
    legacy_price = (request.GET.get("price") or "").strip()
    vehicle_segment = (request.GET.get("vehicle_segment") or "all").strip().lower()
    sort = (request.GET.get("sort") or "car_make").strip().lower()

    if legacy_year and not year_from and not year_to:
        year_from = legacy_year
        year_to = legacy_year
    if legacy_mileage and not mileage_min and not mileage_max:
        mileage_max = legacy_mileage
    if legacy_price and not price_min and not price_max:
        price_max = legacy_price

    if q:
        queryset = queryset.filter(
            Q(car_make__name__icontains=q)
            | Q(car_model__name__icontains=q)
        )
    if car_make:
        queryset = queryset.filter(car_make__name__icontains=car_make)
    if car_model:
        queryset = queryset.filter(car_model__name__icontains=car_model)
    if fuel_type:
        queryset = queryset.filter(fuel_type__iexact=fuel_type)
    if transmission:
        queryset = queryset.filter(transmission__iexact=transmission)
    if year_from:
        queryset = queryset.filter(year__gte=year_from)
    if year_to:
        queryset = queryset.filter(year__lte=year_to)
    if mileage_min:
        queryset = queryset.filter(mileage__gte=mileage_min)
    if mileage_max:
        queryset = queryset.filter(mileage__lte=mileage_max)
    if price_min:
        queryset = queryset.filter(price__gte=price_min)
    if price_max:
        queryset = queryset.filter(price__lte=price_max)

    if vehicle_segment == "suvs":
        queryset = queryset.filter(
            Q(car_type__name__in=["SUV", "Pickup Truck", "Crossover"])
            | Q(car_model__name__icontains="suv")
            | Q(car_model__name__icontains="truck")
            | Q(car_model__name__icontains="awd")
            | Q(description__icontains="suv")
            | Q(description__icontains="truck")
            | Q(description__icontains="awd")
        )
    elif vehicle_segment == "cars":
        queryset = queryset.filter(
            Q(car_type__name__in=[
                "Sedan",
                "Coupe",
                "Hatchback",
                "Wagon",
                "Convertible",
                "Sports Car",
            ])
            | (
                Q(car_type__isnull=True)
                & ~Q(car_model__name__icontains="suv")
                & ~Q(car_model__name__icontains="truck")
                & ~Q(car_model__name__icontains="awd")
            )
        )

    if sort == "price":
        queryset = queryset.order_by("price", "-created", "-id")
    elif sort == "year":
        queryset = queryset.order_by("-year", "-created", "-id")
    elif sort == "date_added":
        queryset = queryset.order_by("-created", "-id")
    else:
        queryset = queryset.order_by("car_make__name", "car_model__name", "-created", "-id")

    return queryset


def _get_selected_vehicle_ids(request):
    raw_ids = request.session.get(SESSION_KEY_SELECTED_VEHICLES, [])
    valid_ids = []
    for value in raw_ids:
        try:
            valid_ids.append(str(uuid.UUID(str(value))))
        except (TypeError, ValueError):
            continue
    return valid_ids


def _save_selected_vehicle_ids(request, ids):
    request.session[SESSION_KEY_SELECTED_VEHICLES] = ids
    request.session.modified = True


def _send_submission_notification(listing: Listing, status: str) -> None:
    profile = listing.owner
    if not profile:
        return

    if profile.user_id is None and profile.username:
        linked_profile = Profile.objects.filter(
            username=profile.username,
            user__isnull=False,
        ).first()
        if linked_profile:
            profile = linked_profile

    if status == "approved":
        subject = "Your car submission was accepted"
        message = (
            f"Your submission for {listing.car_make} {listing.car_model} was accepted by the admin and is now live on the site."
        )
    elif status == "rejected":
        subject = "Your car submission was rejected"
        message = (
            f"Your submission for {listing.car_make} {listing.car_model} was rejected by the admin."
        )
    else:
        return

    Notification.objects.create(
        profile=profile,
        subject=subject,
        message=message,
    )


@require_http_methods(["GET"])
def listings_page(request):
    queryset = _filtered_listings(request)
    paginator = Paginator(queryset, 6)
    page_number = request.GET.get("page")
    listings = paginator.get_page(page_number)
    for listing in listings:
        _attach_primary_image_url(listing)

    fuel_types = (
        Listing.objects.exclude(fuel_type="")
        .values_list("fuel_type", flat=True)
        .distinct()
        .order_by("fuel_type")
    )

    transmission_types = list(
        TransmissionType.objects.values_list("name", flat=True).order_by("name")
    )
    if not transmission_types:
        transmission_types = list(
            Listing.objects.exclude(transmission="")
            .values_list("transmission", flat=True)
            .distinct()
            .order_by("transmission")
        )

    context = {
        "listings": listings,
        "values": request.GET,
        "fuel_types": fuel_types,
        "transmission_types": transmission_types,
        "sort": (request.GET.get("sort") or "car_make").strip().lower(),
        "vehicle_segment": (request.GET.get("vehicle_segment") or "all").strip().lower(),
    }
    return render(request, "listings.html", context)


@require_http_methods(["GET", "POST"])
@login_required(login_url="login")
def create_listing_form(request):
    profile, _ = Profile.objects.get_or_create(
        user=request.user,
        defaults={
            "username": request.user.username,
            "email": request.user.email,
            "name": request.user.get_full_name(),
        },
    )

    choice_options = _get_choice_options()

    if request.method == "POST":
        data = request.POST.dict()
        data["owner_username"] = profile.username or request.user.username
        payload, status = _build_listing(
            data,
            request.FILES,
            owner_profile=profile,
        )

        if (
            status == 201
            and payload.get("ok")
            and (request.user.is_staff or request.user.is_superuser)
        ):
            listing_id = payload.get("listing", {}).get("id")
            if listing_id:
                Listing.objects.filter(pk=listing_id).update(is_approved=True)

        context = {
            "result": payload,
            "is_success": status == 201,
            "status_code": status,
            "form_data": data,
            "is_admin_submission": bool(
                request.user.is_staff or request.user.is_superuser
            ),
            **choice_options,
        }
        return render(
            request,
            "create_listing_form.html",
            context,
            status=status,
        )

    return render(
        request,
        "create_listing_form.html",
        {
            "form_data": {
                "owner_username": profile.username or request.user.username,
            },
            **choice_options,
        },
    )


@csrf_exempt
@require_http_methods(["POST"])
def create_listing_with_make_model(request):
    payload, status = _build_listing(_payload_from_request(request), request.FILES)
    return JsonResponse(payload, status=status)


@require_http_methods(["GET"])
def single_listing(request, listing_id):
    """Display a single listing's details."""
    listing = get_object_or_404(
        Listing.objects.select_related("car_make", "car_model", "owner"),
        pk=listing_id,
    )

    profile = None
    if request.user.is_authenticated:
        profile = Profile.objects.filter(user=request.user).first()

    can_view_unapproved = bool(
        request.user.is_authenticated
        and (
            request.user.is_staff
            or request.user.is_superuser
            or (profile and listing.owner_id == profile.id)
        )
    )

    if not listing.is_approved and not can_view_unapproved:
        messages.error(request, "This listing is awaiting admin approval.")
        return redirect("listings_page")

    _attach_primary_image_url(listing)
    return render(request, "single-listing.html", {"listing": listing})


@require_http_methods(["GET", "POST"])
@login_required(login_url="login")
def edit_listing(request, listing_id):
    """Allow the listing owner to edit their listing."""
    listing = get_object_or_404(Listing, pk=listing_id)
    next_url = request.GET.get("next") or request.POST.get("next")

    # Get the logged-in user's profile
    profile = Profile.objects.filter(user=request.user).first()

    # Owner or admin users may edit
    is_admin_user = bool(request.user.is_staff or request.user.is_superuser)
    is_owner = bool(profile and listing.owner == profile)
    if not (is_owner or is_admin_user):
        messages.error(request, "You do not have permission to edit this listing.")
        return redirect(next_url or "listings_page")

    # Clear any stale queued messages so unrelated alerts don't appear here.
    if request.method == "GET":
        storage = get_messages(request)
        for _ in storage:
            pass

    if request.method == "POST":
        make_name = (request.POST.get("car_make") or "").strip()
        model_name = (request.POST.get("car_model") or "").strip()

        if not make_name or not model_name:
            return render(
                request,
                "edit_listing.html",
                {
                    "listing": listing,
                    "form_error": "Car make and car model are required.",
                    "next_url": next_url,
                },
            )

        data = request.POST.dict()
        _apply_listing_fields(listing, data, request.FILES, keep_existing_images=True)
        listing.is_approved = False
        listing.save()

        messages.success(
            request,
            "Listing updated and sent back for admin approval.",
        )
        return redirect(next_url or "listings_page")

    return render(request, "edit_listing.html", {"listing": listing, "next_url": next_url})


@require_http_methods(["GET", "POST"])
@login_required(login_url="login")
def review_submission(request, listing_id):
    """Open a pending submission in the create listing form for admin review."""
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "You do not have permission to review submissions.")
        return redirect("listings_page")

    listing = get_object_or_404(Listing, pk=listing_id)

    if request.method == "POST":
        admin_action = (request.POST.get("admin_action") or "save").strip().lower()

        if admin_action == "reject":
            _send_submission_notification(listing, "rejected")
            listing.delete()
            messages.success(request, "Submission rejected and removed.")
            return redirect("approvals_page")

        make_name = (request.POST.get("car_make") or "").strip()
        model_name = (request.POST.get("car_model") or "").strip()

        if not make_name or not model_name:
            return render(
                request,
                "create_listing_form.html",
                {
                    "listing": listing,
                    "form_data": request.POST.dict(),
                    "is_admin_review": True,
                    "form_error": "Car make and car model are required.",
                    "back_url": "approvals_page",
                    "back_label": "Back to New Submissions",
                    **_get_choice_options(),
                },
            )

        data = request.POST.dict()
        _apply_listing_fields(listing, data, request.FILES, keep_existing_images=True)
        listing.is_approved = admin_action == "approve"
        listing.save()

        if listing.is_approved:
            _send_submission_notification(listing, "approved")
            messages.success(request, "Submission updated and approved.")
        else:
            messages.success(request, "Submission changes saved. It is still pending approval.")

        return redirect("approvals_page")

    form_data = {
        "car_make": listing.car_make.name if listing.car_make else "",
        "car_model": listing.car_model.name if listing.car_model else "",
        "fuel_type": listing.fuel_type,
        "car_type": listing.car_type.name if listing.car_type else "",
        "year": listing.year,
        "mileage": listing.mileage,
        "price": listing.price,
        "engine_size": listing.engine_size,
        "transmission": listing.transmission,
        "seats": listing.seats,
        "torque": listing.torque,
        "description": listing.description,
        "owner_username": listing.owner.username if listing.owner else "",
    }

    return render(
        request,
        "create_listing_form.html",
        {
            "listing": listing,
            "form_data": form_data,
            "is_admin_review": True,
            "back_url": "approvals_page",
            "back_label": "Back to New Submissions",
            **_get_choice_options(),
        },
    )


@require_http_methods(["GET", "POST"])
@login_required(login_url="login")
def delete_listing(request, listing_id):
    """Allow the listing owner to delete their listing."""
    listing = get_object_or_404(Listing, pk=listing_id)
    next_url = request.GET.get("next") or request.POST.get("next")

    # Get the logged-in user's profile
    profile = Profile.objects.filter(user=request.user).first()

    # Owner or admin users may delete
    is_admin_user = bool(request.user.is_staff or request.user.is_superuser)
    is_owner = bool(profile and listing.owner == profile)
    if not (is_owner or is_admin_user):
        messages.error(request, "You do not have permission to delete this listing.")
        return redirect(next_url or "listings_page")

    if request.method == "POST":
        listing.delete()
        messages.success(request, "Listing deleted successfully.")
        return redirect(next_url or "listings_page")

    return render(request, "delete_listing.html", {"listing": listing, "next_url": next_url})


@require_http_methods(["POST"])
@login_required(login_url="login")
def select_vehicle(request, listing_id):
    """Add a vehicle to the logged-in user's selected list (shopping bag)."""
    listing = get_object_or_404(Listing, pk=listing_id)

    if not listing.is_approved:
        messages.error(request, "You can only select approved vehicles.")
        next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
        return redirect(next_url or "listings_page")

    selected_ids = _get_selected_vehicle_ids(request)
    listing_id_str = str(listing.id)

    if listing_id_str not in selected_ids:
        selected_ids.append(listing_id_str)
        _save_selected_vehicle_ids(request, selected_ids)
        messages.success(request, "Vehicle added to your shopping bag.")

    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
    return redirect(next_url or "listings_page")


@require_http_methods(["POST"])
@login_required(login_url="login")
def unselect_vehicle(request, listing_id):
    """Remove a vehicle from the logged-in user's selected list."""
    selected_ids = _get_selected_vehicle_ids(request)
    listing_id_str = str(listing_id)

    if listing_id_str in selected_ids:
        selected_ids.remove(listing_id_str)
        _save_selected_vehicle_ids(request, selected_ids)
        messages.success(request, "Vehicle removed from your shopping bag.")

    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
    return redirect(next_url or "listings_page")


@require_http_methods(["GET"])
@login_required(login_url="login")
def selected_vehicles_page(request):
    """Display all vehicles currently selected by the logged-in user."""
    selected_ids = _get_selected_vehicle_ids(request)
    listings = Listing.objects.select_related("car_make", "car_model").filter(
        id__in=selected_ids,
        is_approved=True,
    )
    by_id = {str(listing.id): listing for listing in listings}
    ordered = [by_id[_id] for _id in selected_ids if _id in by_id]
    for listing in ordered:
        _attach_primary_image_url(listing)

    return render(
        request,
        "selected_vehicles.html",
        {"selected_listings": ordered},
    )


@require_http_methods(["POST"])
@login_required(login_url="login")
def complete_purchase(request):
    """Submit a purchase request for all currently selected vehicles."""
    selected_ids = _get_selected_vehicle_ids(request)
    profile = Profile.objects.filter(user=request.user).first()

    if not selected_ids:
        messages.error(request, "Purchase failed: your bag is empty.")
        if profile:
            Notification.objects.create(
                profile=profile,
                subject="Payment failed",
                message="Payment could not be completed because your bag was empty.",
            )
        return redirect("selected_vehicles_page")

    full_name = (request.POST.get("full_name") or "").strip()
    email = (request.POST.get("email") or "").strip()
    phone = (request.POST.get("phone") or "").strip()
    billing_address = (request.POST.get("billing_address") or "").strip()
    delivery_address = (request.POST.get("delivery_address") or "").strip()
    cardholder_name = (request.POST.get("cardholder_name") or "").strip()
    card_number_raw = (request.POST.get("card_number") or "").strip()
    expiry_raw = (request.POST.get("expiry") or "").strip()
    cvv_raw = (request.POST.get("cvv") or "").strip()
    notes = (request.POST.get("notes") or "").strip()

    card_number = "".join(ch for ch in card_number_raw if ch.isdigit())
    cvv = "".join(ch for ch in cvv_raw if ch.isdigit())

    expiry_valid = False
    expiry_month = None
    expiry_year = None
    if "/" in expiry_raw:
        month_part, year_part = [item.strip() for item in expiry_raw.split("/", 1)]
        if month_part.isdigit() and year_part.isdigit() and len(year_part) in {2, 4}:
            expiry_month = int(month_part)
            year_int = int(year_part)
            expiry_year = 2000 + year_int if len(year_part) == 2 else year_int
            if 1 <= expiry_month <= 12:
                now = datetime.now()
                expiry_valid = (expiry_year > now.year) or (
                    expiry_year == now.year and expiry_month >= now.month
                )

    if (
        not full_name
        or not email
        or not phone
        or not billing_address
        or not delivery_address
        or not cardholder_name
        or len(card_number) < 13
        or len(card_number) > 19
        or not expiry_valid
        or len(cvv) not in {3, 4}
    ):
        messages.error(request, "Payment failed: please provide valid card and billing details.")
        if profile:
            Notification.objects.create(
                profile=profile,
                subject="Payment failed",
                message="Your payment attempt failed validation. Please verify your card details and try again.",
            )
        return redirect("selected_vehicles_page")

    vehicles = Listing.objects.filter(id__in=selected_ids, is_approved=True)
    vehicle_count = vehicles.count()
    subtotal = sum((item.price or 0) for item in vehicles)
    masked_card = f"**** **** **** {card_number[-4:]}" if len(card_number) >= 4 else "****"
    purchase_reference = uuid.uuid4().hex[:10].upper()

    if vehicle_count == 0:
        messages.error(request, "Payment failed: no approved vehicles were available in your bag.")
        if profile:
            Notification.objects.create(
                profile=profile,
                subject="Payment failed",
                message="Your bag did not contain approved vehicles at checkout time.",
            )
        return redirect("selected_vehicles_page")

    _save_selected_vehicle_ids(request, [])
    messages.success(
        request,
        f"Payment successful for {vehicle_count} vehicle(s), total €{subtotal:,}. Ref: {purchase_reference}",
    )

    if profile:
        Notification.objects.create(
            profile=profile,
            subject="Payment successful",
            message=(
                f"Your payment was successful.\n"
                f"Reference: {purchase_reference}\n"
                f"Vehicles: {vehicle_count}\n"
                f"Total Paid: €{subtotal:,}\n"
                f"Card: {masked_card}\n"
                f"Billing Address: {billing_address}\n"
                f"Delivery Address: {delivery_address}"
                + (f"\nNotes: {notes}" if notes else "")
            ),
        )

    return redirect("selected_vehicles_page")


@require_http_methods(["GET"])
@login_required(login_url="login")
def my_submissions_page(request):
    """Display listings page for admins and personal submissions page for regular users."""
    is_admin_user = bool(request.user.is_staff or request.user.is_superuser)

    base_queryset = Listing.objects.select_related("car_make", "car_model", "car_type", "owner")

    if is_admin_user:
        queryset = base_queryset.filter(is_approved=True).order_by("-created", "-id")
        page_title = "Submissions"
        empty_message = "No listings are available right now."
    else:
        profile = Profile.objects.filter(user=request.user).first()
        queryset = (
            base_queryset.filter(owner=profile, is_approved=False).order_by("-created", "-id")
            if profile
            else base_queryset.none()
        )
        page_title = "My Submissions"
        empty_message = "You have not submitted any listings yet."

    submissions = list(queryset)
    for listing in submissions:
        _attach_primary_image_url(listing)

    return render(
        request,
        "submissions.html",
        {
            "submissions": submissions,
            "is_admin_user": is_admin_user,
            "can_manage_submissions": True,
            "page_title": page_title,
            "empty_message": empty_message,
        },
    )


@require_http_methods(["GET", "POST"])
@login_required(login_url="login")
def approvals_page(request):
    """Allow admin users to approve submitted listings from a single page."""
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "You do not have permission to access approvals.")
        return redirect("listings_page")

    pending_queryset = Listing.objects.select_related(
        "car_make",
        "car_model",
        "owner",
        "owner__user",
    ).filter(
        is_approved=False,
        owner__isnull=False,
        owner__user__isnull=False,
        owner__user__is_staff=False,
        owner__user__is_superuser=False,
    ).order_by("-created")

    paginator = Paginator(pending_queryset, 6)
    page_number = request.GET.get("page")
    pending_listings = paginator.get_page(page_number)
    for listing in pending_listings:
        _attach_primary_image_url(listing)

    return render(
        request,
        "approvals.html",
        {"pending_listings": pending_listings},
    )


@require_http_methods(["POST"])
@login_required(login_url="login")
def approve_submission(request, listing_id):
    """Approve a single user-submitted listing."""
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "You do not have permission to approve submissions.")
        return redirect("listings_page")

    listing = get_object_or_404(Listing, pk=listing_id)
    _attach_primary_image_url(listing)
    listing.is_approved = True
    listing.save(update_fields=["is_approved"])
    _send_submission_notification(listing, "approved")
    messages.success(request, "Submission approved successfully.")
    return redirect("approvals_page")


@require_http_methods(["POST"])
@login_required(login_url="login")
def reject_submission(request, listing_id):
    """Reject a single user-submitted listing by removing it."""
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "You do not have permission to reject submissions.")
        return redirect("listings_page")

    listing = get_object_or_404(Listing, pk=listing_id)
    _attach_primary_image_url(listing)
    _send_submission_notification(listing, "rejected")
    listing.delete()
    messages.success(request, "Submission rejected and removed.")
    return redirect("approvals_page")
