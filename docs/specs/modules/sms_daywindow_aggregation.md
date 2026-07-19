---
entity_id: sms_daywindow_aggregation
type: feature
created: 2026-07-19
updated: 2026-07-19
status: draft
version: "1.0"
tags: [gewitter, sms, compact_summary, telegram, email-pillen, adr-0025, issue-1317, epic-1319, tagesfenster]
---

# SMS/Kurzform-Aggregation über festes Tagesfenster 04:00–19:00 (Epic #1319, Scheibe A)

## Approval

- [x] Approved — PO-„go" 2026-07-19 (inkl. Freigabe, die Änderung über alle vier Kurzformen in einem Zug zu machen; LoC-Override erteilt)

## Purpose

Die vier Kurzform-Renderer (SMS `TH:`/`R`/`PR`/`W`/`G`, E-Mail-Kurzzusammenfassung, E-Mail-Kopf-
Kacheln, Telegram-Fußzeile) fenstern ihre Wert-Token heute ausschließlich auf die **Wanderzeit**
der Etappe — Wetter, das erst **nach der Ankunft** am Ziel eintritt (Nachmittag/Abend am
Lagerplatz oder in der Hütte), fällt strukturell heraus, obwohl die E-Mail-Detailtabelle
„Nacht am Ziel" es korrekt zeigt (gemeldeter Fall #1317: Gewitter 14:00 nach Ankunft, SMS zeigt
`TH:-`). Diese Spec ersetzt die Wanderzeit-Fensterung für alle vier Kurzformen durch ein
**festes Tagesfenster 04:00–19:00 Ortszeit** (Konstante, in Scheibe B einstellbar) und einen
**ortsgenauen** Datenzugriff — bis zur Ankunft entlang der Route, danach am Ziel — gespeist aus
denselben Stunden-Rohdaten wie die Detailtabelle, damit sich Kurzform und Tabelle nie
widersprechen können (ADR-0025-Konsistenz).

## Source

- **File:** `src/output/renderers/sms_trip.py`
- **Identifier:** `SMSTripFormatter.format_sms()` / `_segments_to_normalized_forecast()`
  (Fensterfilter Zeile 106-114)

- **File:** `src/output/renderers/compact_summary.py`
- **Identifier:** `CompactSummaryFormatter.format_stage_summary()` / `_collect_hourly_data()`
  (Zeile 140-165) / `_format_thunder()` (Zeile 365-386)

- **File:** `src/output/renderers/email/helpers.py`
- **Identifier:** `build_metrics_summary_pills()` (Zeile 1428-1477, Fensterfilter
  Zeile 1450-1465), aufgerufen aus `email/compact.py:144`, `email/html.py:1199`,
  `email/plain.py:155`

- **File:** `src/output/renderers/narrow.py`
- **Identifier:** `_windowed_thunder_severity()` (Zeile 164-191) / `_tg_day_footer()`
  (Zeile 194-246)

- **File:** `src/output/renderers/trip_report.py`
- **Identifier:** `TripReportFormatter.format_email()` — Glue: hält bereits `night_weather`
  (Parameter Zeile 62), berechnet `arrival_hour` (Muster Zeile 108-115) und ruft alle vier
  Kurzform-Einstiegspunkte auf (Telegram Zeile 189-201, SMS Zeile 224-233,
  Kurzzusammenfassung via `_generate_compact_summary()` Zeile 699-710, Pillen indirekt über
  `render_email()`/`render_html()`/`render_plain()`/`render_compact()`).

- **File:** `src/output/renderers/email/__init__.py`, `email/html.py`, `email/plain.py`,
  `email/compact.py`
- **Identifier:** `render_email()`, `render_html()`, `render_plain()`, `render_compact()` —
  reichen aktuell `night_rows` (bereits aggregierte 2h-Blöcke für die Detailtabelle) bis zu
  `build_metrics_summary_pills()` durch; `night_weather` selbst (rohe `ForecastDataPoint`-Liste)
  fehlt in dieser Kette und muss nach demselben, bereits etablierten Muster wie `night_rows`
  zusätzlich durchgereicht werden, damit die Pillen dieselbe Rohquelle wie die Tabelle nutzen
  können.

