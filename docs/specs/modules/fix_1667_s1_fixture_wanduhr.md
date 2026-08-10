---
entity_id: fix_1667_s1_fixture_wanduhr
type: bugfix
created: 2026-08-10
updated: 2026-08-10
status: draft
workflow: fix-1667-arrival-midnight-wrap
version: "1.0"
tags: [issue-1667, tests, fixtures, day-window, freezegun, radar-alerts]
---

# S1 — Zeitfensterabhängige Test-Fixtures entschärfen (Mitternachts-Wanduhr)

## Approval

- [x] Approved — PO „freigabe" 2026-08-10

## 🔴 Diese Scheibe schließt Issue #1667 NICHT

**S1 hat keine Produktwirkung und keinen Produktivcode-Eingriff.** Sie
entschärft ausschließlich Test-Fixtures, die zwischen ~22:00 und 00:00 UTC
reproduzierbar rot werden. Die zugrundeliegende Sicherheitslücke — ein
Wanderer, der nach Mitternacht ankommt, verliert bis zu 11 h 50 min
Radar-/NowCast-Überwachung ohne jeden Alarm (gemessen in Phase 2, s.
`docs/context/fix-1667-arrival-midnight-wrap.md`, Abschnitt „Die
Sicherheitslücke — gemessen, nicht hergeleitet") — bleibt nach S1
**unverändert offen**. Sie wird erst durch S2 (Klemme → Modulo in
Naismith, drei Sprachen) und S3 (tagesübergreifende Segment-Auswahl)
adressiert. **Aus „die ~30 Tests sind wieder grün" darf nicht geschlossen
werden, dass die Lücke geschlossen ist** — genau diese Verwechslung war der
Auslöser des Tickets: Das Issue benannte als Ursache eine 2h-Regel, die seit
PR #1590 gar nicht mehr existiert, und übersah die tatsächliche,
sicherheitsrelevante 23:59-Klemme in `naismith.py`, weil die sichtbaren
Symptome — abendlich rote Tests — einer anderen, harmlosen Ursache
entspringen (`wp_days[0]` ist strukturell immer 0, s. u.).

**Issue #1667 bleibt nach S1 explizit offen** (PO-Entscheidung
2026-08-10). Schließen erst nach S3.

## Purpose

Zwölf Testdateien mit ~29–31 Testfunktionen bauen ihre Trip-Fixturen, indem
sie `arrival_calculated` direkt als `(now + N h).strftime("%H:%M")` bei
Stage-Datum `now.date()` schreiben — sie umgehen die Naismith-Berechnung
komplett und damit auch deren 23:59-Klemme. Das kollidiert mit einer
zweiten, unabhängigen Eigenschaft des Segmentbaus:
`src/services/trip_segments.py:151-159` erkennt einen Tageswechsel
zwischen zwei Wegpunkten nur bei **strikt fallender** Uhrzeit
(`t < prev`); der **erste** Wegpunkt (`wp_days[0]`) ist dadurch strukturell
immer 0 — ein Rollover *vor* dem ersten Wegpunkt ist im Datenmodell nicht
darstellbar.

Ab 23:00 UTC erzeugt eine `+1h/+4h`-Fixture die Folge `wp0=00:00,
wp1=03:00` — **steigend statt fallend**, also kein erkannter Rollover. Das
Segment wird mit `target_date + wp_days[0]=0` kombiniert und landet damit
23 Stunden in der Vergangenheit; der Guard „alle Segmente vorbei"
(`src/services/trip_alert.py:749-763`) greift, `check_radar_alerts()`
liefert 0 Treffer statt der erwarteten 1. Punktgenau reproduziert:
`tests/tdd/test_alert_urgency.py::test_convective_radar_logs_high` läuft
grün bis 22:59 UTC und rot ab exakt 23:00 UTC (`assert 0 == 1`); bei
`+2h/+4h`-Fixturen liegt die Kippkante bei 22:00 UTC. Ein zweiter,
seltenerer Mechanismus greift um 23:59:59→00:00:01: `date_type.today()`
(`src/services/trip_alert.py:739`) springt bereits auf den Folgetag,
während das Stage-Datum der Fixture beim Vortag bleibt —
`get_stage_for_date()` findet dann nichts mehr.

