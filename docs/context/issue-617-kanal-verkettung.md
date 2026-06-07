# Context: #617 — Kanal-Verkettung (Briefing-Zeitplan + Alerts)

## Request Summary
Der im Wetter-Metriken-Tab gesetzte Kanal-Zustand (`display_config.channels = {email, telegram, sms}`)
soll durch die Nachbar-Tabs „Briefing-Zeitplan" und „Alerts" fließen: nur dort aktive Kanäle erscheinen
als Option, Alerts erben sie als Vorbelegung (pro Alert überschreibbar). Slice 3/4 des Design-Pakets
„Trip bearbeiten" (#575). Quelle: `screen-trip-edit-v2-main.jsx` (`TE2_ZeitplanTab`, `TE2_AlertsTab`).

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/trip-detail/WeatherV2Kanaele.svelte` | #587 — setzt `display_config.channels` (Quelle der Verkettung) |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | Hält/persistiert `channels` (read-modify-write auf display_config) |
| `frontend/src/lib/components/trip-detail/BriefingScheduleTab.svelte` | Ziel-Tab 1; rendert EditReportConfigSection |
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` | Aktuelle Kanal-Checkboxen (global, gated nur über Account-Profil) |
| `frontend/src/lib/components/alerts-tab/AlertsTab.svelte` | Ziel-Tab 2; aktuell Metrik-Tabellen-Paradigma (#586), KEIN Kanal-Konzept |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Tab-Container; rendert die Tabs unabhängig (kein gemeinsamer Channel-State wie im JSX) |
| `frontend/src/lib/types.ts` | `ReportConfig` (send_email/telegram/sms global), `AlertRule` (kein channels-Feld) |
| `internal/model/trip.go` | `ReportConfig`/`DisplayConfig` = `map[string]interface{}` (additiv ✓); `AlertRule` = typisierter Struct (Feld-Add nötig für per-Alert-Kanäle) |
| `src/services/trip_report_scheduler.py` | Send-Pipeline liest `report_config.send_email/telegram/sms` (global) |
| `src/services/trip_alert.py` | Alert-Versand liest ebenfalls `report_config.send_email/telegram` (kein per-Alert-Kanal) |

## Existing Patterns
- **Zwei Kanal-Konzepte koexistieren heute:**
  1. `report_config.send_email/telegram/sms` — global pro Trip, **treibt tatsächlich den Versand** (Scheduler + Alerts).
  2. `display_config.channels` (#587 Wetter-Tab) — aktuell **nur UI/gespeichert, NICHT im Versand konsumiert**.
- JSX-Modell: ein gemeinsamer React-`channels`-State im Parent, per Props in alle Tabs durchgereicht.
  Svelte heute: jeder Tab lädt/speichert eigenständig (kein geteilter State über TripTabs).
- Read-modify-write ist Pflicht bei display_config/report_config (Datenverlust-Schutz, BUG-DATALOSS-GR221).

## Daten-Gap (entscheidend für Scope)
- **Briefing-Zeitplan:** `report_config` ist map → per-Briefing-Typ-Kanäle wären additiv ohne Go-Schema-Änderung
  speicherbar. Aber: Scheduler liest heute **globale** send_*-Flags, nicht pro-Typ.
- **Alerts:** `AlertRule` ist ein **typisierter Go-Struct** → ein `channels`-Feld erfordert Go-Schema-Änderung
  (sonst fällt es beim JSON-Roundtrip raus). Versand (`trip_alert.py`) kennt heute keine per-Alert-Kanäle.

## Risks & Considerations
- **Potemkin-UI-Risiko:** UI-Kanal-Auswahl, die der Versand nicht honoriert → sichtbare, aber wirkungslose Schalter.
- **Scope-Entscheidung nötig (PO):** Reine UI-Verkettung (Config-Oberfläche) vs. vollständige Versand-Verdrahtung
  (Go-AlertRule.Channels + per-Typ-Kanäle + Python-Scheduler/Alert-Service + Multi-User-Tests).
- **Doppelte Gating-Logik:** Briefing-Tab gated Kanäle heute über Account-Profil-Verfügbarkeit (mail_to etc.);
  JSX kennt nur Wetter-Metriken-Kanäle. Beide Gates müssen sinnvoll kombiniert werden.
- **Alerts-Paradigmen-Konflikt:** JSX `TE2_AlertsTab` = Karte-pro-Alert mit Kanal-Chips; aktuelle AlertsTab (#586)
  = Metrik-Tabelle + Modus-Picker. 1:1-JSX würde die #586-Oberfläche stark umbauen.
- Multi-User: jeder Endpoint mit echtem user_id, mit zwei Nutzern testen.

## Existing Specs
- `docs/specs/modules/issue_587_weather_tab_v2.md` — Wetter-Tab v2 (Quelle der channels)
- `docs/specs/modules/issue_180_alert_metric_table.md` — aktuelles Alerts-Paradigma (#586)

## PO-Entscheidungen (2026-06-07)
- **Scope = Schlanke Verkettung:** `display_config.channels` (Wetter-Tab) ist die EINE Quelle.
  Briefing-Zeitplan zeigt nur diese Kanäle; `report_config.send_*` wird synchron gehalten,
  damit der Versand sofort stimmt. Eine trip-weite Kanal-Menge (KEINE pro-Briefing-Typ-Persistenz).
- **#617 zugeschnitten auf NUR Briefing-Zeitplan.** Alerts-Teil ausgegliedert nach **#638**.
- **#638 (separat):** Alerts auf Karten-Modell (JSX) umbauen, Severity-Spalte entfernen
  (heute Falle: „Info" = stilles Stummschalten via Significance-Filter `trip_alert.py:411`;
  Warnung/Kritisch nur kosmetisch), Kanal pro Alert inkl. Versand-Routing in `trip_alert.py`.
- **Befund Severity:** `_RULE_SEVERITY_TO_CHANGE_SEVERITY` (info→MINOR/warn→MODERATE/crit→MAJOR),
  Filter sendet nur ≥MODERATE → info wird nie versendet. Richtung (Temp hoch/runter) ist bereits
  über getrennte Metriken `temperature_min`/`temperature_max` + `_ALERT_METRIC_COMPARISON` gelöst.
