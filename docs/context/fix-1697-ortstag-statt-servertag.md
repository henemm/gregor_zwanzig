# Context & Analysis: fix-1697-ortstag-statt-servertag

**Issue:** [#1697](https://github.com/henemm/gregor_zwanzig/issues/1697)
**Workflow:** `fix-1697-ortstag-statt-servertag` (Standard Track, Intake-Score 3)
**Erstellt:** 2026-08-10 · Basis-HEAD `dc100be9`
**Reihenfolge:** vor [#1667 S3](fix-1667-s3-tagesuebergreifende-segmente.md) (PO 2026-08-10)

## Request Summary

Der Alarm- und Briefing-Pfad bestimmt „welcher Tag der Tour ist jetzt" über `date.today()` —
das Datum der **Serveruhr** (`Etc/UTC`). Eine Etappe trägt aber ein **Ortsdatum**. Fallen
beide auseinander, wird die Etappe nicht gefunden und der Trip stillschweigend übersprungen.
Gemessen: Neuseeland verliert die ersten ~4 von 11 Stunden **jedes** Etappentags, Kalifornien
die letzten ~2 — bei ganz normaler Tagesetappe, ohne Nacht-Etappe.

## Type
**Bug.** Verstoß gegen eine bereits getroffene Grundsatzentscheidung (ADR-0044), nicht
gegen eine offene Frage.

## 🔴 Die Entwurfsfrage ist bereits entschieden — nicht neu aufmachen

`docs/adr/0044-kalendertage-folgen-der-ortszeit.md` (**Akzeptiert**, PO 2026-08-03) legt fest:

> **Kalendertage — „heute", „morgen" — bestimmen sich nach der Ortszeit der Tour.**
> Die Zone wird aus den Koordinaten des Wegpunkts aufgelöst, mit dreistufigem Rückfall:
> Etappe des Weltzeit-Tages → erste Etappe mit Wegpunkten → importierte UTC-Konstante.

Die dortige Restliste nennt vier Stellen in `trip_command_processor.py` als „bewusst
ausgegrenzt, nicht vergessen". **`trip_alert.py` und `trip_report_scheduler.py` stehen dort
nicht** — sie sind schlicht übersehen worden, und sie wiegen schwerer als die genannten
(Alarme statt Anzeige).

### Das Muster existiert bereits, erprobt und gehärtet

`docs/specs/modules/fix_1470_drilldown_ortszeit.md` (#1470, PO-freigegeben 2026-08-03) löst
exakt dieselbe Frage inklusive der **Henne-Ei-Falle**: Man braucht ein Datum, um die Zone zu
bestimmen, und die Zone, um das Datum zu bestimmen.

Auflösung in zwei Schritten (`trip_command_processor.py:783-824`):

```python
def _trip_tz(self, trip):                      # :794 — Rückfall 2
    stage = next((s for s in trip.stages if s.waypoints), None)
    if stage is None:
        return UTC                             # Rückfall 3
    wp = stage.waypoints[0]
    return tz_for_coords(wp.lat, wp.lon)

def _display_tz(self, trip, day_date):         # :809 — Rückfall 1
    stage = trip.get_stage_for_date(day_date)
    if stage is None or not stage.waypoints:
        return self._trip_tz(trip)
    wp = stage.waypoints[0]
    return tz_for_coords(wp.lat, wp.lon)

# :783 — _anchor_tz: Zone der Etappe des WELTZEIT-Tages, weil dieser Tag
# höchstens einen Tag daneben liegt und damit praktisch immer die richtige
# Etappe findet, OHNE selbst schon von der Zone abzuhängen.
```

Der Adversary hat diese Fassung erzwungen: die erste ankerte an der **ersten Etappe der
Tour** und lag bei einer Tour Neuseeland → Korsika **zehn Stunden** daneben.

**Die drei Methoden sind heute privat auf `TripCommandProcessor`** — für #1697 müssen sie
in einen geteilten Baustein wandern. Eine benannte Funktion „heutiges Datum am Ort X"
existiert im ganzen Repo **nicht**; es gibt nur Inline-Ableitungen
(`compare_location_weather_source.py:116`, `trip_segments.py:275`).

### Mehr-Zonen-Touren: bewusst kein Thema (PO 2026-08-10)

ADR-0044 stuft den Restfehler bereits ab: „Wechselt der Wanderer **an genau diesem Tag** die
Zone, … Der Fehler ist dann die Differenz zweier benachbarter Etappen — in aller Regel null."
Der PO hat das am 2026-08-10 bestätigt: nicht bauen, als bekannte Grenze dokumentieren.

## 🔴 Der Fund, der den Zuschnitt bestimmt: Schreiber und Leser hängen aneinander

`date.today()` ist nicht nur der Etappen-Anker, sondern auch der **Schlüssel des
Wetter-Schnappschusses**:

| Rolle | Stelle | Datum |
|---|---|---|
| **schreibt** | `trip_report_scheduler.py:1109` `save_dated(trip.id, target_date, …)` | `_get_target_date()` → `date.today()` (morgens) / `+1` (abends), `:653-667` |
| **liest** | `trip_alert.py:570` `load_dated(trip.id, today)` | `date.today()` |
| **liest** | `trip_alert.py:971` `load_dated(trip.id, today)` | `date.today()` |
| **prüft** | `trip_alert.py:592` `anchor_date == today` | `date.today()` — **neu seit #1661** (`edef0523`, parallele Sitzung) |

Heute ist die Kette **in sich konsistent falsch**: Schreiber und Leser irren gleich, deshalb
passt es zusammen. Wird **nur** die Etappenauswahl (`trip_alert.py:881`) auf Ortszeit
umgestellt, entsteht ein **neuer** Bruch — die gewählte Etappe stammt vom Ortstag, der
Schnappschuss vom Serverdatum. Folgen: `_briefing_precip_for_onset` (`:838-865`) matcht auf
`segment_id` und vergleicht dann gegen die Daten einer **anderen** Etappe; die seit #1661
scharfe Frischeprüfung `anchor_date == today` könnte einen gültigen Anker verwerfen und
`_report_missing_anchor` auslösen.

**Daraus folgt die Zuschnitt-Regel: „welcher Tag der Tour ist jetzt" muss einmal aufgelöst
und in der ganzen Kette gleich verwendet werden.** Eine Einzelzeile zu ändern ist hier nicht
der kleine, sondern der gefährliche Schnitt.

## Related Files — 17 Stellen, nach Wirkung sortiert

### Kette A — wählt die Etappe für Alarm/Briefing (der Kern)

| Datei:Zeile | Funktion | Wirkung bei falschem Tag |
|---|---|---|
| `src/services/trip_alert.py:881` | Radar-/NowCast-Schleife | **kein Alarm** (`continue`) |
| `src/services/trip_alert.py:569` | `_get_cached_weather` | Anker nicht gefunden / verworfen |
| `src/services/trip_alert.py:971` | Briefing-Vergleich im Radar-Alarm | Vergleich gegen falsche Etappe |
| `src/services/trip_report_scheduler.py:663` | `_get_target_date` | **Briefing für den falschen Tag** |
| `src/services/trip_report_scheduler.py:617` | `_get_active_trips` | Trip gilt als nicht aktiv ⇒ **kein Briefing** |
| `src/services/trip_report_scheduler.py:857` | `_send_trip_report` | Segmente der falschen Etappe |
| `src/services/trip_report_scheduler.py:1109` | `save_dated` | Schnappschuss unter falschem Schlüssel |
| `src/services/trip_alert.py:386` | `check_all_trips` | Trip-Filter `end_date < today` — Randtag |

### Kette B — Anzeige, Vorschau, Werkzeuge (eigener Schnitt)

`trip_command_processor.py:1276` (`/jetzt`), `:1125` (`/status`), `:498` (`_handle_query`,
**löst Versand aus**), `:428` (`command_date`) — die vier von ADR-0044 bereits benannten ·
`inbound_telegram_reader.py:358` · `preview_service.py:94` · `api/routers/debug.py:61` ·
`trip_report_scheduler.py:719,883,1434,1749,2142` · `tools/weather_validation.py:94,226`

### Bewusst NICHT betroffen (feste Zone ist dort Absicht, nicht Fehler)

`forecast_budget._today_utc:124` und `meteoalarm_budget._today_utc:170` (Kontingent-
Tageswechsel bewusst UTC) · `alert_daily_limit.py:32` und `deviation_alert_engine.py:112`
(Tageszähler/Ruhezeit fest `Europe/Vienna`) · `scheduler_dispatch_service.py:164` (Slot-Stunde)

## Bestehende Wächter

`tests/test_output_timezone_guard.py` (#1402) ist eine **AST-Ratsche** mit schrumpfender
`KNOWN_VIOLATIONS`-Liste: sie flaggt rohes `.astimezone()`, stille Zonen-Rückfälle und
verlangt, dass Produktiv-Aufrufer `tz` **explizit** übergeben
(`test_production_callsites_pass_tz_explicitly`). Neuer Code muss deshalb `local_dt(dt, UTC)`
aus `src/utils/timezone.py` benutzen, **nicht** `dt.astimezone(UTC)`.

Elf weitere Zeitzonen-Wächter (`test_drilldown_day_window_local_date.py`,
`test_compare_local_time_basis.py`, `test_bug_397_output_localtime.py`,
`test_alert_quiet_hours_localtime.py`, `test_alert_event_time_uses_local_timezone.py` u.a.).
**Keiner** von ihnen steht in `.github/ci_tdd_excludes.txt` — anders als bei #1667 S3 laufen
hier alle einschlägigen Wächter in CI.

**Nicht bewacht:** kein Test prüft, dass die **Etappenauswahl** dem Ortstag folgt. Genau
diese Lücke hat den Fehler getragen.

## Technischer Ansatz

1. **Geteilter Baustein** — die drei privaten Methoden aus `TripCommandProcessor` in ein
   gemeinsames Modul heben (Kandidat: `src/utils/timezone.py`, wo `tz_for_coords`/`local_dt`
   schon liegen, oder ein neues `src/services/trip_day.py`) und um die eigentliche
   Zielfunktion ergänzen:
   `trip_local_today(trip, now_utc) -> date` — zweistufig nach dem #1470-Muster.
   `TripCommandProcessor` ruft anschließend den geteilten Baustein, statt eine vierte Kopie
   entstehen zu lassen.
2. **Kette A geschlossen umstellen**, damit Schreiber und Leser gekoppelt bleiben.
3. **Kette B unverändert lassen** und als Folge-Issue buchen — inklusive der vier Stellen,
   die ADR-0044 schon kennt.

**Sommerzeit ist Pflicht, nicht Kür.** ADR-0044 schreibt vor: „**Immer beide Wechseltage
testen**", und warnt vor der Rechenfalle — gleiche `tzinfo` ⇒ Python rechnet auf Wanduhr-
Werten und liefert an jedem Tag 24,0 Stunden. Für eine reine *Datums*bestimmung ist das
weniger scharf als für Fensterlängen, muss aber belegt werden statt angenommen.

## Scope Assessment
- Dateien: 1 CREATE (Baustein) + 3–4 MODIFY + 1 CREATE (Tests)
- LoC: ~50 Baustein, ~30 Aufrufstellen, ~120–150 Tests (drei Zonen × Kippkanten + zwei
  Sommerzeit-Wechseltage) ⇒ **~200–230**, Limit 250 — machbar, aber ohne Puffer
- Risiko: **MEDIUM-HIGH** — die Änderung betrifft *jeden* Trip, auch jeden europäischen (s. u.).

## 🔴 Nachgemessen und korrigiert: „in Europa ändert sich nichts" ist FALSCH

Diese Analyse hat zunächst angenommen, der Fix sei für Mitteleuropa bitgleich und nur für
ferne Zonen wirksam. **Nachgemessen stimmt das nicht:**

| Zone | Ortsdatum ≠ Serverdatum | Fenster |
|---|---|---|
| Europe/Paris, Europe/Vienna | **2,00 h/Tag** | 22:00–00:00 UTC (= 00:00–02:00 Ortszeit) |
| America/Los_Angeles | 7,00 h/Tag | 00:00–07:00 UTC |
| Pacific/Auckland | 12,00 h/Tag | 12:00–00:00 UTC |

**Auch ein Korsika-Trip ist jede Nacht zwei Stunden lang betroffen.** Was in diesem Fenster
passiert, ändert sich substanziell:

| | heute | nach dem Fix |
|---|---|---|
| Serverdatum 22:30 UTC | Tag D | Tag D |
| Ortsdatum (00:30 Ortszeit) | — | **Tag D+1** |
| gewählte Etappe | D — deren Segmente endeten 19:00 Ortszeit ⇒ **alle vorbei** ⇒ `continue` | **D+1** — alle Segmente in der Zukunft ⇒ `now < segments[0].start_time` ⇒ `active = segments[0]` |
| Radar-Abfrage | **keine** | **eine, am Startpunkt der morgigen Etappe** |

Fachlich ist die neue Auswahl **richtig** — um 00:30 Ortszeit ist lokal tatsächlich der
Folgetag, und die Vorschau-Regel („aktives *oder nächstes* Segment", #822) ist Absicht.

**Aber sie deckt eine vorbestehende Schwäche auf:** `check_radar_alerts` hat **keinen**
Horizont-Guard — `NOWCAST_HORIZON_MIN` kommt in `trip_alert.py` nicht vor. Die
Schwesterfunktion `_build_starkregen_hint` hat ihn (`trip_report_scheduler.py:1352-1357`).
Nach dem Fix würde also jede Nacht ein Radar-**Nowcast** (Horizont ~60 min) für ein Segment
abgerufen, das erst in 7,5 Stunden beginnt — fachlich sinnlos und reine Kontingent-Last.

Gemildert, aber nicht beseitigt: `check_nowcast_gate` läuft **vor** `get_nowcast`
(`trip_alert.py` — Gate, dann Abruf), die Ruhezeit unterdrückt also bei konfiguriertem
`alert_quiet_from/to` auch den Abruf. Ruhezeiten sind aber **optional pro Trip**.

**Konsequenz für die Spec:** Der fehlende Horizont-Guard gehört als eigenes AC mit in diese
Scheibe. Ihn wegzulassen hieße, einen Fix auszuliefern, der bei jedem europäischen Trip
nächtliche Fehlabrufe erzeugt — und das wäre keine Nebenwirkung, sondern ein neuer Fehler.
Die beiden Kopien sollen ohnehin dieselbe Regel tragen.

## Nachweis-Strategie
- **Der wichtigste Test ist das Verhalten im 22:00–00:00-UTC-Fenster eines Korsika-Trips**,
  nicht Neuseeland. Genau dort ändert sich etwas für den Bestand, und genau dort hätte eine
  unbelegte „bitgleich"-Behauptung den Fehler durchgelassen.
- **Außerhalb dieses Fensters** muss der gewählte Tag für einen Korsika-Trip über alle
  24 Stunden unverändert sein.
- **Wirkung** über die **Koordinaten** des abgefragten Segments, nicht über einen
  Alarm-Zähler — ein Zähler hätte die Falsch-Ortung nie bemerkt.
- **Uhr:** `freeze_time` (seit #1667 S1 Dev-Dependency); der Alarm-Pfad liest die Wanduhr an
  mehreren Stellen, eine einzelne DI-Naht wäre eine halbe Uhr.
- **Mutations-Gegenprobe:** Baustein auf `date.today()` zurückdrehen ⇒ der Neuseeland-Test
  muss rot werden.

## Open Questions
- [ ] **Gehört `_get_target_date` (Briefing) in dieselbe Scheibe wie der Alarm-Pfad?**
      Dafür: Schreiber/Leser-Kopplung (s. o.) — getrennt entsteht ein neuer Bruch.
      Dagegen: LoC-Limit und ein zweiter Wirkbereich (Briefing-Versand) in einer
      Adversary-Runde. **Mit dem Horizont-Guard als Pflicht-AC ist das Budget knapp.**
