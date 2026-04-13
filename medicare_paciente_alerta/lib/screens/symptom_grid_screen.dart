import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../l10n/app_strings.dart';
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
        title: const Text(AppStrings.queSentis),
        leading: const BackButton(),
      ),
      body: CustomScrollView(
        slivers: [
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
              child: Text(
                AppStrings.sintomasGuia,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: Colors.white60),
              ),
            ),
          ),
          for (final nivel in TriageNivel.values) ...[
            if (nivel != TriageNivel.rojo)
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(24, 12, 24, 4),
                  child: Divider(
                    height: 1,
                    color: Theme.of(context).colorScheme.outline.withOpacity(0.35),
                  ),
                ),
              ),
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 20, 16, 8),
                child: Semantics(
                  header: true,
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
                    final items = kSintomasPorNivel[nivel]!;
                    if (i >= items.length) return null;
                    return _SintomaCard(sintoma: items[i]);
                  },
                  childCount: kSintomasPorNivel[nivel]!.length,
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
    final surface = Theme.of(context).colorScheme.surfaceContainerHighest;
    return Material(
      color: surface,
      borderRadius: BorderRadius.circular(16),
      child: Semantics(
        button: true,
        label: sintoma.label,
        hint: AppStrings.sintomaSemanticsHint(sintoma.nivel.apiLabel),
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
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.w700,
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
