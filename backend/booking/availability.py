"""All scheduling rules live here; HTTP and MCP never calculate availability."""

from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from zoneinfo import ZoneInfo

from core.models import Business
from django.utils import timezone

from .models import Booking, Staff, TimeOff, WorkingHours

MAX_DAYS = 14
GRID_MINUTES = 15


def local_time(day, value, zone):
    """Skip nonexistent DST wall times. For repeated times use the first occurrence."""
    candidate = datetime.combine(day, value, zone)
    restored = candidate.astimezone(dt_timezone.utc).astimezone(zone)
    return candidate if candidate.replace(tzinfo=None) == restored.replace(tzinfo=None) else None


def slots_for(service, first, last, *, exclude=None, now=None, duration_minutes=None):
    if last < first or (last - first).days >= MAX_DAYS:
        raise ValueError(f"Date range must contain 1–{MAX_DAYS} days.")
    if not service.is_active:
        return []
    zone = ZoneInfo(Business.current().timezone)
    now = now or timezone.now()
    staff = list(Staff.objects.filter(is_active=True))
    hours = list(WorkingHours.objects.filter(staff__in=staff))
    # Bound these queries in UTC; pad one day for zones at either edge of UTC.
    lower = datetime.combine(first, datetime.min.time(), dt_timezone.utc) - timedelta(days=1)
    upper = datetime.combine(last, datetime.min.time(), dt_timezone.utc) + timedelta(days=2)
    bookings = Booking.objects.filter(status="confirmed", start__lt=upper, end__gt=lower)
    if exclude:
        bookings = bookings.exclude(pk=exclude.pk)
    busy = list(bookings.values_list("staff_id", "start", "end"))
    busy += list(
        TimeOff.objects.filter(start__lt=upper, end__gt=lower).values_list(
            "staff_id", "start", "end"
        )
    )
    names = {person.id: person.name for person in staff}
    found = {}
    day = first
    while day <= last:
        for hours_row in hours:
            if hours_row.weekday != day.weekday():
                continue
            opening = local_time(day, hours_row.start, zone)
            closing = local_time(day, hours_row.end, zone)
            if opening is None or closing is None:
                continue
            candidate = opening.astimezone(dt_timezone.utc)
            limit = closing.astimezone(dt_timezone.utc)
            while (
                candidate + timedelta(minutes=duration_minutes or service.duration_minutes) <= limit
            ):
                end = candidate + timedelta(minutes=duration_minutes or service.duration_minutes)
                if candidate >= now and not any(
                    s == hours_row.staff_id and a < end and b > candidate for s, a, b in busy
                ):
                    found.setdefault((candidate, end), set()).add(hours_row.staff_id)
                candidate += timedelta(minutes=GRID_MINUTES)
        day += timedelta(days=1)
    return [
        {
            "start": start.astimezone(zone).isoformat(),
            "end": end.astimezone(zone).isoformat(),
            "staff": [
                {"id": str(pk), "name": names[pk]}
                for pk in sorted(ids, key=lambda pk: (names[pk], str(pk)))
            ],
        }
        for (start, end), ids in sorted(found.items())
    ]
