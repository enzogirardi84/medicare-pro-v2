import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../models/triage_symptom.dart';
import '../services/network_connectivity_service.dart';
import 'countdown_send_screen.dart';

/// Pantalla 2: cuadricula visual por triage (sin teclado).
class SymptomGridScreen extends StatelessWidget {
  const SymptomGridScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Que sentis?'),
        leading: const BackButton(),
      ),
      body: CustomScrollView(
        slivers: [
          for (final nivel in TriageNivel.values) ...[
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 20, 16, 8),
                child: Row(
                  children: [
                    Container(
                      width: 6,
                      height: 22,
                      decoration: BoxDecoration(
                        color: nivel.color,
                        borderRadius: BorderRadius.circular(3),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Text(
                      nivel.tituloSeccion,
                      style: TextStyle(
                        color: nivel.color,
                        fontWeight: FontWeight.w800,
                        fontSize: 13,
                        letterSpacing: 0.8,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            SliverPadding(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              sliver: SliverGrid(
                gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: 2,
                  mainAxisSpacing: 12,
                  crossAxisSpacing: 12,
                  childAspectRatio: 0.95,
                ),
                delegate: SliverChildBuilderDelegate(
                  (ctx, i) {
                    final items = kSintomasTriage.where((s) => s.nivel == nivel).toList();
                    if (i >= items.length) return null;
                    final s = items[i];
                    return _SintomaCard(sintoma: s);
                  },
                  childCount: kSintomasTriage.where((s) => s.nivel == nivel).length,
                ),
              ),
            ),
          ],
          const SliverToBoxAdapter(child: SizedBox(height: 24)),
        ],
      ),
    );
  }
}

class _SintomaCard extends StatelessWidget {
  const _SintomaCard({required this.sintoma});

  final TriageSintoma sintoma;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: const Color(0xFF1E293B),
      borderRadius: BorderRadius.circular(16),
      child: Semantics(
        button: true,
        label: sintoma.label,
        hint: 'Triage ${sintoma.nivel.apiLabel}. Toca para confirmar envio',
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: () async {
            HapticFeedback.selectionClick();
            final ok = await NetworkConnectivityService.ensureBeforeAlert(context);
            if (!context.mounted) return;
            if (!ok) return;
            await Navigator.push<void>(
              context,
              MaterialPageRoute<void>(
                builder: (_) => CountdownSendScreen(sintoma: sintoma),
              ),
            );
          },
          child: Container(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: sintoma.nivel.color.withOpacity(0.55), width: 2),
            ),
            padding: const EdgeInsets.all(12),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(sintoma.icon, size: 44, color: sintoma.nivel.color),
                const SizedBox(height: 10),
                Text(
                  sintoma.label,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 14,
                    height: 1.2,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
