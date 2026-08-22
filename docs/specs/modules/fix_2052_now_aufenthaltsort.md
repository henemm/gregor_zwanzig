---
entity_id: fix_2052_now_aufenthaltsort
type: bugfix
created: 2026-08-21
updated: 2026-08-21
status: approved
workflow: fix-2052-now-aufenthaltsort
version: "1.0"
tags: [alerts, radar, nowcast, trip, now, telegram]
---

# `/jetzt` misst am Aufenthaltsort statt am Etappenstart (Issue #2052)

## Approval

- [x] Approved — PO-Freigabe 2026-08-21 (AC-2 Messzeitpunkt und AC-9 Tagesende bestätigt)

## Purpose

Der Telegram-/Mail-Befehl `/now` (Alias `/jetzt`, `TripCommandProcessor._show_now`) fragt den
Radar-Nowcast heute am **ersten Wegpunkt der Etappe** ab (`stage.waypoints[0]`), unabhängig
davon, wo auf der Etappe der Wanderer zum Abfragezeitpunkt tatsächlich steht. Fragt er um 16:00
mitten auf der Etappe „regnet es gleich?", antwortet der Bot für den Ausgangspunkt vom Morgen —
bei einer Tagesetappe von mehreren Kilometern eine irreführende Antwort.

Dieselbe Fehlerklasse wurde für den Alarm- und den Briefing-Pfad bereits in #2017 behoben: dort
liefert der geteilte Baustein `position_at_time()` die zur Fenstermitte interpolierte Position.
Diese Spec verdrahtet **denselben Baustein** an der dritten, bisher unbewachten Fundstelle — mit
einem bewusst **anderen** Zielzeitpunkt: `/jetzt` ist keine Vorwarnung, sondern eine
Sofortabfrage nach dem Ort, an dem der Nutzer *jetzt* steht. Gemessen wird deshalb `now_utc`
selbst, nicht die Fenstermitte eines Vorwarnfensters, das es bei einer Sofortabfrage gar nicht
gibt.

## Source

- **File:** `src/services/trip_command_processor.py`
- **Identifier:** `class TripCommandProcessor` / `def _show_now`
- **Schicht:** Python-Core (`src/services/`) — kein Go, kein Frontend.

## Estimated Scope

- **LoC:** ~180–220 (Änderung in `_show_now` ~25–35 LoC, neuer Testfall ~150–180 LoC für 11 ACs
  inkl. Helfer/Fixtures, ggf. kleine Kommentar-Anpassung am Struktur-Wächter). Unter dem
  Workflow-Limit von 250, kein `loc_limit_override` nötig.
- **Files:** 3–4 (1 modifiziert: `trip_command_processor.py`; 1 neu:
  `tests/tdd/test_jetzt_misst_am_aufenthaltsort.py`; 1 Doku modifiziert:
  `docs/specs/modules/radar_nowcast.md`; ggf. 1 Kommentar-Anpassung:
  `tests/test_success_status_guard.py`, nur falls der Struktur-Wächter rot wird).
- **Effort:** low–medium.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `services.trip_segments.resolve_current_segment` | function | Liefert `(active, segment_date)` bzw. `None` — Segmentwahl bleibt bei `_show_now`, keine neue Auswahllogik |
| `services.trip_segments.position_at_time` | function | Interpolierte Position (lat/lon/Höhe) zu einem Zielzeitpunkt — hier `now_utc` statt Fenstermitte |
| `services.radar_service.RadarNowcastService.get_nowcast` | function | Erhält die interpolierten Koordinaten + normalisierte Höhe statt `waypoints[0]`, `priority="user_briefing"` bleibt unverändert |
| `services.radar_service.RadarNowcastService.format_now_text` | function | Erhält weiterhin `tz`, jetzt aus den interpolierten Koordinaten |
| `utils.timezone.tz_for_coords` | function | Angewandt auf die interpolierten Koordinaten statt auf `waypoints[0]` |
| `app.trip.Trip.get_stage_for_date` | function | Unverändert — liefert `stage`, weiterhin nötig für den Fehlerfall (AC-11) und als Fallback-Quelle für den letzten Wegpunkt (AC-9) |

## Implementation Details

`_show_now` (`trip_command_processor.py:1499-1544`) hat bereits `trip` und `now_utc` und
berechnet `today = trip_local_today(trip, now_utc)`. Das ist exakt, was
`resolve_current_segment(trip, now_utc, today)` verlangt — es entsteht keine neue
Auswahlschicht. Der bestehende `if not stage or not stage.waypoints:`-Fehlerpfad (AC-11) bleibt
komplett unangetastet, `stage` wird zusätzlich als Fallback-Quelle für AC-9 gebraucht.

