"""Editable Booking domain for one store, using the local copy of Business Core."""

from core.models import CustomerIdentity, Record
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeBoundary, RangeOperators
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class BookingSettings(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    currency = models.CharField(max_length=3, default="TWD")

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(id=1), name="one_booking_settings")
        ]

    @classmethod
    def current(cls):
        return cls.objects.get_or_create(pk=1)[0]


class Service(Record):
    name = models.CharField(max_length=120, unique=True)
    duration_minutes = models.PositiveIntegerField(
        validators=[MinValueValidator(5), MaxValueValidator(1440)]
    )
    price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]


class Staff(Record):
    name = models.CharField(max_length=120, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]


class WorkingHours(Record):
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name="hours")
    weekday = models.PositiveSmallIntegerField(validators=[MaxValueValidator(6)])  # Monday = 0
    start = models.TimeField()
    end = models.TimeField()

    class Meta:
        ordering = ["weekday", "start"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end__gt=models.F("start")), name="hours_forward"
            )
        ]


class TimeOff(Record):
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name="time_off")
    start = models.DateTimeField()
    end = models.DateTimeField()
    reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["start"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end__gt=models.F("start")), name="time_off_forward"
            )
        ]


class Customer(Record):
    identity = models.OneToOneField(
        CustomerIdentity, on_delete=models.PROTECT, related_name="booking_customer"
    )
    phone = models.CharField(max_length=40, blank=True)

    @property
    def name(self):
        return self.identity.display_name

    class Meta:
        ordering = ["identity__display_name", "id"]


class TsTzRange(models.Func):
    function = "TSTZRANGE"
    output_field = DateTimeRangeField()


class Booking(Record):
    currency = models.CharField(max_length=3)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    service = models.ForeignKey(Service, on_delete=models.PROTECT)
    staff = models.ForeignKey(Staff, on_delete=models.PROTECT)
    start = models.DateTimeField()
    end = models.DateTimeField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=12,
        choices=[("confirmed", "Confirmed"), ("cancelled", "Cancelled")],
        default="confirmed",
    )
    source = models.CharField(max_length=8, choices=[("staff", "Staff"), ("agent", "Agent")])
    actor = models.CharField(max_length=150)
    note = models.TextField(blank=True, max_length=2000)

    class Meta:
        ordering = ["-start"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end__gt=models.F("start")), name="booking_forward"
            ),
            *[
                ExclusionConstraint(
                    name=f"booking_no_overlap_{field}",
                    expressions=[
                        (field, RangeOperators.EQUAL),
                        (TsTzRange("start", "end", RangeBoundary()), RangeOperators.OVERLAPS),
                    ],
                    condition=models.Q(status="confirmed"),
                )
                for field in ("staff", "customer")
            ],
        ]
