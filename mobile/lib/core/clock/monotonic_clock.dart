/// Device monotonic clock.
///
/// Wraps a single process-wide [Stopwatch]. `nowMs()` is the value we send as
/// `device_mono_ms`: milliseconds since the app process started, guaranteed
/// non-decreasing and immune to wall-clock/NTP changes. Perfect for ordering and
/// measuring lap intervals. The server stamps `server_ts` on arrival for live
/// laps; for buffered (offline) laps it times them from the `device_mono_ms`
/// delta, so a whole queue uploaded at once still computes correct lap times.
class MonotonicClock {
  MonotonicClock() {
    _sw.start();
  }

  final Stopwatch _sw = Stopwatch();

  /// Milliseconds since app start, as a double (sub-ms precision via microseconds).
  double nowMs() => _sw.elapsedMicroseconds / 1000.0;
}
