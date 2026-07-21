"""System clock adapter.

Reads wall-clock time, which in production is disciplined by **chrony** (see
``infra/`` and ``docs/ARCHITECTURE.md``). We deliberately keep this behind the
``Clock`` port: the offset math never trusts a single reading, but the server's
own timeline is the reference every device is reconciled against, so keeping it
accurate (NTP) matters.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone


class SystemClock:
    def now_ms(self) -> float:
        # time.time() is wall-clock (chrony-disciplined). Milliseconds since epoch.
        return time.time() * 1000.0

    def now(self) -> datetime:
        return datetime.now(tz=timezone.utc)
