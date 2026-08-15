# Context: fix-1726-ruhezeit-ortszone

Issue **#1726** (S4 des Epics **#1722**), Label `bug`, `area:trips`, `area:compare`.
Erhoben 2026-08-12 gegen `origin/main` `bc7dc418` durch drei parallele Kartierungs-Agenten.
Alle Angaben sind am Code gemessen; wo nicht, steht es ausdrücklich dabei.

## Request Summary

Drei Entscheidungen laufen heute auf der Wiener Uhr, obwohl sie den Nutzer an seinem Ort
betreffen: das **Ruhezeit-Fenster**, der **Reset des Alarm-Tageszählers** und die
**Fälligkeit von Ortsvergleichs-Slots**. Sie sollen auf die Ortszone umgestellt werden.
Beide `VIENNA`-Konstanten entfallen.

## Die drei Fundstellen

| Was | Fundstelle | heutige Uhr |
|---|---|---|
| Ruhezeit-Fenster | `src/services/deviation_alert_engine.py:31` (`VIENNA`), wirksam `:112` | `Europe/Vienna` |
| Alarm-Tageszähler-Reset | `src/services/alert_daily_limit.py:23` (`VIENNA`), wirksam `:32` | `Europe/Vienna` |
| Ortsvergleichs-Slot-Fälligkeit | `src/services/dispatch_orchestrator.py:128` (`NOCH_NICHT_ORTSZEIT_SIEHE_1726`), wirksam `:141` | `Europe/Vienna` |

Das Issue nennt für die dritte Stelle noch `scheduler_dispatch_service.py:164`; der Code ist
seit #1724 nach `dispatch_orchestrator.py` umgezogen. Der Aufrufer dort ist
`run_compare_presets_daily()` (`scheduler_dispatch_service.py:136-183`), der `now_utc` als
reinen Zeitpunkt liefert — die Umkehrung aus ADR-0051 ist auf der Aufruferseite also bereits
vollzogen, nur die Strategie rechnet noch in Wien.

## Related Files

### Ruhezeit — sieben Aufrufstellen, alle über einen geteilten Baustein

`DeviationAlertEngine.is_quiet_hours(now, quiet_from, quiet_to, context_label="")`
(`deviation_alert_engine.py:84-143`) ist statisch und location-generisch. Die Zone ist **nicht**
parametrisiert.

| # | Aufrufstelle | Dienst | Objekt im Scope | Zone beschaffbar? |
|---|---|---|---|---|
| 1 | `compare_official_alert.py:119` | Amtliche Warnung, Vergleich | `preset`, `all_locations`, `location_ids` | ja, über die Orte |
| 2 | `trip_alert.py:229` | Wetter-Abweichung, Trip | `trip` | ja, `trip_day.py` |
| 3 | `trip_alert.py:688` | Adapter `_is_quiet_hours(trip, now)` | `trip` | ja |
| 4 | `trip_alert.py:1443` | Amtliche Warnung, Trip | `trip` | ja |
| 5 | `alert_gate.py:93` | Nowcast-Schranke, **geteilt Trip+Vergleich** | nur Schlüsselwort-Parameter, **kein Objekt** | nein — Zone muss durchgereicht werden |
| 6 | `compare_alert.py:176` | Wetter-Abweichung, Vergleich | `preset`, `all_locations`, `config` | ja, über die Orte |
| 7 | `deviation_alert_engine.py:286` | `evaluate()`, Engine-Kern | nur `config: AlertEvaluationConfig` | nein — Zone müsste ins Konfig-Objekt |

Die beiden Aufrufer von #5 haben ihr Objekt: `trip_alert.py:963` (`trip`) und
`compare_radar_alert.py:131` (`preset`, `all_locations`).

`AlertEvaluationConfig` (`point_weather.py:54-71`) ist ein reines Datenobjekt, das laut eigenem
Docstring genau die `trip.*`-Werte bündelt und „ein künftiger Compare-Adapter … aus einem
`ComparePreset` bauen" würde. Ein Zonen-Feld dort ist der Weg, der die Trip/Compare-Teilung
wahrt.

