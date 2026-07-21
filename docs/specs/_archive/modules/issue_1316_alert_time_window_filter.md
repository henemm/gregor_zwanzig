---
entity_id: issue_1316_alert_time_window_filter
type: bugfix
created: 2026-07-18
updated: 2026-07-18
status: draft
version: "1.0"
tags: [official-alerts, briefing, compare, time-filter]
---

<!-- Issue #1316 -->

# Issue #1316 — Zeitfenster-Filter für amtliche Warnungen

## Approval

- [ ] Approved

## Purpose

Amtliche Warnungen (Vigilance, MeteoAlarm, GeoSphere, Massiv-Sperren) werden
aktuell **ohne jeden Zeitfilter** ausgeliefert — auch dann, wenn ihr
`valid_to` bereits in der Vergangenheit liegt. Im Abend-Briefing (Etappe
**morgen**) erscheinen dadurch Warnungen von heute Nacht, die zum
Versandzeitpunkt seit Stunden abgelaufen sind (Ur-Fall: Gewitter
`00:00–01:00` und `01:00–02:00` im 18:00-Briefing für morgen). Diese Spec
führt eine zentrale, pure Zeitfenster-Filterfunktion ein, die VOR dem
bestehenden Zwei-Pass-Quellen-Dedup angewendet wird, damit abgelaufene
Warnungen weder im Briefing noch im Orts-Vergleich noch im Alert-Pfad
erscheinen.

## Source

- **File:** `src/services/official_alerts/base.py` — `def get_official_alerts_for_location(lat, lon, window_start=None, window_end=None)` (aktuell Zeile 45, ohne Fenster-Parameter), neue Funktion `filter_alerts_to_window(alerts, window_start, window_end)`
- **File:** `src/services/official_alerts/__init__.py` — Re-Export von `filter_alerts_to_window`
- **File:** `src/services/trip_report_scheduler.py` — Aufrufstelle Zeile 764-765 (`sw.official_alerts = get_official_alerts_for_location(*coord)`), erweitert um Etappenfenster

> **Schicht-Hinweis:** Alle betroffenen Dateien sind Python-Core-Backend
> (`src/services/...`), keine Go-API- oder Frontend-Änderung. Kein
> Schicht-Konflikt möglich, da der gesamte amtliche-Warnungen-Pfad
> ausschließlich in Python liegt.

## Estimated Scope

