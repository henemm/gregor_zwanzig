# Context: fix-2314-ci-zeitzonen-riss

## Request Summary
Der CI-Job `test` ist täglich 22:00–02:30 UTC rot (144 Tests / 38 Dateien), unabhängig vom PR-Inhalt.
Ziel: Die Testsuite liefert zu **jeder** Uhrzeit dasselbe Ergebnis; die Merge-Ampel blockiert nachts nicht mehr fälschlich.

## Korrektur der Ticket-Diagnose (wichtig für Analyse/Spec)

Das Ticket benennt als Produktivseite `src/services/gpx_processing.py:219`. **Diese Stelle liegt nicht auf dem
fehlschlagenden Pfad** — `gpx_to_stage_data()` wird nur von `POST /api/gpx/parse` (`api/routers/gpx.py:43`) und dem
Mehrdatei-Import (`gpx_processing.py:301`) benutzt, nie vom Scheduler.

Tatsächliche Kette:
- Scheduler: `trip_report_scheduler.py:1281` `_get_target_date()` → `:970` `trip_local_today(trip, now_utc)`
  (`src/services/trip_day.py:57-96`, #1697/#1724) → `_convert_trip_to_segments` → `:1302` Log
  `No segments for trip … on <date>` → `"no_stage"`.
- Produkt rechnet den Kalendertag **richtig** in der Ortszone der Trip-Koordinaten (ADR-0044: Kalendertage folgen
  der Ortszeit, `trip_local_today` ersetzt `date.today()`; ADR-0051: „Zone kommt aus den Daten").
- Tests datieren Trips mit `date.today()` = **Prozesszone** `America/St_Johns` (Root-`conftest.py:23-24`, #1402),
  platzieren sie aber bei `LAT, LON = 47.0, 11.0` (Tirol, UTC+2). Ortstag springt 22:00 UTC, Testtag 02:30 UTC —
  deckungsgleich mit dem Fehlerfenster.

⇒ Der Defekt sitzt in den **Test-Fixtures**, nicht im Produktivcode. Die St.-John's-Fixierung tut genau ihren
Job (#1402: Zonenfehler sichtbar machen) — sie hat hier einen Testfehler sichtbar gemacht, nur eben nur 4,5 h täglich.

## Related Files
| File | Relevance |
|------|-----------|
| `conftest.py:1-24` (Root) | TZ-Pin `America/St_Johns` — bewusster Wächter (#1402), NICHT anfassen |
| `tests/helpers/alert_log_fixtures.py:46,133` | `LAT,LON=47.0,11.0`; `gust_alert_trip()` mit `date=date.today()` — von 46 Testdateien importiert |
| `tests/helpers/briefing_zeiten.py:57-69` | nutzt bereits korrekt `anchor_tz(trip, datetime.now(utc))` — Vorbild; 18 Importeure |
| `tests/tdd/test_alert_undelivered_hint.py:237` | lokale `_trip`-Kopie mit `date.today()` (42 Fehler) |
| `tests/tdd/test_alert_anchor_day_guard.py:155,229-567` | `boeen_trip(..., [date.today()])` (13) |
| `tests/.../test_issue_1088_official_alert_triggers.py:157,557` | `save_dated(trip_id, date.today(), …)` (10) |
| `tests/.../test_alert_state_briefing_reset.py:103,112,608` | dito (7) |
| `src/services/trip_day.py:57-96` | `anchor_tz` / `trip_local_now` / `trip_local_today` — produktive Wahrheitsquelle für den Ortstag |
| `src/services/trip_report_scheduler.py:970,1281,1302` | Verbraucher, Log-Quelle |
| `src/services/gpx_processing.py:219` | im Ticket genannt, aber nicht ursächlich (eigene, harmlose Clock-Nutzung ohne Injektion) |
| `tests/conftest.py:579-627` + `tests/helpers/wanduhr.py` | Uhr-Schalter `GZ_TEST_WALL_CLOCK_UTC` (#2096) — reproduziert das Fenster deterministisch |
| `tests/helpers/wanduhr_matrix.py` | Messgerät (#1709): Testdatei zu mehreren Uhrzeiten fahren, Differenz melden |
| `tests/tdd/test_fixture_wallclock_ratchet.py` | Ratsche #1667: AST-Scanner gegen ein verwandtes Wanduhr-Anti-Muster in Fixtures |
| `tests/tdd/test_trip_fixtures_laufen_unter_gestellter_uhr.py` | verwandter Wächter |
| `tests/test_output_timezone_guard.py` | #1723 „Muster A" (`date.today()`) — scannt nur `src/`/`api/`, **nicht** Tests |
| `docs/reference/critical_lessons.md:51-90` | dokumentierte Klasse „CI abends rot", Messrezepte |

## Existing Patterns
- **Uhr-Injektion im Produkt:** `now_utc`-Parameter in der ganzen `trip_day.py`-API, `_get_target_date`,
  `RadarNowcastService(now_fn=)`, `dpc._default_now`, `warn_egress.wall_clock_fn`, `forecast_capture._utcnow`.
- **Tests:** `freezegun` verbreitet; sitzungsweiter Uhr-Schalter `GZ_TEST_WALL_CLOCK_UTC`.
- **Richtiges Test-Muster existiert schon:** `briefing_zeiten.py` rechnet über `anchor_tz` statt Prozesszone.
- **Ratschen-Muster:** AST-Scanner über `tests/` (#1667) — Vorlage, falls ein Wächter gegen Rückfall nötig wird.

## Dependencies
- Upstream: `trip_day.anchor_tz`/`trip_local_today`, `utils/timezone.tz_for_coords`/`local_dt`, Root-TZ-Pin.
- Downstream: 38 rote Dateien direkt; `alert_log_fixtures.py` hat 46 Importeure, 170 Testdateien enthalten
  `date.today()` (nicht alle betroffen — nur solche, deren Trip-Ort nicht in Prozesszone liegt und die gegen den
  Ortstag des Produkts laufen).

## Existing Specs / ADRs
- `docs/adr/0044-…md` — Kalendertag = Ortszeit
- ADR-0051 — drei Zeitbegriffe, Zone aus den Daten
- `docs/specs/modules/fix_1465_zeitzonen_hausnorm.md` — Test-Hausnorm naive-UTC
- `docs/specs/modules/fix_1723_zeitzonen_waechter_entscheidung.md` — Wächter-Muster A nur Produktcode

## Risks & Considerations
- **Ticket-Option 2 (Fixture-Zone ändern) verbietet sich:** hebelt den #1402-Wächter aus, der sieben reale Vorfälle
  adressiert. Ticket-Option 1 (Produkt-Injektion in `gpx_processing`) trifft die falsche Stelle.
- **Option 3 (Tests auf feste Uhr einfrieren)** kaschiert: die Suite wäre grün, würde aber nur noch EINE Uhrzeit prüfen;
  Tageszeit-Bugs im Produkt (Klasse #1594) blieben unsichtbar. `freezegun` sitzungsweit bricht pydantic-v1-Importe.
- Naheliegende Ursachenlösung: Test-Fixtures datieren Trips über den **Ortstag des Trips** (`trip_local_today` bzw.
  ein Test-Helfer darauf), nicht `date.today()`. Scope-Frage: nur die 38 roten Dateien oder alle Muster-Vorkommen.
- **Nachweis muss uhrzeitunabhängig sein:** grün um 14 Uhr beweist nichts. Beleg per `GZ_TEST_WALL_CLOCK_UTC`
  (z. B. 23:00) bzw. `wanduhr_matrix` — vorher rot, nachher grün.
- **Rückfallschutz:** ohne Wächter kommt das Muster mit dem nächsten Test zurück (170 Fundstellen). Aber
  Regel-Budget beachten (Ersatz oder +90-Tage-Prüfdatum); ggf. bestehende Ratsche #1667 / Wächter #1723 erweitern
  statt neuem Gate.
- `test_trip_report_test_send_past_stage_clamp.py::…test_router_returns_422_with_honest_no_weather_message` ist laut
  Ticket-Kommentar ein **Einfrier-Artefakt** (braucht fortschreitende Wanduhr) — gehört nicht in diesen Befund.
- LoC-Limit 250: Anpassung vieler Testdateien kann es sprengen (Tests zählen mit) → ggf. `loc_limit_override`.

## Analysis

### Type
Bug (Test-Infrastruktur; fälschlich blockierendes Gate, `[triage:c]`). **Kein Produktcode-Defekt.**

### Messbefunde
- **Inventur Nachtlauf** (Job `103636609514`, Log im Scratchpad): exakt **144 Fehler / 38 Dateien** — deckt sich mit dem Ticket, kein Rest.
- **Jede** der 38 Dateien bezieht das Etappendatum aus `date.today()` — direkt oder über Helfer
  (`tests/helpers/alert_log_fixtures.py:133`, `tests/helpers/trip_outlook_channels.py:111`,
  `tests/helpers/nowcast_gate_fixtures.py` `make_trip()`). Einziger Grep-Ausreißer
  (`test_trip_outlook_compact_telegram_dispatch.py`) folgt demselben Muster über `trip_outlook_channels.py:111`.
- **Reproduktion:** `GZ_TEST_WALL_CLOCK_UTC=23:00` → `test_alert_anchor_day_guard.py` 13 failed; `=12:00` → 25 passed.
- **Ortszonen der `date.today()`-Trips sind NICHT einheitlich:**
  - UTC+2 (Wien/Berlin/Paris/Zürich/Rom) — Großteil, Fenster 22:00–02:30 UTC
  - **Atlantic/Reykjavik** (UTC+0): `nowcast_gate_fixtures.make_trip()` (64.13/-21.90) — weicht 00:00–02:30 UTC ab
  - **America/Los_Angeles** (SIERRA 39.19/-120.24, `test_alarm_zeitfenster_ziel.py`) — weicht **02:30–07:00 UTC** ab
    ⇒ zweites, bisher unsichtbares Fenster; ein Nachweis nur im Nachtfenster reicht nicht.
  - Radar-Fixture in `test_alarm_zeitfenster_ziel.py:366-417` wählt Reykjavik/Auckland zur Laufzeit.
- `test_trip_report_test_send_past_stage_clamp.py` (AC-1-Test): **doch dieselbe Ursache** — der Provider-Double lehnt ab,
  wenn `start.date() != date.today()` (~Z.121), das Produkt klemmt aber auf `trip_local_today` (`trip_report_scheduler.py:1320-1323`).
  Fix gehört in den Double-Vergleich. (Der Router-Test aus dem Ticket-Kommentar ist ein anderer Test.)

### Tautologie-Prüfung (Zusicherung dort prüfen, wo sie wirkt)
Ein Helfer, der den Ortstag über das produktive `tz_for_coords` ableitet, ist nur dort zulässig, wo der Test eine
**Folgewirkung bei gegebenem Tag** prüft — nicht die **Tagesberechnung selbst**.
- **Folgewirkung (Helfer zulässig):** `test_alert_anchor_day_guard.py`, `test_alert_anchor_day_boundary.py`,
  `test_trip_briefing_anchor_unchanged.py`, `test_issue_823_snapshot_date_guard.py`,
  `test_alert_channel_anchor_shared_comparison.py` (Fixture nutzt schon `trip_local_today`, rot über `gust_alert_trip()`),
  sowie die übrigen Alarm-/Dispatch-Dateien. Die eigentliche Tagesberechnung ist anderswo mit `freeze_time` +
  `trip_two_zones` bewacht (z. B. `test_alert_etappen_praefix_kurzform.py::test_f001`).
- **Berechnung geprüft (Helfer VERBOTEN — Datum und Uhr explizit pinnen):**
  - `tests/e2e/test_e2e_story3_reports.py:274` — Mail-Betreff muss den Tag enthalten
  - `tests/unit/test_alarm_zeitfenster_ziel.py` Radar-Fixture `:366-417` / Invariante `:619ff` — Koordinaten hängen vom Tag ab (zirkulär)
  - `tests/unit/test_gpx_import_in_trip_dialog.py` — prüft den Default-Tag von `gpx_to_stage_data` (ADR-0044)
  - Grenzfall `test_alert_etappen_praefix_kurzform.py:302/319, 535/539` — im Einzelfall entscheiden

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `tests/helpers/<ortstag-helfer>.py` | CREATE | EIN Helfer „Ortstag zu Koordinaten", `lat`/`lon` **Pflicht** (kein Default), delegiert an produktives `utils.timezone.tz_for_coords`; optional `now_utc` |
| `tests/helpers/alert_log_fixtures.py` | MODIFY | `gust_alert_trip()` Etappendatum über Helfer (46 Importeure) |
| `tests/helpers/trip_outlook_channels.py` | MODIFY | `heute` über Helfer |
| `tests/helpers/nowcast_gate_fixtures.py` | MODIFY | `make_trip()`-Default über Helfer (Reykjavik) |
| ~35 rote Testdateien | MODIFY | lokale `date.today()`-Datierungen von Trips/Ankern/`load_dated`/`save_dated` → Helfer mit den Trip-Koordinaten bzw. `anchor_tz(trip, now)` |
| 3–4 Berechnungs-Tests (s. o.) | MODIFY | explizites Datum + gestellte Uhr statt Wanduhr |
| `tests/tdd/test_trip_report_test_send_past_stage_clamp.py` | MODIFY | Double vergleicht gegen Ortstag |
| `conftest.py` (Root) | — | **unverändert** (#1402-Wächter bleibt) |
| `src/`, `api/` | — | **unverändert** |

### Scope Assessment
- Files: ~40 (fast nur Testcode), 1 neu
- Estimated LoC: ca. +220/−150 (viele 1–3-Zeilen-Diffs) → `loc_limit_override 500` vor `/40`
- Risk Level: MEDIUM — kein Produktrisiko; Risiko ist **falsches Grün** (Tautologie, Default-Koordinaten, Nachweis nur zu einer Uhrzeit)

### Technical Approach
**Ansatz A** — Fixtures datieren Trips nach dem **Ortstag der Trip-Koordinaten** statt nach dem Prozesstag.
- Verworfen **B** (Tests einfrieren): würde nur noch eine Uhrzeit prüfen, Tageszeit-Bugs im Produkt blieben unsichtbar;
  sitzungsweites `freezegun` bricht pydantic-v1-Importe.
- Verworfen **C** (Fixture-Zone ändern): hebelt #1402 aus; bei mehreren Trip-Zonen ohnehin nicht lösbar.
- Verworfen **Produkt-Injektion in `gpx_processing.py`** (Ticket-Option 1): trifft nicht die Ursache.
- **Nachweis uhrzeitunabhängig über ganzen Tag**: `GZ_TEST_WALL_CLOCK_UTC` bzw. `tests/helpers/wanduhr_matrix.py` zu
  mehreren Uhrzeiten, die alle Zonenfenster abdecken (mind. 12:00 Kontrolle, 23:00 und 01:00 für UTC+2/Reykjavik,
  04:00 für Los Angeles) — vorher rot, nachher grün, für alle 38 Dateien.

### Dependencies
- Helfer → `src/utils/timezone.py:37` `tz_for_coords` (keine Abhängigkeit zu `app.trip`, importzyklusfrei)
- Wo schon ein `Trip` existiert: `src/services/trip_day.py` `anchor_tz(trip, now_utc)` (Muster `tests/helpers/briefing_zeiten.py:57-69`)

### Rückfallschutz (Entscheidung)
Kein neues Gate in diesem Workflow (Regel-Budget). Erweiterung der bestehenden Wanduhr-Ratsche #1667
(`tests/tdd/test_fixture_wallclock_ratchet.py`) um „`date.today()` als Trip-Etappendatum" wird als Checkbox in
**#1196** gebucht (Nebenbefund-Triage: Test-/Gate-Befund).

### Open Questions
- keine PO-Fragen offen — alle Entscheidungen technisch begründbar (siehe oben)
