/// A practice swim assigned to this timer, as returned by `GET /my-swims`.
class Swim {
  const Swim({
    required this.id,
    required this.swimmerName,
    required this.venueName,
    required this.laneNo,
    required this.scheduledStart,
    required this.status,
    required this.lapTarget,
    required this.assignedTimerId,
  });

  final int id;
  final String swimmerName;
  final String venueName;
  final int laneNo;
  final DateTime scheduledStart;
  final String status;
  final int? lapTarget;
  final int? assignedTimerId;

  bool get isLive => status == 'live';
  bool get isScheduled => status == 'scheduled';

  factory Swim.fromJson(Map<String, dynamic> j) => Swim(
        id: j['id'] as int,
        swimmerName: (j['swimmer_name'] as String?) ?? 'Swimmer',
        venueName: (j['venue_name'] as String?) ?? '',
        laneNo: j['lane_no'] as int,
        scheduledStart: DateTime.parse(j['scheduled_start'] as String).toLocal(),
        status: j['status'] as String,
        lapTarget: j['lap_target'] as int?,
        assignedTimerId: j['assigned_timer_id'] as int?,
      );
}