**🔴 Alternative, geprüft und verworfen:** Naheliegend wäre, das
Stage-Datum aus dem Ankunfts-`datetime` abzuleiten, statt `now.date()` zu
nehmen. **Das löst das Problem nicht.** `wp_days[0]` bleibt strukturell 0,
weil es für den ersten Wegpunkt keinen Vorgänger gibt, an dem eine
fallende Uhrzeit erkannt werden könnte (`prev is None` beim ersten
Durchlauf, `trip_segments.py:151-159`). Ein Rollover *vor* dem ersten
Wegpunkt ist im Datenmodell nicht darstellbar — gleich, welches Datum die
Fixture setzt. Dieser Absatz steht hier, damit die Alternative nicht
erneut versucht wird.

Diese Scheibe ersetzt die Uhrzeit-Arithmetik in allen zwölf Fixturen durch
ein Ankunftsfenster, das **innerhalb desselben Kalendertags monoton
steigt** (02:00–22:00 Ortszeit) — ein im Repo bereits zweimal erprobtes
Muster (`test_952_onset_alert_fidelity.py:125-147`,
`test_issue_1069_tier_channel_gating.py:430-450`). Damit bleibt
`wp_days` immer `[0, 0, …]`, das Segment landet nie in der Vergangenheit,
und die Tests werden von der Wanduhr unabhängig.

## Source

