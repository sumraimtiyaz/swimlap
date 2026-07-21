# SwimLap — Timer App (Flutter)

The pool-side app a **timer** uses to record laps for one swimmer by tapping.
Built offline-first: every *confirmed* tap is written to a durable local buffer
before upload, so laps survive dead zones, backgrounding, and app restarts, then
sync when connectivity returns.

## The capture flow (PRD §6)

1. **Tap** → the monotonic timestamp is read in `onPointerDown` (lowest latency,
   before gesture disambiguation), a heavy haptic fires, and the tap becomes a
   **pending capture**.
2. **Confirm** → a Yes/No confirmation shows the lap number. **Yes** (or tapping
   LAP again, or a 10-second auto-confirm) queues it durably with its original
   timestamp and increments the counter; **No** drops it — nothing is sent, the
   counter is unchanged, and the lap number is not consumed. A press within 250 ms
   of the previous capture is treated as a bounce and raises no confirmation.
3. **Sync** → batches are POSTed to `/swims/{id}/laps`, each lap carrying its own
   `seq`, `device_mono_ms`, and a `was_buffered` flag (set when captured offline).
   Acknowledged sequence numbers are pruned from the buffer; duplicates are
   idempotent server-side.
4. **Complete** → a corner **hold-to-end** control (≥ 800 ms, with a filling
   progress ring; a tap does nothing) flushes queued laps and then closes the
   swim. Offline, completion is queued behind the laps and fires on reconnect.

The screen stays awake (`wakelock_plus`) while timing, and the auth token is kept
in the platform secure store (`flutter_secure_storage` — iOS keychain / Android
keystore), never plain preferences. In release builds the client refuses a
non-HTTPS endpoint.

> The server owns the clock: it stamps `server_ts` on arrival for live laps and
> times buffered laps from the `device_mono_ms` delta. There is no device-side
> clock-offset handshake — the phone only sends its monotonic reading.

## Generate the platform folders + run

This repo ships the Dart source (`lib/`) and `pubspec.yaml` but not the generated
`android/` and `ios/` folders. Create them once, then run:

```bash
cd mobile
flutter create .            # generates android/ ios/ etc. around the existing lib/
flutter pub get
flutter test                # unit tests for the capture/confirmation logic
```

Point the app at your backend and run. On the Android emulator the host is
reachable at `10.0.2.2` (the default); override for a device or iOS sim:

```bash
flutter run                                                   # Android emulator
flutter run --dart-define=SWIMLAP_API=http://192.168.1.20:8000   # device / iOS sim
```

Sign in with a **timer** account (issued from the coordinator console), open an
assigned swim, and tap the big pad to record laps.

## Layout

```
lib/
├── core/
│   ├── contract.dart              # Dart mirror of shared/contracts/contract.json
│   ├── clock/monotonic_clock.dart # Stopwatch → device_mono_ms
│   ├── network/                   # http client (HTTPS-only in release) + ApiException
│   ├── storage/                   # durable per-swim lap buffer + PendingLap
│   ├── di/service_locator.dart    # manual singletons; baseUrl via --dart-define
│   └── theme/app_theme.dart       # Material 3 pool-blue theme
├── features/
│   ├── auth/{data,domain,presentation}     # username login; token in secure storage
│   ├── swims/{data,domain,presentation}    # assigned scheduled/live swims
│   └── timing/{data,domain,presentation}   # the tap pad + confirmation + offline sync
├── shared/widgets/
└── main.dart

test/
└── timing_controller_test.dart    # confirmation state machine (no device needed)
```

Each feature is split data / domain / presentation so UI never talks to HTTP
directly and the capture logic is unit-testable in isolation (see
`test/timing_controller_test.dart`, which drives the real controller against
in-memory fakes). State lives in `ChangeNotifier` controllers wired through a
small manual service locator.

## Notes

- `--dart-define=SWIMLAP_API=...` sets the backend origin; the default
  (`http://10.0.2.2:8000`) targets the Android emulator's host loopback.
- The buffer is keyed per swim and stores un-acknowledged laps only; a pending
  capture (awaiting confirmation) is not yet buffered, so if the app is killed
  with a confirmation open that one tap is lost — which is why the 10-second
  auto-confirm exists.
