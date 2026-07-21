import 'package:flutter/material.dart';

import '../../../core/di/service_locator.dart';
import '../../../core/network/api_exception.dart';
import '../../auth/domain/app_user.dart';
import '../../timing/presentation/timing_screen.dart';
import '../domain/swim.dart';

/// The heat/swim list. Shows only assigned scheduled or live swims (the server
/// enforces this filter). Each row shows swimmer name, lane, scheduled start,
/// and the lap target if set.
class SwimsScreen extends StatefulWidget {
  const SwimsScreen({super.key, required this.user});

  final AppUser user;

  @override
  State<SwimsScreen> createState() => _SwimsScreenState();
}

class _SwimsScreenState extends State<SwimsScreen> {
  late Future<List<Swim>> _future;

  @override
  void initState() {
    super.initState();
    _future = Services.I.swimsRepository.mySwims();
  }

  void _refresh() => setState(() => _future = Services.I.swimsRepository.mySwims());

  void _open(Swim swim) {
    Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => TimingScreen(swim: swim),
    )).then((_) => _refresh());
  }

  String _when(DateTime dt) {
    String two(int n) => n.toString().padLeft(2, '0');
    return '${two(dt.hour)}:${two(dt.minute)}';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('My Swims'),
        actions: [IconButton(onPressed: _refresh, icon: const Icon(Icons.refresh))],
      ),
      body: FutureBuilder<List<Swim>>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError) {
            final msg = snap.error is ApiException ? (snap.error as ApiException).message : 'Failed to load swims';
            return _Message(text: msg, onRetry: _refresh);
          }
          final swims = snap.data ?? [];
          if (swims.isEmpty) {
            return const _Message(text: 'No swims assigned to you yet.');
          }
          return RefreshIndicator(
            onRefresh: () async => _refresh(),
            child: ListView.separated(
              itemCount: swims.length,
              separatorBuilder: (_, __) => const Divider(height: 1),
              itemBuilder: (context, i) {
                final s = swims[i];
                final target = s.lapTarget != null ? ' · ${s.lapTarget} laps' : '';
                return ListTile(
                  title: Text(s.swimmerName, style: const TextStyle(fontWeight: FontWeight.w600)),
                  subtitle: Text('Lane ${s.laneNo} · ${_when(s.scheduledStart)}$target'),
                  trailing: s.isLive
                      ? const Icon(Icons.play_circle_fill, color: Color(0xFF0072CE))
                      : Chip(label: Text(s.status)),
                  onTap: () => _open(s),
                );
              },
            ),
          );
        },
      ),
    );
  }
}

class _Message extends StatelessWidget {
  const _Message({required this.text, this.onRetry});
  final String text;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(text, style: const TextStyle(color: Colors.blueGrey)),
          if (onRetry != null) ...[
            const SizedBox(height: 12),
            OutlinedButton(onPressed: onRetry, child: const Text('Retry')),
          ],
        ],
      ),
    );
  }
}
