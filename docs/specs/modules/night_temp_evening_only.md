---
entity_id: night_temp_evening_only
type: module
created: 2026-07-23
updated: 2026-07-23
status: draft
version: "1.0"
tags: [renderer, tokens, sms, telegram, compact-summary, night-weather, epic-1319]
---

<!-- Issue #1319 (Epic) — Scheibe D -->

# N (Nacht-Tiefsttemperatur) nur im Abendbriefing, aus night_weather (Issue #1319 Scheibe D)

## Approval

- [x] Approved (PO „freigabe" 2026-07-23)

## Purpose

Die Nacht-Tiefsttemperatur (`N`) erscheint heute unbedingt in Morgen- UND
Abendbriefing, in allen drei Kurzformen (SMS, E-Mail-Kurzzusammenfassung,
Telegram-Fußzeile/Kurzübersicht) — und ihr Wert stammt aus dem
Tagessegment-Minimum (kälteste Wanderstunde, oft der frühe Start), nicht aus
der echten Übernachtungstemperatur am Etappenziel. Diese Spec behebt beides
(PO-Entscheidung DEC-1, 2026-07-23): `N` wird (a) **nur noch im
Abendbriefing** gezeigt (morgens komplett weggelassen, kein Platzhalter) und
zeigt (b) dort die **echte kommende Nacht-Tiefsttemperatur am Schlafplatz**
aus `night_weather` (Ankunft → 06:00 Folgetag am Etappenziel) — konsistent
mit der großen E-Mail-Tabelle „🌙 Nacht am Ziel", die dieselbe Quelle nutzt
und von dieser Spec unverändert bleibt (DEC-3).

## Source

- **File:** `src/output/tokens/builder.py:222-232` — `build_token_line()`,
  N/D-Token-Erzeugung (Sichtbarkeits-Gate für `N`)
- **File:** `src/output/renderers/sms_trip.py:94-227` —
  `_segments_to_normalized_forecast()` (Wert-Quelle für `N`)
- **File:** `src/output/renderers/compact_summary.py:44-207` —
  `CompactSummaryFormatter.format_stage_summary()` / `_format_temperature()`
- **File:** `src/output/renderers/trip_report.py:752-776` —
  `_generate_compact_summary()` (fehlender `report_type`-Durchgriff)
- **File:** `src/output/renderers/narrow.py:171-400,497-501` —
  `_tg_day_footer()`, `_overview_line()`, `_tg_vortag_line()`,
  `render_telegram_bubbles()`
- **File:** `src/output/renderers/day_window.py` — neue geteilte
  Hilfsfunktion `night_temp_min_c()` (Wert-Quelle, von allen drei Kurzformen
  genutzt)

> **Schicht:** Python-Core / Domain-Backend (`src/output/`), reine
> Renderer-/Token-Logik. Kein Go-, kein Frontend-Anteil. Betrifft
> ausschließlich die drei Kurzformen — die große E-Mail-Tabelle
> (`trip_report.py::_extract_night_rows`, `email/html.py`, `email/plain.py`)
> bleibt unverändert (DEC-3).

## Estimated Scope

- **LoC:** ~150 (grob +120–180/-40 aus der Analyse; unter dem
  250-LoC-Workflow-Limit, wird beim Implementieren beobachtet)
- **Files:** 5 Renderer-/Token-Dateien + 1 geteilte Helper-Erweiterung
  (`day_window.py`) + 1 neue Testdatei
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `night_weather` (`NormalizedTimeseries`, Ankunft→06:00 Ziel) | Datenquelle | Bereits pro Report-Typ korrekt an letzter Etappe verankert (`trip_report_scheduler.py:1212-1225`, `services/segment_weather.fetch_night_weather`) — keine Änderung an der Fetch-Logik nötig |
| `day_window.build_day_window_points()` | intern (geteilt) | Bleibt unverändert für R/PR/W/G/TH; nur `N`/Temperatur bekommt die neue, separate `night_temp_min_c()`-Quelle |
| `trip_report.py::_extract_night_rows()` (Issue #1313) | Referenzmuster | Liefert das Filtermuster (Ankunftsstunde/-datum → 06:00 Folgetag) gegen WeatherCacheService-„covers"-Kontamination — `night_temp_min_c()` übernimmt dieselbe Filterlogik, NICHT die große Tabelle selbst |
| `MetricSpec` / `_visible()` (`builder.py`) | intern | `N` hat KEINE `MetricSpec` (Hardcode im Token-Loop) — Sichtbarkeits-Gate für `N` muss deshalb hart auf `report_type` geprüft werden, nicht über `_visible()` |
| `renderer_mail_gate.py` (#811, Commit-Gate) | Tooling | `sms_trip.py`, `compact_summary.py`, `trip_report.py` sind Mail-Inhalts-Dateien → vor Commit `tests/tdd/test_issue_811_mode_matrix.py` grün + frischer `briefing_mail_validator.py`-Lauf nötig |
| `docs/reference/sms_format.md` §3.2/§4 | Vertrag | `N`-Zeile (Wert AM letzten GEO-Punkt der Etappe) und Null-Form `N-` bleiben inhaltlich gültig für den Abend-Fall; Doku-Ergänzung „nur Abend" ist Folgearbeit (docs-updater, nicht Teil dieser Spec) |

## Implementation Details

### Geteilte Wert-Quelle: `night_temp_min_c()` (neu, `day_window.py`)

Neue kleine Hilfsfunktion, von allen drei Kurzformen genutzt (keine
Drei-fach-Duplikation der Filterlogik):

```python
def night_temp_min_c(
    night_weather: Optional[NormalizedTimeseries],
    segments: list[SegmentWeatherData],
    tz: ZoneInfo,
) -> Optional[float]:
    """Echte Nacht-Tiefsttemperatur am Schlafplatz: Ankunft (Ende des
    letzten Segments) bis 06:00 Folgetag, gefiltert wie
    trip_report.py::_extract_night_rows Schritt 1 (gegen
    WeatherCacheService-"covers"-Kontamination), dann min(t2m_c).
    None bei fehlenden Daten (fail-soft, kein Crash)."""
```

Filterung identisch zu `_extract_night_rows`: `arrival_hour =
local_hour(segments[-1].segment.end_time, tz)`, `arrival_date =
segments[-1].segment.end_time.astimezone(tz).date()`, Punkte im Bereich
`(gleicher Tag UND Stunde >= arrival_hour)` ODER `(Folgetag UND Stunde <=
6)`. Danach `min(dp.t2m_c für dp mit t2m_c is not None)`. Diese Funktion
ersetzt NICHT `_extract_night_rows()` (bleibt für die große Tabelle
unverändert, DEC-3) — sie ist eine separate, einfachere Ableitung ohne
2h-Block-Aggregation.

### (a) Sichtbarkeit — `builder.py`

Der `N`/`D`-Loop (Zeile 223-232) baut beide Token über dieselbe
`_visible(spec, report_type)`-Prüfung — `N` hat aber keine `MetricSpec`
(`by_sym.get("N")` ist `None`), also ist `_visible(None, ...)` immer `True`
und `N` erscheint unbedingt. Fix: `N` und `D` getrennt behandeln — `D`
bleibt wie bisher, `N` bekommt zusätzlich ein hartes
`report_type == "evening"`-Gate, unabhängig von einer eventuell künftig
vergebenen `MetricSpec`.

### (b) Wert-Quelle Abend — `sms_trip.py`

`format_sms()` hat `report_type` bereits als Parameter (Default
`"evening"`), reicht ihn aber nicht an `_segments_to_normalized_forecast()`
durch. Fix: `report_type` durchreichen; dort `temp_min_c` bei
`report_type == "evening"` aus `night_temp_min_c(night_weather, segments,
tz)` setzen (Fallback auf das bisherige `day_min` aus den Segment-Aggregaten,
falls `night_weather` fehlt oder die Nachtfenster-Filterung keine Punkte
liefert — fail-soft, analog zum bestehenden Docstring-Vertrag „`night_weather:
None = fail-soft`"). Bei `report_type == "morning"` bleibt `temp_min_c`
irrelevant, da `builder.py` das `N`-Token dort gar nicht mehr baut.

### E-Mail-Kurzzusammenfassung — `compact_summary.py` + `trip_report.py`

`_generate_compact_summary()` (`trip_report.py:752-776`) übergibt aktuell
KEIN `report_type` an `format_stage_summary()`. Fix: `report_type`
durchreichen bis zu `_format_temperature()`. Dort:
- **morgens:** nur `t_max` zeigen (`"{t_max}°C"`, kein Bereich/Min) —
  Tech-Lead-Default aus der Analyse.
- **abends:** `night_min–t_max` (`night_temp_min_c()`-Wert statt
  `summary.temp_min_c` aus dem Tagessegment; Fallback auf
  `summary.temp_min_c`, wenn `night_temp_min_c()` `None` liefert).

`_aggregate(segments)` (Tagessegment-Aggregat) bleibt für `t_max`
unverändert Quelle — nur der Min-Wert wechselt abends die Quelle.

### Telegram — `narrow.py`

**Kurzübersicht (`_overview_line`, Zeile 358-400):** generisch für alle
Metriken über `seg_tables` (Tagesfenster-Zeilen). Für `metric_id ==
"temperature"` wird ein Sonderfall nötig: `report_type` und optional
`night_min_c` (vorberechnet über `night_temp_min_c()`) als Parameter
ergänzen. Morgens: nur der Max-Wert (`{label} {max}°C`, kein
`{lo}-{hi}@{h}`-Bereich). Abends: `{label} {night_min}-{max}@{h}` (der
Peak-Hour-Teil bezieht sich weiter auf das Max, wie bisher).

**Fußzeile (`_tg_day_footer`):** zeigt heute keine eigene Temperaturzeile
(nur ⚡/Sicht/0°C-Grenze) — kein Änderungsbedarf, dient nur als
Kontext-Referenz für das gleiche Tagesfenster.

**Vortag-Vergleich (`_tg_vortag_line`, Zeile 252-304):** vergleicht den
`temp_min`-Delta gegen den gestrigen Snapshot als Vorhersage-Aussage
(„Temp min ±X°C"). Da `N` morgens nicht mehr angezeigt wird, würde ein
Delta auf einen unsichtbaren Wert verwirren (Konsistenz-Anspruch Epic-Punkt
6). Fix: `report_type` als Parameter ergänzen; der `("temp_min", "Temp
min", "°C")`-Eintrag aus `_LABELS` wird bei `report_type == "morning"` aus
der Kandidatenliste gefiltert, bevor `top = collected[:3]` gebildet wird.
`temp_max` bleibt in beiden Report-Typen im Vokabular (D bleibt unverändert
in Morgen und Abend).

`render_telegram_bubbles()` reicht `report_type` (bereits als Parameter
Zeile 438 vorhanden) an `_overview_line()`-Aufrufe und `_tg_vortag_line()`
durch.

## Expected Behavior

- **Input:** `report_type` ∈ {`morning`, `evening`}, `segments`,
  `night_weather` (optional), `tz` — identisch zu den bestehenden
  Renderer-Signaturen, keine neuen Pflichtparameter für Aufrufer.
- **Output:**
  - Morgenbriefing: `N`-Token/-Angabe fehlt in allen drei Kurzformen
    vollständig (kein `N-`, kein Platzhalter, kein „Temp min"-Delta).
  - Abendbriefing: `N`-Token/-Angabe erscheint in allen drei Kurzformen,
    Wert = Tiefstwert aus `night_weather` im Fenster Ankunft→06:00 am
    Etappenziel (nicht das Tagessegment-Minimum).
  - Große E-Mail-Tabelle „🌙 Nacht am Ziel" unverändert in beiden
    Report-Typen (DEC-3, #1313-Verhalten).
- **Side effects:** keine neuen API-Calls (`night_weather` wird bereits für
  beide Report-Typen seit #1313 gefetcht); reine Render-Logik, keine
  Persistenzänderung (DEC-4).

## Acceptance Criteria

- **AC-1:** Given ein Morgenbriefing (`report_type="morning"`) mit
  vorhandenen Segment- und Nachtdaten / When SMS, E-Mail-Kurzzusammenfassung
  und Telegram-Kurzübersicht/-Fußzeile gerendert werden / Then enthält
  KEINE der drei Kurzformen ein `N`-Token bzw. eine Nacht-Min-Angabe (kein
  `N-`, kein `N9`, kein Platzhalter, kein „Temp min"-Delta in
  `_tg_vortag_line`).
  - Test: Drei Renderer-Aufrufe mit identischem Fixture-Trip,
    `report_type="morning"`, gegen den gerenderten Text prüfen, dass kein
    `N`-Token/-Segment vorkommt.

- **AC-2:** Given ein Abendbriefing (`report_type="evening"`) mit
  `night_weather`-Daten am Ziel / When alle drei Kurzformen gerendert
  werden / Then zeigen alle drei ein `N`-Token bzw. eine Nacht-Min-Angabe,
  UND der Wert entspricht `min(t2m_c)` aus `night_weather` im Fenster
  Ankunft→06:00 (NICHT dem Tagessegment-Minimum).
  - Test: Fixture mit künstlich abweichenden Werten — kalte frühe
    Wanderstunde (z.B. 3°C um 6 Uhr am Start) UND milde Nacht am Ziel
    (z.B. 11°C in `night_weather`) — alle drei Kurzformen müssen `11`
    zeigen, nicht `3`.

- **AC-3:** Given identische Trip-/Wetterdaten / When SMS,
  E-Mail-Kurzzusammenfassung und Telegram in Morgen UND Abend gerendert
  werden / Then verhalten sich alle drei Kurzformen konsistent (gleiches
  Sichtbarkeits-Muster, gleicher numerischer Nacht-Min-Wert bei Übereinstimmung).
  - Test: Ein Fixture-Trip, alle drei Renderer je Report-Typ aufrufen,
    extrahierten Nacht-Min-Wert (SMS-Token, Kurzzusammenfassungs-Zahl,
    Telegram-Zahl) auf Gleichheit vergleichen (Abend) bzw. Abwesenheit
    (Morgen).

- **AC-4:** Given ein Briefing (Morgen ODER Abend) mit aktivierter großer
  E-Mail-Nachttabelle (`dc.show_night_block=True`) / When die E-Mail
  gerendert wird / Then bleibt der „🌙 Nacht am Ziel"-Block unverändert in
  Struktur und Inhalt vorhanden — unabhängig vom `N`-Sichtbarkeits-Gate der
  Kurzformen.
  - Test: E-Mail-Rendering (HTML + Plain) vor und nach der Änderung auf
    dasselbe Fixture anwenden, `_extract_night_rows()`-Ausgabe /
    „Nacht am Ziel"-Textblock bleibt bit-identisch in Morgen und Abend.

- **AC-5:** Given ein Bestandstrip ohne jegliche Datenmigration / When die
  drei Kurzformen nach dem Deploy gerendert werden / Then läuft das
  Rendering fehlerfrei durch (kein Schema-/Persistenzfehler) — reine
  Render-Logik-Änderung, alte Trips laden unverändert.
  - Test: Bestehendes Trip-Fixture (unverändertes Format, keine neuen
    Felder) durch alle drei Renderer laufen lassen, kein Exception-Pfad,
    kein KeyError/AttributeError.

- **AC-6:** Given `night_weather=None` (Provider-Fehler/Fetch-Ausfall) im
  Abendbriefing / When die drei Kurzformen gerendert werden / Then stürzt
  kein Renderer ab, und die Nacht-Min-Anzeige fällt fail-soft auf das
  bisherige Tagessegment-Minimum zurück (keine leere/kaputte Ausgabe).
  - Test: Fixture mit `night_weather=None` und vorhandenen
    Segment-Aggregaten, `report_type="evening"` rendern — Nacht-Min-Wert
    entspricht dem alten `day_min`-Verhalten, kein Crash.

## Test-Plan

Kern-Schicht (deterministisch, echte Rendering-Aufrufe, kein Mock-Theater),
neue Testdatei benannt nach Verhalten:
`tests/tdd/test_night_temp_evening_only.py`.

Abdeckung je AC:

| AC | Testfall |
|----|----------|
| AC-1 | `test_n_absent_in_all_three_short_forms_morning` |
| AC-2 | `test_n_from_night_weather_not_day_segment_min_evening` |
| AC-3 | `test_short_forms_consistent_night_min_and_visibility` |
| AC-4 | `test_large_email_night_table_unchanged` |
| AC-5 | `test_legacy_trip_renders_without_migration` |
| AC-6 | `test_night_min_fails_soft_to_day_min_without_night_weather` |

**Betroffene Bestandstests** (aus Kontext-Analyse, strukturelle
Assertion-Änderung, kein Regressionsbug — Golden-/Fixture-Anpassung nötig,
da `N` morgens bisher hart erwartet wurde):

- `test_sms_daywindow_aggregation.py` (Zeilen 317, 427, 499, 527)
- `test_issue_245_sms_stage_colon.py`
- `test_telegram_footer_metric_gating.py`
- `test_issue_831_mobile_einfach.py`
- `test_epic_140_preview_endpoints.py`
- `test_sms_unknown_on_missing_data.py`
- `test_bug305_mobile_email.py`
- `test_sms_preview_matches_sent.py`

**Renderer-Commit-Gate #811 (Pflicht vor Commit):** da `sms_trip.py`,
`compact_summary.py` und `trip_report.py` Mail-Inhalts-Dateien sind,
blockiert `renderer_mail_gate.py` den Commit, bis (1)
`tests/tdd/test_issue_811_mode_matrix.py` grün ist UND (2) ein frischer
`briefing_mail_validator.py`-Lauf gegen eine echte Staging-Testmail
erfolgreich war.

## Known Limitations

- `docs/reference/sms_format.md` §3.2 beschreibt `N` weiterhin als
  Pflicht-Token in der Token-Reihenfolge (§2); die Ergänzung „nur im
  Abendbriefing" ist eine reine Doku-Nachführung (Folgearbeit,
  docs-updater), nicht Teil dieser Implementierung, aber vor Merge
  empfohlen, damit der Vertrag nicht driftet.
- Fail-soft-Fallback (AC-6) verwendet weiterhin das Tagessegment-Minimum,
  wenn `night_weather` fehlt — in diesem Randfall zeigt das Abendbriefing
  dann wieder die „kälteste Wanderstunde" statt der echten Nachttemperatur.
  Das ist bewusst (Verfügbarkeit vor Präzision), kein neuer Bug.
- Scheibe E (TH+:-Bezugstag) und das konfigurierbare Tagesfenster
  (Scheiben B+C, bereits live) sind NICHT Teil dieser Spec.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Kein neues strukturelles Muster — Erweiterung eines
  bestehenden Sichtbarkeits-Gates (`report_type`) um einen Sonderfall ohne
  `MetricSpec`, plus eine kleine geteilte Wert-Ableitungsfunktion
  (`night_temp_min_c()`) nach demselben Filtermuster wie die bereits
  bestehende `_extract_night_rows()`. Keine neue Datenquelle (nutzt das seit
  #1313 ohnehin für beide Report-Typen gefetchte `night_weather`), kein
  neuer Kanal, keine Schema-Änderung.

## Changelog

- 2026-07-23: Initial spec created — Issue #1319 Scheibe D
