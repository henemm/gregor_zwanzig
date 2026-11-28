# Context: feat-2799-ampel-weitere (Issue #2799, Epic #2791 Scheibe S7)

## Request Summary

Ampel aus der Vorlage (ADR-0106 Punkt 5/6) auf weitere Metriken ausdehnen: Sonnenstunden (nur unten, umgekehrt),
Bewölkung, tiefe Wolken, Taupunkt (nur oben; Bewölkung/Taupunkt Vorboten), Nullgrad- und Schneefallgrenze
(beidseitig, **relativ** zur höchsten Stelle der Etappe bzw. Ortshöhe), Schneehöhe (beidseitig je Vorlage).
Reine Anzeige bleiben Luftfeuchte, Luftdruck, Windrichtung, Niederschlagsart, mittlere/hohe Wolken.
Nullgrad-/Schneefallgrenze und Schneehöhe werden über den S2-Stufenwechsel alarmfähig (ersetzt D4-Δ),
Vorboten nie (ADR-0010). Alle Renderer, alle vier Kanäle, Metrik-Zeilen im Reiter Wetter („m rel.“).

Offene Punkte aus Issue-Kommentaren:
- PO 2026-11-14: `cloud_mid` erneut prüfen (Höhenbänder der Provider mit Quelle, relative Bewertung zur Route
  für `cloud_mid`/`cloud_low`?), Empfehlung je Vorlage vorlegen; Abweichung von ADR-0106 P5 ⇒ ADR-Nachtrag.
- Aus #2222: Reste der alten Δ-Logik abbauen (#961-Backfill `alert_preset.py:303-380`,
  `deviation_alert_engine.py:161-178 _has_active_alert_metric`, `trip_alert.py:694/1793-1823`,
  Gate `trip_alert.py:713-718` + Spiegel `hubUebersichtModell.ts:166-187`).
- S2-Spec `feat_2793_s2_alarm_stufenwechsel.md:90,237` nennt auch `temperature_night` als „ab S7 über Ampel“.

## Kernbefund

Die Vorlagen-Daten aller Zielmetriken stehen schon in `src/app/ampel_templates.py` (`_ZEILEN`, Kopf l.14:
„erst in S7 gelesen“), Ratsche gegen die Doku: `tests/tdd/test_ampel_vorlagen_gleich_einstellungen_doku.py`.
Der zentrale Engpass ist die Allow-List `AMPEL_LESER` in `src/app/ampel.py:~300`; `schwellen_aus_ampel()`
(~332) liefert `{}` für alles außerhalb → kein Renderer, kein Alarm färbt. **Relative Bewertung existiert
nirgends**; keine Schwellenfunktion nimmt eine Bezugshöhe.

## Related Files

