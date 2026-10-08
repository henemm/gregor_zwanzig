---
entity_id: rework_2230_corridor_path_removal
type: module
created: 2026-10-08
updated: 2026-10-08
status: approved
version: "1.0"
workflow: rework-2230-corridor-path-removal
tags: [rework, removal, dead-code, alerts, corridor]
---

# Rueckbau Korridor-/Grenzwert-Alarmpfad (#2230)

## Approval

- [x] Approved (PO, 2026-10-08 — ohne AC-4/Test 2: reiner Rückbau ohne geänderten Datenweg, AC-3 sichert die Ausgaben; `test_cape_not_selectable.py` AC-10 ersatzlos löschen; `loc_limit_override 1500`)

## Purpose

Der Korridor-/Grenzwert-Alarmpfad (`evaluate_corridor_thresholds()` -> `corridor_hits` -> `CorridorEvent` -> Korridor-Renderer) hat seit #1460 keinen Produktiv-Aufrufer mehr: Wertebereiche (`corridors`) sind nur noch Empfindlichkeitsstufe und Mail-Markierung, kein Alarm-Ausloeser. PO-Entscheid 2026-09-08: der tote Pfad wird entfernt, nicht reaktiviert. Das Persistenz-/Editor-Feld `corridors` bleibt unangetastet (Datenerhalt #102).

## Source

- **File:** `src/services/corridor_threshold.py` (Modul entfaellt vollstaendig)
- **Identifier:** `evaluate_corridor_thresholds`, `resolve_corridor_summary_field`, `CorridorHit`; Kette: `TripAlertService._send_alert(corridor_hits)` -> `NotificationService.send_deviation_alert(corridor_hits)` -> `alert.project.to_alert_message(corridor_hits)` -> `to_corridor_events` -> `CorridorEvent` / `AlertMessage.corridor_events` -> Korridor-Zweige in `alert/render.py`

> **Schicht-Hinweis:** ausschliesslich Python-Core (`src/services/`, `src/output/renderers/alert/`) und `tests/`. Keine Aenderung an Go-API (`internal/`), Frontend (`frontend/src`), `src/app/models.py`, `src/app/trip.py`, `src/app/loader.py`. Grep ueber `internal/`, `frontend/src`, `api/`, `cmd/`, `scripts/`, CI-Listen: null Treffer auf `corridor_hits`, `evaluate_corridor_thresholds`, `corridor_threshold`, `CorridorHit`, `CorridorEvent`.

## Estimated Scope

- **LoC:** ca. -1.100 / +120 (Quellcode ca. -410, Tests ca. -800 geloescht bzw. angepasst, +120 neue Gleichheits-Tests). Ueber dem 250-LoC-Limit des Workflows: `workflow.py set-field loc_limit_override 1500` noetig.
- **Files:** 7 Quelldateien (1 geloescht, 6 gekuerzt), 2 Testdateien geloescht, 11 Testdateien angepasst, 1 Testdatei plus Fixture-Ordner neu
- **Effort:** medium (viel Streichen, wenig Neues; Risiko liegt in der Byte-Gleichheit der verbleibenden Alarm-Ausgaben)

## Fundstellen-Inventar

Kategorien: (a) Produktionscode zu entfernen, (b) Test prueft nur den toten Pfad -> loeschen, (c) Test uebergibt Korridor-Objekte nur nebenbei -> anpassen, (d) bleibt (Persistenz / Editor / Mail-Markierung).

### (a) Produktionscode entfernen

