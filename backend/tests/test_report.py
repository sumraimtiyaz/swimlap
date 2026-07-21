"""Tests for the report engine (domain.report) and the reference→report path."""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from app.domain.entities import Lap, ReferenceLap
from app.domain.enums import LapSource, SwimStatus, UserRole
from app.domain.report import build_report
from app.services.lap_service import LapInput

from tests.fakes import Bundle
from tests.test_services import make_swim, make_timer

UTC = timezone.utc
START = datetime(2026, 7, 21, 9, 0, 0, tzinfo=UTC)


def lap(seq, *, server_offset_s, mono, buffered=False, late=False, valid=True):
    return Lap(
        id=seq, swim_id=1, timer_id=1, seq=seq, device_mono_ms=float(mono),
        server_ts=START + timedelta(seconds=server_offset_s), was_buffered=buffered,
        was_late=late, is_valid=valid, source=LapSource.MANUAL,
    )


def ref(lap_no, elapsed, valid=True):
    return ReferenceLap(id=lap_no, swim_id=1, lap_no=lap_no, elapsed_ms=elapsed, is_valid=valid, source="simulated")


class ReportMathTests(unittest.TestCase):
    def test_live_deltas_and_derived_lap1(self):
        laps = [
            lap(1, server_offset_s=40, mono=1000),
            lap(2, server_offset_s=82, mono=2000),   # 42s after lap1
            lap(3, server_offset_s=124, mono=3000),  # 42s after lap2
        ]
        refs = [ref(2, 40900), ref(3, 41700)]
        r = build_report(scheduled_start=START, laps=laps, references=refs)

        self.assertTrue(r.laps[0].derived)
        self.assertAlmostEqual(r.laps[0].recorded_ms, 40000)     # 40s from scheduled start
        self.assertIsNone(r.laps[0].deviation_ms)                 # derived → excluded
        self.assertAlmostEqual(r.laps[1].recorded_ms, 42000)
        self.assertAlmostEqual(r.laps[1].deviation_ms, 1100)
        self.assertAlmostEqual(r.laps[2].deviation_ms, 300)
        # cumulative is the running sum of recorded lap times
        self.assertAlmostEqual(r.laps[2].cumulative_ms, 40000 + 42000 + 42000)
        self.assertAlmostEqual(r.summary.average_deviation_ms, 700)
        self.assertEqual(r.summary.largest_deviation_lap, 2)
        self.assertEqual(r.summary.laps_without_comparison, 1)   # the derived lap

    def test_buffered_laps_use_mono_delta_not_near_zero(self):
        # PRD §2 acceptance: eight taps ~40s apart, uploaded together, must not
        # compute as ~0. All share one arrival server_ts; mono is spaced 40s.
        laps = [lap(i + 1, server_offset_s=360, mono=10000 + i * 40000, buffered=True) for i in range(8)]
        r = build_report(scheduled_start=START, laps=laps, references=[])
        for rl in r.laps[1:]:  # laps 2..8
            self.assertAlmostEqual(rl.recorded_ms, 40000)

    def test_late_excluded_from_average_but_shown(self):
        laps = [
            lap(1, server_offset_s=40, mono=1000),
            lap(2, server_offset_s=82, mono=2000),
            lap(3, server_offset_s=124, mono=3000, late=True),
        ]
        refs = [ref(2, 41000), ref(3, 41000)]
        r = build_report(scheduled_start=START, laps=laps, references=refs)
        self.assertEqual(len(r.laps), 3)                # late lap still appears
        self.assertEqual(r.summary.late_count, 1)
        # only lap 2 is comparable (lap1 derived, lap3 late)
        self.assertAlmostEqual(r.summary.average_deviation_ms, r.laps[1].deviation_ms)

    def test_no_comparable_laps(self):
        laps = [lap(1, server_offset_s=40, mono=1000), lap(2, server_offset_s=82, mono=2000)]
        refs = [ref(2, 41000, valid=False)]  # invalid reference → no comparison
        r = build_report(scheduled_start=START, laps=laps, references=refs)
        self.assertFalse(r.summary.comparable)
        self.assertIsNone(r.summary.average_deviation_ms)

    def test_zero_captures_renders(self):
        r = build_report(scheduled_start=START, laps=[], references=[])
        self.assertEqual(r.summary.laps_recorded, 0)
        self.assertIsNone(r.summary.average_deviation_ms)
        self.assertFalse(r.summary.comparable)


class ReferenceIntegrationTests(unittest.TestCase):
    def _run(self, failure_rate):
        b = Bundle(failure_rate=failure_rate)
        swim = make_swim(b, start=START, target=None)
        t = make_timer(b)
        b.swim_service.assign_timer(swim_id=swim.id, timer_id=t.user.id)
        for i in range(1, 5):
            b.lap_ingest.ingest(swim_id=swim.id, timer_id=t.user.id,
                                laps=[LapInput(seq=i, device_mono_ms=1000.0 + i * 41000)],
                                server_ts=START + timedelta(seconds=41 * i))
        return b.report.build(swim.id)

    def test_references_generated_and_report_comparable(self):
        ctx = self._run(failure_rate=0.0)
        self.assertTrue(ctx.report.simulated)
        # references exist for every valid lap → laps 2+ are comparable
        self.assertTrue(ctx.report.summary.comparable)
        self.assertTrue(all(rl.reference_ms is not None for rl in ctx.report.laps[1:]))

    def test_all_references_invalid_gives_no_comparison(self):
        ctx = self._run(failure_rate=1.0)
        self.assertFalse(ctx.report.summary.comparable)
        self.assertIsNone(ctx.report.summary.average_deviation_ms)


if __name__ == "__main__":
    unittest.main()