- **Files:** zwölf Testdateien unter `tests/tdd/` und `tests/unit/` (s.
  „Affected Files"), neuer gemeinsamer Helfer unter `tests/helpers/`
- **Identifier:** `_save_radar_trip()`, `_make_trip()`, `_radar_trip()`,
  `_make_active_trip()`, `_save_trip_direct()`, drei Inline-Stellen in
  `test_issue_822_radar_nowcast_segment.py`, zwei `pytest.skip`-Guards

> **Schicht-Hinweis:** Ausschließlich Python-Testcode
> (`tests/tdd/`, `tests/unit/`, `tests/helpers/`) und
> `pyproject.toml` (Dev-Dependency `freezegun`). **Kein** Eingriff in
> `src/`, `api/`, `internal/`, `frontend/`, `cmd/` — das ist die zentrale
> Nicht-Wirkungs-Zusicherung dieser Scheibe (s. AC-6).

## Affected Files

| Datei:Zeile | Helfer | Heutiger Versatz |
|---|---|---|
| `tests/tdd/test_alert_log_metrics.py:115` | `_save_radar_trip()` (Ursprung) | +1h/+4h |
| `tests/tdd/test_alert_urgency.py:175` | `_save_radar_trip()` (bitidentische Kopie) | +1h/+4h |
| `tests/tdd/test_issue_827_radar_throttle_recording.py:38` | `_make_trip()` | +2h/+4h |
| `tests/tdd/test_issue_1070_daily_alert_limit.py:227` | `_make_trip()` | +2h/+4h |
| `tests/tdd/test_alert_channel_threshold.py:214` | `_radar_trip()` | +2h/+4h |
| `tests/tdd/test_issue_883_acute_danger_override.py:76` | `_make_active_trip()` | −1h/+2h |
| `tests/tdd/test_alert_quiet_hours_robustness.py:224` | `_save_trip_direct()` | −1h/+2h |
| `tests/tdd/test_issue_822_radar_nowcast_segment.py:169,713,800` | inline (3×, ohne benannten Helfer) | diverse (−4h/−2h/+2h; −1h/+1h; −1h/+1h) |
| `tests/tdd/test_bundle_791_847_844_alerts.py:196` | inline | −1h/+3h |
| `tests/tdd/test_issue_995_scheduler_pause.py:183-184` | inline (`arr1`/`arr2`) | −1h/+2h |
| `tests/tdd/test_issue_818_radar_briefing_integration.py:401` | `pytest.skip` vor 04:00 UTC (in `test_ac5_past_segment_no_alert_guard_test`, Zeile 386) — zurückbauen | — |
| `tests/unit/test_alarm_zeitfenster_ziel.py:350` | `pytest.skip` in den ersten 3 Min des UTC-Tages — zurückbauen | — |

Alle Zeilenangaben am HEAD `5ea233a4` nachgemessen (Bash `grep -n`/`sed
-n`); zwei Zeilennummern aus dem Briefing waren um 1 verschoben
(`test_issue_818…:401` statt 400, `test_alarm_zeitfenster_ziel.py:350`
statt 349) — hier korrigiert.

## Estimated Scope

- **LoC:** ~110–140 (neuer Helfer `tests/helpers/arrival_window_fixtures.py`
  ~35–45 LoC; zehn Aufrufstellen schrumpfen von je ~6–10 Zeilen
  Uhrzeit-Arithmetik auf 1–3 Zeilen Aufruf, macht die drei Inline-Stellen in
  `test_issue_822_…` und die Umbau-Differenz an den übrigen neun Stellen
  netto positiv aber klein; zwei `pytest.skip`-Rückbauten je ~5-10 Zeilen
  löschen/anpassen; `pyproject.toml` +1 Zeile)
- **Files:** 13 (12 Testdateien + 1 neuer Helfer) + `pyproject.toml`
- **Effort:** medium — reine Mechanik an vielen Stellen, aber mit
  eigenem Zeit-Nahweis-Nachweis (freezegun) pro Fixture zu verifizieren

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `tests/tdd/test_952_onset_alert_fidelity.py::_active_window` (Zeile 125-147) | pattern | Vorbild für die 02:00–22:00-Ortszeit-Klemmung — im Repo bereits erprobt |
| `tests/tdd/test_issue_1069_tier_channel_gating.py::_active_window_now` (Zeile 430-450) | pattern | Zweites, bitidentisches Vorbild — bestätigt, dass das Muster kein Einzelfall ist |
| `src/services/trip_segments.py::convert_trip_to_segments` (Zeile 151-159, `wp_days`) | module | Die Eigenschaft, gegen die entschärft wird — NICHT geändert, nur an ihr Verhalten angepasst |
| `tests/helpers/nowcast_gate_fixtures.py` | module | Bestehender Helfer-Baustein derselben Fixture-Familie (Issue #1467 S3); neuer Helfer fügt sich stilistisch ein (echte Trips/Waypoints, kein Mock), baut aber KEINE gemeinsame Funktion mit ihm, da dessen `make_trip()` bewusst einen ganztägigen 00:00–23:59-Bereich nutzt, nicht das hier gebrauchte Ankunfts-Offset-Muster |
| `freezegun` (neu, Dev-Dependency) | tool | Test-Uhr für den Vorher/Nachher-Nachweis (AC-1); ohne sie ist S1 nur um 23:xx UTC live beweisbar |
| `pytest-socket` (bestehend) | tool | Analogie für die Hauskonvention „fertiges Standardwerkzeug statt Eigenbau", auf die sich die Aufnahme von `freezegun` beruft |

## Implementation Details

**1. Neuer gemeinsamer Helfer `tests/helpers/arrival_window_fixtures.py`**

Enthält eine Funktion (Arbeitsname `active_window_offsets(lat, lon,
start_offset_min, end_offset_min)`), die exakt das Muster aus
`test_952_onset_alert_fidelity.py::_active_window` /
`test_issue_1069_tier_channel_gating.py::_active_window_now` kapselt:
Ortszeit-Fenster um `datetime.now(tz)` herum, auf `02:00–22:00 Ortszeit`
geklemmt, `HH:MM`-Strings für Start/Ende zurückgegeben. Die zehn
namentlich benannten Aufrufstellen (alle außer den drei Inline-Stellen in
`test_issue_822_…`, die einen dritten Wegpunkt und abweichende
Zeitzonen/Muster verwenden und deshalb nicht ohne Signaturänderung passen)
rufen den Helfer auf, statt die Uhrzeit-Arithmetik lokal zu wiederholen.

```
def active_window_offsets(lat: float, lon: float,
                           start_offset_min: int, end_offset_min: int
                           ) -> tuple[str, str]:
    """Ankunftszeiten fuer zwei Wegpunkte, geklemmt auf 02:00-22:00
    Ortszeit — verhindert den Mitternachts-Rollover-Verlust aus
    trip_segments.py:151-159 (wp_days[0] ist strukturell immer 0).
    Vorbild: test_952_onset_alert_fidelity.py::_active_window."""
    tz = tz_for_coords(lat, lon)
    now_local = datetime.now(tz)
    start = now_local + timedelta(minutes=start_offset_min)
    end = now_local + timedelta(minutes=end_offset_min)
    day_start = now_local.replace(hour=2, minute=0, second=0, microsecond=0)
    day_end = now_local.replace(hour=22, minute=0, second=0, microsecond=0)
    if start < day_start:
        start = day_start
    if end > day_end:
        end = day_end
    if end <= start:
        end = start + timedelta(hours=1)
    return start.strftime("%H:%M"), end.strftime("%H:%M")
```

Aufruf an den zehn Stellen z. B. `test_alert_urgency.py::_save_radar_trip`:

```
arr0, arr1 = active_window_offsets(LAT, LON, 60, 240)  # statt now+1h/+4h
```

Die drei Inline-Stellen in `test_issue_822_radar_nowcast_segment.py` (Zeile
169, 713, 800) rufen dieselbe Funktion mit ihren jeweiligen
Offset-Paaren auf; wo drei Wegpunkte gebraucht werden (Zeile 169:
−4h/−2h/+2h), wird der Helfer zweimal aufgerufen (Start/Mitte,
Mitte/Ende) oder — falls das die Monotonie verletzt — die Fixture bleibt
mit begründetem Kommentar bei lokal geklemmter Arithmetik. **Diese
Entscheidung fällt in der Implementierung, nicht in dieser Spec** —
Leitplanke ist: `wp_days` muss `[0, 0, 0]` bleiben, geprüft durch AC-1/AC-2.

**2. Zwei `pytest.skip`-Rückbauten**

- `test_issue_818_radar_briefing_integration.py:401` — Guard `if
  now.hour < 4: pytest.skip(...)` entfällt; die Fixture in derselben
  Funktion (baut auf `wp1 = now-2h`) wird auf den Helfer umgestellt, womit
  der Zeitumbruch-Grund für den Skip entfällt.
- `tests/unit/test_alarm_zeitfenster_ziel.py:350` — Guard `if
  arrival.date() != date.today(): pytest.skip(...)` entfällt; die Fixture
  (Ankunft `now - 3min`) verliert ihre Abhängigkeit von der UTC-Tagesgrenze,
  weil `arrival` nicht mehr direkt mit `date.today()` verglichen werden
  muss — die Konstruktion nutzt stattdessen ebenfalls ein Wanduhr-robustes
  Muster (Details in der Implementierung, kein neuer AC nötig: AC-4 deckt
  das Ergebnis „kein `pytest.skip` mehr zeitabhängig" bereits ab).

**3. `freezegun` als Dev-Dependency**

`pyproject.toml`, Abschnitt `[dependency-groups].dev` (Zeile 82-88):
Zeile `"freezegun>=1.5.0",` ergänzen, analog zur bestehenden Zeile
`"pytest-socket>=0.8.0",` — Hauskonvention „fertiges Standardwerkzeug statt
Eigenbau" (`freezegun` ist ausdrücklich als Werkzeug für S1 markiert,
Regel-Budget-Prüfdatum s. u.).

## Expected Behavior

- **Input:** Testlauf zu beliebiger Wanduhrzeit, inklusive 22:00–00:00 UTC
  und der Sekunde 23:59:59→00:00:01.
- **Output:** Alle betroffenen ~29-31 Testfunktionen sind zu jeder
  Wanduhrzeit grün (nachgewiesen für die Kippkanten via `freeze_time`,
  s. AC-1/AC-2). Kein `pytest.skip` greift mehr zeitabhängig (AC-4).
- **Side effects:** keine Produktwirkung — `git diff --stat` zeigt null
  Zeilen in `src/`, `api/`, `internal/`, `frontend/` (AC-6).

## Acceptance Criteria

- **AC-1:** Given der Test `test_alert_urgency.py::test_convective_radar_logs_high`
  läuft mit der ursprünglichen (unveränderten) Fixture unter `freeze_time`
  auf `2026-08-10T23:30:00+00:00` / When der Test in diesem Zustand
  ausgeführt wird / Then schlägt er fehl (`assert 0 == 1`) — das ist der
  Vorher-Nachweis der Kippkante bei 23:00 UTC.
  - Test: `freezegun.freeze_time` auf die genannte Uhrzeit setzen, den
    unveränderten Test (vor dem Fixture-Umbau, z. B. am Commit vor dieser
    Änderung oder über eine temporär zurückgesetzte Kopie der Fixture)
    ausführen und den `AssertionError` beobachten. Dieser AC ist der
    Vorher-Teil des Vorher/Nachher-Paars mit AC-2.

- **AC-2:** Given dieselbe Testfunktion nach dem Fixture-Umbau dieser
  Scheibe, wieder unter `freeze_time` auf `2026-08-10T23:30:00+00:00` /
  When der Test ausgeführt wird / Then ist er grün — der Nachweis über die
  gestellte Uhr ist der Kern der Abnahme dieser Scheibe: derselbe Test,
  dieselbe simulierte Zeit, vorher rot, nachher grün.
  - Test: `freezegun.freeze_time("2026-08-10T23:30:00+00:00")` um den
    Testlauf von `test_alert_urgency.py::test_convective_radar_logs_high`
    (nach dem Fixture-Umbau); Assert Exit 0 bzw. `check_radar_alerts()`
    liefert wieder 1 Treffer.

- **AC-3 (Kippkanten):** Given dieselben umgebauten Fixturen aus
  `test_alert_log_metrics.py`/`test_alert_urgency.py` (+1h/+4h-Familie),
  `test_issue_827_radar_throttle_recording.py`/`test_issue_1070_daily_alert_limit.py`/
  `test_alert_channel_threshold.py` (+2h/+4h-Familie) und die
  Datumssprung-Sekunde / When je ein Testlauf unter `freeze_time` auf
  22:59:59 UTC, 23:00:00 UTC (bzw. 21:59:59/22:00:00 für die
  +2h/+4h-Familie) sowie 23:59:59 UTC und 00:00:01 UTC des Folgetags läuft
  / Then bleiben alle vier Zeitpunkte grün — die Kippkanten sind
  abgedeckt, nicht nur ein Einzelzeitpunkt.
  - Test: pro genannter Kippkante ein `freeze_time`-Lauf über mindestens
    eine Fixture aus jeder betroffenen Versatz-Familie (+1h/+4h,
    +2h/+4h, −1h/+2h) sowie eine 23:59:59→00:00:01-Probe über eine der
    beiden vormals überspringenden Dateien (`test_issue_818_…`,
    `test_alarm_zeitfenster_ziel.py`); Assert jeweils Exit 0 ohne Skip.
  - 🔴 **Die drei Familien kippen NICHT aus demselben Grund** — wer das
    übersieht, prüft bei `−1h/+2h` eine Grenze, die es dort nicht gibt:
    - `+1h/+4h` und `+2h/+4h`: **Rollover-Kippkante** bei 23:00 bzw.
      22:00 UTC. Ab dort ist die Folge *steigend* (z.B. `00:00 → 03:00`),
      der Tageswechsel wird nicht erkannt, `wp_days` bleibt `[0,0]`, das
      Segment landet in der Vergangenheit.
    - `−1h/+2h`: **keine Rollover-Kippkante.** Der erste Wegpunkt liegt
      stets vor `now`, die Folge ist damit immer *fallend* (z.B.
      `21:00 → 00:00`), der Rollover greift korrekt und `wp_days` wird
      richtig `[0,1]`. Für diese Familie ist **allein die
      Mitternachtsgrenze 00:00:01 UTC** relevant: `date_type.today()`
      springt auf den neuen Tag, während das Stage-Datum der Fixture beim
      Vortag bleibt ⇒ `get_stage_for_date()` findet nichts ⇒ leere
      Segmentliste. Ein Test dieser Familie an 22:00/23:00 UTC wäre
      **grün aus dem falschen Grund** und bewiese nichts.

- **AC-4 (keine zeitabhängigen Skips mehr):** Given
  `test_issue_818_radar_briefing_integration.py::test_ac5_past_segment_no_alert_guard_test`
  und `test_alarm_zeitfenster_ziel.py` (die Testfunktion um Zeile 350) /
  When beide unter `freeze_time` auf eine Uhrzeit laufen, die vorher den
  jeweiligen `pytest.skip` ausgelöst hätte (z. B. 02:00 UTC bzw. 00:00:30
  UTC) / Then wird kein `pytest.skip` mehr aufgerufen und der Test läuft
  bis zu einem echten Pass/Fail durch.
  - Test: `freeze_time` auf die genannten vormals überspringenden
    Zeitpunkte setzen, `pytest -rs` (zeigt Skip-Gründe) auf beide
    Testfunktionen; Assert keine Zeile mit `SKIPPED` für diese Tests.

- **AC-5 (Mutations-Gegenprobe):** Given der Helfer
  `active_window_offsets()` wird in der 02:00–22:00-Klemmung deaktiviert
  (z. B. `day_start`/`day_end`-Klemmung durch eine No-Op ersetzt, sodass er
  wieder rohe `now + N h`-Werte ohne Tagesgrenze liefert) / When
  `test_alert_urgency.py::test_convective_radar_logs_high` unter
  `freeze_time` auf 23:30 UTC läuft / Then wird der Test wieder rot — die
  Klemmung ist die Zusicherung, die den Fund tatsächlich verhindert, und
  ohne sie fängt kein anderer Test dieselbe Regression.
  - Test: Mutation per Textersetzung (nach CLAUDE.md-Vorgabe: externe
    Sicherungskopie, keine `git checkout/stash/reset`) an
    `active_window_offsets()`, dann `freeze_time("...23:30:00+00:00")` +
    Testlauf; Assert `AssertionError`. Mutation danach zurückspielen.

- **AC-6 (Nicht-Wirkung, Produktivcode unangetastet):** Given der
  vollständige Diff dieser Scheibe / When `git diff --stat
  origin/main...HEAD -- src/ api/ internal/ frontend/ cmd/` ausgeführt wird
  / Then ist die Ausgabe leer (null geänderte Zeilen in Produktivcode) —
  die Scheibe belegt damit selbst, dass sie keine Produktwirkung
  beansprucht.
  - Test: `git diff --stat` gegen den Merge-Basis-Commit über exakt diese
    fünf Verzeichnisse laufen lassen; Assert leere Ausgabe. (Kann als
    manueller Nachweis im PR oder als CI-Schritt erfolgen — kein neuer
    Pytest-Test nötig, da es sich um eine repo-strukturelle Prüfung
    handelt, keine Verhaltensprüfung von Anwendungscode.)

## Known Limitations

- **Die gesamte Produktionslücke bleibt offen.** S1 löst nichts an der
  23:59-Klemme (`naismith.py:54-60`) oder an `wp_days[0]` — beide sind
  Gegenstand von S2/S3. Ein realer Wanderer mit Abendstart verliert
  weiterhin bis zu ~12 h Überwachung ohne Alarm.
- **Nicht alle zehn Fixture-Kopien werden zu EINER Funktion
  zusammengeführt.** Die drei Inline-Stellen in
  `test_issue_822_radar_nowcast_segment.py` behalten möglicherweise lokale
  Arithmetik, wenn der Drei-Wegpunkte-Fall nicht sauber auf den
  Zwei-Wegpunkte-Helfer passt (Entscheidung fällt in der Implementierung).
- **Fixtures außerhalb der Alarm-/Radar-Ecke sind nicht Teil dieser
  Scheibe.** Andere Tests, die `arrival_calculated` mit ähnlicher
  Wanduhr-Abhängigkeit setzen, aber nicht in der Liste der zwölf Dateien
  stehen, wurden nicht durchsucht und bleiben unverändert.
- **`test_issue_822_radar_nowcast_segment.py` behält teils andere
  Zeitzonen/Muster** (Island UTC+0, London UTC+0) — der Helfer wird dort
  ggf. mit anderen Koordinaten aufgerufen, ändert aber nichts an der
  grundsätzlichen 02:00–22:00-Ortszeit-Klemmung.

## Risiko

**Der Fixture-Fix entfernt den einzigen derzeit vorhandenen
Frühwarn-Effekt** für die echte Sicherheitslücke: die abendlich roten
Tests waren bislang das einzige Signal, das überhaupt auf eine
Uhrzeit-Abhängigkeit im Alarm-Pfad hinwies — auch wenn dieses Signal aus
einem harmlosen Testfixture-Artefakt stammte (`wp_days[0]`), nicht aus der
tatsächlichen 23:59-Klemme. Nach S1 gibt es **kein automatisches Signal
mehr**, das auf die verbleibende Lücke hinweist, bis S2/S3 sie mit eigenen,
gezielten Tests abdecken. Dieses Risiko wird bewusst in Kauf genommen,
weil die roten Tests aktuell ein Fixture-Artefakt bewachen und keine
verlässliche Aussage über die echte Lücke treffen — ein rotes Ergebnis um
23:00 UTC beweist nichts über eine Ankunft nach Mitternacht, weil die
Fixture diesen Fall (Ankunft > 23:59 real, geklemmt auf 23:59) gar nicht
konstruiert.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner Testinfrastruktur-Umbau ohne neue
  Architekturentscheidung — keine neue Zeitquelle, kein neuer
  Auflöser, kein Produktivcode-Konsument. `freezegun` als Dev-Dependency
  ist ein Werkzeug-Zusatz, kein Architekturentscheid; das Regel-Budget dazu
  (Prüfdatum 2026-11-08, s. u.) ersetzt kein bestehendes ADR und begründet
  keines.

## Regel-Budget

`freezegun` als Dev-Dependency ist an diese Scheibe gekoppelt.
**Prüfdatum: 2026-11-08 (+90 Tage).** Fang-Beleg bei Einführung: ohne
Test-Uhr ist der Vorher/Nachher-Nachweis aus AC-1/AC-2 nur zwischen ~22:00
und 00:00 UTC live erbringbar — jede andere Verifikation müsste auf die
passende Uhrzeit warten. Am Prüfdatum: hat `freezegun` außerhalb dieser
Scheibe (S2/S3, andere Zeit-abhängige Tests) einen zweiten, unabhängigen
Fang belegt? Kein Fang → Rückbau prüfen (die punktuellen DI-Uhren
`_now_fn` bleiben als Alternative bestehen).

## Changelog

- 2026-08-10: Initial spec created