### Tageszähler — ein Datensatz je Nutzer, zehn Aufrufstellen

`alert_daily_limit.py`: `load`/`is_allowed`/`increment`, alle mit `(user_id, now, …)`. Datei
`<get_data_dir(user_id)>/alert_daily_count.json`, Schema exakt:

```json
{"date": "2026-07-07", "count": 2}
```

**Kein Diskriminator** — keine Trip-, Preset- oder Zonen-Kennung. Trip- und Vergleichs-Alarme
teilen denselben Datensatz; das ist kein Nebeneffekt, sondern zugesichert (AC-5 in
`tests/tdd/test_issue_1070_daily_alert_limit.py`). Schreibweise ist bereits
Read-Modify-Write über Tempfile + `os.replace()` (`:94-99`).

Aufrufstellen — **elf**: `alert_gate.py:105/:123`, `compare_official_alert.py:138/:182`,
`trip_alert.py:240/:344/:1449/:1490`, `compare_alert.py:151/:293`, dazu die reine Lesestelle
`trip_report_scheduler.py:1570`.

⚠️ Diese Zeile stand hier zunächst mit **zehn** Stellen — `compare_alert.py:151`
(`is_allowed(..., reason="forecast_change")`, im selben Preset-Lauf wie `:293`) ging beim
Übertragen aus dem Kartierungs-Bericht verloren, obwohl der Bericht sie hatte. Gefunden hat es
der spec-writer beim Nachmessen. Das ist exakt die Fehlerklasse, die dieses Dokument unter
Risiko 9 beschreibt und die #1725 zweimal getroffen hat: **eine unvollständige Aufzählung liest
sich wie eine vollständige.** Wer hier eine Aufrufstellen-Liste verwendet, zählt sie am Code
nach, statt sie zu glauben.

### Ortsvergleichs-Slots

`CompareDispatchStrategy.collect_due()` (`dispatch_orchestrator.py:130-146`) →
`presets_due_for_hour(presets, hour, today)` (`compare_slot_scheduler.py:102-156`) prüft
**Stundengleichheit** (`:152`). Slots sind zwei Preset-Felder (`morning_time`,
`evening_time`); beide können gleichzeitig fällig sein.

## Existing Patterns

**Das Vorbild steht fertig im Trip-Pfad.** `TripReportSchedulerService._collect_due_trips`
(`trip_report_scheduler.py:376-438`):

```python
vor_ort = trip_local_now(trip, now_utc)                              # Zone je Trip
if not stunde <= vor_ort.hour < stunde + NACHHOL_FENSTER_STUNDEN:    # Fenster = 3 (:91)
    continue
if store.is_recorded(trip.id, report_type, vor_ort.date(), zone=vor_ort.tzinfo):
    continue                                                          # Idempotenz
```

**Zonen-Auflösung ist vorhanden, es ist nichts zu erfinden:**

