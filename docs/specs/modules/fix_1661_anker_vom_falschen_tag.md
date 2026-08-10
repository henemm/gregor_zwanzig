---
entity_id: fix_1661_anker_vom_falschen_tag
type: bugfix
created: 2026-08-10
updated: 2026-08-10
status: draft
workflow: fix-1661-anker-vom-falschen-tag
version: "1.0"
tags: [alerts, trip, compare, day-window, anchor, issue-1661, observability]
---

# Alarm-Anker vom falschen Tag wird still als gültig behandelt (Issue #1661)

## Approval

- [x] Approved — PO-Freigabe 2026-08-10 (alle 16 ACs auf Deutsch vorgelegt und bestätigt)

## Purpose

Der Abweichungs-Alarm eines Trips vergleicht die aktuelle Vorhersage gegen einen
gespeicherten Referenz-Wert ("Anker"). Fehlt für heute die tagesdatierte
Referenz, greift der Code auf eine undatierte Reservedatei zurück — und liest
sie **ungeprüft**, obwohl in der Datei selbst steht, für welchen Tag sie
eigentlich gilt. Am 08.08.2026 stammte diese Reservedatei vom Vortag (07.08.);
der Abweichungs-Wächter des Trips „KHW 403" lief dadurch rund 16 Stunden lang
strukturell blind, ohne dass irgendjemand das bemerkt hätte — ~28 stille
Alarm-Läufe im Viertelstundentakt. Diese Spec macht die Reservedatei
tages-geprüft (mit einer Alters-Grenze als Auffangnetz), stellt für den
Ortsvergleichs-Abendanker dieselbe Tages-Treue her und macht einen verworfenen
Anker erstmals sichtbar, statt ihn kommentarlos zu verwerfen.

Vollständige Herleitung, gemessene Produktivbelege und PO-Entscheidungen:
`docs/context/fix-1661-anker-vom-falschen-tag.md`. Diese Spec wiederholt nichts
davon, sondern zieht Scope und Acceptance Criteria daraus.

## Source

- **File:** `src/services/trip_alert.py`
- **Identifier:** `TripAlertService._get_cached_weather` (Zeile 484-512) — Kern
  des Bugs: `svc.load(trip.id)` in Zeile 509 wird ohne jede Prüfung
  zurückgegeben.
- Nebendateien: `src/services/weather_snapshot.py` (neue Leseoperation),
  `src/services/scheduler_dispatch_service.py`,
  `src/services/compare_location_weather_source.py`,
  `src/services/point_weather.py`, `src/services/compare_weather_snapshot.py`,
  `src/services/compare_alert.py` (Ortsvergleich-Teil),
  `src/services/alert_briefing_anchor.py`,
  `internal/scheduler/briefing_health.go` (Sichtbarkeit).

> **Schicht-Hinweis:** Python-Core (`src/services/`) für Anker-Prüfung,
> Datums-Feld und Diagnose-Schreiber; Go-API (`internal/scheduler/`) für die
> Aggregation am Status-Endpunkt. Kein Frontend-Code.

## Estimated Scope

- **LoC:** ~185-235 Produktivcode, ~80-150 Tests. Workflow-Limit für diese
  Scheibe auf 500 angehoben (PO-Entscheidung, drei Teile in einem Workflow,
  E1).
- **Files:** 9 Produktivdateien, 3 bestehende Testdateien (Attrappen-Signatur,
  je ~3 LoC), mindestens 2 neue Testdateien.
- **Effort:** medium-high — kritischer Alarm-Pfad, aber additive Änderungen
  ohne Schema-Bruch und ohne Migration.

### Affected Files