| Datei:Zeile | Was | Kat. |
|---|---|---|
| `src/services/corridor_threshold.py:1-119` | Gesamtes Modul (`resolve_corridor_summary_field` :32, `CorridorHit` :57, `evaluate_corridor_thresholds` :68) | a |
| `src/services/trip_alert.py:46` | Import `CorridorHit` | a |
| `src/services/trip_alert.py:2880`, `:2890`, `:2933` | Parameter `corridor_hits` von `_send_alert`, Docstring-Satz, Durchreichung an `send_deviation_alert` | a |
| `src/services/notification_service.py:860`, `:867-868`, `:895` | Parameter `corridor_hits`, Docstring, Durchreichung an `to_alert_message` | a |
| `src/output/renderers/alert/project.py:312`, `:321-323`, `:387-390`, `:393` | Parameter `corridor_hits`, Docstring, Aufbau `corridor_events`, Uebergabe an `AlertMessage` | a |
| `src/output/renderers/alert/project.py:398-439` | `_resolve_corridor_metric_id` (importiert `resolve_corridor_summary_field`) | a |
| `src/output/renderers/alert/project.py:442-481` | `to_corridor_events` | a |
| `src/output/renderers/alert/project.py:19` | Import `CorridorEvent` | a |
| `src/output/renderers/alert/model.py:246-275` | Dataclass `CorridorEvent` | a |
| `src/output/renderers/alert/model.py:291-295` | Feld `AlertMessage.corridor_events` samt Kommentar | a |
| `src/output/renderers/alert/render.py:24` | Import `CorridorEvent` | a |
| `src/output/renderers/alert/render.py:406-427` | `_corridor_where`, `_corridor_when` | a |
| `src/output/renderers/alert/render.py:446-484` | `_corridor_value_str`, `_corridor_label`, `_corridor_line`, `_sms_corridor_token` | a |
| `src/output/renderers/alert/render.py:1273`, `:1282-1287` | Betreff-Zweige (`not msg.corridor_events`-Bedingung vereinfachen, Korridor-Zweig streichen) | a |
| `src/output/renderers/alert/render.py:1424-1445` | `_render_email_corridor_only` | a |
| `src/output/renderers/alert/render.py:1457`, `:1459-1460` | E-Mail-Dispatch-Zweig | a |
| `src/output/renderers/alert/render.py:1548-1556`, `:1576-1577` | Korridor-Zeilen/-Zeilen im E-Mail-Mischpfad (Klartext und HTML) | a |
| `src/output/renderers/alert/render.py:1597`, `:1602-1605` | Telegram-Zweig | a |
| `src/output/renderers/alert/render.py:1643` | Korridor-Zeilen im Telegram-Mischpfad | a |
| `src/output/renderers/alert/render.py:1727-1746` | `_render_sms_corridor_only` | a |
| `src/output/renderers/alert/render.py:1814`, `:1816-1817`, `:1843`, `:1858` | SMS-Dispatch, Etappen-Praefix-Liste, Token-Liste | a |
| `src/services/alert_log.py:196-217` | `register_pairs_from_corridor_hits` (schreibt im Korridor-Pfad die Gewitterstufe als Zahl; einziger Aufrufer `resolve_corridor_summary_field`) | a |

Kommentar-Verweise ohne Logik, mitzupflegen: `render.py:88`, `:197`, `:205`, `:250`, `:545`; `model.py:213`.

Nicht entfernen (geteilt): `_stage_prefix` (`render.py:246`, auch von `official_alerts.py:2109`), `_hail_note_suffix` / `_sms_hail_suffix` (nutzen auch AlertEvent/OnsetShift-Pfade), `_hail_flag_for`, `_label`, `_code`, `_val`, `_is_level_metric`, `weather_change_detection._ALERT_METRIC_TO_SUMMARY_FIELD`, `weather_change_detection._peak_occurred_at`.

### (b) Tests, die nur den toten Pfad pruefen -> loeschen

| Datei:Zeile | Was | Kat. |
|---|---|---|
| `tests/tdd/test_corridor_threshold_evaluation.py` (312 Zeilen, 10 Tests) | ganze Datei | b |
| `tests/tdd/test_hagel_im_korridor_alarmtext.py` (161 Zeilen, 4 Tests) | ganze Datei (Kette `evaluate_corridor_thresholds` -> `to_alert_message(corridor_hits=)`) | b |
| `tests/tdd/test_alert_log_metrics.py:88-112` | `test_ac2_beide_korridor_namensraeume_liefern_dasselbe_register_paar` | b |
| `tests/tdd/test_alert_log_metric_values.py:436-459` (+ Import `:45`) | `test_ac24_korridor_treffer_traegt_wert_ohne_vorwert_und_ohne_schwelle` | b |
| `tests/tdd/test_alert_etappen_praefix_kurzform.py:412-451` (+ Import `:58`) | `test_ac4_corridor_alert_carries_stage_prefix` | b |
| `tests/tdd/test_alert_stufenwort.py:229-250` | `test_ac7_korridor_alarm_grenze_und_wert_beide_als_wort` | b |
| `tests/tdd/test_thunder_low_no_event_claim.py:419-451` | `test_corridor_alert_line_no_gewitter_word_for_pure_low` | b |
| `tests/tdd/test_alert_reference_timestamp.py:300-326` | `test_ac5_regression_korridor_only_footer_bleibt_unveraendert` | b |
| `tests/tdd/test_alert_location_measured_km.py:217-327` | Block "vierter Event-Typ": `_corridor_message`, `test_ac13_korridor_alarm_zeigt_nie_die_luftlinien_kilometer`, `test_ac1_korridor_alarm_zeigt_gemessene_km_spanne`, `test_ac15_korridor_projektion_traegt_die_segmentkennung` | b |
| `tests/tdd/test_alert_flag_propagation_snapshot.py:186-206` | `test_ac15_corridorevent_traegt_das_flag_aus_der_echten_projektion` | b |

