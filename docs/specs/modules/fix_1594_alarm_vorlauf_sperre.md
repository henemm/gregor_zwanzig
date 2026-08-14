---
entity_id: fix_1594_alarm_vorlauf_sperre
type: bugfix
created: 2026-08-14
updated: 2026-08-14
status: draft
version: "1.0"
tags: [alerts, trip, compare, issue-1594]
---

# Alarm-Vorlauf-Sperre: keine Doppel-Meldung kurz vor einem geplanten Briefing (Issue #1594)

## Approval

- [ ] Approved

## Purpose

Änderungsalarme (`forecast_change`) und amtliche Warnungen (`official_alert`) werden derzeit
auch dann als eigenständige Zusatz-Nachricht verschickt, wenn Minuten später ohnehin ein
geplantes Briefing mit demselben Inhalt rausgeht. Das ist besonders auffällig am Ende der
Ruhezeit: Alarme, die während der Ruhezeit unterdrückt wurden, gehen dort **gesammelt** raus,
sobald die Ruhezeit endet — und genau das fällt bei vielen Nutzern zeitlich mit dem
Morgen-Briefing zusammen.

**Gemessen am Produktivkonto des PO (Trip `5f534011`, „KHW 403"), 2026-08-14:**

| Tag | Alarm | Briefing | Reihenfolge |
|---|---|---|---|
| 13.08. | 05:02 UTC | 05:00 UTC | Alarm **nach** dem Briefing |
| 14.08. | 05:01 UTC | 05:04 UTC | Alarm **vor** dem Briefing |

`alert_quiet_to` und `report_config.morning_time` stehen beide auf 07:00 Ortszeit (05:00 UTC) —
das Ende der Ruhezeit fällt exakt auf die geplante Briefing-Zeit. Am 08.08. stand
`alert_quiet_to` noch auf 06:00; die protokollierte Alarmzeit ist seither mitgewandert (bis
06.08. durchgehend 04:00 UTC, seit 13.08. 05:01–05:02 UTC) — die Alarmzeit folgt der
Konfiguration, nicht dem Wetter. Frühere Messungen desselben Kontos zeigen zusätzlich Alarme um
04:00 und 04:45 UTC gegen ein Briefing um 05:00 UTC, also 60 bzw. 15 Minuten vorher.

**Es ist kein reines „vorher", sondern ein Wettlauf zweier unabhängiger Takte:** der
Alarm-Takt läuft alle 15 Minuten, der Briefing-Takt stündlich. Eine Sperre, die nur „N Minuten
**vor** dem geplanten Versand" prüft, hätte den Fall vom 13.08. (Alarm 2 Minuten **nach** dem
Briefing) nicht gefangen.

**Diese Scheibe fügt eine zusätzliche, rein lesende Freigabe-Stufe** hinzu: Sie unterdrückt
einen Änderungsalarm oder eine amtliche Warnung für eine Entität (Trip oder
Ortsvergleich-Preset), wenn für dieselbe Entität unmittelbar ein geplantes Briefing ansteht
(Vorlauf) oder gerade eines rausgegangen ist (Nachlauf). Der Wetter-Inhalt geht dem Nutzer dabei
nicht verloren — er kommt vollständig im Briefing an, das Sekunden bis Minuten später folgt. Die
Meldung wird **ersetzt**, nicht verschluckt. **NowCast-Alarme (Regen-/Gewitter-Onset) sind
ausdrücklich ausgenommen** (PO-Entscheid) — sie bleiben zeitkritisch und laufen unverändert
weiter.

## Der Widerspruch zu #1233 und seine Auflösung

`src/services/compare_official_alert.py:124-125` sichert wörtlich zu:

> `#1233: Ruhezeit unterdrueckt frueh -> kein State-Verbrauch der Warnung, damit sie nach Ende
> der Ruhezeit noch als "neu" zugestellt wird (AC-2).`

Bewacht von `tests/tdd/test_compare_official_alert.py:610`
(`test_ac1_quiet_hours_suppresses_send_state_and_limit`): eine während der Ruhezeit
unterdrückte Warnung darf **keinen** State schreiben — sonst würde sie nach Ende der Ruhezeit
als „schon gemeldet" verschluckt, statt zugestellt zu werden.

**Das Losbrechen am Ruhezeit-Ende ist also kein Versehen, sondern eine bewusst gebaute und
getestete Eigenschaft aus #1233.** Diese Scheibe darf sie nicht still brechen — und tut es
nicht: Die neue Vorlauf-Sperre schreibt **ebenfalls keinen State**. Sie verzögert nur bis das
Briefing raus ist, und das Briefing selbst setzt Δ-Anker und Melde-Gedächtnis zurück
(`alert_briefing_anchor.write_anchor_and_reset_memory`,
`src/services/alert_briefing_anchor.py:247-303`). Für eine Entität **ohne** anstehendes
Briefing bleibt das #1233-Verhalten (Sammel-Zustellung nach Ruhezeit-Ende) vollständig
unverändert — die neue Sperre greift dort gar nicht (AC-9).

## Symmetrie: morgens wie abends, Trip wie Ortsvergleich

Die Sperre gilt für **beide** Tageszeiten und **beide** Entitätsarten gleichermaßen — es gibt
keinen fachlichen Grund, warum ein Abend-Briefing weniger Anspruch auf eine unverdoppelte
Meldung hätte als ein Morgen-Briefing.

