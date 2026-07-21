"""Integration-style service tests over the in-memory adapters (no DB, no FastAPI)."""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from app.domain.entities import Swimmer, Venue
from app.domain.enums import ClosureMethod, SwimStatus, UserRole
from app.domain.errors import DomainError, ErrorCode
from app.services.lap_service import LapInput

from tests.fakes import Bundle

UTC = timezone.utc
START = datetime(2026, 7, 21, 9, 0, 0, tzinfo=UTC)


def make_timer(b: Bundle, username="t1", name="Timer One"):
    return b.user_admin.create_user(username=username, display_name=name, role=UserRole.TIMER)


def make_venue(b: Bundle, lanes=8):
    return b.venues.add(Venue(id=0, name="Aqua Center", lane_count=lanes))


def make_swimmer(b: Bundle, name="Alex Rivera"):
    return b.swimmers.add(Swimmer(id=0, name=name))


def make_swim(b: Bundle, *, lane=1, start=START, target=None):
    v = make_venue(b)
    s = make_swimmer(b)
    return b.swim_service.create_swim(venue_id=v.id, swimmer_id=s.id, lane_no=lane,
                                      scheduled_start=start, lap_target=target)


class AuthTests(unittest.TestCase):
    def test_login_and_wrong_password(self):
        b = Bundle()
        issued = make_timer(b)
        self.assertTrue(b.auth.login("t1", issued.password).token)
        with self.assertRaises(DomainError) as e:
            b.auth.login("t1", "nope")
        self.assertEqual(e.exception.code, ErrorCode.AUTH_INVALID_CREDENTIALS)

    def test_lockout_after_five_failures(self):
        b = Bundle()
        make_timer(b)
        for _ in range(5):
            with self.assertRaises(DomainError):
                b.auth.login("t1", "wrong")
        with self.assertRaises(DomainError) as e:
            b.auth.login("t1", "wrong")
        self.assertEqual(e.exception.code, ErrorCode.AUTH_LOCKED)

    def test_lockout_expires(self):
        b = Bundle()
        issued = make_timer(b)
        for _ in range(5):
            with self.assertRaises(DomainError):
                b.auth.login("t1", "wrong")
        b.clock.advance(16 * 60)  # past the 15-minute lockout
        self.assertTrue(b.auth.login("t1", issued.password).token)

    def test_deactivated_account_cannot_login(self):
        b = Bundle()
        issued = make_timer(b)
        b.user_admin.deactivate(issued.user.id)
        with self.assertRaises(DomainError) as e:
            b.auth.login("t1", issued.password)
        self.assertEqual(e.exception.code, ErrorCode.AUTH_ACCOUNT_DISABLED)


class AccountAdminTests(unittest.TestCase):
    def test_password_generated_and_hashed(self):
        b = Bundle()
        issued = make_timer(b)
        self.assertTrue(issued.password)
        stored = b.users.get_by_username("t1")
        self.assertNotEqual(issued.password, stored.hashed_password)  # stored hashed, not plaintext

    def test_duplicate_username_rejected(self):
        b = Bundle()
        make_timer(b)
        with self.assertRaises(DomainError):
            make_timer(b)

    def test_reset_password_changes_and_revokes(self):
        b = Bundle()
        issued = make_timer(b)
        old = b.users.get_by_username("t1").hashed_password
        reset = b.user_admin.reset_password(issued.user.id)
        new = b.users.get_by_username("t1").hashed_password
        self.assertNotEqual(old, new)
        self.assertIsNotNone(b.users.get_by_username("t1").tokens_valid_from)
        self.assertTrue(b.auth.login("t1", reset.password).token)

    def test_deactivate_keeps_record(self):
        b = Bundle()
        issued = make_timer(b)
        b.user_admin.deactivate(issued.user.id)
        self.assertFalse(b.users.get_by_id(issued.user.id).is_active)