| Bereich | Datei:Zeile |
|---|---|
| Stammdaten | `src/app/ampel_templates.py` (`_ZEILEN` 25ff, `_vorlage` ~176) |
| Auflösung/Gate | `src/app/ampel.py` (`validate_ampel` ~126, `_verschmelzen` ~211, `resolve_ampel` ~228, `AMPEL_LESER` ~300, `AMPEL_ABGELEITET`, `hat_ampel`, `schwellen_aus_ampel` ~332, `_stufe` ~355) |
| Katalog | `src/app/metric_catalog.py` (dewpoint 359, snowfall_limit 556, cloud_total 585, cloud_low 605, sunshine 679, freezing_level 734, snow_depth 749; `AMPEL_METRIC_IDS` 1321; `_REITER_WETTER` 1420-1471, Seiten/alertable schon gesetzt; `reiter_wetter_eigenschaften` 1474) |
| Format | `src/output/metric_format.py:147 severity_for`, l.225 Kommentar „freezing_level strukturell trip-relativ“ |
| Trip-Mail | `src/output/renderers/email/html.py` 236-257, 658, 1167; `email/helpers.py` 710/727, 1029-1080, 1404, 1530-1550 + 1822-1843 (`_PILL_NEUTRAL_TONE` cloud_low/freezing_level/dewpoint), 1577-1603, 1743; `email/plain.py:194`, `compact.py:224`, `outlook.py:463` |
| Orte-Mail | `email/compare_html.py` 123-165 (`_sev_*`), 355-378 (Übersicht freezing_level/snow_depth ohne sev), 492, 777; `comparison.py` 225/830/1165; `compact_compare.py:222` |
| Telegram | `src/output/renderers/narrow.py` 510, 623, 817 |
| SMS/Premium | `src/output/tokens/builder.py` (`AMPEL_METRIK_JE_KUERZEL` 178 nur R/PR/W/G/UV; `INVERS_MIN_AMPEL_METRIK` 271 „FZ hat keinen“; FZ 539; SU/HP 573); `orte_sms.py:57-72`, `sms_trip.py:342-552` |
| Höhen | `src/app/trip.py` (`Waypoint.elevation_m` 75, `Stage.highest_waypoint` 124, `Trip.highest_point` 280); `trip_report_scheduler.py:1355 max_elev`; `models.py:428 TripSegment` (kein Etappen-Höchstpunkt), 461-500 `SegmentWeatherSummary`; `app/user.py:60 SavedLocation.elevation_m`; `compare_alert.py:758` |
| Alarm S2 | `src/services/ampel_alarm.py` (`AMPEL_FELDER` ~57 ohne freezing/snowfall/snow_depth, `_sprung`, `alarmfaehige_felder`, `_farbe` ohne Höhe); `trip_alert.py:216-229 ampel_alarmquelle_aktiv` |
| Alarm D4 alt | `deviation_alert_engine.py:33 D4_ALERT_METRICS`, ~218 `_select_d4_detector` („bis S7“); `alert_preset.py:19, 60-64`; `weather_change_detection.py:96-118, 618-647` |
| Alarmtexte | `services/alert_channel_texts.py:75/90`; `trip_command_processor.py:577-593, 1935` |
| Frontend | `organisms/wetter-tab/MetrikZeile.svelte` (71-74), `AmpelLeiste.svelte`, `GrenzenEditor.svelte`; `shared/wetter-tab/ampelModell.ts` (`grenzEinheit`, `HINWEIS_IDS` ~201), `ampelLeiste.ts`; i18n `frontend/src/lib/i18n/messages/{de,en}/wetter.json` 66-68 |
| API | `api/routers/config.py:110-160` (`threshold_unit = m.unit`) |
| Go | `internal/model/metric_preset.go:~62` (Ampel map), `internal/handler/ampel.go validateAmpelIm` |
| Provider Wolken | `src/providers/openmeteo.py` 268, 460-462, 1011-1013; `geosphere.py` 560-626, 715; `src/app/cloud_cover.py` (`HOCHLAGE_SCHWELLE_M=2500`, ADR-0122) |
| Validatoren | `.claude/hooks/briefing_mail_validator.py:1138 _AMPEL_SPALTEN`; `docs/reference/mail_validators.md:405-418` |

## Existing Patterns