> Referenz für erwartetes Verhalten (darf nicht regressieren): `trip_report.py:280-323`
> (`_extract_night_rows`) — speist die Detailtabelle „Nacht am Ziel" korrekt aus `night_weather`.

## Estimated Scope

- **LoC:** ~200-260 (Produktivcode über 9 Dateien inkl. eines neuen kleinen, geteilten
  Fenster-Moduls; Tests zusätzlich, zählen nicht gegen die Kern-Grenze). **Risiko, die
  projektweite 250-LoC-Workflow-Grenze zu reißen — kein eigenmächtiger Override, bei
  Überschreitung PO-Permission einholen** (CLAUDE.md „Kein LoC-Override ohne Permission").
- **Files:** 9 Produktivdateien (`sms_trip.py`, `compact_summary.py`, `email/helpers.py`,
  `narrow.py`, `trip_report.py`, `email/__init__.py`, `email/html.py`, `email/plain.py`,
  `email/compact.py`) + 1 neue Datei (geteiltes Fenster-Modul, s. Implementation Details) +
  zugehörige Testdateien.
- **Effort:** high (sicherheitskritischer Pfad, vier Kanäle + eine mehrstufige Aufrufkette
  müssen synchron geändert werden, Konsistenz-Invariante aus ADR-0025 muss über alle Kanäle und
  gegen die Detailtabelle erhalten bleiben).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| ADR-0025 (`docs/adr/0025-eine-gewitter-quelle-fuer-alle-briefing-kanaele.md`) | Architekturentscheidung | Definiert die Ein-Quelle-/Ein-Fenster-Invariante, die diese Spec novelliert (Fenster = festes Tagesfenster statt Wanderzeit) |
| `docs/reference/sms_briefing_overview.md` §5 | Leitlinie | PO-Entscheid 2026-07-19 „Vereinbartes Zielkonzept" — diese Spec setzt Punkte 1-3 und 6 um, NICHT 4 (N-Logik), 7 (bereits stundenscharf) oder 8/9 (explizit out of scope) |
| `docs/specs/modules/thunder_night_at_destination_channels.md` | Spec (superseded) | Enge Vorgänger-Lösung nur für Gewitter/Nacht-am-Ziel; liefert bereits verifizierte Fakten zu `night_weather`/`arrival_hour`, die diese Spec übernimmt und auf alle Wert-Token sowie das volle Tagesfenster erweitert |
| `src/output/metric_format.py` (`thunder_label_value`, `thunder_ordinal`) | module | Kanonische Skalen — Render- vs. Sortier-Skala, dürfen nicht vermischt werden (ADR-0025 Entscheidung 3) |
| `src/services/segment_weather.py` (`fetch_segment_weather`, Zeile 140-201) | service | Liefert `seg.timeseries` bereits **ungefiltert als vollen Tag** (24h); nur die interne Aggregation nutzt eine wanderzeit-gefilterte Kopie — Beleg dafür, dass die 04-Uhr-Stunden vor Aufbruch bereits im vorhandenen Datensatz liegen |
| `src/services/trip_report_scheduler.py` (`_fetch_night_weather`, Zeile 1177-1220) | service | Liefert `night_weather` (Ankunft am Zielpunkt `seg.end_point` → 06:00 Folgetag), seit #1313 für morning UND evening befüllt, gesteuert über `dc.show_night_block` — diese Spec ändert das Fetch-Gating **nicht** |
| `app.models.NormalizedTimeseries` / `ForecastDataPoint` | model | Datentyp von `seg.timeseries` und `night_weather`; beide tragen `dp.thunder_level`, `dp.precip_1h_mm`, `dp.wind10m_kmh`, `dp.gust_kmh`, `dp.pop_pct` — dieselben Felder wie die Detailtabelle |
| `trip_report.py:_extract_night_rows` (Zeile 280-323) | function | Referenzimplementierung des Ankunft→06:00-Fensters und der Zielort-Bestimmung (Musterreferenz, nicht identisch aufzurufen) |

## Implementation Details

**Kernidee:** Statt der bisherigen Fensterung `start_h <= h <= end_h` (Wanderzeit der Etappe)
verwenden alle vier Kurzformen künftig ein festes Tagesfenster
`DAY_WINDOW_START_HOUR = 4` / `DAY_WINDOW_END_HOUR = 19` (benannte Modul-Konstanten, die Scheibe B
durch einen konfigurierbaren Wert ersetzt — die Spec verdrahtet sie bewusst fest, damit der
spätere Austausch punktuell an einer Stelle passiert). Ortsbezug bleibt **ortsgenau**: bis zur
Ankunft kommen die Stunden aus der Route (Segment-`timeseries`), ab der Ankunft aus dem Ziel
(`night_weather`).

### Geklärte technische Punkte (aus Code-Analyse, verbindlich für TDD/Implement)

1. **Stunden vor Etappenstart (04:00–Aufbruch):** `seg.timeseries.data` (das UNGEFILTERTE Feld
   auf `SegmentWeatherData`, `segment_weather.py:201`) enthält bereits den **vollen Kalendertag**
   (24h), nicht nur die Wanderzeit — Kommentar `segment_weather.py:164-166` („OpenMeteo returns
   full-day (24h) data; aggregation must use only segment hours") sowie die **tagesbasierten**
   (nicht stundengenauen) `start_date`/`end_date`-Parameter des Providers
   (`openmeteo.py:862-863`) belegen das. Die vier Kurzformen filtern dieses bereits vorhandene
   Array heute künstlich auf `[start_h, end_h]` herunter. Für Scheibe A heißt das: die
   Frühstunden 04:00–Aufbruch sind bereits im **ersten** Segment vorhanden (dessen
   `timeseries` an `segment.start_point` hängt — dem Ort, an dem der Wanderer vor dem Aufbruch
   ist) und müssen nur durch eine abgesenkte untere Fenstergrenze (`4` statt `start_h`, für das
   erste Segment) freigeschaltet werden. **Grenze/Annahme:** nur für den Default-Provider
   OpenMeteo verifiziert; für andere Provider (z. B. MOSMIX, Decision-Matrix) nicht separat
   geprüft — falls ein Provider tatsächlich nur die Wanderzeit liefert, ist das vor der
   Implementierung an der betroffenen Provider/Segment-Kombination gegenzuprüfen (siehe Known
   Limitations).

2. **Ziel-Stunden Ankunft→19:00:** `night_weather` deckt Ankunft am Zielpunkt (`seg.end_point`
   des letzten Segments, `trip_report_scheduler.py:1196-1215`) bis 06:00 des Folgetags ab —
   19:00 liegt damit sicher innerhalb. Die Ankunftsstunde wird nach dem bestehenden Muster
   `arrival_hour = local_hour(last_seg.segment.end_time, tz)` bestimmt
   (`trip_report.py:112`, dort bereits für die Detailtabelle verwendet). `night_weather` ist
   seit #1313 für **beide** Report-Typen (morning/evening) befüllt, gesteuert über
   `dc.show_night_block` (Fetch-Gating bleibt unverändert).

3. **Aggregation bei mehreren Segmenten (ortsgenaue Zuordnung):** Für jede Fenster-Stunde
   (04:00–19:00) gilt: bis zur Ankunft liefert **die jeweils zuständige Segment-Zeitreihe** den
   Wert (unverändertes Wanderzeit-Verhalten pro Segment, nur beim **ersten** Segment die untere
   Grenze auf 4 abgesenkt, s. Punkt 1); ab der Ankunftsstunde bis 19:00 liefert **ausschließlich
   `night_weather`** den Wert (nicht die Zeitreihe des letzten Segments — deren `timeseries`
   hängt an `segment.start_point`, **nicht** am Zielort, und wäre nach der Ankunft geografisch
   falsch). Beide Quellen werden zu einer Stundenliste vereinigt und pro Ortszeit-Stunde
   dedupliziert — analog zum bestehenden `_dedup_by_hour` (`sms_trip.py:148-153`): bei
   Überschneidung an der Ankunftsstunde (Segment liefert sie inklusive, Nacht-Fenster beginnt bei
   ihr, Muster `_extract_night_rows:301`) gewinnt der Höchstwert je Metrik, konsistent mit der
   bestehenden Grenzstunden-Regel aus Bug #925/#1146.

### Geteiltes Fenster-Modul (ADR-0025-Konsistenz, Code-Teilung)

Damit alle vier Kanäle nachweisbar **dieselbe** Fenster-Logik verwenden (nicht viermal
unabhängig nachgebaut — das wäre der #874/#1275-Fehlermodus), wird eine kleine geteilte
Hilfsfunktion eingeführt (Vorschlag: `src/output/renderers/day_window.py`), die aus
`(segments, night_weather, tz)` eine deduplizierte Liste von `ForecastDataPoint`s im Fenster
04:00–19:00 baut — inklusive korrekter Ortszuordnung gemäß Punkt 3. Die vier Renderer konsumieren
diese Liste anstelle ihrer bisherigen, je eigenen `start_h`/`end_h`-Filterschleife; die
Token-/Onset-Peak-Bildung selbst (`_dedup_by_hour`, `render_threshold_peak_value`,
`_format_thunder`, `_pill_for_metric`, `_windowed_thunder_severity`) bleibt unverändert — es
ändert sich nur, **welche** Rohdaten hineinfließen, nicht **wie** sie verarbeitet werden. Exakter
Funktionsname/-signatur ist Implementierungsdetail der TDD/Implement-Phase; bindend ist nur:
eine einzige Implementierung, von allen vier Kanälen verwendet.

### Threading `night_weather` bis zu den Pillen

`build_metrics_summary_pills()` wird heute nur mit `segments` aufgerufen (`email/compact.py:144`,
`email/html.py:1199`, `email/plain.py:155`). `night_weather` muss nach demselben, bereits
etablierten Muster wie `night_rows` (aktuell in `render_email()` → `render_html()`/
`render_plain()`/`render_compact()` durchgereicht) zusätzlich als optionaler Parameter
durchgereicht werden — kein neuer Mechanismus, sondern dieselbe Kette, ein zusätzliches Feld.

### Was unverändert bleibt

Die Token-Anzahl der SMS ändert sich nicht (`TH:`/`R`/`PR`/`W`/`G` bleiben dieselben Symbole),
`TH+:` bleibt unverändert (andere Quelle, `thunder_forecast`, nicht Teil dieser Spec), `N`/`D`
bleiben bei der Wanderzeit-Logik (Scheibe D), die Skalen-Trennung (`thunder_ordinal()` vs.
`thunder_label_value()`) bleibt vollständig erhalten.

## Expected Behavior

- **Input:** `segments` (Etappen-Zeitreihen, jetzt ungefiltert bis 04:00 vor Aufbruch relevant)
  + `night_weather` (`NormalizedTimeseries`, Ankunft → 06:00 morgens, sofern
  `dc.show_night_block`) + `report_type` (morning/evening) + `tz`.
- **Output:** SMS-Token `R PR W G TH:`, E-Mail-Kurzzusammenfassungssatz, Metriken-Pillen
  (E-Mail-Kopf) und Telegram-Fußzeile berücksichtigen jede Stunde im Fenster 04:00–19:00
  Ortszeit — unabhängig davon, ob sie vor Aufbruch, während der Wanderung oder nach Ankunft am
  Ziel liegt — konsistent mit der Detailtabelle „Nacht am Ziel" (für den Ausschnitt bis 19:00).
- **Side effects:** keine. Reine Erweiterung/Verschiebung der Eingabedaten-Fenster in
  bestehenden Rendering-Pfaden; kein neuer Fetch (`night_weather` und der volle Tages-`timeseries`
  existieren bereits).

## Acceptance Criteria

- **AC-1 (gemeldeter Fall #1317, Morgen-Report):** Given ein Morgen-Report (Erzeugung ~07:00),
  dessen `night_weather` nach der heutigen Ankunft (12:00) ein Gewitter um 14:00 enthält / When
  `TripReportFormatter.format_email(report_type="morning")` mit `segments` und `night_weather`
  aufgerufen wird / Then zeigen SMS-`TH:`-Token, Kurzzusammenfassungssatz, Metriken-Pille und
  Telegram-Fußzeile ein Gewitter — dies ist die exakte Reproduktion des gemeldeten Bugs (heute:
  alle vier schweigen, obwohl die Tabelle das 14:00-Gewitter zeigt).
  - Test: `format_email(report_type="morning")`-Aufruf mit Bug-Fixture; rot vor Fix, grün danach.

- **AC-2 (gleicher Fall, Abend-Report):** Given denselben Fall wie AC-1, aber ein Abend-Report
  (der berichtete Tag ist „morgen") / When `format_email(report_type="evening")` aufgerufen wird
  / Then zeigen alle vier Kurzformen das Gewitter für den berichteten (morgigen) Tag — der
  Bezugstag-Mechanismus (`TH:` = berichteter Tag) bleibt dabei unverändert korrekt.
  - Test: `format_email(report_type="evening")`-Aufruf mit derselben Fixture wie AC-1, verschoben
    auf den Folgetag.

- **AC-3 (Begleitwerte konsistent):** Given denselben Fall wie AC-1, wobei die 14:00-Stunde in
  `night_weather` zusätzlich Regen (>0,2 mm), Regenwahrscheinlichkeit (>20%) und Böen (>20 km/h)
  trägt / When alle vier Kanäle gerendert werden / Then zeigen SMS `R`/`PR`/`G`, die
  Kurzzusammenfassung und die Regen-/Wind-Pille ebenfalls Werte für 14:00 (kein „Gewitter ohne
  Regen" — dieselbe Stunde liefert alle Metriken aus derselben Rohquelle).
  - Test: echter Aufruf der vier Einstiegsfunktionen mit einer Zeitreihe, die um 14:00 alle vier
    Metriken gleichzeitig über der Schwelle trägt; Assert auf alle betroffenen Token/Sätze.

- **AC-4 (Konsistenz-Invariante):** Given denselben Fall wie AC-1 / When SMS, Kurzzusammenfassung,
  Pille, Telegram-Fußzeile **und** die Detailtabelle „Nacht am Ziel" aus demselben
  `format_email()`-Aufruf erzeugt werden / Then melden alle fünf Ausgaben übereinstimmend ein
  Gewitter für 14:00 (keine widerspricht einer anderen) — Fortführung von ADR-0025 auf das
  erweiterte Fenster.
  - Test: ein einziger `format_email()`-Aufruf, Assert über alle fünf Ausgabefelder des
    `TripReport` hinweg.

- **AC-5 (obere Fenstergrenze, Ausschluss):** Given ein Gewitter in `night_weather` um 20:00
  (außerhalb 04–19, aber innerhalb Ankunft→06:00) / When alle vier Kanäle gerendert werden / Then
  löst diese Stunde **kein** Gewitter-Token/keine Gewitter-Pille aus.
  - Test: Fixture mit Ereignis exakt um 20:00; Assert, dass keiner der vier Kanäle es zeigt.

- **AC-6 (obere Fenstergrenze, Einschluss):** Given dasselbe Szenario wie AC-5, aber das Ereignis
  liegt um 18:00 (innerhalb 04–19) / When alle vier Kanäle gerendert werden / Then zeigen alle
  vier das Gewitter für 18:00.
  - Test: Fixture mit Ereignis exakt um 18:00; Assert, dass alle vier Kanäle es zeigen.

- **AC-7 (untere Fenstergrenze, vor Aufbruch):** Given eine Etappe mit Aufbruch um 08:00 und
  einem Gewitter um 05:00 (vor Aufbruch, aber innerhalb 04–19) in der bereits vorhandenen,
  ungefilterten Zeitreihe des ersten Segments / When alle vier Kanäle gerendert werden / Then
  zeigen alle vier das Gewitter für 05:00; ein Ereignis um 03:00 (außerhalb 04–19) wird dagegen
  **nicht** gezeigt.
  - Test: zwei Fixture-Varianten (Ereignis 05:00 vs. 03:00) gegen dieselben vier
    Einstiegsfunktionen; Assert auf Ein-/Ausschluss.

- **AC-8 (Regressionsschutz Wanderzeit):** Given eine Etappe ohne jedes Ereignis vor Aufbruch oder
  nach Ankunft (alles Wetter liegt innerhalb der bisherigen Wanderzeit-Fensterung) / When alle
  vier Kanäle gerendert werden / Then bleibt das Ergebnis identisch zum Vorzustand, und die
  bestehenden ADR-0025-Testsuiten (u. a. zu #1275, SMS-`TH:`/`TH+:`, Telegram-Fußzeile,
  Kopf-Kachel) bleiben grün.
  - Test: bestehende ADR-0025-Bestandstests unverändert grün nach dem Fix; zusätzliche
    Regressions-Fixture ohne Frühe-/Spät-Ereignis liefert bit-identische Ausgabe.

- **AC-9 (fehlendes night_weather → fail-soft):** Given `night_weather is None` (z. B.
  `dc.show_night_block == False`, kein Zielsegment oder kein Nacht-Fetch) / When einer der vier
  Kanäle gerendert wird / Then verhält sich der Kanal wie reine Segment-Fensterung im Fenster
  04–19 (kein Absturz, kein fehlender Report), ohne Ziel-Stunden nach Ankunft.
  - Test: alle vier Einstiegsfunktionen jeweils mit `night_weather=None` aufgerufen; Assert auf
    fail-soft-Verhalten (keine Exception, plausibles Ergebnis aus Segment-Daten allein).

## Known Limitations

- **Einstellbarkeit des Fensters** (Config/UI, pro Wanderung) ist **nicht** Teil dieser Scheibe
  → Scheibe B/C. Hier ist 04:00–19:00 eine feste, benannte Konstante.
- **`N`/`D`-Temperatur bleibt in Scheibe A unverändert** auf die Wanderzeit gefenstert — die
  N-Logik (Nacht-Tiefsttemperatur am aktuellen Schlafplatz, nur im Abendbriefing) ist Scheibe D.
- **`TH+:`** (Folgetag-Vorschau) bleibt unverändert — ist seit #1275 korrekt relativ (Morgen→
  morgen, Abend→übermorgen); ein Regressionstest dafür ist Scheibe E, nicht Teil dieser Spec.
- **Amtliche Warnungen** sind nicht Teil dieser Spec → Issue #1318.
- Punkt 1 der Implementation Details (volle Tagesdaten im ersten Segment) ist nur für den
  Default-Provider OpenMeteo im Code verifiziert; bei anderen Providern ist vor der Umsetzung
  gegenzuprüfen, ob `seg.timeseries.data` für das erste Segment tatsächlich den vollen Tag ab
  04:00 enthält.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0025 (Novellierung: Fenster = festes Tagesfenster 04–19 statt Wanderzeit, für
  alle Kurzformen)
- **Rationale:** ADR-0025 legt fest, dass alle Kanäle eine Gewitter-/Wert-Aussage aus derselben
  Rohdatenquelle (`dp.thunder_level` u. a.) und demselben Fenster ableiten, um Kanal-Widersprüche
  (#874, #1275) strukturell auszuschließen. Diese Spec ändert **nicht** die Rohquelle und
  **nicht** das Prinzip „ein Fenster für alle Kanäle" — sie ersetzt lediglich die
  Fensterdefinition von „Wanderzeit der Etappe" auf „festes Tagesfenster 04:00–19:00, ortsgenau
  bis zur Ankunft entlang der Route und danach am Ziel", weil die bisherige Definition eine
  strukturelle Lücke hatte: Wetter vor Aufbruch und nach Ankunft floss in keinem der vier
  Kurzform-Kanäle ein, obwohl die Rohdaten dafür bereits vorliegen (voller Tages-`timeseries`,
  bereits gefetchtes `night_weather`). Die Konsistenz-Invariante (alle Kanäle stimmen überein)
  und die Skalen-Trennung (`thunder_ordinal()` vs. `thunder_label_value()`) bleiben vollständig
  erhalten — das Fenster wird für alle vier betroffenen Kanäle gleichzeitig geändert, nie für
  einzelne.

## Changelog

- 2026-07-19: Initial spec created (Epic #1319, Scheibe A) — löst Issue #1317 als Nebeneffekt der
  breiteren Fenster-Umstellung; ersetzt die enge, superseded Spec
  `docs/specs/modules/thunder_night_at_destination_channels.md`.
