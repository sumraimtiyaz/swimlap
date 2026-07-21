import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:wakelock_plus/wakelock_plus.dart';

import '../../../core/contract.dart';
import '../../../core/network/api_exception.dart';
import '../../../core/storage/lap_buffer.dart';
import '../../../core/storage/pending_lap.dart';
import '../data/timing_repository.dart';

enum SyncState { syncing, synced, offline, error }

/// One capture awaiting confirmation. It is NOT yet in the durable buffer, so if
/// the app is killed with a confirmation open this capture is lost — the only
/// case where a tap does not survive, and why the 10s auto-confirm exists (§6.7).
class _Pending {
  _Pending({required this.monoMs, required this.deviceTsIso, required this.wasBuffered});
  final double monoMs;
  final String deviceTsIso;
  final bool wasBuffered;
}

/// Drives the timing screen. Offline-first: a confirmed tap is buffered durably,
/// then uploaded. Implements the PRD §6.4–§6.7 capture + confirmation rules.
class TimingController extends ChangeNotifier {
  TimingController({
    required this.swimId,
    required this.lapTarget,
    required TimingRepository repository,
    required LapBuffer buffer,
  })  : _repo = repository,
        _buffer = buffer;

  final int swimId;
  final int? lapTarget;
  final TimingRepository _repo;
  final LapBuffer _buffer;

  int _nextSeq = 1;
  int _lapCount = 0;
  double? _firstCommittedMono;
  double? _lastCommittedMono;
  List<double> _recentLaps = []; // most recent first, capped at 3
  _Pending? _pending;
  Timer? _autoConfirm;

  bool _online = true;
  bool _swimClosed = false;
  bool _pendingComplete = false;
  SyncState _sync = SyncState.syncing;
  int _uploadBacklog = 0;

  StreamSubscription? _connSub;
  Timer? _liveness;

  // ---- exposed state ----
  int get lapCount => _lapCount;
  List<double> get recentLaps => List<double>.unmodifiable(_recentLaps);
  bool get hasPending => _pending != null;
  int get pendingLapNumber => _lapCount + 1;
  bool get swimClosed => _swimClosed;
  bool get online => _online;
  SyncState get syncState => _sync;
  int get uploadBacklog => _uploadBacklog;

  /// Elapsed time across this session's confirmed captures (for the completion
  /// confirmation). Null until at least two captures exist.
  double? get elapsedMs =>
      (_firstCommittedMono != null && _lastCommittedMono != null && _lastCommittedMono! > _firstCommittedMono!)
          ? _lastCommittedMono! - _firstCommittedMono!
          : null;

  static String _completeKey(int swimId) => 'swimlap.pendingComplete.$swimId';

  Future<void> init() async {
    await WakelockPlus.enable();

    final prefs = await SharedPreferences.getInstance();
    _pendingComplete = prefs.getBool(_completeKey(swimId)) ?? false;

    // Resume counter + recent laps from the server (PRD §6.8).
    try {
      final st = await _repo.fetchState(swimId);
      _nextSeq = st.lastSeq + 1;
      _lapCount = st.lapCount;
      _recentLaps = List<double>.from(st.recentLapsMs);
      if (st.status == 'closed') _swimClosed = true;
    } on ApiException {
      // Offline at open — carry on with whatever is buffered locally.
    }

    final buffered = await _buffer.load(swimId);
    _uploadBacklog = buffered.length;
    for (final l in buffered) {
      if (l.seq >= _nextSeq) _nextSeq = l.seq + 1;
    }

    _connSub = Connectivity().onConnectivityChanged.listen((results) {
      _online = !results.contains(ConnectivityResult.none);
      if (_online) {
        unawaited(_flush());
      } else {
        _sync = SyncState.offline;
        notifyListeners();
      }
    });
    _liveness = Timer.periodic(const Duration(seconds: 10), (_) => unawaited(_ping()));

    notifyListeners();
    await _flush();
  }

