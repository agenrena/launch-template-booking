"""Optional synthetic catalog only; no users, passwords, keys or customers."""

from datetime import time

from django.core.management.base import BaseCommand
from django.db import transaction

from booking.models import Service, Staff, WorkingHours


class Command(BaseCommand):
    @transaction.atomic
    def handle(self, *args, **kwargs):
        Service.objects.get_or_create(
            name="基本服務", defaults={"duration_minutes": 60, "price": 1000}
        )
        for person_name in ["示範人員 A", "示範人員 B"]:
            staff, _ = Staff.objects.get_or_create(name=person_name)
            for weekday in range(5):
                WorkingHours.objects.get_or_create(
                    staff=staff, weekday=weekday, start=time(9), end=time(18)
                )
        self.stdout.write(
            "Created a demo service, staff and hours. No credentials or customers created."
        )
