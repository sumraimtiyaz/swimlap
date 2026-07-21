/// A lap captured on-device, awaiting confirmed upload.
///
/// The monotonic timestamp is captured at tap time and never changes, so even a
/// lap that sits in the buffer for minutes (offline) uploads with its true
/// capture time. [wasBuffered] records that the lap was captured while offline,
/// so the server times it from the monotonic delta rather than its (delayed)
/// arrival — PRD §2.
class PendingLap {
  const PendingLap({
    required this.seq,
    required this.deviceMonoMs,
    required this.wasBuffered,
    this.deviceTsIso,
    this.source = 'manual',
  });

  final int seq;
  final double deviceMonoMs;
  final bool wasBuffered;
  final String? deviceTsIso; // wall-clock at capture, best-effort (may be null)
  final String source;

  Map<String, dynamic> toJson() => {
        'seq': seq,
        'device_mono_ms': deviceMonoMs,
        'was_buffered': wasBuffered,
        if (deviceTsIso != null) 'device_ts': deviceTsIso,
        'source': source,
      };

  factory PendingLap.fromJson(Map<String, dynamic> j) => PendingLap(
        seq: j['seq'] as int,
        deviceMonoMs: (j['device_mono_ms'] as num).toDouble(),
        wasBuffered: j['was_buffered'] as bool? ?? false,
        deviceTsIso: j['device_ts'] as String?,
        source: j['source'] as String? ?? 'manual',
      );
}
