from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta
from datetime import timezone as dt_timezone
from decimal import Decimal
from unittest.mock import patch
from zoneinfo import ZoneInfo

from core.models import (
    AgenrenaConnection,
    AgentKey,
    AgentPermission,
    AgentRole,
    AuditEvent,
    Business,
    CustomerIdentity,
    Membership,
)
from core.permissions import agent_actor, human_actor
from core.services import update_customer_profile
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import OperationalError, close_old_connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from booking.availability import slots_for
from booking.models import Booking, BookingSettings, Customer, Service, Staff, TimeOff, WorkingHours
from booking.services import BookingError, cancel_booking, create_booking, reschedule_booking

REF_A, REF_B, NEW_REF = (f"bcr_{n:032x}" for n in (0xA, 0xB, 0x1))


def fixtures(obj):
    obj.business = Business.current()
    obj.owner = get_user_model().objects.create_user(
        username="booking_owner", password="Test-password-739!"
    )
    Membership.objects.create(user=obj.owner, role="owner")
    obj.actor = human_actor(obj.owner)
    obj.staff = Staff.objects.create(name="Person A")
    obj.staff_b = Staff.objects.create(name="Person B")
    obj.service = Service.objects.create(name="Haircut", duration_minutes=60, price=100)
    obj.start = (timezone.now() + timedelta(days=7)).replace(
        hour=2, minute=0, second=0, microsecond=0
    )
    obj.day = obj.start.astimezone(ZoneInfo("Asia/Taipei")).date()
    for person in [obj.staff, obj.staff_b]:
        for weekday in range(7):
            WorkingHours.objects.create(staff=person, weekday=weekday, start=time(9), end=time(18))
    obj.identity = CustomerIdentity.objects.create(display_name="Ada", agenrena_customer_ref=REF_A)
    obj.customer = Customer.objects.create(identity=obj.identity)
    obj.identity_b = CustomerIdentity.objects.create(
        display_name="Ben", agenrena_customer_ref=REF_B
    )
    obj.customer_b = Customer.objects.create(identity=obj.identity_b)