- Vorlagen-Ampel S1: Tupel (rot, orange, gelb) unten / (gelb, orange, rot) oben, `alarm_ab`.
- Umgekehrte Ampel (nur unten) existiert für Sicht (VS) und Gefühlte (TF) im Token-Builder.
- Abgeleitete Ampel `AMPEL_ABGELEITET` (Windrichtung, #3228) als Vorbild für „Ampel mit Zusatzeingabe“.
- `HOCHLAGE_SCHWELLE_M` (ADR-0122) ist bisher die einzige höhenabhängige Wolkenlogik.

## Dependencies / Dependents

- Voraussetzungen S1 (#2792) und S3a (#2794) geschlossen. S2 (#2793) liefert die Stufenwechsel-Engine.
- Dependents: alle Renderer/Kanäle, Mail-Validatoren (Trip + Orte), Frontend Reiter Wetter, Alarm-Pipeline.

## Existing Specs / ADRs

- ADR-0106 (P5 l.28, P6 l.29, D4 l.43), ADR-0010 (Vorboten), ADR-0019 (Nullgradgrenze Alarm-Metrik), ADR-0122 (Hochlage).
- `docs/context/einstellungen_neu.md` §4.2 (l.254-264), §4.4 (l.277-299), Vorlagen-Tabellen l.302-478.
- Specs: `feat_2792_s1_profil_ampel.md`, `feat_2793_s2_alarm_stufenwechsel.md`, `feat_2794_s3a_teil3_wetter.md`,
  `rework_2988_ampel_ableitung.md`, `ampel_schwellen_katalog.md`, `ampel_schwellen_renderer.md`.

## Tests

`tests/tdd/test_ampel_modell_und_aufloesung.py`, `test_ampel_vorlagen_gleich_einstellungen_doku.py`,
`test_profil_ampel_kette.py`, `test_alarm_folgt_ampel_stufenwechsel.py`, `test_alarm_ampel_*`, `test_s1c4b_*`,
`test_compare_katalog_schwellen.py`, `test_einstellung_gleich_mail_validatoren.py`; Go `internal/handler/ampel_*_test.go`;
Frontend `shared/wetter-tab/__tests__/ampelModell.test.ts`, e2e `s3a2794-teil3-*.spec.ts`.

## Risks

1. **Umfang:** acht Metriken × fünf Renderer × vier Kanäle + Alarm + Frontend + Altlasten-Abbau überschreitet
   eine Liefereinheit deutlich ⇒ in der Analyse in Teil-Scheiben schneiden (Vorbild S1c4b/S3a-Teile).
2. **Relative Bezugshöhe** muss bis in jeden Renderer und die Alarm-Engine durchgereicht werden; Segmente
   kennen den Etappen-Höchstpunkt nicht. Ohne Höhe: keine Färbung + Hinweis (nie falsche Farbe).
3. **Alarm-Umstellung D4 → Stufenwechsel** für Nullgradgrenze; Snow_line-#961-OR-Politik; Bestands-Trips mit
   `alert_on_changes=False`.
4. **cloud_mid-Frage** kann ADR-Nachtrag erfordern (PO-Entscheidung).
5. Mail-Validatoren/Renderer-Commit-Gate müssen mitgezogen werden.
6. Zwei Ampel-Listen (`AMPEL_LESER` vs. `AMPEL_METRIC_IDS`) — Drift-Gefahr.

## Analyse-Rohbefunde (Phase 2, Agenten)

### Nicht-relative Metriken (sunshine, cloud_total, cloud_low, dewpoint, snow_depth)
- `AMPEL_LESER` (`src/app/ampel.py:291-294`) nötig, nicht hinreichend. Zusätzliche Sperrlisten:
  - Trip-Pillen `email/helpers.py:1449 _PILL_NEUTRAL_TONE` (genutzt 1812-1843) → auf `ampel_stage_tone`/`_extreme_ampel_tone` wie Temperatur.
  - Tabellenzellen `helpers.py:1404 _AMPEL_CAPABLE_METRIC_IDS = AMPEL_METRIC_IDS` (`metric_catalog.py:1321-1323`, verlangt `display_thresholds`) → zweite Liste, aus `AMPEL_LESER` ableiten (Drift beseitigen).
  - Orte-Mail Tagesübersicht `compare_html.py:355-400` braucht `"sev"` je Zeile (Muster `_sev_*` 123-165); Stundenzeilen (`:492 hat_ampel`) färben automatisch.
  - Telegram `narrow.py:510-516, 623` färbt automatisch über `hat_ampel`.
  - SMS `tokens/builder.py:178-183 AMPEL_METRIK_JE_KUERZEL` um CT/CL/DP(/SD) ergänzen; SU (`:573-580 render_int`) hat keinen Ampel-Pfad; Orte-SMS `_TAGESWERT_RID` (`orte_sms.py:53-54`).
  - Validator `.claude/hooks/briefing_mail_validator.py:1138 _AMPEL_SPALTEN`.
  - Tests, die kippen: `tests/tdd/test_renderer_katalog_schwellen.py:299-312` (sunshine/dewpoint neutral), `tests/helpers/metrik_listen_scan.py:298-300, 381-384`.
- „nur unten“ funktioniert schon (Sicht als Vorbild, `_lt`-Schlüssel, `metric_format.py:160-205`).
- Sonnenstunden: Grenzen 1/3 h sind Tagessumme; Pille summiert Tagesstunden (`helpers.py:~1840 calculate_sunny_hours`), Stundenzelle ist ein anderer Wert ⇒ Ampel nur auf Tageswert anwenden.

### Relative Metriken (freezing_level, snowfall_limit)
- Trip: `trip_report_scheduler.py:1346-1371 _compute_stage_stats` liefert `max_elevation_m` (höchster Wegpunkt der Etappe), über `stage_stats` bis `format_email` (`renderers/trip_report.py:70-100`). Telegram `render_telegram_bubbles` (`narrow.py:770-790`) bekommt `trip`; SMS `sms_trip.py:579` (Durchreichung ungeprüft). Orte: `SavedLocation.elevation_m` (`app/user.py:60`), `LocationResult` (`:119`).
- Vorschlag: reine Funktion `ampel_mit_bezug(ampel, bezug_m)` in `app/ampel.py` — rechnet die relativen Grenzen in absolute (`bezug + offset`), einmal je Render-Einstieg und je Alarm-Segment; ohne `bezug_m` werden die beiden Metriken entfernt (keine Farbe + Hinweis). Alle übrigen Aufrufer bleiben unverändert.

### Alarm
- `src/services/ampel_alarm.py:59-75 AMPEL_FELDER` + `freezing_level_m`, `snowfall_limit_m`, `snow_depth_cm` (`models.py:487-493`); `AmpelFeld.seite` kennt nur oben/unten/stufe → „beidseitig“ nötig (`_farbe` 114-127, `_art` 130-140); Bezug je Segment über Segment→Etappe-Karte aus `trip.stages` in TripAlertService.
- D4-Rückbau: `deviation_alert_engine.py:33-35 D4_ALERT_METRICS` (freezing_level, snow_line), `_select_d4_detector` 216-229, `evaluate` 333/338; `_has_active_alert_metric` 161-178; `alert_preset.py:303-380` #961-Backfill; `trip_alert.py:694, 713-718, 1793-1823`; `_PRESET_TABLE`-Zeile `alert_preset.py:60-64` bleibt (liest `_sprung`); `loader.py:849` Migration snow_line→freezing_level bleibt.

### Specs / ADRs
- S2-Spec `feat_2793_s2_alarm_stufenwechsel.md:23, 90, 237`: `temperature_night`, `snow_depth`, `snowfall_limit` alarmieren über die Ampel erst mit S7. S1-Spec l.160 und S3a-Spec l.65 nennen ebenfalls „Nacht“ für S7. `temperature_night` hat Vorlagen-Zeilen in allen 7 Vorlagen (`ampel_templates.py:27,49,…`). Kontext-Doku l.612 nennt sie nicht ⇒ **in S7 aufnehmen** (drei freigegebene Specs verschieben sie hierher).
- ADR-0019: genau eine Alert-Metrik `freezing_level`; „eigenständige Schneefallgrenze-Alert-Metrik bräuchte neue Spezifikation“. ADR-0010 l.37 zählt Schneefallgrenze als Alert-Metrik. ADR-0106 P6 + Vorlagen (`alarm_ab` Orange für snowfall_limit) + S7-Issue sehen Schneefallgrenze alarmfähig ⇒ S7-Spec ist diese „neue Spezifikation“; ADR-0019-Nachtrag nötig.
- Kein ADR-Text zu „ohne Höhe keine Farbe“ — steht nur im Issue (Umfang Nr. 1).
- Glossar: Nullgradgrenze fehlt; „über höchster Stelle“, „m rel.“ fehlen.
- Schnitt-Konvention Epic: eine Gesamt-Spec mit Lieferplan + Teil-Specs je Teil-PR (S3a) bzw. Nachträge in einer Spec (S1).

### Wolkenschichten (PO-Frage cloud_mid)
- Open-Meteo (https://open-meteo.com/en/docs, auch /dwd-api, /ecmwf-api): „Low level clouds and fog up to 3 km altitude“, „Mid level clouds from 3 to 8 km altitude“, „High level clouds from 8 km altitude“. ECMWF: tief = rel. Feuchte 1000/925/850 hPa, mittel = 700/500 hPa, hoch = 300/250/200 hPa. Bezug Boden vs. Meer nicht angegeben; Druckflächen-Tabellen sind „above sea level“, 700 hPa ≈ 3 km ⇒ vermutlich über Meer (Schluss, nicht Quelle).
- Folgerung: Mittlere Wolken beginnen bei ~3 km über Meer, nicht bei 2000 m; eine Etappe bis 3000 m steckt bei viel mittlerer Bewölkung praktisch nie drin, Gipfel ab ~3000 m schon. Tiefe Wolken (0–3 km) sind das Signal „Gipfel in Wolken“ für fast alle Routen; ab 2500 m Standorthöhe zählt die Normalisierung tiefe Wolken bereits nicht (ADR-0122).

## Analysis

**Type:** Feature (Epic #2791, Scheibe S7). Track voller Prozess, Score 5.

### Technical Approach (Variante A, empfohlen)

| Variante | Dateien | LoC | Paritäts-Risiko |
|---|---|---|---|
| **A: `ampel_mit_bezug(ampel, bezug_m)` einmal je Render-Einstieg/Alarm-Segment** | ~8 | ~250 | niedrig |
| B: Höhe in `severity_for`/jede Schwellenfunktion | ~25 | ~600 | hoch |
| C: absolute Grenzen je Etappe speichern | Schema | ~400 | mittel, falsch für Orte |

- Reine Funktion in `src/app/ampel.py`: rechnet die relativ gespeicherten Grenzen von `freezing_level`/`snowfall_limit`
  in absolute (`bezug + offset`); ohne Bezugshöhe entfernt sie die beiden Metriken ⇒ `hat_ampel` False ⇒ alle
  vier Kanäle neutral (Parität per Konstruktion). Hinweis „keine Höhe“ wird an EINER Stelle erzeugt.
- Bezugshöhe: Trip = `max_elevation_m` der Etappe (`_compute_stage_stats`), Orte = `SavedLocation.elevation_m`;
  Helper `bezug_fuer(...)` für beide.
- `snow_depth` bleibt absolut (cm, je Vorlage). Sonnenstunden nur auf den Tageswert (Stundenzelle ist anderer Wert).
- Zweite Liste `AMPEL_METRIC_IDS`/`_AMPEL_CAPABLE_METRIC_IDS`, `_PILL_NEUTRAL_TONE`, `AMPEL_METRIK_JE_KUERZEL`,
  `_AMPEL_SPALTEN` werden aus `AMPEL_LESER` abgeleitet (Drift beseitigen).
- `temperature_night` wird aufgenommen (S1/S2/S3a-Specs verschieben sie nach S7): heute nicht gefärbt, eigener
  Leser + eigenes Alarmfeld (nicht `temp_min_c`).
- Alarm: `AmpelFeld` bekommt Seite „beidseitig“; Felder freezing_level_m, snowfall_limit_m, snow_depth_cm,
  Nacht-Tiefsttemperatur; Segment→Etappe-Bezugskarte in TripAlertService; Segment ohne Höhe ⇒ kein Alarm
  für die relative Metrik (still, getestet). D4 für freezing_level wird stillgelegt.

### Lieferplan (Teil-PRs, je ≤5 Dateien / ≤250 LoC Produktivcode)

| Teil | Inhalt | Risiko |
|---|---|---|
| S7a1 | Vorbau ohne sichtbare Änderung: Ampel-Listen aus `AMPEL_LESER` abgeleitet (Pillen, Tabellenzellen, Orte-Übersicht-sev generisch, SMS-Kürzelkarte, Validator-Spalten) | mittel |
| S7a2 | Aktivierung Bewölkung, tiefe Wolken, Taupunkt, Sonnenstunden (Tageswert) in allen vier Kanälen + Validator-Fälle, Ratschen-Tests | hoch (Mail) |
| S7a3 | Nacht-Tiefsttemperatur färben (alle Kanäle) | mittel |
| S7b1 | `ampel_mit_bezug` + `bezug_fuer` + Durchreichung Trip/Orte zu allen Renderern, noch nicht aktiv | mittel |
| S7b2 | Aktivierung Nullgrad-/Schneefallgrenze relativ in allen Kanälen, Hinweis ohne Höhe, Anzeigewert (PO-Entscheid), Validator | hoch |
| S7c1 | Alarm Nullgrad-/Schneefallgrenze per Stufenwechsel, D4 freezing_level aus | mittel-hoch |
| S7c2 | Alarm Schneehöhe + Nacht-Tiefsttemperatur | mittel |
| S7d | Abbau Δ-Reste #2222 (#961-Backfill, `_has_active_alert_metric`, `_detect_all_changes`, Gate + Spiegel `hubUebersichtModell.ts`) | mittel |
| S7e | Reiter Wetter: Einheit „m rel.“, Hinweis ohne Höhe, i18n de/en | niedrig |
| S7f | Glossar (Nullgradgrenze, „über höchster Stelle“, „m rel.“), ADR-0019-Nachtrag (Schneefallgrenze alarmfähig) | keins |

Reihenfolge: S7f-ADR-Nachtrag vor S7c1; Mail-Teile (a1, a2, a3, b2) mit Validator im Umfang.
Spec-Struktur nach Epic-Konvention (S3a): eine Gesamt-Spec mit Lieferplan + ACs; Teil-PRs referenzieren sie.

### Scope / Risk
Gesamt ~10 Teil-PRs, Kernpfad `ampel.py`, `ampel_alarm.py`, `email/helpers.py`, `tokens/builder.py`,
`compare_html.py`, `narrow.py`, `deviation_alert_engine.py`, `trip_alert.py`, Frontend `ampelModell.ts`/`MetrikZeile.svelte`.
Risiko gesamt hoch (alle Kanäle + Alarm), je Teil durch Vorbau/Aktivierung-Trennung beherrschbar.

### Befunde gegen den Plan
1. Sonnenstunden-Einheit: Grenzen sind Tagessumme ⇒ nur Tageswert färben.
2. Schneefallgrenze als Alert-Metrik widerspricht ADR-0019 ⇒ Nachtrag vor S7c1.
3. Fehlende Höhe auch im Alarm ⇒ kein Alarm, Test.
4. Ratsche `test_ampel_vorlagen_gleich_einstellungen_doku.py` und `test_renderer_katalog_schwellen.py:299-312` kippen in S7a2.

### Open Questions (PO)
1. **Mittlere Wolken** (PO-Hinweis 2026-11-14): Empfehlung reine Anzeige beibehalten — Schicht beginnt laut
   Open-Meteo/ECMWF bei ~3 km (700 hPa), nicht 2000 m; „Gipfel in Wolken“ trägt `cloud_low` (0–3 km);
   Provider liefern keine Wolkenuntergrenze ⇒ keine relative Bewertung möglich. Kein ADR-Nachtrag.
2. **Anzeigewert Nullgrad-/Schneefallgrenze:** Empfehlung relativ als Hauptwert („+250 m über höchster Stelle“),
   absolut in Klammern in E-Mail/Telegram, SMS/Premium kurz mit Vorzeichen (`FZ+250`). Alternative: Wert bleibt
   absolut, nur die Farbe ist relativ.
3. (technisch, selbst entschieden) Gate `alert_rules` in S7d: in deren Spec klären.

### PO-Entscheidungen (2026-11-28, AskUserQuestion)
1. Mittlere Wolken: **nur Anzeige** (kein ADR-Nachtrag); Wiedervorlage, falls ein Provider eine Wolkenuntergrenze liefert.
2. Anzeigewert Nullgrad-/Schneefallgrenze: **relativ als Hauptwert, absolut in Klammern** in E-Mail/Telegram
   („+250 m über höchster Stelle (2650 m)“), SMS/Premium kurz mit Vorzeichen (`FZ+250`).
