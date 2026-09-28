from zoneinfo import ZoneInfo

from core.models import Business


def booking(record):
    zone = ZoneInfo(Business.current().timezone)
    return {
        "id": str(record.pk),
        "service": {"id": str(record.service_id), "name": record.service.name},
        "staff": {"id": str(record.staff_id), "name": record.staff.name},
        "customer": {"id": str(record.customer_id), "name": record.customer.name},
        "start": record.start.astimezone(zone).isoformat(),
        "end": record.end.astimezone(zone).isoformat(),
        "price": f"{record.price:.2f}",
        "currency": record.currency,
        "status": record.status,
        "source": record.source,
        "note": record.note,
    }