- **LoC:** +80/-20 (inkl. Tests)
- **Files:** 4–6
- **Effort:** medium (geteilte Funktion, 4 Konsumenten: Briefing, Compare, Compare-Alarm, Alert-Pfad — Risiko liegt in der Interaktion mit dem bestehenden Dedup, nicht in der Filterlogik selbst)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `services.official_alerts.base.get_official_alerts_for_location` | function | Bestehende Registry-Abfrage + Zwei-Pass-Dedup (#1086/#1245) — Filter wird hier VOR Pass 1 eingehängt |
| `services.official_alerts.models.OfficialAlert` | dataclass | Liefert `valid_from`/`valid_to` (beide `Optional[datetime]`) als Filtergrundlage |
| `app.models.TripSegment` (`start_time`/`end_time`, UTC) | dataclass | Etappenfenster-Quelle für den Briefing-Aufruf — SSoT #822, keine Neuberechnung |
| `services.trip_segments._convert_trip_to_segments` | function | Erzeugt die `TripSegment`-Liste, aus der `segments[0].start_time`/`segments[-1].end_time` das Fenster bilden |
| `services.comparison_engine` (Zeile 224), `services.compare_official_alert` (Zeile 162), `services.trip_alert` (Zeile 942) | Aufrufer | Bleiben unverändert (kein Fenster übergeben) — profitieren automatisch vom Default-Fenster `[now, ∞)` |
| Renderer-Mail-Gate #811 (`briefing_mail_validator.py`, `tests/tdd/test_issue_811_mode_matrix.py`) | Gate | Mail-Inhalt (Warnblock) ändert sich → Pflicht-Lauf vor Commit, da der Fix `official_alerts`-Renderpfad berührt |

## Implementation Details

### 1. Pure Filterfunktion (`base.py`)

```
def filter_alerts_to_window(
    alerts: list[OfficialAlert],
    window_start: datetime | None,
    window_end: datetime | None,
) -> list[OfficialAlert]:
    """Ueberlappungssemantik: eine Warnung bleibt, wenn ihr Zeitraum das
    Fenster [window_start, window_end] irgendwo schneidet. Warnungen ohne
    valid_from/valid_to bleiben immer erhalten (fail-safe, Quelle liefert
    keine Zeitangabe -> kann nicht sicher als abgelaufen gelten)."""
```

Regeln:
- `alert.valid_to is None` **oder** `alert.valid_from is None` → Warnung bleibt (fail-safe).
- Sonst: bleibt, wenn `alert.valid_to >= window_start` **und** (`window_end is None` **oder** `alert.valid_from <= window_end`) — klassische Intervall-Überlappung, Teilüberlappung reicht.
- Reihenfolge der Eingabeliste bleibt erhalten (keine Sortierung, kein zusätzlicher Dedup-Schritt).

### 2. Erweiterte Signatur + Einhängepunkt (`base.py`)

```
def get_official_alerts_for_location(
    lat: float,
    lon: float,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> list[OfficialAlert]:
    ...
    results = <bestehender Fetch-Loop, unveraendert>
    now = datetime.now(timezone.utc)
    effective_start = max(now, window_start) if window_start is not None else now
    results = filter_alerts_to_window(results, effective_start, window_end)
    # ab hier: bestehender Zwei-Pass-Dedup (Pass 1 / Pass 2) UNVERAENDERT,
    # operiert jetzt auf der bereits gefilterten Liste
```

Kritisch: Der Filter läuft **vor** Pass 1 (beste Quelle je Gefahr) und Pass 2
(Dubletten-Kollaps). Liefe er danach, könnte eine bereits abgelaufene
Level-3-Warnung von Quelle X in Pass 1 als „beste Quelle" für die Gefahr
gewinnen und die gültige Level-2-Warnung von Quelle Y verdrängen — Pass 2
würde die gültige Warnung dann verwerfen, Ergebnis: leerer Warnblock trotz
aktiver Gefahr. Effektives unteres Fenster ist immer `max(now, window_start)`
— eine in der Vergangenheit liegende `window_start` (z.B. Testfall mit
vergangener Etappe) darf `now` nie unterschreiten.

`now` ist **nicht** hart auf `datetime.now()` verdrahtet, sondern über einen
optionalen, testbaren Zeitpunkt-Parameter oder Modul-Function injizierbar
(analog zum bestehenden Muster in `trip_report_scheduler.py`), damit Tests
mit `freezegun`-artigen oder relativen Zeitstempeln arbeiten können statt mit
fixen Kalenderdaten.

### 3. Aufrufstelle Briefing (`trip_report_scheduler.py`, Zeile ~764-765)

```
window_start = segments[0].start_time
window_end = segments[-1].end_time
sw.official_alerts = get_official_alerts_for_location(
    *coord, window_start=window_start, window_end=window_end,
)
```

`segments` ist zu diesem Zeitpunkt in der Methode bereits vorhanden (aus
Schritt 1, `_convert_trip_to_segments`). `start_time`/`end_time` sind laut
`TripSegment`-Dataclass (`app/models.py:322`) UTC-`datetime` — keine weitere
Konvertierung nötig, kein Zugriff auf `TripSegment`-interne Berechnung, reine
Wiederverwendung der SSoT (#822).

### 4. Übrige 3 Aufrufstellen unverändert

`comparison_engine.py:224`, `compare_official_alert.py:162`,
`trip_alert.py:942` rufen `get_official_alerts_for_location(lat, lon)` ohne
Fenster-Argumente auf. Sie erhalten automatisch das Default-Fenster
`[now, ∞)` und damit denselben Fix (keine abgelaufenen Warnungen mehr) ohne
Codeänderung an diesen Stellen.

### 5. MeteoAlarm-Query-Fenster bleibt unangetastet

`meteoalarm.py:213-220` fragt bewusst 23 h rückwärts ab (Sendezeit-Fenster
der Quelle, nicht Gültigkeitsfenster der Warnung). Eine Änderung dieses
Werts auf ≥24 h würde einen API-Fehler auslösen. Der neue Filter arbeitet
ausschließlich auf den bereits abgerufenen Ergebnissen, nicht auf dem
Query-Parameter.

## Expected Behavior

- **Input:** `get_official_alerts_for_location(lat, lon)` ohne Fenster (Default) oder mit `window_start`/`window_end` aus dem Etappenfenster
- **Output:** Liste von `OfficialAlert`, aus der alle Warnungen mit `valid_to < effective_window_start` entfernt sind; Warnungen ohne Zeitangaben bleiben immer enthalten; Dedup-Ergebnis (Pass 1/Pass 2) operiert nur noch auf der gefilterten Menge
- **Side effects:** keine — reine Funktionserweiterung, kein Schema-/Persistenz-Wechsel, kein neuer Netzwerk-Call

## Acceptance Criteria

- **AC-1:** Given ein Abend-Briefing wird um 18:00 für die Etappe **morgen** generiert / When eine amtliche Warnung existiert, deren `valid_to` vor dem Beginn des Etappenfensters von morgen liegt (Ur-Fall: Gewitter heute Nacht 00:00–01:00) / Then erscheint diese Warnung NICHT im Warnblock der Briefing-Mail.
  - Test: Kern-Test mit injiziertem `now`/Etappenfenster relativ zueinander — kein fixes Kalenderdatum. Beweist Verhalten über `get_official_alerts_for_location`-Rückgabewert bzw. gerendertem Warnblock, nicht über Dateiinhalt.

- **AC-2:** Given eine amtliche Warnung überlappt das Etappenfenster nur teilweise (z.B. beginnt vor dem Fensterstart und endet innerhalb des Fensters) / When der Filter angewendet wird / Then bleibt diese Warnung in der Ausgabe erhalten (Teilüberlappung genügt, kein vollständiges Einschließen nötig).
  - Test: Fixture mit `valid_from` vor `window_start`, `valid_to` innerhalb `[window_start, window_end]` — Warnung muss im Ergebnis auftauchen.

- **AC-3:** Given eine amtliche Warnung hat kein `valid_from`/`valid_to` (Quelle liefert keine Zeitangabe) / When der Filter angewendet wird, unabhängig vom übergebenen Fenster / Then bleibt diese Warnung erhalten (fail-safe — keine Zeitangabe darf nie als „abgelaufen" interpretiert werden).
  - Test: Fixture ohne Zeitfelder, Fenster beliebig gesetzt — Warnung erscheint unverändert im Ergebnis.

- **AC-4:** Given `get_official_alerts_for_location(lat, lon)` wird ohne Fenster-Argumente aufgerufen (Compare-, Compare-Alarm- oder Alert-Pfad, alle drei unverändert) / When eine Warnung existiert, deren `valid_to` vor dem aktuellen Zeitpunkt liegt / Then erscheint diese Warnung NICHT im Ergebnis (Default-Fenster `[now, ∞)` behebt denselben Fehler in allen vier Konsumenten).
  - Test: Aufruf ohne Fenster-Parameter mit einer relativ zu `now` bereits abgelaufenen Warnung im Fixture-Fetch — Ergebnis darf sie nicht enthalten.

- **AC-5:** Given zwei Warnungen derselben Gefahr von unterschiedlichen Quellen existieren, eine davon (höheres `level`, Quelle X) ist bereits abgelaufen und die andere (niedrigeres `level`, Quelle Y) ist noch gültig / When `get_official_alerts_for_location` aufgerufen wird / Then erscheint die gültige Warnung von Quelle Y im Ergebnis — die abgelaufene Warnung von Quelle X darf sie nicht über den Zwei-Pass-Dedup (Pass 1: „beste Quelle je Gefahr") verdrängen, weil der Zeitfenster-Filter VOR Pass 1 läuft.
  - Test: Kern-Test reproduziert exakt dieses Interaktionsszenario (Filter-vor-Dedup-Reihenfolge) und beweist am Rückgabewert, dass Quelle Y erhalten bleibt.

- **AC-6:** Given zwei getrennte, nicht-abgelaufene Zeiträume derselben Quelle für dieselbe Gefahr existieren (Ur-Fall #1245, z.B. zwei Vigilance-Hitze-Fenster) / When der neue Zeitfenster-Filter aktiv ist / Then bleibt das bestehende #1245-Verhalten unverändert — beide Perioden erscheinen weiterhin getrennt im Ergebnis (der Filter entfernt nur tatsächlich abgelaufene Perioden, keine gültigen getrennten Perioden derselben Quelle).
  - Test: Regressions-Lauf des bestehenden `test_official_alert_dedup_timespan.py`-Szenarios mit auf injiziertes `now` umgestellten (statt fixen) Zeitstempeln.

- **AC-7:** Given der Briefing-Pfad ruft `get_official_alerts_for_location` auf / When das Fenster übergeben wird / Then stammt es unverändert aus `TripSegment.start_time` (erstes Segment) und `TripSegment.end_time` (letztes Segment) der bereits vorhandenen Segment-Liste (`trip_segments.py`, SSoT #822) — keine parallele Neuberechnung des Etappenfensters.
  - Test: Kern-Test prüft, dass die an `get_official_alerts_for_location` übergebenen Fenstergrenzen exakt den `start_time`/`end_time`-Werten der Segment-Fixture entsprechen (Aufruf-Argumente, kein Dateiinhalt-Check).

- **AC-8:** Given Test-Fixtures für den Zeitfenster-Filter und die bestehende Dedup-Suite / When sie geschrieben bzw. migriert werden / Then verwenden sie ein injiziertes `now` bzw. relative Zeitstempel (z.B. `now + timedelta(...)`) statt fixer Kalenderdaten (die bestehenden Fixtures mit `2026-07-13`/`2026-07-14` liegen zum Zeitpunkt dieser Spec bereits in der Vergangenheit und würden sonst durch reines Zeitverstreichen erneut falsch-negativ bzw. falsch-positiv werden).
  - Test: Statischer Review der migrierten Fixture-Datei(en) — keine `datetime(2026, ...)`-Literale mehr in den zeitfensterrelevanten Testfällen, stattdessen `now`-Parameter/-Fixture.

## Known Limitations

- Test-/On-Demand-Briefing auf eine komplett vergangene Etappe: Das
  Etappenfenster liegt dann vollständig vor `now`, der effektive Fensterstart
  wird auf `now` geklemmt → der Warnblock ist in diesem Fall leer (kein Fehler,
  Folge der Klemm-Invariante `max(now, window_start)`).
- Bereits gemeldete abgelaufene Einträge bleiben im Alert-State stehen (der
  Dedup-/Notification-State ist Key-basiert über den Zeitraum, nicht
  betroffen von diesem Fix — harmlos).
- MeteoAlarm-Sendezeit-Limitation bleibt unverändert: Publikationen, die
  älter als 23 h sind, werden von der Quelle selbst nicht mehr geliefert
  (Query-Fenster, kein Gültigkeits-Fenster) — dieser Fix ändert daran nichts.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (kein neues ADR-Dokument angelegt)
- **Rationale:** Zentraler Fenster-Filter in `base.py` VOR dem Zwei-Pass-Dedup,
  Default-Fenster `[now, ∞)`, statt Filterung je Quelle oder beim Konsumenten
  nach dem Fetch. Begründung (PO-Entscheid 2026-07-18, „zusätzlich auf morgen
  zuschneiden"): Filter je Quelle würde Logik duplizieren und ist für
  MeteoAlarm semantisch unmöglich (dessen Query-Parameter ist die Sendezeit,
  nicht die Gültigkeit). Filter beim Konsumenten nach dem Fetch würde exakt
  die in AC-5 beschriebene Dedup-Interaktion falsch behandeln (abgelaufene
  starke Warnung verdrängt gültige schwächere vor der Filterung) und müsste
  bei jedem künftigen fünften Konsumenten erneut eigens bedacht werden. Die
  Entscheidung ist auf Funktionsebene lokal genug, um kein eigenständiges ADR
  zu rechtfertigen — sie betrifft eine einzelne Funktion, keine
  Systemarchitektur.

## Changelog

- 2026-07-18: Initial spec erstellt — Issue #1316
