---
entity_id: fix_1727_s5b_versandpfade_ortstag
type: bugfix
created: 2026-08-14
updated: 2026-08-14
status: draft
version: "1.0"
tags: [timezone, trip-report-scheduler, scheduler-dispatch-service, compare-preset, issue-1727, issue-1722, adr-0044, adr-0051]
workflow: fix-1727-s5b-versandpfade
---

# Fix #1727 S5b — Versandpfade folgen dem Ortstag der Tour

## Approval

- [ ] Approved — PO-Freigabe ausstehend, 9 ACs auf Deutsch vorgelegt

## Purpose

Neun Fundstellen im Trip- und Ortsvergleichs-Versand bestimmen den Kalendertag weiterhin
über die Serveruhr (`date.today()`) statt über den Ortstag der Tour bzw. des Preset-Orts —
ein Verstoß gegen die bereits akzeptierte ADR-0044. Anders als die vorangegangene Scheibe S5a
(Anzeige-/Befehlspfade) wirken alle neun Stellen dieser Scheibe auf **versendete Inhalte**:
Etappenwahl im Test-Fallback, Wetter-Input, Ausblicks- und Gewitter-Ausblickszeilen, ob ein
Versandfehler-Vermerk überhaupt noch nachgeliefert wird, ob ein Compare-Preset pausiert wird,
Datumsangaben im Mail-/SMS-/Telegram-Präfix und der Zieltag des Compare-Einzelversands. Diese
Scheibe schließt alle neun, indem sie an jeder den geteilten Baustein
`trip_local_today(trip, now_utc)` (bzw. `first_resolvable_tz(locations)` dort, wo es kein
`Trip`-Objekt, sondern mehrere Compare-Orte gibt) einsetzt — keine eigene Kopie der
Zonen-Auflösung.

