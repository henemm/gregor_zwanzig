# Context: fix-1818-timeline-zweitagesanker

Issue: [#1818](https://github.com/henemm/gregor_zwanzig/issues/1818) · Label `bug`, `priority:high`,
`area:output` · Milestone **Tour KHW 2026-08** · Basis `cba7ffa3`

## Request Summary

Die Telegram-Abfragen `timeline_heute` / `timeline_morgen` / `glance` antworten fuer einen der
beiden Tage **„Keine Etappe geplant"**, obwohl die Etappe existiert. Die Antwort behauptet etwas
ueber die **Tourplanung**, weiss aber nur etwas ueber den **Datenbestand**: der undatierte
Wetter-Anker traegt strukturell nur EINEN Tag.

## Wirkkette (belegt)

| Schritt | Datei:Zeile | Was passiert |
|---|---|---|
| 1 | `src/services/trip_report_scheduler.py:927-950` (`_get_target_date`) | `"morning"` → Ortstag, `"evening"` → Ortstag+1. **Genau ein** `target_date` je Lauf. |
| 2 | `src/services/trip_report_scheduler.py:1505-1512` (`_write_briefing_anchor`) | schreibt `save(trip.id, segment_weather, target_date)` → **ueberschreibt** `{trip_id}.json` komplett; zusaetzlich `save_dated(...)` → `{trip_id}_{YYYY-MM-DD}.json`. |
| 3 | `src/services/weather_snapshot.py:96-107` (`save`) | `target_date` existiert **nur einmal auf oberster Ebene**; kein Datum je Segment. |
| 4 | `src/services/weather_extractor.py:80-109` (`timeline`) | gibt **alle** Segmente der Datei zurueck, filtert **nicht** nach Tag; `target_date` wird nur durchgereicht. |
| 5 | `src/services/trip_command_processor.py:837-877` (`_aggregate_day`), `:969-1007` (`_fmt_timeline`) | Tagestrennung passiert **erst hier** (`local_dt(p.arrival_time, tz).date() == target_date`). Kein Treffer → `"{label} ({datum}): Keine Etappe geplant"`. |

**Folge:** Nach dem Morgen-Briefing traegt der Anker heute → `timeline_morgen` faellt aus.
Nach dem Abend-Briefing traegt er morgen → `timeline_heute` faellt aus. Die betroffene Seite
wechselt im Tagesrhythmus.

## Zwei Sperren, die einen naiven Fix wirkungslos machen

**Sperre A — der Nachlade-Pfad ist doppelt verriegelt.**
`_fetch_and_save_snapshot` (`trip_command_processor.py:278-316`) laeuft nur, wenn
`not timeline.available` (`:541`). Selbst wenn man diese Bedingung auf „kein Punkt fuer den
angefragten Tag" erweitert, bricht der Helper **intern erneut ab**: sein eigener Cache-Check
(`:289-296`) kehrt bei `raw["target_date"] == today.isoformat()` sofort zurueck — und genau das
ist der Normalfall nach einem Morgen-Briefing. Ein Fix nur an `:541` waere strukturell
wirkungslos.

**Sperre B — Nachladen wuerde die Alarm-Vergleichsbasis zerstoeren.**
`_fetch_and_save_snapshot` schreibt `briefing_backed=False` (`:312-314`). Heute ist das
harmlos, weil er nur laeuft, wenn gar kein Anker existiert. Bei einem Fix wuerde er einen
**vorhandenen briefing-backed Anker ueberschreiben** — und `TripAlertService._get_cached_weather`
(`src/services/trip_alert.py:738-742`) verwirft eine nicht-briefing-gestuetzte Basis
(`reason="not_briefing_backed"`, ADR-0009 / #1699). Ein Button-Druck des Wanderers wuerde damit
den Abweichungs-Alarm blind machen.

## Kostenloser Teil-Rueckfall: die datierten Snapshots

`_write_briefing_anchor` legt **zusaetzlich** `{trip_id}_{YYYY-MM-DD}.json` ab
(`save_dated`, `weather_snapshot.py:115-141`, Retention 7 Tage via `_prune_dated_snapshots:182`).
Daraus folgt eine Asymmetrie, die den Loesungszuschnitt bestimmt:

| Zeitpunkt | Undatierter Anker traegt | Fehlender Tag | Liegt er datiert vor? |
|---|---|---|---|
| Nach Morgen-Briefing | heute | **morgen** | **Nein** — `{trip}_{morgen}.json` entsteht erst im heutigen Abend-Briefing |
| Nach Abend-Briefing | morgen | **heute** | **Ja** — `{trip}_{heute}.json` stammt aus dem heutigen Morgen-Briefing |

Die Abend-Haelfte des Bugs ist also **ohne einen einzigen API-Abruf** behebbar; die
Vormittags-Haelfte nicht.

## Kontingent (Issue #1329) — schliesst einen Weg aus

Open-Meteo Free-Tier: **10.000 Anfragen/Tag**, chronisch ausgeschoepft
(`docs/specs/modules/fix_1329_forecast_cache_budget.md:19-22`; Prod-Log 2026-07-20: HTTP 429
durchgehend 00–14 Uhr). `_fetch_weather` (`trip_report_scheduler.py:1935-1977`) kostet
**1 Call je Segment**. Der Weg „Anker traegt immer beide Tage" wuerde den Verbrauch **je
Briefing verdoppeln** — bei einem Kontingent, das bereits 429er produziert. Dieser Weg
scheidet damit aus Betriebsgruenden aus, nicht aus Geschmacksgruenden.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/trip_command_processor.py` | Abfrage-Dispatch `:505-560`, Nachlade-Helper `:278-316`, Formatierer `:837-1030` — **Hauptaenderungsort** |
| `src/services/weather_extractor.py` | `timeline()` `:80-109` — liefert ungefilterte Punkte |
| `src/services/weather_snapshot.py` | `save` `:77-113`, `save_dated`/`load_dated` `:115-179`, `load_briefing_backed` `:347-370` |
| `src/services/trip_report_scheduler.py` | `_get_target_date` `:927-950`, `_write_briefing_anchor` `:1505-1512` — nur lesend relevant |
| `src/services/trip_alert.py` | `_get_cached_weather` `:629-750` — **Kollisionsflaeche**, kein Tagesfilter auf der undatierten Basis |

## Existing Patterns

- **Prioritaetskette statt Einzelquelle:** `trip_alert.py:629-750` (#1916) loest Wetterdaten
  ueber gestufte Quellen auf (Briefing-Anker → rollierender Alarm-Anker → undatierter Rueckfall)
  mit benanntem `reason` je Ablehnung. Dasselbe Muster passt auf die Timeline-Aufloesung.
- **Herkunft mitfuehren statt raten:** `briefing_backed` (#1699) haelt fest, ob Daten als
  Vergleichsbasis taugen. Neue Schreibpfade muessen die Herkunft bewusst setzen.
- **Read-Modify-Write statt Replace** (CLAUDE.md, BUG-DATALOSS-GR221): `save()` ist heute ein
  reiner Replace — jede Erweiterung des Ankers muss das beruecksichtigen.
- **Ehrliche Fehlanzeige statt Falschaussage:** `_fmt_gewitter` `:938-941` trennt bereits
  „kein Snapshot verfuegbar" von „keine Etappe geplant" — das Vorbild fehlt nur der Timeline.

## Dependencies

- **Upstream:** `WeatherSnapshotService` (Persistenz), `TripReportSchedulerService._fetch_weather`
  (Provider-Abruf), `trip_local_now`/`display_tz` (#1795, ADR-0044 Ortszeit-Aufloesung).
- **Downstream:** Telegram-Inbound-Antworten (`timeline_heute`, `timeline_morgen`, `glance`,
  `heute_gewitter`); indirekt der Alarm-Pfad ueber den geteilten undatierten Anker.

## Existing Specs & ADRs

- `docs/specs/modules/fix_1699_anker_ohne_briefing.md` — `briefing_backed`, ADR-0009
- `docs/specs/modules/fix_1329_forecast_cache_budget.md` — Kontingent
- `docs/context/fix-1795-timeline-ortszeit.md` — Fundstelle dieses Befunds, Abgrenzung
- ADR-0044 (Ortszeit), ADR-0056 (rollierender Alarm-Anker), ADR-0009 (Vergleichsbasis)

## Risks & Considerations

1. **Alarm-Vergleichsbasis (hoch).** Jede Aenderung am undatierten Anker `{trip_id}.json`
   trifft `trip_alert.py:711-750` mit. Dort gibt es — anders als in `_aggregate_day` — **keinen
   Tagesfilter**: ein zweitaegiger Anker wuerde morgige Segmente still in den Δ-Vergleich
   einspeisen. Nachweis-Pflicht in der Spec.
2. **Radar-Unterdrueckung (mittel).** `trip_alert.py:680` (`load_dated(trip.id, today)`) und
   `:1324` lesen die datierten Snapshots. Wuerde ein Abfrage-Pfad dort schreiben, veraenderte er
   die eingefrorene Briefing-Referenz (#818/#1667, AC-11) — genau das, was `save_alarm_anchor`
   (`weather_snapshot.py:225-240`) bewusst vermeidet.
3. **Kontingent (mittel).** Jeder Nachlade-Weg kostet Calls. Bei 429 muss die Antwort ehrlich
   ausfallen statt in „Keine Etappe geplant" zurueckzufallen — sonst ist der Bug unter Last
   unveraendert sichtbar.
4. **Testfixturen verdecken den Bug (hoch, nachweisrelevant).**
   `tests/tdd/test_issue_651_telegram_query_glance.py:108-119` und
   `tests/tdd/test_timeline_folgt_der_ortszeit.py:95-101` schreiben ihren Anker **kuenstlich mit
   beiden Tagen in EINEM `save()`-Aufruf**. Der Produktionspfad — zwei getrennte, einander
   ueberschreibende Laeufe — kommt in **keinem** Test vor. Ein RED-Test muss den Anker daher
   ueber **zwei aufeinanderfolgende `_write_briefing_anchor`-artige Schreibvorgaenge** aufbauen,
   sonst ist er trivial gruen.
5. **Nur ein `target_date`-Feld.** Die Ankerstruktur kann zwei Tage im `segments`-Array tragen,
   aber nicht zwei Zieltage benennen. Jeder Leser, der `load_target_date()` als Torwaechter
   nutzt, bekaeme eine halbe Wahrheit.
