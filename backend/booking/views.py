from datetime import timedelta
from zoneinfo import ZoneInfo

from core.models import Business
from core.permissions import agent_actor, authorize, human_actor
from core.serializers import BusinessSerializer, CustomerRefInput
from core.services import audit
from core.views import AgentView, validated
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from . import payloads, services
from .availability import MAX_DAYS, slots_for
from .models import BookingSettings, Customer, Service, Staff, TimeOff, WorkingHours
from .serializers import (
    AgentCreateInput,
    AgentRescheduleInput,
    AvailabilityInput,
    CreateBookingInput,
    CustomerInput,
    CustomerSerializer,
    HoursSerializer,
    RescheduleInput,
    ServiceSerializer,
    SettingsSerializer,
    StaffSerializer,
    TimeOffSerializer,
)


def actor_for(request, is_agent=False):
    return agent_actor(request.auth) if is_agent else human_actor(request.user)


def page_of(rows, raw_page, size=30):
    try:
        page = int(raw_page)
    except (TypeError, ValueError):
        raise ValidationError("頁碼必須是正整數。")
    count = rows.count() if hasattr(rows, "model") else len(rows)
    pages = max(1, (count + size - 1) // size)
    if page < 1 or page > pages:
        raise NotFound("頁碼不存在。")
    return rows[(page - 1) * size : page * size], {"page": page, "pages": pages, "count": count}


class SettingsView(APIView):
    def get(self, request):
        authorize(human_actor(request.user), "catalog.read")
        return Response(SettingsSerializer(BookingSettings.current()).data)

    def patch(self, request):
        serializer = SettingsSerializer(BookingSettings.current(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(
            SettingsSerializer(services.save_catalog(human_actor(request.user), serializer)).data
        )


class CatalogViewSet(viewsets.ModelViewSet):
    http_method_names = ["get", "post", "patch", "head", "options"]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        authorize(
            human_actor(request.user),
            "catalog.read" if request.method in {"GET", "HEAD", "OPTIONS"} else "catalog.write",
        )

    def perform_create(self, serializer):
        services.save_catalog(human_actor(self.request.user), serializer)

    def perform_update(self, serializer):
        services.save_catalog(human_actor(self.request.user), serializer)


class ServiceViewSet(CatalogViewSet):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer


class StaffViewSet(CatalogViewSet):
    queryset = Staff.objects.all()
    serializer_class = StaffSerializer


class ScheduleViewSet(CatalogViewSet):
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def perform_destroy(self, instance):
        services.delete_schedule(human_actor(self.request.user), instance)


class HoursViewSet(ScheduleViewSet):
    queryset = WorkingHours.objects.all()
    serializer_class = HoursSerializer


class TimeOffViewSet(ScheduleViewSet):
    queryset = TimeOff.objects.all()
    serializer_class = TimeOffSerializer


class CustomerViewSet(viewsets.GenericViewSet):
    queryset = Customer.objects.select_related("identity")
    serializer_class = CustomerSerializer

    def list(self, request):
        authorize(human_actor(request.user), "customers.read")
        q = request.query_params.get("q", "")
        rows = self.queryset.filter(Q(identity__display_name__icontains=q) | Q(phone__icontains=q))
        page, meta = page_of(rows, request.query_params.get("page", 1))
        return Response({"results": CustomerSerializer(page, many=True).data, **meta})

    def create(self, request):
        values = validated(CustomerInput, request.data)
        return Response(
            CustomerSerializer(services.save_customer(human_actor(request.user), values)).data,
            status=201,
        )

    def partial_update(self, request, pk=None):
        values = validated(CustomerInput, request.data, partial=True)
        return Response(
            CustomerSerializer(
                services.save_customer(human_actor(request.user), values, self.get_object())
            ).data
        )


class AvailabilityView(APIView):
    is_agent = False

    @transaction.atomic
    def get(self, request):
        actor = actor_for(request, self.is_agent)
        authorize(actor, "availability.read")
        data = validated(AvailabilityInput, request.query_params.dict())
        exclude = None
        duration = None
        if data.get("booking_id"):
            exclude = get_object_or_404(
                services.customer_rows(actor, "booking.reschedule", data.get("customer_ref")),
                pk=data["booking_id"],
            )
            if exclude.service_id != data["service"].pk:
                raise ValidationError("改期必須使用原服務項目。")
            if exclude.status != "confirmed" or exclude.start <= timezone.now():
                raise services.BookingError("not_reschedulable")
            duration = int((exclude.end - exclude.start).total_seconds() / 60)
        elif data.get("customer_ref"):
            raise ValidationError("customer_ref 僅用於查詢指定預約的改期空檔。")
        today = timezone.now().astimezone(ZoneInfo(Business.current().timezone)).date()
        first = data.get("date_from", today)
        last = data.get(
            "date_to", first if "date_from" in data else first + timedelta(days=MAX_DAYS - 1)
        )
        try:
            slots = slots_for(
                data["service"],
                first,
                last,
                exclude=exclude,
                duration_minutes=duration,
            )
        except ValueError as exc:
            raise ValidationError(str(exc))
        rows, meta = page_of(slots, data["page"])
        if self.is_agent:
            audit(
                actor,
                "availability.queried",
                customer=exclude.customer.identity if exclude else None,
            )
        return Response(
            {
                "slots": rows,
                "date_from": first,
                "date_to": last,
                **meta,
            }
        )


class BookingsView(APIView):
    is_agent = False

    @transaction.atomic
    def get(self, request):
        actor = actor_for(request, self.is_agent)
        ref = (
            validated(CustomerRefInput, {"customer_ref": request.query_params.get("customer_ref")})[
                "customer_ref"
            ]
            if self.is_agent
            else None
        )
        rows = services.customer_rows(actor, "booking.read", ref)
        if not self.is_agent:

            class Dates(serializers.Serializer):
                date_from = serializers.DateField()
                date_to = serializers.DateField()

            data = validated(Dates, request.query_params)
            first, last = data["date_from"], data["date_to"]
            if last < first or (last - first).days > 62:
                raise ValidationError("請選擇最多 63 天。")
            zone = ZoneInfo(Business.current().timezone)
            lower = timezone.datetime.combine(first, timezone.datetime.min.time(), zone)
            upper = timezone.datetime.combine(
                last + timedelta(days=1), timezone.datetime.min.time(), zone
            )
            rows = rows.filter(start__lt=upper, end__gt=lower)
        page, meta = page_of(
            rows.order_by("-start", "id"),
            request.query_params.get("page", 1),
            size=30 if self.is_agent else 100,
        )
        if self.is_agent:
            from core.models import CustomerIdentity

            audit(
                actor,
                "booking.listed",
                customer=CustomerIdentity.objects.filter(agenrena_customer_ref=ref).first(),
            )
        return Response(
            {
                "results": [payloads.booking(b) for b in page],
                "now": timezone.now().astimezone(ZoneInfo(Business.current().timezone)).isoformat(),
                **meta,
            }
        )

    def post(self, request):
        data = validated(AgentCreateInput if self.is_agent else CreateBookingInput, request.data)
        record = services.create_booking(actor=actor_for(request, self.is_agent), **data)
        return Response(payloads.booking(record), status=201)


class BookingView(APIView):
    is_agent = False

    def patch(self, request, pk):
        data = validated(AgentRescheduleInput if self.is_agent else RescheduleInput, request.data)
        record = services.reschedule_booking(pk, actor=actor_for(request, self.is_agent), **data)
        return Response(payloads.booking(record))


class CancelView(BookingView):
    def post(self, request, pk):
        data = validated(CustomerRefInput, request.data) if self.is_agent else {}
        return Response(
            payloads.booking(
                services.cancel_booking(pk, actor=actor_for(request, self.is_agent), **data)
            )
        )


class AgentShopView(AgentView):
    @transaction.atomic
    def get(self, request):
        actor = agent_actor(request.auth)
        authorize(actor, "catalog.read")
        authorize(actor, "business.read")
        audit(actor, "shop.read")
        return Response(
            {
                **BusinessSerializer(Business.current()).data,
                **SettingsSerializer(BookingSettings.current()).data,
                "services": ServiceSerializer(
                    Service.objects.filter(is_active=True), many=True
                ).data,
                "staff": StaffSerializer(Staff.objects.filter(is_active=True), many=True).data,
                "working_hours": HoursSerializer(
                    WorkingHours.objects.filter(staff__is_active=True), many=True
                ).data,
                "note": "Working hours are not availability; use find_availability.",
            }
        )


class AgentAvailabilityView(AgentView, AvailabilityView):
    is_agent = True


class AgentBookingsView(AgentView, BookingsView):
    is_agent = True


class AgentBookingView(AgentView, BookingView):
    is_agent = True


class AgentCancelView(AgentView, CancelView):
    is_agent = True
