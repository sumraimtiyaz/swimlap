import 'package:flutter/material.dart';

import '../../features/timing/presentation/timing_controller.dart';

/// Compact, glanceable sync indicator. A timer must be able to trust that their
/// taps are safe even on flaky venue wifi.
class SyncStatusChip extends StatelessWidget {
  const SyncStatusChip({super.key, required this.state, required this.backlog});

  final SyncState state;
  final int backlog;

  @override
  Widget build(BuildContext context) {
    final (color, label, icon) = switch (state) {
      SyncState.synced => (Colors.green, 'Synced', Icons.cloud_done_outlined),
      SyncState.syncing => (Colors.blue, 'Syncing…', Icons.cloud_sync_outlined),
      SyncState.offline => (Colors.orange, 'Offline · buffered', Icons.cloud_off_outlined),
      SyncState.error => (Colors.red, 'Retrying', Icons.error_outline),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withValues(alpha: 0.4)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: color),
          const SizedBox(width: 6),
          Text(label, style: TextStyle(color: color, fontWeight: FontWeight.w600, fontSize: 13)),
          if (backlog > 0) ...[
            const SizedBox(width: 6),
            Text('($backlog)', style: TextStyle(color: color, fontSize: 13)),
          ],
        ],
      ),
    );
  }
}
