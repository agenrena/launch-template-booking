"""What the customer sees in their Agenrena conversation when a booking changes.

Facts only — service, person, time and price. Notes stay private. The store is
the sender, so it is not repeated. Customers without a reference (entered by
staff) are skipped by the core.
"""

import hashlib
from decimal import Decimal
from zoneinfo import ZoneInfo

from core.models import Business
from core.services import notify_customer

EVENTS = {
    "created": ("預約已確認", "success"),
    "rescheduled": ("預約已改期", "info"),
    "cancelled": ("預約已取消", "cancelled"),
}
WEEKDAYS = "一二三四五六日"


def announce(record, event):
    header, status = EVENTS[event]
    start = record.start.astimezone(ZoneInfo(Business.current().timezone))
    when = f"{start.month}/{start.day}（{WEEKDAYS[start.weekday()]}）{start:%H:%M}"
    rows = [
        ("服務", record.service.name),
        ("人員", record.staff.name),
        ("時間", when),
        ("金額", money(record.price, record.currency)),
    ]
    notify_customer(
        record.customer.identity,
        clip(" · ".join([header, record.service.name, when]), 200),
        card={
            "status": status,
            "header": header,
            "content": [{"label": label, "value": clip(value, 200)} for label, value in rows],
        },
        message_id=message_id(record, event),
    )


def message_id(record, event):
    """Stable per fact, so a retried request never posts twice (Agenrena dedupes)."""
    if event != "rescheduled":
        return f"booking-{record.pk}-{event}"
    change = f"{record.start.isoformat()}|{record.staff_id}"
    return f"booking-{record.pk}-rescheduled-{hashlib.sha256(change.encode()).hexdigest()[:12]}"


def money(value, currency):
    value = Decimal(value)
    shown = f"{value:,.0f}" if value == value.to_integral_value() else f"{value:,.2f}"
    return f"{currency} {shown}"


def clip(value, limit):
    return value if len(value) <= limit else value[: limit - 1] + "…"
