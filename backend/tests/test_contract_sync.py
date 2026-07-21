"""Guards the DRY invariant: the Python domain must match shared/contracts.

If someone edits an enum value or a threshold in code but forgets the JSON (or
vice-versa), this test fails and points at the drift.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from app.domain.enums import ClosureMethod, LapSource, SwimStatus, UserRole
from app.domain.tuning import TUNING

CONTRACT = json.loads(
    (Path(__file__).resolve().parents[2] / "shared" / "contracts" / "contract.json").read_text()
)


class EnumSyncTests(unittest.TestCase):
    def test_enums_match_contract(self):
        enums = CONTRACT["enums"]
        self.assertEqual([r.value for r in UserRole], enums["UserRole"])
        self.assertEqual([s.value for s in SwimStatus], enums["SwimStatus"])
        self.assertEqual([c.value for c in ClosureMethod], enums["ClosureMethod"])
        self.assertEqual([s.value for s in LapSource], enums["LapSource"])


class TuningSyncTests(unittest.TestCase):
    def test_tuning_matches_contract(self):
        t = CONTRACT["timing"]
        self.assertEqual(TUNING.lap_ingest.late_grace_ms, t["lapIngest"]["lateGraceMs"])
        self.assertEqual(TUNING.lap_ingest.max_laps_per_batch, t["lapIngest"]["maxLapsPerBatch"])
        self.assertEqual(TUNING.lap_ingest.min_inter_lap_ms, t["lapIngest"]["minInterLapMs"])
        self.assertEqual(TUNING.swim.auto_inactivity_timeout_seconds, t["swim"]["autoInactivityTimeoutSeconds"])
        self.assertEqual(TUNING.swim.default_lane_count, t["swim"]["defaultLaneCount"])
        self.assertEqual(TUNING.swim.max_lane_count, t["swim"]["maxLaneCount"])
        self.assertEqual(TUNING.auth.token_ttl_hours, t["auth"]["tokenTtlHours"])
        self.assertEqual(TUNING.auth.max_failed_attempts, t["auth"]["maxFailedAttempts"])
        self.assertEqual(TUNING.auth.lockout_minutes, t["auth"]["lockoutMinutes"])
        self.assertEqual(TUNING.reference.base_lap_ms, t["reference"]["baseLapMs"])
        self.assertEqual(TUNING.reference.variation_ms, t["reference"]["variationMs"])
        self.assertEqual(TUNING.reference.failure_rate, t["reference"]["failureRate"])


if __name__ == "__main__":
    unittest.main()