Ablauf nach der bestehenden Fehlerprüfung, ersetzt `wp = stage.waypoints[0]`:

```python
from services.trip_segments import resolve_current_segment, position_at_time

resolved = resolve_current_segment(trip, now_utc, today)
if resolved is not None:
    active, segment_date = resolved
    try:
        _pos = position_at_time(trip, active, segment_date, now_utc)
    except Exception as e:
        logger.error(
            "Jetzt-Befehl: Positionsbestimmung fuer Trip %s fehlgeschlagen "
            "(%s) -- falle zurueck auf den ersten Wegpunkt der Etappe.",
            trip.id, e,
        )
        _pos = stage.waypoints[0]
else:
    # Vorrangkette liefert None: Etappentag ist abgelaufen (typ. nach 23:00
    # Ortszeit). Der Wanderer ist am Tagesziel, nicht am Etappenstart.
    _pos = stage.waypoints[-1]

wp_elevation_m = (
    int(round(_pos.elevation_m)) if _pos.elevation_m is not None else None
)
```

Die vier bisherigen Verwendungen von `wp.lat`/`wp.lon`/`wp.elevation_m` (`get_nowcast`-Aufruf,
`tz_for_coords`-Aufruf) werden auf `_pos.lat`/`_pos.lon`/`wp_elevation_m` umgestellt.
`priority="user_briefing"` und der Kommentarblock zu #1329 C2 bleiben unverändert stehen (AC-6).

**Zielzeitpunkt bewusst `now_utc`, nicht `now_utc + Offset//2` wie in #2017:** Der Alarm- und
Briefing-Pfad messen zur Mitte des Vorwarnfensters, weil sie eine **Vorwarnung** sind — relevant
ist, wo der Wanderer sein wird, wenn das Ereignis eintritt. `/jetzt` ist keine Vorwarnung; der
Nutzer steht an einem Ort und fragt nach genau diesem Ort. Eine Fenstermitte-Messung könnte
„hier ist es trocken" antworten, während er im Regen steht. Der Zirkelschluss-Vorbehalt aus
#2017 (Onset entsteht erst aus dem Nowcast-Ergebnis, ein fester Zeitpunkt vermeidet den Zirkel)
bleibt gewahrt: `now_utc` ist ein fester, aus dem Ergebnis nicht ableitbarer Wert — er ist so
onset-frei wie die Fenstermitte, nur dichter am tatsächlichen Abfragezeitpunkt.

