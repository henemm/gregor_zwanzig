# Context: fix-3462-testalarm-beispielwerte (Issue #3462)

## Request Summary
Der Test-Alarm (#3441) baut Beispielwerte, die sich widersprechen: Rückfall-Beispiel Böen
(Schwelle 50, alt 40 → neu 60) zeigt „↑ Änderung unter deiner Alarm-Schwelle (50 km/h) ✓“,
und gleichlautende Wettergrößen erscheinen doppelt („Temp 6 °C, Temp 6 °C“, „Niedersch“ mehrfach).
Ziel: Beispiel liest sich wie ein echter Alarm — Schwelle sichtbar überschritten, jede Größe einmal.

## Ursachen (belegt)
1. **Schwellen-Semantik.** `threshold` ist laut ADR-0013 (teilweise abgelöst durch ADR-0106,
   `threshold` bleibt Sprung-Schwelle) IMMER die Δ-Schwelle. Der Renderer urteilt
   `over_thr(e) = abs(value_to - value_from) >= threshold` (`src/output/renderers/alert/model.py:339`).
   `_beispiel()` (`src/services/alert_test_service.py`) setzt aber neu = 1.2·S, alt = 0.8·S
   bei ABSOLUTE- und THRESHOLD_CROSSING-Regeln ⇒ Δ = 0.4·S < S ⇒ „unter“. Betroffen: Rückfall
   (ABSOLUTE Böen 50), jede ABSOLUTE-Trip-Regel, Sicht (THRESHOLD_CROSSING, 800 → 1200 „increase“,
   obwohl Sicht-Alarm ein Fallen meint).
2. **Doppelte Größen.** Mehrere Regeln landen auf demselben Summary-Feld bzw. derselben
   Katalog-Metrik: Vergleich-Standard liefert `temperature_min` und `temperature_change` (beide
   `temp_min_c`), `precipitation_sum` und `precipitation_change` (beide `precip_sum_mm`). Zudem
   löst `temp_min_c` mit Richtung „increase“ auf die Katalog-Metrik `temperature` auf — dieselbe
   wie `temp_max_c` ⇒ zweimal „Temp“ (`_resolve_metric_id`, `src/output/renderers/alert/project.py:234`).
3. **Gewitterstufe.** 0 → 1.2 rundet auf Stufe „leicht“ ⇒ Label „Luftmasse“ statt Gewitter
   (`_deviation_label`, render.py:202) — liest sich nicht wie ein Alarm.

## Related Files
- `src/services/alert_test_service.py` — `_beispiel`, `beispiel_aenderungen` (einziger Änderungsort)
- `src/output/renderers/alert/project.py` — `_resolve_metric_id`, `_METRICS` (Katalog, cmp je Metrik)
- `src/output/renderers/alert/model.py` — `over_thr`, `side_label`
- `src/output/renderers/alert/render.py` — `_verdict_single`, `_datablock_single`, `_deviation_label`
- `tests/tdd/test_alert_test_service.py` — bestehende Tests mit alter Formel (1.2/0.8), anzupassen
- `docs/specs/modules/feat_3441_test_alarm.md` — AC-11 nennt die alte Formel; wird durch neue Spec abgelöst

## Existing Patterns
- Katalog-cmp entscheidet die Richtung: `freezing_level`, `visibility`, `temperature_cold` = „unter“.
- Gewitter ist Stufenmetrik (0..3, `thunder_ordinal`), „leicht“ = 1.

## Lösungsansatz (Analyse, Summe 1 ⇒ zusammen mit Kontext)
- Richtung je Feld aus dem Katalog: hat ein Kandidat cmp „unter“ ⇒ fallend, sonst steigend.
- Steigend: alt = Basis (0 bei DELTA, sonst 0.8·S), neu = alt + 1.2·S. Fallend: neu = 0.8·S,
  alt = neu + 1.2·S. Damit |Δ| = 1.2·S ≥ S für jede Regelart.
- Stufenmetrik Gewitter: alt = 0, neu = min(3, max(2, ceil(1.2·S))) ⇒ mindestens „mäßig“.
- %-Einheit: neu ≤ 100 (alt entsprechend), damit keine unmöglichen Werte.
- Dedupe nach aufgelöster Katalog-Metrik: erste Regel gewinnt.

## Dependencies / Dependents
- Nur der Test-Alarm nutzt `_beispiel`; echte Alarmwege unberührt.

## Risks
- Spec #3441 AC-11 nennt die alte Formel ⇒ neue Spec dokumentiert die Ablösung.
- Mehrere Orte im Vergleich: dieselbe Größe erscheint je Ort einmal — das ist gewollt (je Ort ein Block),
  keine Doppelung im Sinne des Issues.

## Analysis

- **Type:** Bugfix (Befund aus Abnahme #3441)
- **Affected Files:** `src/services/alert_test_service.py` (MODIFY, ~40 LoC), `tests/tdd/test_alert_test_service.py`
  (MODIFY: alte Formel-Zusicherung ersetzen) + neue Testdatei für #3462 (CREATE),
  `docs/specs/modules/fix_3462_testalarm_beispielwerte.md` (CREATE), Spec #3441 AC-11 Verweis auf Ablösung (MODIFY).
- **Scope/Risk:** klein, niedrig — nur der Test-Alarm-Baustein; echte Alarmwege, Renderer und Katalog unverändert.
- **Technical Approach:** siehe „Lösungsansatz“ oben; Prüfung am echten Renderer (`over_thr`/`side_label`
  für jede Beispiel-Änderung „über“; gerenderte Mail/SMS/Telegram DE und EN enthalten nie „unter deiner
  Alarm-Schwelle“/„below your alert threshold“ und je Ort/Etappe jede Katalog-Metrik höchstens einmal).
- **Dependencies:** `_resolve_metric_id` und `_METRICS` aus `output.renderers.alert.project` (lesend).
- **Open Questions:** keine (fachlich klar aus Issue-Ziel; reine Beispielwerte).