class SwimLifecycleTests(unittest.TestCase):
    def test_create_rejects_lane_beyond_venue(self):
        b = Bundle()
        v = make_venue(b, lanes=4)
        s = make_swimmer(b)
        with self.assertRaises(DomainError):
            b.swim_service.create_swim(venue_id=v.id, swimmer_id=s.id, lane_no=5,
                                       scheduled_start=START, lap_target=10)

    def test_assign_only_timers_and_one_per_swim(self):
        b = Bundle()
        swim = make_swim(b)
        coord = b.user_admin.create_user(username="c2", display_name="Coord", role=UserRole.COORDINATOR)
        with self.assertRaises(DomainError):
            b.swim_service.assign_timer(swim_id=swim.id, timer_id=coord.user.id)
        t1 = make_timer(b, "t1")
        t2 = make_timer(b, "t2")
        b.swim_service.assign_timer(swim_id=swim.id, timer_id=t1.user.id)
        with self.assertRaises(DomainError):
            b.swim_service.assign_timer(swim_id=swim.id, timer_id=t2.user.id)

    def test_overlapping_assignment_rejected(self):
        b = Bundle()
        v = make_venue(b)
        sw = make_swimmer(b)
        t1 = make_timer(b, "t1")
        a = b.swim_service.create_swim(venue_id=v.id, swimmer_id=sw.id, lane_no=1,
                                       scheduled_start=START, lap_target=20)  # ~15min window
        near = b.swim_service.create_swim(venue_id=v.id, swimmer_id=sw.id, lane_no=2,
                                          scheduled_start=START + timedelta(minutes=10), lap_target=20)
        far = b.swim_service.create_swim(venue_id=v.id, swimmer_id=sw.id, lane_no=3,
                                         scheduled_start=START + timedelta(hours=1), lap_target=20)
        b.swim_service.assign_timer(swim_id=a.id, timer_id=t1.user.id)
        with self.assertRaises(DomainError) as e:
            b.swim_service.assign_timer(swim_id=near.id, timer_id=t1.user.id)
        self.assertEqual(e.exception.code, ErrorCode.OVERLAPPING_ASSIGNMENT)
        self.assertTrue(b.swim_service.assign_timer(swim_id=far.id, timer_id=t1.user.id))

    def test_first_capture_takes_live_and_origin_unchanged(self):
        b = Bundle()
        swim = make_swim(b, start=START)
        t1 = make_timer(b)
        b.swim_service.assign_timer(swim_id=swim.id, timer_id=t1.user.id)
        res = b.lap_ingest.ingest(swim_id=swim.id, timer_id=t1.user.id,
                                  laps=[LapInput(seq=1, device_mono_ms=1000.0)],
                                  server_ts=START + timedelta(seconds=40))
        self.assertTrue(res.went_live)
        self.assertEqual(res.swim_status, SwimStatus.LIVE)
        self.assertEqual(b.swims.get(swim.id).scheduled_start, START)

    def test_complete_closes_as_timer_completed(self):
        b = Bundle()
        swim = make_swim(b)
        t1 = make_timer(b)
        b.swim_service.assign_timer(swim_id=swim.id, timer_id=t1.user.id)
        b.lap_ingest.ingest(swim_id=swim.id, timer_id=t1.user.id,
                            laps=[LapInput(seq=1, device_mono_ms=1000.0)],
                            server_ts=START + timedelta(seconds=40))
        closed = b.swim_service.close_swim(swim.id, method=ClosureMethod.TIMER_COMPLETED)
        self.assertEqual(closed.status, SwimStatus.CLOSED)
        self.assertEqual(closed.closure_method, ClosureMethod.TIMER_COMPLETED)

    def test_auto_close_after_inactivity(self):
        b = Bundle()
        swim = make_swim(b)
        t1 = make_timer(b)
        b.swim_service.assign_timer(swim_id=swim.id, timer_id=t1.user.id)
        b.lap_ingest.ingest(swim_id=swim.id, timer_id=t1.user.id,
                            laps=[LapInput(seq=1, device_mono_ms=1000.0)], server_ts=b.clock.now())
        self.assertIsNone(b.swim_service.auto_close_if_inactive(swim.id))
        b.clock.advance(15 * 60 + 1)  # past the 15-minute window
        closed = b.swim_service.auto_close_if_inactive(swim.id)
        self.assertIsNotNone(closed)
        self.assertEqual(closed.closure_method, ClosureMethod.AUTO_INACTIVITY)


class LapIngestTests(unittest.TestCase):
    def _assigned(self, b):
        swim = make_swim(b, start=START, target=3)
        t1 = make_timer(b)
        b.swim_service.assign_timer(swim_id=swim.id, timer_id=t1.user.id)
        return swim, t1.user

    def test_ownership_enforced(self):
        b = Bundle()
        swim, _ = self._assigned(b)
        other = make_timer(b, "t2")
        with self.assertRaises(DomainError) as e:
            b.lap_ingest.ingest(swim_id=swim.id, timer_id=other.user.id,
                                laps=[LapInput(seq=1, device_mono_ms=1000.0)])
        self.assertEqual(e.exception.code, ErrorCode.NOT_ASSIGNED)

    def test_idempotent_same_seq(self):
        b = Bundle()
        swim, user = self._assigned(b)
        b.lap_ingest.ingest(swim_id=swim.id, timer_id=user.id,
                            laps=[LapInput(seq=1, device_mono_ms=1000.0)], server_ts=START + timedelta(seconds=40))
        res = b.lap_ingest.ingest(swim_id=swim.id, timer_id=user.id,
                                  laps=[LapInput(seq=1, device_mono_ms=1000.0)], server_ts=START + timedelta(seconds=41))
        self.assertEqual(res.outcomes[0].status, "duplicate")
        self.assertEqual(len(b.laps.list_for_swim(swim.id)), 1)

    def test_no_cap_past_target(self):
        b = Bundle()
        swim, user = self._assigned(b)  # target 3
        for i in range(1, 6):
            b.lap_ingest.ingest(swim_id=swim.id, timer_id=user.id,
                                laps=[LapInput(seq=i, device_mono_ms=1000.0 + i * 40000)],
                                server_ts=START + timedelta(seconds=40 * i))
        self.assertEqual(len(b.laps.list_for_swim(swim.id)), 5)
        self.assertEqual(b.swims.get(swim.id).status, SwimStatus.LIVE)

    def test_late_capture_after_close(self):
        b = Bundle()
        swim, user = self._assigned(b)
        b.lap_ingest.ingest(swim_id=swim.id, timer_id=user.id,
                            laps=[LapInput(seq=1, device_mono_ms=1000.0)], server_ts=START + timedelta(seconds=40))
        b.swim_service.close_swim(swim.id, method=ClosureMethod.COORDINATOR)
        closed_at = b.swims.get(swim.id).closed_at
        res = b.lap_ingest.ingest(
            swim_id=swim.id, timer_id=user.id,
            laps=[LapInput(seq=2, device_mono_ms=81000.0, was_buffered=True)],
            server_ts=closed_at + timedelta(seconds=5))
        self.assertTrue(res.outcomes[0].was_late)
        self.assertEqual(len(b.laps.list_for_swim(swim.id)), 2)


class PresenceTests(unittest.TestCase):
    def test_ping_then_offline(self):
        b = Bundle()
        b.presence.ping(42)
        self.assertTrue(b.presence.is_connected(42))
        b.clock.advance(31)
        self.assertFalse(b.presence.is_connected(42))
        self.assertFalse(b.presence.is_connected(99))


if __name__ == "__main__":
    unittest.main()