| Datei | Änderungstyp | Beschreibung |
|---|---|---|
| `src/services/weather_snapshot.py` | MODIFY | Neue schlanke Methode `load_target_date(trip_id) -> Optional[date]` — liest nur das `target_date`-Feld der undatierten Datei, ohne Segmente zu rekonstruieren |
| `src/services/trip_alert.py` | MODIFY | `_get_cached_weather` bekommt die Datums-/Alters-Prüfung (Teil A) und protokolliert/eskaliert einen verworfenen bzw. fehlenden Anker (Teil C). **Korrigiert 2026-08-10** (s. Abschnitt „🔴 Korrektur"): die Tages-/Altersprüfung gilt NUR dem Δ-Pfad (`:435`), NICHT dem amtliche-Warnungen-Pfad (`:1128`) — sonst verstummen Unwetterwarnungen für gebriefte, noch nicht gestartete Touren. Gesteuert über einen keyword-only Pflichtparameter ohne Default; zusätzlich musste das Tor `if not cached: continue` HINTER den amtlichen Check gezogen werden, sonst wirkt der Parameter nur im Test, nicht in Produktion |
| `src/services/scheduler_dispatch_service.py` | MODIFY | `_write_compare_alert_snapshots` bekommt einen Pflicht-Parameter `target_date`, gespeist aus dem bereits vorhandenen `target_date`-Parameter von `send_one_compare_preset` über die Closure `_anchor_and_reset()` |
| `src/services/compare_location_weather_source.py` | MODIFY | `fetch()` bekommt einen optionalen `target_date`-Parameter; steuert bei Angabe den Kalendertag des Zeitfensters statt des tatsächlichen „heute" |
| `src/services/point_weather.py` | MODIFY | `PointWeatherData` bekommt ein optionales Feld `target_date: Optional[date] = None` |
| `src/services/compare_weather_snapshot.py` | MODIFY | `target_date` additiv serialisieren (nur wenn gesetzt) und lesen (Altbestand liefert `None`) |
| `src/services/compare_alert.py` | MODIFY | `_evaluate_one_location` reicht das `target_date` des Ankers konditional an den Frisch-Abruf durch, wenn es gesetzt ist |
| `src/services/alert_briefing_anchor.py` | MODIFY | Neue Funktion `record_alert_anchor_rejected(...)`, fail-soft, Muster `record_briefing_dispatch_failure` (#1629) |
| `internal/scheduler/briefing_health.go` | MODIFY | Neuer Analyzer `analyzeAlertAnchorRejections` (Lücken-Schwelle 60 min) + neues Feldpaar an `BriefingHealth()` |
| `tests/tdd/test_compare_alert_day_window.py` | MODIFY | Attrappen-`fetch()`-Signatur (Zeile 397-400) bekommt `target_date`; AC-5-Docstring wird umformuliert (s. u.) |
| `tests/tdd/test_compare_briefing_anchor_survives_dispatch_failure.py` | MODIFY | Attrappen-Signatur (Zeile 96-100) bekommt `target_date` |
| `tests/tdd/test_compare_briefing_anchor_and_memory_reset.py` | MODIFY | Attrappen-Signatur (Zeile 188-196) bekommt `target_date` |
| `tests/tdd/test_alert_anchor_day_guard.py` | CREATE | Teil A + C (Trip): Tages-/Alters-Prüfung, Sichtbarkeit, Bug-Nachweis |
| `tests/tdd/test_compare_anchor_target_date.py` | CREATE | Teil B (Compare): `target_date`-Weitergabe Anker ↔ Frisch-Abruf |
| `internal/scheduler/briefing_health_test.go` (oder gleichwertig) | CREATE | Go-Analyzer `analyzeAlertAnchorRejections` |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `WeatherSnapshotService.load`/`load_dated` | function | unverändert weiterverwendet — `load_target_date` ist eine NEUE, schlanke Ergänzung, kein Ersatz |
| `alert_briefing_anchor.record_briefing_dispatch_failure` (#1629) | function | Vorbild (Signatur, fail-soft-Muster, JSONL-Format) für `record_alert_anchor_rejected` |
| `alert_briefing_anchor.write_anchor_and_reset_memory` | function | geteilter Baustein Trip+Compare — bleibt unverändert; `_anchor_and_reset()` in `scheduler_dispatch_service.py` ruft ihn weiterhin identisch auf |
| `internal/scheduler/briefing_health.go` `analyzeBriefingDispatchErrors` (#1629) | function | Vorbild für `analyzeAlertAnchorRejections` (Streak-/Lücken-Logik, Privacy-Filter) |
| `compare_alert.py` `_anchor_too_old`/`_MAX_ANCHOR_AGE` | function/const | unverändert, läuft weiterhin VOR der neuen `target_date`-Weitergabe |
| `send_one_compare_preset(..., target_date=...)` (#1232) | function | trägt bereits den korrekten Tag (Morgen-Slot → heute, Abend-Slot → heute+1, s. `compare_slot_scheduler.py:109-112`) — wird hier zum ersten Mal bis zum Δ-Anker durchgereicht |
| `docs/specs/modules/fix_1584c_compare_alarm_zeitfenster.md` | doc | führte `_MAX_ANCHOR_AGE`/26 h und AC-5 ein — AC-5 wird hier fachlich neu gefasst, nicht gebrochen (E3) |
| `docs/specs/modules/fix_1629_briefing_anker_versandfehler.md` | doc | nennt #1661 wörtlich als Folgescheibe; liefert das Diagnose-Muster |

## Nicht in dieser Scheibe

- **Rauschen der Warnzeile „No fresh weather data"** (`trip_alert.py:237`,
  ~1350 Journal-Treffer) — Sammel-Eintrag in **#1199**. Diese Zeile gehört zum
  Frisch-Abruf-Pfad, nicht zum hier behandelten Anker-Rückfall.
- **Rückwirkendes Neuschreiben verworfener Anker.** Ein verworfener Anker
  bleibt verworfen; der nächste reguläre Briefing-Lauf stellt ihn automatisch
  wieder her. Ein Neuschreiben aus dem Alarm-Pfad heraus widerspräche ADR-0009
  und der #1584c-AC-7-Lehre (aus zeitweiliger Unterdrückung würde sonst
  Dauerstille).
- **#1007-Abweichung in `trip_command_processor.py:294-303`.** Der
  On-Demand-Pfad (`/heute`-Kommando) schreibt einen Snapshot direkt über
  `WeatherSnapshotService.save()` und umgeht damit
  `write_anchor_and_reset_memory()`, das bei `on_demand=True` bewusst
  aussteigt. Er überschreibt dadurch den undatierten Trip-Anker, den der
  Alarm als Netz nutzt. **Bekannte, unveränderte Abweichung** — wird hier nur
  benannt, nicht behoben (eigenes Issue nötig, falls das PO-Entscheidung
  erfordert).
- **Mitternachts-Tagesfenster beim Compare-Segment** (`start_hour > end_hour`)
  — bestehende, unveränderte Grenze aus `fix_1584c`, hier nicht angefasst.
- **Neu-Kalibrierung von Δ-Schwellen** für den Compare-Alarm — unverändert.

## Implementation Details

### Teil A — Trip-Leseseite: Anker vom falschen Tag wird verworfen

`WeatherSnapshotService.load_target_date(trip_id: str) -> Optional[date]`
(`weather_snapshot.py`): öffnet dieselbe Datei wie `load()`
(`{trip_id}.json`), liest **ausschließlich** das `target_date`-Feld und
parst es über `date.fromisoformat(...)`. Jeder Fehler (Datei fehlt, JSON
korrupt, Feld fehlt, Wert unlesbar) wird abgefangen und ergibt `None` — exakt
das gleiche fail-soft-Muster wie `load()`/`load_dated()`. Bewusst eine
**eigene** Methode statt eines geänderten Rückgabewerts von `load()` (A1):
`load()` hat drei Aufrufer, zwei davon (`weather_extractor.py:84,127`) sind
reine Anzeigepfade für `/heute`-/`/morgen`-Kommandos, die bewusst „was auch
immer da ist" zeigen sollen — ein geänderter Rückgabetyp würde deren Semantik
still mitverändern.

`TripAlertService._get_cached_weather` (`trip_alert.py:484-512`) bekommt die
eigentliche Prüfung — Prüfort = Wirkort (A2), symmetrisch zur Begründung in
`compare_alert.py:399-401`:

```
dated = svc.load_dated(trip.id, today)
if dated is not None:
    return dated

undated = svc.load(trip.id)
if undated is None:
    # Fall 3: gar kein Anker — Behandlung s. Teil C.
    ...
    return None

target_date = svc.load_target_date(trip.id)
if target_date == today:
    return undated

if target_date is None:
    age = now_utc - undated[0].fetched_at
    if age <= timedelta(hours=26):
        return undated
    reason = "too_old"
else:
    reason = "wrong_day"

# Fall 1/2: verwerfen — Behandlung s. Teil C.
...
return None
```

Das Altersnetz (A3) greift **ausschließlich**, wenn `target_date` fehlt oder
unlesbar ist — ein vorhandenes, aber falsches Datum wird bereits vom
Datumsabgleich erledigt; ein Altersnetz würde dort ein inhaltlich falsches
Datum durchwinken, solange es frisch geschrieben ist. Grenze 26 Stunden,
derselbe Wert wie beim Ortsvergleich (`compare_alert.py::_MAX_ANCHOR_AGE`) und
aus demselben Grund (Briefings laufen 1-2×/Tag) — geteilt wird nur der
**Zahlenwert**, nicht der Code (A2): die Trip-Seite bekommt ein eigenes,
schärferes Kriterium (Datum zuerst), der Ortsvergleich behält seine
bestehende, unveränderte `_anchor_too_old`-Prüfung.

Verwerfen heißt genau: `None` zurückgeben (A4). Kein Anfassen von
`alert_state`/Cooldown, kein Neuschreiben des Ankers — sonst würde aus
zeitweiliger Unterdrückung Dauerstille (Lehre `fix_1584c` AC-7).

### 🔴 Korrektur 2026-08-10 (Phase 6, gemessen): die Prüfung gilt NUR dem Δ-Pfad

Der folgende Absatz war **falsch** und ist abgelöst. Er ordnete an, dass die
Datums-/Alters-Prüfung beide Aufrufer aus einer zentralen Stelle versorgt. Die
Umsetzung nach dieser Anweisung machte zwei Bestandstests rot
(`tests/tdd/test_alert_state_briefing_reset.py`, #1614) und deckte dabei den
eigentlichen Fehler auf:

`check_official_alert_triggers` (`trip_alert.py:1202-1276`) benutzt `cached`
**nicht** als Δ-Vergleichspunkt, sondern ausschließlich als **Routen-Geometrie
mit absoluten Zeiten**: es liest `segment.start_point.lat/lon`, gruppiert nach
Koordinate und Zeitfenster und **überspringt vergangene Etappen einzeln**
(`if end_time is None or end_time < now_utc: continue`, `:1256`). Der Pfad ist
gegen einen veralteten Anker also **selbst abgesichert** — und laut #1460 P4
prüft er bewusst die gesamte Restroute mit Tagen Vorlauf.

Die zentrale Prüfung hätte deshalb **amtliche Warnungen stummgeschaltet** für
Touren, die bereits gebrieft, aber noch nicht gestartet sind: deren undatierter
Anker trägt `target_date = Starttag` (also „morgen"), würde als `wrong_day`
verworfen, und `check_official_alert_triggers` gäbe sofort `[]` zurück — in
genau den Tagen vor dem Aufbruch, in denen eine Unwetterwarnung am meisten zählt.
Das wäre ein schwererer Schaden als der behobene.

**Gültig ist:** die Datums-/Alters-Prüfung wirkt **nur** auf dem
Abweichungs-Alarm-Pfad (`check_and_send_alerts`, Tor `:434-437`). Der
amtliche-Warnungen-Pfad (`:1128-1130`) lädt weiterhin ungeprüft und behält
seinen eigenen, feineren Zeitfilter pro Etappe. Prüfort = Wirkort, sauber
angewandt: der Δ-Vergleich braucht einen Anker **desselben Tages**, die
Geometrie-Auswertung braucht Koordinaten und absolute Zeiten — zwei
verschiedene Anforderungen, zwei verschiedene Prüfungen.

Die freigegebenen Acceptance Criteria bleiben davon **unberührt** — sie sprechen
durchgehend vom Abweichungs-Alarm, nie von amtlichen Warnungen. AC-13/AC-14
(fehlender Anker) gelten unverändert für beide Tore, weil „gar kein Anker"
auch die Geometrie-Auswertung leerlaufen lässt.

<details>
<summary>Abgelöster Absatz (Stand Freigabe, nur zur Nachvollziehbarkeit)</summary>

**Warum eine zentrale Stelle beide „Tore" versorgt:** `check_and_send_alerts`
(Gate `trip_alert.py:434-437`, `if not cached: continue`) und
`check_official_alert_triggers` (Gate `trip_alert.py:1128-1130`,
`if not cached: return []`) rufen **beide** `self._get_cached_weather(trip)`
auf. Die Prüfung, das Logging und die Eskalation leben deshalb bewusst in
dieser einen Methode statt doppelt an den beiden Aufrufstellen — sie erhält
`trip` bereits als Parameter und kann `trip.start_date`/`trip.end_date` direkt
auswerten.

</details>

### Teil B — Ortsvergleich-Abendanker trägt das richtige Datum

`send_one_compare_preset(preset, settings, user_id, data_root, ...,
target_date=None)` (`scheduler_dispatch_service.py:297-323`) hat bereits einen
`target_date`-Parameter (#1232): Morgen-Slot → heute, Abend-Slot → heute+1
(`compare_slot_scheduler.py:109-112`). Bislang endet dieser Wert beim
E-Mail-Betreff (`build_compare_preset_subject`); die Closure
`_anchor_and_reset()` (`:407-420`), die im selben Funktions-Scope liegt, gibt
ihn **nicht** an `_write_compare_alert_snapshots()` weiter.

`_write_compare_alert_snapshots(preset_id, locations, user_id, preset,
target_date)` (`:496-532`) bekommt `target_date` als **Pflicht**-Parameter
ohne Default — dieselbe Begründung wie beim bereits pflichtigen
`preset`-Parameter (Adversary-Finding F001 der Vorgänger-Scheibe): ein
vergessenes Argument mit `=None` würde still auf „heute" zurückfallen und den
Abendanker wieder mit dem falschen Tag beschriften. Reicht `target_date`
durch an `CompareLocationWeatherSource.fetch(loc.id, loc.lat, loc.lon,
start_hour, end_hour, target_date)`.

`CompareLocationWeatherSource.fetch()` (`compare_location_weather_source.py`)
bekommt einen optionalen `target_date: Optional[date] = None`. Ohne Angabe
verhält sich `fetch()` exakt wie heute: `local_today` wird aus
`now.astimezone(tz).date()` gebildet (B1). Mit Angabe wird `target_date`
STATT `local_today` als Kalendertag für die Fenstergrenzen verwendet — der
Abendanker deckt damit den Tag ab, über den das Briefing tatsächlich
informiert (heute+1), nicht den Schreibtag. Das zurückgegebene
`PointWeatherData` trägt `target_date` zusätzlich als Feld.

`PointWeatherData` (`point_weather.py`) bekommt ein optionales Feld
`target_date: Optional[date] = None` (B1, additiv). `TripSegmentWeatherAdapter`
setzt es nicht (Trip-Pfad hat sein eigenes, bestehendes Datums-Schema über
Dateinamen).

`CompareWeatherSnapshotService.save()`/`load()`
(`compare_weather_snapshot.py`) serialisieren/lesen `target_date` additiv —
nur geschrieben, wenn gesetzt (`point.target_date.isoformat()` bzw. Feld
fehlt in der JSON); beim Lesen liefert ein fehlendes Feld `None`. Dateiname
und Ablageort (`{preset_id}__{location_id}.json`) bleiben unverändert — kein
neues Schema, kein Pruning, keine Migration. Altbestand (Dateien ohne das
Feld) verhält sich exakt wie heute.

`CompareAlertService._evaluate_one_location` (`compare_alert.py:352-385`)
reicht das `target_date` des geladenen Ankers **konditional** an den
Frisch-Abruf weiter (B2):

```
cached = self._snapshot_service.load(preset_id, location_id)
if cached and self._anchor_too_old(cached[0], preset_id, location_id):
    return None
start_hour, end_hour = day_window
anchor_target_date = cached[0].target_date if cached else None
fresh_point = self._weather_source.fetch(
    location_id, loc.lat, loc.lon, start_hour, end_hour,
    target_date=anchor_target_date,
)
```

Ohne gesetztes `target_date` (Morgen-Slot-Preset, Altbestand) ist das
Verhalten identisch zu heute — `fetch()` fällt auf `local_today` zurück.
Nur wenn der Anker ein Datum trägt (Abend-Slot-Preset), holt der Frisch-Abruf
DENSELBEN Tag statt des tatsächlichen „heute" — Anker und Frisch-Abruf
beschreiben dadurch **immer denselben Kalendertag**, unabhängig davon, wann
der 15-Minuten-Check läuft (Nachzug der `fix_1584c`-AC-5-Zusicherung, E3;
`_anchor_too_old`/`_MAX_ANCHOR_AGE` bleiben davor unangetastet, B3).

### Teil C — Sichtbarkeit: ein verworfener oder fehlender Anker bleibt nicht stumm

`record_alert_anchor_rejected(*, user_id: str, entity_id: str, reason: str)`
(`alert_briefing_anchor.py`), fail-soft nach dem Muster von
`record_briefing_dispatch_failure` (#1629): hängt eine JSONL-Zeile
`{"ts": ..., "entity_id": ..., "reason": ...}` an
`data/users/<uid>/diagnostics/alert_anchor_rejected.jsonl` an
(`reason` ∈ `"wrong_day"`, `"too_old"`, `"missing"`). Jeder Fehler beim
Schreiben wird gefangen und nur geloggt — ein defekter Diagnose-Schreiber darf
den Alarm-Lauf nie zusätzlich zum Absturz bringen.

**Drei Fälle, zwei Behandlungen (C2), alle in `_get_cached_weather`:**

1. **„Anker vom falschen Tag"** (`target_date` gesetzt, aber ≠ heute) und
2. **„Anker zu alt"** (`target_date` fehlt/unlesbar UND Alter > 26 h) —
   beide werden **unbedingt** eskaliert: `logger.warning(...)` MIT
   Trip-Kennung und Grund, UND `record_alert_anchor_rejected(...)`. Existiert
   überhaupt ein Anker, ist mindestens ein Briefing gelaufen — das
   rechtfertigt die Eskalation unabhängig vom Trip-Laufzeitraum.
3. **„Gar kein Anker"** (weder datierte noch undatierte Datei vorhanden) ist
   für einen noch nicht gestarteten Trip der harmlose Normalfall (noch kein
   Briefing gelaufen) — dort NUR eine `logger.debug`-Zeile, KEIN
   `record_alert_anchor_rejected`-Aufruf (sonst Dauerrauschen, #1199-Muster).
   Läuft der Trip dagegen bereits
   (`trip.start_date is not None and trip.end_date is not None and
   trip.start_date <= date.today() <= trip.end_date`), ist „kein Anker"
   ebenfalls eskalationswürdig: `logger.warning(...)` UND
   `record_alert_anchor_rejected(..., reason="missing")` — die Wache ist bei
   einem laufenden Trip komplett blind, und genau das soll auffallen.

`internal/scheduler/briefing_health.go` bekommt einen neuen Analyzer
`analyzeAlertAnchorRejections(dataDir string, now time.Time) (string, int)`,
strukturell identisch zu `analyzeBriefingDispatchErrors` (Glob über
`users/*/diagnostics/alert_anchor_rejected.jsonl`, nur `ts` wird dekodiert —
**Privacy #252: weder `entity_id` noch `reason` verlassen die Go-Seite**).
Eigene Lücken-Schwelle `alertAnchorRejectedGapThreshold = 60 * time.Minute`
(NICHT die 26 h der Briefing-Diagnose, NICHT die 2 h der Provider-Diagnose):
der Abweichungs-Alarm läuft alle 15 Minuten, ein Ausbleiben über eine Stunde
markiert also bereits einen echten Aussetzer, während 26 h denselben Fehler
tagelang unsichtbar ließen. `BriefingHealth()` bekommt zwei neue
Feldpaar-Einträge: `alert_anchor_rejected_streak_since` und
`alert_anchor_rejected_recent_count` — Namens- und Formelanalogie zu den
bestehenden `*_streak_since`/`*_recent_count`-Paaren, damit dieselbe externe
Eskalationsformel (`now - streak_since`) ohne Anpassung greift.

## Expected Behavior

- **Input:** ein Alarm-Lauf für einen Trip, dessen datierter Anker für heute
  fehlt und dessen undatierter Rückfall ein `target_date` ungleich heute trägt
  (oder gar kein `target_date`, mit Alter > 26 h); ein Ortsvergleich-Preset mit
  aktiviertem Abend-Slot.
- **Output:** ein Anker vom falschen Tag oder zu alter Anker wird verworfen
  (`None`), NICHT stillschweigend als gültig verwendet; der Compare-Abendanker
  trägt `target_date = heute+1` und der zugehörige 15-Minuten-Frisch-Abruf holt
  denselben Tag; ein verworfener oder (bei laufendem Trip) fehlender Anker
  erzeugt einen Diagnose-Eintrag, der am Status-Endpunkt sichtbar wird.
- **Side effects:** ein neuer, kleiner JSONL-Diagnose-Eintrag je betroffenem
  Nutzer; zwei neue Felder am bestehenden `/api/scheduler/status`. Kein neuer
  HTTP-Aufruf, kein neuer Endpunkt, keine Migration von Bestandsdaten.

## Acceptance Criteria

- **AC-1 (Bug-Nachweis, Teil A):** Given kein datierter Wetter-Anker für heute
  existiert und der undatierte Rückfall ein `target_date` von gestern trägt
  (genau der gemessene Produktivfall vom 08.08.2026), When der
  Abweichungs-Alarm-Lauf für diesen Trip startet, Then wird dieser Anker
  verworfen (kein Alarm-Vergleich gegen den falschen Tag) UND es erscheint eine
  WARNUNG mit Grund „falscher Tag" statt eines stillen Durchlaufs.
  - Test: Kern. `_get_cached_weather()` bzw. der volle
    `check_and_send_alerts()`-Pfad mit einer präparierten undatierten
    Snapshot-Datei (`target_date` = gestern), kein datierter Snapshot. Assert:
    Rückgabe `None`, WARNING-Logzeile mit Trip-Kennung, KEIN Alarm-Versand aus
    diesem (falschen) Vergleich.
  - Scheitert ohne Fix: `svc.load(trip.id)` wird ungeprüft zurückgegeben, der
    Alarm-Lauf vergleicht heutige Segmente gegen einen Referenzwert von gestern.

- **AC-2 (Regressionsschutz — richtiges Datum bleibt gültig):** Given kein
  datierter Anker für heute existiert und der undatierte Rückfall `target_date =
  heute` trägt, When der Alarm-Lauf startet, Then wird der Rückfall weiterhin
  normal als Vergleichsbasis verwendet — keine Verschärfung ohne Grund.
  - Test: Kern. Wie AC-1, aber `target_date` = heute. Assert: Rückgabe ist die
    geladenen Segmente, kein Verwerfen, keine WARNUNG.

- **AC-3 (Altersnetz greift nur bei fehlendem Datum, innerhalb der Grenze):**
  Given der undatierte Rückfall trägt KEIN lesbares `target_date` (reiner
  Absicherungsfall — das Feld wird seit jeher geschrieben, es geht also um eine
  beschädigte oder unvollständige Datei), ist aber jünger als 26 Stunden
  (`snapshot_at`), When der Alarm-Lauf startet, Then wird der Rückfall
  weiterhin verwendet.
  - Test: Kern. Snapshot-Fixture ohne `target_date`-Feld, `snapshot_at` = jetzt
    minus 10 h. Assert: Rückgabe ist die geladenen Segmente.

- **AC-4 (Altersnetz verwirft, außerhalb der Grenze):** Given der undatierte
  Rückfall trägt KEIN lesbares `target_date` UND ist älter als 26 Stunden
  (`snapshot_at`), When der Alarm-Lauf startet, Then wird er verworfen UND es
  erscheint eine WARNUNG mit Grund „zu alt".
  - Test: Kern. Wie AC-3, aber `snapshot_at` = jetzt minus 27 h. Assert:
    Rückgabe `None`, WARNING-Logzeile, `record_alert_anchor_rejected` wurde
    mit `reason="too_old"` aufgerufen (Diagnose-Datei enthält die Zeile).
  - Scheitert ohne Fix: ein Uralt-Snapshot (im gemessenen Bestand bis zu 57
    Tage alt) würde unbegrenzt weiterverwendet.

- **AC-5 (Verworfener Anker rührt niemals Melde-Gedächtnis oder Cooldown an):**
  Given ein Anker wird verworfen (Fall AC-1 oder AC-4), When der Alarm-Lauf
  diesen Fall durchläuft, Then bleiben `alert_state` und der Cooldown-Zähler
  für diesen Trip exakt unverändert, UND der verworfene Anker wird NICHT neu
  geschrieben.
  - Test: Kern. `AlertStateService`-Zustand vor und nach dem Lauf vergleichen
    (identisch); Dateizeitstempel der undatierten Snapshot-Datei vor/nach dem
    Lauf vergleichen (identisch — kein Neuschreiben).
  - Mutations-Gegenprobe: Schriebe der Fix versehentlich den Anker beim
    Verwerfen neu oder setzte er `alert_state` zurück, MUSS dieser Test rot
    werden (Lehre `fix_1584c` AC-7 — sonst wird aus temporärer Unterdrückung
    Dauerstille).

- **AC-6 (Regressionsschutz — Anzeigepfade bleiben unangetastet):** Given die
  Kommandos `/heute` und `/morgen` (bzw. deren interne Entsprechung in
  `weather_extractor.py`), When sie denselben undatierten Snapshot lesen, den
  der Alarm-Pfad soeben verworfen hätte, Then zeigen sie ihn trotzdem an — ihr
  Verhalten ändert sich durch diese Scheibe NICHT.
  - Test: Kern. `WeatherExtractor.timeline()`/`.drilldown()` mit derselben
    Fixture wie AC-1 (falsches `target_date`) aufrufen — Assert: Ergebnis zeigt
    weiterhin die vorhandenen Daten (`available=True`), keine neue
    Datumsprüfung in diesem Pfad.

- **AC-7 (Teil B — Abendanker trägt den gebriefte Tag):** Given ein
  Ortsvergleich-Preset mit aktiviertem Abend-Slot, When der Abend-Report
  versendet wird und dabei den Δ-Anker schreibt, Then trägt der gespeicherte
  Δ-Anker `target_date = heute+1` (den Tag, über den das Briefing tatsächlich
  informiert), NICHT den Schreibtag.
  - Test: Kern. `send_one_compare_preset(..., target_date=morgen)` über den
    echten Sendepfad (Muster `Szenario.versand()` aus
    `test_compare_alert_day_window.py`) mit `mail_sink`-Naht laufen lassen,
    danach `CompareWeatherSnapshotService.load()` prüfen: `target_date` des
    gespeicherten Ankers ist der übergebene Tag.
  - Scheitert ohne Fix: `_write_compare_alert_snapshots` bekommt `target_date`
    nicht durchgereicht, der Anker trägt weiterhin keinerlei Tagesbezug.

- **AC-8 (Teil B — Anker und Frisch-Abruf beschreiben denselben Tag):** Given
  ein Δ-Anker mit gesetztem `target_date` (Abend-Slot-Preset), When der
  15-Minuten-Alarm-Check den Frisch-Abruf für diesen Ort holt, Then bezieht sich
  der Frisch-Abruf auf DENSELBEN Kalendertag wie der Anker — unabhängig davon,
  welcher Tag beim Check gerade „heute" ist.
  - Test: Kern. Anker mit `target_date` = morgen schreiben (wie AC-7), Alarm-Check
    noch am selben Kalendertag (heute) laufen lassen — Assert (über die
    Spionage-Wetterquelle aus `test_compare_alert_day_window.py`): das an
    `fetch()` übergebene `target_date` entspricht dem Anker-`target_date`, nicht
    dem tatsächlichen „heute".
  - Dies ist die neu gefasste Zusicherung, die `fix_1584c` AC-5 ablöst (s. u.
    „Bekannte, zu Recht rote Bestandstests").

- **AC-9 (Teil B — Morgen-Slot bleibt unverändert):** Given ein
  Ortsvergleich-Preset OHNE aktivierten Abend-Slot (Produktiv-Regelfall: 4 von
  5 Presets), When der Morgen-Report den Δ-Anker schreibt, Then trägt der Anker
  `target_date = heute`, und der nachfolgende Alarm-Check verhält sich exakt wie
  vor dieser Scheibe.
  - Test: Kern. Wie AC-7, aber `target_date = heute` (Morgen-Slot-Default).
    Assert: gespeicherter Anker trägt `target_date = heute`; Frisch-Abruf ohne
    Anker-Datum verhält sich identisch zum Bestand (Regressionstest gegen
    `test_compare_alert_day_window.py` AC-1/AC-2/AC-3a/AC-3b).

- **AC-10 (Teil B — Altbestand ohne `target_date` bleibt unverändert):** Given
  ein Compare-Δ-Anker aus der Zeit vor dieser Scheibe (Datei ohne
  `target_date`-Feld), When der Alarm-Check ihn lädt, Then wird `target_date`
  als `None` gelesen und der Frisch-Abruf verhält sich exakt wie heute (lokaler
  laufender Tag) — kein Fehler, keine Migration nötig.
  - Test: Kern. Fixture-Datei ohne `target_date`-Schlüssel direkt anlegen (nicht
    über `save()`), `CompareWeatherSnapshotService.load()` aufrufen — Assert:
    `target_date is None`, kein Absturz, Frisch-Abruf-Fenster identisch zum
    Bestandsverhalten.

- **AC-11 (Teil C — verworfener Anker wird sichtbar):** Given ein Anker wird
  verworfen (Fall „falscher Tag" oder „zu alt", AC-1/AC-4), When das passiert,
  Then entsteht ein Diagnose-Eintrag, der über den Status-Endpunkt
  (`/api/scheduler/status`) als wachsendes Signal sichtbar wird — nicht nur als
  Logzeile, die im Dauerrauschen untergeht.
  - Test: Kern. Nach AC-1/AC-4 die Datei
    `data/users/<uid>/diagnostics/alert_anchor_rejected.jsonl` prüfen (Zeile
    vorhanden, `ts` gesetzt) UND `analyzeAlertAnchorRejections()` (Go) mit dieser
    Fixture aufrufen — `recentCount >= 1`.

- **AC-12 (Teil C — wachsendes Signal bei Serie):** Given mehrere
  aufeinanderfolgende Anker-Ablehnungen desselben Nutzers innerhalb von 60
  Minuten, When der Status-Endpunkt abgefragt wird, Then wächst
  `alert_anchor_rejected_streak_since` NICHT mit jeder weiteren Ablehnung nach
  vorne (bleibt der Serienbeginn), UND eine Lücke von mehr als 60 Minuten ohne
  neue Ablehnung beendet die Serie.
  - Test: Kern. `analyzeAlertAnchorRejections()` mit einer JSONL-Fixture aus
    mehreren dicht aufeinanderfolgenden Zeitstempeln (< 60 min Abstand) plus
    einem weit zurückliegenden Ausreißer (> 60 min Lücke) — `streak_since`
    bleibt der jüngere Serienbeginn (Lücken-Logik wie
    `analyzeBriefingDispatchErrors`).

- **AC-13 (Teil C — laufender Trip ohne jeden Anker eskaliert):** Given ein
  Trip, dessen Laufzeitraum bereits begonnen hat und noch nicht vorbei ist
  (`start_date <= heute <= end_date`), aber weder eine datierte noch eine
  undatierte Anker-Datei existiert, When der Alarm-Lauf ihn prüft, Then wird das
  als Eskalationsfall behandelt — WARNUNG UND Diagnose-Eintrag mit
  `reason="missing"`, nicht nur eine leise Logzeile.
  - Test: Kern. Trip-Fixture mit `start_date`/`end_date` um heute herum, KEINE
    Snapshot-Dateien vorhanden. Assert: WARNING-Logzeile, Diagnose-Datei enthält
    eine Zeile mit `reason="missing"`.
  - Scheitert ohne Fix: ein laufender Trip ohne jedes Briefing bliebe komplett
    unsichtbar blind — kein Nutzer und kein Betrieb würde es je erfahren.

- **AC-14 (Teil C — noch nicht gestarteter Trip ohne Anker ist der harmlose Normalfall):**
  Given ein Trip, dessen Laufzeitraum noch NICHT begonnen hat
  (`start_date > heute`), und weder eine datierte noch eine undatierte
  Anker-Datei existiert, When der Alarm-Lauf ihn prüft, Then erscheint NUR eine
  sichtbare Logzeile (DEBUG-Ebene) — KEIN Diagnose-Eintrag, keine Eskalation.
  - Test: Kern. Trip-Fixture mit `start_date` = übermorgen, keine
    Snapshot-Dateien. Assert: KEINE Zeile in
    `alert_anchor_rejected.jsonl` entsteht, während die Logzeile trotzdem
    erscheint (verifiziert über `caplog`, nicht über Dateiinhalt-String-Suche).
  - Scheitert bei zu aggressiver Eskalation: ohne diese Unterscheidung würde
    JEDER noch nicht gestartete Trip täglich Dauerrauschen erzeugen
    (#1199-Muster).

- **AC-15 (Teil C — Diagnose-Schreiber ist fail-soft):** Given der
  Diagnose-Schreiber `record_alert_anchor_rejected` selbst scheitert (z. B.
  nicht beschreibbares Zielverzeichnis), When gleichzeitig ein Anker verworfen
  wird (AC-1/AC-4/AC-13), Then bricht der Alarm-Lauf dadurch NICHT zusätzlich
  ab — der verworfene-Anker-Fall wird trotzdem korrekt behandelt (Rückgabe
  `None`, WARNUNG), nur der Diagnose-Eintrag fehlt.
  - Test: Kern. Zielverzeichnis vor dem Aufruf unschreibbar machen (bzw.
    `record_alert_anchor_rejected` mit simuliertem `OSError` versehen),
    restlichen Ablauf wie AC-1 prüfen — Assert: Alarm-Lauf terminiert normal,
    nur eine WARNUNG zum Diagnose-Fehler zusätzlich.

- **AC-16 (Teil C — Privacy #252 an der Go-Grenze):** Given eine Zeile in
  `alert_anchor_rejected.jsonl` enthält `entity_id` (Trip-ID) und `reason`,
  When `analyzeAlertAnchorRejections` (Go) diese Zeile verarbeitet, Then landen
  weder `entity_id` noch `reason` im Rückgabewert oder in `BriefingHealth()` —
  nur Zeitstempel-abgeleitete Zahlen und ein ISO-Zeitstempel.
  - Test: Kern (Go). Fixture-JSONL mit `entity_id`/`reason` einlesen,
    Rückgabewert von `analyzeAlertAnchorRejections` UND die Map von
    `BriefingHealth()` auf Abwesenheit dieser Strings prüfen.

## Was sich NICHT ändern darf

- **Die drei bestehenden `load()`-Aufrufer.** `weather_snapshot.py::load()`
  bleibt in Signatur und Rückgabewert unverändert. `trip_alert.py:509` ist die
  EINZIGE Stelle, deren umgebendes Verhalten sich durch diese Scheibe ändert
  (Teil A). `weather_extractor.py:84` und `weather_extractor.py:127`
  (`/heute`-/`/morgen`-Anzeigepfade) bleiben unverändert — sie zeigen weiterhin
  „was auch immer da ist", ohne neue Datumsprüfung (AC-6).
- **Das Dateilayout beider Anker-Arten.** Trip: `{trip_id}.json` (undatiert),
  `{trip_id}_{YYYY-MM-DD}.json` (datiert). Compare:
  `{preset_id}__{location_id}.json`. Keine neuen Dateien, keine neuen
  Verzeichnisse, keine Migration.
- **`_anchor_too_old`/`_MAX_ANCHOR_AGE` in `compare_alert.py`.** Bleiben
  unangetastet und laufen weiterhin VOR der neuen `target_date`-Weitergabe
  (B3) — Alter und Tagesbezug sind zwei unabhängige Fragen.
- **Altbestand ohne `target_date`** (sowohl Trip-undatierte Dateien als auch
  Compare-Anker) liefert `None`/löst das Altersnetz aus und verhält sich damit
  exakt wie heute — keine Datei muss vor dem Deploy migriert werden.
- **`write_anchor_and_reset_memory`/`reset_alert_memory`** (#1467 S2 AG5) —
  unverändert, kein Eingriff in den geteilten Baustein.

## Bug-Nachweis

AC-1 reproduziert den gemessenen Produktivfall vom 08.08.2026 unmittelbar aus
Nutzersicht: kein datierter Anker für heute, ein undatierter Rückfall mit
`target_date` von gestern (07.08.) — exakt die Konstellation, die am 08.08.
rund 16 Stunden lang zu 28 stillen Alarm-Läufen führte. Vor dem Fix läuft der
Test rot, weil `_get_cached_weather()` den Rückfall ungeprüft zurückgibt und
keine Warnung erscheint; nach dem Fix wird der Anker verworfen UND sichtbar
gemacht (AC-11 schließt die zweite Hälfte des Schadens — die Blindheit war
nicht nur der falsche Vergleich, sondern auch die fehlende Sichtbarkeit).

## Nicht in dieser Scheibe

Siehe Abschnitt gleichen Namens oben (vor „Implementation Details") — dort
stehen die vier ausgeschlossenen Punkte mit Begründung.

## Testplan

Alle Tests laufen in der **Kern-Schicht** (deterministisch, kein Netz, keine
Live-Postfächer) — kein AC dieser Scheibe braucht Staging oder echten Versand.

| AC | Schicht | Ansatz |
|---|---|---|
| AC-1 bis AC-6 | Kern | `WeatherSnapshotService`-Fixtures (echte JSON-Dateien in `tmp_path`/isolierter `get_data_dir()`), echter `TripAlertService`-/`WeatherExtractor`-Aufruf, `caplog` für Log-Assertions |
| AC-7 bis AC-10 | Kern | Muster `Szenario` aus `tests/tdd/test_compare_alert_day_window.py` (echter Sendepfad `send_one_compare_preset()`, echte `CompareLocationWeatherSource` mit Fake-Provider über die Provider-Registry, Spionage-Unterklasse für `fetch()`-Argumente) |
| AC-11, AC-13, AC-14 | Kern (Python) | JSONL-Datei nach dem Lauf direkt lesen; `caplog` für die reine Logzeile ohne Diagnose-Eintrag |
| AC-12, AC-16 | Kern (Go) | `analyzeAlertAnchorRejections()` direkt mit präparierten JSONL-Fixtures aufrufen, `go test` |
| AC-15 | Kern | simulierter Schreibfehler (z. B. unschreibbares Verzeichnis) am Diagnose-Pfad |

Kein Mock-Theater: alle Tests laufen über echte Dateien/echten Sendepfad/echte
Provider-Fakes (keine `Mock()`/`patch()`/`MagicMock`, die nur die eigene
Annahme zurückspiegeln), keine Dateiinhalt-String-Checks als
Verhaltensnachweis (AC-14 nutzt `caplog`, nicht `"reason" in text`).

## Bekannte, zu Recht rote Bestandstests

Diese drei Testdateien werden durch den neuen `target_date`-Parameter an
`CompareLocationWeatherSource.fetch()` zu Recht rot, bis ihre
Attrappen-Signaturen angepasst sind (kein fachlicher Regressionsbefund):

- `tests/tdd/test_compare_alert_day_window.py:397-400` — `SpionierendeQuelle.fetch()`
- `tests/tdd/test_compare_briefing_anchor_survives_dispatch_failure.py:96-100`
- `tests/tdd/test_compare_briefing_anchor_and_memory_reset.py:188-196`

Alle drei erwarten `fetch(self, point_id, lat, lon, start_hour=None,
end_hour=None)` ohne `target_date` — die Produktivseite übergibt das neue
Argument künftig als Keyword, was bei diesen Attrappen zu `TypeError`
führt. Behebung: `target_date=None` in der jeweiligen Signatur ergänzen und im
`super().fetch(...)`-Aufruf durchreichen (analog zum bestehenden
`start_hour`/`end_hour`-Muster).

Zusätzlich muss der Docstring von AC-5 in
`test_compare_alert_day_window.py:559-584` (Funktion
`test_ac5_check_um_22_uhr_bleibt_beim_fenster_des_laufenden_tages`) von
„Anker und Frisch-Abruf bleiben beim Fenster des laufenden Tages" auf „Anker
und Frisch-Abruf beschreiben denselben Tag — nämlich den, über den zuletzt
gebrieft wurde" umformuliert werden (E3, PO-Entscheidung). Der Assert selbst
bleibt unverändert grün: das Preset dieses Tests hat keinen aktivierten
Abend-Slot, der Anker trägt also weiterhin `target_date = heute`, und das
Verhalten „bleibt beim laufenden Tag" ist für diesen konkreten Fall weiterhin
korrekt — nur die Formulierung war zu eng.

## Known Limitations

- **Zwei Rest-Zeitfenster rund um die ORTSmitternacht (vorbestehend, nicht durch
  diese Scheibe entstanden).** Der Anker-Kalendertag entsteht aus `local_today`
  am Ort (`compare_location_weather_source.py:112`) — das ist der von F002
  geforderte Auflösungspunkt. Daraus bleibt:
  1. Überschreitet der Ort seine eigene lokale Mitternacht **zwischen**
     Fälligkeits-Sammlung und Anker-Schreiben, wandert `local_today` mit; der
     Versatz stimmt, der Bezugspunkt hat sich verschoben.
  2. `_write_compare_alert_snapshots` ruft `fetch()` **je Ort einzeln** auf,
     jeder Aufruf löst seinen eigenen Zeitpunkt auf. Fällt eine Ortsmitternacht
     zwischen zwei Orte desselben Ortsvergleichs, kann ein Anker-Satz auf zwei
     Kalendertage zerfallen.

  **Präzisierung (F005):** vorbestehend ist der **Mechanismus** — `fetch()` löste
  seinen Zeitpunkt immer selbst auf, und zwei Aufrufe konnten schon immer über
  eine Ortsmitternacht auseinanderfallen. Das **Fehlerbild** ist dagegen neu:
  vor dieser Scheibe gab es kein `target_date`-Feld, das dabei auseinanderlaufen
  konnte — die Anker trugen gar keinen Tagesbezug. Es ist also keine geerbte
  Altlast, sondern ein Randfall, der mit dem neuen Feld erstmals sichtbar wird.
  **Bewusst NICHT als lauter Fehlschlag umgesetzt:** eine
  Prüfung „Anker-Tag == Mail-Tag" würde für jeden Ort ab UTC+6 östlich
  **dauerhaft** feuern — dort weichen absoluter Mail-Tag und ortslokaler
  Anker-Tag per Konstruktion ab, genau wie es der F002-Test (Kamtschatka)
  verlangt. Ein solcher Wächter risse F002 wieder auf. Punkt 2 wäre sauber
  schließbar, indem `_write_compare_alert_snapshots` **einen** Zeitpunkt
  festhält und durchreicht; das erweitert die Signatur der geteilten
  Wetterquelle auf Lese- und Schreibseite und ist eine eigene Entscheidung —
  als Folge-Issue gebucht, nicht hier mitgemacht.


- **Ein Signal ohne bekannten externen Leser** (bis BetterStack/Monitoring
  explizit ergänzt wird): `alert_anchor_rejected_streak_since` landet am
  Status-Endpunkt, aber ob ein externer Monitor bereits darauf reagiert, ist
  außerhalb dieser Scheibe (R5 im Kontext-Dokument — Lehre aus #1628/#1629:
  ein Signal ohne Leser versandet).
- **Verschärfung kann heute (zufällig) korrekte Alarme abschalten** (R6): ein
  Anker, der bislang trotz falschem Tag zufällig einen richtigen Alarm
  auslöste, tut das nach dieser Scheibe nicht mehr — das ist beabsichtigt
  (der alte Zustand war kein verlässliches Verhalten, sondern Zufall), aber
  eine beobachtbare Verhaltensänderung.
- **#1007-Abweichung bleibt bestehen** (`trip_command_processor.py:294-303`,
  s. „Nicht in dieser Scheibe") — der On-Demand-Pfad kann den Trip-Anker
  weiterhin unbemerkt überschreiben.
- **60-Minuten-Schwelle ist auf den 15-Minuten-Alarm-Takt kalibriert**, nicht
  gemessen an einer realen Serie — analog zur 26-h-Schwelle aus #1629, die
  ebenfalls aus dem jeweiligen Lauftakt abgeleitet (nicht empirisch optimiert)
  wurde.
- **Compare-Teil ändert die gefetchten Rohdaten für Abend-Slot-Presets.** Der
  Δ-Anker eines Abend-Slot-Presets bezieht sich künftig auf das
  Tagesfenster von morgen statt von heute (zum Schreibzeitpunkt) — eine
  bewusste, im Kontext-Dokument (E3) begründete Verhaltensänderung, kein
  Nebeneffekt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue.
- **Rationale:** Diese Scheibe löst zwei bestehende Zusagen ein und
  respektiert eine bestehende Trennung:
  1. **ADR-0018** (Nicht-Kaschieren-Invariante) — ein Anker-Verwerfen ohne
     jedes Signal ist genau das Kaschieren, das ADR-0018 verbietet; Teil C
     wendet dasselbe Streak-/Lücken-Muster wie #1629 auf einen weiteren,
     bislang unerfassten Ausfallpfad an.
  2. **ADR-0021** (geteilte Bausteine Trip/Compare) — der Konflikt aus Risiko
     R1 des Kontext-Dokuments löst sich auf, OHNE einen geteilten Baustein zu
     schaffen: die Trip-Seite bekommt ein eigenes, schärferes Kriterium
     (Datum vor Alter), der Ortsvergleich behält seine bestehende, unveränderte
     `_anchor_too_old`-Politik (A2). Geteilt wird nur der Zahlenwert 26 h,
     nicht der Code — kein ADR-Nachtrag nötig.
  3. **ADR-0009** (kein Vergleichsanker ohne Briefing) — Teil B stellt die
     Tages-Treue zwischen dem Abend-Briefing-Inhalt und dem daraus
     geschriebenen Δ-Anker her, ohne ADR-0009 selbst zu ändern.
  4. **`fix_1584c` AC-5** wird fachlich neu gefasst (nicht gebrochen, E3):
     die Zusicherung „Anker und Frisch-Abruf bleiben immer am laufenden
     lokalen Tag" gilt weiterhin für Morgen-Slot-Presets (AC-9), wird für
     Abend-Slot-Presets aber korrekt als „...beschreiben denselben Tag —
     nämlich den, über den zuletzt gebrieft wurde" verstanden (AC-8).

## Changelog

- 2026-08-10: Initiale Spec. Scope aus `docs/context/fix-1661-anker-vom-falschen-tag.md`
  (PO-Entscheidungen E1/E2/E3, technischer Ansatz A1-A4/B1-B3/C1-C2) übernommen,
  ohne Abweichung. LoC-Budget 500 (bereits durch PO angehoben).
