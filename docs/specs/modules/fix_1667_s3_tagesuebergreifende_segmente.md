---
entity_id: fix_1667_s3_tagesuebergreifende_segmente
type: bugfix
created: 2026-08-11
updated: 2026-08-11
status: draft
workflow: fix-1667-s3-tagesuebergreifende-segmente
version: "1.0"
tags: [issue-1667, radar-alert, nowcast, segmentauswahl, ortstag, midnight-wrap]
---

# S3 — Tagesübergreifende Segment-Auswahl im Alarm-Pfad

## Approval

- [ ] Approved

## 🔴 Diese Scheibe schließt Issue #1667

S1 (Entschärfung der zeitfensterabhängigen Test-Fixtures — rund 30 zwischen
22:00 und 00:00 UTC reproduzierbar rote Testfunktionen in 13 Dateien behoben
durch den gemeinsamen Helfer `tests/helpers/arrival_window_fixtures.py`, der
in Minuten seit Ortszeit-Mitternacht des Etappentags rechnet; null Zeilen
Produktivcode, Merge `db14acd3`) und S2 (Naismith-Modulo-Wrap, Merge
`8d36dc8c`) sind live. S2 macht Nacht-Ankünfte
*darstellbar* — die Segmente werden korrekt gebaut —, aber die Alarm-Pipeline
findet sie nicht, weil sie ausschließlich den heutigen Kalendertag abfragt. S3
schließt diese Lücke additiv. Danach ist #1667 vollständig behoben.

## Purpose