### (c) Tests, die Korridor-Objekte nur nebenbei verwenden -> anpassen

| Datei:Zeile | Anpassung | Kat. |
|---|---|---|
| `tests/tdd/test_alert_location_measured_km.py:330-390` | `test_ortsangabe_ohne_segmentkennung_ist_ueber_alle_event_typen_gleich`: `CorridorEvent`-Zweig (`:362-366`, `:376-379`) streichen, `AlertEvent` und `OnsetShiftEvent` bleiben | c |
| `tests/tdd/test_ascii_folding.py:208-248` | `test_radar_alert_trip_short_survives_double_truncation`: Traeger ist `CorridorEvent` + `_render_sms_corridor_only`; auf verbleibenden Kopf-Traeger umziehen oder loeschen (siehe offene Frage 1) | c |
| `tests/tdd/test_cape_not_selectable.py:409-428` | `TestCorridorGoesInertForCape` ruft `resolve_corridor_summary_field`; auf den Mail-Markierungs-Pfad umziehen oder loeschen (siehe offene Frage 2) | c |
| `tests/tdd/test_alert_sms_onset_zeit_token_kappung.py:11` | nur Kommentar "Muster `_render_sms_corridor_only`" -> Kommentar anpassen | c |
| `tests/tdd/test_channel_metric_matrix.py:1842` | nur Kommentar `_sms_corridor_token` -> Kommentar anpassen | c |
| `tests/tdd/test_alert_etappen_praefix_kurzform.py:8`, `:20`, `:33` | Modul-Docstring nennt `CorridorEvent`/`to_corridor_events` -> Docstring anpassen | c |
| `tests/tdd/test_alert_flag_propagation_snapshot.py:17` | Docstring nennt `CorridorEvent.km_measured` -> anpassen | c |
| `tests/tdd/test_alert_location_vocabulary.py:23` | Docstring nennt `CorridorHit.segment_id` -> anpassen | c |
| `tests/tdd/test_trip_mail_corridor_mark.py:322` | Docstring nennt `resolve_corridor_summary_field()`; Test selbst prueft Mail-Markierung -> Docstring-Bezug auf `summary_field_for` umstellen, Verhalten unveraendert | c |

### (d) Bleibt (Persistenz, Editor, Mail-Markierung, Gegenprobe zu #1460)

| Datei | Warum | Kat. |
|---|---|---|
| `src/app/models.py` (`Corridor`), `src/app/trip.py`, `src/app/loader.py:224`, `:652` (`_corridor_from_dict`) | Datenmodell/Persistenz, nicht anfassen | d |
| `internal/model/trip.go`, `internal/model/compare_preset.go`, `internal/store/trip.go`, `internal/store/compare_preset.go`, `internal/handler/trip.go` | Go-Persistenz/Handler fuer `corridors`, nicht anfassen | d |
| `src/services/corridor_match.py`, `src/output/renderers/email/corridor_mark.py`, `src/output/renderers/email/html.py`, `compare_html.py`, `trip_report.py`, `comparison.py` | Mail-Markierung "im Wertebereich" (kein Alarm) | d |
| `src/services/report_config_resolver.py:247-281` | liest `corridors` ueber `_corridor_from_dict` | d |
| `frontend/src/lib/components/shared/corridor-editor/**`, `compare/**`, `trip-new/**` | Wertebereiche-Editor | d |
| `tests/tdd/test_corridor_no_longer_triggers_alerts.py` | Gegenprobe #1460: Trip mit `notify=True`-Korridor loest keinen Alarm aus; importiert nichts aus dem Modul | d |
| `tests/tdd/test_corridor_persistence.py`, `test_corridor_migration.py`, `test_null_list_fields.py`, `test_corridor_match.py`, `test_trip_mail_corridor_mark.py`, `test_compare_mail_corridor_mark.py`; Go: `internal/handler/trip_corridors_write_test.go`, `internal/model/corridor_test.go` | Persistenz-/Roundtrip-/Markierungs-Tests | d |
| `scripts/migrate_1231_corridors.py` und zugehoerige Migrationstests | Datenmigration | d |

