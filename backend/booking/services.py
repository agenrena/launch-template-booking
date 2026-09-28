"""Shared writes: human console and customer MCP use the same permissions/rules."""

from datetime import timedelta
from zoneinfo import ZoneInfo

from core.models import Business, CustomerIdentity
from core.permissions import authorize, scoped_customer
from core.services import audit
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .availability import slots_for
from .models import Booking, BookingSettings, Customer, Staff
from .notifications import announce


class BookingError(Exception):
    def __init__(self, code, **details):
        self.body = {"error": code, **details}
        super().__init__(code)


def customer_rows(actor, permission, customer_ref=None):
    rows = Booking.objects.select_related("customer__identity", "service", "staff")
    if actor.kind == "agent":
        _, identity = scoped_customer(actor, permission, customer_ref)
        return rows.filter(customer__identity=identity) if identity else rows.none()
    authorize(actor, permission)
    return rows


def _existing(customer, start, end, exclude=None):
    rows = Booking.objects.filter(
        customer=customer, status="confirmed", start__lt=end, end__gt=start
    )
    if exclude:
        rows = rows.exclude(pk=exclude.pk)
    return rows.first()


def _validate(service, staff, start, *, exclude=None, duration_minutes=None):
    if timezone.is_naive(start):
        raise BookingError("timezone_required")
    if start <= timezone.now():
        raise BookingError("in_past")
    if not service.is_active or not staff.is_active:
        raise BookingError("inactive_resource")
    day = start.astimezone(ZoneInfo(Business.current().timezone)).date()
    slots = slots_for(service, day, day, exclude=exclude, duration_minutes=duration_minutes)
    if not any(
        timezone.datetime.fromisoformat(s["start"]) == start
        and any(p["id"] == str(staff.pk) for p in s["staff"])
        for s in slots
    ):
        nearby = sorted(
            slots,
            key=lambda s: abs(
                (timezone.datetime.fromisoformat(s["start"]) - start).total_seconds()
            ),
        )[:3]
        raise BookingError("slot_unavailable", alternatives=nearby)


@transaction.atomic
def create_booking(
    *,
    actor,
    service,
    staff_id,
    start,
    customer_id=None,
    customer_ref=None,
    customer_name=None,
    note="",
):
    if actor.kind == "agent":
        ref, identity = scoped_customer(actor, "booking.create", customer_ref)
        if identity is None:
            if not customer_name:
                raise ValidationError({"customer_name": "首次預約請提供顧客姓名。"})
            identity, _ = CustomerIdentity.objects.get_or_create(
                agenrena_customer_ref=ref, defaults={"display_name": customer_name}
            )
        identity = CustomerIdentity.objects.select_for_update().get(pk=identity.pk)
        if not identity.display_name:
            if not customer_name:
                raise ValidationError({"customer_name": "請提供顧客姓名。"})
            identity.display_name = customer_name
            identity.save(update_fields=["display_name"])
        customer, _ = Customer.objects.get_or_create(identity=identity)
    else:
        authorize(actor, "booking.create")
        if customer_id is None:
            raise ValidationError({"customer_id": "請選擇顧客。"})
        identity = CustomerIdentity.objects.select_for_update().get(pk=customer_id.identity_id)
        customer = Customer.objects.get(pk=customer_id.pk)
    # Lock order: customer identity, booking (on updates), staff. Staff changes use same staff lock.
    staff = Staff.objects.select_for_update().get(pk=staff_id.pk)
    # Retry identity does not depend on the current catalog duration/price.
    repeated = Booking.objects.filter(
        customer=customer,
        service=service,
        staff=staff,
        start=start,
        status="confirmed",
    ).first()
    if repeated:
        announce(repeated, "created")  # Same message id: Agenrena keeps one copy.
        return repeated
    end = start + timedelta(minutes=service.duration_minutes)
    if existing := _existing(customer, start, end):
        raise BookingError("already_booked", booking_id=str(existing.pk))
    _validate(service, staff, start)
    try:
        with transaction.atomic():
            record = Booking.objects.create(
                customer=customer,
                service=service,
                staff=staff,
                start=start,
                end=end,
                price=service.price,
                currency=BookingSettings.current().currency,
                source="agent" if actor.kind == "agent" else "staff",
                actor=actor.id,
                note=note,
            )
    except IntegrityError:
        _validate(service, staff, start)
        raise BookingError("booking_conflict") from None
    audit(actor, "booking.created", record, customer=identity)
    announce(record, "created")
    return record


