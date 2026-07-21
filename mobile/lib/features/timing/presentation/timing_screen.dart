import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../core/contract.dart';
import '../../../core/di/service_locator.dart';
import '../../../shared/widgets/sync_status_chip.dart';
import '../../swims/domain/swim.dart';
import 'timing_controller.dart';

/// The stopwatch surface. One enormous tap target so a timer never misses.
///
/// **Why pointer-down, not onTap:** a stopwatch must record at the instant the
/// finger lands. `GestureDetector.onTap` waits to disambiguate the gesture,
/// adding tens of milliseconds. We use a raw [Listener] and read the monotonic
/// timestamp in `onPointerDown`, before anything else (PRD §6.4).
class TimingScreen extends StatefulWidget {
  const TimingScreen({super.key, required this.swim});

  final Swim swim;

  @override
  State<TimingScreen> createState() => _TimingScreenState();
}

class _TimingScreenState extends State<TimingScreen> {
  late final TimingController _c;
  bool _flash = false;

  @override
  void initState() {
    super.initState();
    _c = Services.I.timingControllerFor(swimId: widget.swim.id, lapTarget: widget.swim.lapTarget);
    _c.init();
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  void _onPointerDown(PointerDownEvent _) {
    if (_c.swimClosed) return;
    // 1) read the timestamp FIRST, 2) tactile confirmation, 3) record.
    final mono = Services.I.clock.nowMs();
    HapticFeedback.heavyImpact();
    _c.onTap(mono);
    setState(() => _flash = true);
    Future.delayed(const Duration(milliseconds: 90), () {
      if (mounted) setState(() => _flash = false);
    });
  }

  Future<void> _endPractice() async {
    final ok = await showDialog<bool>(
      context: context,
      barrierDismissible: false, // never auto-confirms (PRD §6.6)
      builder: (ctx) => AlertDialog(
        title: const Text('End practice?'),
        content: Text(
          '${_c.lapCount} laps recorded'
          '${_c.elapsedMs != null ? ' · ${_fmt(_c.elapsedMs)} elapsed' : ''}.\n\n'
          'This closes the swim. It cannot be reopened.',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Keep timing')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('End practice')),
        ],
      ),
    );
    if (ok == true) {
      await _c.complete();
    }
  }

  String _fmt(double? ms) {
    if (ms == null) return '—';
    final total = ms.round();
    final m = total ~/ 60000;
    final s = (total % 60000) / 1000.0;
    return '${m > 0 ? '$m:' : ''}${s.toStringAsFixed(2)}s';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('${widget.swim.swimmerName} · Lane ${widget.swim.laneNo}'),
        actions: [
          Center(
            child: ListenableBuilder(
              listenable: _c,
              builder: (_, __) => Padding(
                padding: const EdgeInsets.symmetric(horizontal: 8),
                child: SyncStatusChip(state: _c.syncState, backlog: _c.uploadBacklog),
              ),
            ),
          ),
          // PRACTICE COMPLETED — in the corner, distinct, long-press only (§6.6).
          ListenableBuilder(
            listenable: _c,
            builder: (_, __) => _c.swimClosed
                ? const SizedBox.shrink()
                : _HoldToEndButton(onCompleted: _endPractice),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: ListenableBuilder(
        listenable: _c,
        builder: (context, _) {
          if (_c.swimClosed) return const _ClosedView();
          return Column(
            children: [
              Expanded(
                child: Listener(
                  behavior: HitTestBehavior.opaque,
                  onPointerDown: _onPointerDown,
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 90),
                    color: _flash
                        ? Theme.of(context).colorScheme.primary.withValues(alpha: 0.18)
                        : Theme.of(context).colorScheme.surface,
                    width: double.infinity,
                    child: _CounterView(controller: _c, fmt: _fmt),
                  ),
                ),
              ),
              if (_c.hasPending) _ConfirmationBar(controller: _c),
            ],
          );
        },
      ),
    );
  }
}

class _CounterView extends StatelessWidget {
  const _CounterView({required this.controller, required this.fmt});
  final TimingController controller;
  final String Function(double?) fmt;