**Gemessen:** Die Abend-Redundanz tritt heute faktisch kaum auf. Vor dem Abend-Briefing endet
keine Ruhezeit (Ruhezeit beginnt um 20:00, Abend-Briefing geht um 18:00 raus), daher staut sich
dort nichts auf. Seit 25.07.: **14** Änderungs-/Warn-Alarme in der Stunde vor dem
Morgen-Briefing, **1** in der Stunde vor dem Abend-Briefing. Der symmetrische Zuschnitt bleibt
trotzdem richtig — Ruhezeiten und Briefing-Zeiten sind pro Nutzer frei konfigurierbar, und genau
ihre Verschiebung hat den Effekt hier binnen einer Woche entstehen lassen. Eine Sperre, die nur
für den Morgen gälte, wäre eine unbegründete Ausnahme, sobald ein Nutzer seine Zeiten anders
legt.

## Source

Drei Einhängepunkte, keiner davon im Engine-Kern:

| Datei:Zeile | Alarmart | Rolle |
|---|---|---|
| `src/services/trip_alert.py:680` (`_is_quiet_hours`) | Trip Änderungsalarm **und** Trip amtliche Warnung | **ein** Adapter für beide Aufrufer (`:231` Änderungsalarm, `:1447` amtliche Warnung) |
| `src/services/compare_alert.py:183` | Ortsvergleich Änderungsalarm | eigene Aufrufstelle |
| `src/services/compare_official_alert.py:126` | Ortsvergleich amtliche Warnung | eigene Aufrufstelle |

**Nicht** `src/services/deviation_alert_engine.py:285` (`evaluate()`, Engine-Kern): dessen
`AlertEvaluationConfig` (`src/services/point_weather.py:54-75`) ist ausdrücklich „kein
Trip-Bezug" und trägt weder Versandzeiten noch eine Entitäts-Kennung — der Engine-Kern *kann*
die neue Prüfung nicht rechnen. Zudem läuft `evaluate()` bei beiden Aufrufern erst **nach** dem
Wetterabruf (`trip_alert.py:250` vor `:283`; `compare_alert.py:387-394` vor `:401`) — eine
Sperre dort würde den Abruf nicht mehr einsparen.

Betroffene Schicht: ausschließlich **Python-Core** (`src/services/`). Kein Go-Code, kein
Frontend-Code.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/alert_gate.py` | module (Bestand) | Vorgesehene Heimat der neuen Funktion `check_briefing_imminent()`, klar getrennt von `check_nowcast_gate()` |
| `src/services/alert_briefing_anchor.py::last_briefing_at()` | module (Bestand) | Liefert den Zeitpunkt des letzten Briefings je `(entity_id, entity_type)` — deckt den Nachlauf-Zweig |
| `src/services/compare_slot_scheduler.py::presets_due_for_hour()` | module (Bestand) | Beantwortet für den Ortsvergleich „ist jetzt ein Briefing fällig?" — inkl. `is_silenced`/`end_date`/`weekly`/Slot-Flags |
| `src/services/trip_report_scheduler.py::_get_active_trips()` | module (Bestand) | Vorlage für ein neu herauszulösendes reines Trip-Fälligkeits-Prädikat — **ohne** den `skip_next`-Verbrauch |
| `src/services/compare_alert_guard.py::is_silenced()` | module (Bestand) | Der eine Stilllegungs-Riegel (`paused_at`/`schedule=="manual"`/`archived_at`), bereits Teil von `presets_due_for_hour()` |
| `src/services/deviation_alert_engine.py::DeviationAlertEngine.is_quiet_hours()` | module (Bestand) | Geteilte Ruhezeit-Prüfung an allen drei Einhängepunkten — bleibt unverändert, die neue Stufe kommt zusätzlich |
| `src/services/trip_alert.py`, `compare_alert.py`, `compare_official_alert.py` | services (Bestand) | Aufrufer der neuen Stufe an den drei Einhängepunkten |

## Estimated Scope

- **LoC:** ~100–125 Produktivcode (siehe Affected Files). Testcode wird deutlich umfangreicher
  — ein `loc_limit_override` ist wahrscheinlich nötig.
- **Files:** 5 Produktivdateien geändert, keine neue Produktivdatei (`alert_gate.py` wird
  erweitert, nicht ersetzt); 3–4 neue Testdateien, bestehende Testdateien namentlich unten.
- **Effort:** medium — kein neuer Baustein-Typ (das Muster „geteilter Freigabe-Baustein +
  dünne Aufrufer" existiert bereits aus #1467 S3), aber vier Aufrufstellen und ein
  Seiteneffekt-Fund (`skip_next`), der besondere Sorgfalt braucht.

## Implementation Details

### Vorgeschlagene Schnittstelle (in der Umsetzung präzisierbar)

```
def check_briefing_imminent(
    *,
    user_id: str,
    entity_id: str,
    entity_type: str,          # "route" | "vergleich"
    now: datetime,
    zone: ZoneInfo,
    briefing_due_at: Callable[[datetime], bool],  # reines Faelligkeits-Praedikat, gg. Zeitpunkt ausgewertet
    vorlauf_minuten: int = 60,
    nachlauf_minuten: int = 15,
) -> bool
```

Zwei ODER-verknüpfte, rein lesende Bedingungen:

1. **Vorlauf:** Das bestehende Fälligkeits-Prädikat der Entität — beim Ortsvergleich
   `presets_due_for_hour()`, beim Trip das unten beschriebene herausgelöste Prädikat — wird
   nicht nur gegen `now`, sondern zusätzlich gegen `now + vorlauf_minuten` ausgewertet. Wird die
   Entität innerhalb dieses verschobenen Zeitpunkts fällig, steht ihr Briefing unmittelbar
   bevor.
2. **Nachlauf:** `alert_briefing_anchor.last_briefing_at(user_id=..., entity_id=...,
   entity_type=...)` liegt nicht länger als `nachlauf_minuten` zurück.

Die genaue Funktionssignatur ist Implementierungsdetail; verbindlich ist die beobachtbare
Wirkung in den Acceptance Criteria unten.

### Warum „Fälligkeit fragen, nicht neu rechnen"

Eine eigene Zeitrechnung wäre bereits die **dritte** Fassung derselben Regel — eine liegt schon
im Frontend (`frontend/src/lib/utils/cockpitHelpers568.ts:247`, `deriveNextSend`, mit der
ausdrücklichen Auflage, deckungsgleich mit `resolve_preset_slots` zu bleiben). Stattdessen
fragt die neue Stufe dieselben Funktionen, die den tatsächlichen Versand auslösen —
verschoben um die Vorlaufzeit.

### Trip: reines Fälligkeits-Prädikat ohne `skip_next`-Verbrauch

`src/services/trip_report_scheduler.py::_get_active_trips()` (`:736-793`) konsumiert
`report_config.skip_next` per Read-Modify-Write **mit `save_trip()`** bei **jedem** Aufruf
(`:784-789`):

```python
if rc.skip_next is True:
    new_rc = dataclasses.replace(rc, skip_next=False)
    new_trip = dataclasses.replace(trip, report_config=new_rc)
    save_trip(new_trip, user_id=self._user_id)
    continue