@transaction.atomic
def reschedule_booking(booking_id, *, actor, start=None, staff_id=None, customer_ref=None):
    record = get_object_or_404(
        customer_rows(actor, "booking.reschedule", customer_ref), pk=booking_id
    )
    identity = CustomerIdentity.objects.select_for_update().get(pk=record.customer.identity_id)
    record = (
        Booking.objects.select_for_update()
        .select_related("service", "staff", "customer__identity")
        .get(pk=record.pk)
    )
    if record.status != "confirmed" or record.start <= timezone.now():
        raise BookingError("not_reschedulable")
    start = start or record.start
    staff = Staff.objects.select_for_update().get(pk=(staff_id.pk if staff_id else record.staff_id))
    if record.start == start and record.staff_id == staff.pk:
        return record
    duration = int((record.end - record.start).total_seconds() / 60)
    end = start + timedelta(minutes=duration)
    if existing := _existing(record.customer, start, end, exclude=record):
        raise BookingError("already_booked", booking_id=str(existing.pk))
    _validate(record.service, staff, start, exclude=record, duration_minutes=duration)
    try:
        with transaction.atomic():
            record.start, record.end, record.staff = start, end, staff
            record.save(update_fields=["start", "end", "staff"])
    except IntegrityError:
        _validate(record.service, staff, start, exclude=record, duration_minutes=duration)
        raise BookingError("booking_conflict") from None
    audit(actor, "booking.rescheduled", record, customer=identity)
    announce(record, "rescheduled")
    return record


@transaction.atomic
def cancel_booking(booking_id, *, actor, customer_ref=None):
    record = get_object_or_404(customer_rows(actor, "booking.cancel", customer_ref), pk=booking_id)
    identity = CustomerIdentity.objects.select_for_update().get(pk=record.customer.identity_id)
    record = (
        Booking.objects.select_for_update()
        .select_related("customer__identity", "service", "staff")
        .get(pk=record.pk)
    )
    if record.status == "cancelled":
        return record
    if record.start <= timezone.now():
        raise BookingError("in_past")
    record.status = "cancelled"
    record.save(update_fields=["status"])
    audit(actor, "booking.cancelled", record, customer=identity)
    announce(record, "cancelled")
    return record


@transaction.atomic
def save_customer(actor, values, obj=None):
    authorize(actor, "customers.write")
    if obj is None:
        identity = CustomerIdentity.objects.create(display_name=values["name"])
        obj = Customer.objects.create(identity=identity, phone=values.get("phone", ""))
        action = "customer.created"
    else:
        identity = CustomerIdentity.objects.select_for_update().get(pk=obj.identity_id)
        identity.display_name = values.get("name", identity.display_name)
        identity.full_clean()
        identity.save(update_fields=["display_name"])
        obj.phone = values.get("phone", obj.phone)
        obj.full_clean()
        obj.save(update_fields=["phone"])
        action = "customer.updated"
    audit(actor, action, obj, customer=identity, detail={"fields": sorted(values)})
    return obj


@transaction.atomic
def save_catalog(actor, serializer):
    authorize(actor, "catalog.write")
    new = serializer.instance is None
    result = serializer.save()
    audit(
        actor,
        f"{result._meta.model_name}.created" if new else f"{result._meta.model_name}.updated",
        result,
        detail={"fields": sorted(serializer.validated_data)},
    )
    return result


@transaction.atomic
def delete_schedule(actor, obj):
    authorize(actor, "catalog.write")
    audit(actor, f"{obj._meta.model_name}.removed", obj)
    obj.delete()