### Produktiv-Befuellung von `corridor_hits` (gemessen)

Kein Produktivpfad befuellt `corridor_hits`. `TripAlertService.check_and_send_alerts` ruft `_send_alert` (`trip_alert.py:864`) ohne `corridor_hits`; der Default `corridor_hits or []` bleibt dort immer leer. Die einzigen Aufrufer, die `corridor_hits=` setzen, sind Tests (`test_alert_etappen_praefix_kurzform.py:436`, `test_hagel_im_korridor_alarmtext.py:58`). Der Compare-/Radar-/Official-Pfad erzeugt `AlertMessage` (`project.py:532`, `:697`, `radar_alert_service.py:76`, `notification_service.py:1661`, `validator_render_service.py:196`) nie mit `corridor_events`.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/renderers/alert/render.py` | module | Alarm-Renderer; nach Rueckbau nur noch `AlertEvent`/`OnsetEvent`/`OnsetShiftEvent`-Pfade |
| `src/services/weather_change_detection.py` | module | behaelt `_ALERT_METRIC_TO_SUMMARY_FIELD`, `_peak_occurred_at` (Aenderungs-Waechter) |
| `src/app/metric_catalog.py` (`summary_field_for`) | module | bleibt; wurde nur vom entfernten Modul zusaetzlich genutzt |
| `src/services/alert_log.py` | module | bleibt bis auf `register_pairs_from_corridor_hits` |
| `src/app/models.py`, `src/app/loader.py`, `internal/model`, `internal/store` | module | Persistenz `corridors`, unveraendert (#102) |
| `tests/tdd/test_corridor_no_longer_triggers_alerts.py` | test | Gegenprobe #1460, bleibt gruen |
| `tests/tdd/test_corridor_persistence.py` | test | Roundtrip `corridors`, bleibt gruen |

## Implementation Details

1. Vor dem ersten Streichen: Referenz-Ausgaben aufzeichnen. Ein Trip mit gespeicherten `corridors` (`notify=True`, `mark=True`, verschiedene Metriken) und realen `WeatherChange`-Eintraegen laeuft durch die echten Renderer `render_subject`, `render_email` (HTML + Klartext), `render_telegram`, `render_sms` sowie den Premium-SMS-Text (derselbe SMS-Text, Kanal `premium_sms`). Die Ausgaben werden als versionierte Fixtures unter `tests/fixtures/alert_corridor_removal_2230/` abgelegt (aufgezeichnet VOR dem Rueckbau, nie nachtraeglich regeneriert).
2. Reihenfolge Streichen von aussen nach innen: Aufrufer-Parameter (`trip_alert.py`, `notification_service.py`) -> `project.py` -> `render.py`-Zweige -> `model.py` -> `alert_log.py` -> Modul `corridor_threshold.py`. Nach jedem Schritt `uv run pytest <benannte Testdateien>`.
3. `if not msg.events and not msg.corridor_events and msg.onset_shift_events` wird zu `if not msg.events and msg.onset_shift_events`; Zweige "nur Korridor" entfallen. Bei leerem `corridor_events` ist das Ergebnis heute identisch, daher keine Verhaltensaenderung fuer Bestandsnachrichten.
4. Tests nach Inventar loeschen bzw. anpassen. Keine neuen Mocks; Gleichheits-Tests nutzen die echten Renderer und die aufgezeichneten Fixtures.
5. `loader.py`, `models.py`, `trip.py`, `internal/**` werden nicht editiert (Schema-Backup-Hook feuert nicht).

## Expected Behavior

- **Input:** unveraendert: `WeatherChange`-Listen, offizielle Warnungen, Radar-/Onset-Ereignisse; ein Trip mit gespeicherten `corridors`.
- **Output:** Alarm-Mail (Betreff, HTML, Klartext), Telegram, SMS und Premium-SMS sind fuer jede Eingabe, die vorher ohne `corridor_hits` lief (also jede Produktiv-Eingabe), byte-gleich zum Stand vor dem Rueckbau.
- **Side effects:** keine. `corridors` im Trip-JSON wird weiter geladen, in Mail-Markierung und Editor genutzt und beim Speichern unveraendert zurueckgeschrieben. Es verschwindet ausschliesslich Code, der in Produktion nie lief.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN eine aufgezeichnete Referenz-Alarmnachricht eines Trips mit gespeicherten `corridors` WHEN Subject/E-Mail/Telegram/SMS/Premium-SMS gerendert werden THEN sind alle Ausgaben byte-gleich zu den Fixtures (laeuft vor dem Rueckbau gruen, nach dem Rueckbau gruen).
- [ ] Test 3: GIVEN ein Trip-JSON mit `corridors` inkl. unbekanntem Zusatzfeld WHEN er geladen und gespeichert wird THEN ist das Feld `corridors` im Ergebnis byte-gleich (bestehend: `test_corridor_persistence.py`, `trip_corridors_write_test.go`).
- [ ] Test 4: GIVEN der Rueckbau WHEN `services.corridor_threshold`, `CorridorHit`, `CorridorEvent`, `register_pairs_from_corridor_hits` und der Parameter `corridor_hits` importiert/aufgerufen werden THEN schlaegt das mit `ImportError` bzw. `TypeError` fehl (Nachweis ueber `inspect.signature` und echten Import, kein Dateiinhalt-Check).
- [ ] Test 5: GIVEN ein Trip mit `notify=True`-Korridor, dessen Wert die Grenze reisst WHEN `check_and_send_alerts` laeuft THEN wird kein Alarm versendet (bestehend: `test_corridor_no_longer_triggers_alerts.py`).

## Acceptance Criteria

- **AC-1:** Given der Repo-Stand nach dem Rueckbau / When `src/services/corridor_threshold.py` importiert wird oder `corridor_hits` an `TripAlertService._send_alert`, `NotificationService.send_deviation_alert` oder `to_alert_message` uebergeben wird / Then schlagen Import (`ImportError`) und Aufruf (`TypeError`) fehl, und weder `CorridorHit`, `CorridorEvent`, `to_corridor_events` noch `register_pairs_from_corridor_hits` existieren mehr.
  - Test: neue Datei `tests/tdd/test_alert_ausgabe_nach_korridor_rueckbau.py` prueft per echtem Import und `inspect.signature`, dass Modul, Klassen und Parameter weg sind.

- **AC-2:** Given der Rueckbau / When `alert/render.py` und `alert/model.py` betrachtet werden / Then enthalten sie keine Korridor-Renderer mehr (`_render_email_corridor_only`, `_render_sms_corridor_only`, `_corridor_line`, `_corridor_label`, `_corridor_where`, `_corridor_when`, `_corridor_value_str`, `_sms_corridor_token`), und `AlertMessage` hat kein Feld `corridor_events`; die gemeinsam genutzten Helfer `_stage_prefix` und die Hagel-Suffix-Helfer bleiben.
  - Test: derselbe neue Test prueft per `hasattr`/`dataclasses.fields` auf dem echten Modul; die geteilten Helfer werden ueber die Alarm-Ausgaben aus AC-3 mitbewacht.

- **AC-3:** Given ein Trip mit gespeicherten `corridors` (`notify=True`, `mark=True`) und realen Wetteraenderungen / When Alarm-Betreff, E-Mail (HTML und Klartext), Telegram, SMS und Premium-SMS gerendert werden / Then sind alle Ausgaben byte-gleich zu den vor dem Rueckbau aufgezeichneten Fixtures unter `tests/fixtures/alert_corridor_removal_2230/`.
  - Test: neue Datei `tests/tdd/test_alert_ausgabe_nach_korridor_rueckbau.py` rendert mit den echten Renderern und vergleicht mit den Fixtures. Zusaetzlich bleiben gruen: `tests/tdd/test_alert_stufenwort.py`, `test_alert_sms_delta_notation.py`, `test_alert_sms_segment_head.py`, `test_alert_etappen_praefix_kurzform.py`, `test_alert_telegram_stand_zeile.py`, `test_telegram_kurzstil_trip_alert.py`, `test_alert_location_measured_km.py`, `tests/unit/test_alert_channel_premium_sms.py`, `tests/unit/test_official_alert_output_unchanged.py`.

- **AC-4:** _gestrichen (PO-Freigabe 2026-10-08): kein geänderter Datenweg, Ausgabe-Gleichheit sichert AC-3._
  - Test: in `tests/tdd/test_alert_ausgabe_nach_korridor_rueckbau.py` mit lokalen Transport-Stubs (`mail_sink`, Telegram-/SevenIO-Stub wie in `test_alert_etappen_praefix_kurzform.py`), Nutzer ueber `nutzer_mit_tier`; bestehend zusaetzlich `tests/tdd/test_alert_tenancy_two_users.py`.

- **AC-5:** Given gespeicherte Trips (und Orts-Vergleiche) mit `corridors`-Eintraegen inklusive unbekannter Zusatzfelder / When sie nach dem Rueckbau geladen und ueber Python-Loader und Go-Store wieder gespeichert werden / Then ist das Feld `corridors` im gespeicherten JSON unveraendert (Read-Modify-Write ohne Feldverlust), und `src/app/models.py`, `src/app/trip.py`, `src/app/loader.py`, `internal/model/*`, `internal/store/*` sind im Diff nicht enthalten.
  - Test: bestehend `tests/tdd/test_corridor_persistence.py`, `tests/tdd/test_corridor_migration.py`, `tests/tdd/test_null_list_fields.py`, `internal/handler/trip_corridors_write_test.go`, `internal/model/corridor_test.go` bleiben gruen; der Diff-Nachweis erfolgt im Adversary-Schritt per `git diff --stat`.

- **AC-6:** Given ein Trip mit `notify=True`-Korridor, dessen Grenze gerissen ist / When der Alarm-Lauf `check_and_send_alerts` laeuft / Then wird kein Alarm erzeugt (Verhalten aus #1460 unveraendert), und die Mail-Markierung "im Wertebereich" im Trip-Briefing und im Orts-Vergleich rendert unveraendert.
  - Test: bestehend `tests/tdd/test_corridor_no_longer_triggers_alerts.py`, `tests/tdd/test_trip_mail_corridor_mark.py`, `tests/tdd/test_compare_mail_corridor_mark.py`, `tests/tdd/test_corridor_match.py` bleiben gruen.

- **AC-7:** Given der Rueckbau / When der Kern-Testlauf ueber die benannten Alarm-, Korridor- und Renderer-Testdateien laeuft / Then sind alle Tests gruen, `tests/tdd/test_corridor_threshold_evaluation.py` und `tests/tdd/test_hagel_im_korridor_alarmtext.py` sind geloescht, und kein verbleibender Test importiert `services.corridor_threshold`, `CorridorHit` oder `CorridorEvent`.
  - Test: `uv run pytest` mit benannten Dateien; zusaetzlich `uv run pytest --collect-only` ueber `tests/tdd` ohne Importfehler.

## Known Limitations

- Historische Specs und Kontext-Dokumente (`docs/specs/modules/feat_1444_*`, `rework_1460_*`, `docs/context/*`) nennen das Modul weiterhin; sie sind Archiv und werden nicht umgeschrieben.
- Die Byte-Gleichheit gilt fuer alle Eingaben ohne `corridor_hits`, also fuer die gesamte Produktion. Eine kuenftige Wiedereinfuehrung eines Grenzwert-Alarms muesste neu spezifiziert werden (PO-Entscheid 2026-09-08).
- Der Prod-Deploy ist ohne sichtbare Nutzeraenderung; Staging-Validierung = HTTP-Smoke plus ein Test-Alarm an den Test-Trip mit IMAP-Pruefung.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue
- **Rationale:** Die Entfernung setzt den PO-Entscheid vom 2026-09-08 um und kehrt keine dokumentierte ADR-Entscheidung still um. ADR-0013 (eigener Render-Vertrag fuer Schwellen-Treffer) und ADR-0040 (nutzergesetzte Absolut-Schwellen) betreffen den hier entfernten toten Pfad; ihr Index-Eintrag bleibt, die Spec nennt den Rueckbau. Ob ADR-0013 einen Hinweis "Teil entfernt durch #2230" bekommt, entscheidet der Developer anhand von `tests/test_adr_index_drift.py`.

## Changelog

- 2026-10-08: Initial spec created (Issue #2230)
