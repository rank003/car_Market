from django.urls import path

from . import views

urlpatterns = [
    path("", views.listings_page, name="listings_page"),
    path("create/", views.create_listing_form, name="create_listing_form"),
    path("approvals/", views.approvals_page, name="approvals_page"),
    path(
        "approvals/<uuid:listing_id>/approve/",
        views.approve_submission,
        name="approve_submission",
    ),
    path(
        "approvals/<uuid:listing_id>/review/",
        views.review_submission,
        name="review_submission",
    ),
    path(
        "approvals/<uuid:listing_id>/reject/",
        views.reject_submission,
        name="reject_submission",
    ),
    path("<uuid:listing_id>/", views.single_listing, name="single_listing"),
    path("<uuid:listing_id>/edit/", views.edit_listing, name="edit_listing"),
    path("<uuid:listing_id>/delete/", views.delete_listing, name="delete_listing"),
    path(
        "<uuid:listing_id>/select/",
        views.select_vehicle,
        name="select_vehicle",
    ),
    path(
        "<uuid:listing_id>/unselect/",
        views.unselect_vehicle,
        name="unselect_vehicle",
    ),
    path("selected/", views.selected_vehicles_page, name="selected_vehicles_page"),
    path(
        "api/create/",
        views.create_listing_with_make_model,
        name="create_listing_with_make_model",
    ),
]
