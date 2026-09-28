from core.permissions import CUSTOMER_REF
from core.serializers import CustomerRefInput, StrictInput
from django.utils import timezone
from rest_framework import serializers

from .models import BookingSettings, Customer, Service, Staff, TimeOff, WorkingHours


class AwareDateTime(serializers.DateTimeField):
    def to_internal_value(self, value):
        from django.utils.dateparse import parse_datetime

        try:
            parsed = parse_datetime(value) if isinstance(value, str) else value
        except (TypeError, ValueError):
            parsed = None
        if parsed is None or not hasattr(parsed, "utcoffset") or timezone.is_naive(parsed):
            raise serializers.ValidationError("請使用包含 UTC offset 的 ISO 8601 時間。")
        return super().to_internal_value(value)


class SettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookingSettings
        fields = ["currency"]

    def validate_currency(self, value):
        if len(value) != 3 or not value.isascii() or not value.isalpha():
            raise serializers.ValidationError("請輸入三碼幣別，例如 TWD。")
        return value.upper()


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ["id", "name", "duration_minutes", "price", "is_active"]


class StaffSerializer(serializers.ModelSerializer):
    class Meta:
        model = Staff
        fields = ["id", "name", "is_active"]


class HoursSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkingHours
        fields = ["id", "staff", "weekday", "start", "end"]

    def validate(self, attrs):
        if attrs.get("end", getattr(self.instance, "end", None)) <= attrs.get(
            "start", getattr(self.instance, "start", None)
        ):
            raise serializers.ValidationError("結束時間必須晚於開始時間，跨日請拆成兩段。")
        return attrs


class TimeOffSerializer(serializers.ModelSerializer):
    start = AwareDateTime()
    end = AwareDateTime()

    class Meta:
        model = TimeOff
        fields = ["id", "staff", "start", "end", "reason"]

    def validate(self, attrs):
        if attrs.get("end", getattr(self.instance, "end", None)) <= attrs.get(
            "start", getattr(self.instance, "start", None)
        ):
            raise serializers.ValidationError("結束時間必須晚於開始時間。")
        return attrs


class CustomerSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="identity.display_name", read_only=True)
    from_agent = serializers.SerializerMethodField()

    def get_from_agent(self, obj):
        return bool(obj.identity.agenrena_customer_ref)

    class Meta:
        model = Customer
        fields = ["id", "name", "phone", "from_agent"]


class CustomerInput(StrictInput):
    name = serializers.CharField(max_length=120)
    phone = serializers.CharField(max_length=40, allow_blank=True, required=False)


class CreateBookingInput(StrictInput):
    service = serializers.PrimaryKeyRelatedField(queryset=Service.objects.all())
    staff_id = serializers.PrimaryKeyRelatedField(queryset=Staff.objects.all())
    start = AwareDateTime()
    note = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")
    customer_id = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.select_related("identity")
    )


class AgentCreateInput(CreateBookingInput, CustomerRefInput):
    customer_id = None
    customer_name = serializers.CharField(max_length=120, required=False)


class RescheduleInput(StrictInput):
    start = AwareDateTime(required=False)
    staff_id = serializers.PrimaryKeyRelatedField(queryset=Staff.objects.all(), required=False)


class AgentRescheduleInput(RescheduleInput, CustomerRefInput):
    pass


class AvailabilityInput(StrictInput):
    service = serializers.PrimaryKeyRelatedField(queryset=Service.objects.all())
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    page = serializers.IntegerField(min_value=1, default=1)
    booking_id = serializers.UUIDField(required=False)
    customer_ref = serializers.RegexField(rf"^{CUSTOMER_REF}$", required=False)