| Werkzeug | Zweck | Rückfall |
|---|---|---|
| `utils/timezone.resolve_location_tz(location)` | der **einzige** erlaubte Auflöser für Orte (PO-Entscheidung E3, #1378) | `SavedLocation.timezone` → `tz_for_coords(lat, lon)` → `None` |
| `services/trip_day.trip_local_now(trip, now_utc)` | Ortstag **und** Ortsstunde eines Trips aus **einer** Auflösung | UTC-Konstante bei Trips ohne Wegpunkte |
| `utils/timezone.local_dt(dt, tz)` | reine Umrechnung; `.astimezone()` ist vom Wächter verboten | — |

**Präzedenzfall für den Mehrzonen-Fall — bereits PO-entschieden:** Die Compare-Mail nimmt für
ihre Kopfzeile die Zone des **erstgenannten Orts der konfigurierten Reihenfolge**:

```python
# compare_html.py:1535-1538 — Issue #1378 (AC-4)
# Kopfzeilen-Zeitbasis = Ortszeit des ERSTGENANNTEN Ortes der konfigurierten
# Reihenfolge (`location_render_order`, #1359) -- nicht alphabetisch, nicht Serverzeit.
header_tz = location_tz(locations[0].location) if locations else UTC
```

Klartext-Pendant `comparison.py:216`. Die Ortsliste `LocationIDs` ist geordnet und stabil
(`order_locations_by_ids`, #1359). Individuelle Ortsblöcke bleiben in ihrer **eigenen** Zone —
nur die preset-weite Angabe folgt dem ersten Ort. ⚠️ Der Kommentar bei `comparison.py:201-202`
behauptet noch alphabetische Sortierung; das ist seit #1359 falsch — der Code gilt, nicht der
Kommentar.

## Dependencies

- **Upstream:** `utils/timezone`, `services/trip_day`, `services/user_tier.daily_alert_limit`,
  `app.loader.get_data_dir`, Go-Cron `internal/scheduler/scheduler.go:143` (stündlich)
- **Downstream:** alle vier proaktiven Alarmwege (Trip-Abweichung, Trip-amtlich, Vergleich-
  Abweichung, Vergleich-amtlich), beide Nowcast-Wege über `alert_gate`, der Starkregen-Hinweis
  im Briefing, der Ortsvergleichs-Versand

## Existing Specs

| Spec | Inhalt |
|---|---|
| `docs/adr/0051-drei-zeitbegriffe-zone-an-den-daten.md` | **Status „Vorgeschlagen".** Regel 2: „Die Zone gehört an die Daten, nicht an den Server." Stundengleichheit als Fälligkeitsprüfung ist unzulässig. |
| `docs/adr/0044-kalendertage-folgen-der-ortszeit.md` | Akzeptiert. Listet `alert_daily_limit` und `deviation_alert_engine` heute noch als **„bewusst NICHT betroffen"** — muss fortgeschrieben werden. Verwirft ausdrücklich eine Nutzer-Zeitzonen-Einstellung. |
| `docs/specs/modules/fix_1725_faelligkeit_und_idempotenz.md` | Das Vorbild: Fenster + `BriefingSlotStore`. |
| `docs/specs/modules/fix_1724_faelligkeit_in_der_ortszone.md` | Vorstufe: Fälligkeit je Trip in seiner Zone. |
| `docs/specs/modules/issue_1378_compare_zeitbasis.md` | Liefert den „erster Ort"-Präzedenzfall und PO-Entscheidung E3. |
| `docs/specs/modules/alert_daily_limit.md` | Schreibt den Vienna-Reset heute fest. |

## Risks & Considerations

1. **Der nutzerweite Zähler hat keine Ortszone.** ADR-0051 Regel 2 zeigt auf „die Zone des
   Gegenstands, über den geredet wird" — der Gegenstand ist hier der Nutzer, und eine
   Nutzer-Zone ist von ADR-0044 ausdrücklich verworfen. Würde jede Aufrufstelle ihre eigene
   Zone mitbringen, schriebe derselbe Lauf den `date`-Schlüssel zwischen zwei Kalendertagen
   hin und her; bei jedem Wechsel setzt `increment()` auf 1 zurück und **das Limit griffe
   effektiv nie** — es bremst kostenpflichtige Premium-SMS. Produktentscheidung nötig.

2. **Deploy mitten am Tag ändert die Bedeutung von `date` still.** Steht der Zähler auf dem
   Wiener Datum und liest der neue Code ein abweichendes Ortsdatum, greift
   `data.get("date") == today` nicht → Reset auf 0 → **Kontingent-Leck** für den Rest des Tages.
   Braucht dieselbe Rückwärts-Ableitung, die #1725 für den Versand-Vermerk gebaut hat.

3. **Der Ortsvergleich hat keinerlei Idempotenz-Mechanik** — gemessen: `letzter_versand` ist ein
   reines Anzeigefeld, nirgends als Sperre gelesen. Schutz vor Doppelversand ist heute allein die
   exakte Stundengleichheit. Wird nur die Zone getauscht, bleibt die Umstellungstag-Lücke stehen
   (29.03. Slot entfällt, 25.10. Slot doppelt). Wird zusätzlich auf ein Fenster umgestellt,
   **muss** das Compare-Pendant zu `BriefingSlotStore` mitkommen — sonst stündlicher
   Serienversand.

4. **Der Go-Cron tickt selbst in Wiener Zeit** (`internal/config/config.go:20`,
   `SchedulerTimezone` default `Europe/Vienna`) und fällt an Umstellungstagen aus. Das ist
   S5/#1727, begrenzt aber, was #1726 allein erreichen kann.

5. **Vier Einträge der Wächter-Ausnahmeliste gehören zu dieser Scheibe** und müssen mit dem Fix
   verschwinden — `test_known_violations_only_shrink()` (`test_output_timezone_guard.py:694`)
   erzwingt es: `:622`, `:623` (Muster B) und `:630`, `:636` (gekoppelte `raw_astimezone`).

6. **Die Compare-Konstante ist unbewacht.** `NOCH_NICHT_ORTSZEIT_SIEHE_1726` steht **nicht** in
   der Liste — der AST-Scanner sieht ein String-Literal in einer Klassenvariable nicht als feste
   Zone. Die am deutlichsten benannte Fundstelle des Issues hat keinen Wächter.

7. **Fehlzuordnung in derselben Liste:** Der Blockkommentar bei `:593` weist alle 53
   Bestandseinträge #1726 zu, darunter ~25 Muster-A-Fundstellen (`date.today()`), die das Epic
   ausdrücklich S5/#1727 zuordnet. Wird #1726 geschlossen, verweist die Liste auf ein
   erledigtes Issue.

8. **Der #1479-AST-Wächter bricht nicht.** `tests/tdd/test_alert_quiet_hours_robustness.py`
   (AC-11) prüft nur, dass kein eigenes `try/except` um den Aufruf steht, nicht die
   Argumentliste. Eine Signaturerweiterung ist zulässig. `#1479` selbst bleibt gewahrt:
   unbrauchbarer Ruhezeit-Wert gilt weiter als „keine Ruhezeit gesetzt".

9. **Der Testbestand nagelt Wien fest, teils im Test selbst falsch.**
   `tests/helpers/nowcast_gate_fixtures.py` verdrahtet `VIENNA` zentral für mehrere Suiten.
   `test_issue_883_acute_danger_override.py` AC-5 legt einen Trip auf Island-Koordinaten,
   baut das Fenster aber über `VIENNA` — der Fehlerfall dieses Issues steckt bereits im Test.
   Betroffen außerdem: `test_alert_quiet_hours_localtime.py`,
   `test_alert_quiet_hours_robustness.py` (AC-9), `test_compare_alert_quiet_hours_precedes_fetch.py`,
   `test_compare_radar_alert.py`, `test_issue_1168_alert_engine_extract.py`,
   `test_issue_1070_daily_alert_limit.py` (prüft Reset **und** JSON-Schema wörtlich gegen Wien).

10. **Die Oberfläche nennt keine Zone.** `AlertQuietHoursCard.svelte` sagt nur „Stille Stunden";
    heute wäre die ehrliche Beschriftung „Wiener Zeit". Nach dem Fix wird sie nutzersichtbar zur
    Ortszeit — Scope ist damit **full-stack**, das Frontend-Browser-Gate greift.

11. **Beide Sommerzeit-Wechseltage sind Pflichtfälle** (ADR-0051), geprüft auf die Häufigkeit
    *jeder einzelnen Stunde*. Ruhezeit über Mitternacht (Wrap) je einmal östlich und westlich
    von Wien.

## Nebenbefund (kein Teil dieser Scheibe)

`trip_report_scheduler.py:1570` prüft `alert_daily_limit.is_allowed(..., reason="nowcast")` für
den Starkregen-Kurzfristhinweis im Briefing, **bucht aber nie** — gemessen: die fünf
`increment()`-Aufrufe im Produktivcode liegen alle woanders. Vermutlich Absicht (der Hinweis ist
Teil des Briefings, kein eigener Alarm), aber die Asymmetrie ist nirgends begründet.
Kandidat für #1199.
