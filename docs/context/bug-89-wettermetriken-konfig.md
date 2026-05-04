# Context: Bug #89 — Konfiguration Wettermetriken

## Request Summary

Issue #89 meldet, dass der "Wetter-Metriken konfigurieren" Dialog (1) den friendly-format-Toggle
nicht zeigt, (2) die Aggregations-Konfiguration unzureichend ist, (3) nicht der Spec entspricht
und (4) schlechter als die alte UI ist.

## Beobachteter Ist-Zustand (Screenshot 2026-04-25)

Der Dialog hat 6 Spalten: Metrik | Wert (Agg) | Label (friendly) | Alert | M | A

**Bugs:**
- Alert-Checkboxen sind für Temperatur, Gefühlte Temp, Wind, Böen standardmäßig **aktiviert** (Bug: Default sollte `false` sein)
- Label-Spalte hat 130px-Lücken für Metriken ohne `friendly_label`
- Dialog ist zu breit → rechte Seite abgeschnitten

## Related Files

| File | Relevance |
|------|-----------|
| `src/web/pages/weather_config.py` | Haupt-Dialog-Implementierung |
| `src/app/metric_catalog.py` | MetricDefinition mit `friendly_label`, `default_change_threshold` |
| `src/app/models.py` | MetricConfig, UnifiedWeatherDisplayConfig |
| `src/app/loader.py` | Serialisierung/Deserialisierung |
| `docs/specs/modules/weather_config.md` | Spec v2.3 — Dialog-Layout |
| `docs/specs/modules/weather_metrics_ux.md` | Spec v1.1 — Friendly format toggle |

## Existing Specs

- `docs/specs/modules/weather_config.md` v2.3 — Phase 2 Dialog mit 6 Spalten
- `docs/specs/modules/weather_metrics_ux.md` v1.1 — Friendly format toggle (use_friendly_format)

## Diskrepanz Spec vs. Implementierung

**Spec (weather_config.md v2.1 Phase 2 Layout)** zeigt einfaches 2-Spalten-Layout:
- Metrik-Checkbox + Aggregations-Buttons

**Aktuelle Implementierung** hat 6 Spalten inkl. Label, Alert, M, A — das ist mehr als die
ursprüngliche Spec zeigte, aber entspricht v2.3 (Alert wurde in v2.3 hinzugefügt).

Der Benutzer kritisiert aber, dass das Resultat visuell unbrauchbar ist (zu breit, Alert-Bug,
Lücken in Label-Spalte).

## Dependencies

- Upstream: `metric_catalog.py` → `MetricDefinition.friendly_label`, `default_change_threshold`
- Downstream: `trip_report.py` → liest `use_friendly_format` aus gespeicherter Config

## Risks & Considerations

- Alert-Bug: `initial_alert = mc.alert_enabled` — wenn Trip-JSON bereits `alert_enabled: true`
  gespeichert hat, wird es auch so geladen (kein UI-Bug, sondern Datenbug)
- Oder: Default in `MetricConfig` ist `alert_enabled: bool = False`, aber bestehende Trip-JSONs
  könnten `alert_enabled: true` enthalten
- Dialog-Breite: `max-width: 960px` sollte passen, aber 6 Spalten mit min-width-Constraints
  können zu Overflow führen

---

## Bezug zur SMS-Format-Spec v2.0 (Commit 202ae47)

**Wichtig:** Der Konfig-Dialog steuert genau die Metriken, die in der Token-Line der
Reports landen. `docs/reference/sms_format.md` v2.0 ist die Single Source of Truth
für die Output-Tokens — sie definiert, was der Dialog konfiguriert.

### Mapping Dialog-Spalte → Spec v2.0

| Dialog-Spalte | v2.0-Konzept | Quelle |
|---------------|--------------|--------|
| **Metrik** (Checkbox) | Aktiviert das Token (`N`, `D`, `R`, `PR`, `W`, `G`, `TH`, `TH+`) | sms_format.md §3.2 |
| **Wert (Agg)** | Threshold + Peak in Klammern: `R0.2@6(1.4@16)` | sms_format.md §5 |
| **Label (friendly)** | Klartext-Variante für E-Mail-Summary | renderer_email_spec.md §3 |
| **Alert** | `change_threshold`-Tracking → Update-Reports | metric_catalog.default_change_threshold |
| **M / A** | Token aktiv im Morning- bzw. Abend-Report | sms_format.md §8 (Beispiele) |

### Welche Tokens sind user-konfigurierbar?

| Kategorie | Konfigurierbar? | Begründung |
|-----------|-----------------|------------|
| Forecast (`N D R PR W G TH TH+`) | **Ja** | Standard-Wetter-Metriken |
| Vigilance (`HR:` `TH:` Vigilance) | **Nein** | Provider-getrieben (Météo France), entweder verfügbar oder nicht |
| Fire (`Z:` `M:`) | **Nein** | Korsika-only, automatisch wenn relevant |
| Wintersport (`SN SN24+ SFL AV WC`) | **Ja** (optional) | Nur bei `trip.profile == "wintersport"` |
| Debug (`DBG`) | **Nein** | Nur Dry-Run |

### Konsequenzen für den Dialog-Fix

1. **Dialog zeigt nur konfigurierbare Tokens.** Vigilance/Fire/Debug sind keine Dialog-Zeilen.
2. **Threshold-Spalte korrespondiert zu §5 v2.0:** Threshold==Max-Optimierung muss serverseitig
   greifen — der Dialog konfiguriert nur den Schwellwert, nicht die Klammern-Logik.
3. **Alert-Default = `false`** ist konsistent mit v2.0 — Alerts sind explizite Opt-ins für
   Update-Reports, nicht das Standard-Verhalten.
4. **Label-Spalte (friendly):** Nur sichtbar wenn `MetricDefinition.friendly_label` gesetzt ist.
   Leere Zeilen für Tokens ohne Klartext (z.B. `TH+`) sind Layout-Bug, kein Spec-Mismatch.

### Cross-Spec-Konsistenz prüfen

Beim Fix sicherstellen:
- `metric_catalog.py` enthält für jeden konfigurierbaren v2.0-Token ein `MetricDefinition`-Eintrag
- `MetricConfig.aggregations` (Bug #89 Kern: dead code) wird durch Threshold + Peak (v2.0 §5) ersetzt
- M/A-Toggles greifen in `trip_report.py` beim Token-Line-Bau