class BookingTests(TestCase):
    def setUp(self):
        fixtures(self)
        self.console = APIClient()
        self.console.force_login(self.owner)
        self.role = AgentRole.objects.get(pk="customer_service")
        self.key, self.secret = AgentKey.issue("Customer Agent", self.role)
        self.agent = APIClient()
        self.agent.credentials(HTTP_AUTHORIZATION="Bearer " + self.secret)

    def create(self, **kwargs):
        args = {
            "actor": self.actor,
            "customer_id": self.customer,
            "service": self.service,
            "staff_id": self.staff,
            "start": self.start,
        }
        args.update(kwargs)
        return create_booking(**args)

    def body(self, **kwargs):
        data = {
            "customer_ref": REF_A,
            "service": str(self.service.pk),
            "staff_id": str(self.staff.pk),
            "start": self.start.isoformat(),
        }
        data.update(kwargs)
        return data

    def test_availability_lists_each_free_person(self):
        slots = slots_for(self.service, self.day, self.day)
        self.assertTrue(slots)
        self.assertEqual(
            {p["id"] for s in slots for p in s["staff"]}, {str(self.staff.pk), str(self.staff_b.pk)}
        )
        self.create()
        taken = next(
            s
            for s in slots_for(self.service, self.day, self.day)
            if s["start"] == (self.start.astimezone(ZoneInfo("Asia/Taipei")).isoformat())
        )
        self.assertEqual([p["id"] for p in taken["staff"]], [str(self.staff_b.pk)])

    def test_agent_availability_and_booking(self):
        query = {"service": str(self.service.pk), "date_from": str(self.day)}
        r = self.agent.get("/api/agent-api/availability/", query)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data["slots"])
        r = self.agent.post("/api/agent-api/bookings/", self.body(), format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertNotIn("location", r.data)

    def test_agent_shop_lists_services_staff_and_hours(self):
        r = self.agent.get("/api/agent-api/shop/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            {x["id"] for x in r.data["staff"]}, {str(self.staff.pk), str(self.staff_b.pk)}
        )
        self.assertEqual([x["name"] for x in r.data["services"]], ["Haircut"])
        self.assertNotIn("locations", r.data)

    def test_inactive_staff_blocks_new_booking_but_keeps_history(self):
        b = self.create()
        self.staff.is_active = False
        self.staff.save()
        with self.assertRaises(BookingError) as e:
            self.create(customer_id=self.customer_b, start=self.start + timedelta(hours=2))
        self.assertEqual(e.exception.body["error"], "inactive_resource")
        r = self.console.get(
            "/api/console/bookings/", {"date_from": str(self.day), "date_to": str(self.day)}
        )
        self.assertEqual(r.data["results"][0]["id"], str(b.pk))
        self.assertEqual(cancel_booking(b.pk, actor=self.actor).status, "cancelled")

    def test_retry_keeps_original_duration_price_currency_and_note(self):
        first = self.create(note="Original")
        self.service.price = Decimal("250")
        self.service.duration_minutes = 90
        self.service.save()
        config = BookingSettings.current()
        config.currency = "USD"
        config.save()
        again = self.create(note="Changed")
        self.assertEqual(again.pk, first.pk)
        self.assertEqual(again.price, 100)
        self.assertEqual(again.currency, "TWD")
        self.assertEqual(again.end - again.start, timedelta(minutes=60))
        self.assertEqual(again.note, "Original")
        self.assertEqual(AuditEvent.objects.filter(action="booking.created").count(), 1)

    def test_customer_cannot_overlap_with_another_person(self):
        self.create()
        with self.assertRaises(BookingError) as e:
            self.create(staff_id=self.staff_b)
        self.assertEqual(e.exception.body["error"], "already_booked")
        self.create(customer_id=self.customer_b, staff_id=self.staff_b)
        self.assertEqual(Booking.objects.count(), 2)

    def test_back_to_back_and_cancel_retry(self):
        b = self.create()
        self.create(customer_id=self.customer_b, start=b.end)
        cancel_booking(b.pk, actor=self.actor)
        cancel_booking(b.pk, actor=self.actor)
        self.assertEqual(AuditEvent.objects.filter(action="booking.cancelled").count(), 1)
        again = self.create()
        self.assertNotEqual(again.pk, b.pk)

    def test_reschedule_to_another_person_preserves_snapshot(self):
        b = self.create()
        self.service.duration_minutes = 120
        self.service.price = 300
        self.service.save()
        changed = reschedule_booking(
            b.pk, actor=self.actor, start=self.start + timedelta(hours=2), staff_id=self.staff_b
        )
        self.assertEqual(changed.staff_id, self.staff_b.pk)
        self.assertEqual(changed.end - changed.start, timedelta(minutes=60))
        self.assertEqual(changed.price, 100)
        self.assertEqual(changed.currency, "TWD")

    def test_reschedule_into_a_taken_slot_is_refused_atomically(self):
        b = self.create()
        self.create(customer_id=self.customer_b, staff_id=self.staff_b)
        with self.assertRaises(BookingError):
            reschedule_booking(b.pk, actor=self.actor, staff_id=self.staff_b)
        b.refresh_from_db()
        self.assertEqual(b.staff_id, self.staff.pk)
        self.assertEqual(b.start, self.start)

    def test_time_off_hours_grid_and_past(self):
        TimeOff.objects.create(
            staff=self.staff, start=self.start, end=self.start + timedelta(hours=1)
        )
        slots = slots_for(self.service, self.day, self.day)
        at_start = [
            s
            for s in slots
            if s["start"] == self.start.astimezone(ZoneInfo("Asia/Taipei")).isoformat()
        ]
        self.assertNotIn(str(self.staff.pk), [p["id"] for s in at_start for p in s["staff"]])
        for start in [self.start + timedelta(minutes=7), timezone.now() - timedelta(minutes=10)]:
            with self.assertRaises(BookingError):
                self.create(start=start)
        WorkingHours.objects.all().delete()
        self.assertEqual(slots_for(self.service, self.day, self.day), [])

    def test_duration_and_query_bounds(self):
        self.assertEqual(
            self.console.post(
                "/api/console/services/",
                {"name": "Invalid", "duration_minutes": 0, "price": "10"},
                format="json",
            ).status_code,
            400,
        )
        with self.assertRaises(ValueError):
            slots_for(self.service, self.day, self.day + timedelta(days=14))
        r = self.agent.get(
            "/api/agent-api/availability/", {"service": str(self.service.pk), "page": 0}
        )
        self.assertEqual(r.status_code, 400)

    def test_dst_slots_keep_elapsed_duration(self):
        self.business.timezone = "America/New_York"
        self.business.save()
        WorkingHours.objects.all().delete()
        WorkingHours.objects.create(staff=self.staff, weekday=6, start=time(1), end=time(4))
        for day in [datetime(2030, 3, 10).date(), datetime(2030, 11, 3).date()]:
            slots = slots_for(
                self.service, day, day, now=datetime(2029, 1, 1, tzinfo=dt_timezone.utc)
            )
            self.assertTrue(slots)
            for slot in slots:
                self.assertEqual(
                    datetime.fromisoformat(slot["end"]) - datetime.fromisoformat(slot["start"]),
                    timedelta(minutes=60),
                )

    def test_agent_cannot_list_or_change_another_customer(self):
        b = self.create(customer_id=self.customer_b)
        r = self.agent.get("/api/agent-api/bookings/", {"customer_ref": REF_A})
        self.assertEqual(r.data["count"], 0)
        for method, path, data in [
            (
                "patch",
                f"/api/agent-api/bookings/{b.pk}/",
                {"customer_ref": REF_A, "start": (self.start + timedelta(hours=1)).isoformat()},
            ),
            ("post", f"/api/agent-api/bookings/{b.pk}/cancel/", {"customer_ref": REF_A}),
        ]:
            self.assertEqual(
                getattr(self.agent, method)(path, data, format="json").status_code, 404
            )
        b.refresh_from_db()
        self.assertEqual(b.status, "confirmed")

    def test_agent_must_have_each_permission(self):
        permission = AgentPermission.objects.get(pk="booking.create")
        self.role.permissions.remove(permission)
        self.assertEqual(
            self.agent.post("/api/agent-api/bookings/", self.body(), format="json").status_code, 403
        )
        self.assertEqual(Booking.objects.count(), 0)
        with self.assertRaises(PermissionDenied):
            create_booking(
                actor=agent_actor(self.key),
                service=self.service,
                staff_id=self.staff,
                start=self.start,
                customer_ref=REF_A,
            )

    def test_reschedule_availability_is_scoped_and_uses_original_duration(self):
        b = self.create()
        self.service.duration_minutes = 120
        self.service.save()
        query = {
            "service": str(self.service.pk),
            "date_from": str(self.day),
            "booking_id": str(b.pk),
            "customer_ref": REF_A,
        }
        r = self.agent.get("/api/agent-api/availability/", query)
        self.assertEqual(r.status_code, 200, r.data)
        original = next(
            s for s in r.data["slots"] if datetime.fromisoformat(s["start"]) == self.start
        )
        self.assertEqual(
            datetime.fromisoformat(original["end"]) - datetime.fromisoformat(original["start"]),
            timedelta(minutes=60),
        )
        self.assertEqual(
            self.agent.get(
                "/api/agent-api/availability/", {**query, "customer_ref": REF_B}
            ).status_code,
            404,
        )
        self.assertEqual(
            self.agent.get(
                "/api/agent-api/availability/",
                {k: v for k, v in query.items() if k != "customer_ref"},
            ).status_code,
            400,
        )

    def test_first_agent_booking_reuses_core_profile(self):
        profile = update_customer_profile(agent_actor(self.key), NEW_REF, "New name")
        r = self.agent.post(
            "/api/agent-api/bookings/", self.body(customer_ref=NEW_REF), format="json"
        )
        self.assertEqual(r.status_code, 201, r.data)
        customer = Customer.objects.get(pk=r.data["customer"]["id"])
        self.assertEqual(str(customer.identity_id), profile["id"])
        self.assertEqual(r.data["customer"]["name"], "New name")

    def test_failed_agent_booking_rolls_back_new_customer(self):
        r = self.agent.post(
            "/api/agent-api/bookings/",
            self.body(
                customer_ref=NEW_REF,
                customer_name="New",
                start=(self.start + timedelta(minutes=7)).isoformat(),
            ),
            format="json",
        )
        self.assertEqual(r.status_code, 409)
        self.assertFalse(CustomerIdentity.objects.filter(agenrena_customer_ref=NEW_REF).exists())
        self.assertEqual(Customer.objects.count(), 2)

    def test_agent_first_contact_requires_name_and_does_not_merge_same_name(self):
        r = self.agent.post(
            "/api/agent-api/bookings/", self.body(customer_ref=NEW_REF), format="json"
        )
        self.assertEqual(r.status_code, 400)
        r = self.agent.post(
            "/api/agent-api/bookings/",
            self.body(customer_ref=NEW_REF, customer_name="Ada"),
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertNotEqual(r.data["customer"]["id"], str(self.customer.pk))

    def test_console_customer_updates_same_core_identity(self):
        r = self.console.patch(
            f"/api/console/customers/{self.customer.pk}/",
            {"name": "New Ada", "phone": "123"},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(
            self.agent.get("/api/agent-api/customer-profile/", {"customer_ref": REF_A}).data[
                "profile"
            ]["display_name"],
            "New Ada",
        )
        r = self.console.post(
            "/api/console/customers/", {"name": "Manual", "phone": "456"}, format="json"
        )
        self.assertEqual(r.status_code, 201)
        self.assertIsNone(Customer.objects.get(pk=r.data["id"]).identity.agenrena_customer_ref)
        self.assertEqual(
            self.console.patch(
                f"/api/console/customers/{self.customer.pk}/",
                {"agenrena_customer_ref": "forged"},
                format="json",
            ).status_code,
            400,
        )

    def test_calendar_range_and_customer_search(self):
        a = self.create()
        b = self.create(customer_id=self.customer_b, staff_id=self.staff_b)
        query = {"date_from": str(self.day), "date_to": str(self.day)}
        r = self.console.get("/api/console/bookings/", query)
        self.assertEqual({x["id"] for x in r.data["results"]}, {str(a.pk), str(b.pk)})
        later = self.day + timedelta(days=1)
        r = self.console.get(
            "/api/console/bookings/", {"date_from": str(later), "date_to": str(later)}
        )
        self.assertEqual(r.data["count"], 0)
        self.assertEqual(self.console.get("/api/console/customers/?q=Ada").data["count"], 1)

    def test_catalog_schedule_and_bookings_are_audited_without_private_values(self):
        r = self.console.post(
            "/api/console/services/",
            {"name": "Private service", "duration_minutes": 30, "price": "25"},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        b = self.create(note="Private note")
        reschedule_booking(b.pk, actor=self.actor, start=self.start + timedelta(hours=2))
        cancel_booking(b.pk, actor=self.actor)
        audit = list(AuditEvent.objects.values())
        for action in [
            "service.created",
            "booking.created",
            "booking.rescheduled",
            "booking.cancelled",
        ]:
            self.assertTrue(any(e["action"] == action for e in audit))
        self.assertNotIn("Private note", str(audit))
        self.assertNotIn("Private service", str(audit))

    def test_strict_agent_inputs_and_offsets(self):
        for extra in [
            {"customer_id": str(self.customer_b.pk)},
            {"location": "anything"},
            {"role": "owner"},
        ]:
            self.assertEqual(
                self.agent.post(
                    "/api/agent-api/bookings/", self.body(**extra), format="json"
                ).status_code,
                400,
            )
        self.assertEqual(
            self.agent.post(
                "/api/agent-api/bookings/", self.body(start="2030-01-01T10:00:00"), format="json"
            ).status_code,
            400,
        )

    def test_failed_audit_rolls_back_booking(self):
        with (
            patch("booking.services.audit", side_effect=RuntimeError("failure")),
            self.assertRaises(RuntimeError),
        ):
            self.create()
        self.assertEqual(Booking.objects.count(), 0)


@override_settings(AGENRENA_VENDOR_ID="vendor-1", AGENRENA_VENDOR_SECRET="bvs_private")
class BookingNotificationTests(TestCase):
    """Booking changes reach the customer's conversation with the store."""

    def setUp(self):
        from core.tests.test_agenrena import FakeAgenrena

        fixtures(self)
        cache.clear()
        self.platform = FakeAgenrena()
        patcher = patch("core.agenrena._request", self.platform)
        patcher.start()
        self.addCleanup(patcher.stop)
        AgenrenaConnection.objects.create(status="connected", grant_id="grant-store")
        role = AgentRole.objects.get(pk="customer_service")
        _, secret = AgentKey.issue("Store Agent", role)
        self.agent = APIClient()
        self.agent.credentials(HTTP_AUTHORIZATION="Bearer " + secret)

    def sent(self):
        return [c for c in self.platform.calls if c["path"].endswith("/messages/send/")]

    def test_created_rescheduled_and_cancelled_are_announced(self):
        body = {
            "customer_ref": REF_A,
            "service": str(self.service.pk),
            "staff_id": str(self.staff.pk),
            "start": self.start.isoformat(),
            "note": "Private note",
        }
        with self.captureOnCommitCallbacks(execute=True):
            created = self.agent.post("/api/agent-api/bookings/", body, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        booking_id = created.data["id"]
        with self.captureOnCommitCallbacks(execute=True):
            self.agent.post("/api/agent-api/bookings/", body, format="json")  # retry
            reschedule_booking(booking_id, actor=self.actor, start=self.start + timedelta(hours=2))
            cancel_booking(booking_id, actor=self.actor)
        sent = self.sent()
        self.assertEqual({c["grant_id"] for c in sent}, {"grant-store"})
        self.assertEqual(
            [c["body"]["card"]["header"] for c in sent],
            ["預約已確認", "預約已確認", "預約已改期", "預約已取消"],
        )
        # The retry repeats the same message id, so Agenrena keeps one copy.
        self.assertEqual(sent[0]["body"]["client_message_id"], f"booking-{booking_id}-created")
        self.assertEqual(sent[1]["body"]["client_message_id"], sent[0]["body"]["client_message_id"])
        rows = {r["label"]: r["value"] for r in sent[0]["body"]["card"]["content"]}
        self.assertEqual(
            {k: rows[k] for k in ["服務", "人員", "金額"]},
            {"服務": "Haircut", "人員": "Person A", "金額": "TWD 100"},
        )
        self.assertIn(rows["時間"], sent[0]["body"]["text"])
        self.assertNotIn("Private note", str(sent))
        for message in sent:
            self.assertLessEqual(len(message["body"]["text"]), 200)

    def test_staff_booking_for_an_agent_customer_is_announced(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.create_by_staff(self.customer)
        (message,) = self.sent()
        self.assertEqual(message["body"]["customer_ref"], REF_A)

    def test_customers_without_reference_are_not_messaged(self):
        walk_in = Customer.objects.create(
            identity=CustomerIdentity.objects.create(display_name="W")
        )
        with self.captureOnCommitCallbacks(execute=True):
            self.create_by_staff(walk_in)
        self.assertEqual(self.sent(), [])

    def test_delivery_failure_keeps_the_booking(self):
        self.platform.send_error = (503, {"error": {"code": "INTERNAL_ERROR"}})
        with self.captureOnCommitCallbacks(execute=True):
            record = self.create_by_staff(self.customer)
        self.assertTrue(Booking.objects.filter(pk=record.pk, status="confirmed").exists())
        self.assertTrue(AuditEvent.objects.filter(action="agenrena.message_failed").exists())

    def create_by_staff(self, customer):
        return create_booking(
            actor=self.actor,
            customer_id=customer,
            service=self.service,
            staff_id=self.staff,
            start=self.start,
        )


@override_settings(AGENRENA_VENDOR_ID="vendor-1", AGENRENA_VENDOR_SECRET="bvs_private")
class BookingNotificationCommitTests(TransactionTestCase):
    """HTTP results stay successful when delivery fails after a real commit."""

    def setUp(self):
        from core.tests.test_agenrena import FakeAgenrena

        fixtures(self)
        cache.clear()
        self.platform = FakeAgenrena()
        patcher = patch("core.agenrena._request", self.platform)
        patcher.start()
        self.addCleanup(patcher.stop)
        AgenrenaConnection.objects.create(status="connected", grant_id="grant-store")
        self.console = APIClient()
        self.console.force_login(self.owner)

    def booking_lifecycle(self):
        created = self.console.post(
            "/api/console/bookings/",
            {
                "customer_id": str(self.customer.pk),
                "service": str(self.service.pk),
                "staff_id": str(self.staff.pk),
                "start": self.start.isoformat(),
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        record = Booking.objects.get(pk=created.data["id"])
        self.assertEqual(record.status, "confirmed")
        path = f"/api/console/bookings/{record.pk}/"
        later = self.start + timedelta(hours=2)
        changed = self.console.patch(path, {"start": later.isoformat()}, format="json")
        self.assertEqual(changed.status_code, 200, changed.data)
        record.refresh_from_db()
        self.assertEqual(record.start, later)
        cancelled = self.console.post(path + "cancel/", {}, format="json")
        self.assertEqual(cancelled.status_code, 200, cancelled.data)
        record.refresh_from_db()
        self.assertEqual(record.status, "cancelled")
        for action in ("booking.created", "booking.rescheduled", "booking.cancelled"):
            self.assertTrue(AuditEvent.objects.filter(action=action).exists())

    def test_unexpected_delivery_error_keeps_all_booking_changes(self):
        with patch("core.agenrena._request", side_effect=ValueError("private delivery error")):
            self.booking_lifecycle()
        failures = AuditEvent.objects.filter(action="agenrena.message_failed")
        self.assertEqual(failures.count(), 3)
        self.assertTrue(all(e.detail == {"error": "DELIVERY_OUTCOME_UNKNOWN"} for e in failures))

    def test_notification_audit_failure_keeps_all_booking_changes(self):
        # Booking imports its own audit function; only notification auditing fails.
        with (
            patch("core.services.audit", side_effect=OperationalError("private audit error")),
            self.assertLogs("core.services", level="ERROR") as logs,
        ):
            self.booking_lifecycle()
        self.assertEqual(
            logs.output,
            ["ERROR:core.services:Agenrena delivery outcome could not be recorded."] * 3,
        )
        self.assertEqual(
            len([c for c in self.platform.calls if c["path"].endswith("/messages/send/")]), 3
        )


class BookingConcurrencyTests(TransactionTestCase):
    def setUp(self):
        fixtures(self)

    def run_write(self, customer_pk):
        close_old_connections()
        try:
            return create_booking(
                actor=human_actor(get_user_model().objects.get(pk=self.owner.pk)),
                service=Service.objects.get(pk=self.service.pk),
                staff_id=Staff.objects.get(pk=self.staff.pk),
                start=self.start,
                customer_id=Customer.objects.select_related("identity").get(pk=customer_pk),
            ).pk
        except BookingError:
            return None
        finally:
            close_old_connections()

    def test_simultaneous_retry_is_one_booking(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(self.run_write, [self.customer.pk, self.customer.pk]))
        self.assertIsNotNone(ids[0])
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(Booking.objects.count(), 1)

    def test_simultaneous_customers_cannot_double_book(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(self.run_write, [self.customer.pk, self.customer_b.pk]))
        self.assertEqual(sum(i is not None for i in ids), 1)
        self.assertEqual(Booking.objects.count(), 1)
