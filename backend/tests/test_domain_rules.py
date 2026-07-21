"""Tests for domain.validation, domain.state_machine, domain.reference."""
from __future__ import annotations

import math
import random
import unittest
from datetime import datetime, timedelta, timezone

from app.domain import state_machine as sm
from app.domain.enums import ClosureMethod, SwimStatus
from app.domain.errors import DomainError
from app.domain.reference import generate_reference
from app.domain.tuning import TUNING, ReferenceTuning
from app.domain.validation import LapCandidate, LapContext, is_late, validate_lap

LI = TUNING.lap_ingest
UTC = timezone.utc


def ctx(**kw):
    base = dict(previous_seq=None, previous_mono_ms=None)
    base.update(kw)
    return LapContext(**base)


class ValidateLapTests(unittest.TestCase):
    def test_clean_lap_is_valid(self):
        v = validate_lap(LapCandidate(1, 1000.0, "manual"), ctx(previous_seq=0, previous_mono_ms=500.0), LI)
        self.assertTrue(v.is_valid)
        self.assertEqual(v.reasons, ())

    def test_nan_mono_is_invalid(self):
        v = validate_lap(LapCandidate(1, math.nan, "manual"), ctx(), LI)
        self.assertFalse(v.is_valid)
        self.assertIn("non_finite_mono", v.reasons)

    def test_infinity_mono_is_invalid(self):
        v = validate_lap(LapCandidate(1, math.inf, "manual"), ctx(), LI)
        self.assertFalse(v.is_valid)

    def test_duplicate_seq_flagged_but_not_hard_invalid(self):
        v = validate_lap(LapCandidate(5, 20000.0, "manual"), ctx(previous_seq=5, previous_mono_ms=1000.0), LI)
        self.assertTrue(v.is_duplicate)
        self.assertTrue(v.is_valid)

    def test_out_of_order_seq_is_invalid(self):
        v = validate_lap(LapCandidate(3, 20000.0, "manual"), ctx(previous_seq=5, previous_mono_ms=1000.0), LI)
        self.assertFalse(v.is_valid)
        self.assertIn("out_of_order_seq", v.reasons)

    def test_debounce_rejects_too_fast_taps(self):
        # min_inter_lap_ms is 250; a 50ms gap is a bounce.
        v = validate_lap(LapCandidate(2, 1050.0, "manual"), ctx(previous_seq=1, previous_mono_ms=1000.0), LI)
        self.assertFalse(v.is_valid)
        self.assertIn("debounced", v.reasons)

    def test_backwards_mono_is_invalid(self):
        v = validate_lap(LapCandidate(2, 500.0, "manual"), ctx(previous_seq=1, previous_mono_ms=1000.0), LI)
        self.assertFalse(v.is_valid)
        self.assertIn("backwards_mono", v.reasons)

    def test_unknown_source_is_invalid(self):
        v = validate_lap(LapCandidate(1, 1000.0, "telepathy"), ctx(), LI)
        self.assertFalse(v.is_valid)
        self.assertIn("unknown_source", v.reasons)

    def test_simulated_source_allowed(self):
        v = validate_lap(LapCandidate(1, 1000.0, "simulated"), ctx(previous_seq=0), LI)
        self.assertTrue(v.is_valid)


class LateTests(unittest.TestCase):
    def test_not_late_when_open(self):
        self.assertFalse(is_late(datetime(2026, 7, 21, 9, 0, tzinfo=UTC), None, LI))

    def test_late_after_close_beyond_grace(self):
        closed = datetime(2026, 7, 21, 9, 0, 0, tzinfo=UTC)
        # grace 1500ms
        self.assertFalse(is_late(closed + timedelta(milliseconds=1400), closed, LI))
        self.assertTrue(is_late(closed + timedelta(milliseconds=1600), closed, LI))


class StateMachineTests(unittest.TestCase):
    def test_legal_and_illegal_transitions(self):
        self.assertTrue(sm.can_transition(SwimStatus.SCHEDULED, SwimStatus.LIVE))
        self.assertTrue(sm.can_transition(SwimStatus.LIVE, SwimStatus.CLOSED))
        self.assertFalse(sm.can_transition(SwimStatus.SCHEDULED, SwimStatus.CLOSED))
        self.assertFalse(sm.can_transition(SwimStatus.CLOSED, SwimStatus.LIVE))
        with self.assertRaises(DomainError):
            sm.assert_transition(SwimStatus.CLOSED, SwimStatus.LIVE)

    def test_accept_submission_all_states(self):
        # First capture takes a scheduled swim live, and closed still accepts buffered.
        self.assertTrue(sm.can_accept_lap_submission(SwimStatus.SCHEDULED))
        self.assertTrue(sm.can_accept_lap_submission(SwimStatus.LIVE))
        self.assertTrue(sm.can_accept_lap_submission(SwimStatus.CLOSED))

    def test_inactivity(self):
        base = datetime(2026, 7, 21, 9, 0, 0, tzinfo=UTC)
        self.assertFalse(sm.should_auto_close_for_inactivity(last_activity=None, now=base, timeout_seconds=900))
        self.assertFalse(sm.should_auto_close_for_inactivity(
            last_activity=base, now=base + timedelta(seconds=899), timeout_seconds=900))
        self.assertTrue(sm.should_auto_close_for_inactivity(
            last_activity=base, now=base + timedelta(seconds=900), timeout_seconds=900))

    def test_closure_method_priority(self):
        self.assertEqual(sm.closure_method_for(timer_completed=True, triggered_by_inactivity=True),
                         ClosureMethod.TIMER_COMPLETED)
        self.assertEqual(sm.closure_method_for(timer_completed=False, triggered_by_inactivity=True),
                         ClosureMethod.AUTO_INACTIVITY)
        self.assertEqual(sm.closure_method_for(timer_completed=False, triggered_by_inactivity=False),
                         ClosureMethod.COORDINATOR)


class ReferenceGeneratorTests(unittest.TestCase):
    def test_failure_rate_zero_is_always_valid(self):
        t = ReferenceTuning(base_lap_ms=40000, variation_ms=1500, failure_rate=0.0)
        rng = random.Random(1)
        for _ in range(50):
            elapsed, valid = generate_reference(t, rng)
            self.assertTrue(valid)
            self.assertGreaterEqual(elapsed, 1)

    def test_failure_rate_one_is_always_invalid(self):
        t = ReferenceTuning(base_lap_ms=40000, variation_ms=1500, failure_rate=1.0)
        rng = random.Random(1)
        for _ in range(50):
            _, valid = generate_reference(t, rng)
            self.assertFalse(valid)

    def test_variation_bounded(self):
        t = ReferenceTuning(base_lap_ms=40000, variation_ms=1500, failure_rate=0.0)
        rng = random.Random(7)
        for _ in range(200):
            elapsed, _ = generate_reference(t, rng)
            self.assertGreaterEqual(elapsed, 40000 - 1500)
            self.assertLessEqual(elapsed, 40000 + 1500)


if __name__ == "__main__":
    unittest.main()
