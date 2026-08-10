---
entity_id: fix_1697_ortstag_statt_servertag
type: bugfix
created: 2026-08-10
updated: 2026-08-10
status: draft
workflow: fix-1697-ortstag-statt-servertag
version: "1.0"
tags: [issue-1697, timezone, adr-0044, trip-alert, radar-alert, calendar-day]
---

# Fix #1697 — Alarm-Pfad folgt dem Ortstag der Tour, nicht der Serveruhr

## Approval

- [x] Approved — **PO Henning, 2026-08-10, wörtlich: „Freigabe auf 500."**
  Freigegeben wurden zugleich die neun Akzeptanzkriterien und der erweiterte
  LoC-Rahmen (`loc_limit_override 500` statt 250). Begründung für den Rahmen:
  der „Zweite Fund" (geteilte Testfixture `stage_date`, zwölf Testdateien) ist
  kein Komfort-Zusatz, sondern verhindert, dass diese Spec dieselbe
  Fehlerklasse im Testbestand neu erzeugt.

**Vorausgegangene PO-Entscheidungen zu diesem Zuschnitt (2026-08-10):**

- **Das Zeitzonen-Problem wird als Zeitzonen-Problem gelöst**, nicht durch
  Absuchen von Nachbartagen. Ein zunächst vorgeschlagener Zuschnitt (#1667 S3
  sucht zusätzlich einen Tag vorwärts) wurde vom PO mit genau dieser
  Begründung verworfen — er hätte um eine falsch gestellte Frage herumgebaut.
- **#1697 vor #1667 S3.** Die Sicherheitslücke aus #1667 bleibt so lange offen;
  bewusst in Kauf genommen, um auf sauberer Grundlage aufzusetzen.
