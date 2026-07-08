# Context: fix-1105-compare-metrics-snow

## Request Summary
Im v2-Ortsvergleich-Layout (#1110) soll die im Editor gewählte Metrik-Teilmenge die
Übersichtstabelle der echt zugestellten Mail exakt bestimmen — inkl. Schneehöhe als
ganz normale, abwählbare Metrik (PO: keine Sonderrolle).

## Ausgangslage (nach #1110 v2 + #1104 Resolver)
Die Resolver-Kette ist Ende-zu-Ende **bereits verdrahtet** und wirkt im produktiven
Preset-Versandpfad:

Editor (`activeMetricKeys`) → Go `PUT /api/compare/presets/{id}` →
`data/users/<uid>/compare_presets.json` `display_config.active_metrics` →
`scheduler_dispatch_service.py` → `resolve_enabled_metrics()` →
`render_compare_html(enabled_metrics=…)` → `_visible_metrics()`-Filter.

**Der eigentliche Bug:** Schneehöhe ist im v2-Renderer-Katalog `CV2_METRICS` gar nicht
enthalten. Sie kann daher weder angezeigt noch (folglich) abgewählt werden — obwohl
Datenmodell, Resolver und Frontend-Katalog sie tragen. „Abwählbar" setzt „renderbar" voraus.

## Related Files
| Datei | Relevanz |
|------|-----------|
| `src/output/renderers/email/compare_html.py` | `CV2_METRICS` (Z. 70–77) + `_metric_value` (Z. 122–126) + `_visible_metrics` (Z. 169–176). **Kernänderung:** Schnee-Zeile(n) ergänzen. `_metric_value` nutzt `getattr(loc, key)` → Schnee-Attribute existieren bereits, kein Sonderfall nötig. |
| `src/output/renderers/comparison.py` | Single Entry Point `render_compare_email` (Z. 112) + Plain-Text `render_comparison_text` (Z. 28, Metrik-Zeilen ~74–81). Plain-Text muss Schnee analog rendern. |
| `src/output/renderers/compare_metric_ids.py` | Resolver `resolve_enabled_metrics` (Z. 23–40). Mapping enthält bereits `snow_depth_cm→snow_depth_cm`, `snow_new_sum_cm→snow_new_cm` (Z. 12–13). Keine Änderung nötig. |
| `src/app/user.py` | `LocationResult.snow_depth_cm` (Z. 157), `snow_new_cm` (Z. 158). Datenquelle für `getattr`. |
| `frontend/src/lib/components/compare/compareMetricDefs.ts` | `ALL_METRICS` inkl. `SNOW_DEPTH` (`snow_depth_cm`, Label „Schneehöhe") + `SNOW_NEW` (`snow_new_sum_cm`). Frontend bietet Schnee bereits an. |
| `src/services/scheduler_dispatch_service.py` | Produktiver Preset-Pfad, Resolver bei Z. 270 verdrahtet (:277 durchgereicht). Vermutlich keine Änderung. |
| `src/services/compare_subscription.py` | Zweiter Versandpfad (Subscriptions, `sub.display_config`), Z. 102–106 bewusst **nicht** an `enabled_metrics` verdrahtet. Offener Punkt (s.u.). |

## Existing Patterns
- **Metrik = Katalog-Eintrag:** Jede Übersichts-Metrik ist ein Dict in `CV2_METRICS`
  (`key`/`label`/`unit`/optional `sev`/`decimals`). `_metric_value` liest per `getattr`.
  Schnee folgt exakt diesem Muster → `{"key": "snow_depth_cm", "label": "Schneehöhe", "unit": "cm"}`.
- **Filter-Semantik (#1104):** `enabled_metrics=None` → alle Zeilen (Default);
  Set → `warn` immer + gewählte Keys. Snow-Keys müssen die Renderer-IDs sein
  (`snow_depth_cm`, `snow_new_cm`), damit der Filter greift.
- **v2-Tests vorhanden:** `tests/tdd/test_issue_1110_compare_mail_v2.py` prüft
  `_visible_metrics`-Filter (Z. 312–355). Neue Schnee-Tests reihen sich hier ein.

## Dependencies
- **Upstream:** `LocationResult.snow_depth_cm/snow_new_cm` müssen für Schnee-Orte befüllt
  sein (Provider). Fehlt → `_fmt_metric` rendert „—" (unkritisch).
- **Downstream:** Compare-Mail-Validator (`email_spec_validator.py`, `X-GZ-Mail-Type: compare`),
  #811-Mode-Matrix, `renderer_mail_gate.py` (blockiert Commit auf Mail-Renderer-Dateien
  bis Validator+Mode-Matrix frisch grün).

## Existing Specs / Tests
- `tests/tdd/test_issue_1104_compare_config_foundation.py` — Resolver + Durchreichung.
- `tests/tdd/test_issue_1110_compare_mail_v2.py` — v2-Layout + enabled_metrics-Filter.
- `tests/tdd/test_issue_811_mode_matrix.py` — Renderer-Mode-Gate (17 Tests).

## Risks & Considerations
- **Default-Sichtbarkeit:** PO-Entscheid „keine Sonderrolle" → Schnee im Default (kein
  Filter) sichtbar wie alle Metriken. Konsequenz: auch schneefreie Vergleiche zeigen
  eine „Schneehöhe: — / — / —"-Zeile. Bewusst so; in ACs zur PO-Freigabe explizit machen.
- **Ein oder zwei Schnee-Zeilen?** Frontend bietet `SNOW_DEPTH` + `SNOW_NEW`. „Keine
  Sonderrolle" spricht für beide als reguläre Metriken. In Spec-ACs festlegen.
- **Zweiter Versandpfad:** `compare_subscription.py` filtert `enabled_metrics` nicht.
  Der Editor speist den **Preset**-Pfad (bereits gefiltert). Ob Subscriptions ebenfalls
  gefiltert werden müssen → Spec-Entscheid: mit-verdrahten oder Folge-Issue.
- **Gate-Pflicht:** Mail-Renderer-Edit ⇒ `renderer_mail_gate.py` blockiert Commit ohne
  frischen Compare-Validator-Lauf gegen echt zugestellte Staging-Mail + grüne Mode-Matrix.

## Analysis

### Type
Bug — Schneehöhe fehlt im v2-Renderer-Katalog, daher weder anzeigbar noch abwählbar.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/email/compare_html.py` | MODIFY | Zwei Schnee-Einträge zu `CV2_METRICS` ergänzen (`snow_depth_cm` „Schneehöhe" cm, `snow_new_cm` „Neuschnee" cm). `_metric_value` bleibt unverändert (`getattr` deckt beide ab). |
| `src/output/renderers/comparison.py` | MODIFY | Plain-Text-Übersicht: Schnee-Zeilen analog rendern, damit Text-Mail konsistent ist. |
| `tests/tdd/test_issue_1105_compare_snow_metric.py` | CREATE | Rote Tests: Schnee im Default sichtbar; Schnee abwählbar via `enabled_metrics`; Schnee erscheint bei expliziter Wahl. |

### Scope Assessment
- Files: 3 (2 MODIFY, 1 CREATE Test)
- Estimated LoC: +~40 / -0
- Risk Level: LOW (folgt exakt bestehendem Katalog-Muster; Resolver-Kette bereits verdrahtet)

### Technical Approach
Schnee als reguläre Metrik behandeln (PO: keine Sonderrolle):
1. `CV2_METRICS` um `{"key": "snow_depth_cm", "label": "Schneehöhe", "unit": "cm"}` und
   `{"key": "snow_new_cm", "label": "Neuschnee", "unit": "cm"}` erweitern. Renderer-Keys
   müssen exakt den Resolver-Ziel-IDs entsprechen, damit `_visible_metrics` greift.
2. `_metric_value` unverändert — `getattr(loc, "snow_depth_cm")` / `getattr(loc, "snow_new_cm")`
   funktioniert; `None` → `_fmt_metric` rendert „—".
3. Plain-Text-Renderer (`comparison.py`) analoge Schnee-Zeilen ergänzen.
4. Keine Schwellen-/`sev`-Färbung für Schnee (kein Risiko-Signal wie Temp/Wind) — reine Datenzeile.

### Dependencies
- Resolver `resolve_enabled_metrics` (compare_metric_ids.py) trägt Snow-Mapping bereits — unverändert.
- Filter `_visible_metrics` unverändert — greift automatisch, sobald Snow-Keys im Katalog stehen.

### Open Questions
- [x] Ein oder zwei Schnee-Zeilen? → **Beide** (Schneehöhe + Neuschnee), reguläre Metriken.
- [x] Subscription-Pfad mit-verdrahten? → **Nein**, Folge-Issue (Editor speist nur Preset-Pfad).
- [ ] Default-Sichtbarkeit von Schnee (immer sichtbar bei fehlendem Filter) → in AC-Freigabe bestätigen.