Zusätzlich zu ADR-0044 (Ortstag statt Servertag) setzt diese Scheibe an sechs der neun
Fundstellen auch Regel 3 aus ADR-0051 um (`now_utc` als Pflichtparameter statt
Systemuhr-Default) — an den übrigen drei (Fundstellen 2, 8, 9) bleibt „jetzt" bewusst eine
interne, aber **vor jedem Netzabruf** liegende Auflösung; das ist der Millisekunden-Fall, für
den ein Pflichtparameter keinen Sicherheitsgewinn bringt (Begründung unten, „Known
Limitations").

## Source

- **File:** `src/services/trip_report_scheduler.py`
  **Identifier:** `select_test_stage` (Zeile 849, Verstoß Zeile 871), `_send_trip_report_outcome`
  (Zeile 1001, Verstoß Zeile 1103), `_clamp_segments_to_today` (Zeile 1696, Verstoß Zeile 1708),
  `_build_stage_trend` (Zeile 1984, Verstoß Zeile 2023), `_collect_future_stage_weather`
  (Zeile 2374, Verstoß Zeile 2416)
- **File:** `src/services/alert_briefing_anchor.py`
  **Identifier:** `briefing_target_day_is_current` (Zeile 144, Verstoß Zeile 169)
- **File:** `src/services/scheduler_dispatch_service.py`
  **Identifier:** `_auto_pause_expired_presets` (Zeile 60, Verstoß Zeile 79),
  `send_one_compare_preset` (Zeile 322, Verstoß Zeile 369)
- **File:** `src/services/notification_service.py`
  **Identifier:** `_target_date_from_report` (Zeile 1711, Verstoß Zeile 1717)
- **Zonen-Auflösung (unverändert nutzen):** `src/services/trip_day.py::trip_local_today(trip,
  now_utc)` (Zeile 90–96), `src/utils/timezone.py::first_resolvable_tz(locations,
  context_label="")` (Zeile 77–99), `src/utils/timezone.py::local_dt(dt, tz)` (Zeile 109–111)
- **Zeilennummern gemessen am Basis-HEAD `1e5e0be9`** (2026-08-14); vgl. ADR-0044s eigene Lehre
  aus veralteten Zeilenangaben.

## Estimated Scope

- **LoC:** Produktivcode ~+70/−30, Bestandstests ~43 geänderte Zeilen (Signaturanpassungen, je
  eine Zeile), neue Tests ~450–600 → **Gesamt ~600–700 → LoC-Override auf 800 einzuholen**,
  sobald die Testfläche steht (Zahlen aus der Kartierung übernommen, nicht neu geschätzt)
- **Files:** 6 Produktivdateien MODIFY (davon 1 rein mechanisch, s. u.), 1 Wächterdatei MODIFY,
  1 ADR MODIFY, ~20 Bestandstestdateien MODIFY, 1 neue Testdatei CREATE
- **Effort:** high — die Einzelrechnung ist pro Stelle klein (bestehender, bereits getesteter
  Baustein), aber fünf der neun Stellen wirken auf tatsächlich versendete Inhalte (Risiko laut
  Kartierung: MEDIUM)

### Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/trip_report_scheduler.py` | MODIFY | Fundstellen 1–5: `now_utc` einmal zu Beginn von `_send_trip_report_outcome` binden und an `select_test_stage`, `_clamp_segments_to_today`, `_build_stage_trend`, `_build_thunder_forecast_from_trend_or_fetch` (reiner Durchreichungs-Helfer, keine eigene Fundstelle) und `_collect_future_stage_weather` durchreichen |
| `src/services/alert_briefing_anchor.py` | MODIFY | Fundstelle 6: `today` wird Pflichtparameter ohne Systemuhr-Rückfall |
| `src/services/scheduler_dispatch_service.py` | MODIFY | Fundstelle 7: `_auto_pause_expired_presets` bekommt `now_utc` + Ortsliste, prüft je Preset gegen `first_resolvable_tz(locations)`; Fundstelle 9: Ortsauflösung in `send_one_compare_preset` vor den `target_date is None`-Zweig gezogen |
| `src/services/dispatch_orchestrator.py` | MODIFY | Fundstelle 7: `pre_pass` reicht sein bereits vorhandenes `now_utc` sowie die in `collect_due` bereits geladene Ortsliste an `_auto_pause_expired_presets` durch |
| `src/services/notification_service.py` | MODIFY | Fundstelle 8: `_target_date_from_report` leitet den Fallback-Tag aus `request.trip_tz` ab |
| `src/services/preview_service.py` | MODIFY | **Rein mechanisch, keine eigene Fundstelle:** die beiden Aufrufstellen `_build_stage_trend(...)`/`_build_thunder_forecast_from_trend_or_fetch(...)` (Zeile 218/222) reichen `now_utc=datetime.now(timezone.utc)` durch, weil die Signaturen der Fundstellen 4/5 sonst nicht mehr aufrufbar wären. Die EIGENE Zonen-Logik der Vorschau (`_resolve_target_date`s `date.today()`, Zeile 94) bleibt unverändert — sie gehört laut ADR-0044-Restliste zu „Vorschau, Werkzeuge", einer späteren Scheibe |
| `tests/test_output_timezone_guard.py` | MODIFY | Neun `KNOWN_VIOLATIONS`-Einträge entfernen (s. AC-8) |
| `docs/adr/0044-kalendertage-folgen-der-ortszeit.md` | MODIFY | „Umgesetzt"/„Noch nicht umgesetzt" nachziehen — die neun Fundstellen standen dort bislang gar nicht (Nebenbefund der Kartierung) |
| ~20 Bestandstestdateien | MODIFY | ~43 Aufrufstellen der geänderten Signaturen, je eine Zeile |
| `tests/tdd/test_<verhalten>.py` | CREATE | Verhaltenstests aller neun Fundstellen, nach Verhalten benannt |

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `services.trip_day.trip_local_today(trip, now_utc)` | module function | Ersetzt `date.today()` an den Fundstellen 1–6, wo ein `Trip`-Objekt vorliegt |
| `utils.timezone.first_resolvable_tz(locations, context_label="")` | module function | Zonenwahl bei mehreren Compare-Orten (Fundstellen 7, 9) — dasselbe Muster wie in #1726 |
| `utils.timezone.local_dt(dt, tz)` | module function | Ortszeit aus `now_utc` + aufgelöster Zone (Fundstelle 8, wo bereits eine `ZoneInfo` vorliegt, kein `Trip`) |
| ADR-0044 (Akzeptiert) | decision | Verlangt Ortstag statt Servertag; die neun Stellen dieser Scheibe standen bislang NICHT in dessen Restliste (Nebenbefund) |
| ADR-0051 Regel 3 (Vorgeschlagen) | decision | Verbietet Systemuhr-Default; an sechs der neun Fundstellen als Pflichtparameter umgesetzt, an dreien (2, 8, 9) bewusst noch nicht (Millisekunden-Fall, s. Known Limitations) |
| `trip_report_scheduler._get_target_date`/`_get_active_trips` (#1724) | pattern | Vorbild „`now_utc` als Pflichtparameter, `trip_local_today` im Rumpf" |
| `scheduler_dispatch_service.run_compare_presets_daily` (#1726) | pattern | Vorbild für Ortsauflösung bei mehreren Compare-Orten über `first_resolvable_tz` |
| `tests/test_output_timezone_guard.py::test_known_violations_only_shrink` | guard | Die neun Einträge müssen im selben Commit entfallen, sonst rot (s. AC-8) |
| `docs/specs/modules/fix_1727_s5a_befehlspfade_ortstag.md` | pattern | Vorgängerscheibe — Vorbild für Aufbau, Nachweisform und den Vorbedingungs-Anker (AC-9) |
| Zwei-/Drei-Zonen-Fixturen aus S5a (`tests/tdd/conftest.py`) | test fixture | Wellington+Korsika sowie Pago Pago/Korsika/Kiritimati — werden wiederverwendet, keine vierte Kopie |

## Implementation Details

Ein Muster, neunmal angewandt — kein neuer Baustein, keine neue Abstraktion:

| Lage am Fundort | Vorgehen | Fundstellen |
|---|---|---|
| `trip` vorhanden, `now_utc` vom Aufrufer erreichbar | `now_utc` Pflichtparameter, `trip_local_today(trip, now_utc)` | 1, 4, 5 |
| `trip` vorhanden, `now_utc` nur intern (vor jedem I/O) | `now_utc` **einmal** oben binden, dann `trip_local_today(trip, now_utc)` | 2 |
| Weder `trip` noch `now_utc` am Fundort | Fertigen Tag vom Aufrufer hereinreichen | 3 |
| `now_utc` liegt ungenutzt am Aufrufort | Durchreichen, `trip_local_today(trip, now_utc)` | 6, 7 |
| Zone bereits als `ZoneInfo` im DTO aufgelöst | `local_dt(now_utc, request.trip_tz).date()` | 8 |
| Mehrere Orte statt eines Trips, Zone auflösbar | Reihenfolge korrigieren, `first_resolvable_tz(locations)` | 7, 9 |

**Fundstellen 1 + 3 (Test-Fallback-Pipeline):**
```python
def select_test_stage(self, trip, report_type, now_utc: datetime):
    today = trip_local_today(trip, now_utc)
    ...

def _clamp_segments_to_today(self, segments, from_date, today: date):
    delta_days = (today - from_date).days
    ...
```
Beide werden ausschließlich aus `_send_trip_report_outcome` heraus aufgerufen; dort ist
`now_utc` nach der Änderung an Fundstelle 2 bereits gebunden.

**Fundstelle 2 — `now_utc` einmal binden statt zweimal implizit auflösen:**
```python
now_utc = datetime.now(timezone.utc)  # jetzt VOR dem if, nicht mehr nur darin
if target_date is None:
    target_date = self._get_target_date(report_type, trip, now_utc)
segments = self._convert_trip_to_segments(trip, target_date)
...
if allow_test_fallback and target_date < trip_local_today(trip, now_utc):
    weather_segments = self._clamp_segments_to_today(
        segments, target_date, trip_local_today(trip, now_utc),
    )
```
Die externe Signatur von `_send_trip_report_outcome` bleibt unverändert — `now_utc` ist eine
lokale Variable, kein neuer Parameter (0 Test-Aufrufstellen).

**Fundstellen 4 + 5 — `now_utc` als Pflichtparameter, durchgereicht durch den
Zwischen-Helfer:**
```python
def _build_stage_trend(self, trip, target_date, now_utc: datetime, tz=None):
    ...
    today = trip_local_today(trip, now_utc)

def _build_thunder_forecast_from_trend_or_fetch(
    self, trip, target_date, now_utc: datetime, tz, multi_day_trend=None, night_weather=None,
):
    ...  # reicht now_utc an _collect_future_stage_weather durch, keine eigene Fundstelle

def _collect_future_stage_weather(self, trip, target_date, now_utc: datetime, wanted_dates=None):
    if trip is None:  # #1498 — Reihenfolge bewusst UNVERÄNDERT: vor der Zonen-Auflösung
        return []
    ...
    today = trip_local_today(trip, now_utc)
```
Zwei Produktiv-Aufrufer je Funktion: `trip_report_scheduler.py` selbst (hat `now_utc` aus
Fundstelle 2 im Scope) und `preview_service.py:218`/`:222` (mechanischer Durchreich, s.
Affected Files).

**Fundstelle 6:**
```python
def briefing_target_day_is_current(target_date, *, today: date) -> bool:  # kein Default mehr
    ...

# Aufrufer trip_report_scheduler.py:538, in _process_pending_markers (hat now_utc UND trip):
if is_dispatch_error and not briefing_target_day_is_current(
    entry.get("date"), today=trip_local_today(trip, now_utc),
):
```

**Fundstelle 7 — Ortsauflösung analog #1726:**
```python
def _auto_pause_expired_presets(presets, user_id, data_root, now_utc, all_locations):
    by_id = {loc.id: loc for loc in all_locations}
    for preset in presets:
        ...
        locations = order_locations_by_ids(all_locations, preset.get("location_ids") or [])
        zone = first_resolvable_tz(locations, context_label=f"Preset {preset.get('id')}")
        heute = local_dt(now_utc, zone).date()
        expired = date.fromisoformat(end_date_str) < heute
```
`pre_pass` (`dispatch_orchestrator.py:146`) hat `now_utc` bereits als Parameter und die
Ortsliste bereits aus `collect_due` im Cache (`self._all_locations`, dort VOR `pre_pass`
geladen) — beides wird durchgereicht statt neu aufgelöst.

Im selben Zug ersetzt `now_iso = now_utc.isoformat()` das heutige
`now_iso = _datetime.utcnow().isoformat() + "Z"` (`scheduler_dispatch_service.py:69`). Das ist
ein **Zeitstempel**, kein Kalendertag — ADR-0044 greift dort nicht, wohl aber ADR-0051 Regel 3,
und `datetime.utcnow()` ist zusätzlich veraltet (naiv, ohne Zone). Der Zeitstempel stammt danach
aus derselben Zeitabfrage wie die Ablauf-Prüfung darüber.

**Fundstelle 8:**
```python
@staticmethod
def _target_date_from_report(report, request: TripReportRequest):
    if report.segments and report.segments[0].segment:
        return report.segments[0].segment.start_time.date()
    return local_dt(datetime.now(timezone.utc), request.trip_tz).date()
```
`request.trip_tz` liegt am DTO bereits als `ZoneInfo` vor (`notification_service.py:68`) —
kein zusätzlicher Parameter nötig.

**Fundstelle 9 — Ortsauflösung vor den Zieltag-Zweig ziehen:**
```python
if all_locations_cache is None:
    all_locations_cache = load_all_locations(user_id=user_id)
locations = order_locations_by_ids(all_locations_cache, preset.get("location_ids") or [])
if not locations:
    raise ValueError(f"Preset {preset_id}: Orte {location_ids} nicht aufloesbar")

if (target_date is None) != (tage_ab_ortstag is None):
    raise ValueError(...)  # unveraendert
if target_date is None:
    target_date = local_dt(datetime.now(timezone.utc), first_resolvable_tz(locations)).date()
    tage_ab_ortstag = 0
```
Der Empfänger-Check (`default_to`) bleibt VOR der Ortsauflösung stehen — seine Position
relativ zur Orte-Prüfung ändert sich damit **nicht**, nur die Orte-Auflösung wandert vor die
`target_date`-Bestimmung, weil sie deren Zone liefert.

## Nicht in dieser Scheibe

- **`send_on_demand_report`** (`trip_report_scheduler.py:966`) — löst intern
  `datetime.now(timezone.utc)` auf und übergibt es an `_get_target_date`; der Tag ist bereits
  **richtig** (Ortstag über `trip_local_today`), es fehlt nur (b) (Zeitpunkt kommt nicht vom
  Aufrufer). **Für Muster A unsichtbar**, weil `datetime.now()` hier ein `tz`-Argument trägt —
  der Wächter-Scanner erkennt nur den Systemuhr-Aufruf ohne Zone. Gehört zusammen mit den
  Fundstellen 2, 8, 9 in die (b)-Folgescheibe im bestehenden Ticket #1727.
- **Die Go-Seite** (225 × `time.Now()`) — unverändert eigener Befund außerhalb dieses Epics.
- **`preview_service.py`s eigene Zonen-Logik** (`_resolve_target_date:94`, `date.today()`) —
  nur die durch Fundstelle 4/5 erzwungene Signatur-Anpassung der beiden Aufrufstellen ist
  Teil dieser Scheibe (s. Affected Files); die Vorschau selbst folgt weiterhin dem Servertag
  und ist Teil der ADR-0044-Restliste „Vorschau, Werkzeuge" (S5c).

## Expected Behavior

- **Input:** ein fälliger Trip-/Compare-Versand (`now_utc` aus dem Scheduler-Zeitpunkt) bzw.
  ein Handversand/Test-Versand ohne Slot-Kontext.
- **Output:** Etappenwahl (Test-Fallback), Wetter-Abruf-Fenster, Ausblicks-/
  Gewitter-Ausblickszeilen, Verfall eines Nachliefer-Vermerks, Auto-Pause eines
  Compare-Presets, das Datum im Mail-/SMS-/Telegram-Präfix sowie Zieltag und Δ-Anker des
  Compare-Einzelversands richten sich nach dem **Ortstag der betroffenen Tour bzw. des ersten
  auflösbaren Preset-Orts** — nicht nach dem Servertag (`Etc/UTC`).
- **Side effects:** `briefings/<id>.json`-Pause-Einträge (Fundstelle 7) werden weiterhin per
  Read-Modify-Write mit Merge geschrieben, kein Replace (BUG-DATALOSS-GR221). Keine Migration
  von Bestandsdaten nötig.

## Acceptance Criteria

- **AC-1:** Given ein Trip-Test-Versand (`allow_test_fallback=True`) für eine Tour in einer
  Zone mit positivem UTC-Offset (z. B. Neuseeland), deren einzige Etappe auf den Servertag D
  fällt, während der ORTSTAG bereits D+1 ist (Mismatch-Fenster 00:00–12:00 UTC) / When
  `select_test_stage` (`trip_report_scheduler.py:849`) die Fallback-Etappe wählt und
  anschließend `_clamp_segments_to_today` (`:1696`) deren Segmentzeiten für den Wetterabruf
  klemmt / Then zählt Etappe D für `select_test_stage` NICHT mehr als „kommend" (sie ist
  ortszeitlich bereits vergangen, der Fallback greift auf die chronologisch früheste Etappe
  zurück), und `_clamp_segments_to_today` verschiebt die Segmentzeiten um
  `trip_local_today(trip, now_utc) - from_date` statt um `date.today() - from_date` Tage — vor
  dem Fix behandelte `s.date >= today` Etappe D fälschlich noch als aktuell, weil `today` den
  Servertag D trug.
  - Test: `freeze_time` im Mismatch-Fenster, Ein-Etappen-Trip-Fixtur mit Etappe D und
    Neuseeland-Wegpunkt; Assertion, dass `select_test_stage(trip, report_type, now_utc)` NICHT
    Etappe D liefert, und dass `_clamp_segments_to_today` mit dem Ortstag-Parameter einen
    anderen Delta liefert als mit dem (falschen) Servertag.

- **AC-2:** Given `_send_trip_report_outcome` (`trip_report_scheduler.py:1001`) läuft für eine
  Tour in einer Zone mit negativem UTC-Offset (z. B. PCT), deren `target_date` bereits
  ortsrichtig aus `_get_target_date` → `trip_local_today` stammt, während der SERVERTAG noch
  einen Tag zurückliegt (Mismatch-Fenster 12:00–24:00 UTC) / When die Zeile 1103 prüft, ob der
  Wetter-Klemm-Zweig greift / Then vergleicht sie `target_date < trip_local_today(trip,
  now_utc)` statt `target_date < date.today()`, wobei `now_utc` EINMAL oben in der Funktion
  gebunden wird (statt bisher nur innerhalb des `if target_date is None:`-Zweigs bei Zeile
  1076 aufgelöst zu werden) — vor dem Fix verglich der Code einen bereits ortsrichtigen
  `target_date` gegen den rohen Servertag, zwei verschiedene Tagesbegriffe im selben
  `<`-Vergleich.
  - Test: `freeze_time` im Mismatch-Fenster, `target_date` auf den (aus Serversicht noch
    nicht erreichten) wahren Ortstag gesetzt; Assertion, dass der Klemm-Zweig NICHT greift,
    obwohl `date.today() > target_date` gälte — er darf nur greifen, wenn `target_date` auch
    ortszeitlich in der Vergangenheit liegt.

- **AC-3:** Given zwischen der `now_utc`-Bindung in `_send_trip_report_outcome` und dem
  Aufruf von `_build_stage_trend` (`:1984`) bzw. dessen Rückfall `_collect_future_stage_weather`
  (`:2374`) liegt ein echter Wetterabruf mit Retry-Backoff (`_fetch_weather`,
  `FETCH_RETRY_ATTEMPTS=2`, `FETCH_RETRY_BACKOFF_SECONDS=1`, je Segment aufsummiert) / When
  beide Funktionen ihren Ausblicks-Horizont über `is_within_forecast_horizon(stage.date,
  today)` prüfen / Then bestimmen beide `today` über den ALS PARAMETER übergebenen `now_utc`
  (`trip_local_today(trip, now_utc)`), NICHT über eine eigene `date.today()`-Auflösung im
  eigenen Funktionskörper — sonst könnte ein langsamer Abruf zwischen Bindung und Aufruf
  bereits den nächsten Ortstag tragen, während `target_date` noch auf dem alten steht (derselbe
  Zwei-Tagesbegriffe-Bruch wie #1697, hier zwischen zwei eigenen `now()`-Aufrufen statt gegen
  die Serveruhr — bereits einmal gemessen und dokumentiert in
  `dispatch_orchestrator.py:157-163` zum strukturgleichen Compare-Pfad). `now_utc` wird dazu
  Pflichtparameter beider Funktionen ohne Default.
  - Test: **Parameter gegen Systemuhr** (Muster S5a-F001, `test_befehlspfade_folgen_ortszone.py`)
    — `freeze_time(X)` setzen und `now_utc=Y` übergeben, wobei X und Y auf **verschiedene
    Ortstage** derselben Trip-Zone fallen; Assertion, dass das Ergebnis dem Ortstag von Y folgt.
    Eine Implementierung, die den Pflichtparameter zwar entgegennimmt, im Rumpf aber
    `date.today()` benutzt, liefert dann den Ortstag von X und macht den Test rot. Das ist die
    einzige Form, die den in diesem AC beschriebenen Mitternachtssprung fängt — eine
    Verzögerungs-Simulation im Wetterabruf prüft nur den Testaufbau, nicht die Zusicherung.

- **AC-4:** Given ein Versandfehler-Vermerk (`reason == "dispatch_error"`) mit Zieltag D
  wartet in `_process_pending_markers` (`trip_report_scheduler.py:495`) auf Nachlieferung, und
  die betroffene Tour liegt in einer Zone, in der Ortstag und Servertag zum Prüfzeitpunkt
  auseinanderfallen / When `briefing_target_day_is_current` (`alert_briefing_anchor.py:144`)
  an Zeile 538 prüft, ob der Vermerk noch aktuell ist / Then erhält die Funktion
  `today=trip_local_today(trip, now_utc)` explizit vom Aufrufer statt intern `heute = today or
  date.today()` aufzulösen — ein Vermerk verfällt (bzw. bleibt gültig) nach dem ORTSTAG der
  Tour; vor dem Fix konnte er im Mismatch-Fenster einen Tag zu früh verfallen oder einen Tag
  zu spät weitergeschleppt werden.
  - Test: `freeze_time` im Mismatch-Fenster, Vermerk mit Zieltag = wahrer Ortstag − 1 (aus
    Ortssicht bereits abgelaufen, aus Serversicht noch aktuell); Assertion auf
    `briefing_target_day_is_current`s Rückgabewert unter dem Ortstag-Parameter gegenüber dem
    (falschen) Servertag-Ergebnis.

- **AC-5:** Given ein Compare-Preset mit `end_date` = Ortstag D des ERSTEN auflösbaren
  Preset-Orts, dessen Zone vom Servertag abweicht (Mismatch-Fenster) / When
  `_auto_pause_expired_presets` (`scheduler_dispatch_service.py:60`), aufgerufen aus `pre_pass`
  (`dispatch_orchestrator.py:146`), prüft, ob das Preset automatisch pausiert wird / Then
  vergleicht die Funktion `end_date` gegen den über `first_resolvable_tz(locations)` (analog
  #1726) und das bereits verfügbare `now_utc` aufgelösten Ortstag — statt gegen `date.today()`;
  vor dem Fix konnte ein Preset im Mismatch-Fenster einen Tag zu früh oder zu spät pausiert
  werden. Der Persistenz-Schreibweg (`save_compare_preset_pause`, Read-Modify-Write mit Merge)
  bleibt unverändert.
  - Test: `freeze_time` im Mismatch-Fenster, Preset mit `end_date` = Ortstag D, erster
    auflösbarer Ort in einer Zone mit deutlichem Offset; Assertion auf `paused_at` in der
    geschriebenen `briefings/<id>.json`-Fixtur, abhängig vom Ortstag statt Servertag.

- **AC-6:** Given ein Trip-Report ohne verwertbare Segmente (`report.segments` leer oder
  `.segment` unbesetzt — der reine Fallback-Fall) wird mit Präfixen versehen / When
  `_apply_prefixes` (`notification_service.py:1671`) über `_target_date_from_report`
  (`:1711`) das Zieldatum für den Präfix-Text ermittelt / Then leitet die Funktion den Tag aus
  `request.trip_tz` ab (`local_dt(datetime.now(timezone.utc), request.trip_tz).date()`) statt
  `_date.today()` zurückzugeben — die Zone liegt am `TripReportRequest`-DTO bereits als
  `ZoneInfo` vor; vor dem Fix trug der Präfix-Text im Mismatch-Fenster das falsche Datum.
  - Test: `freeze_time` im Mismatch-Fenster, `TripReportRequest` mit `trip_tz` einer Zone mit
    deutlichem Offset, leere `report.segments`; Assertion auf das von
    `_target_date_from_report` gelieferte Datum gegen den Ortstag statt den Servertag.

- **AC-7:** Given der Compare-Einzelversand (`send_one_compare_preset`,
  `scheduler_dispatch_service.py:322`) wird OHNE Slot-Kontext aufgerufen (`target_date=None`,
  `tage_ab_ortstag=None` — z. B. Handversand) für ein Preset mit mehreren Orten in
  unterschiedlichen Zonen, dessen erster konfigurierter Ort NICHT auflösbar ist / When der
  `date.today()`-Zweig (Zeile 366–370) greift / Then bestimmt die Funktion den Ortstag über
  `first_resolvable_tz(locations)` — den ERSTEN AUFLÖSBAREN Ort, überspringt also den
  unauflösbaren ersten —, und `target_date` sowie `tage_ab_ortstag=0` stammen aus DERSELBEN
  Zeitabfrage statt aus zwei getrennten (`date.today()` vs. separat behauptetem Versatz 0).
  **Invariante:** der externe Vertrag der Funktion bleibt unverändert — Parameterliste, Typen
  und die Reihenfolge der beiden bestehenden `ValueError`-Pfade zueinander (fehlender
  Empfänger vor unauflösbaren Orten) ändern sich nicht; keine der 67 Aufrufstellen muss
  zwingend angepasst werden.
  - Test: `freeze_time` im Mismatch-Fenster, Preset mit zwei Orten unterschiedlicher Zone
    (erster Ort unauflösbar, zweiter auflösbar), Einzelversand-Aufruf ohne `target_date`;
    Assertion, dass `target_date` den Ortstag des zweiten Orts trägt, und dass beide
    bestehenden `ValueError`-Pfade weiterhin in ihrer bisherigen Reihenfolge zueinander
    auslösen (Empfänger-Fehler bei fehlendem `mail_to` VOR Orte-Fehler bei unauflösbaren IDs).

- **AC-8:** Given alle neun Fundstellen dieser Scheibe sind auf `trip_local_today`/`local_dt`
  umgestellt / When `tests/test_output_timezone_guard.py::test_known_violations_only_shrink`
  läuft / Then sind die neun Einträge
  `src/services/trip_report_scheduler.py::select_test_stage::0`,
  `src/services/trip_report_scheduler.py::_send_trip_report_outcome::0`,
  `src/services/trip_report_scheduler.py::_clamp_segments_to_today::0`,
  `src/services/trip_report_scheduler.py::_build_stage_trend::1`,
  `src/services/trip_report_scheduler.py::_collect_future_stage_weather::0`,
  `src/services/alert_briefing_anchor.py::briefing_target_day_is_current::0`,
  `src/services/scheduler_dispatch_service.py::_auto_pause_expired_presets::0`,
  `src/services/scheduler_dispatch_service.py::send_one_compare_preset::0` und
  `src/services/notification_service.py::_target_date_from_report::0` aus `KNOWN_VIOLATIONS`
  entfernt, und sowohl dieser Test als auch `test_no_unlisted_output_timezone_violations`
  bleiben grün. **Miterledigt werden muss die Ordinal-Rückverschiebung in
  `_build_stage_trend`:** der verbleibende Eintrag `::2` (Ternary-Rückfall zum `tz`-Default,
  bleibt bewusst gelistet) rutscht auf `::1`, sobald der Muster-A-Fund davor entfällt — das ist
  die Gegenbewegung zu der in `tests/test_output_timezone_guard.py:581-586` dokumentierten
  Verschiebung aus #1723. Ohne diese Umbenennung meldet der Wächter `::2` als veraltet **und**
  `::1` als neuen, unbekannten Verstoß, ohne dass sich eine zweite Codestelle geändert hätte.
  - Test: `tests/test_output_timezone_guard.py::test_known_violations_only_shrink` und
    `::test_no_unlisted_output_timezone_violations`.

- **AC-9:** Given eine neue Testfunktion dieser Scheibe behauptet, dass Ortstag und Servertag
  bei ihrer Fixtur auseinanderfallen — der Vorbedingungs-Anker ist Pflicht, keine Kür / When
  der Test seine Hauptzusicherung prüft / Then belegt er das ZUVOR mit einer eigenen
  Vorbedingungs-Assertion (Muster `tests/tdd/test_befehlspfade_folgen_ortszone.py:619-636`:
  `erwartet_parameter != erwartet_systemuhr`, `tag_uhr != tag_param`, `datetime.now(tz=
  timezone.utc) == FROST_UTC`) — ohne sie ist die Hauptzusicherung strukturell nie
  falsifizierbar (#1726 F002). An den Fundstellen **1, 3, 4, 5, 6, 7** — überall dort, wo
  `now_utc` bzw. der fertige Tag künftig als Pflichtparameter hereinkommt — tritt die
  Parameter-gegen-Systemuhr-Probe aus AC-3 **hinzu**, sie ersetzt den Anker nicht. Nur an den
  Fundstellen **2, 8, 9** ist sie strukturell unmöglich, weil „jetzt" dort funktionsintern
  aufgelöst bleibt; dort genügt die (a)-Prüfung „Ortstag ≠ Servertag unter `freeze_time`".
  - Test: nicht automatisierbar; im QA-Bericht zu belegen, dass jede neue Testfunktion dieser
    Scheibe eine solche Vorbedingungs-Assertion trägt (Muster: fix_1727_s5a AC-9).

## Nachweisführung

Vollständig **offline** belegbar (Kern-Schicht): `freeze_time` + In-Memory-`Trip`/`Stage`/
`Waypoint`/`Preset`-Fixturen. Keine Staging-Mail nötig — geprüft wird die Tagesbestimmung,
nicht der Transport.

Verfügbare Mehrzonen-Fixturen (aus S5a übernommen, keine vierte Kopie):

- `_trip_two_zones` (`tests/tdd/conftest.py`) — Wellington + Korsika, zwölf Stunden auseinander
- Drei-Zonen-Fixtur Pago Pago (−11) / Korsika (+2) / Kiritimati (+14) aus S5a
- `tests/unit/test_trip_local_today.py` — Vorbedingungs-Anker-Muster (`:60-63`)

### Nachweis-Grenze dieser Scheibe

Die Parameter-gegen-Systemuhr-Probe (AC-3, Muster S5a-F001) ist **überall dort möglich und
Pflicht, wo ein Pflichtparameter entsteht**: Fundstellen 1, 3, 4, 5, 6, 7. Sie ist die einzige
Form, die „Parameter entgegengenommen, im Rumpf ignoriert" fängt — genau die Lücke, an der in
S5a fünf von sechs Aufrufstellen blind waren.

An den Fundstellen **2, 8 und 9** ist sie strukturell **nicht** möglich, weil „jetzt" dort
funktionsintern aufgelöst bleibt (bewusst, s. Known Limitations) — es gibt keinen Parameter,
den man der Uhr entgegenstellen könnte. Geprüft wird dort ausschließlich (a): unter
`freeze_time` liefert eine Tour bzw. ein Preset-Ort in einer Zone mit deutlichem Offset einen
anderen Ortstag als den Servertag. Das ist falsifizierbar und ausreichend für die Zusicherung,
die diese Scheibe an diesen drei Stellen macht.

## Testbenennung

Testdateien nach Verhalten benennen, nicht nach Issue-Nummer — durchgesetzt von
`test_naming_gate.py`, das neue issue-nummerierte Testdateien hart blockiert. Kein
`test_issue_1727*`-Name. Vorschlag (analog S5a): `tests/tdd/test_versandpfade_folgen_
ortszone.py` als Sammel-Datei für alle neun Fundstellen; eine Aufteilung je Fundstelle ist
ebenso zulässig.

## Known Limitations

**Bekannte Grenzen dieser Scheibe:**

- **Verbleibende Regel-3(b)-Lücke an den Fundstellen 2, 8, 9.** „Jetzt" wird dort weiterhin
  INNERHALB der jeweiligen Funktion aufgelöst, statt als Pflichtparameter hereinzukommen —
  jeweils aber **vor** jedem Netzabruf. Das ist der Millisekunden-Fall: das Zeitfenster
  zwischen Auflösung und Verwendung ist so klein, dass ein Pflichtparameter (mit den
  zugehörigen ~90 Test-Aufrufstellen bei den betroffenen Funktionen) keinen messbaren
  Sicherheitsgewinn brächte. Zusammen mit `send_on_demand_report` bildet diese Lücke die
  (b)-Folgescheibe im bestehenden Ticket #1727 — kein eigenes Issue.
- **Mehrzonen-Touren:** Restfehler = Zonendifferenz zweier benachbarter Etappen an einem
  Wechseltag. Unverändert bewusst offen (ADR-0044, PO-Entscheidung).
- **Ungezählte Menge:** ob unter den 67 Aufrufstellen von `send_one_compare_preset` welche den
  Servertag im `target_date=None`-Pfad ausdrücklich behaupten (z. B. eine Golden-Datei mit
  fest erwartetem Datum). Bei mitteleuropäischen Fixturen fällt der Unterschied meist nicht
  an; vor der Umsetzung ist das auszuzählen, nicht zu schätzen — ein Fund verlangt keine
  Scope-Änderung, nur eine angepasste Fixtur.
- **`preview_service.py`:** die durch Fundstellen 4/5 erzwungene Signaturänderung wird an den
  beiden Aufrufstellen (`:218`/`:222`) mechanisch nachgezogen (`now_utc=datetime.now(
  timezone.utc)`); die EIGENE Zonen-Logik der Vorschau (`_resolve_target_date`) bleibt in
  dieser Scheibe unangetastet und folgt weiterhin dem Servertag.
- **Der Wächter ist blind für `datetime.utcnow()`.** Muster A erkennt `date.today()` und
  `datetime.now()` ohne `tz`, nicht aber `datetime.utcnow()` — deshalb stand
  `scheduler_dispatch_service.py:69` nie in `KNOWN_VIOLATIONS`. Diese Scheibe räumt die eine
  Fundstelle mit auf, erweitert den Detektor aber **nicht**; das gehört zu S5e
  („Detektor + Liste auf null"). Wie viele weitere `utcnow()`-Stellen es gibt, ist **nicht
  gemessen**.
- **`command_log.json`/Persistenz allgemein:** keine der neun Fundstellen dieser Scheibe
  schreibt einen datumsabhängigen Idempotenz-Schlüssel außer Fundstelle 7
  (`briefings/<id>.json::paused_at`, unverändert Read-Modify-Write) — keine Migration nötig.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0044 (Akzeptiert), ADR-0051 (Vorgeschlagen, Regel 3)
- **Rationale:** Setzt die bereits akzeptierte ADR-0044-Entscheidung an neun weiteren, bislang
  in dessen Restliste gar nicht geführten Stellen um — kein offene Produktfrage, ein Bug gegen
  eine getroffene Entscheidung. Folgt zusätzlich Regel 3 aus ADR-0051 dort, wo die Kosten
  gemessen niedrig sind (Fundstellen 1, 3, 4, 5, 6, 7); an den Fundstellen 2, 8, 9 bleibt die
  interne, aber netzabruf-vorgelagerte Auflösung bewusst bestehen (Millisekunden-Fall, s.
  Known Limitations) — diese Scheibe trifft dazu keine neue Design-Entscheidung, sondern
  übernimmt die bereits in der Kartierung getroffene Kosten-Nutzen-Abwägung.

## Changelog

- 2026-08-14: Spec erstellt nach Kartierung `docs/context/fix-1727-s5b-versandpfade.md`
  (Basis-HEAD `1e5e0be9`), Vorbild `docs/specs/modules/fix_1727_s5a_befehlspfade_ortstag.md`.
