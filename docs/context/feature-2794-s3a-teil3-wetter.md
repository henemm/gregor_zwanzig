# Context: feature-2794-s3a-teil3-wetter (Epic #2791, S3a Teil-PR 3)

## Request Summary
Teil-PR 3 von S3a (#2794): der Inhalt des Reiters **Wetter** für Trip und Orts-Briefing (ein Code, `context="route"|"vergleich"`) nach Mockup Fassung 3. Umfang laut Lieferplan der Gesamt-Spec `docs/specs/modules/feat_2794_s3a_reiter_wetter.md`: **AC-9 bis AC-21, AC-28 (Frontend-Spiegel), AC-29 (Alarmquellen-Gate, in Teil-PR 1 offen geblieben), AC-30**. Teil-PR 1 (Backend, PR #2870) und Teil-PR 2 (Reiterleiste/Umleitungen, PR #2892) sind live; S2b (PR #2862) ist gemergt (2026-11-09).
Grundlagen: Gesamtkontext `docs/context/feature-2794-s3a-reiter-wetter.md` (Analyse, PO-Entscheidungen 2026-11-08), Konzept `docs/context/einstellungen_neu.md` §4–§8, Mockup `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html` (704 Zeilen).

## Ist-Lage (gemessen gegen origin/main @ 7b47b1129, 2026-11-10)

**Reiter heute**
- Trip `frontend/src/lib/components/trip-detail/TripTabs.svelte:216-224`: `wetter` = `shared/WetterMetrikenVersandPanel.svelte` (`context="route" bereich="wetter"`) + darunter `CorridorEditor`/`CorridorEditorMobile` (Kommentar „bis Teil-PR 3“). `zustellung` (:225) = `ZustellungTab`.
- Vergleich `frontend/src/lib/components/compare/CompareTabs.svelte:794-826`: `wetter` = `WetterMetrikenVersandPanel context="vergleich"` (Mount erst bei `wetterMetrikenLayoutHydrationBereit`, :505) + `CorridorEditor(Mobile)`; `zustellung` :825/841. Achtung F012 aus Teil 2: Mount-Bedingungen in CompareTabs sind per AST-Test bewacht (`s3a2794_eine_wmt_instanz.test.ts`).
- `shared/WeatherMetricsTab.svelte` (2274 Zeilen): lädt `/api/metrics`, `/api/templates`, `/api/metric-presets`, `/api/auth/profile` (:544-551). Trip speichert `PUT /api/trips/{id}/weather-config` (:1014, Payload mit `ampel: ampelAngewendet`, :980/:764 via `ampelBeimAnwenden`) und danach `PUT /api/trips/{id}` (:1018). Vergleich speichert über `weather-metrics-tab/weatherMetricsCompareSave.ts` mit `enqueueHubWrite` (Hub-Schreibschlange, ETag-/Konfliktschutz). Amtliche-Warnungen-Schalter Snippet :1428 (Verwendung :1674 Vergleich, :2053 Route), `DayWindowCard` :1599/:1819, `WeatherV2PresetBar` :1718 (nur Trip), Vergleichszweig ab :1467 (Design-Audit: native Checkboxen, andere Oberfläche als Trip).
- Ordner `shared/weather-metrics-tab/`: AggregationMetricRow, channelMetricLayouts, compareAggregationGrouping, compareChannelMetricLayouts, compareMetricOrder, compareMetricSelection, DayWindowCard, kuerzelLegende, kuerzelMarken, MultiSymbolMetricRow, outlookFriendlyCapability, SavePresetDialog, ThresholdMetricRow, weatherMetricsCompareSave, weatherMetricsSavePayload, weatherMetricsTabSections, WeatherV2Grundauswahl, WeatherV2PresetBar, WeatherV2Reihenfolge, wertebereicheAnzeige.

**Backend (aus Teil-PR 1, live)**
- `/api/metrics` (`api/routers/config.py:110ff`, `**reiter_wetter_eigenschaften(m)` :172, definiert `src/app/metric_catalog.py:1252`) liefert `group`, `alertable`, `is_precursor`, `allowed_sides`, `display_only`. **Kein Frontend-Nutzer bisher.**
- `/api/templates` (:25-36) liefert je Vorlage `ampel` (deepcopy `AMPEL_TEMPLATES`). Vorlagen-Zeilen `src/app/ampel_templates.py:23ff` als Tupel `(metric_id, enabled, unten rot/orange/gelb, oben gelb/orange/rot, alarm_ab)`, `_vorlage()` :186-197 → `{"template","metrics":{id:{enabled,lower{red,orange,yellow},upper{yellow,orange,red},alarm_ab}},"thunder":{mittel,hoch}}`; `DEFAULT_TEMPLATE="allgemein"` :204.
- `src/app/ampel.py`: `validate_ampel` :92, `template_id_for` :154, `_verschmelzen` :159, `resolve_ampel` :176, `deviation_count` :245 (zählt enabled/alarm_ab/Grenzen; Metrik ohne Vorlagenzeile = aus/never), `thunder_color` :269, `ampel_seite` :314, `vorlage_label_schluessel` :358.
- Abweichungs-Fixture nur Python: `tests/fixtures/ampel_deviation_cases.json` → Frontend-Spiegel (AC-28) fehlt.
- Eigene Vorlagen: `kind` route/vergleich, Duplikat gegen eigene + 7 System (POST/PATCH, 409 `name_exists`), Standard je Art (Go `internal/handler/metric_preset.go`, Namen-Kopie `systemVorlagenNamen`, Drift-Test `tests/test_systemvorlagen_namen_drift.py`). `horizons` ist `json:"-"`; Migration `scripts/migrate_2794_preset_horizons.py` **noch nicht gelaufen** (gehört zum Deploy von Teil-PR 3, Runbook operations_playbook.md „Vorlagen-Zeithorizonte entfernen“, braucht gestoppte `gregor-api`).
- `SavePresetDialog.svelte` (318 Zeilen): Felder name, description, isDefault; POST `/api/metric-presets` mit `metrics[{metric_id,enabled,use_friendly_format,horizons}]` — **ohne `ampel`, ohne `kind`**.

**Speicherwege Go**
- Trip: `PutTripWeatherConfigHandler` `internal/handler/weather_config.go:55`, Ampel-Prüfung :98, `mergeConfigMap(trip.DisplayConfig, cfg)` :105 (flach: oberste Schlüssel überschrieben, `ampel` als Ganzes ersetzt, `trip.go:387-389`). Andere `display_config`-Schlüssel bleiben erhalten (relevant AC-30).
- Vergleich: `UpdateComparePresetHandler` `internal/handler/compare_preset.go:384`, `applyComparePresetPatch` :319, Ampel-Prüfung :437-438; Create :193/:262. Prüfer `internal/handler/ampel.go:93`.

**Alarm (S2b, gemergt)**
- Python-Texte `alarm.ampel.*` nur in `src/i18n/messages/{de,en}/alarm.json:85ff` (Mail/Telegram), Frontend-Katalog hat sie nicht.
- Gate „aktive Alarmquelle“ `src/services/trip_alert.py:684-702`: `has_active_rules = has_preset or has_metric_levels or any(rule.enabled)` — **erkennt `alarm_ab` nicht** (AC-29 offen). `resolve_ampel` erst :807.
- `src/services/compare_alert.py:868-887`: kein entsprechendes Gate, nutzt `metric_alert_levels` und `ampel=resolve_ampel(preset)`; zu prüfen, ob ein Vergleich ohne Altstufen bis dorthin kommt.

**Frontend-Typen/Bausteine**
- `frontend/src/lib/types.ts:368-369`: nur `ampel?: Record<string, unknown> | null`; kein Typ für Ampel-Struktur/`alarm_ab`.
- Ampel-Lesen sonst nur `AlarmeTab.svelte:189` (`aboAmpel`), `pickEigenfelder.ts:87`; `AlarmeTab` eigene „unalertable“-Ableitung :69/:267 (soll durch Katalogfelder ersetzt werden).
- Ersatz-Atome (ADR-0111, Eingabe aus #2881): `molecules/DatumFeld.svelte`, `molecules/UhrzeitFeld.svelte`, `ui/select/Select.svelte` (bits-ui), `ui/segmented/Segmented.svelte` (mit `rolle`; `atoms/Segmented.svelte` ohne), `Dot` doppelt (`atoms/Dot.svelte`, `ui/dot/Dot.svelte`). Natives `<select>` in `DayWindowCard.svelte` und ✓ in `WeatherV2Grundauswahl.svelte` sind beim Neubau zu ersetzen.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/trip-detail/TripTabs.svelte`, `compare/CompareTabs.svelte` | Panel `wetter` auf neuen Reiter umstellen, Mount-/Hydrations-Bedingung erhalten |
| `frontend/src/lib/components/shared/WetterMetrikenVersandPanel.svelte`, `WeatherMetricsTab.svelte`, `weather-metrics-tab/*` | heutige Oberfläche; Speicherwege (Trip-PUT, Vergleich-Schreibschlange) wiederverwenden; Alt-Oberfläche erst löschen, wenn neue vollständig abdeckt (Lieferplan) — Versand-Teil muss im Reiter Zustellung bleiben |
| `frontend/src/lib/components/shared/corridor-editor/` | entfällt im Reiter (Löschung Teil-PR 4) |
| `frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte` | Dialog W5b: + ampel, + kind, Texte, ohne Zeithorizonte |
| `frontend/src/lib/components/shared/weather-metrics-tab/DayWindowCard.svelte`, `versand-tab/dayWindowClamp.ts` | Karte „Anpassen“ (ADR-0035) |
| `frontend/src/lib/types.ts` | Ampel-Typen |
| `frontend/src/lib/i18n/messages/{de,en}/*.json`, `docs/reference/i18n_glossar.md` | neue Texte (Katalog `wetter.json`?), Glossar zuerst |
| `src/app/ampel.py`, `tests/fixtures/ampel_deviation_cases.json` | Referenz für Frontend-Spiegel (AC-28) |
| `src/services/trip_alert.py:684-702`, `src/services/compare_alert.py:868-887` | Alarmquellen-Gate (AC-29) |
| `internal/handler/weather_config.go`, `compare_preset.go`, `ampel.go`, `config_merge.go` | Schreibpfade, Validierung, Merge (AC-17 serverseitig, AC-30) |
| `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html`, `claude-code-handoff/current/jsx/*` | Soll-Optik |

## Existing Patterns
- Ein Code für Trip und Vergleich (`shared/`, `context`), Pendant-Sperre (#1170, ADR-0097).
- Abo speichert nur Abweichungen in `display_config.ampel.metrics`; Auflösung Vorlage → Abo (`resolve_ampel`); Go validiert Ampel bei jedem Schreibweg.
- Vergleich schreibt über die Hub-Schreibschlange (`enqueueHubWrite`, ETag), Trip über `saveController` + PUT.
- Texte nur über Katalog (`$t`), Wächter `keine_hartkodierten_nutzertexte.test.ts`; Paritäts-Test DE/EN.
- Gemeinsame JSON-Fixture für Python- und Frontend-Logik (Parität über beide Testschichten).

## Dependencies
- Upstream: Teil-PR 1 (Katalogfelder, Vorlagen-API), Teil-PR 2 (Reiter-Kennung `wetter`), S2b (Ampel-Alarm).
- Downstream: Teil-PR 4 (Löschung Altkomponenten, Übersicht, Texte), S3b #2795 (Inhalt je Kanal, Roh/Einfach), S8 #2800 (Radar-Schalter Trip).

## Existing Specs
- `docs/specs/modules/feat_2794_s3a_reiter_wetter.md` (Gesamt-Spec, ACs Teil 3 = AC-9…21, 28, 29, 30)
- `docs/specs/modules/feat_2794_s3a_teil2_leiste.md` (Muster: Detail-Spec je Teil-PR)
- `feat_2792_s1_profil_ampel.md`, `feat_2793_s2_alarm_stufenwechsel.md`, ADR-0109, ADR-0111, ADR-0035, ADR-0104

## Risks & Considerations
1. **Größe:** Neubau mehrerer Bausteine (Vorlage-Karte, Metrik-Zeile, Grenzen-Editor, Alarm-ab-Kopf, Nicht-im-Briefing, Warnungen & Radar, Anpassen, Dialog) — LoC-Limit wird überschritten; ggf. Override wie Teil 1 oder Unterteilung 3a/3b prüfen.
2. **Doppelte Instanzen/Speicherer:** Teil 2 hatte Regressionen durch doppelt gemountete Speicherer (Cooldown doppelter PUT). Der neue Reiter darf mit dem Rest von `WeatherMetricsTab` im Reiter Zustellung (Versand) nicht konkurrierend dieselben Felder schreiben.
3. **Ampel-Ersatz als Ganzes:** Server ersetzt `ampel` komplett → Frontend muss immer die vollständige Abweichungsmenge senden; parallele Tabs/Konflikt (ETag) beachten.
4. **Was wird aus Metrik-Auswahl alt (`active_metrics`/`metrics`)?** Neue Auswahl läuft über `ampel.metrics.<id>.enabled`; Renderer/Kanäle lesen evtl. weiter die alte Liste → Konsistenz klären (Analyse).
5. **AC-29 Gate:** Trip-Gate erkennt `alarm_ab` nicht; ohne Fix stellt die Oberfläche Alarme ein, die nie kommen. Vergleich gesondert prüfen.
6. **Migration `horizons`** beim Deploy dieses Teils (gestoppte `gregor-api`).
7. **Design-Audit-Befunde** (#2794-Kommentar 2026-11-09): keine nativen Controls, Kontrast ≥ 4,5:1, Touch-Ziele ≥ 44 px, gleicher Panel-Rahmen Trip/Vergleich.
8. Mandantentrennung: AC-30 mit zwei Nutzern.

## Analysis

### Type
Feature (Teil-PR 3 von S3a, Epic #2791): Inhalt Reiter **Wetter** für Trip und Orts-Briefing, ein Code (`context="route"|"vergleich"`). ACs: AC-9…AC-21, AC-28 (Frontend-Spiegel), AC-29 (Alarmquellen-Gate), AC-30.

### Kernbefunde (verifiziert 2026-11-10, Worktree auf Stand 29ed1d8b6)
1. **Metrik-Auswahl wirkt heute nicht über die Ampel.** Renderer/Resolver lesen die Auswahl aus `display_config.metrics[].enabled` (Trip, `src/output/renderers/trip_metric_ids.py:37-56`) bzw. `display_config.active_metrics` (Vergleich, `src/services/report_config_resolver.py:313`, `compare_metric_ids.py:171-223`). `resolve_ampel` (`src/app/ampel.py:176`) dient nur Farben/Alarm; `ampel.metrics.<id>.enabled` liest nur der Abweichungszähler (`ampel.py:169, 257-262`). Go `weather_config.go:105-108` synchronisiert `alert_rules` über `display_config.metrics`. Spec Z. 43 („Reiter Wetter bestimmt Metrik-Auswahl … in allen vier Kanälen“) nennt keinen Mechanismus → **Lücke, muss in die Teil-Spec**.
2. **AC-20 ODER-Regel existiert nirgends.** Alarm-Leser: `official_warnings.enabled`, Fallback `official_alert_triggers_enabled` (`trip_alert.py:1116-1118`, `compare_official_alert.py:184-197`); Inhalt `official_alerts_enabled` getrennt (`trip_report_scheduler.py:1696`, `scheduler_dispatch_service.py:939`). Frontend liest/schreibt getrennt (`compareHubHydration.ts:95-98`, `compareEditorSave.ts:233-282`, `AlarmeTab.svelte:237`). Go nur Merge/Migration (`trip.go:425-438`, `migrate_1258.go`).
3. **Radar** `radar_alert_enabled` nur Vergleich (`compareEditorSave.ts:237`, `compareHubHydration.ts:98`, Python `compare_radar_alert.py:228`); Trip ohne Schalter (S8).
4. **AC-29 Gate:** `trip_alert.py:684-709` und zweiter Block `:1190-1218`: `has_active_rules` kennt weder `alarm_ab` noch Ampel; Early-Return nur bei `not has_active_rules and report_config and not alert_on_changes`; `resolve_ampel` erst `:807`. `compare_alert.py` hat kein solches Gate (Fallback `_STANDARD_METRIC_LEVELS` :868-870, `ampel=resolve_ampel(preset)` :886) → Vergleich braucht keine Gate-Änderung, aber den Test mit/ohne `alarm_ab`; prüfen, dass `_display_config_from_active_metrics` Ampel-Metriken nicht wegfiltert.
5. **Speicherwege:** Trip `PUT /api/trips/{id}/weather-config` (`weather_config.go:55-126`, Ampel-Validierung :97-99, `mergeConfigMap` flach, `ampel` als Ganzes ersetzt; fremde `display_config`-Schlüssel bleiben → Basis für AC-30). Frontend Trip setzt `ampel` heute nur beim Vorlage-Anwenden (`WeatherMetricsTab.svelte:741/764/980`, `weatherMetricsSavePayload.ts:98-102`). Vergleich `weatherMetricsCompareSave.ts` (`enqueueHubWrite`, ETag) schreibt **kein** `ampel`; Compare-Preset-Handler validiert `ampel` bereits.
6. **Mounts & Wächter:** `WeatherMetricsTab` nur über `WetterMetrikenVersandPanel.svelte:63` (Prop `bereich` wetter|zustellung|alles, Trennung `weatherMetricsTabSections.ts:70-84`). Nutzer: `TripTabs.svelte:219`, `CompareTabs.svelte:800-806` (Hydrations-Bedingung `wetterMetrikenLayoutHydrationBereit` :505 erhalten), `TripNewEditor.svelte:866/1129`, `CompareNewEditor.svelte:534/545/608/613`, `ZustellungTab.svelte:37`. AST-Wächter: `shared/__tests__/s3a2794_eine_wmt_instanz.test.ts`, `s3a2794_speicher_owner_waechter.test.ts`, `s3a2794_zustellung_vergleich_ein_speicherer.test.ts`, `s3a2794_hub_zustellung_verdrahtung.test.ts`, `weather-metrics-tab/__tests__/s3a2794_bereich_filter.test.ts`; Bundle-Test `tests/tdd/test_issue_934_wizard_schedule.py:73-138`; E2E `frontend/e2e/s3a2794-hub-reiter-wetter-zustellung.spec.ts`, `hub-wetter-metriken-speichert-selbst.spec.ts`. Wächter werden bewusst nachgezogen, nicht aufgeweicht.
7. **Wiederverwendbar:** `alerts-tab/alarmAbAnzeige.ts` (Typ `AlarmAb`, `alarmAbZeile`, `ladeVorlagenAmpeln`, `STANDARD_VORLAGE`), `ui/segmented/Segmented.svelte` (mit `rolle`, ohne Farbpunkte), `ui/select/Select.svelte`, `molecules/DatumFeld|UhrzeitFeld`, `Dot`. Keine Ampel-Leisten-Komponente vorhanden.
8. **Glossar** (`docs/reference/i18n_glossar.md`): „Alarm ab“ vorhanden (Z. 185); fehlen: Wetter (Reiter), Vorlage, Ampel, Grenzen ändern, Nicht im Briefing. Veraltet: Reiter „Wertebereiche“, „Versand“ (Bereinigung Teil-PR 4).
9. **ADRs:** 0109 (Reiterstruktur, Pendant-Sperre), 0106 (Ampel einzige Bewertung, Gewitter ohne Gelb), 0111 (Design), 0110 (HubKopf), 0035 (Tagesfenster, `DayWindowCard`/`dayWindowClamp.ts`), 0097, 0104, 0101 (RMW). ADR-0108 nur „Vorgeschlagen“.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/trip_alert.py` (:684-709, :1190-1218) | MODIFY | gemeinsamer Helfer „Ampel-Alarmquelle aktiv“ (aktive Metrik in effektiver Auswahl mit `alarm_ab ≠ never`) in beiden Gate-Blöcken (AC-29) |
| `tests/tdd/test_*2794*_alarmquelle*.py` | CREATE | Trip- und Vergleichs-Einstieg mit/ohne `alarm_ab`, Versand beobachtet (AC-29) |
| `frontend/src/lib/components/shared/wetter-tab/ampelModell.ts` | CREATE | Ampel-Typen, Auflösung (Spiegel `_verschmelzen`), Abweichungszähler (AC-28), Reihenfolge-Regeln (AC-17), Gewitter-Regeln (AC-18), Erklärsatz-Modell |
| `frontend/src/lib/components/shared/wetter-tab/ampelSchreiben.ts` | CREATE | Speicher-Payload: minimale `ampel`-Abweichungsmenge + vollständige `metrics[]`/`active_metrics` |
| `frontend/src/lib/components/shared/wetter-tab/amtlicheWarnungen.ts` | CREATE | ODER-Lese-Regel + Doppelschreiben (AC-20) |
| `frontend/src/lib/components/shared/wetter-tab/__tests__/*.test.ts` | CREATE | `node --test` gegen `tests/fixtures/ampel_deviation_cases.json` (gemeinsame Fixture), Reihenfolge, ODER-Regel |
| `shared/wetter-tab/WetterTab.svelte` + `VorlageKarte`, `AlarmAbKopf`, `MetrikZeile`, `AmpelLeiste`, `GrenzenEditor`, `NichtImBriefing`, `WarnungenRadarKarte`, `AnpassenKarte` | CREATE | Oberfläche nach Mockup Fassung 3, genau ein Speicherer, `context`-Prop (AC-9…AC-21) |
| `shared/weather-metrics-tab/SavePresetDialog.svelte` | MODIFY | + `ampel`, + `kind`, Texte, ohne Zeithorizonte/Zusammenfassung |
| `shared/weather-metrics-tab/DayWindowCard.svelte` | MODIFY | `<select>` → `Select`-Atom, Clamp unverändert |
| `trip-detail/TripTabs.svelte`, `compare/CompareTabs.svelte`, `trip-detail/TripNewEditor.svelte`, `compare/CompareNewEditor.svelte` | MODIFY | Reiter `wetter` auf `WetterTab`; `WeatherMetricsTab` nur noch `bereich="zustellung"`; Hydrations-Bedingung Vergleich erhalten |
| `shared/weather-metrics-tab/weatherMetricsCompareSave.ts` | MODIFY | Vergleich-Speichern über Schreibschlange um `ampel`, `active_metrics`, Warn-Felder, `radar_alert_enabled` (oder neuer Speicherer nutzt `enqueueHubWrite` direkt) |
| `frontend/src/lib/types.ts` (:368-369) | MODIFY | Ampel-Typen statt `Record<string, unknown>` |
| `frontend/src/lib/i18n/messages/{de,en}/wetter.json`, `docs/reference/i18n_glossar.md` | CREATE/MODIFY | Texte DE/EN, Glossar zuerst |
| `internal/handler/*_test.go` (weather_config, compare_preset) | CREATE/MODIFY | AC-30 zwei Nutzer, Feld-Erhalt `metric_alert_levels`, `alarm_ab_migration`, Zustellungs-Felder; AC-20 Roundtrip beide Felder |
| `shared/__tests__/s3a2794_*.test.ts` | MODIFY | AST-Wächter auf neuen Wetter-Träger nachziehen (ein Speicherer je Reiter bleibt Zusicherung) |
| `frontend/e2e/s3a2794-teil3-*.spec.ts` | CREATE | Playwright je AC, gleicher Test-Code route/vergleich |

### Scope Assessment
- Files: ca. 25–30 (davon ~15 neu)
- Estimated LoC: Frontend ~+2500–3500 inkl. Tests, Python ~+150, Go-Tests ~+200; Entfernen erst Teil-PR 4
- Risk Level: **HIGH** — zentrale Einstellfläche beider Kontexte, zwei Speicherwege, Mount-Regressionen aus Teil 2, Auswahl-Mechanismus (Befund 1)

### Technical Approach (Tech-Lead-Entscheidung)
- **Auswahl-Mechanismus (Befund 1): Option (i) „Frontend hält beide Quellen konsistent“.** Auswahl lesen aus `metrics[]`/`active_metrics` (Bestandsabos bleiben korrekt); beim Speichern schreibt der Reiter `metrics[]`/`active_metrics` vollständig **und** `ampel.metrics.<id>.enabled` als Abweichung von der Vorlage. Reihenfolge bleibt die der bestehenden Liste, „+“ hängt hinten an. Vorlagenwechsel/Zurücksetzen setzt die Auswahl aus Vorlagen-`enabled` und leert die Abweichungen. Verworfen: (ii) Renderer/Resolver auf `resolve_ampel` umstellen (4 Kanäle + Compare-Resolver + `SyncAlertRules`, Mail-Inhalt soll sich in S3a nicht ändern, Reihenfolge gehört nicht in die Ampel); (iii) Go leitet beim Schreiben ab (Katalogwissen doppelt, zwei Handler). Absicherung: Test über die 7 Vorlagen, dass Frontend-Ableitung und `resolve_ampel` dieselbe aktive Menge liefern; Abweichungszähler = Python-Referenz über die gemeinsame Fixture.
- **AC-20:** ODER-Regel als Frontend-Lese-Helfer (`official_warnings` vorhanden → `official_warnings.enabled || official_alerts_enabled`; sonst `official_alert_triggers_enabled`, Default an); Umlegen schreibt beide Felder gleich. Renderer/Alarm-Engine unverändert. Go-Roundtrip-Test beider Speicherwege; Python-Test als Konsistenzprobe der bestehenden Alarm-Lesart.
- **AC-29:** gemeinsamer Python-Helfer in beiden Trip-Gate-Blöcken; Vergleich ohne Code-Änderung, aber mit Test.
- **Speichern:** Trip ein PUT `weather-config` (`ampel`, `metrics`, Warn-Felder, Tagesfenster), Go-Merge erhält fremde Schlüssel (AC-30); Vergleich über `enqueueHubWrite` mit ETag; `ampel` immer als vollständige Abweichungsmenge, bei Konflikt neu laden statt still überschreiben. Genau ein Speicherer je Reiter (Teil-2-Lehre).
- **Lieferung:** ein Workflow, eine Teil-Spec, intern in zwei Stufen (3.1 Modul/Gate/Lese-Regel ohne Oberfläche, 3.2 Oberfläche); LoC-Override wie Teil-PR 1 begründet. Benennung „3.1/3.2“, nicht „3a/3b“ (Kollision mit S3b #2795).
- **Deploy:** Migration `scripts/migrate_2794_preset_horizons.py` mit Dry-Run und Pre-Snapshot bei gestoppter `gregor-api` (Runbook „Vorlagen-Zeithorizonte entfernen“).

### Dependencies
- Upstream live: Teil-PR 1 (Katalogfelder, Vorlagen-API mit `ampel`/`kind`/Duplikat-Prüfung), Teil-PR 2 (Reiterkennung `wetter`, Umleitungen), S2b (Ampel-Alarm `alarm_ab`).
- Downstream: Teil-PR 4 (Löschung Altkomponenten, Glossar-Altbegriffe), S3b #2795 (Inhalt je Kanal), S8 #2800 (Radar Trip).

### Open Questions (technisch, in /30-write-spec zu entscheiden, keine PO-Frage)
- [ ] Teil-Spec `docs/specs/modules/feat_2794_s3a_teil3_wetter.md` nach Muster Teil 2; Mechanismus Befund 1 als eigene Zusicherung (neues AC oder Präzisierung AC-11/AC-19) aufnehmen.
- [ ] Orts-Standardvorlage (Spec-Hinweis Z. 327): beim Anlegen `active_metrics` aus Vorlagen-`enabled` ableiten — in Teil 3 oder Anlege-Kette.
- [ ] Fallback für eigene Bestandsvorlagen ohne `ampel` definieren.
- [ ] Hat die Altstufen-Migration (`alarm_ab_migration`) Bestandsabos schon alarmfähig gemacht? (betrifft nur Dringlichkeit AC-29)
