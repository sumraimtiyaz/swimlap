/// Dart mirror of `shared/contracts/contract.json`.
///
/// These constants MUST match the JSON contract (and the backend's
/// `domain/enums.py` + `domain/tuning.py`). In a production setup a codegen step
/// would emit this file from the JSON; for the MVP it is hand-kept and the
/// values are small and stable. See docs/ARCHITECTURE.md.
class UserRole {
  static const coordinator = 'coordinator';
  static const timer = 'timer';
}

class SwimStatus {
  static const scheduled = 'scheduled';
  static const live = 'live';
  static const closed = 'closed';
}

class LapSource {
  static const manual = 'manual';
  static const simulated = 'simulated';
}

/// Timing thresholds shared with the backend + mirrored UX constants.
class Timing {
  /// A press within this window of the previous capture raises no confirmation.
  static const int minInterLapMs = 250;

  /// A confirmation left untouched this long confirms itself (PRD §6.5).
  static const int confirmAutoAcceptMs = 10000;

  /// PRACTICE COMPLETED requires a hold of at least this long (PRD §6.6).
  static const int completionLongPressMs = 800;
}
