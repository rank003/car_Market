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
import uuid
from typing import Any, Dict, Optional, Tuple

from django.contrib import messages
from django.contrib.messages import get_messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from users.models import Profile
from .models import CarMake, CarModel, Listing


SESSION_KEY_SELECTED_VEHICLES = "selected_vehicle_ids"


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


def _build_listing(data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
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

    owner = None
    owner_created = False
    owner_username = (data.get("owner_username") or "").strip()
    if owner_username:
        owner, owner_created = Profile.objects.get_or_create(
            username=owner_username,
        )

    listing = Listing.objects.create(
        owner=owner,
        car_make=car_make,
        car_model=car_model,
        mileage=_parse_int(data, "mileage"),
        year=_parse_int(data, "year"),
        engine_size=(data.get("engine_size") or "").strip(),
        transmission=(data.get("transmission") or "").strip(),
        description=(data.get("description") or "").strip(),
        price=_parse_int(data, "price"),
        fuel_type=(data.get("fuel_type") or "").strip(),
        seats=_parse_int(data, "seats"),
        torque=_parse_int(data, "torque"),
        listing_image_1=(
            data.get("listing_image_1")
            or "listings/default-listing-img.jpg"
        ).strip(),
    )

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
        },
    }, 201


def _filtered_listings(request):
    queryset = Listing.objects.select_related(
        "car_make",
        "car_model",
    ).order_by("-created", "-id")

    car_make = (request.GET.get("car_make") or "").strip()
    car_model = (request.GET.get("car_model") or "").strip()
    fuel_type = (request.GET.get("fuel_type") or "").strip()
    year = (request.GET.get("year") or "").strip()
    mileage = (request.GET.get("mileage") or "").strip()
    price = (request.GET.get("price") or "").strip()

    if car_make:
        queryset = queryset.filter(car_make__name__icontains=car_make)
    if car_model:
        queryset = queryset.filter(car_model__name__icontains=car_model)
    if fuel_type:
        queryset = queryset.filter(fuel_type__iexact=fuel_type)
    if year:
        queryset = queryset.filter(year=year)
    if mileage:
        queryset = queryset.filter(mileage__lte=mileage)
    if price:
        queryset = queryset.filter(price__lte=price)

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


@require_http_methods(["GET"])
def listings_page(request):
    queryset = _filtered_listings(request)
    paginator = Paginator(queryset, 6)
    page_number = request.GET.get("page")
    listings = paginator.get_page(page_number)

    fuel_types = (
        Listing.objects.exclude(fuel_type="")
        .values_list("fuel_type", flat=True)
        .distinct()
        .order_by("fuel_type")
    )

    context = {
        "listings": listings,
        "values": request.GET,
        "fuel_types": fuel_types,
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

    if request.method == "POST":
        data = request.POST.dict()
        data["owner_username"] = profile.username or request.user.username
        payload, status = _build_listing(data)
        context = {
            "result": payload,
            "is_success": status == 201,
            "status_code": status,
            "form_data": data,
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
            }
        },
    )


@csrf_exempt
@require_http_methods(["POST"])
def create_listing_with_make_model(request):
    payload, status = _build_listing(_payload_from_request(request))
    return JsonResponse(payload, status=status)


@require_http_methods(["GET"])
def single_listing(request, listing_id):
    """Display a single listing's details."""
    listing = get_object_or_404(
        Listing.objects.select_related("car_make", "car_model", "owner"),
        pk=listing_id,
    )
    return render(request, "single-listing.html", {"listing": listing})


@require_http_methods(["GET", "POST"])
@login_required(login_url="login")
def edit_listing(request, listing_id):
    """Allow the listing owner to edit their listing."""
    listing = get_object_or_404(Listing, pk=listing_id)

    # Get the logged-in user's profile
    profile = Profile.objects.filter(user=request.user).first()

    # Only the owner may edit
    if not profile or listing.owner != profile:
        messages.error(request, "You do not have permission to edit this listing.")
        return redirect("listings_page")

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
                },
            )

        car_make, _, car_model, _ = _get_or_create_make_model(make_name, model_name)

        listing.car_make = car_make
        listing.car_model = car_model
        listing.fuel_type = (request.POST.get("fuel_type") or "").strip()
        listing.year = _parse_int(request.POST.dict(), "year")
        listing.mileage = _parse_int(request.POST.dict(), "mileage")
        listing.price = _parse_int(request.POST.dict(), "price")
        listing.engine_size = (request.POST.get("engine_size") or "").strip()
        listing.transmission = (request.POST.get("transmission") or "").strip()
        listing.seats = _parse_int(request.POST.dict(), "seats")
        listing.torque = _parse_int(request.POST.dict(), "torque")
        listing.description = (request.POST.get("description") or "").strip()
        listing.save()

        messages.success(request, "Listing updated successfully.")
        return redirect("listings_page")

    return render(request, "edit_listing.html", {"listing": listing})


@require_http_methods(["GET", "POST"])
@login_required(login_url="login")
def delete_listing(request, listing_id):
    """Allow the listing owner to delete their listing."""
    listing = get_object_or_404(Listing, pk=listing_id)

    # Get the logged-in user's profile
    profile = Profile.objects.filter(user=request.user).first()

    # Only the owner may delete
    if not profile or listing.owner != profile:
        messages.error(request, "You do not have permission to delete this listing.")
        return redirect("listings_page")

    if request.method == "POST":
        listing.delete()
        messages.success(request, "Listing deleted successfully.")
        return redirect("listings_page")

    return render(request, "delete_listing.html", {"listing": listing})


@require_http_methods(["POST"])
@login_required(login_url="login")
def select_vehicle(request, listing_id):
    """Add a vehicle to the logged-in user's selected list (shopping bag)."""
    listing = get_object_or_404(Listing, pk=listing_id)
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
    )
    by_id = {str(listing.id): listing for listing in listings}
    ordered = [by_id[_id] for _id in selected_ids if _id in by_id]

    return render(
        request,
        "selected_vehicles.html",
        {"selected_listings": ordered},
    )
