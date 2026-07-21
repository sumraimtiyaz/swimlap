import '../../../core/network/api_client.dart';
import '../domain/swim.dart';

class SwimsRepository {
  SwimsRepository(this._api);

  final ApiClient _api;

  /// Assigned scheduled/live swims. The server already filters out closed swims
  /// (PRD §6.2), so the app never sees a past swim.
  Future<List<Swim>> mySwims() async {
    final res = await _api.get('/my-swims') as List;
    return res.cast<Map<String, dynamic>>().map(Swim.fromJson).toList();
  }
}
