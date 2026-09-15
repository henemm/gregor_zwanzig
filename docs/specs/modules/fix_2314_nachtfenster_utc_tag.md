---
entity_id: fix_2314_nachtfenster_utc_tag
type: bugfix
created: 2026-09-15
updated: 2026-09-15
status: implemented
version: "1.0"
tags: [tests, ci, zeitzone, issue-2314]
---

<!-- Issue #2314, zweiter Durchgang — der AC-9-Nachtlauf aus Durchgang 1 (PR #2329) war am
     15.09. um 00:20 UTC trotzdem rot: 60 Fehlschlaege, Schnittmenge mit den alten 144 = 0.
     Ursache: das Teilfenster 00:00-02:30 UTC (Prozesstag != UTC-Tag) war mit dem einzigen
     bisherigen Messwerkzeug (gestellte Uhr, freezegun ohne tz_offset) strukturell nicht
     herstellbar — date.today() liefert unter freeze_time immer den UTC-Tag. -->

# Fix #2314 (Durchgang 2) — Nachtfenster 00:00–02:30 UTC: Fixtures datieren nach UTC-Tag statt Prozesstag

## Approval

- [ ] Approved

## Purpose

Durchgang 1 hat das Teilfenster 22:00–24:00 UTC geheilt (Ortstag der Trip-Koordinaten springt vor
Mitternacht Prozesszone). Der reale Nachtlauf am 15.09. um 00:20 UTC zeigt: es gibt ein **zweites,
bisher unentdecktes Teilfenster** 00:00–02:30 UTC, in dem der **Prozesstag** (Kalendertag der
fixierten Prozesszone `America/St_Johns`, #1402) bereits **gestern** ist, waehrend der **UTC-Tag**
noch **heute** ist. 20 Testdateien datieren Zaehler, Snapshots und Fixture-Provider-Daten am
**UTC-Tag**, wurden in Durchgang 1 aber (folgerichtig fuer das erste Fenster) auf **Ortstag**
umgestellt oder blieben unveraendert auf Prozesstag — beides ist in diesem zweiten Fenster falsch.
Diese Lieferung schliesst das zweite Fenster, indem sie (a) ein Messwerkzeug schafft, mit dem
„Prozesstag != UTC-Tag" zu jeder Tageszeit lokal herstellbar ist, und (b) die betroffenen Fixtures
auf den fachlich richtigen Tag (UTC-Tag fuer Familien A/C, Ortstag fuer Familie B, reine
Uhrzeit-Klemmung fuer Familie D) umstellt — weiterhin ohne Produktivcode anzutasten.

## Source

- **File:** `tests/helpers/ortstag.py` (ERWEITERT um `utc_tag()`), `conftest.py` (Root, ERWEITERT
  um Env-Knopf), `tests/tdd/test_fixture_wallclock_ratchet.py` (ERWEITERT)
- **Identifier:** `utc_tag(*, now_utc: datetime | None = None) -> date` (neu, neben `ortstag()`);
  Env-Variable `GZ_TEST_PROCESS_TZ` in Root-`conftest.py`

> **Schicht-Hinweis:** reines Test-Infrastruktur-Artefakt (`tests/`, Root-`conftest.py`).
> Produktivcode (`src/`, `api/`, `internal/`, `frontend/`) wird ausschliesslich gelesen (als
> Wahrheitsquelle fuer den fachlich richtigen Tag: `trip_day.trip_local_today` fuer Ortstag,
> `forecast_budget._today_utc` / `meteoalarm_budget` fuer UTC-Tag), nicht veraendert.

## Estimated Scope

- **LoC:** deutlich >250 (≈20 Testdateien + 3-4 Helfer + Root-`conftest.py` + Ratschen-Erweiterung)
  — `loc_limit_override 500` vor `/40-tdd-red` setzen.
- **Files:** ≈20 Testdateien (Familien A–D) + `tests/helpers/ortstag.py` (Erweiterung),
  `tests/helpers/strecke_fixtures.py`, `tests/helpers/arrival_window_fixtures.py`,
  `tests/helpers/official_alert_gate_fixtures.py`, `tests/helpers/nowcast_gate_fixtures.py`
  (Helfer-Erweiterungen) + Root-`conftest.py` + `tests/tdd/test_fixture_wallclock_ratchet.py`
  (Ratschen-Erweiterung, kein neues Gate)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `tests/helpers/ortstag.py::ortstag(lat, lon, *, now_utc=None)` (Durchgang 1) | Wahrheitsquelle Ortstag | unveraendert; `utc_tag()` wird als Geschwisterfunktion in dieselbe Datei ergaenzt, gleiches `now_utc`-Muster |
| `src/services/trip_day.py::trip_local_today`/`anchor_tz` (ADR-0044) | Wahrheitsquelle Ortstag | Produkt-Referenz fuer Familie B |
| `src/services/forecast_budget.py::_today_utc` (Zeile 123), `src/services/official_alerts/meteoalarm_budget.py` | Wahrheitsquelle UTC-Tag | Produkt-Referenz fuer Familie A |
| `src/providers/fixture.py:110` | Wahrheitsquelle UTC-Tag | `FixtureProvider` verankert Offline-Daten am UTC-Tag — Referenz fuer Familie C |
| Root-`conftest.py:1-24` (#1402) | ERWEITERT | bekommt den Env-Knopf `GZ_TEST_PROCESS_TZ`; Default-Verhalten (`America/St_Johns` ohne Variable) bleibt exakt bestehen |
| `tests/conftest.py:579-627` + `tests/helpers/wanduhr.py` (`GZ_TEST_WALL_CLOCK_UTC`, #2096) | unveraendert, getrennter Mechanismus | wirkt NICHT zusammen mit dem Zonen-Knopf (Messgrenze, s. Known Limitations) — Familie D nutzt weiterhin ausschliesslich diesen Schalter |
| `tests/tdd/test_fixture_wallclock_ratchet.py` (#1667) | ERWEITERT | muss `utc_tag()` wie `ortstag()` als Wanduhr-Datum erkennen, sonst neue Bypass-Luecke |
| freezegun 1.5.5 | Randbedingung | `freeze_time` ohne `tz_offset` liefert `date.today()` immer als UTC-Tag — Grund, warum der Zonen-Knopf statt eines Uhr-Patches gewaehlt wird |

## Implementation Details

### Neuer Env-Knopf in Root-`conftest.py` (ABSICHTLICHE Aenderung, Abweichung zu AC-4 aus Durchgang 1)

```python
# conftest.py (Root)
import os
import time

os.environ["TZ"] = os.environ.get("GZ_TEST_PROCESS_TZ", "America/St_Johns")
time.tzset()
```

Ohne gesetzte Variable ist das Verhalten **byte-identisch** zu vorher — Default bleibt
`America/St_Johns` (#1402-Waechter unangetastet). Die Aenderung an `conftest.py` selbst ist in
diesem Durchgang **ausdruecklich gewollt** und weicht damit bewusst von AC-4 aus Durchgang 1
("Root-`conftest.py` bleibt unveraendert") ab: der erste Durchgang konnte das Fenster
00:00–02:30 UTC nicht sehen, weil kein Werkzeug existierte, es lokal herzustellen. Kein Eingriff
in freezegun-Interna; `_gestellte_wanduhr`/#2096 bleibt exakt bestehen und unabhaengig.

### Messreferenz: welche Zone traegt wann

Nachweisbedingung zonen-agnostisch: „eine Prozesszone, in der zum Laufzeitpunkt Prozesstag =
UTC-Tag − 1 gilt". Zwei konkrete Zonen:

| Zone | UTC-Offset | Traegt (UTC-Fenster) | Messstand |
|---|---|---|---|
| `Pacific/Marquesas` | −9:30 (Halbstunden-Versatz wie St_Johns, keine Sommerzeit) | 00:00–09:30 | **gemessen** 15.09. 06:39 UTC: 51/51 CI-Tagesfehler reproduziert (inkl. Subprozess-Test); Vollmessung 15.09. ~06:45 UTC: 12027 passed, 62 rot |
| `<-2330>+23:30` (POSIX) / `GZT+23:30` | −23:30 (POSIX-Vorzeichen: `+` = westlich von UTC) | 00:00–23:30 (deckt auch spaete Laeufe ab, die Marquesas nicht traegt) | **noch nicht mit der Suite gemessen** — Einzelmessung 15.09. 07:05 UTC bestaetigt nur den Mechanismus (`date.today()`=2026-09-14 bei UTC-Tag 2026-09-15, `%z` −2330); Vollmessung ist Aufgabe der Implementierung, kein vorab belegter Nachweis |

### Selbstschutz gegen falsches Gruen

Ist `GZ_TEST_PROCESS_TZ` gesetzt, aber zum Laufzeitpunkt gilt zufaellig Prozesstag == UTC-Tag
(Zone traegt gerade nicht, z. B. Marquesas nach 09:30 UTC), muss das sichtbar werden — Abbruch
oder klarer Fehlschlag mit Meldung, nie ein still gruener, aber wirkungsloser Lauf. Umsetzung:
ein Selbsttest, der die Diskrepanz `date.today() != <UTC-Tag>` bei gesetzter Variable aktiv
prueft und bei Gleichheit fehlschlaegt (Zeitpunkt/Zone im Fehlertext).

### Neuer Helfer `utc_tag()` (Geschwister von `ortstag()`)

```python
# tests/helpers/ortstag.py (ERGAENZUNG)
def utc_tag(*, now_utc: datetime | None = None) -> date:
    """Der UTC-Kalendertag, gemessen an now_utc (Default: jetzt).

    Fuer Fixtures, die einen Zaehler oder Cache-Eintrag datieren, den das
    Produkt am UTC-Tag verankert (_today_utc, FixtureProvider). Keine eigene
    Zonenarithmetik — reiner .date()-Zugriff auf einen UTC-Zeitpunkt.
    """
    jetzt = now_utc if now_utc is not None else datetime.now(timezone.utc)
    return jetzt.date()
```

Kein Pflichtparameter noetig (anders als `ortstag`, das echte Koordinaten braucht) — `utc_tag()`
haengt an keiner Ortsangabe.

### Fixes je Familie

**Familie A — Zaehlerdatei (10 Tests, 5 kopierte `_write_budget`):** `tests/unit/
test_forecast_budget_gate.py:122`, `tests/unit/test_meteoalarm_budget_gate.py:28`, `tests/unit/
test_radar_budget_and_priority.py:103`, `tests/unit/test_radar_upstream_failure.py:119`,
`tests/tdd/test_radar_nowcast_health_journal.py:172`. Der Test schreibt den Budget-Zaehler mit
`date.today()` (Prozesstag), das Produkt liest den Zaehler am UTC-Tag (`_today_utc`,
`forecast_budget.py:123`; `meteoalarm_budget`) — im Fenster gilt der Zaehler als „gestern" und
wird 0. Fix: `date.today()` → `utc_tag()`.

**Familie B — Etappe/Snapshot/Marker (≈33 Tests):** Etappe, Wetter-Snapshot oder Zeitanker mit
Prozesstag, Produkt sucht Ortstag (`trip_local_today`). Betroffene Stellen: `_active_trip()`
`test_starkregen_kurzfristhinweis.py:95` (auch `test_alarm_szenario_laufendes_ereignis.py:924`);
`_write_snapshot()` `test_nowcast_briefing_overtake.py:406`, `test_issue_883_acute_danger_
override.py:165`; `schnappschuss_speichern()` `tests/helpers/official_alert_gate_fixtures.py:190`;
`_make_active_trip()` `test_issue_818_radar_briefing_integration.py:100` (inkl. der 7 zusaetzlich
in der Vollmessung gefundenen Tests, die denselben Helfer nutzen); `frozen_active_window()`
`tests/helpers/nowcast_gate_fixtures.py:471`; ≈11 Stellen in `test_briefing_anchor_survives_
dispatch_failure.py`; `test_thunder_next_day_reference_by_report_type.py:79,103`. Fix:
`date.today()` → `ortstag(lat, lon)` mit den Koordinaten des jeweils gebauten Trips — auch in
Snapshot-/Marker-Nebenpfaden, nicht nur an der Etappe selbst; ohne Wegpunkte gilt der bestehende
UTC-Rueckfall aus Durchgang 1.

**Familie C — FixtureProvider (7 Tests):** `src/providers/fixture.py:110` verankert
Offline-Wetterdaten am UTC-Tag. Betroffene Stellen: `test_compare_outlook_day_boundary.py:86,123`,
`test_compare_outlook.py:111`, `test_ausblick_schleife_bewahrt_alle_nachgeruesteten_
kilometrierungen.py:138,179`, `test_stage_weather_endpoint.py:95/161`, `tests/unit/
test_comparison_engine_no_circular_import.py:72`. Fix: `date.today()` → `utc_tag()`. Sonderfall
`test_comparison_engine_no_circular_import.py`: startet einen **frischen Subprozess** und erbt
dort die Prozess-`TZ` (also auch `GZ_TEST_PROCESS_TZ`, sofern als Env-Variable an den Subprozess
weitergereicht) — die Messung aus Durchgang-1-Kontext (51/51 inkl. Subprozess) bestaetigt, dass
der Zonen-Knopf dort wirkt; gesondert benannt, weil ein Session-`freeze_time` dort NICHT wirken
wuerde (Unterschied zum Uhr-Schalter).

**Familie D — Uhrzeit-Grenze (9 Tests, `test_strecke_km_argument.py`):** **Kein Tagesfehler.**
`tests/helpers/strecke_fixtures.py:38,97` (Koordinaten 0,0) verlangt Versaetze −120/−30 Minuten
im selben Ortstag; `tests/helpers/arrival_window_fixtures.py:170-182` wirft `ValueError`, wenn die
Ortszeit kurz nach Mitternacht liegt. Fix: **keine Tagesumstellung** — die Uhr wird im Test auf
eine unkritische UTC-Zeit gepinnt (`GZ_TEST_WALL_CLOCK_UTC=00:20`), Koordinaten 0,0 bleiben
unveraendert. Dieser Fix nutzt ausschliesslich den bestehenden Uhr-Schalter, nicht den neuen
Zonen-Knopf (s. Messgrenze unten).

### Wanduhr-Ratsche #1667 (Erweiterung, kein neues Gate)

`tests/tdd/test_fixture_wallclock_ratchet.py::_ist_wanduhr_datum()` erkennt bereits
`ortstag(lat, lon)` ohne `now_utc=` als Wanduhr-Datum (Zweig `_ist_ortstag_ohne_gepinnte_uhr`).
Dieselbe Erkennung wird auf `utc_tag()` ohne `now_utc=` ausgeweitet — sonst waere `utc_tag()`
ein unbewachter Bypass der bestehenden Ratsche. Erweiterung einer bestehenden Ratsche
(Regel-Budget: kein neues Gate), Selbsttests analog zu den bestehenden `test_scanner_erkennt_
ortstag_ohne_now_utc_als_etappendatum` / `test_scanner_schweigt_bei_ortstag_mit_gepinnter_uhr`.

### Tautologie-Verbot (aus Durchgang 1 uebernommen)

Tests, die die Tagesberechnung selbst pruefen (Bestand: `tests/unit/
test_gpx_import_in_trip_dialog.py::TestGpxToStageDataCustomDate::test_default_date_is_today`
u. a. bereits in Durchgang 1 behandelte Faelle), bekommen weiterhin gestellte Uhr + hart
hingeschriebenen Literal-Soll-Tag — niemals `ortstag()`/`utc_tag()`. Das gilt unveraendert auch
fuer neue Faelle, die in diesem Durchgang auftauchen.

### Unveraendert

`_gestellte_wanduhr`-Mechanik selbst (`tests/conftest.py`, `tests/helpers/wanduhr.py`) sowie
alles unter `src/`, `api/`, `internal/`, `frontend/`.

## Expected Behavior

- **Input:** dieselben ≈20 Testdateien (Familien A–D), derselbe Testinhalt — nur die
  Datumsquelle der Fixtures aendert sich (Familien A/C: `date.today()` → `utc_tag()`; Familie B:
  `date.today()` → `ortstag(lat, lon)`; Familie D: keine Datumsaenderung, Uhr gepinnt). Root-
  `conftest.py` bekommt zusaetzlich einen Env-Knopf fuer die Prozesszone.
- **Output:** die gesamte Suite ist unter dem Zonen-Knopf (Prozesstag = UTC-Tag − 1) grün,
  ausgenommen die 4 dokumentierten lokalen Umgebungsartefakte; derselbe Kontrolllauf unter
  Standardzone (`America/St_Johns`, kein Env gesetzt) bleibt ebenfalls grün mit denselben
  Ausnahmen. Familie D ist zusaetzlich unter gepinnter Uhr (00:20 UTC) grün.
- **Side effects:** keine am Produktivcode. Ohne gesetzte `GZ_TEST_PROCESS_TZ` ist das Verhalten
  identisch zu vor dieser Lieferung.
- **Close-Pfad:** Issue #2314 wird nach gruenem Prod-Selftest (Exit 0) geschlossen — der
  Kern-Nachweis dieser Spec haengt NICHT an einem echten Nachtlauf. Ein spaeterer roter
  CI-Nachtlauf oeffnet #2314 wieder bzw. erzeugt ein neues Ticket; er wird als Bestaetigung im
  Issue gebucht, ist aber kein Gate fuer den Merge/Deploy dieser Lieferung. Begruendung: AC-9 aus
  Durchgang 1 (Wanduhr-Pflicht vor Issue-Close) hat genau diesen zweiten Durchgang noetig
  gemacht, weil die Messluecke erst durch den echten Nachtlauf sichtbar wurde — ein erneutes
  Warten auf die naechste Nacht wuerde denselben Fehlerkreis nur wiederholen.

## Acceptance Criteria

- **AC-1:** Given Root-`conftest.py` ohne gesetzte Umgebungsvariable `GZ_TEST_PROCESS_TZ` / When
  ein beliebiger Testlauf startet / Then ist die Prozesszone exakt `America/St_Johns`, byte-
  identisch zum Verhalten vor dieser Lieferung — die Aenderung an `conftest.py` ist eine bewusste
  Abweichung von AC-4 aus Durchgang 1, additiv und ruckwaertskompatibel.
  - Test: `python3 -c "import time; print(time.tzname)"` bzw. ein Pytest-Selbsttest ohne
    gesetztes Env prueft die aktive Zone.

- **AC-2:** Given `GZ_TEST_PROCESS_TZ` ist auf eine **Gestern-Zone** gesetzt — Begriff für diese
  Spec: eine Prozesszone, in der zum Laufzeitpunkt Prozesstag = UTC-Tag − 1 gilt (Referenz
  `Pacific/Marquesas` für Läufe 00:00–09:30 UTC, gemessen 51 von 51 CI-Tagesfehlern, Vollmessung
  12027 passed/62 rot; für spätere Läufe `<-2330>+23:30`, trägt 00:00–23:30 UTC, Mechanismus am
  15.09. gemessen) / When `date.today()` in einem beliebigen Testmodul ausgewertet wird / Then
  liefert es den UTC-Tag minus 1 — die reale Situation „Prozesstag ≠ UTC-Tag" ist damit zu fast
  jeder Tageszeit ohne Warten auf die Nacht lokal herstellbar. Kein Nachweis dieser Spec hängt an
  einer bestimmten Uhrzeit.
  - Test: `tests/tdd/test_prozesszonen_schalter.py` (NEU) prüft unter gesetzter Gestern-Zone
    `date.today() == UTC-Tag − 1`; Zone und UTC-Startzeit jedes Nachweislaufs stehen im
    Implementierungsbericht.

- **AC-3:** Given `GZ_TEST_PROCESS_TZ` gesetzt, aber der Lauf startet zu einer UTC-Uhrzeit, zu der
  die gewaehlte Zone Prozesstag == UTC-Tag ergibt (Zone traegt gerade nicht) / When die Suite
  bzw. der Selbsttest startet / Then schlaegt der Lauf sichtbar und mit klarer Meldung fehl,
  statt still gruen durchzulaufen — Selbstschutz gegen ein falsches Gruen durch einen Zonen-Knopf,
  der zufaellig wirkungslos ist.
  - Test: `tests/tdd/test_prozesszonen_schalter.py` (NEU) — Selbsttest, der `GZ_TEST_PROCESS_TZ`
    setzt und `date.today()` gegen den tatsaechlichen UTC-Tag vergleicht; bei Gleichheit
    erwartet der Test einen dokumentierten Fehlschlag/Abbruch mit Zeit- und Zonenangabe im Text.

- **AC-4:** Given einer der auf `ortstag()` umgestellten Familie-B-Tests UND eine gezielte
  Verfaelschung von `src/services/trip_day.py::trip_local_today`, die wieder auf den Prozesstag
  statt den Ortstag zurueckfaellt / When dieser Test unter einer Gestern-Zone (AC-2)
  laeuft / Then wird mindestens einer dieser Tests rot — die Faehigkeit, einen
  echten Ortstag-Produktfehler zu erkennen, bleibt trotz Fixture-Umstellung erhalten.
  - Test: Mutations-Gegenprobe per String-Ersetzung mit externer Sicherungskopie (nie
    `git checkout/stash/reset`) in `trip_local_today`, betroffene Familie-B-Datei(en) unter dem
    Zonen-Knopf laufen lassen, danach Sicherungskopie zurueckspielen.

- **AC-5:** Given einer der auf `utc_tag()` umgestellten Familie-A-Tests UND eine gezielte
  Verfaelschung von `src/services/forecast_budget.py::_today_utc`, die wieder auf den Prozesstag
  statt den UTC-Tag zurueckfaellt / When dieser Test unter einer Gestern-Zone (AC-2)
  laeuft / Then wird mindestens einer dieser Tests rot — die Faehigkeit, einen
  echten UTC-Tag-Produktfehler zu erkennen, bleibt trotz Fixture-Umstellung erhalten.
  - Test: Mutations-Gegenprobe per String-Ersetzung mit externer Sicherungskopie in
    `_today_utc`, betroffene Familie-A-Datei(en) unter dem Zonen-Knopf laufen lassen, danach
    Sicherungskopie zurueckspielen.

- **AC-6:** Given die 5 kopierten `_write_budget`-Stellen der Familie A (`test_forecast_budget_
  gate.py`, `test_meteoalarm_budget_gate.py`, `test_radar_budget_and_priority.py`,
  `test_radar_upstream_failure.py`, `test_radar_nowcast_health_journal.py`) nach dem Fix / When
  sie unter einer Gestern-Zone (AC-2) laufen / Then sind alle 10 Tests
  gruen — der Budget-Zaehler wird am UTC-Tag geschrieben und vom Produkt am UTC-Tag korrekt
  gelesen.
  - Test: `GZ_TEST_PROCESS_TZ=<Gestern-Zone> uv run pytest <5 Dateien> -v -rA`.

- **AC-7:** Given die ≈33 Familie-B-Tests (Etappe/Snapshot/Marker, u. a. `_active_trip()`,
  `_write_snapshot()`, `schnappschuss_speichern()`, `_make_active_trip()`, `frozen_active_
  window()`) nach dem Fix / When sie unter einer Gestern-Zone (AC-2)
  laufen / Then sind alle Tests gruen — Etappe, Snapshot und Zeitanker tragen jetzt konsistent
  den Ortstag der jeweils gebauten Trip-Koordinaten.
  - Test: `GZ_TEST_PROCESS_TZ=<Gestern-Zone> uv run pytest <Familie-B-Dateiliste> -v -rA`.

- **AC-8:** Given die 7 Familie-C-Tests (FixtureProvider, inkl. des Subprozess-Tests
  `test_comparison_engine_no_circular_import.py`) nach dem Fix / When sie unter
  einer Gestern-Zone (AC-2) laufen, der Subprozess-Test inklusive / Then
  sind alle 7 Tests gruen — auch der Subprozess erbt die gesetzte Zone korrekt.
  - Test: `GZ_TEST_PROCESS_TZ=<Gestern-Zone> uv run pytest <Familie-C-Dateiliste> -v -rA`,
    Subprozess-Test einzeln gegengelesen (Env-Vererbung).

- **AC-9:** Given die 9 Familie-D-Tests (`test_strecke_km_argument.py`) nach dem Fix (Uhr auf
  `GZ_TEST_WALL_CLOCK_UTC=00:20` gepinnt, Koordinaten 0,0 unveraendert) / When die Datei mit
  gestellter Uhr laeuft / Then sind alle 9 Tests gruen — dieser Fix nutzt ausschliesslich den
  bestehenden Uhr-Schalter, NICHT den neuen Zonen-Knopf (Messgrenze, s. Known Limitations).
  Zusaetzlich sind 23:00 und 12:00 UTC als Regressionskontrolle gruen.
  - Test: `GZ_TEST_WALL_CLOCK_UTC=00:20 uv run pytest tests/tdd/test_strecke_km_argument.py -v`,
    wiederholt mit `23:00` und `12:00`.

- **AC-10:** Given `tests/tdd/test_fixture_wallclock_ratchet.py` (#1667) nach der Erweiterung /
  When eine Fixture `utc_tag()` ohne `now_utc=` in Kombination mit einer ungeklemmten
  Ankunftszeit verwendet / Then meldet die Ratsche denselben Fund wie heute bei `ortstag()` ohne
  `now_utc=` — `utc_tag()` ist kein unbewachter Bypass.
  - Test: `test_scanner_erkennt_utc_tag_ohne_now_utc_als_etappendatum` (NEU, analog zum
    bestehenden `ortstag`-Paar) + Gegenprobe `test_scanner_schweigt_bei_utc_tag_mit_gepinnter_
    uhr`.

- **AC-11:** Given die gesamte Testsuite (CI-Flags `--disable-socket --allow-unix-socket
  --allow-hosts=127.0.0.1,::1,localhost`, CI-Excludes) nach dem Fix / When sie unter
  einer Gestern-Zone (AC-2) laeuft / Then ist sie gruen, ausgenommen
  genau die 4 dokumentierten lokalen Umgebungsartefakte (`tests/test_public_host_links.py`, 3
  Tests; `tests/tdd/test_issue_1014_live_optin.py`, 1 Test) — dieselben, die auch in Standardzone
  rot sind.
  - Test: `GZ_TEST_PROCESS_TZ=<Gestern-Zone> uv run pytest <CI-Flags> <CI-Excludes> -v -rA`
    ueber die gesamte Suite, UTC-Startzeit protokolliert.

- **AC-12:** Given dieselbe Suite nach dem Fix / When sie OHNE gesetzte `GZ_TEST_PROCESS_TZ`
  (Standardzone `America/St_Johns`) laeuft / Then ist sie gruen mit denselben 4 Ausnahmen — der
  Fix darf keine bisher gruene Standardzone-Messung rot faerben.
  - Test: `uv run pytest <CI-Flags> <CI-Excludes> -v -rA` ueber die gesamte Suite ohne Env.

- **AC-13:** Given die 67 betroffenen Tests in 20 Dateien VOR dem Fix / When sie unter
  einer Gestern-Zone (AC-2) (Familien A–C) bzw. mit gepinnter Uhr
  00:20 UTC in Standardzone (Familie D) laufen / Then schlagen sie fehl — das ist der Bug-Nachweis
  aus Nutzersicht (der Nachtlauf blockiert einen inhaltlich unveraenderten PR).
  - Test: Referenz auf CI-Run `34912773403` / Job `104203730792` (60 rote Tests, real gemessen)
    plus ein frischer Vorher-Lauf mit dem neuen Zonen-Knopf, der die vollen 67 zeigt.

- **AC-14:** Given die Umstellung aller ≈20 Dateien und Helfer / When die Testanzahl je Datei vor
  und nach der Aenderung verglichen wird (`pytest --collect-only`) / Then ist sie unveraendert —
  kein Test geloescht, uebersprungen (`skip`) oder als erwarteter Fehlschlag (`xfail`) markiert.
  - Test: `uv run pytest <Dateiliste> --collect-only -q` vor und nach der Aenderung, Zeilenzahl
    je Datei diffen.

- **AC-15:** Given der gesamte Produktivcode unter `src/`, `api/`, `internal/`, `frontend/` sowie
  die Prozesszonen-Fixierung selbst (`os.environ["TZ"] = os.environ.get(..., "America/St_
  Johns")`) / When der Fix eingespielt ist / Then ist `git diff --stat main... -- src/ api/
  internal/ frontend/` leer — nur Testcode, `tests/helpers/`, Root-`conftest.py` und die Ratsche
  aendern sich.
  - Test: `git diff --stat main... -- src/ api/ internal/ frontend/` liefert keine Zeilen.

## Out of Scope

- Erweiterung der Wanduhr-Ratsche #1667 um weitere, ueber `utc_tag()`/`ortstag()` hinausgehende
  Muster — nicht Gegenstand dieser Lieferung.
- Produkt-Nebenbefund `src/providers/openmeteo.py:325,349,1031` (`date.today()`/`datetime.now()`
  fuer Availability-Cache-TTL bzw. totem Zweig) — kein Ursachenzusammenhang mit dem
  Nachtfenster (Prod laeuft `Etc/UTC`), gebucht in Sammel-Issue #1199.
- Ein echter CI-Nachtlauf als Merge-/Deploy-Gate — s. Close-Pfad in „Expected Behavior".
- Inhaltliche Aenderung der Zusicherungen in den 20 Dateien — geaendert wird ausschliesslich,
  WOHER das Datum bzw. die Uhrzeit kommt.

## Risiken

- **Fixture-Fehler vs. Produktfehler verdecken:** Umdatieren einer Fixture auf UTC-Tag oder
  Ortstag darf keinen echten Produktfehler verdecken. Gegenmassnahme: pro Familie ist im
  Abschnitt „Fixes je Familie" die fachlich richtige Tagesquelle explizit benannt und an einer
  Produktstelle verankert (`_today_utc`, `trip_local_today`, `FixtureProvider`); AC-4/AC-5 sind
  die Mutations-Gegenproben fuer beide Tagesquellen.
- **Messwerkzeug selbst fehlerhaft:** ein Zonen-Knopf, der zufaellig nicht traegt (Zone hat sich
  „ueberholt"), wuerde einen Lauf still gruen zeigen, ohne das Fenster wirklich zu testen.
  Gegenmassnahme: AC-3, Selbstschutz mit sichtbarem Fehlschlag.
- **Zwei Knoepfe vermischt:** Zonen-Knopf und gestellte Uhr wirken nicht zusammen (Messgrenze
  unten). Wird das in einem Testlauf dennoch vermischt, entstehen nicht reproduzierbare
  Ergebnisse. Gegenmassnahme: strikte Trennung in den ACs — Familien A–C nutzen ausschliesslich
  den Zonen-Knopf mit echter Uhr, Familie D ausschliesslich die gestellte Uhr in Standardzone.
- **Env-Vererbung im Subprozess:** `test_comparison_engine_no_circular_import.py` startet einen
  frischen Interpreter; wird `GZ_TEST_PROCESS_TZ` dort nicht an den Subprozess weitergereicht,
  bleibt der Test unter dem Zonen-Knopf faelschlich gruen (weil in Standardzone laufend), obwohl
  er die falsche Datumsquelle behaelt. Gegenmassnahme: AC-8 prueft den Subprozess-Test explizit
  mit.

## Test-Plan

| AC | Testdatei/Befehl |
|----|-------------------|
| AC-1 | Selbsttest ohne gesetztes `GZ_TEST_PROCESS_TZ`, Zone geprueft |
| AC-2 | `GZ_TEST_PROCESS_TZ=<Gestern-Zone> uv run pytest <Familien A-C> -v -rA` |
| AC-3 | `tests/tdd/test_prozesszonen_schalter.py` (NEU) |
| AC-4 | Mutations-Gegenprobe `trip_local_today` → Prozesstag, Familie-B-Test(s) unter Zonen-Knopf |
| AC-5 | Mutations-Gegenprobe `_today_utc` → Prozesstag, Familie-A-Test(s) unter Zonen-Knopf |
| AC-6 | `GZ_TEST_PROCESS_TZ=<Gestern-Zone> uv run pytest <5 Familie-A-Dateien> -v -rA` |
| AC-7 | `GZ_TEST_PROCESS_TZ=<Gestern-Zone> uv run pytest <Familie-B-Dateiliste> -v -rA` |
| AC-8 | `GZ_TEST_PROCESS_TZ=<Gestern-Zone> uv run pytest <Familie-C-Dateiliste> -v -rA` |
| AC-9 | `GZ_TEST_WALL_CLOCK_UTC=00:20/23:00/12:00 uv run pytest test_strecke_km_argument.py -v` |
| AC-10 | `tests/tdd/test_fixture_wallclock_ratchet.py` — 2 neue Selbsttests fuer `utc_tag()` |
| AC-11 | `GZ_TEST_PROCESS_TZ=<Gestern-Zone> uv run pytest <CI-Flags+Excludes>` Gesamtsuite |
| AC-12 | `uv run pytest <CI-Flags+Excludes>` Gesamtsuite ohne Env |
| AC-13 | Referenz CI-Run `34912773403`/Job `104203730792` + frischer Vorher-Lauf (67 Tests) |
| AC-14 | `pytest --collect-only -q` vor/nach, je Datei diffen |
| AC-15 | `git diff --stat main... -- src/ api/ internal/ frontend/` |

## Known Limitations

1. **Zonen-Knopf und gestellte Uhr wirken NICHT zusammen.** Unter `freeze_time` ohne `tz_offset`
   liefert `date.today()` den UTC-Tag, unabhaengig von der Prozesszone — der Zonen-Knopf ist unter
   einer gestellten Uhr wirkungslos. Deshalb sind es strikt getrennte Nachweislaeufe: Familien
   A–C werden ausschliesslich mit dem Zonen-Knopf und echter Uhr nachgewiesen, Familie D
   ausschliesslich mit gepinnter Uhr in Standardzone. Keine AC dieser Spec verlangt beide
   Mechanismen in einem Lauf.
2. **Jede Gestern-Zone trägt nur ein Tagesfenster.** `Pacific/Marquesas` 00:00–09:30 UTC,
   `<-2330>+23:30` 00:00–23:30 UTC. Außerhalb zeigt der Lauf Prozesstag == UTC-Tag — AC-3 macht
   das sichtbar, statt still grün zu melden. Die Nachweisläufe wählen die Zone passend zur
   Laufzeit; die POSIX-Zone ist bisher nur im Mechanismus gemessen, ihre erste Vollmessung erfolgt
   in `/40-tdd-red` (Vorher-Lauf, AC-13). Zeigt sie dort Artefakte (z. B. Code, der die Prozesszone
   als IANA-Namen nachschlägt), wird das dort protokolliert und die Nachweisläufe laufen mit
   `Pacific/Marquesas` im Morgenfenster.
3. **Subprozess-Vererbung ist eine zusaetzliche Fehlerquelle**, die bei der gestellten Uhr nicht
   existiert (dort wirkt Session-`freeze_time` ohnehin nicht im Subprozess) — beim Zonen-Knopf
   muss die Env-Variable aktiv weitergereicht werden, sonst laeuft der Subprozess in der
   System-Standardzone.
4. Nur die 67 gemessenen Tests in 20 Dateien sind Gegenstand. Weitere `date.today()`-Vorkommen
   im Repo, die den Fehler nicht ausloesen (Koordinaten in der Prozesszone o. Ae.), bleiben
   unberuehrt.
5. Ein echter CI-Nachtlauf bestaetigt diese Lieferung erst nach dem Merge — er ist bewusst kein
   Gate (s. Close-Pfad), weil genau das Warten auf einen einzelnen Nachtlauf in Durchgang 1 die
   Messluecke verdeckt hat, statt sie zu schliessen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** reine Testinfrastruktur-Korrektur ohne Verhaltensaenderung an Produktivcode —
  keine neue Entscheidungsflaeche. Inhaltlich getragen von ADR-0044 (Kalendertage folgen der
  Ortszeit) und ADR-0051 (Zone kommt aus den Daten); beide bleiben unveraendert in Kraft. Die
  Erweiterung von Root-`conftest.py` um einen Env-Knopf ist additiv und veraendert die mit #1402
  getroffene Entscheidung (fixierte Prozesszone als Default) nicht.

## Changelog

- 2026-09-15: `/60-validate` bestanden.
- 2026-09-15: ACs zonenunabhängig gefasst („Gestern-Zone", AC-2) — kein Nachweis hängt an einem
  Uhrzeitfenster; Versatz der POSIX-Zone korrigiert (−23:30).
- 2026-09-15: Initial spec erstellt — Issue #2314, zweiter Durchgang (Nachtlauf 15.09. 00:20 UTC
  zeigte 60 rote Tests im bislang unentdeckten Fenster 00:00–02:30 UTC).