- **Touren über mehrere Zeitzonen werden nicht gebaut** — als bekannte Grenze
  dokumentiert (deckt sich mit ADR-0044, das den Restfehler als „in aller
  Regel null" einstuft).

## Purpose

`src/services/trip_alert.py` bestimmt „welcher Tag der Tour ist jetzt" an vier
Stellen über `date.today()` — das Datum der **Serveruhr** (`Etc/UTC`). Eine
Etappe trägt aber ein **Ortsdatum**. Fallen beide auseinander, findet
`Trip.get_stage_for_date` (striktes `==`) keine Etappe mehr, und der Trip wird
per `continue` stillschweigend übersprungen: kein Alarm, keine Meldung.

Gemessen (Kontext-Dokument, Basis-HEAD `dc100be9`), Abweichung Ortsdatum vs.
Serverdatum:

| Zone | Abweichung | Fenster |
|---|---|---|
| Europe/Paris, Europe/Vienna | 2,00 h/Tag | 22:00–00:00 UTC (= 00:00–02:00 Ortszeit) |
| America/Los_Angeles | 7,00 h/Tag | 00:00–07:00 UTC |
| Pacific/Auckland | 12,00 h/Tag | 12:00–00:00 UTC |

Trefferquote bei einer normalen Etappe 08:00–19:00 Ortszeit, vier
Stichproben über den Tag:

| Zone | Serverdatum trifft | Ortsdatum trifft |
|---|---|---|
| Europe/Paris | 4/4 | 4/4 |
| America/Los_Angeles | 3/4 | 4/4 |
| Pacific/Auckland | 2/4 | 4/4 |

Nutzerwirkung: Ein Neuseeland-Trip verliert die ersten ~4 von 11 Stunden
**jedes** Etappentags, ein Kalifornien-Trip die letzten ~2 — ohne jede
Nacht-Etappe.

## Die Entwurfsfrage ist entschieden — nicht neu aufmachen

`docs/adr/0044-kalendertage-folgen-der-ortszeit.md` (**Akzeptiert**, PO
2026-08-03): „Kalendertage bestimmen sich nach der Ortszeit der Tour. Die Zone
wird aus den Koordinaten des Wegpunkts aufgelöst, mit dreistufigem Rückfall:
Etappe des Weltzeit-Tages → erste Etappe mit Wegpunkten → importierte
UTC-Konstante."

Die Henne-Ei-Falle — man braucht ein Datum, um die Zone zu bestimmen, und die
Zone, um das Datum zu bestimmen — ist in `docs/specs/modules/fix_1470_drilldown_ortszeit.md`
Abschnitt „Die Reihenfolge-Falle" gelöst und vom Adversary gehärtet. Diese
Spec **übernimmt die dortige Auflösung wörtlich**, sie wird hier nicht neu
erfunden:

1. **Welcher Kalendertag?** entscheidet die Zone der Etappe des
   **Weltzeit-Tages**. Der liegt höchstens einen Tag daneben, trifft also
   praktisch immer die Etappe, auf der der Nutzer gerade steht.
2. **Der eigentliche Ortstag** ergibt sich dann aus derselben Zone, angewendet
   auf `now_utc`.

Bestehender Code (unverändert übernommen, nur verschoben — s. Implementation
Details): `src/services/trip_command_processor.py:775-824`
(`_anchor_tz`/`_trip_tz`/`_display_tz`).

### 🔴 Verworfene Alternative: Zone der ersten Etappe der Tour

Die ERSTE Fassung von #1470 ankerte an der ersten Etappe der Tour. Der
Adversary hat mit einer Tour Neuseeland → Korsika **zehn Stunden** Abweichung
nachgewiesen (12:00–22:00 UTC meldete bereits den Folgetag, während es am Ort
erst 14:00–23:00 war). Diese Alternative ist verworfen und wird durch diese
Spec nicht erneut erwogen.

## Source

- **Files:** `src/services/trip_alert.py` (Wirkort), `src/services/trip_command_processor.py`
  (verliert drei private Methoden an den neuen Baustein),
  `src/services/trip_day.py` (neu, geteilter Baustein), sowie
  `tests/helpers/arrival_window_fixtures.py` (geteilte Testfixture, s.
  „🔴 Zweiter Fund" unten)
- **Identifier:** `TripAlertService.check_all_trips` (`:363`),
  `TripAlertService._get_cached_weather` (`:509`),
  `TripAlertService.check_radar_alerts` (`:862`),
  `TripAlertService.check_official_alert_triggers` (`:1244`)

> **Schicht-Hinweis:** Reines Python-Core / Domain-Backend
> (`src/services/`). Kein Go-, kein Frontend-Anteil. `trip_day.py` liegt
> bewusst in `src/services/`, nicht in `src/utils/timezone.py` — letzteres
> kennt weder `Trip` noch `Stage` und bleibt eine generische
> Koordinaten/Zeitzonen-Bibliothek ohne Domänenwissen (s. Implementation
> Details, Abschnitt „Warum ein neues Modul").

## 🔴 Zweiter Fund: die geteilte Testfixture muss mitgehen

Zwölf Alarm-/Radar-Testdateien bauen ihre Etappen über den Helfer
`tests/helpers/arrival_window_fixtures.py` (#1667 S1). Dessen Funktion
`stage_date()` ist **niladisch** und liefert wörtlich `date.today()` — mit der
Begründung im eigenen Docstring: „Dort steht `today = date_type.today()`;
`convert_trip_to_segments` sucht die Etappe über `get_stage_for_date(today)`."
Das ist exakt der Code, den diese Spec an `trip_alert.py:881` ändert.

**Ohne Anpassung entsteht durch diese Spec selbst eine neue, tägliche
Zeitfenster-Lücke — diesmal im Testbestand statt in Produktion.** Nach der
Umstellung sucht `check_radar_alerts` die Etappe über
`trip_local_today(trip, now_utc)`; die Fixture würde ihre Stage aber
weiterhin unter `date.today()` (Serverdatum) ablegen. In der
22:00–00:00-UTC-Randzeit (oder dem Äquivalent der jeweiligen Testkoordinaten)
laufen beide dann auf verschiedene Tage — exakt dieselbe Fehlerklasse, die
diese Spec beheben soll, nur eine Ebene höher. Zwölf Testdateien würden damit
**zeitabhängig neu flakig**, ausgerechnet in den Randfenstern, die AC-2/AC-3
absichern sollen.

Betroffen (per Grep verifiziert, echte Aufrufe von `stage_date()`, keine
Namenskollisionen):

`tests/tdd/test_issue_818_radar_briefing_integration.py`,
`tests/tdd/test_issue_822_radar_nowcast_segment.py` (6 Aufrufe),
`tests/tdd/test_bundle_791_847_844_alerts.py`,
`tests/tdd/test_issue_827_radar_throttle_recording.py`,
`tests/tdd/test_alert_urgency.py`,
`tests/tdd/test_issue_1070_daily_alert_limit.py`,
`tests/tdd/test_issue_995_scheduler_pause.py`,
`tests/tdd/test_alert_channel_threshold.py`,
`tests/tdd/test_issue_883_acute_danger_override.py`,
`tests/tdd/test_alert_quiet_hours_robustness.py`,
`tests/tdd/test_alert_log_metrics.py`,
`tests/unit/test_arrival_window_fixtures.py` (der Guard selbst).

**Warum genau zwölf und nicht dreizehn:** `grep -rln "arrival_window_fixtures
import" tests/` liefert exakt diese zwölf Dateien. Ein reiner Textgriff nach
`stage_date` trifft zusätzlich `tests/tdd/test_gpx_proxy.py` — dort ist
`stage_date` ein **Query-Parameter** des GPX-Endpunkts, kein Aufruf dieses
Helfers. Diese Datei wird **nicht** angefasst.

**Konsequenz für den Zuschnitt:** Diese Korrektur gehört zwingend **in diese
Scheibe**, aus demselben Grund, aus dem der Horizont-Guard zwingend ist —
sie ist keine Erweiterung, sondern die Vermeidung eines neuen, durch diese
Spec selbst verursachten Fehlers. Sie treibt den LoC-Umfang über das
250er-Limit (s. Estimated Scope).

`_tagesbezug(lat, lon)` in derselben Datei kennt `lat`/`lon` bereits (für
`tz_for_coords`) — nur `stage_date()` selbst ist koordinatenblind. Die
Korrektur macht `stage_date(lat, lon)` **PFLICHT-parametrisiert** (kein
Default, analog zum bestehenden `tagesgleicher_anker_noetig`-Muster in
`_get_cached_weather`): jeder der zwölf Aufrufer muss bewusst dieselben
Koordinaten übergeben, die er auch für `active_window_offsets(lat, lon, …)`
benutzt. Die Formel selbst ist **kein** Aufruf von
`services.trip_day.trip_local_today` — die Fixture kennt ihre Koordinaten
bereits direkt (keine Henne-Ei-Falle, kein Trip zum Nachschlagen nötig) und
bleibt bei der einfacheren `local_dt(datetime.now(timezone.utc),
tz_for_coords(lat, lon)).date()`, die bereits mit den in dieser Datei
importierten Bausteinen (`tz_for_coords`, aus `utils.timezone` zu ergänzen:
`local_dt`) auskommt.

## Affected Files

| Datei:Zeile | Änderung |
|---|---|
| `src/services/trip_day.py` (NEU) | `trip_tz`, `display_tz`, `anchor_tz` — verschoben aus `trip_command_processor.py`; neue Funktion `trip_local_today(trip, now_utc) -> date` |
| `src/services/trip_command_processor.py:775-824` | `_anchor_tz`/`_trip_tz`/`_display_tz` entfernt (nach `trip_day.py` verschoben, Verhalten bit-identisch) |
| `src/services/trip_command_processor.py:735-773` | `_day_window` ruft `trip_day.trip_local_today`/`trip_day.display_tz`/`trip_day.anchor_tz` statt `self._…` — AC-8 |
| `src/services/trip_alert.py:9-34` | Import `from services.trip_day import trip_local_today` ergänzt |
| `src/services/trip_alert.py:382-394` | `check_all_trips`: `today = date_type.today()` → `now_utc = datetime.now(timezone.utc)`; `today` je Trip **innerhalb** der Schleife über `trip_local_today(trip, now_utc)` |
| `src/services/trip_alert.py:441` | End-Date-Filter (`trip.end_date < today`) nutzt den je-Trip aufgelösten `today` |
| `src/services/trip_alert.py:446,452` | `_get_cached_weather`-Aufruf bekommt `now_utc=now_utc`; `check_official_alert_triggers`-Aufruf bekommt `now_utc` |
| `src/services/trip_alert.py:509-570` | `_get_cached_weather`: neuer optionaler Parameter `now_utc: Optional[datetime] = None` (Begründung für den Default s. u.); `today = date.today()` → `today = trip_local_today(trip, now_utc or datetime.now(timezone.utc))` |
| `src/services/trip_alert.py:1244-1274` | `check_official_alert_triggers`: neuer optionaler Parameter `now_utc: Optional[datetime] = None`, durchgereicht an `_get_cached_weather` |
| `src/services/trip_alert.py:877-887` | `check_radar_alerts`: `today = date_type.today()` (vor der Schleife) entfernt; je Trip `today = trip_local_today(trip, now_utc)` vor `convert_trip_to_segments(trip, today)` |
| `src/services/trip_alert.py:906-908` (neu) | Horizont-Guard vor dem Nowcast-Gate: `active.start_time > now_utc` + `NOWCAST_HORIZON_MIN`-Vergleich → `continue` |
| `src/services/trip_alert.py:971` | `load_dated(trip.id, today)` — unverändert im Code, profitiert vom korrigierten `today` (AC-5) |
| `tests/helpers/arrival_window_fixtures.py:155-207` | `stage_date()` → `stage_date(lat, lon)` (Pflicht-Parameter); `_tagesbezug`/`past_window_offsets` rufen die neue Signatur |
| 12 bestehende Testdateien (Liste oben, „Zweiter Fund") | Aufrufe von `stage_date()` → `stage_date(lat, lon)` mit denselben Koordinaten wie das jeweils benutzte `active_window_offsets`/`past_window_offsets` |
| `tests/unit/test_arrival_window_fixtures.py` | neue Zusicherung: `stage_date(lat, lon)` weicht für eine Ost-Zone (Korsika) und eine West-Zone (Kalifornien) unter gestellter Uhr korrekt vom Serverdatum ab — Regressionsschutz für die Korrektur oben |
| `tests/unit/test_trip_local_today.py` (NEU) | Reine Funktionstests von `trip_day.py`: Rückfallkette (AC-6), Sommerzeit (AC-7) |
| `tests/tdd/test_radar_alert_follows_ortstag.py` (NEU) | Wirkungstests gegen `TripAlertService`: Auckland-Koordinatennachweis (AC-1), Korsika-Bestandsschutz (AC-2), Korsika-Randfenster (AC-3), Horizont-Guard (AC-4), Schnappschuss-Konsistenz (AC-5), Delegation (AC-8), Mutations-Gegenprobe |

**Nicht angefasst (bewusst, DRAUSSEN):** `trip_report_scheduler.py:663`
(`_get_target_date`), `:617` (`_get_active_trips`), `:857`, `:1109`
(`save_dated`) — Briefing-Schreiber bleibt auf Serverdatum, eigene Scheibe.
Kette B (`trip_command_processor.py` `/jetzt`, `/status`, `_handle_query`,
`command_date`; `inbound_telegram_reader.py`; `preview_service.py`;
`api/routers/debug.py`; `tools/weather_validation.py`) — eigenes Folge-Issue.
Mehr-Zonen-Touren — bewusst nicht gebaut (PO 2026-08-10, s. Known
Limitations). `corridor_threshold.py` — kein Produktions-Aufrufer.
`forecast_budget._today_utc`, `meteoalarm_budget._today_utc`,
`alert_daily_limit.py:32`, `deviation_alert_engine.py:112` — feste Zone ist
dort Absicht, nicht Fehler.

## Estimated Scope

- **LoC:** ~300–330 — deutlich über dem 250er-Limit. Aufschlüsselung:
  `trip_day.py` ~70 (Baustein, inkl. Docstrings im Detailgrad des
  Vorbilds), `trip_command_processor.py` ~‑35 (drei Methoden entfernt,
  `_day_window` leicht umgebaut — netto Rückgang), `trip_alert.py` ~50 (vier
  Aufrufstellen + Horizont-Guard + zwei optionale Parameter),
  `arrival_window_fixtures.py` ~15, zwölf Testdateien × ~2 Zeilen
  (Koordinaten-Argument ergänzen) ~24, `test_arrival_window_fixtures.py`
  ~20 (neue Zusicherung), zwei neue Testdateien ~170–200 (drei Zonen ×
  Kippkante, zwei Sommerzeit-Wechseltage, Horizont-Guard mit
  Aufruf-Zähler, Mutations-Gegenprobe).
  **Empfehlung:** `workflow.py set-field loc_limit_override 500` vor der
  Implementierung setzen — der Zweite Fund (geteilte Testfixture) ist kein
  Komfort-Zusatz, sondern notwendig, um AC-2/AC-3 überhaupt ohne neue
  Nacht-Flakiness abzusichern.
- **Files:** 3 neu (`trip_day.py`, zwei Testdateien), 16 geändert
  (`trip_command_processor.py`, `trip_alert.py`,
  `arrival_window_fixtures.py`, `test_arrival_window_fixtures.py`, 12
  bestehende Testdateien) = 19.
- **Effort:** medium-high — die Kernänderung ist klein (vier Aufrufstellen +
  ein Guard), der Aufwand liegt im Sommerzeit-Nachweis, im
  Horizont-Guard-Test und im sauberen Nachziehen der geteilten Testfixture.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/adr/0044-kalendertage-folgen-der-ortszeit.md` | ADR | Bereits akzeptierte Grundsatzentscheidung — diese Spec setzt sie für Kette A um, öffnet sie nicht neu |
| `docs/specs/modules/fix_1470_drilldown_ortszeit.md` | spec | Henne-Ei-Auflösung (Weltzeit-Tag-Anker) wörtlich übernommen |
| `src/services/trip_command_processor.py::_anchor_tz/_trip_tz/_display_tz` (`:775-824`) | module | Quellcode der Auflösung, wird nach `trip_day.py` verschoben |
| `src/utils/timezone.py::tz_for_coords`, `local_dt`, `UTC` | module | Bausteine, aus denen `trip_day.py` UND die korrigierte Testfixture bestehen — keine dritte Kopie |
| `src/services/radar_service.py::NOWCAST_HORIZON_MIN` | constant | Schwellwert des neuen Horizont-Guards, identisch zum Vorbild |
| `src/services/trip_report_scheduler.py::_build_starkregen_hint` (`:1352-1357`) | pattern | Vorbild für die Horizont-Guard-Formel (`minutes_until_start > NOWCAST_HORIZON_MIN`) |
| `tests/tdd/test_starkregen_kurzfristhinweis.py::test_ac2_zeitfenster_guard_kein_fetch_ausserhalb_horizon` (`:330`) | pattern | Vorbild für den Horizont-Guard-Test: echte `RadarNowcastService.get_nowcast`-Ersetzung mit Aufruf-Liste, Nah/Fern-Gegenprobe im selben Test |
| `tests/helpers/arrival_window_fixtures.py` (#1667 S1) | fixture | Geteilte Testfixture für ~30 Alarm-/Radar-Tests; zwölf davon rufen `stage_date()` direkt und müssen mit dieser Spec mitgehen (s. „Zweiter Fund") |
| `tests/tdd/test_fixture_wallclock_ratchet.py` | guard | AST-Ratsche gegen rohe Wanduhr-Arithmetik in Testdateien; behandelt `stage_date()`-Aufrufe bereits als „wanduhr-getragen" — bleibt durch die Signaturänderung unberührt (prüft Aufruf-Muster, nicht die Formel dahinter) |
| `src/services/weather_snapshot.py::load_dated/load/load_target_date` | module | Ziel der Lesungen an `:570`/`:971` — unverändert im Code, das übergebene `today` ändert sich |

## Implementation Details

### Warum ein neues Modul (`src/services/trip_day.py`) statt `utils/timezone.py`

`src/utils/timezone.py` ist eine generische Koordinaten-/Zeitzonen-Bibliothek
ohne Domänenwissen (`tz_for_coords`, `local_dt`, `UTC` — keine Kenntnis von
`Trip`/`Stage`). Die drei Methoden aus #1470 kennen dagegen `Trip.stages` und
`Trip.get_stage_for_date`. Sie gehören in die Domänen-Schicht
(`src/services/`), analog dazu, wie sie heute schon auf
`TripCommandProcessor` (auch `services/`) liegen. `trip_day.py` importiert
`Trip` nur unter `TYPE_CHECKING` (wie `trip_alert.py` es bereits tut) — kein
Kreislaufimport-Risiko, da `app/trip.py` selbst nichts aus `services/`
importiert.

### Der geteilte Baustein

```python
# src/services/trip_day.py
def trip_tz(trip: "Trip") -> ZoneInfo:
    """Ortszone der Tour OHNE Tagesbezug — erste Etappe mit Wegpunkten."""
    stage = next((s for s in trip.stages if s.waypoints), None)
    return tz_for_coords(stage.waypoints[0].lat, stage.waypoints[0].lon) \
        if stage else UTC

def display_tz(trip: "Trip", day_date: date) -> ZoneInfo:
    """Ortszone der Etappe an ``day_date`` — Rückfall auf ``trip_tz``."""
    stage = trip.get_stage_for_date(day_date)
    if stage is None or not stage.waypoints:
        return trip_tz(trip)
    wp = stage.waypoints[0]
    return tz_for_coords(wp.lat, wp.lon)
```

```python
def anchor_tz(trip: "Trip", now_utc: datetime) -> ZoneInfo:
    """Zone der Etappe des WELTZEIT-Tages (#1470 F003) — entscheidet, WELCHER
    Kalendertag gerade ist, ohne selbst schon vom Ortstag abzuhängen."""
    return display_tz(trip, local_dt(now_utc, UTC).date())

def trip_local_today(trip: "Trip", now_utc: datetime) -> date:
    """Der Kalendertag „heute", gemessen an der Ortszeit der Tour (ADR-0044)."""
    return local_dt(now_utc, anchor_tz(trip, now_utc)).date()
```

`trip_tz`/`display_tz`/`anchor_tz` sind unveränderte Verschiebungen der
#1470-Methoden (nur `self.` entfernt); `trip_local_today` ist neu und fasst
exakt zusammen, was `TripCommandProcessor._day_window`'s „today"-Zweig heute
schon inline tut (`local_dt(received_at, self._anchor_tz(...)).date()`).

### Kette A — vier Aufrufstellen

Alle vier Stellen bekommen denselben `now_utc`, damit ein Lauf konsistent
bleibt (kein Trip sieht eine andere „Jetzt"-Sekunde als der nächste):

- `check_all_trips`: `now_utc = datetime.now(timezone.utc)` einmal zu
  Laufbeginn; `today = trip_local_today(trip, now_utc)` **je Trip** innerhalb
  der Schleife (nicht mehr davor — die Zone hängt vom Trip ab).
- `check_radar_alerts`: `now_utc` bleibt an seiner bisherigen Stelle
  (`:882`); `today` wandert von vor die Schleife in die Schleife.
- `_get_cached_weather`/`check_official_alert_triggers`: bekommen `now_utc`
  als **optionalen** Parameter (`Optional[datetime] = None`, Default
  `datetime.now(timezone.utc)`), NICHT als Pflicht-Parameter ohne Default.

### 🔴 Bewusste Abweichung vom „kein Default"-Muster

`_get_cached_weather`s bestehender Parameter `tagesgleicher_anker_noetig` hat
explizit **keinen** Default — eine neue Aufrufstelle muss sich bewusst
entscheiden. `now_utc` bekommt dagegen einen Default. Grund: Es handelt sich
um zwei verschiedene Fragen. `tagesgleicher_anker_noetig` ist eine
**Verhaltensentscheidung** (welcher Alarmpfad, welche Semantik) — ein
falscher Default wäre gefährlich still falsch. `now_utc` ist dagegen „wie
spät ist es" — ein Default auf die echte Wanduhr ist exakt das, was jeder
der 34 bestehenden direkten Aufrufe von `check_official_alert_triggers(trip)`
(8 Testdateien) und der beiden direkten Aufrufe von `_get_cached_weather`
(`tests/tdd/test_alert_anchor_day_guard.py`,
`tests/tdd/test_issue_823_snapshot_date_guard.py`) heute bereits implizit
tun. Ein Pflicht-Parameter hätte alle 10 Dateien zum Nacharbeiten gezwungen
— eine Scope-Explosion ohne fachlichen Gewinn, da keine dieser Testdateien
zonenübergreifende Trips baut. `check_all_trips` reicht ihren einen
`now_utc`-Wert explizit durch und ist damit in sich konsistent; alle anderen
Aufrufer erhalten unverändert das Verhalten von heute.

### Horizont-Guard in `check_radar_alerts`

Direkt nach der Segmentauswahl (vor der Throttle-/Ruhezeit-Prüfung, analog
zur Reihenfolge in `_build_starkregen_hint`):

```python
if active.start_time > now_utc:
    from services.radar_service import NOWCAST_HORIZON_MIN
    minutes_until_start = (active.start_time - now_utc).total_seconds() / 60.0
    if minutes_until_start > NOWCAST_HORIZON_MIN:
        logger.debug(
            f"Radar alert skipped: Segment beginnt erst in "
            f"{minutes_until_start:.0f} min (>{NOWCAST_HORIZON_MIN} min "
            f"Horizont) fuer {trip.id}"
        )
        continue
```

Kein `alert_log`-Eintrag — analog zu den bestehenden Zweigen „keine
Segmente"/„alle Segmente vorbei" ein paar Zeilen darüber, die ebenfalls ohne
Protokolleintrag `continue`n. Ein Protokolleintrag ist dem
Throttle-/Ruhezeit-Zweig vorbehalten, der einen sonst *fälligen* Alarm
unterdrückt — hier ist der Alarm schlicht noch nicht fällig.

### Zweiter Fund: `stage_date(lat, lon)`

```python
def stage_date(lat: float, lon: float) -> date:
    """Ortstag am Wegpunkt — dieselbe Formel wie in Produktion, nicht
    dieselbe Funktion: hier ist die Zone schon bekannt, keine Henne-Ei-Falle."""
    return local_dt(datetime.now(timezone.utc), tz_for_coords(lat, lon)).date()
```

`_tagesbezug` ruft `stage_date(lat, lon)` statt `stage_date()`;
`past_window_offsets` ebenso. Die zwölf Aufrufer übergeben dieselben
Koordinaten, die sie bereits für `active_window_offsets`/`past_window_offsets`
verwenden — eine mechanische, nicht-fachliche Änderung je Datei.

## Expected Behavior

- **Input:** Ein Lauf von `check_all_trips` oder `check_radar_alerts` zu
  einem beliebigen Zeitpunkt `now_utc`.
- **Output:** Jeder Trip wird anhand des **Ortstags seiner aktuellen Etappe**
  bewertet, nicht anhand des Serverdatums. Radar-Nowcast-Abrufe erfolgen nur
  für Segmente, die innerhalb von `NOWCAST_HORIZON_MIN` beginnen.
- **Side effects:** Für Trips, deren Zone während des gesamten Laufzeitraums
  mit dem Serverdatum übereinstimmt (die meisten Tests, alle Trips außerhalb
  der jeweiligen Randfenster), ist das Verhalten bit-identisch zu heute.

## LoC-Rahmen — nachgemessen und angehoben (PO 2026-08-10)

Die RED-Phase hat ergeben, dass der **Nachweis** ~742 LoC braucht statt der geschätzten
170–200. Nachgemessen, nicht geschätzt; auf ausdrückliche Ansage wurde **kein Test
weggekürzt**, um eine Zahl zu treffen. Zusammen mit ~300–330 LoC Produktivcode liegt die
Scheibe bei **~1070**.

Der PO hat entschieden: **eine Scheibe, Rahmen auf 1100** (statt der ebenfalls vorgelegten
Teilung in zwei Scheiben). Alle neun Akzeptanzkriterien bleiben in **einem** Änderungssatz.

**Zweite Anhebung auf 1400 (PO 2026-08-10), nach zwei Adversary-Fix-Schleifen.** Endstand
gemessen: **+1313/−123** in `src/` und `tests/`, netto **+1190** — davon **152 Zeilen
Produktivcode**. Der gesamte Zuwachs gegenüber 1100 sind Wächter, die der Adversary
erzwungen hat:

| Fund | Wirkort | Was ohne den Wächter passiert wäre |
|---|---|---|
| **F001** (CRITICAL) | `trip_alert.py:584` (`_get_cached_weather`, Δ-Anker-Pfad) | Die Korrektur ließ sich auf `date.today()` zurückdrehen, **ohne dass einer von 218 Tests rot wurde** |
| **F002** (HIGH) | `trip_alert.py:404` (`check_all_trips`, Filter `end_date < today`) | Dasselbe bei **266 Tests**. Wirkung: bei negativem UTC-Versatz (Los Angeles) gilt die Tour am letzten Ortstag zu früh als abgelaufen ⇒ übersprungen ⇒ keine Alarme — das ursprüngliche Fehlerbild an neuer Stelle |
| Nachbesserung AC-8 | `trip_day.py:71` (`anchor_tz`) | Der Anker ließ sich auf die bei #1470 mit zehn Stunden Abweichung verworfene Fassung zurückdrehen; gefangen hätte es nur die **geerbte** #1470-Suite, nicht der eigene Bestand |

**Die Lehre, die über diese Scheibe hinausgeht:** Dreimal in Folge war der Produktivcode
**korrekt** und trotzdem unbewacht. Jede Aufrufstelle rechnet ihren eigenen Ortstag und
braucht ihren eigenen Wächter — ein grüner Testlauf über alle neun Kriterien hat das
dreimal nicht bemerkt. Gemessen und abgeschlossen: `trip_alert.py` enthält genau **drei**
unabhängige `today = trip_local_today(...)`-Zuweisungen (`:404`, `:584`, `:901`), alle drei
sind jetzt einzeln durch eine Mutations-Gegenprobe belegt.

Das ist zugleich der Beleg für die Hausregel, den Aufwand des **Nachweises**
mitzuschätzen: die Verhaltensänderung ist klein (vier Aufrufstellen plus ein Guard), der
Nachweis das Achtfache davon.

Das ist ein Beleg für die Hausregel, den Aufwand des **Nachweises** mitzuschätzen und nicht
nur den des Fixes: die Kernänderung ist klein (vier Aufrufstellen plus ein Guard), der
Nachweis ist das Vielfache davon — drei Zeitzonen, zwei Sommerzeit-Wechseltage, ein
22-Stichproben-Bestandsschutz und ein Koordinaten-Nachweis, der eine stille Falsch-Ortung
sichtbar macht.

## Acceptance Criteria

- **AC-1 (Wirkung — Koordinatennachweis, nicht Alarm-Zähler):** Given ein
  Trip mit Etappe in Pacific/Auckland und Ortsdatum D, die Uhr steht auf
  einen Zeitpunkt innerhalb des Etappenfensters, an dem das Serverdatum noch
  D-1 ist / When der Scheduler `check_radar_alerts` über alle Trips dieses
  Nutzers laufen lässt / Then erfolgt der
  Nowcast-Abruf an den Koordinaten des tatsächlich begangenen Segments von
  Ortsdatum D — nicht an denen einer Etappe von D-1 oder gar keiner.
  - Test: `tests/tdd/test_radar_alert_follows_ortstag.py`,
    Ersetzung von `RadarNowcastService.get_nowcast` durch eine echte
    Funktion, die `(lat, lon)` protokolliert (Muster
    `test_starkregen_kurzfristhinweis.py::_install_fake_nowcast`); Assert
    protokollierte Koordinaten == Wegpunkt der D-Etappe.

- **AC-2 (Bestandsschutz):** Given ein Trip auf Korsika (Europe/Paris,
  UTC+2) mit einer gewöhnlichen Tagesetappe 08:00–19:00 Ortszeit / When
  `check_radar_alerts` zu allen 24 vollen Stunden eines Tages läuft / Then
  ist außerhalb des Fensters 22:00–00:00 UTC die ausgewählte Etappe an jeder
  geprüften Stunde identisch zum Verhalten vor dieser Änderung.
  - Test: parametrisierter Lauf über 22 Stichproben (jede volle Stunde
    außer 22 und 23 Uhr UTC) unter `freeze_time`; Assert gewähltes Segment
    unverändert gegenüber der alten `date.today()`-Formel als lokal
    hinterlegte Referenz.

- **AC-3 (das ehrliche Fenster):** Given derselbe Korsika-Trip aus AC-2, der
  zusätzlich eine Etappe am Folgetag trägt / When die Uhr
  auf 22:30 UTC steht (= 00:30 Ortszeit des Folgetags) / Then wählt
  `check_radar_alerts` die Etappe des
  Folgetags statt in `continue` zu enden — dies ist fachlich beabsichtigt,
  nicht ein Fehlerbild.
  - Test: `freeze_time("…T22:30:00Z")`, Assert gewähltes Segment gehört zur
    Folgetags-Etappe, Assert kein `continue` ohne jede Segmentwahl.

- **AC-4 (Horizont-Guard, mit Gegenprobe im selben Test):** Given zwei
  ansonsten gleiche Läufe, bei denen das gewählte Segment einmal später als
  `NOWCAST_HORIZON_MIN` in der Zukunft beginnt und einmal innerhalb dieses
  Horizonts / When `check_radar_alerts` in beiden Läufen die Segmentwahl
  durchlaufen hat und vor dem Nowcast-Abruf steht / Then unterbleibt der
  `get_nowcast`-Aufruf im Fern-Fall vollständig, während er im Nah-Fall
  genau einmal erfolgt — die Zahl der protokollierten Abrufe ist 0
  beziehungsweise 1.
  - Test: `tests/tdd/test_radar_alert_follows_ortstag.py`, Muster
    `test_starkregen_kurzfristhinweis.py::test_ac2_zeitfenster_guard_kein_fetch_ausserhalb_horizon`
    — echte Funktions-Ersetzung mit Aufruf-Liste, Fern-Fall (>60 min) und
    Nah-Fall (≤60 min) im selben Test.

- **AC-5 (kein neuer interner Bruch innerhalb von Kette A):** Given ein Trip,
  dessen Ortstag D vom Serverdatum D-1 abweicht, und ein Wetter-Schnappschuss,
  der **ausschließlich** unter dem Ortstag D abgelegt ist und für die
  Einsetzstunde des gewählten Segments angekündigten, nicht-konvektiven Regen
  ≥ 0,5 mm enthält / When `check_radar_alerts` läuft und der Radar für dieses
  Segment nicht-konvektiven Regen meldet / Then wird der Alarm **unterdrückt**
  („Briefing hatte das schon angekündigt") — was beweist, dass die
  Schnappschuss-Lesung unter **demselben** Ortstag nachgeschlagen hat wie die
  Segmentwahl.
  - **Gegenprobe im selben Test (die diskriminierende Hälfte):** derselbe
    Schnappschuss stattdessen **ausschließlich** unter dem Serverdatum D-1
    abgelegt / Then wird er **nicht** gefunden und der Alarm **feuert**.
    Genau dieser zweite Fall ist heute das Verhalten und wäre bei einer
    halbierten Umstellung (Segmentwahl auf Ortstag, Schnappschuss weiter auf
    Serverdatum) das Fehlerbild.
  - Test: `tests/tdd/test_radar_alert_follows_ortstag.py`, zwei Läufe unter
    derselben gestellten Uhr, Assert auf die Zahl zugestellter Alarme
    (0 bzw. 1). **Kein** Codereview-Assert, keine Struktur-Zusicherung — die
    Kopplung wird über ihre Wirkung gemessen, nicht über den Fundort im Code.
  - **Grenze dieses AC, ausdrücklich benannt:** AC-5 misst die *Kopplung*
    zwischen Segmentwahl und Schnappschuss-Lesung, nicht die Richtigkeit der
    Segmentwahl selbst — eine Wahl unter dem falschen Tag, die zufällig
    dieselben Koordinaten trifft, bliebe hier unbemerkt. Das deckt **AC-1**
    ab (Koordinatennachweis). Die beiden gehören zusammen; keines von beiden
    genügt allein.

- **AC-6 (Rückfallkette):** Given zwei Touren, von denen die eine keine
  Etappe am aufgelösten Tag hat, aber andere Etappen mit Wegpunkten trägt,
  und die andere überhaupt keine Etappe mit Wegpunkten besitzt / When
  `trip_local_today` für beide Touren die Zeitzone bestimmen muss, um daraus
  den Ortstag abzuleiten / Then fällt die erste auf die Zone der ersten
  Etappe mit Wegpunkten zurück und die zweite auf die aus
  `src/utils/timezone.py` importierte UTC-Konstante — an keiner Stelle auf
  ein hartverdrahtetes `ZoneInfo("UTC")`.
  - Test: `tests/unit/test_trip_local_today.py`, drei Fälle (Treffer,
    Rückfall 1, Rückfall 2) gegen `trip_day.trip_local_today`.

- **AC-7 (Sommerzeit, ADR-0044-Pflicht):** Given eine europäische Zone an
  beiden Umstellungstagen eines Jahres (Vorstellung und Rückstellung) / When
  `trip_local_today` für Zeitpunkte kurz vor und kurz nach der Umstellung
  ausgewertet wird / Then liefert sie an beiden Tagen den korrekten Ortstag —
  ohne die Rechenfalle „gleiche tzinfo ⇒ 24,0 Stunden an jedem Tag"
  (ADR-0044).
  - Test: `tests/unit/test_trip_local_today.py`, `freeze_time` auf beide
    Wechseltage 2026, Assert Ortstag korrekt vor/nach der Umstellungsstunde.

- **AC-8 (keine vierte Kopie):** Given der Umbau ist abgeschlossen / When
  `TripCommandProcessor` inspiziert wird / Then trägt die Klasse **nicht**
  mehr die Methoden `_trip_tz`/`_display_tz`/`_anchor_tz` als eigene
  Implementierung — sie ruft `trip_day` auf; im Repo existiert danach eine
  Auflösung, nicht zwei.
  - Test: `assert not hasattr(TripCommandProcessor, "_trip_tz")` (und
    Geschwister) in `tests/unit/test_trip_local_today.py`; zusätzlich bleibt
    die bestehende #1470-Suite
    (`tests/tdd/test_drilldown_day_window_local_date.py`) unverändert grün —
    Verhaltensnachweis, dass die Verschiebung nichts gebrochen hat.

- **AC-9 (geteilte Testfixture bleibt synchron — „Zweiter Fund"):** Given
  `tests/helpers/arrival_window_fixtures.py::stage_date(lat, lon)` wird für
  eine Korsika-Koordinate und für eine UTC-neutrale Koordinate unter
  identischer gestellter Uhr in der 22:00–00:00-UTC-Randzeit aufgerufen /
  When beide Ergebnisse verglichen werden / Then weicht die Korsika-Koordinate
  vom Serverdatum ab (Folgetag), während die UTC-neutrale Koordinate beim
  Serverdatum bleibt — die Fixture folgt derselben Formel wie
  `trip_alert.py`, nicht mehr der alten `date.today()`-Konstante.
  - Test: `tests/unit/test_arrival_window_fixtures.py`, neue Zusicherung
    unter `freeze_time` auf `…T22:30:00Z`.

## Known Limitations

- **Mehr-Zonen-Touren.** Wechselt der Wanderer an genau dem aufgelösten Tag
  die Zeitzone, kann die Etappe des Weltzeit-Tages eine andere Zone tragen
  als die des Ortstages. Der Restfehler ist die Differenz zweier
  benachbarter Etappen — **warum genau zwei:** der Anker nimmt die Etappe des
  Weltzeit-Tages (`anchor_tz`), der Ortstag höchstens die des Nachbartags;
  weiter als einen Tag können die beiden nie auseinanderliegen, weil kein
  UTC-Offset 24 h überschreitet. ADR-0044 stuft das als „in aller Regel null"
  ein. Bewusst nicht gebaut (PO-Entscheidung 2026-08-10).
- **Briefing-Schreiber bleibt auf Serverdatum.** `trip_report_scheduler.py`
  schreibt Schnappschüsse weiterhin unter `date.today()`/`+1`
  (`_get_target_date`, `:653-667`; Schreibstelle `save_dated`, `:1109`). Für
  positive UTC-Offsets (Europe, Auckland) bleibt
  das mit dem neuen Leser kompatibel, **weil** der Abend-Lauf bereits heute
  pauschal `+1 Tag` schreibt (`trip_report_scheduler.py:667`:
  `return today + timedelta(days=1)`), unabhängig von der tatsächlichen
  Ortszeit
  seines Laufzeitpunkts — dieser Vorgriff deckt sich mit dem Ortstag, den der
  Leser in der Randzeit sucht. Für negative Offsets (America/Los_Angeles)
  löst dieser Fix exakt die Lücke, die Messung 2 zeigt (3/4 → 4/4 Treffer),
  weil der Morgen-Lauf ohnehin unter dem für den lokalen Tag richtigen
  Serverdatum schreibt.
  **Verbleibende, nicht einmalige Lücke:** In der Randzeit selbst
  (22:00–00:00 UTC bzw. Zonen-Äquivalent) kann der Abend-Lauf zum
  Prüfzeitpunkt noch nicht gelaufen sein — dann findet `:971`
  (`_briefing_precip_for_onset`) **keinen** Schnappschuss unter dem neuen
  Ortstags-Schlüssel. Das ist **fail-soft, nicht einmalig**: `kein Schnappschuss
  ⇒ keine briefing-basierte Unterdrückung ⇒ der Radar-Alarm feuert trotzdem`
  (sichere Richtung — ein möglicher Zusatz-Alarm, kein verschluckter).
  **Belegt, nicht gefolgert:** `_briefing_precip_for_onset`
  (`src/services/trip_alert.py:838-865`) gibt bei `snapshot is None` sofort
  `None` zurück; die Unterdrückung an `:975` verlangt
  `_briefing_precip is not None and _briefing_precip >= 0.5`. Fehlender
  Schnappschuss kann also nur zu *weniger* Unterdrückung führen. **Die
  Gegenprobe zu AC-5 misst genau diesen Zweig** (Schnappschuss unter dem
  falschen Schlüssel ⇒ Alarm feuert) — die Limitation ist damit von einem
  laufenden Test gedeckt, nicht nur von einem Absatz. Das
  kann an jedem Tag in diesem 2-Stunden-Fenster erneut auftreten, abhängig
  vom konfigurierten `evening_time` des jeweiligen Trips, nicht nur einmalig
  bei der Umstellung.
- **Kette B unverändert.** `/jetzt`, `/status`, `_handle_query`,
  `command_date`, `inbound_telegram_reader.py`, `preview_service.py`,
  `api/routers/debug.py`, `tools/weather_validation.py` bleiben auf
  Serverzeit-Logik — eigenes Folge-Issue.
- **`_get_cached_weather`s Datums-Treffer bleibt ungeprüft frisch.** Der
  Fast-Path bei exaktem Schlüsseltreffer (`:571`) prüft nur die
  Datumsgleichheit, keine zusätzliche Alters-/Frische-Prüfung — unverändertes
  Verhalten von vor dieser Spec, nicht neu eingeführt.

## Nachweis-Strategie

- **Der wichtigste Test ist das Verhalten im 22:00–00:00-UTC-Fenster eines
  Korsika-Trips**, nicht Neuseeland — genau dort ändert sich etwas für den
  Bestand (AC-2/AC-3), und genau dort hätte eine unbelegte
  „bitgleich"-Behauptung den Fehler durchgelassen (Kontext-Dokument, Abschnitt
  „Nachgemessen und korrigiert").
- **Wirkung** wird über **Koordinaten** des abgefragten Segments
  nachgewiesen, nicht über einen Alarm-Zähler — ein Zähler hätte die
  Falsch-Ortung (falsches Segment, richtiger Alarm) nie bemerkt.
- **Uhr:** `freeze_time` (seit #1667 S1 Dev-Dependency). Keine DI-Naht: der
  Alarm-Pfad liest die Wanduhr an mehreren Stellen (`check_all_trips`,
  `check_radar_alerts`, der Testfixture selbst) — eine einzelne Naht wäre
  eine halbe Uhr.
- **Mutations-Gegenprobe (Pflicht, per Textersetzung + externer
  Sicherungskopie, kein `git checkout/stash/reset`):**
  1. `trip_local_today` in `trip_day.py` auf `date.today()` zurückgedreht ⇒
     der Auckland-Koordinatentest (AC-1) muss rot werden.
  2. Horizont-Guard aus `check_radar_alerts` entfernt ⇒ der AC-4-Fern-Fall
     muss rot werden (Aufruf-Liste nicht mehr leer).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0044 (bereits akzeptiert, keine neue ADR nötig)
- **Rationale:** Diese Spec setzt eine bereits getroffene Grundsatzentscheidung
  für Kette A (Alarm-/Radar-Pfad) um, statt eine neue zu treffen. Sie ändert
  weder die Auflösungsregel noch den Rückfallmechanismus aus ADR-0044 — sie
  überträgt sie unverändert von `TripCommandProcessor` (#1470, Kette
  Drilldown) auf `TripAlertService` (Kette A, Alarm/Radar) und behebt einen
  dadurch aufgedeckten Nebenbefund in der geteilten Testfixture.

## Changelog

- 2026-08-10: Initial spec created
