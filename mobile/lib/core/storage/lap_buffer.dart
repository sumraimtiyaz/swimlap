import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import 'pending_lap.dart';

/// Durable, per-swim buffer of laps not yet acknowledged by the server.
///
/// Backed by shared_preferences so taps survive connectivity loss *and* an app
/// restart — the core promise of an offline-first timing tool. Small volume
/// (a swim is dozens of laps), so JSON is fine.
class LapBuffer {
  static String _key(int swimId) => 'swimlap.buffer.swim.$swimId';

  Future<List<PendingLap>> load(int swimId) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_key(swimId));
    if (raw == null) return [];
    final list = (jsonDecode(raw) as List).cast<Map<String, dynamic>>();
    return list.map(PendingLap.fromJson).toList();
  }

  Future<void> add(int swimId, PendingLap lap) async {
    final laps = await load(swimId)..add(lap);
    await _save(swimId, laps);
  }

  /// Remove laps whose seq the server has confirmed (accepted, duplicate, or invalid).
  Future<void> ackSeqs(int swimId, Set<int> confirmed) async {
    final laps = await load(swimId);
    laps.removeWhere((l) => confirmed.contains(l.seq));
    await _save(swimId, laps);
  }

  Future<void> _save(int swimId, List<PendingLap> laps) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_key(swimId), jsonEncode(laps.map((l) => l.toJson()).toList()));
  }
}