  /// Called on every LAP press. The monotonic timestamp is read by the view at
  /// touch time and passed in unchanged (PRD §6.4).
  void onTap(double monoMs) {
    if (_swimClosed) return;

    // Tapping LAP while a confirmation is open confirms the pending one (§6.5).
    if (_pending != null) {
      _commit();
    }
    // A press within 250ms of the previous capture is a bounce — no confirmation.
    if (_lastCommittedMono != null && (monoMs - _lastCommittedMono!) < Timing.minInterLapMs) {
      return;
    }
    _pending = _Pending(
      monoMs: monoMs,
      deviceTsIso: DateTime.now().toUtc().toIso8601String(),
      wasBuffered: !_online,
    );
    _autoConfirm?.cancel();
    _autoConfirm = Timer(const Duration(milliseconds: Timing.confirmAutoAcceptMs), _commit);
    notifyListeners();
  }

  /// Yes — keep the pending capture with its original timestamp.
  void confirmPending() => _commit();

  /// No — drop the pending capture entirely. Nothing sent, counter unchanged, and
  /// the lap number is NOT consumed (seq is only assigned on commit) (§6.5).
  void rejectPending() {
    _autoConfirm?.cancel();
    _autoConfirm = null;
    _pending = null;
    notifyListeners();
  }

  void _commit() {
    final p = _pending;
    if (p == null) return;
    _autoConfirm?.cancel();
    _autoConfirm = null;
    _pending = null;

    final seq = _nextSeq++;
    if (_lastCommittedMono != null) {
      _recentLaps.insert(0, p.monoMs - _lastCommittedMono!);
      if (_recentLaps.length > 3) _recentLaps = _recentLaps.sublist(0, 3);
    }
    _firstCommittedMono ??= p.monoMs;
    _lastCommittedMono = p.monoMs;
    _lapCount++;
    notifyListeners(); // optimistic UI update

    final lap = PendingLap(
      seq: seq, deviceMonoMs: p.monoMs, wasBuffered: p.wasBuffered, deviceTsIso: p.deviceTsIso);
    unawaited(_persistAndFlush(lap));
  }

  Future<void> _persistAndFlush(PendingLap lap) async {
    await _buffer.add(swimId, lap);
    _uploadBacklog += 1;
    notifyListeners();
    await _flush();
  }

  Future<void> _flush() async {
    if (!_online) {
      _sync = SyncState.offline;
      notifyListeners();
      return;
    }
    final pending = await _buffer.load(swimId);
    if (pending.isNotEmpty) {
      _sync = SyncState.syncing;
      notifyListeners();
      try {
        final res = await _repo.submit(swimId: swimId, laps: pending);
        await _buffer.ackSeqs(swimId, res.confirmedSeqs);
        _uploadBacklog = (await _buffer.load(swimId)).length;
        if (res.swimStatus == 'closed') _swimClosed = true;
        _sync = _uploadBacklog == 0 ? SyncState.synced : SyncState.error;
      } on ApiException catch (e) {
        _sync = e.code == 'NETWORK_ERROR' ? SyncState.offline : SyncState.error;
        notifyListeners();
        return;
      }
    } else {
      _sync = SyncState.synced;
      _uploadBacklog = 0;
    }
    // Queued captures are sent before the completion request (§6.6): only fire a
    // pending completion once the buffer is empty.
    if (_pendingComplete && _uploadBacklog == 0 && !_swimClosed) {
      try {
        await _repo.complete(swimId);
        _swimClosed = true;
        await _clearPendingComplete();
      } on ApiException {
        // Stays queued; retried on the next flush/reconnect.
      }
    }
    notifyListeners();
  }

  /// PRACTICE COMPLETED. Confirms any pending capture, then queues completion so
  /// it is sent after every buffered lap. If offline it stays queued and the swim
  /// closes when the server receives it (§6.6).
  Future<void> complete() async {
    if (_pending != null) _commit();
    _pendingComplete = true;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_completeKey(swimId), true);
    await _flush();
  }

  Future<void> _clearPendingComplete() async {
    _pendingComplete = false;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_completeKey(swimId));
  }

  Future<void> _ping() async {
    if (_online && !_swimClosed) {
      try {
        await _repo.ping(swimId);
      } catch (_) {
        // presence is best-effort; a missed ping just shows offline briefly.
      }
    }
  }

  @override
  void dispose() {
    _autoConfirm?.cancel();
    _connSub?.cancel();
    _liveness?.cancel();
    WakelockPlus.disable();
    super.dispose();
  }
}
