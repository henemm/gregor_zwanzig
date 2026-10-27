# Context: fix-2480-radar-alle-messpunkte

## Request Summary
Issue #2480 (Herkunft #2261 Teil A Sz.8, Anforderung B-3 aus #2050): Der Trip-Radar-Alarm wertet die
Auslöseregel nur am ersten Messpunkt aus (Position zur Fenstermitte, #2017). Die Folgepunkte
(#2051 S2a, bis 6 Punkte im Abstand von 2 km) liefern nur die Nass-Zonen. Regen, der nur über Punkt 2+
liegt (2–10 km weiter auf der Strecke), löst deshalb keinen Alarm aus. Offen ist die Produktentscheidung,
die Auslöseregel auf alle Punkte auszudehnen.

## Related Files
| File | Relevance |
|------|-----------|
| src/services/trip_alert.py:1842-1930 | Punktbildung (`_punkte[0]` = Messpunkt), Abruf Punkt 0 (`result`), Zonen-Schleife Punkte 1..N |
| src/services/trip_alert.py:1936-2481 | Alles danach liest `result` (Punkt 0): `_menge_mm`, `_radar_urgency`, `radar_alert_due` (2074), `_onset_dt` (2082), Briefing-Vergleich (2101-2164), Label/Ende/Reichweite (2217-2250), `RadarAlertRequest` (2254-2313), Identitäts-Gate (2335-2374), Versand (2397), Capture-ID (2415), `record_nowcast_sent`/`record_event_identity` (2462-2481) |
| src/services/trip_alert.py:182-193 | `radar_alert_due(result, threshold)`: onset ≤ 55 Min oder `already_running` |
| src/services/trip_alert.py:196-209 | `_zonen_messwert`: behält das volle NowcastResult (None bei throttled/data_unavailable) |
| src/services/trip_alert.py:245-311 | `_radar_e1_fields` (E-1): Vorwarnzeit/Ereigniszeit/Quelle aus `result`; `measurement_point` = Segment-km, nicht Punkt-km |
| src/services/trip_segments.py:683-715 | `points_along_remaining_route` → `List[GPXPoint]` (lat/lon/elevation/`distance_from_start_km`, KEINE Zeit je Punkt); `RADAR_ZONE_POINT_SPACING_KM=2.0`, `RADAR_ZONE_MAX_POINTS=6` |
| src/services/rain_extent.py:47-131 | `derive_rain_zones`/`RainZone`: nass = `onset_minutes is not None`; keine Konvektion/Menge |
| src/services/compare_radar_alert.py:449-509 | `_detect_triggered_locations`: JEDER Ort kann auslösen; Bündelung, `highest_urgency` (296-302) — Vorbild |
| src/services/radar_service.py:129 | `RADAR_ONSET_THRESHOLD_MIN = 55` |
| src/output/renderers/alert/render.py:597-787, 1121-1249 | Text: „ab HH:MM“, Nass-Zonen-Suffix, SMS-Form |
| src/output/renderers/alert/segments.py:91-121 | Ortsangabe: Segment-km bzw. „Etappe N“ |

## Existing Patterns
- Ortsvergleich (`compare_radar_alert`): jeder Ort einzeln gegen `radar_alert_due`, Dringlichkeit = höchste der auslösenden Orte, eine gebündelte Nachricht.
- Fehlerpolitik #2050 S4a: Ausfall des auslösenden Punkts bricht den Trip ab (`REASON_DATA_UNAVAILABLE`), Ausfall eines Folgepunkts ist eine Messlücke und läuft weiter.
- Geteilter Code Trip/Compare (ADR-0021): gleiche Gate-Reihenfolge, gleiche Schwelle.

## Dependencies
- Upstream: `RadarNowcastService.get_nowcast` (Cache, Budget #1329), `position_at_time` (#2017), `alert_gate`, `alert_state` (Sperrzeit, Vergleichsbasis #2065), `alert_daily_limit`, Identitäts-Gate (#1467), `alert_log`.
- Downstream: Alarmtext alle vier Kanäle (Mail/Telegram/SMS/Premium-SMS), Alarmprotokoll (E-1), `/strecke`-Kommando (nutzt `points_from_km`, nicht betroffen), Mitschnitt (`_nowcast_capture_id`).

## Existing Specs
- docs/specs/modules/feat_2051_s2a_raeumliche_ausdehnung.md — Folgepunkte; Zeile 268 „keine Änderung an der Auslöseregel“ (keine Begründung dokumentiert)
- docs/specs/modules/fix_2017_nowcast_messpunkt.md — KL 8 (Fenstermitte statt Onset), KL 9 (dieses Restrisiko)
- docs/specs/modules/feat_2261_sz8_messpunkt_position.md — AC-5 hält #2480 fest
- docs/specs/modules/feat_2050_s4a_radar_teilausfall.md:63-68 — zwei Fehlerpolitiken
- docs/specs/modules/fix_2065_verschaerfung_ueberholt_sperre.md, radar_nowcast.md, fix_2009_nowcast_vorlauf.md, feat_2051_s2b_ausdehnung_kanaele.md
- ADRs: 0021, 0009 (Mail nennt Etappe, Segment-km, Onset-Zeit), 0046, 0052, 0056

## Tests
- Szenario-Harness: tests/helpers/alarm_pruefstrecke.py (`AlarmPruefstrecke(...).lauf(at=, zweig="radar", trip=, radar_service=)`), Spec docs/specs/modules/alarm_pruefstrecke.md
- Sz.8: tests/tdd/test_alarm_szenario_messpunkt_position.py
- Fake-Radar je Punktindex: `recording_radar_service_type(calls, script=idx->result)`, `nass()`, `trocken()` in tests/helpers/strecke_fixtures.py:156-233; `_ZonenRadar` in test_regen_ausdehnung_textstellen.py:390
- **Kollidierender Wächter:** test_radar_messluecken_protokoll.py:595-625 `test_ausfall_am_ersten_punkt_erzeugt_keine_ausdehnungszeile` erwartet `sent == 0`, wenn Punkt 0 ausfällt und Folgepunkte nass sind.
- Kein Test hält heute „Punkt 0 trocken, Folgepunkt nass ⇒ kein Alarm“ fest.

## Risks & Considerations
- **Wahrheit des Texts (B-1/B-2):** `onset_minutes` eines Folgepunkts ist relativ zu JETZT, nicht zur Ankunft des Wanderers dort. Welcher Beginn erscheint im Text (frühester über alle auslösenden Punkte?), und welcher Ort?
- **Welche Größen vom auslösenden Punkt:** Dringlichkeit, Konvektion, Menge (#2065-Vergleichsbasis), Ende, Quelle, Label — Aggregation (max/min) oder „maßgeblicher Punkt“ muss festgelegt werden; Vergleichsbasis muss über Läufe konsistent bleiben (C-3).
- **Mehr Alarme:** Folgepunkte vergrößern die Fläche → mehr Auslösungen; Sperrzeit, Tageslimit, Identitäts-Gate (C-2) müssen weiter greifen.
- **Fehlerpolitik:** Ausfall Punkt 0 bei nassem Folgepunkt — heute Abbruch (Wächter oben); B-4 „Teilausfall nie Entwarnung“ spricht dafür, dass ein nasser Folgepunkt dann auslösen darf → Wächter muss bewusst angepasst werden.
- **E-1 Protokoll:** `measurement_point` trägt nur Segment-km; der auslösende Punkt (km) sollte protokolliert werden.
- **Ortsvergleich nicht betroffen** (löst schon an jedem Ort aus); Teilungs-Invariante: Auswahllogik möglichst als geteilter Baustein mit `_detect_triggered_locations`-Muster.
- Abruf-Budget unverändert (alle Punkte werden bereits abgerufen).

## Analysis

### Type
Bug (nutzersichtbare Alarm-Lücke; Auslöseregel nur an Punkt 0, `trip_alert.py:2074`)

### Verifizierte Befunde (Phase 2)
- `result` = Punkt 0 (`trip_alert.py:1874`); `_zonen_ergebnisse` (1904-1919) hält positionsgleich die VOLLEN
  NowcastResults aller Punkte (None bei throttled/data_unavailable/Exception) — onset/urgency/Menge der Folgepunkte
  stehen nach der Schleife zur Verfügung.
- **Korrektur zur Kontext-Annahme „Abruf-Budget unverändert":** gilt nur, wenn Punkt 0 nicht WIRFT. Bei Exception an
  Punkt 0 (1878-1892) `continue` VOR der Zonenschleife ⇒ Folgepunkte werden nie abgerufen. Bei `data_unavailable`
  an Punkt 0 läuft die Schleife dagegen schon (Ausstieg erst 2062-2072). Auslösen nach Punkt-0-Exception bedeutet
  also echte Zusatzabrufe gegen Budget #1329.
- Drei Ausfallarten Punkt 0 unterscheiden: **throttled** = Budget-Druck ⇒ weitere Abrufe sinnlos, Verhalten
  unverändert lassen; **data_unavailable** (Folgepunkte schon abgerufen) und **Exception** ⇒ Kandidat für Auslösen
  über Folgepunkte.
- Mitschnitt-Capture-ID (2415-2417) wird aus `_nowcast_source_key(lat, lon)` von PUNKT 0 gebildet ⇒ muss auf die
  Koordinate des maßgeblichen Punkts umgestellt werden, sonst verweist das Protokoll auf den falschen Abruf.
- **Ortsangabe existiert bereits:** Nass-Zonen-Suffix (#2051 S2b) nennt in allen vier Kanälen die nasse Strecke
  (`render.py:732-749` Mail/Telegram „km 2-4", `render.py:1121-1145` SMS „km8-12" mit Budgetlogik), sofern
  `km_measured`. Ein zusätzliches „bei km X" ist damit weitgehend redundant ⇒ Render-Scope entfällt voraussichtlich;
  nur prüfen, dass der Onset-Kopf („ab HH:MM") bei Auslösung durch Folgepunkt nicht als Ortsaussage über den
  Standort missverstanden wird (Kopf nennt Segment-km).
- Wächter `tests/tdd/test_radar_messluecken_protokoll.py:595-625` (AC-8 aus #2050 S4a, PO-freigegeben) erwartet
  `sent == 0` bei Ausfall Punkt 0 (Exception UND data_unavailable). Spec `feat_2050_s4a_radar_teilausfall.md:63-68`
  legt die „zwei Fehlerpolitiken" fest. ADRs (0021/0046/0052/0056) fixieren die Punkt-0-Regel nach grep NICHT ⇒
  kein neues ADR nötig, aber die S4a-AC-8 wird bewusst abgelöst (PO-Entscheid nötig, Spec muss es benennen).
- Ortsvergleich (`compare_radar_alert._detect_triggered_locations` 449-509) löst bereits an jedem Ort aus; nicht betroffen.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/services/trip_alert.py | MODIFY | Nach Zonenschleife maßgeblichen Punkt wählen und als eigene Variable an allen nachgelagerten Stellen statt `result` nutzen (Menge 1936, Dringlichkeit 1946, Sperrzeit-Override, data_unavailable-Ausstieg 2062, Guard 2074, Onset 2082, Request, Capture-ID 2415 mit Punkt-Koordinate, record_nowcast_sent 2462); Punkt-0-Exception ⇒ Folgepunkte trotzdem abrufen |
| src/services/radar_service.py oder alert_urgency.py | MODIFY | kleiner reiner Baustein „maßgeblichen Eintrag wählen" (auslösend via `radar_alert_due`, frühester Onset, dann höhere Dringlichkeit, dann kleinerer Index) |
| src/services/trip_alert.py `_radar_e1_fields` | MODIFY | additiv: km des auslösenden Punkts im Protokoll (optional, rückwärtskompatibel) |
| tests/tdd/test_radar_messluecken_protokoll.py | MODIFY | AC-8-Wächter bewusst anpassen (Punkt 0 aus + Folgepunkt nass ⇒ Alarm; Punkt 0 aus + Rest trocken ⇒ weiter `data_unavailable`, kein Alarm) |
| tests/tdd/test_radar_alarm_folgepunkte.py (o.ä.) | CREATE | Szenarien über `AlarmPruefstrecke` mit `recording_radar_service_type(script=idx->result)` |
| docs/specs/modules/feat_2050_s4a_radar_teilausfall.md, feat_2051_s2a_raeumliche_ausdehnung.md:268, fix_2017_nowcast_messpunkt.md KL 9, feat_2261_sz8_messpunkt_position.md AC-5 | MODIFY | Ablösung/Erledigt-Vermerk |

### Scope Assessment
- Files: ~3 produktiv + 2 Tests + Spec-Vermerke
- Estimated LoC: +80/-20 produktiv (unter 250)
- Risk Level: MEDIUM — zentrale Alarmentscheidung; mehr Alarme by design; Gate-Reihenfolge (Sperrzeit-Override liest Menge/Dringlichkeit VOR dem Guard ⇒ Auswahl muss direkt nach der Zonenschleife stehen)

### Technical Approach
EIN maßgeblicher Punkt (keine Aggregation je Größe — sonst Mischwerte, die kein Abruf geliefert hat). Auswahl unter
verwertbaren Punkten, für die `radar_alert_due` gilt: frühester Onset (`already_running` = 0), Gleichstand höhere
Dringlichkeit, dann kleinerer Index. Alle nachgelagerten Größen aus diesem einen Ergebnis. Punkt 0 auslösend ⇒
Verhalten und Text bitgleich wie heute.
Zeit im Text = Regenbeginn ab jetzt (es gibt keine Ankunftszeit je Punkt); Ort = bestehender Zonen-Suffix.
**Stickiness (zuletzt gemeldeten Punkt bevorzugen) wird NICHT eingebaut** — wäre eine Persistenzänderung in
`alert_state`. Stattdessen Pflicht-Test: Wechsel des maßgeblichen Punkts zwischen zwei Läufen ohne Verschärfung
erzeugt keinen zweiten Alarm (Identitäts-Gate #1467 / Sperrzeit / #2065-Vergleichsbasis). Fällt der Test rot, wird
Stickiness in der Spec nachgezogen.
Sperrzeit, Tageslimit, Identitäts-Gate bleiben unverändert (laufen nach der Auswahl).

### Dependencies
`RadarNowcastService.get_nowcast` (Budget #1329), `radar_alert_due`, `alert_state`/#2065, Identitäts-Gate #1467,
`alert_input_capture`, `derive_rain_zones`, Renderer-Zonen-Suffix (#2051 S2b) — unverändert.

### Open Questions (PO-Produktentscheidung)
- [x] (a) Alarm auch, wenn Regen innerhalb der nächsten Stunde 2–10 km weiter vorn auf der Strecke beginnt? **PO-Entscheid 2026-10-02: JA** (Uhrzeit = Regenbeginn dort, nicht Ankunft; Ort über bestehenden Zonen-Suffix)
- [x] (b) Alarm auch, wenn der eigene Messpunkt nicht abrufbar ist, weiter vorn aber Regen belegt ist? **PO-Entscheid 2026-10-02: JA** — löst #2050 S4a AC-8 bewusst ab; vorn alles trocken ⇒ weiter `data_unavailable` protokolliert, kein Alarm; throttled an Punkt 0 bleibt unverändert (keine Zusatzabrufe bei Budget-Druck)

## Hinweise aus der RED-Phase (2026-10-02, für /50-implement)

- **Festgelegte Schnittstellen (vom RED-Test erzwungen):** `services.trip_alert.waehle_massgeblichen_punkt(ergebnisse) -> tuple[int, NowcastResult] | None`; E-1-Feld `trigger_point_km` (float) in `alert_log._E1_FIELD_TYPES`, `_apply_e1_fields` und als `append_entry`-Kwarg; falsch typisierter Wert ⇒ nur das Feld weglassen. Bei Auslösung durch Punkt 0 wird das Feld NICHT geschrieben (AC-2-Referenz `tests/fixtures/radar_folgepunkte/punkt0_referenz.json`, aufgenommen auf `e140b3955`, ohne Regenerier-Schalter).
- **Fake-Radar steuert nach Koordinate**, Soll-Punkte per trockenem Probelauf je Uhr; Capture-ID wird über `alert_input_capture.capture_system` je Punkt zuordenbar.
- **AC-7-Lesart:** Heute ruft der Lauf auch bei `throttled` an Punkt 0 alle sechs Punkte ab (Zonenschleife). Getestet ist „nicht mehr Abrufe als heute" (kein Punkt doppelt, höchstens Punktzahl, nur `polling`) plus kein Alarm.
- **AC-6** ist heute schon grün (REASON_DATA_UNAVAILABLE wird in beiden Ausfallwegen geschrieben) — Regressionsschutz.
- **Nicht getestet (bewusst offen):** ob `measurement_gaps` Punkt 0 bei Ausnahme als Lücke führt; eigener Zweitlauf-Test für `event_duplicate` (AC-8 prüft nur Register-Stufe MODERATE des gewählten Punkts; AC-9 deckt „kein zweiter Alarm" ab).
- **AC-8 Tageslimit:** frischer Tag ohne Zustellung zählt als LOW ⇒ jede Stufe wäre Eskalation; Test macht erst einen Folgepunkt-Alarm, leert dann das Budget, prüft Verschärfung ohne Stufenwechsel (Grund `daily_limit`).
