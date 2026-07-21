import '../clock/monotonic_clock.dart';
import '../network/api_client.dart';
import '../storage/lap_buffer.dart';
import '../../features/auth/data/auth_repository.dart';
import '../../features/swims/data/swims_repository.dart';
import '../../features/timing/data/timing_repository.dart';
import '../../features/timing/presentation/timing_controller.dart';

/// Tiny manual service locator (no external DI package needed for an app this
/// size). Everything is constructed once and shared; controllers are created
/// per screen via factory methods.
class Services {
  Services._();
  static final Services I = Services._();

  // Base URL: overridable at build time with --dart-define=SWIMLAP_API=...
  // 10.0.2.2 is the Android emulator's alias for the host machine (debug only;
  // release builds require https — see ApiClient).
  static const _baseUrl =
      String.fromEnvironment('SWIMLAP_API', defaultValue: 'http://10.0.2.2:8000');

  late final ApiClient api = ApiClient(baseUrl: _baseUrl);
  late final MonotonicClock clock = MonotonicClock();
  late final LapBuffer lapBuffer = LapBuffer();

  late final AuthRepository authRepository = AuthRepository(api);
  late final SwimsRepository swimsRepository = SwimsRepository(api);
  late final TimingRepository timingRepository = TimingRepository(api);

  TimingController timingControllerFor({required int swimId, int? lapTarget}) {
    return TimingController(
      swimId: swimId,
      lapTarget: lapTarget,
      repository: timingRepository,
      buffer: lapBuffer,
    );
  }
}