```

Würde die neue Sperre diese Methode direkt mitbenutzen, verbrauchte sie im 15-Minuten-Alarmtakt
den Nutzerwunsch „nächstes Briefing überspringen", bevor der Briefing-Scheduler ihn je sieht —
das Briefing käme trotzdem. Die Umsetzung löst deshalb ein reines Prädikat heraus, das **alle**
übrigen Aktiv-Filter aus `_get_active_trips()` enthält — Etappe am Zieltag
(`trip.get_stage_for_date`), `trip.paused_at is None`, `report_config.enabled is not False`,
`report_config.paused_until` in der Vergangenheit oder unbesetzt — aber **ohne** den
`skip_next`-Zweig. `_get_active_trips()` selbst bleibt unverändert (Bestandspfad
verhaltensgleich), das neue Prädikat ist eine parallele, seiteneffektfreie Funktion.

### Einsortierung an den drei Einhängepunkten

Die neue Stufe wird an jedem der drei Einhängepunkte als **zusätzliche letzte, rein lesende
Stufe direkt neben der bestehenden Ruhezeit-Prüfung** eingefügt, vor jedem Wetterabruf. Die
bestehenden — heute an allen drei Stellen unterschiedlichen — Prüf-Reihenfolgen bleiben
ansonsten unangetastet; das Vereinheitlichen ist #1467 S4, nicht dieser Fix:

| Pfad | Reihenfolge (neue Stufe **fett**) |
|---|---|
| `trip_alert._is_quiet_hours` (deckt `:231` und `:1447`) | Ruhezeit → **Vorlauf-Sperre** → (Sperrzeit → Tageslimit → Abruf, unverändert je Aufrufer) |
| `compare_alert.py:133-196` | `is_silenced` → Sperrzeit → Tageslimit → Ruhezeit(`:183`) → **Vorlauf-Sperre** → Abruf |
| `compare_official_alert.py:98-141` | `is_silenced` → Migrations-Check → Ruhezeit(`:126`) → **Vorlauf-Sperre** → Abruf |

### Kein State-Verbrauch, keine Protokollierung

Alle Buchungen (`AlertStateService.save`, `ThrottleStore.record`,
`alert_daily_limit.increment`) liegen an allen drei Einhängepunkten strukturell **hinter** dem
Versand — die neue Stufe sitzt weit davor und liest nur. Eine unterdrückte Meldung erzeugt
**keinen** neuen Protokolleintrag: `rework_1467_s3_nowcast.md` AC-9 legt bereits fest, dass
Δ-Wetter- und amtlicher Pfad keine Unterdrückungs-Protokollierung bekommen, und die Meldung wird
hier ohnehin **ersetzt**, nicht verschluckt — eine „nicht zugestellt"-Zeile für etwas, das
Minuten später vollständig ankommt, wäre irreführend.

## Expected Behavior

- **Input:** Der jeweilige Alarm-Lauf (`*/15`-Takt) an einem der drei Einhängepunkte, mit der
  Entität (`Trip` bzw. Ortsvergleich-Preset-Dict), der Nutzer-Kennung, dem aktuellen Zeitpunkt
  und der Ortszone der Entität — alles bereits im Scope der jeweiligen Aufrufstelle, nichts muss
  zusätzlich durchgereicht werden.
- **Output:** Eine Ja/Nein-Antwort auf „steht für diese Entität unmittelbar ein geplantes
  Briefing an oder ist gerade eines rausgegangen?". Bei „ja" bricht der Alarm-Lauf für diese
  Entität ab und verschickt **keine** Meldung; bei „nein" läuft er unverändert weiter.
- **Side effects:** **Keine.** Die Stufe liest ausschließlich — sie schreibt kein
  Melde-Gedächtnis (`AlertStateService`), keine Sperrzeit (`ThrottleStore`), keinen Tageszähler
  (`alert_daily_limit`), keinen Protokolleintrag (`alert_log`), und sie konsumiert insbesondere
  **nicht** `report_config.skip_next`. Sie beschafft auch keine Wetterdaten: sie sitzt an allen
  drei Einhängepunkten vor dem Abruf, ein gesperrter Lauf kostet also kein Abruf-Kontingent
  (Ausnahme: der amtliche Trip-Pfad, dessen Abruf schon heute früher liegt — siehe „Bewusst
  NICHT in dieser Scheibe").

## Invarianten

- **Reihenfolge:** die neue Stufe läuft an jedem Einhängepunkt NACH der bestehenden
  Ruhezeit-Prüfung und VOR jedem Wetterabruf. Sie ersetzt keine bestehende Stufe und
  vertauscht keine bestehende Reihenfolge.
- **Rein lesend:** `check_briefing_imminent()` schreibt nichts — kein `AlertStateService`, kein
  `ThrottleStore`, kein Tageszähler, kein `alert_log`-Eintrag, kein `skip_next`-Verbrauch.
- **NowCast bleibt unberührt:** `check_nowcast_gate()` ruft die neue Funktion nicht auf.
- Mandantentrennung: `user_id` nie auf `"default"` zurückfallen lassen, jeder Teil mit ZWEI
  Nutzern verifiziert.
- Testpolitik: kein Mock-Theater, keine Dateiinhalt-Checks als Verhaltensnachweis.
- Testdateien nach VERHALTEN benennen, nie nach Issue-Nummer.

## Affected Files

| Datei | Art | ~LoC | Beschreibung |
|---|---|---|---|
| `src/services/alert_gate.py` | MODIFY | 50–70 | Neue Funktion `check_briefing_imminent(...)` — Vorlauf über das jeweilige Fälligkeits-Prädikat, Nachlauf über `last_briefing_at()`. Getrennt von `check_nowcast_gate()`. |
| `src/services/trip_report_scheduler.py` | MODIFY | 15–25 | Reines Fälligkeits-Prädikat herauslösen, **ohne** `skip_next`-Verbrauch. Bestandspfad (`_get_active_trips`) verhaltensgleich. |
| `src/services/trip_alert.py` | MODIFY | ~15 | Beide Aufrufstellen (`:231`, `:1447`) über den gemeinsamen Adapter an `_is_quiet_hours()` abgedeckt. |
| `src/services/compare_alert.py` | MODIFY | ~8 | Eine Aufrufstelle nach `:183`. |
| `src/services/compare_official_alert.py` | MODIFY | ~8 | Eine Aufrufstelle nach `:126`. |

## Bewusst NICHT in dieser Scheibe

- **Der amtliche Trip-Abruf wird nicht vorgezogen.** `check_official_alert_triggers()` läuft
  unbedingt bei `trip_alert.py:469`, also **vor** der Prüfung bei `:1447` — die bestehende
  Ruhezeit-Prüfung spart diesen Abruf schon heute nicht, und diese Scheibe ändert daran nichts.
  Die Sperre verhindert die **Meldung**, nicht den Abruf. Beobachtung für #1199.
- **Vereinheitlichung der drei unterschiedlichen Prüf-Reihenfolgen** (Ruhezeit/Sperrzeit/
  Tageslimit-Abfolge unterscheidet sich heute zwischen Trip, Ortsvergleich-Änderung und
  Ortsvergleich-amtlich) → #1467 S4.
- **Anzeige/Wortwahl unterdrückter Meldungen** — ob und wie ein unterdrückter Alarm dem Nutzer
  gegenüber überhaupt benannt wird → #1750/#1800 (zweite Frage).
- **Kein neuer Go-Endpunkt, kein neuer Cron-Job.** `internal/scheduler/scheduler.go` bleibt
  unangetastet — die Fälligkeit entscheidet ausschließlich Python.
- **Kein Frontend-Code.**
- **#1714 wird NICHT miterledigt.** Dort zeigt das Ortsvergleich-Briefing eine amtliche Warnung
  an, vermerkt sie aber nicht im Melde-Gedächtnis (`scheduler_dispatch_service.py:453-464` fehlt
  das Gegenstück zu `trip_report_scheduler.py:1218-1226`), weshalb der Prüfer sie erneut
  verschickt. Diese Scheibe **mildert** das nur innerhalb ihres Fensters: eine Wiederholung
  innerhalb der 15 Nachlauf-Minuten fällt weg, eine 20 oder 40 Minuten später nicht. Die Ursache
  — der fehlende Vermerk — bleibt bestehen. #1714 darf deshalb nicht mit dieser Scheibe
  geschlossen werden.

## Risiken

| | Risiko | Test, der es fängt |
|---|---|---|
| **R1** | Ortsvergleich ohne geplantes Briefing (`manual`, pausiert, archiviert, `end_date` vergangen, Slot aus) wird versehentlich mitgesperrt — Alarm schweigt ohne Ersatz (Fehlerklasse #1555/#1584) | AC-7 |
| **R2** | Trip ohne geplantes Briefing (pausiert, `enabled: false`, `paused_until`, keine Etappe am Zieltag) wird versehentlich mitgesperrt | AC-8 |
| **R3** | `skip_next` wird durch die neue Sperre konsumiert, weil sie bequem `_get_active_trips()` mitbenutzt statt des herausgelösten reinen Prädikats | AC-11 |
| **R4** | Die neue Sperre schreibt State (Melde-Gedächtnis/Sperrzeit/Tageszähler) und bricht damit die #1233-Zusicherung „kein State-Verbrauch bei Unterdrückung" | AC-10 |
| **R5** | NowCast wird versehentlich mitgesperrt, weil `check_nowcast_gate()` (oder sein Aufrufer) die neue Funktion mitruft | AC-12 |
| **R6** | Ohne Nachlauf-Deckel bleibt die Sperre wirksam, obwohl das Briefing gar nicht (mehr) zugestellt wurde (`record_briefing_dispatch_failure`) — Meldeloch ohne Grenze | AC-6 |

## Test-Plan

Kern-Schicht (deterministisch, kein Netz), sofern nicht anders vermerkt.

| AC | Datei | Schicht |
|---|---|---|
| AC-1, AC-2, AC-8, AC-11 | `tests/tdd/test_trip_alert_briefing_imminent.py` (neu) | Kern |
| AC-3, AC-7 | `tests/tdd/test_compare_alert_briefing_imminent.py` (neu) | Kern |
| AC-4, AC-9 | `tests/tdd/test_compare_official_alert_briefing_imminent.py` (neu) | Kern |
| AC-5, AC-6 | `tests/tdd/test_alert_gate.py` (Bestand, ergänzt — reine `check_briefing_imminent()`-Logik) + je ein Integrationsfall in den drei neuen Dateien | Kern |
| AC-9 (Bestandsanteil) | `tests/tdd/test_compare_official_alert.py:610` (Bestand, MUSS unverändert grün bleiben) | Kern |
| AC-10 | alle drei neuen Dateien, je ein State-/Zähler-Snapshot vor/nach | Kern |
| AC-12 | `tests/tdd/test_alert_gate.py` (Bestand, ergänzt) | Kern |
| AC-13 | alle drei neuen Dateien, Protokoll-Snapshot vor/nach | Kern |
| AC-14 | alle drei neuen Dateien, parametrisiert morgens/abends | Kern |
| AC-15 | `tests/tdd/test_trip_alert_briefing_imminent.py` + `tests/tdd/test_compare_alert_briefing_imminent.py` (neu, je zwei `user_id`-Verzeichnisse) | Kern |
| AC-16 | `tests/tdd/test_trip_alert_briefing_imminent.py` (neu) — unterdrückte Warnung dem Briefing-Renderer übergeben und im Ergebnis nachweisen | Kern |

### Pflicht-Mutationsgegenproben (Adversary-Runde)

1. Vorlauf auf 0 Minuten setzen → ein Alarm kurz vor dem Slot muss trotzdem gesperrt sein
   (fängt AC-1–AC-4 gegen einen zu knapp bemessenen Vorlauf ab).
2. NowCast-Ausnahme entfernen → bei anstehendem Briefing UND auslösendem Regenradar muss der
   NowCast durchgehen, der Änderungsalarm nicht (AC-12).
3. `manual`-/pausiertes/archiviertes Preset bzw. pausierten/deaktivierten Trip nicht ausnehmen
   → der jeweilige Alarm muss trotzdem durchgehen (AC-7, AC-8).
4. State-Verbrauch einbauen (z. B. `AlertStateService.save` vor der Sperr-Prüfung) →
   `alert_state`, Sperrzeit-Speicher und Tageszähler müssen nach einer gesperrten Meldung
   unverändert sein (AC-10).
5. `skip_next` durch die neue Sperre konsumieren lassen → nach einem Sperr-Lauf muss
   `skip_next` weiterhin `True` sein (AC-11).

### Bestehende Testdateien, die GRÜN bleiben MÜSSEN

| Zweck | Datei |
|---|---|
| Sieben-Stellen-Vollständigkeit der Ruhezeit-Prüfungen | `tests/tdd/test_ruhezeit_und_zaehler_folgen_der_ortszone.py` |
| #1233-Zusicherung „kein State-Verbrauch bei Ruhezeit-Unterdrückung" | `tests/tdd/test_compare_official_alert.py:610` |
| AST-Wächter „kein eigenes try/except um `is_quiet_hours()`" | `tests/tdd/test_alert_quiet_hours_robustness.py` |
| NowCast-Ausnahme (Bestandsverhalten) | `tests/tdd/test_alert_gate.py`, `tests/tdd/test_trip_radar_nowcast_gate_migration.py`, `tests/tdd/test_compare_radar_alert_daily_limit.py` |
| Trip-Änderungsalarm (Bestandsverhalten) | `tests/tdd/test_alert_cooldown_quiet.py`, `tests/tdd/test_alert_quiet_hours_localtime.py`, `tests/tdd/test_issue_1168_alert_engine_extract.py` |
| Ortsvergleich-Änderungsalarm (Bestandsverhalten) | `tests/tdd/test_compare_alert_quiet_hours_precedes_fetch.py` |

Live-E2E: nicht vorgesehen — die Fälligkeits-/Zeitfenster-Logik ist deterministisch mit
eingefrorener Uhrzeit vollständig im Kern prüfbar; ein Nachweis „auf den nächsten echten
Briefing-Lauf warten" wäre unzuverlässig und langsam.

## Acceptance Criteria

**(a) Kernverhalten — Meldung unterdrückt, wenn ein Briefing unmittelbar bevorsteht**

- **AC-1:** Given ein Trip, für den in Kürze (innerhalb von 60 Minuten) das nächste geplante
  Briefing verschickt wird, When in diesem Zeitfenster ein Wetter-Änderungsalarm für den Trip
  ausgelöst würde, Then wird diese Alarm-Nachricht NICHT als eigenständige Zusatz-Meldung
  verschickt.
  - Test: Trip mit fälligem Briefing in 30 Minuten, änderungswürdige Wetterdaten simulieren,
    Versandpfad prüfen — kein Alarm auf keinem Kanal.

- **AC-2:** Given einen Trip, für den in Kürze das nächste geplante Briefing verschickt wird,
  When in diesem Zeitfenster eine amtliche Unwetterwarnung für den Trip einträfe, Then wird
  diese Warnung NICHT als eigenständige Zusatz-Meldung verschickt — sie erscheint stattdessen im
  Briefing.
  - Test: Trip mit fälligem Briefing in 15 Minuten, amtliche Warnung simulieren, `
    _send_official_alert_only` liefert „nicht versendet".

- **AC-3:** Given einen Ortsvergleich, für den in Kürze das nächste geplante Briefing verschickt
  wird, When in diesem Zeitfenster ein Wetter-Änderungsalarm für ein Preset des Vergleichs
  ausgelöst würde, Then wird diese Alarm-Nachricht NICHT als eigenständige Zusatz-Meldung
  verschickt.
  - Test: Preset mit fälligem Morgen-Slot in 45 Minuten, änderungswürdige Wetterdaten für einen
    Ort simulieren, kein Versand.

- **AC-4:** Given einen Ortsvergleich, für den in Kürze das nächste geplante Briefing verschickt
  wird, When in diesem Zeitfenster eine amtliche Warnung für ein Preset des Vergleichs einträfe,
  Then wird diese Warnung NICHT als eigenständige Zusatz-Meldung verschickt.
  - Test: Preset mit fälligem Slot in 10 Minuten, amtliche Warnung simulieren, kein Versand.

**(b) Nachlauf und Fenstergrenzen**

- **AC-5:** Given eine Entität (Trip oder Ortsvergleich-Preset), deren letztes Briefing
  nachweislich vor wenigen Minuten (bis zu 15) rausgegangen ist, When unmittelbar danach ein
  Änderungsalarm oder eine amtliche Warnung für dieselbe Entität ausgelöst würde, Then wird
  diese Meldung ebenfalls NICHT als eigenständige Zusatz-Meldung verschickt — das entspricht dem
  gemessenen 13.08.-Fall (Alarm 2 Minuten nach dem Briefing).
  - Test: `last_briefing_at()` auf „vor 5 Minuten" setzen, Alarm-Bedingung erfüllen, kein
    Versand.

- **AC-6:** Given eine Entität, deren nächstes Briefing weiter als 60 Minuten entfernt ist UND
  deren letztes Briefing länger als 15 Minuten zurückliegt (oder es gab noch keins), When ein
  Änderungsalarm oder eine amtliche Warnung ausgelöst würde, Then wird diese Meldung wie bisher
  regulär verschickt — die neue Sperre greift außerhalb des Fensters nicht.
  - Test: nächstes Briefing in 90 Minuten, letztes Briefing vor 30 Minuten, Alarm-Bedingung
    erfüllen, Versand erfolgt normal.

**(c) Kein Schweigen ohne Ersatz**

- **AC-7:** Given ein Ortsvergleich-Preset OHNE geplantes Briefing (Zeitplan `manual`, pausiert,
  archiviert, `end_date` in der Vergangenheit oder der betroffene Slot abgeschaltet), When ein
  Änderungsalarm oder eine amtliche Warnung für dieses Preset ausgelöst würde, Then wird diese
  Meldung NIEMALS durch die neue Sperre unterdrückt — ohne geplantes Briefing gibt es keinen
  Ersatz, also darf auch nichts verschluckt werden.
  - Test: je ein Preset mit `schedule: "manual"`, `paused_at` gesetzt, `archived_at` gesetzt,
    abgelaufenem `end_date` und abgeschaltetem Slot — in jedem Fall geht der Alarm normal raus.

- **AC-8:** Given einen Trip OHNE geplantes Briefing (pausiert über den Trip-Pause-Knopf,
  `report_config.enabled` auf falsch, `report_config.paused_until` in der Zukunft, oder keine
  Etappe am jeweiligen Zieltag), When ein Änderungsalarm oder eine amtliche Warnung für diesen
  Trip ausgelöst würde, Then wird diese Meldung NIEMALS durch die neue Sperre unterdrückt.
  - Test: je ein Trip mit `paused_at` gesetzt, `report_config.enabled=False`,
    `paused_until` in der Zukunft und ohne Etappe am Zieltag — in jedem Fall geht der Alarm
    normal raus.

**(d) Bestehende Zusicherungen bleiben erhalten**

- **AC-9:** Given eine Entität, deren Ruhezeit endet, OHNE dass für sie ein Briefing ansteht
  (z. B. Ortsvergleich-Preset mit `schedule: "manual"`), When während der Ruhezeit ein Alarm
  unterdrückt wurde, Then wird diese Meldung nach Ende der Ruhezeit weiterhin gesammelt
  zugestellt — die #1233-Eigenschaft bleibt für Entitäten ohne anstehendes Briefing unverändert
  erhalten, die neue Sperre greift dort nicht.
  - Test: `tests/tdd/test_compare_official_alert.py:610` bleibt unverändert grün; ergänzender
    Fall in `test_compare_official_alert_briefing_imminent.py` mit `schedule: "manual"` bestätigt
    dasselbe Verhalten unter der neuen Sperre.

- **AC-10:** Given eine Meldung, die durch die neue Vorlauf-Sperre unterdrückt wird, When der
  jeweilige Lauf beendet ist, Then sind weder das Melde-Gedächtnis (`AlertStateService`) noch
  die Sperrzeit-Ablage (`ThrottleStore`) noch der Tageszähler für diese Entität verändert worden
  — genau wie bei einer während der Ruhezeit unterdrückten Meldung (#1233-Analogie).
  - Test: Zustands-Snapshot vor und nach einem durch die neue Sperre unterdrückten Lauf
    vergleichen — exakte Gleichheit.

- **AC-11:** Given einen Trip, dessen `report_config.skip_next` auf `True` steht, When während
  des Vorlauf-Fensters ein Alarm-Lauf die neue Sperre prüft, Then bleibt `skip_next` nach diesem
  Lauf weiterhin `True` — die Sperre darf den Nutzerwunsch „nächstes Briefing überspringen"
  nicht vorzeitig verbrauchen.
  - Test: Trip mit `skip_next=True` und fälligem Briefing in Kürze, Alarm-Lauf ausführen,
    `report_config.skip_next` danach unverändert `True`.

- **AC-12:** Given eine Entität, für die gleichzeitig ein NowCast-Alarm (Regen-/
  Gewitter-Onset) UND ein Änderungsalarm anstünden UND ein Briefing unmittelbar bevorsteht,
  When beide Alarmarten geprüft werden, Then wird der NowCast-Alarm trotzdem zugestellt,
  während der Änderungsalarm unterdrückt bleibt — die neue Sperre wirkt ausschließlich auf
  Änderungsalarme und amtliche Warnungen, NICHT auf NowCast.
  - Test: Szenario mit anstehendem Briefing, auslösendem Regenradar UND auslösender
    Wetteränderung gleichzeitig — NowCast-Versand erfolgt, Änderungsalarm-Versand bleibt aus.

- **AC-13:** Given eine durch die neue Sperre unterdrückte Meldung, When der jeweilige Lauf
  beendet ist, Then entsteht dafür KEIN neuer Eintrag im Alarm-Protokoll — die Unterdrückung
  bleibt wie beim Δ-Wetter- und amtlichen Pfad heute unprotokolliert (Status quo aus
  `rework_1467_s3_nowcast.md` AC-9).
  - Test: Protokoll-Snapshot vor und nach einem durch die neue Sperre unterdrückten Lauf
    vergleichen — keine neuen Einträge.

**(e) Symmetrie und Mandantentrennung**

- **AC-14:** Given identische Vorlauf-/Nachlauf-Bedingungen, When sie für ein Morgen-Briefing
  UND für ein Abend-Briefing geprüft werden, sowohl beim Trip als auch beim Ortsvergleich, Then
  wirkt die Sperre in allen vier Kombinationen gleichermaßen — es gibt keine versteckte
  Bevorzugung des Morgen- oder des Trip-Pfads.
  - Test: dieselbe Fenster-Logik parametrisiert für (Morgen, Abend) × (Trip, Ortsvergleich)
    durchlaufen, identisches Unterdrückungsverhalten in allen vier Fällen.

- **AC-15:** Given zwei verschiedene Nutzer mit je einer Entität, deren Fälligkeits- und
  Briefing-Zeitpunkte unabhängig geführt werden, When bei beiden gleichzeitig ein Alarm während
  des Vorlauf-Fensters des jeweils EIGENEN Briefings ausgelöst wird, Then wirkt die Sperre für
  jeden Nutzer ausschließlich auf seine eigenen Daten — kein Nutzer beeinflusst den anderen.
  - Test: zwei `user_id`-Verzeichnisse, unterschiedliche Briefing-Zeiten, je ein Alarm im
    eigenen Vorlauf-Fenster auslösen, Unterdrückung nur beim jeweils betroffenen Nutzer.

**(f) Die tragende Rechtfertigung — nachgewiesen, nicht vorausgesetzt**

- **AC-16:** Given eine amtliche Warnung, die durch die neue Sperre als eigenständige Meldung
  unterdrückt wurde, When das unmittelbar folgende geplante Briefing gerendert wird, Then
  erscheint dieselbe Warnung darin — die Meldung ist damit nachweislich **ersetzt** und nicht
  verschluckt. Ohne dieses Kriterium wäre die gesamte Scheibe auf einer ungeprüften Annahme
  gebaut.
  - Test: dieselbe amtliche Warnung, die den unterdrückten Alarm ausgelöst hätte, dem
    Briefing-Renderer übergeben (`seg.official_alerts` → Warn-Block,
    `src/output/renderers/email/html.py:1565-1595`) und im gerenderten Ergebnis nachweisen.
    Gilt für den Trip-Pfad; für den Wetter-Änderungsalarm ist die Ersetzung baulich gegeben
    (das Briefing zeigt den vollständigen aktuellen Wetterstand) und wird nicht separat geprüft.

## Known Limitations

- **Minutengenauigkeit ist wirkungslos.** Versandzeiten werden von Go auf die volle Stunde
  gekappt (`internal/store/slot_hour_normalization.go:36-49,66-69,159-164`), sowohl beim
  Schreiben als auch beim Laden. Der 60-Minuten-Vorlauf wirkt dadurch effektiv stundenbezogen —
  eine minutengenaue Sperre hätte keinen zusätzlichen Nutzen.
- **Der amtliche Trip-Abruf wird durch diese Scheibe nicht vorgezogen** (siehe „Bewusst NICHT in
  dieser Scheibe"). Die Sperre spart also kein Abruf-Kontingent beim amtlichen Trip-Pfad ein,
  nur die Zustellung der resultierenden Meldung entfällt.
- **Scheitert der Briefing-Versand** (`record_briefing_dispatch_failure`), bleibt der Anker
  unverändert, und der Nachlauf-Zweig wirkt entsprechend nicht mehr für diesen Fall. Der zuvor
  im Vorlauf-Fenster unterdrückte Alarm bleibt dadurch für maximal einen Alarm-Takt (bis zu 15
  Minuten) unzugestellt — der nächste reguläre Alarm-Lauf ist davon nicht betroffen und prüft
  wieder normal.
- **Die Abend-Sperre bleibt in der Praxis meist folgenlos**, weil die Abend-Redundanz heute kaum
  auftritt (gemessen: 1 von 15 Fällen seit 25.07.). Das ist kein Defekt dieser Scheibe, sondern
  Ausdruck der aktuell verbreiteten Konfiguration (Ruhezeit-Ende ≠ Abend-Briefing-Zeit) — ändert
  sich die Konfiguration eines Nutzers, greift die Symmetrie sofort.
- **Ad-hoc-Briefings („Handversand") lösen den Nachlauf nicht aus.**
  `write_anchor_and_reset_memory(on_demand=True)` schreibt weder Anker noch Reset (#1007) — ein
  auf Zuruf abgerufenes Briefing aktualisiert `last_briefing_at()` also nicht und unterdrückt
  entsprechend keinen nachfolgenden Alarm. Das ist beabsichtigt: ein Ad-hoc-Abruf ist gegenüber
  beiden Zuständen bewusst read-only, und ein solcher Abruf ersetzt kein geplantes Briefing.
- **Kein ADR zur Grundsatzfrage „wann darf ein Alarm unterdrückt werden".** Diese Scheibe fügt
  eine weitere, implizit begründete Sperrart hinzu (analog Ruhezeit, Sperrzeit, Tageslimit).
  Ein eigenständiger ADR-Nachtrag ist nicht Teil dieser Scheibe (siehe unten).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue.
- **Rationale:** ADR-0009 (Alerts als Abweichungs-Wächter gegen den letzten Briefing-Snapshot)
  trägt bereits die fachliche Begründung, warum eine Unterdrückung hier überhaupt zulässig ist —
  die Meldung wird durch das nachfolgende Briefing ersetzt, nicht ersatzlos verschluckt. ADR-0009
  macht keine Aussage über den Zeitpunkt der Unterdrückung, daher genügt die bestehende
  Begründung ohne Nachtrag. Ein möglicher künftiger ADR-Nachtrag zur Sammelfrage „welche
  Sperrarten existieren und in welcher Reihenfolge" bleibt #1467 S4 vorbehalten, das die drei
  heute unterschiedlichen Prüf-Reihenfolgen ohnehin zusammenlegt.

## Changelog

- 2026-08-14: Initiale Spec, basierend auf `docs/context/fix-1594-alarm-vorlauf-sperre.md`. Alle
  zehn dort getroffenen Entscheidungen 1:1 übernommen (drei Einhängepunkte, Heimat
  `alert_gate.py`, Fälligkeit fragen statt neu rechnen, 60-Minuten-Vorlauf / 15-Minuten-Nachlauf,
  kein State-Verbrauch, keine Protokollierung, NowCast-Ausnahme, Ersatzlosigkeits-Schutz für
  beide Entitätsarten, eine Scheibe für alle vier Aufrufstellen). Alle referenzierten
  Codestellen und Testdateien am Ist-Code vom 2026-08-14 verifiziert.