  @override
  Widget build(BuildContext context) {
    final c = controller;
    final target = c.lapTarget;
    final recent = c.recentLaps;
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.baseline,
          textBaseline: TextBaseline.alphabetic,
          children: [
            Text('${c.lapCount}',
                style: const TextStyle(fontSize: 120, fontWeight: FontWeight.bold, height: 1.0)),
            if (target != null)
              Padding(
                padding: const EdgeInsets.only(left: 8),
                child: Text('/ $target target', style: const TextStyle(fontSize: 22, color: Colors.blueGrey)),
              ),
          ],
        ),
        const Text('LAPS', style: TextStyle(letterSpacing: 4, color: Colors.blueGrey)),
        const SizedBox(height: 28),
        // Last three lap times, most recent first — static, not scrollable (§6.3).
        Column(
          children: [
            const Text('Last three laps', style: TextStyle(color: Colors.blueGrey, fontSize: 13)),
            const SizedBox(height: 6),
            if (recent.isEmpty)
              const Text('—', style: TextStyle(fontSize: 20, color: Colors.blueGrey))
            else
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  for (final ms in recent)
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 10),
                      child: Text(fmt(ms), style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w600)),
                    ),
                ],
              ),
          ],
        ),
        const SizedBox(height: 44),
        const Text('Tap anywhere to record a lap', style: TextStyle(color: Colors.blueGrey)),
      ],
    );
  }
}

class _ConfirmationBar extends StatelessWidget {
  const _ConfirmationBar({required this.controller});
  final TimingController controller;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Theme.of(context).colorScheme.primaryContainer,
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Row(
            children: [
              Expanded(
                child: Text('Record lap ${controller.pendingLapNumber}?',
                    style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w600)),
              ),
              OutlinedButton(
                onPressed: controller.rejectPending,
                child: const Padding(padding: EdgeInsets.symmetric(vertical: 6, horizontal: 8), child: Text('No')),
              ),
              const SizedBox(width: 12),
              FilledButton(
                onPressed: controller.confirmPending,
                child: const Padding(padding: EdgeInsets.symmetric(vertical: 6, horizontal: 16), child: Text('Yes')),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Press-and-hold control (>= 800ms) with a filling progress ring. A tap does
/// nothing; releasing early resets. Kept small and distinct, in the app-bar
/// corner, away from the LAP path (PRD §6.6).
class _HoldToEndButton extends StatefulWidget {
  const _HoldToEndButton({required this.onCompleted});
  final Future<void> Function() onCompleted;

  @override
  State<_HoldToEndButton> createState() => _HoldToEndButtonState();
}

class _HoldToEndButtonState extends State<_HoldToEndButton> with SingleTickerProviderStateMixin {
  late final AnimationController _anim = AnimationController(
    vsync: this, duration: const Duration(milliseconds: Timing.completionLongPressMs))
    ..addStatusListener((status) {
      if (status == AnimationStatus.completed) {
        _anim.reset();
        widget.onCompleted();
      }
    });

  @override
  void dispose() {
    _anim.dispose();
    super.dispose();
  }

  void _down(_) => _anim.forward(from: 0);
  void _cancel([_]) {
    if (_anim.status != AnimationStatus.completed) {
      _anim.stop();
      _anim.reset();
    }
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTapDown: _down,
      onTapUp: _cancel,
      onTapCancel: _cancel,
      child: Tooltip(
        message: 'Hold to end practice',
        child: SizedBox(
          width: 44,
          height: 44,
          child: AnimatedBuilder(
            animation: _anim,
            builder: (_, __) => Stack(
              alignment: Alignment.center,
              children: [
                SizedBox(
                  width: 34, height: 34,
                  child: CircularProgressIndicator(
                    value: _anim.value == 0 ? null : _anim.value,
                    strokeWidth: 3,
                    backgroundColor: Colors.white24,
                    valueColor: const AlwaysStoppedAnimation(Colors.redAccent),
                  ),
                ),
                const Icon(Icons.flag, size: 18, color: Colors.redAccent),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _ClosedView extends StatelessWidget {
  const _ClosedView();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.flag_outlined, size: 72, color: Colors.blueGrey),
          SizedBox(height: 12),
          Text('Swim closed', style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold)),
          SizedBox(height: 8),
          Text('All recorded laps are synced.', style: TextStyle(color: Colors.blueGrey)),
        ],
      ),
    );
  }
}
