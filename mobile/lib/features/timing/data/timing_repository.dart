import '../../../core/network/api_client.dart';
import '../../../core/storage/pending_lap.dart';

class SubmitResult {
  const SubmitResult({
    required this.confirmedSeqs,
    required this.swimStatus,
    required this.validLapCount,
    required this.wentLive,
  });
  final Set<int> confirmedSeqs;
  final String swimStatus;
  final int validLapCount;
  final bool wentLive;
}

class SwimStateSnapshot {
  const SwimStateSnapshot({
    required this.status,
    required this.lapCount,
    required this.lastSeq,
    required this.recentLapsMs,
  });
  final String status;
  final int lapCount;
  final int lastSeq;
  final List<double> recentLapsMs;

  factory SwimStateSnapshot.fromJson(Map<String, dynamic> j) => SwimStateSnapshot(
        status: j['status'] as String,
        lapCount: j['lap_count'] as int,
        lastSeq: j['last_seq'] as int,
        recentLapsMs: ((j['recent_laps_ms'] as List?) ?? []).map((e) => (e as num).toDouble()).toList(),
      );
}

/// Speaks HTTP for the timing screen. Stateless — the controller owns sequencing,
/// buffering, and confirmation; this class just serialises requests.
class TimingRepository {
  TimingRepository(this._api);

  final ApiClient _api;

  Future<SubmitResult> submit({required int swimId, required List<PendingLap> laps}) async {
    final res = await _api.post('/swims/$swimId/laps', body: {
      'laps': laps.map((l) => l.toJson()).toList(),
    });
    final outcomes = (res['outcomes'] as List).cast<Map<String, dynamic>>();
    // A lap is "confirmed" (safe to drop from the buffer) if the server accepted
    // it, already had it, or rejected it as invalid — all mean it is durably dealt with.
    final confirmed = <int>{
      for (final o in outcomes)
        if (o['status'] == 'accepted' || o['status'] == 'duplicate' || o['status'] == 'invalid')
          o['seq'] as int,
    };
    return SubmitResult(
      confirmedSeqs: confirmed,
      swimStatus: res['swim_status'] as String? ?? 'live',
      validLapCount: res['valid_lap_count'] as int? ?? 0,
      wentLive: res['went_live'] as bool? ?? false,
    );
  }

  Future<SwimStateSnapshot> fetchState(int swimId) async {
    final res = await _api.get('/swims/$swimId/state') as Map;
    return SwimStateSnapshot.fromJson(res.cast<String, dynamic>());
  }

  Future<void> ping(int swimId) => _api.post('/swims/$swimId/liveness');

  Future<void> complete(int swimId) => _api.post('/swims/$swimId/complete');
}
