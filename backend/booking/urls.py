from django.urls import include, path
from rest_framework.routers import SimpleRouter

from . import views as v

router = SimpleRouter()
for name, view in [
    ("services", v.ServiceViewSet),
    ("staff", v.StaffViewSet),
    ("hours", v.HoursViewSet),
    ("time-off", v.TimeOffViewSet),
    ("customers", v.CustomerViewSet),
]:
    router.register(name, view)
urlpatterns = [
    path("api/console/booking-settings/", v.SettingsView.as_view()),
    path("api/console/availability/", v.AvailabilityView.as_view()),
    path("api/console/bookings/", v.BookingsView.as_view()),
    path("api/console/bookings/<uuid:pk>/", v.BookingView.as_view()),
    path("api/console/bookings/<uuid:pk>/cancel/", v.CancelView.as_view()),
    path("api/console/", include(router.urls)),
    path("api/agent-api/shop/", v.AgentShopView.as_view()),
    path("api/agent-api/availability/", v.AgentAvailabilityView.as_view()),
    path("api/agent-api/bookings/", v.AgentBookingsView.as_view()),
    path("api/agent-api/bookings/<uuid:pk>/", v.AgentBookingView.as_view()),
    path("api/agent-api/bookings/<uuid:pk>/cancel/", v.AgentCancelView.as_view()),
]