**Fehlerpfad-Trennung (AC-10):** Der `try` umschließt ausschließlich
`position_at_time(...)`, nicht den nachfolgenden `get_nowcast`-Aufruf — dasselbe Muster wie
`trip_alert.py:1309-1318` (Adversary-Finding F-ADV1 aus #2017): eine fehlschlagende
Positionsbestimmung bekommt eine unterscheidbare Meldung und einen definierten Fallback
(`waypoints[0]`, das bisherige Verhalten), statt unter „Radar nowcast failed" zu verschwinden
oder den Befehl ganz scheitern zu lassen.

**Doku-Nachzug:** `docs/specs/modules/radar_nowcast.md:110-117` beschreibt die
Verfeinerungskette der Alarm-/Briefing-Pfade (`waypoints[0]` → `active.start_point` →
interpolierte Position). Der Abschnitt wird um einen Satz ergänzt, der `/jetzt` als eigenen,
zeitgleich behobenen Pfad nennt — mit dem abweichenden Zielzeitpunkt `now_utc` statt
Fenstermitte, damit die Known Limitation nicht den falschen Eindruck erweckt, alle drei Pfade
maßen inzwischen gleich.

## Expected Behavior

- **Input:** `trip`, `now_utc` (Zeitpunkt der Abfrage) — unverändert die bestehende Signatur von
  `_show_now`.
- **Output:** `CommandResult` mit Nowcast-Text für die interpolierte Position statt für
  `waypoints[0]`; bei fehlender heutiger Etappe unverändert die bestehende Fehlerantwort; bei
  fehlgeschlagener Positionsbestimmung Fallback auf das bisherige Verhalten (`waypoints[0]`).
- **Side effects:** Keine zusätzlichen `get_nowcast()`-Aufrufe — weiterhin genau ein Abruf je
  `/jetzt`-Aufruf. Kein neues Persistenzfeld, keine Migration.

## Test Plan

Neuer Test folgt dem Muster aus `tests/tdd/test_issue_822_radar_nowcast_segment.py`: eine
Zwei-Wegpunkt-Etappe über `tests/helpers/nowcast_gate_fixtures.py::make_trip()`, eine
aufzeichnende `RadarNowcastService`-Subklasse per
`monkeypatch.setattr("services.radar_service.RadarNowcastService", ...)` — `_show_now` importiert
`RadarNowcastService` lokal innerhalb der Methode (`trip_command_processor.py:1511`) und hat
keinen Konstruktor-DI-Seam, siehe `tests/unit/test_radar_budget_and_priority.py:243-248`. Der
Sollwert (erwarteter interpolierter Punkt) wird unabhängig vom Prüfling nachgerechnet, nicht aus
dessen eigener Logik abgeleitet. Kein Netz, kein `Mock()`.

Testdatei (nach Verhalten benannt, nicht nach Issue-Nummer):
`tests/tdd/test_jetzt_misst_am_aufenthaltsort.py`.

**Mitlaufende Wächter:**

- `tests/test_success_status_guard.py:1855` führt für `_show_now` die feste B18-Zahl `1`. Kommt
  durch die neue `try`/`except`-Struktur ein weiterer unzugewiesener Aufruf hinzu, muss die
  Restliste angepasst und die Anpassung im Commit begründet werden — `logger.error(...)` gehört
  in den `except`-Zweig, nie in den Normalpfad.
- `tests/tdd/test_befehlspfade_folgen_ortszone.py` (`test_ac3_jetzt_nimmt_den_wegpunkt_der_ortstag_etappe`,
  `..._nicht_der_systemuhr[jetzt]`) — Etappen dort haben je einen Wegpunkt, Interpolation liefert
  denselben Punkt, muss unverändert grün bleiben.
- `tests/tdd/test_issue_731_unified_commands.py`, `tests/tdd/test_issue_704_telegram_interactive_navigation.py`,
  `tests/unit/test_radar_budget_and_priority.py::test_jetzt_command_uses_user_briefing_priority_explicitly`,
  `tests/tdd/test_feature_656_radar_nowcast.py` — prüfen Routing, Priority oder Text, keine
  Koordinaten; müssen unverändert grün bleiben, dienen als Regressionsschutz.

## Acceptance Criteria

- **AC-1 (Kern):** Given ein Trip mit einer heutigen Etappe, deren aktuelles Segment zum
  Abfragezeitpunkt läuft / When `/jetzt` aufgerufen wird / Then wird der Nowcast an der über
  `resolve_current_segment(trip, now_utc, today)` und `position_at_time()` interpolierten
  Position abgefragt, nicht an `stage.waypoints[0]`.
  - Test: echter `_show_now`-Aufruf mit Zwei-Wegpunkt-Etappe, Assert auf die tatsächlich an
    `get_nowcast()` übergebenen Koordinaten (Aufzeichnungs-Subklasse, kein Mock).

- **AC-2 (Zeitpunkt):** Given eine laufende Etappe / When `/jetzt` aufgerufen wird / Then ist der
  an `position_at_time()` übergebene Zielzeitpunkt `now_utc` selbst — nicht die Fenstermitte
  (`now_utc + RADAR_ONSET_THRESHOLD_MIN // 2` bzw. `+ NOWCAST_HORIZON_MIN // 2`), die Alarm- und
  Briefing-Pfad verwenden. `/jetzt` ist eine Sofortabfrage nach dem Ort, an dem der Nutzer
  **steht**; eine Vorausmessung könnte „trocken" melden, während er im Regen steht. Der
  Zirkelschluss-Vorbehalt aus #2017 bleibt gewahrt, weil `now_utc` nicht aus dem Nowcast-Ergebnis
  ableitbar ist.
  - Test: Zwei-Wegpunkt-Etappe mit unterschiedlichen erwarteten Positionen bei `now_utc` vs.
    `now_utc + Offset//2`; Assert, dass die tatsächlich abgefragten Koordinaten dem `now_utc`-Punkt
    entsprechen, nicht dem Fenstermitte-Punkt.

- **AC-3 (Nicht-Trivialität / Gegenprobe):** Given eine Etappe, deren Zielwegpunkt verschoben
  wird / When `/jetzt` erneut aufgerufen wird / Then verschiebt sich der abgefragte Messpunkt
  mit — UND interpolierter Punkt und `waypoints[0]` unterscheiden sich messbar (Schwelle wie in
  `test_issue_822_radar_nowcast_segment.py:1176-1233`), sonst wäre AC-1 trivial erfüllbar.
  - Test: zwei Läufe mit verschobenem Zielwegpunkt, Assert auf unterschiedliche abgefragte
    Koordinaten; zusätzlicher Assert, dass der interpolierte Punkt > 0.01° vom Startpunkt entfernt
    liegt.

- **AC-4 (Höhe):** Given ein Segment mit unterschiedlicher Höhe an Start- und Endpunkt / When
  `/jetzt` aufgerufen wird / Then wird die Höhe des interpolierten Punktes mitgeführt und **an
  der Aufrufstelle** in `_show_now` auf ganze Meter normalisiert (`int(round(...))`, `None`
  bleibt `None`) — `get_nowcast` führt `elevation_m` roh im Cache-Schlüssel, `1000` vs. `1000.0`
  erzeugte in #1991 zwei Einträge für denselben Punkt.
  - Test: Assert auf den an `get_nowcast(elevation_m=...)` übergebenen Wert — ganzzahlig, gleich
    dem gerundeten interpolierten Höhenwert.

- **AC-5 (Zeitzone):** Given eine laufende Etappe / When `/jetzt` aufgerufen wird / Then wird
  `tz_for_coords()` auf die interpolierten Koordinaten angewandt, nicht mehr auf
  `waypoints[0]` — die Onset-Uhrzeit im Antworttext gilt für den Messpunkt.
  - Test: die an `tz_for_coords()` übergebenen Koordinaten aufzeichnen und gegen den
    interpolierten Punkt prüfen — nicht gegen `waypoints[0]`. (Eine Etappe über eine echte
    Zeitzonengrenze ist als Nachweis NICHT nötig und wäre ein eigener Randfall, siehe
    Known Limitations.)

- **AC-6 (Negativ):** Given ein `/jetzt`-Aufruf / When `get_nowcast()` aufgerufen wird / Then
  bleibt `priority="user_briefing"` unverändert (#1329 C2) — eine Nutzeraktion wird nie
  gedrosselt.
  - Test: `tests/unit/test_radar_budget_and_priority.py::test_jetzt_command_uses_user_briefing_priority_explicitly`
    bleibt unverändert grün (Regressionsschutz, kein neuer Test nötig).

- **AC-7 (Negativ):** Given ein `/jetzt`-Aufruf / When die Etappe für heute aufgelöst wird / Then
  bleibt die Ortstag-Auswahl unverändert (#1402, #1727 S5a, ADR-0044) — der Etappentag bestimmt
  weiterhin, **welche** Etappe gilt; geändert wird nur, **wo auf ihr** gemessen wird. Der
  bestehende Zwei-Zonen-Test muss unverändert grün bleiben.
  - Test: `tests/tdd/test_befehlspfade_folgen_ortszone.py::test_ac3_jetzt_nimmt_den_wegpunkt_der_ortstag_etappe`
    und `..._nicht_der_systemuhr[jetzt]` bleiben unverändert grün (Regressionsschutz).

- **AC-8 (Vorschau, Bitgleichheit):** Given der Nutzer fragt `/jetzt` **vor** dem Start der
  heutigen Etappe / When `resolve_current_segment()` Stufe 3 (Vorschau) greift / Then liefert
  `position_at_time()` den `start_point` — das Ergebnis ist **bitgleich** zum Verhalten vor
  dieser Änderung.
  - Test: `now_utc` vor dem ersten Segment des Tages, Assert auf Koordinaten-Identität mit
    `waypoints[0]` (nicht nur numerische Nähe).

- **AC-9 (Randfall nach Tagesende):** Given `resolve_current_segment()` liefert `None` (der
  Nutzer fragt nach dem Ende des Tagesfensters, typisch nach 23:00 Ortszeit) / When `/jetzt`
  aufgerufen wird / Then wird am **letzten** Wegpunkt der heutigen Etappe gemessen
  (`stage.waypoints[-1]`), nicht am ersten. Begründung: `None` bedeutet in dieser Vorrangkette
  eindeutig „der Etappentag ist abgelaufen" — der Wanderer ist dann am Tagesziel, und
  `waypoints[0]` wäre die volle Etappenlänge daneben.
  - Test: `now_utc` nach Ende des letzten Tagessegments (und nach dem Vortag), Assert auf
    Koordinaten-Identität mit `stage.waypoints[-1]`, nicht `waypoints[0]`.

- **AC-10 (Fehlerpfad):** Given `position_at_time()` wirft wider Erwarten eine Exception / When
  `/jetzt` aufgerufen wird / Then bekommt der Nutzer trotzdem eine Antwort (Rückfall auf
  `waypoints[0]`, das bisherige Verhalten), und der Fehler wird geloggt. Der `try` umschließt
  ausschließlich die Positionsbestimmung, nicht den Nowcast-Abruf — damit die Meldung
  unterscheidbar bleibt (Adversary-Finding F-ADV1 aus #2017). Der `logger`-Aufruf steht im
  `except`-Zweig, nie im Normalpfad.
  - Test: `position_at_time` per `monkeypatch` so präpariert, dass sie wirft; Assert, dass
    `_show_now` trotzdem `success=True` mit Nowcast-Text liefert, mit den Koordinaten von
    `waypoints[0]`; separater Assert, dass ein `logger.error`-Aufruf erfolgte (Caplog), nicht der
    Text-Inhalt allein.

- **AC-11 (Bestandsschutz):** Given ein Trip ohne heutige Etappe / When `/jetzt` aufgerufen
  wird / Then bleibt die bestehende Fehlerantwort („Keine heutige Etappe gefunden…",
  `success=False`) wortgleich erhalten. Im Erfolgsfall bleibt der `🔄 Aktualisieren`-Button mit
  `callback_data: "now"` unverändert erhalten — er hängt am Erfolgspfad, der Fehlerpfad trägt
  heute wie künftig kein `reply_markup`.
  - Test: Trip ohne heutige Stage → Assert auf `success=False` und exakten Fehlertext; zweiter
    Assert im Erfolgsfall auf `reply_markup` mit `callback_data == "now"` (Regressionsschutz,
    bestehender Test `test_issue_704_telegram_interactive_navigation.py` deckt beides bereits).

## Known Limitations

1. **Wandernder Cache-Schlüssel bei `/jetzt`.** Jede `/jetzt`-Abfrage erzeugt jetzt einen
   potenziell neuen Cache-Schlüssel, weil sich die abgefragte Position mit der Zeit ändert (der
   Nutzer bewegt sich auf der geplanten Route). Bei `priority="user_briefing"` unkritisch (nie
   gedrosselt, kein Budget-Wächter betroffen), aber der Effekt ist zu benennen: zwei `/jetzt`-
   Aufrufe kurz hintereinander an verschiedenen Etappenpunkten teilen sich keinen Cache-Treffer
   mehr, selbst wenn sie innerhalb der Cache-TTL liegen.

2. **Vortags-Rückgriff kann spät nachts ein gestriges Ziel-Segment liefern.** Die Vorrangkette
   aus `resolve_current_segment()` (Stufe 2) greift auf das aktive Segment von gestern zurück,
   bevor sie auf `None` fällt. In seltenen Randfällen (aktives Ziel-Segment von gestern reicht
   bis kurz vor Mitternacht) kann `/jetzt` kurz nach Mitternacht noch den gestrigen Zielpunkt
   liefern, statt auf AC-9 (letzter Wegpunkt der heutigen Etappe) zu greifen. Dieses Verhalten
   ist identisch zum Alarm-/Briefing-Pfad aus #2017 und wird hier nicht gesondert behandelt.

3. **`src/services/trip_day.py:41,51` nutzt weiterhin `waypoints[0]`.** Dort zur
   Zeitzonen-Bestimmung des Etappentags, nicht zur Positionsbestimmung für den Nowcast —
   ausdrücklich nicht Teil dieses Tickets (siehe „Bewusst nicht Teil dieses Tickets").

## Bewusst nicht Teil dieses Tickets

- `src/services/trip_day.py:41,51` — nutzt ebenfalls `stage.waypoints[0]`, dort aber zur
  Zeitzonen-Bestimmung des Etappentags. Eigene Frage (Etappe über Zeitzonengrenze), im Ticket
  ausdrücklich ausgeklammert.
- Die Trip-Konfiguration des PO wird nicht angefasst.
- Die Tages-/Ortszonen-Logik von `_show_now` (#1402, #1727 S5a, ADR-0044) bleibt unverändert —
  geändert wird nur der Messpunkt innerhalb der bereits gewählten Etappe, nicht die Auswahl der
  Etappe selbst.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Keine Entscheidungsfläche im Sinne von `docs/adr/README.md` (Kanäle, Provider,
  Datenmodell/Persistenz, Auth, Editor-Paradigma, Test-/Deploy-Strategie) ist berührt — dieselbe
  Begründung wie in `docs/specs/modules/fix_2017_nowcast_messpunkt.md:414-420`. Die Änderung
  verdrahtet einen bereits bestehenden, geteilten Baustein (`position_at_time()`) an einer
  dritten Fundstelle. Die dazugehörige Known Limitation in
  `docs/specs/modules/radar_nowcast.md:106-113` wird um `/jetzt` fortgeschrieben (Scope-Eintrag
  oben), keine neue Grundsatzentscheidung.

## Changelog

- 2026-08-21: Initial spec created (Issue #2052)