`TripAlertService.check_radar_alerts()` fragt pro Lauf genau **einen**
Kalendertag ab (`today = trip_local_today(trip, now_utc)`,
`convert_trip_to_segments(trip, today)`, `trip_alert.py:911-913`). Eine
Etappe mit Abendstart und Ankunft nach Mitternacht erzeugt ein Ziel-Segment,
das real bis in den Nachmittag des Folgetags reicht (`trip_segments.py:264-297`,
Tagesfenster-Ende statt fixer 2h-Grenze, Ergebnis von #1584) — aber
`get_stage_for_date` löst strikt per `==` auf (`trip.py:268-272`) und findet
die gestrige Etappe unter dem heutigen Datum nicht.

Zwei gemessene Folgen (Kontext-Dokument, Abschnitt „Ist-Stand, am Code
gemessen"):

| Trip-Form | Verhalten heute | Wirkung |
|---|---|---|
| Ein-Etappen-Trip | `convert_trip_to_segments(trip, today)` liefert `[]` → `continue` | **null Radar-/NowCast-Alarme**, bis zu 11 h 50 min Überwachungsverlust, obwohl korrekt gebaute Segmente existieren |
| Mehr-Etappen-Trip | heutige Etappe liefert Segmente, aber keines ist aktiv ⇒ Vorstart-Regel wählt `segments[0]` der Folgeetappe | **stille Falsch-Ortung**: Nowcast wird für den Startpunkt der *nächsten* Etappe abgerufen, während der Wanderer real noch an der Vortages-Koordinate steht |

Seit #1697 (Ortstag statt Serverdatum, live) und dem dort eingeführten
Horizont-Guard (`trip_alert.py:940-955`, `NOWCAST_HORIZON_MIN=60`) ist der
zweite Befund **verengt, nicht behoben**: Startet die Folgeetappe mehr als
60 min entfernt, unterdrückt der Guard bereits jeden Abruf — reiner
Überwachungsverlust, keine Falsch-Ortung mehr. Nur im letzten
60-Minuten-Fenster vor dem Start der Folgeetappe greift der Guard nicht, und
genau dort wird weiterhin die falsche Koordinate abgefragt.

S3 macht die Segment-Auswahl additiv tagesübergreifend: ein aktives Segment
von gestern gewinnt, solange heute keines aktiv ist — ohne die
Zeitrechnung aus #1584/S2 anzufassen.

## Source

- **File:** `src/services/trip_segments.py`
- **Identifier:** neue Funktionen `select_active_segment`, `resolve_current_segment`

> **Schicht-Hinweis:** reiner Python-Core-Wirkort (`src/services/`,
> `src/app/`) — keine Go-API-, keine Frontend-Berührung. Geprüft per Grep
> auf `check_radar_alerts`/`convert_trip_to_segments`: beide Symbole
> existieren ausschließlich unter `src/`.

## Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/trip_segments.py` | MODIFY | neu: `select_active_segment(segments, now_utc)` (heutige Regel 1:1 extrahiert) und `resolve_current_segment(trip, now_utc, today)` (Vorrangkette, gibt `tuple[TripSegment, date]` zurück) |
| `src/services/trip_alert.py` | MODIFY | `:911-932` auf `resolve_current_segment` umgestellt (Segment **und** dessen Datum); `:1020` `load_dated(trip.id, today)` → `load_dated(trip.id, segment_date)` — das Datum, dem das gewählte Segment tatsächlich entstammt |
| `src/services/trip_report_scheduler.py` | MODIFY | nur Docstring-Korrektur `:1395-1396`: veralteter Verweis „trip_alert.py:730-745" → tatsächliche Fundstelle `:917-955`. **Kein** Vortags-Fallback in `_build_starkregen_hint` (s. Known Limitations) |
| `tests/tdd/test_radar_alert_follows_ortstag.py` | MODIFY (oder neue Geschwisterdatei daneben, gleiche Helfer-Imports) | sechs neue ACs (AC-1…AC-6 dieser Spec) als CI-laufender Nachweis — bewusst **nicht** `tests/unit/` (Begründung: Delta-Messung, Abschnitt „Konsequenz für den Test-Zuschnitt") |

**Nicht angefasst (bewusst):** `api/routers/debug.py:61` (Staging-Debug,
bleibt auf `date_type.today()`), `src/services/corridor_threshold.py` (kein
Produktions-Aufrufer), `src/services/trip_alert.py:518 ff.`
(`_get_cached_weather`/Deviations-Pfad — gleiche Fehlerklasse, anderer Pfad).

## Estimated Scope

- **LoC:** ~190 netto (Limit 250) — ~40-50 Produktivcode (zwei neue
  Funktionen in `trip_segments.py`, Integration in `trip_alert.py`,
  Docstring-Korrektur), ~130-150 Test-LoC (sechs neue ACs nach dem Muster
  der bestehenden Datei: `freeze_time`, `CountingFrameSource`,
  `reset_radar_cache()` je Test)
- **Files:** 3 MODIFY + 1 MODIFY-oder-CREATE (Test)
- **Effort:** medium — die Kernänderung (Vorrangkette) ist klein, der Aufwand
  liegt im Nachweis (sechs voneinander unabhängige Szenarien mit gestellter
  Uhr und Koordinaten-Assertion, keine Zähler-Beweise)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/trip_day.py::trip_local_today` | function | liefert das bereits ortstag-korrigierte „heute" (ADR-0044); „gestern" = `today - 1 Tag` relativ dazu, nie relativ zu einem Serverdatum |
| `src/app/trip.py::Trip.get_stage_for_date` | method | strikte `==`-Auflösung — der Grund, warum „aus gestern wird nie eine Vorschau genommen" strukturell unverletzbar ist: ein Segment von `today - 1` kann bei `now_utc` nie in der Zukunft liegen |
| `src/services/trip_segments.py::convert_trip_to_segments` | function | Baustein für beide Tage (heute UND gestern); unverändert, wird nur zweimal mit unterschiedlichem Datum aufgerufen |
| `src/services/radar_service.py::NOWCAST_HORIZON_MIN` | const | Horizont-Guard (60 min), grenzt das verbleibende Falsch-Ortungsfenster ein — von S3 nicht verändert, nur der Eingang (welches Segment geprüft wird) ändert sich |
| `src/services/weather_snapshot.py::WeatherSnapshotService.load_dated` | method | Schnappschuss-Leser; muss ab S3 das **Segment-Datum** statt `today` bekommen, sonst wird ein frisch gewonnener Alarm still unterdrückt |
| `tests/helpers/nowcast_gate_fixtures.py` | fixture | `make_trip`/`trip_stage`/`CountingFrameSource`/`reset_radar_cache` — bereits für mehrstufige Trips mit exakten Ankunftszeiten erweitert (#1697), keine Duplizierung nötig |
| `tests/tdd/test_radar_alert_follows_ortstag.py` | test | Nachbarwächter (28 Tests, CI-laufend) und Ablageort der neuen ACs; Kollisionsprüfung zeigt: kein bestehender Test dort exerziert den S3-Kernfall (alle Ein-Etappen-Trips oder AC-3, das strukturell nicht kollidiert) |
| `docs/adr/0044-kalendertage-folgen-der-ortszeit.md` | adr | „heute"/„gestern" bestimmen sich nach der Ortszeit der Tour — Grundlage für `today`/`yesterday` in der Vorrangkette |
| `docs/specs/modules/fix_1584_alarm_zeitfenster.md:310-323` | spec | Abgrenzung: ein *konfiguriertes* Tagesfenster über Mitternacht ist am Ziel-Segment bewusst nicht abgebildet — nicht derselbe Fall wie eine *Etappe* mit Ankunft nach Mitternacht; `test_mitternachtsfenster_22_2_klemmt_auf_mindestfenster` bleibt unverändert grün |

## Implementation Details

Zwei Funktionen in `src/services/trip_segments.py`, getrennt entlang der
Asymmetrie ihrer Aufrufer (nur `check_radar_alerts` braucht die
Vorrangkette; die Debug-Route und ggf. der Scheduler brauchen nur die
Basisregel):

```python
def select_active_segment(
    segments: List[TripSegment], now_utc: datetime
) -> Optional[TripSegment]:
    """Heutige Regel 1:1 — aktives Segment, sonst Vorschau auf segments[0]
    (wenn now_utc davor liegt), sonst None."""
    for seg in segments:
        if seg.start_time <= now_utc <= seg.end_time:
            return seg
    if segments and now_utc < segments[0].start_time:
        return segments[0]
    return None
```

```python
def resolve_current_segment(
    trip: "Trip", now_utc: datetime, today: date
) -> Optional[Tuple[TripSegment, date]]:
    """Vorrangkette: (1) aktiv heute -> (2) aktiv gestern -> (3) Vorschau
    heute[0] -> (4) nichts. Liefert das Segment MIT dem Datum, dem es
    entstammt — Aufrufer duerfen dieses Datum nicht durch `today` ersetzen."""
    segments_today = convert_trip_to_segments(trip, today)
    active_today = next(
        (s for s in segments_today if s.start_time <= now_utc <= s.end_time), None
    )
    if active_today is not None:
        return (active_today, today)

    yesterday = today - timedelta(days=1)
    segments_yesterday = convert_trip_to_segments(trip, yesterday)
    active_yesterday = next(
        (s for s in segments_yesterday if s.start_time <= now_utc <= s.end_time), None
    )
    if active_yesterday is not None:
        return (active_yesterday, yesterday)

    preview = select_active_segment(segments_today, now_utc)
    return (preview, today) if preview is not None else None
```

`check_radar_alerts()` (`trip_alert.py:911-932`) ruft `resolve_current_segment`
statt der heutigen Inline-Logik; `active, today = ...` ersetzt `active = ...`,
und `:1020` liest `load_dated(trip.id, today)` mit dem so zurückgegebenen
`today` (das jetzt das Segment-Datum ist, nicht mehr zwingend
`trip_local_today`). Der Horizont-Guard (`:940-955`) bleibt unverändert —
er prüft weiterhin `active.start_time` gegen `now_utc`, unabhängig davon, aus
welchem Tag das Segment stammt.

**Vorrangkette, Begründung „heute gewinnt bei echter Überlappung":**

1. *Fachlich:* Das Ziel-Segment von gestern ist ein **ortsfestes** Fenster an
   der Unterkunft (Startkoordinate = Ankunftspunkt, `trip_segments.py:299-320`).
   Läuft heute ein Segment, ist der Wanderer in Bewegung — diese Koordinate
   ist die informativere.
2. *Technisch:* Solange heute ein aktives Segment existiert, ist das Ergebnis
   **bitgleich** zum Ist-Zustand (`active_today` gewinnt sofort, Stufe 2/3
   werden nie erreicht). Das macht die Änderung additiv und ohne
   Regressionsrisiko für den heutigen Normalfall.

„Gestern" heißt **genau ein Tag** relativ zu dem bereits ortstag-korrigierten
`today` aus `trip_local_today` (`trip_day.py:90-96`) — nicht relativ zu einer
Serveruhr. Der Vortagsbau ist **lazy**: `convert_trip_to_segments(trip,
yesterday)` wird nur aufgerufen, wenn heute kein aktives Segment liefert.

### Verworfene Alternativen

- **`_now_fn`-Naht auf `TripAlertService` statt `freeze_time` in den Tests.**
  Wäre eine **halbe** Uhr: `now_utc`/`today` werden im Alarmpfad an
  mindestens vier Stellen gelesen, dazu `RadarNowcastService._now_fn`
  (`radar_service.py:127`) — eine Naht nur im Alarmdienst ließe Radar-Service
  und Cache auf der echten Uhr laufen. `freeze_time` ersetzt `datetime`/`date`
  global, ist seit S1 Dev-Dependency und wird in `test_radar_alert_follows_ortstag.py`
  bereits für genau diesen Code verwendet.
- **Zusammengeführte Segmentliste (`gestern + heute`) statt Vorrangkette.**
  Degradiert die Regel zu „Listenreihenfolge + `break`": in der Überlappung
  stünde das Ziel-Segment von gestern vorn in der Liste und würde fälschlich
  gewinnen. Die Liste kann die Vorrangregel „heute schlägt gestern bei echter
  Überlappung" strukturell nicht abbilden.
- **Vortags-Fallback im Briefing-Pfad (`_build_starkregen_hint`).**
  `_get_target_date` ist strikt vorwärtsgerichtet (morgens `today`, abends
  `today+1`); Kopfdaten des Briefings kommen aus `trip.get_stage_for_date(target_date)`.
  Ein Vortags-Fallback dort erzeugte ein Briefing mit heutiger Etappe im Kopf
  und gestriger Koordinate im Regenhinweis — ein **neuer**
  Inkonsistenzfehler, keine Reparatur. Live-Überwachung eines noch laufenden
  Vortagssegments ist Aufgabe von `check_radar_alerts` (alle ~15 min), nicht
  der zweimal täglichen Briefing-Erzeugung.
- **Mehrtägige Rückwärtssuche (mehr als ein Tag zurück).** Neuer Scope: ein
  Trip mit Lücken oder eine unbegrenzte Rückwärtssuche ist nicht Teil dieser
  Scheibe. „Gestern" heißt genau ein Tag (AC-5 sichert das als Negativtest ab).

## Expected Behavior

- **Input:** ein Trip mit einer Etappe, deren Ankunft nach Mitternacht des
  Folgetags liegt (Naismith-Modulo-Wrap seit S2), sowie der aktuelle
  Zeitpunkt `now_utc` und das ortstag-korrigierte `today`.
- **Output:** `resolve_current_segment` liefert entweder `(Segment, Datum)`
  entlang der Vorrangkette oder `None`. `check_radar_alerts()` fragt den
  Nowcast an den Koordinaten dieses Segments ab und lädt den
  Wetter-Schnappschuss unter demselben Datum, dem das Segment entstammt.
- **Side effects:** Trips, bei denen heute ein aktives Segment existiert,
  verhalten sich **bitgleich** zum Ist-Zustand — S3 ändert im Alltag nichts
  Sichtbares. Erst der Fall „heute nichts aktiv, gestern noch etwas aktiv"
  ändert sich sichtbar: von 0 Alarmen/falscher Koordinate zu korrekten
  Alarmen an der richtigen Koordinate.

## Acceptance Criteria

- **AC-1 (Vorrangkette — Koordinaten-Nachweis):** Given ein Trip mit zwei
  Etappen, bei dem zum Prüfzeitpunkt sowohl ein Segment der heutigen Etappe
  als auch das Ziel-Segment der gestrigen Etappe zeitlich aktiv wären (echte
  Überlappung) / When `check_radar_alerts()` läuft / Then erfolgt der
  Nowcast-Abruf an den Koordinaten des **heutigen** Segments, nicht an denen
  des gestrigen — der Nachweis läuft ausschließlich über die tatsächlich
  abgefragten Koordinaten, nicht über einen Alarm-Zähler (ein reiner
  Zähler-Test hätte eine Falsch-Ortung bei richtigem Alarm nie bemerkt).
  - Test: neue Funktion in `tests/tdd/test_radar_alert_follows_ortstag.py`
    (oder Geschwisterdatei), Aufbau analog `test_ac1_auckland_koordinatennachweis`
    — `freeze_time`, `CountingFrameSource`, Assertion auf `frame_source.calls[0]`.

- **AC-2 (verengtes Falsch-Ortungs-Fenster — richtige Koordinate im
  60-Minuten-Fenster):** Given ein Trip mit einer gestrigen Etappe, deren
  Ziel-Segment zum Prüfzeitpunkt noch aktiv ist, und einer heutigen
  Folgeetappe, deren Start innerhalb von `NOWCAST_HORIZON_MIN` (60 min) vom
  Prüfzeitpunkt entfernt liegt (also **innerhalb** des Horizont-Guards, der
  seit #1697 bei `trip_alert.py:940-955` sitzt) / When `check_radar_alerts()`
  zu diesem Zeitpunkt läuft / Then erfolgt der Nowcast-Abruf an den
  Koordinaten des noch aktiven **gestrigen** Ziel-Segments, nicht an denen
  der Folgeetappe — vor S3 hätte der Horizont-Guard hier nicht gegriffen und
  die Folgeetappen-Koordinaten wären real abgerufen worden, obwohl der
  Wanderer noch an der Vortages-Koordinate steht.
  - Test: neue Funktion, Aufbau analog `test_ac3_das_ehrliche_fenster_waehlt_die_folgetags_etappe`
    (Korsika, realistische Etappenzeiten), aber mit einer zusätzlichen
    gestrigen Etappe und dem Prüfzeitpunkt **innerhalb** statt außerhalb des
    60-Minuten-Fensters; Assertion auf `frame_source.calls[0]` gegen die
    gestrigen Koordinaten.

- **AC-3 (Schnappschuss-Datum folgt dem Segment-Datum — Unterdrückung plus
  Gegenprobe):** Given das gewählte Segment stammt von gestern (Stufe 2 der
  Vorrangkette) und ein Briefing-Schnappschuss mit angekündigtem Regen für
  denselben `segment_id` liegt unter dem **gestrigen** Datum / When
  `check_radar_alerts()` läuft / Then wird der Alarm unterdrückt (der
  Schnappschuss wird gefunden, weil unter dem Segment-Datum statt `today`
  gesucht wird). Gegenprobe im selben Test: liegt **derselbe** Schnappschuss
  ausschließlich unter dem **heutigen** Datum (nicht unter gestern), feuert
  der Alarm trotz des dort angekündigten Regens — ohne diese Kopplung wäre
  S3 in genau dem Fall wirkungslos, für den es gebaut wird (ein gerade
  gewonnener Alarm würde vom Schnappschuss des falschen Tages still
  unterdrückt).
  - Test: neue Funktion, Aufbau analog `test_ac5_segmentwahl_und_schnappschuss_lesen_denselben_ortstag`
    (`tests/tdd/test_radar_alert_follows_ortstag.py:461-524`) — zwei Läufe
    mit `_write_briefing_snapshot`, einmal unter dem Segment-Datum, einmal
    nur unter dem heutigen Datum; Assertion auf `check_radar_alerts()`
    Rückgabewert (Anzahl ausgelöster Alarme).

- **AC-4 (Ein-Etappen-Trip nach Mitternacht — Kernmotivation):** Given ein
  Trip mit genau einer Etappe, deren Start bei ca. 22:00 Ortszeit liegt und
  deren kumulierte Naismith-Gehzeit über Mitternacht des Folgetags reicht
  (Modulo-Wrap aus S2) / When `check_radar_alerts()` zu einem Zeitpunkt nach
  Mitternacht, aber noch innerhalb des berechneten Ziel-Segment-Fensters
  läuft / Then erfolgt ein Nowcast-Abruf an den Koordinaten des Ziel-Segments
  (statt der heutigen 0 Alarme) UND außerhalb dieses Fensters (vor Start bzw.
  nach `window_end`) bleibt es bei 0 Abrufen — sowohl Koordinaten- als auch
  Zeitfenster-Nachweis in einem Test.
  - Test: neue Funktion, Ein-Etappen-Fixture mit `arrival_start="22:00"` und
    Wegpunkten, deren Gehzeit den Mitternachts-Wrap auslöst; zwei
    `freeze_time`-Zeitpunkte im selben Test (innerhalb/außerhalb des
    Ziel-Segment-Fensters), Assertion auf `frame_source.calls`.

- **AC-5 (Rückwärts-Suche genau einen Tag — Negativtest):** Given ein Trip,
  dessen letzte Etappe vor **zwei** Kalendertagen endete (eine echte Lücke
  von mindestens einem vollständigen dazwischenliegenden Tag ohne Etappe) /
  When `check_radar_alerts()` heute läuft / Then wird **kein** Nowcast-Abruf
  ausgelöst — die Vorrangkette schaut nur genau einen Tag zurück, keine
  mehrtägige Rückwärtssuche.
  - Test: neue Funktion, Trip mit `stage_date = heute - 2 Tage`, keine
    weitere Etappe; Assertion `frame_source.calls == []`.

- **AC-6 (Bestandsschutz):** Given die zwölf #1584-Tests in
  `tests/unit/test_alarm_zeitfenster_ziel.py` (insbesondere
  `test_mitternachtsfenster_22_2_klemmt_auf_mindestfenster`) und alle sieben
  bestehenden Tests in `tests/tdd/test_radar_alert_follows_ortstag.py` / When
  sie nach der S3-Änderung erneut laufen / Then bleiben alle unverändert
  grün — Voraussetzung: S3 führt nirgends „Fensterende auf den Folgetag
  schieben" ein, sondern übernimmt Segmente unverändert so, wie
  `convert_trip_to_segments` sie baut.
  - Test: bestehende Testdateien unverändert im Kernlauf mitführen,
    `uv run pytest tests/unit/test_alarm_zeitfenster_ziel.py
    tests/tdd/test_radar_alert_follows_ortstag.py` (konkret benannte
    Dateien, s. CLAUDE.md „Breiter Testlauf gesperrt"); Assert Exit 0 ohne
    Anpassung an diesen Dateien.

## Darf nicht brechen

- `tests/unit/test_alarm_zeitfenster_ziel.py` — alle zwölf #1584-Tests,
  namentlich `test_mitternachtsfenster_22_2_klemmt_auf_mindestfenster`
  (PO-Entscheidung 2026-08-08) und
  `test_radarpfad_spaetankunft_faellt_nicht_in_alle_segmente_vorbei`.
- `tests/tdd/test_radar_alert_follows_ortstag.py` — alle sieben bestehenden
  Tests (AC-1…AC-5, F001, F002), insbesondere AC-3
  (`test_ac3_das_ehrliche_fenster_waehlt_die_folgetags_etappe`) — nachgerechnet
  in der Delta-Messung: bleibt grün, weil um 22:30 UTC auch das Ziel-Segment
  des Vortags dort bereits seit 5,5 h vorbei ist und Stufe (2) der
  Vorrangkette folglich nicht greift.
- `tests/unit/test_arrival_window_fixtures.py` (10 Tests) und
  `tests/tdd/test_fixture_wallclock_ratchet.py` (13 Tests) — S1-Bestand,
  von S3 nicht berührt, aber im selben Alarmpfad.
- `tests/tdd/test_naismith_midnight_wrap_segments.py`,
  `test_naismith_hhmm_wrap_parity.py` — S2-Bestand.
- `tests/tdd/test_starkregen_kurzfristhinweis.py:277-626` (AC-1…AC-8) —
  Briefing-Starkregenhinweis; S3 ändert dort nur den Docstring, keine Logik.

## Known Limitations

- **Briefing-Pfad (`_build_starkregen_hint`) bekommt keinen
  Vortags-Fallback.** Begründung s. „Verworfene Alternativen". Dort bleibt
  nur die Docstring-Korrektur `trip_report_scheduler.py:1395-1396`.
- **Doppel-Alarm-Guard-Schlüssel `precip:{segment_id}`
  (`trip_alert.py:1037`) kollidiert über den Tageswechsel.** Ein Segment mit
  `segment_id="Ziel"` von gestern und ein gleichnamiges Segment von heute
  teilen sich denselben Guard-Schlüssel — begrenzt auf ein Cooldown-Fenster,
  benannt statt repariert (eigener Scope).
- **`api/routers/debug.py:61`** bleibt auf `date_type.today()` — reine
  Staging-Debug-Route, von #1697 bereits nicht umgestellt, aus dem Scope
  dieser Scheibe.
- **`corridor_threshold.evaluate_corridor_thresholds` hat keinen
  Produktions-Aufrufer** — nicht anfassen, wäre unbelegbare Arbeit.
- **Sehr lange Nacht-Etappen** (Ankunft nach dem Folgetags-Fensterende,
  Gehzeit > 21 h ab 22:00-Start) behalten das 1-h-Mindestfenster — das ist
  die von #1584 AC-3 abgenommene Spätankunfts-Behandlung, kein neuer Mangel.
- **`_get_cached_weather`/Deviations-Pfad** (`trip_alert.py:518 ff.`) lädt
  ebenfalls nur den heutigen Schnappschuss — gleiche Fehlerklasse, anderer
  Pfad, nicht S3.
- **Oberhalb des 60-Minuten-Horizonts** bleibt reiner Überwachungsverlust
  ohne Falsch-Ortungs-Risiko bestehen, bis der Nowcast-Horizont selbst
  erweitert würde — außerhalb S3.

## Risiken

- **`alert_daily_limit` (`src/services/alert_daily_limit.py:61-74`) ist
  user-scoped, nicht trip-scoped.** Ein Wrap-Trip, der bisher nichts
  verbrauchte (weil er `continue`-te), kann jetzt das geteilte Tagesbudget
  des Nutzers belegen und andere Trips desselben Nutzers verdrängen. Gewollte
  Wirkung (der Trip bekommt jetzt zu Recht Alarme), aber zu benennen.
- **Provider-Last:** unverändert **ein** `get_nowcast`-Call pro Trip pro
  Lauf — die Vorrangkette liefert höchstens ein Segment, nie mehrere.
- **Doppel-Aktivierung ist kein Risiko** bei einer sequenziellen Kette mit
  Kurzschluss (erste zutreffende Stufe gewinnt, keine weiteren Stufen werden
  ausgewertet); der Throttle-Schlüssel ist ohnehin `trip.id`
  (`alert_gate.py:71-111`), nicht das Segment — eine zusammengeführte Liste
  hätte hier zusätzlich die Vorrangregel selbst untergraben (s. „Verworfene
  Alternativen").
- **`check_nowcast_gate` (#1467 S3) bleibt unberührt** — S3 ändert nur, *ob*
  ein Segment überhaupt in die Gate-Prüfung eintritt, nicht die Gate-Logik
  selbst (Ruhezeit → Sperrzeit → Tagesobergrenze).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (wendet ADR-0044 an, führt keine neue Entscheidung ein)
- **Rationale:** ADR-0044 hat bereits akzeptiert, dass „heute"/„morgen" sich
  nach der Ortszeit der Tour bestimmen. S3 fügt dem Alarm-Pfad, der ADR-0044
  seit #1697 bereits anwendet, lediglich einen zusätzlichen, additiven
  Rückgriff auf den unmittelbaren Vortag hinzu — keine neue Zeitquelle, kein
  geänderter Kalendertag-Begriff, keine neue Zone-Auflösung. Die
  Vorrangkette selbst ist eine Produktentscheidung im Sinne der Analyse
  („heute gewinnt bei echter Überlappung"), aber keine, die ein eigenes ADR
  rechtfertigt — sie betrifft ausschließlich die interne Segment-Auswahl
  einer einzelnen Funktion, keine Entscheidungsfläche (Kanäle, Provider,
  Datenmodell, Auth, Editor-Paradigma, Test-/Deploy-Strategie).

## Changelog

- 2026-08-11: Initial spec created (S3, Wiederaufnahme nach #1697 gemäß
  Delta-Messung im Kontext-Dokument)
