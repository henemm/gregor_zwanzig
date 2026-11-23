# Context: b6b2-3276-altfelder-frontend (Issue #3276)

## Request Summary
Nach #3237 werten Ausgabe und Prüfwerkzeuge nur noch `placements` (Tabelle „Was steht wo“, ADR-0124) aus. Das Frontend liest/schreibt aber noch Altfelder. Ziel (Spec #3122 AC-38, zweiter Teil): keine Oberfläche liest oder schreibt sie, jede Einstellung ist genau einmal (in der Tabelle) erreichbar. Voraussetzungen #3237 und #3154 sind geschlossen.

## Altfelder (Namen korrigiert)
`channel_layouts`, `outlook_metrics`, `outlook_metric_formats` (Issue schreibt fälschlich `outlook_metrics_formats`), `channel_active_metrics`, `hourly_metrics`, `hourly_metric_formats` (#3097, fehlt in der Issue-Liste), `show_outlook` (report_config). `per_channel_layouts` existiert im Frontend nicht (nur `channel_layouts_per_report`, types.ts:330 — prüfen).

## Related Files
| File | Relevance |
|------|-----------|
| frontend/src/lib/components/shared/WeatherMetricsTab.svelte | liest channel_layouts/outlook_* (509–597), schreibt Trip-Payload (937–963); bindet OutlookLayoutControls (1631, 1977) und CompareHourlyLayoutControls (1601) ein |
| frontend/src/lib/components/shared/WetterMetrikenVersandPanel.svelte | bettet WeatherMetricsTab ein; nur noch in TripNewEditor (919/1176) und CompareNewEditor (574/621) mit `bereich="zustellung"` |
| shared/weather-metrics-tab/weatherMetricsSavePayload.ts, channelMetricLayouts.ts, compareChannelMetricLayouts.ts, weatherMetricsCompareSave.ts | Aufbau/Merge der Altfeld-Payloads |
| compare/compareEditorSave.ts | schreibt hourly_*, outlook_*, channel_active_metrics (175–218, 551–572) |
| shared/versandVergleichSpeicherung.ts, alarmeVergleichSpeicherung.ts, wetter-tab/wertebereicheVergleichSpeicherung.ts | reichen hourly_/outlook_* an compareEditorSave durch |
| shared/MailInhaltCard.svelte, mailInhaltZustand.ts, mailInhaltKonstanten.ts | show_outlook durchgereicht (kein Schalter mehr) |
| shared/pickEigenfelder.ts | Schlüssellisten (69, 82–83) |
| shared/alarme-tab/alarmeDeliveryPayload.ts, utils/cockpitHelpers568.ts, kanalStilSpeicherung.ts | Issue-Liste; cockpitHelpers568:60 nutzt channel_layouts als „Layout konfiguriert“-Anzeige |
| shared/OutlookLayoutControls.svelte, compare/CompareHourlyLayoutControls.svelte | alte Bedienflächen für Ausblick/Stundenverlauf |
| shared/wetter-tab/wetterTabSpeicherung.ts, wasStehtWo*.ts, organisms/wetter-tab/WasStehtWoKarte.svelte | neuer Weg: placements |

## Existing Patterns
- Detail-Hub ist bereits sauber: CompareTabs/TripTabs nutzen `ZustellungTab` (#3154) und `WetterTab` mit „Was steht wo“-Karte; WeatherMetricsTab hängt nur noch im Anlege-Ablauf (Trip/Vergleich neu) über WetterMetrikenVersandPanel `bereich="zustellung"`.
- Sperre-Vorbild: tests/test_altpfad_import_sperre.py (VERBOTEN-Liste, ERLAUBT mit Begründung + Ablaufdatum, Selbstnachweis). Frontend-Pendant: Text-Scan per readFileSync (Muster: frontend/src/lib/issue_523_suggested_flag_cleanup.test.ts), läuft unter `node --test`.

## Dependencies
- Upstream: Go-Merge `internal/handler/config_merge.go:11–21` (Top-Level-Merge, nichts wird gelöscht); Trip PUT `trip.go:472/484`; Vergleich `briefing_subscription.go:180–300`, `compare_preset.go:325`; placements `store/briefing_placements.go:22–51`. ⇒ Lässt das Frontend Altfelder weg, bleiben sie in den Daten erhalten (Read-Modify-Write) — kein Datenverlust. Entfernen aus den Daten ist #3277.
- Downstream: keine Ausgabe liest die Altfelder mehr (#3237, Golden-Test tests/tdd/test_3237_golden_vier_kanaele.py).

## Existing Specs
- docs/specs/modules/feat_3122_was_steht_wo.md:306 (AC-38 wörtlich)
- docs/specs/modules/feat_3237_altpfad_entfernen.md (:27 „Schreibpfade = #3276“, :167, :66–67 show_outlook-Bereinigung = #3277)

## Risks & Considerations
- Vollständiges Senden von `channel_layouts`/`outlook_metrics` ersetzt den Bestand (kein Merge je Kanal) — Weglassen ist sicherer als leer senden. Nie leere Werte senden.
- Anlege-Ablauf: neue Trips/Vergleiche dürfen ohne Altfelder trotzdem korrekte placements bekommen (Standard über WetterTab createMode).
- Viele Unit-Tests (≈11 Dateien) und ~19 Playwright-Specs prüfen Altfelder; sie müssen umgestellt oder entfernt werden, nicht still gelöscht (Verhaltensnachweis über placements).
- show_outlook: hier nur Schreibweg entfernen; Modell-Bereinigung ist #3277.
- Trip/Vergleich-Codeteilung (#1170): Änderungen symmetrisch im geteilten Code.
- Home-Anzeige „Layout konfiguriert“ (cockpitHelpers568) braucht neue Quelle (placements) oder entfällt.

## Analysis

### Type
Feature (Rückbau, Spec #3122 AC-38 Teil 2)

### Zuschnitt (23.11.)
Gesamtumfang (22 Produktionsdateien, ~97 Testdateien, ~17 Playwright-Specs) zu groß für einen Durchlauf. Zerlegt in Kind-Issues von Epic #3122:
- **#3276 (dieser Workflow): Ortsvergleich-Pfad** — Anlegen + Speichern
- #3297: Trip-Pfad, show_outlook, Home-Anzeige „Layout konfiguriert" über placements
- #3298: Typen + Frontend-Sperrtest (scharf erst nach #3276/#3297)

### Affected Files (#3276)
| File | Change Type | Description |
|------|-------------|-------------|
| frontend/src/lib/components/compare/compareEditorSave.ts | MODIFY | hourly_*/outlook_*/channel_active_metrics nicht mehr schreiben (175–218, 551–572) |
| frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts | MODIFY/DELETE | Altfeld-Payload Vergleich |
| frontend/src/lib/components/shared/weather-metrics-tab/compareChannelMetricLayouts.ts | MODIFY/DELETE | channel_layouts Vergleich |
| frontend/src/lib/components/shared/versandVergleichSpeicherung.ts, alarmeVergleichSpeicherung.ts, wetter-tab/wertebereicheVergleichSpeicherung.ts | MODIFY | Durchreicher entfernen |
| frontend/src/lib/components/compare/wetterMetrikenPropsAus.ts | MODIFY | hourly*/outlook*/channelActive*-Props entfernen (78–114) |
| frontend/src/lib/components/compare-new/CompareNewEditor.svelte | MODIFY | POST ohne channelActiveMetricKeys/hourly*/outlook* (357–359) |
| frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts | MODIFY | stundenverlauf/ausblick aus ZUSTELLUNGS_SECTIONS Vergleich (83) |
| frontend/src/lib/components/compare/CompareHourlyLayoutControls.svelte | DELETE | alte Bedienfläche Stundenverlauf |
| frontend/src/lib/components/shared/WeatherMetricsTab.svelte | MODIFY | Mounts Vergleich-Zweig (1601, 1631) entfernen; OutlookLayoutControls-Trip-Zweig bleibt bis #3297 |
| zugehörige *.test.ts + e2e-Specs | MODIFY/DELETE | auf placements umstellen, nicht still löschen |

### Scope Assessment
- Files: ~12 Produktion + Tests
- Estimated LoC: netto stark negativ (Löschung), Neucode < 100
- Risk Level: MEDIUM (sichtbarer Anlege-Ablauf Vergleich; Go-Merge ersetzt Top-Level-Werte → Altschlüssel weglassen, nie leer senden)

### Technical Approach
Altschlüssel im Vergleich-Anlegen und -Speichern ersatzlos weglassen; placements entstehen bereits über WetterTab createMode (wetterTabSpeicherung.ts:54–60/115/140, mitPlacements). Tabelle deckt Stundenverlauf/Ausblick (places/formats je Metrik, outlook_reports Morgen/Abend) und Kanal-Auswahl (places je Kanal) vollständig ab → kein Funktionsverlust. Bestandsdaten bleiben durch Top-Level-Merge (config_merge.go:11–21) erhalten; Bereinigung ist #3277. Nachweis: Anlegen eines Vergleichs → POST enthält keine Altschlüssel, placements vorhanden, Mail-Ausgabe unverändert (Golden #3237).

### Dependencies
Go-Merge config_merge.go, compare_preset.go:325, briefing_subscription.go:180–300 (beim Spec-Schreiben prüfen: keine Server-Defaults/Validierung, die fehlende Altschlüssel verlangen).

### Open Questions
- keine Produktfrage offen (Home-Anzeige: Tech-Lead-Entscheid „Quelle wechselt auf placements", in #3297)
