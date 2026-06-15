# Context: Issue #817 — Alerts-Tab auf Abweichungs-Schwellen (Δ statt absolut)

## Request Summary
Slice 2/3 von Epic #813. Der Alerts-Tab konfiguriert künftig **Δ-Schwellen** ("ab welcher
Änderung gegenüber dem letzten Briefing wird gemeldet") statt absoluter Festwerte. Das
#809-Gerüst (zentrale Ableitung, Self-Heal, Kanal-Erbschaft, ehrlicher Leerzustand) bleibt;
nur die Regel-Semantik wechselt absolut→Δ. Auswertung selbst kommt aus Slice 1 (#816, live).

## Schlüssel-Erkenntnis (Architektur)
Unter Slice 1 (#816) sind die **absoluten alert_rules-Schwellen bereits tot**: `from_alert_rules`
liest für `kind="absolute"`-Regeln NICHT `rule.threshold`, sondern setzt per `setdefault` den
**MetricCatalog-Δ-Default** ein (weather_change_detection.py:213–223). Nur für `kind="delta"`-Regeln
fließt `rule.threshold` direkt als Δ-Schwelle durch (Z. 224–236). Heute erzeugt aber Go's
`SyncAlertRules` ausschließlich `kind="absolute"`-Regeln und **entfernt aktiv alle Delta-Regeln**.

→ **Konsequenz:** Damit der im UI eingestellte Δ-Wert tatsächlich greift, MUSS `SyncAlertRules`
künftig `kind="delta"`-Regeln erzeugen. Die bisherigen absoluten Thresholds waren nie alert-wirksam
(Slice 1 überschrieb sie mit Katalog-Defaults) → Migration auf Δ verliert nichts Reales.

## Related Files
| File | Relevance |
|------|-----------|
| `internal/model/trip.go` | `AlertRuleKind` (absolute/delta existieren), `AlertRule`, `DefaultAlertThreshold` (nur absolut), `ActiveAlertableMetricIDs`, **`SyncAlertRules`** (erzeugt heute nur absolut, löscht Δ) |
| `internal/store/store.go` | Self-Heal: `SyncAlertRules` in `LoadTrip` (in-memory) + `SaveTrip` (compute-on-save) |
| `internal/handler/trip.go` | `UpdateTripHandler` (PUT /api/trips/{id}) merged `alert_rules`, vertraut auf SaveTrip-Sync |
| `internal/handler/weather_config.go` | PUT weather-config ruft zusätzlich SyncAlertRules |
| `frontend/src/lib/components/alerts-tab/AlertsTab.svelte` | Tab-Container, Loop über `AlertCard` |
| `frontend/src/lib/components/alerts-tab/AlertCard.svelte` | **Hauptziel UI**: zeigt heute nur `rule.threshold` absolut ("Schwelle:"), Mono `${metric} · ${threshold} ${unit}` |
| `frontend/src/lib/utils/alertMetricLabels.ts` | SSoT Labels/Units/Vergleichs-Operator pro Metrik |
| `frontend/src/lib/types.ts` | `AlertRuleKind='absolute'\|'delta'`, `AlertRule` (kind, threshold, delta_window, channels) — Typen existieren bereits |
| `frontend/src/lib/components/alerts-tab/AlertPreviewCard.svelte` | Empty-State #809 (`alert-preview-no-metrics`), kind-aware Preview |
| `src/services/weather_change_detection.py` | **Vertrag**: `from_alert_rules` liest `rule.threshold` für DELTA→`_thresholds[field]`; `detect_changes(include_absolute=False)` |
| `src/app/metric_catalog.py` | `default_change_threshold` pro Metrik (Δ-SSoT): gust/wind 20, precip 10, temp 5, thunder 1 |
| `src/app/models.py` | Python `AlertRule` (kind, metric, threshold, severity, enabled) |

## Existing Patterns
- **Self-Heal (#809):** `SyncAlertRules` idempotent in LoadTrip (in-memory) + SaveTrip (compute-on-save) — keine separate Migration nötig, läuft beim nächsten Load/Save automatisch.
- **Cross-Language-Wertekontrakt (#802 naismith):** Go-Defaults müssen Python-`default_change_threshold` exakt spiegeln. Neuer `DefaultDeltaThreshold`-Map muss zu metric_catalog passen.
- **Δ-Default-Setdefault (#816):** Slice 1 nutzt bereits Katalog-Δ-Defaults für absolute Regeln → genau diese Werte werden zu den editierbaren Δ-Start-Werten in Slice 2.
- **Mandantentrennung:** Store namespaced über UserID; PUT-Handler nutzt UserIDFromContext.

## Dependencies
- **Upstream (Slice 1, #816, live):** `from_alert_rules` (DELTA-Pfad), `detect_changes(include_absolute=False)`, `alert_state`, `render_deviation_alert`. Diese KONSUMIEREN bereits Δ-Regeln korrekt.
- **Downstream:** Briefing-Pfad nutzt `detect_changes(include_absolute=True)` separat — darf nicht brechen. Weather-Metriken-Ampel (`display_thresholds`) ist getrennt von alert_rules, unberührt.

## Existing Specs
- `docs/specs/modules/issue_816_alert_deviation_core.md` — Slice 1 (Δ-Auswertung)
- Epic #813 (Konzept-Issue, offen) — PO-Vision: Alert = Abweichungs-Wächter gegen letztes Briefing

## Risks & Considerations
- **Migration/Datenerhalt (CLAUDE.md Schema-Rework):** Bestehende `kind="absolute"`-Regeln → `kind="delta"` mit Δ-Default. Custom-absolute-Thresholds waren nie alert-wirksam → Reset auf Δ-Default ist sauber, ABER: enabled/severity/channels/pair_id MÜSSEN erhalten bleiben (read-modify-write, kein Replace).
- **Cross-Lang-Drift:** Go `DefaultDeltaThreshold` muss `metric_catalog.default_change_threshold` exakt spiegeln, sonst weichen Default-Anzeige (Go/UI) und Auswertung (Python) ab.
- **snow_line:** hat evtl. KEIN `default_change_threshold` im Katalog — Δ-Semantik für Schneefallgrenze klären (im Spec).
- **Delta-only-Metriken** (`temperature_change`, `wind_change`, `precipitation_change`): parallele AlertMetric-Werte. Mit Δ-Semantik der Basis-Metriken (temp_max etc.) werden sie überflüssig/überlappend — Scope im Spec abgrenzen.
- **Idempotenz:** Self-Heal muss bei wiederholtem Load/Save stabil bleiben (kein erneutes Reset bereits migrierter Δ-Regeln).
- **Scope-Grenze (Issue):** NUR UI + Regel-Semantik. Keine Änderung an der Δ-Auswertung (Slice 1).
