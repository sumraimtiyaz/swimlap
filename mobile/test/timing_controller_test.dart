// Unit tests for the capture + confirmation state machine (PRD §6.4–§6.5).
//
// These exercise the real TimingController against in-memory fakes for the lap
// buffer and the HTTP repository, so they run with `flutter test` on any machine
// — no device, no plugins (secure storage / wakelock / connectivity are only
// touched by init()/dispose(), which these tests deliberately don't call), and
// no server. The controller's confirmation logic is pure and synchronous, which
// is exactly what we assert on.
import 'package:flutter_test/flutter_test.dart';

import 'package:swimlap/core/storage/lap_buffer.dart';
import 'package:swimlap/core/storage/pending_lap.dart';
import 'package:swimlap/features/timing/data/timing_repository.dart';
import 'package:swimlap/features/timing/presentation/timing_controller.dart';

/// In-memory buffer. `addedLog` records every persisted lap in commit order, so
/// tests can assert deterministically on what was captured (add() is awaited
/// first inside the controller's commit path, so log order == commit order).
class FakeLapBuffer implements LapBuffer {
  final Map<int, List<PendingLap>> _store = {};
  final List<PendingLap> addedLog = [];

  @override
  Future<List<PendingLap>> load(int swimId) async => List.of(_store[swimId] ?? const []);

  @override
  Future<void> add(int swimId, PendingLap lap) async {
    addedLog.add(lap);
    (_store.putIfAbsent(swimId, () => [])).add(lap);
  }

  @override
  Future<void> ackSeqs(int swimId, Set<int> confirmed) async {
    _store[swimId]?.removeWhere((l) => confirmed.contains(l.seq));
  }
}

class FakeTimingRepository implements TimingRepository {
  @override
  Future<SubmitResult> submit({required int swimId, required List<PendingLap> laps}) async {
    return SubmitResult(
      confirmedSeqs: laps.map((l) => l.seq).toSet(),
      swimStatus: 'live',
      validLapCount: laps.length,
      wentLive: true,
    );
  }

  @override
  Future<SwimStateSnapshot> fetchState(int swimId) async =>
      const SwimStateSnapshot(status: 'live', lapCount: 0, lastSeq: 0, recentLapsMs: []);

  @override
  Future<void> ping(int swimId) async {}

  @override
  Future<void> complete(int swimId) async {}
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late FakeLapBuffer buffer;
  late FakeTimingRepository repo;

  TimingController make() =>
      TimingController(swimId: 1, lapTarget: 20, repository: repo, buffer: buffer);

  setUp(() {
    buffer = FakeLapBuffer();
    repo = FakeTimingRepository();
  });

  test('a tap opens a pending capture without incrementing the counter', () {
    final c = make();
    expect(c.hasPending, isFalse);
    c.onTap(1000);
    expect(c.hasPending, isTrue);
    expect(c.lapCount, 0); // counter increments only on confirm (§6.5)
    expect(c.pendingLapNumber, 1);
    c.rejectPending(); // cancel the pending auto-confirm timer
  });

  test('confirming keeps the capture with its original timestamp', () async {
    final c = make();
    c.onTap(1000);
    c.confirmPending();
    expect(c.hasPending, isFalse);
    expect(c.lapCount, 1);
    await pumpEventQueue();
    expect(buffer.addedLog.map((l) => l.seq), [1]);
    expect(buffer.addedLog.single.deviceMonoMs, 1000);
  });

  test('No drops the capture and does not consume the lap number', () async {
    final c = make();
    c.onTap(1000);
    c.rejectPending();
    expect(c.lapCount, 0);
    // The next confirmed lap must still be seq 1 — the rejected tap consumed nothing.
    c.onTap(2000);
    c.confirmPending();
    await pumpEventQueue();
    expect(buffer.addedLog.map((l) => l.seq), [1]);
    expect(buffer.addedLog.single.deviceMonoMs, 2000);
  });

  test('tapping LAP with a confirmation open confirms the pending one and starts a new capture', () async {
    final c = make();
    c.onTap(1000); // pending #1
    c.onTap(41000); // 40s later: confirms #1 (tap-through), opens #2
    expect(c.lapCount, 1);
    expect(c.hasPending, isTrue);
    expect(c.pendingLapNumber, 2);
    c.confirmPending(); // confirm #2
    expect(c.lapCount, 2);
    expect(c.recentLaps.first, 40000); // two taps 40s apart -> a ~40s lap
    await pumpEventQueue();
    expect(buffer.addedLog.map((l) => l.seq), [1, 2]);
    expect(buffer.addedLog.map((l) => l.deviceMonoMs), [1000, 41000]);
  });

  test('a press within 250ms of the previous capture raises no confirmation', () {
    final c = make();
    c.onTap(1000);
    c.confirmPending(); // committed at mono 1000
    c.onTap(1100); // 100ms later — a bounce
    expect(c.hasPending, isFalse);
    expect(c.lapCount, 1);
  });

  test('captures past the lap target are ordinary — no cap', () async {
    final c = make(); // target is 20
    var mono = 0.0;
    for (var i = 0; i < 25; i++) {
      mono += 41000;
      c.onTap(mono);
      c.confirmPending();
    }
    expect(c.lapCount, 25);
    await pumpEventQueue();
    expect(buffer.addedLog.length, 25);
  });

  test('a closed swim ignores taps', () async {
    // Simulate the server closing the swim mid-flush by returning swim_status
    // closed; then further taps do nothing.
    final closingRepo = _ClosingRepo();
    final c = TimingController(swimId: 1, lapTarget: null, repository: closingRepo, buffer: buffer);
    c.onTap(1000);
    c.confirmPending();
    await pumpEventQueue(); // flush sees swim_status == closed
    expect(c.swimClosed, isTrue);
    final before = c.lapCount;
    c.onTap(90000);
    expect(c.hasPending, isFalse);
    expect(c.lapCount, before);
  });
}

class _ClosingRepo implements TimingRepository {
  @override
  Future<SubmitResult> submit({required int swimId, required List<PendingLap> laps}) async =>
      SubmitResult(confirmedSeqs: laps.map((l) => l.seq).toSet(), swimStatus: 'closed', validLapCount: 0, wentLive: false);
  @override
  Future<SwimStateSnapshot> fetchState(int swimId) async =>
      const SwimStateSnapshot(status: 'live', lapCount: 0, lastSeq: 0, recentLapsMs: []);
  @override
  Future<void> ping(int swimId) async {}
  @override
  Future<void> complete(int swimId) async {}
}
