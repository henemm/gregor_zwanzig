# Context: fix-1594-alarm-vorlauf-sperre

Issue: #1594 · Track: Full Process · Phase 1 (Kontext), erstellt 2026-08-14
Verwandt: #1467 (S4 offen), #1800, #1750, #1777, #1233, #1555, #1584

## Request Summary

Änderungsalarme (`forecast_change`) und amtliche Warnungen (`official_alert`) sollen unterdrückt
werden, wenn ohnehin gleich ein geplantes Briefing derselben Entität rausgeht — symmetrisch
morgens wie abends, Trip wie Ortsvergleich, ohne feste Uhrzeit im Code. **NowCast bleibt
ausgenommen** (PO-Entscheid, wörtlich bekräftigt).

## Gemessener Ist-Stand (Produktivsystem, 2026-08-14)

Quelle: `/var/lib/gregor/users/henning/`, nur gelesen.

| Feld des Trips `5f534011` („KHW 403") | Ortszeit | UTC |
|---|---|---|
| `alert_quiet_to` | **07:00** | 05:00 |
| `report_config.morning_time` | **07:00** | 05:00 |
| `alert_quiet_from` | 20:00 | 18:00 |
| `report_config.evening_time` | 18:00 | 16:00 |

Das Ende der Ruhezeit fällt heute **exakt auf die geplante Briefing-Zeit**. Am 2026-08-08 stand
`alert_quiet_to` noch auf 06:00; die Alarm-Uhrzeit im Protokoll ist mitgewandert (bis 06.08. immer
04:00 UTC, seit 13.08. 05:01/05:02 UTC). Die Alarmzeit folgt der Konfiguration, nicht dem Wetter.

**Es ist kein reines „vorher", sondern ein Wettlauf zweier Takte:**

| Tag | Alarm | Briefing | Reihenfolge |
|---|---|---|---|
| 13.08. | 05:02 | 05:00 | Alarm **nach** dem Briefing |
| 14.08. | 05:01 | 05:04 | Alarm **vor** dem Briefing |

Der Alarm-Takt ist `*/15` (`internal/scheduler/scheduler.go:145`), der Briefing-Takt `0 * * * *`
(`:141`). Eine Sperre, die nur „N Minuten **vor** dem geplanten Versand" formuliert ist, fängt den
Fall vom 13.08. nicht.

**Abend-Redundanz gemessen (offene PO-Frage aus dem Issue):** entsteht **nicht** in vergleichbarem
Ausmaß. Vor dem Abend-Briefing endet keine Ruhezeit (Ruhezeit beginnt 20:00, Briefing 18:00), also
staut sich nichts auf. Seit 25.07.: **14** Änderungs-/Warn-Alarme in der Stunde vor dem
Morgen-Briefing, **1** in der Stunde vor dem Abend-Briefing. Der symmetrische Zuschnitt bleibt
trotzdem richtig — die Zeiten sind frei konfigurierbar, und genau ihre Verschiebung hat den Effekt
hier binnen einer Woche verschoben.

## 🔴 Der Befund, der die Spec bindet: die Sammel-Zustellung ist ZUGESICHERT

`src/services/compare_official_alert.py:124-125` sagt es wörtlich:

> `#1233: Ruhezeit unterdrueckt frueh -> kein State-Verbrauch der Warnung, damit sie nach Ende der
> Ruhezeit noch als "neu" zugestellt wird (AC-2).`

Bewacht von `tests/tdd/test_compare_official_alert.py:610`
(`test_ac1_quiet_hours_suppresses_send_state_and_limit`) mit der Zusicherung: *„Waehrend Ruhezeit
unterdrueckte Warnung darf KEINEN State schreiben (sonst wird sie nach Ende der Ruhezeit als 'schon
gemeldet' verschluckt)"*.

**Das Losbrechen am Ruhezeit-Ende ist also kein Versehen, sondern eine bewusst gebaute und
getestete Eigenschaft aus #1233.** #1594 darf sie nicht still brechen. Die Auflösung, die beide
Zusicherungen erhält: die neue Sperre schreibt **ebenfalls keinen State** — sie verzögert nur, bis
das Briefing raus ist, und das Briefing selbst setzt Anker und Melde-Gedächtnis zurück
(`alert_briefing_anchor.write_anchor_and_reset_memory`, `src/services/alert_briefing_anchor.py:247-303`).
Die Meldung wird damit **ersetzt**, nicht verschluckt.

## Related Files

### Einhängepunkte — real VIER, nicht fünf

Der Bestandstest `tests/tdd/test_ruhezeit_und_zaehler_folgen_der_ortszone.py:425-624` zählt
**sieben** Ruhezeit-Stellen (`test_ac3_stelle1..7`). Davon sind Stelle 5 die NowCast-Schranke
(ausgenommen) und Stelle 3 der geteilte Trip-Adapter, den sich Stelle 2 und 4 bereits teilen:

| # | Datei:Zeile | Alarmart | Rolle |
|---|---|---|---|
| 1 | `src/services/trip_alert.py:680` (`_is_quiet_hours`) | Trip Änderung + amtlich | **ein** Adapter für die Aufrufer `:231` und `:1447` |
| 2 | `src/services/compare_alert.py:183` | Ortsvergleich Änderung | |
| 3 | `src/services/compare_official_alert.py:126` | Ortsvergleich amtlich | |
| 4 | `src/services/deviation_alert_engine.py:285` (`evaluate()`) | Engine-Kern | Aufrufer nur `trip_alert.py:282`, `compare_alert.py:400` |
| — | `src/services/alert_gate.py:98` | **NowCast** | **ausgenommen**, nicht anfassen |

### Bausteine, auf die die Sperre aufsetzt

| Datei | Relevanz |
|---|---|
| `src/services/alert_gate.py` (133 Z.) | Vorgesehene Heimat der neuen Funktion. Enthält `check_nowcast_gate()` (`:72`) und `record_nowcast_sent()` (`:119`), `GateResult` (`:47`). **Die Sperre darf NICHT in `check_nowcast_gate` eingebaut werden.** |
| `src/services/alert_briefing_anchor.py:208` `last_briefing_at()` | Liefert den Zeitpunkt des letzten Briefings je `(entity_id, entity_type)` — geteilt Trip+Vergleich. Deckt die **zweite Hälfte** des Fensters ab („gerade rausgegangen"). |
| `src/services/compare_slot_scheduler.py:104-171` `presets_due_for_hour()` | Beantwortet für den Ortsvergleich bereits „ist jetzt ein Briefing fällig?" mit `now_utc` als Parameter — inklusive `is_silenced`, `end_date`, `weekly`, Slot-Flags. |
| `src/services/trip_report_scheduler.py:437-451`, `:724-734`, `:766-790` | Dasselbe für den Trip: Fälligkeits-Fenster, Stunden-Ermittlung, Aktiv-Filter. |
| `src/services/compare_alert_guard.py:39-54` `is_silenced()` | Der **eine** Stilllegungs-Riegel für alle Alarmpfade (#1467 S2 AG6, AC-28): `paused_at` / `schedule == "manual"` / `archived_at`. |
| `src/services/briefing_slots.py` (301 Z., #1725, ADR-0051) | Idempotenz-Vermerk `(trip_id, slot, local_day, outcome)`. Trip-seitig, rückblickend. |
| `src/services/alert_log.py` | `REASON_QUIET_HOURS` / `REASON_COOLDOWN` / `REASON_DAILY_LIMIT`, Zwei-Listen-Ablage `entries` / `not_delivered`. |

### Konfigurations-Quellen

| Seite | Felder | Fundstelle |
|---|---|---|
| Trip | `report_config.morning_time`/`evening_time` (Typ `datetime.time`), **ein** Schalter `enabled` | `src/app/models.py:1033,1036-1037`; Laden `src/app/loader.py:572-573`; Flachfelder `:626-629` |
| Ortsvergleich | `morning_enabled`/`morning_time`/`evening_enabled`/`evening_time` (einzeln schaltbar), `schedule`, `weekday`, `end_date` | `src/app/models.py:1234-1237`; Auflösung `src/services/compare_slot_scheduler.py:81-100` |

## Existing Patterns

- **Geteilter Baustein + dünne Aufrufstellen** (Hausmuster S2 AG1 / S3): `alert_gate.py`,
  `compare_alert_guard.is_silenced`, `alert_briefing_anchor`. Genau so soll die Sperre entstehen.
- **Zone kommt aus derselben Auflösung wie die Fälligkeit** (#1726): Trip `anchor_tz(trip, now_utc)`
  (`src/services/trip_day.py:53-68`), Ortsvergleich `first_resolvable_tz(...)`
  (`src/utils/timezone.py:77`). Beide werden bereits von den Alarm-Gates benutzt — kein Zonenbruch.
- **Die Prüf-Reihenfolge ist heute an drei Stellen VERSCHIEDEN** — die Einsortierung der neuen
  Stufe ist deshalb eine bewusste Entscheidung, keine Formalie:

  | Pfad | Reihenfolge |
  |---|---|
  | `alert_gate.check_nowcast_gate` | Ruhezeit → Sperrzeit → Tages-Obergrenze |
  | `trip_alert` (Änderung, `:231-247`) | Ruhezeit → Sperrzeit → Tages-Obergrenze → Abruf |
  | `compare_alert` (`:133-190`) | `is_silenced` → Sperrzeit → Tages-Obergrenze → **Ruhezeit** → Abruf |

## Dependencies

- **Upstream:** `DeviationAlertEngine.is_quiet_hours`, `alert_daily_limit`, `ThrottleStore`,
  `alert_log`, `anchor_tz`/`first_resolvable_tz`, Trip-/Preset-Konfiguration.
- **Downstream:** `alert_log.json` (`not_delivered`) → Go-Zählung `internal/store/log.go`,
  Cockpit-Kachel, Briefing-Hinweis `undelivered_since_last_briefing` (#1461),
  `src/output/renderers/email/undelivered_hint.py`.

## Existing Specs

| Spec | Zusicherung, die die Sperre brechen könnte |
|---|---|
| `docs/specs/modules/rework_1467_s3_nowcast.md` | AC-11 „Abbruch an der ERSTEN zutreffenden Stufe"; AC-12 NowCast prüft gegen das **volle** Tagesbudget; AC-9 Δ/amtlich bekommen ausdrücklich **keine** Unterdrückungs-Protokollierung |
| `docs/specs/modules/fix_1479_ruhezeit_wurzel.md` | AC-11: **kein eigenes `try/except`** um `is_quiet_hours()`-Aufrufe — AST-Wächter |
| `docs/specs/modules/alert_quiet_hours_localtime.md` (#1312) | AC-6: alle Aufrufer teilen EINEN zentralen Aufruf, Sonderfälle je Alarmart verboten |
| `docs/specs/modules/fix_1555_nowcast_alert_priority.md` | NowCast bleibt zustellbar, auch wenn `forecast_change` gesperrt ist |
| `docs/specs/modules/fix_1584_alarm_zeitfenster.md` | Ruhezeiten und Tagesfenster sind **Schnittmenge, keine Ablösung** |
| `docs/specs/modules/fix_1584c_compare_alarm_zeitfenster.md:356` | nennt #1594 ausdrücklich als „nicht in dieser Scheibe" — bestätigt die Abgrenzung |
| `docs/specs/modules/feat_1459_alert_protokoll.md` | D4: Cockpit-/Archiv-Zahlen dürfen sich für Bestandstouren um keine Zahl ändern |
| `docs/specs/modules/fix_1726_ruhezeit_und_zaehler_ortszone.md` | Ruhezeit und Zähler laufen auf der Ortszone |

**ADRs:** ADR-0009 (Alerts sind Δ-Wächter gegen den letzten Briefing-Snapshot — die fachliche
Begründung, warum die Sperre überhaupt zulässig ist), ADR-0021 (geteilte Engine, mit Nachtrag
#1467 S3 zur Gate-Reihenfolge), ADR-0044/ADR-0051 (Kalendertag folgt der Ortszeit).
**Kein ADR zur Frage „wann darf ein Alarm unterdrückt werden"** — bislang implizit.

## Waechter-Tests (für die RED-Phase namentlich zu benennen)

| Zweck | Datei |
|---|---|
| Sieben-Stellen-Vollständigkeit (beste Vorlage) | `tests/tdd/test_ruhezeit_und_zaehler_folgen_der_ortszone.py` |
| #1233-Zusicherung „kein State-Verbrauch" | `tests/tdd/test_compare_official_alert.py:610` |
| AST-Wächter „kein eigenes try/except" | `tests/tdd/test_alert_quiet_hours_robustness.py:1158-1239` |
| NowCast-Ausnahme (Negativ-Nachweis) | `tests/tdd/test_alert_gate.py`, `tests/tdd/test_trip_radar_nowcast_gate_migration.py`, `tests/tdd/test_compare_radar_alert_daily_limit.py` |
| Trip-Änderung | `tests/tdd/test_alert_cooldown_quiet.py`, `tests/tdd/test_alert_quiet_hours_localtime.py`, `tests/tdd/test_issue_1168_alert_engine_extract.py` |
| Ortsvergleich-Änderung | `tests/tdd/test_compare_alert_quiet_hours_precedes_fetch.py` |

## Risks & Considerations

1. **🔴 Sperre ohne Ersatz = #1555 in neuer Verkleidung.** Vier der fünf realen Ortsvergleiche des
   PO stehen auf `schedule: "manual"` — sie haben **gar kein** geplantes Briefing. Dort darf die
   Sperre niemals greifen. Dasselbe gilt für pausierte/archivierte Vergleiche (`is_silenced`),
   `end_date` in der Vergangenheit, abgeschaltete Slots und Trips ohne Etappe am Zieltag.
2. **🔴 Die #1233-Zusicherung darf nicht still brechen** (siehe oben). Die Sperre muss dieselbe
   Eigenschaft haben: kein State-Verbrauch, keine Zähler-Buchung.
3. **Fenster muss beschränkt sein.** Der Trip hat ein **3-Stunden-Nachholfenster**
   (`NACHHOL_FENSTER_STUNDEN = 3`, `src/services/trip_report_scheduler.py:105,444`). Eine Sperre
   „solange ein Briefing aussteht" würde dort bis zu drei Stunden schweigen. Die Sperre braucht
   eine feste, begrenzte Vorlaufzeit.
4. **Briefing kann ausfallen.** Geht das Briefing nicht raus (`record_briefing_dispatch_failure`,
   `src/services/alert_briefing_anchor.py:105`), war die Sperre umsonst. Die Lücke muss auf ein
   Fenster begrenzt bleiben, damit der nächste Alarm-Takt wieder durchkommt.
5. **Dritte/vierte Fassung derselben Regel.** „Nächster Versand" existiert bereits im Frontend
   (`frontend/src/lib/utils/cockpitHelpers568.ts:247` `deriveNextSend`, mit der ausdrücklichen
   Auflage, deckungsgleich mit `resolve_preset_slots` zu bleiben). Ein neu gerechnetes
   Python-Pendant wäre eine weitere Fassung. **Empfehlung für die Analyse:** dieselben Funktionen
   fragen, die den Versand auslösen (`presets_due_for_hour`, Trip-Fälligkeitslogik), mit
   verschobenem Zeitpunkt — statt die Regel neu zu bauen.
6. **Minuten existieren nicht.** Go kappt alle Versandzeiten auf die volle Stunde
   (`internal/store/slot_hour_normalization.go:36-49,66-69,159-164`), beim Schreiben **und** beim
   Laden. Eine minutengenaue Sperre hätte keinen zusätzlichen Nutzen.
7. **Keine zwei Wahrheiten.** Der Go-Cron trägt keine Zeit-Konfiguration, er ist nur Taktgeber
   (`internal/scheduler/scheduler.go:141,145`); die Fälligkeit entscheidet ausschließlich Python.
   Das Risiko entstünde erst, wenn die Sperre eine eigene Kopie der Zeiten hielte.
8. **Unterdrückung wird für Δ/amtlich heute NICHT protokolliert** — nur NowCast schreibt seit
   #1467 S3 einen `not_delivered`-Eintrag. Ohne bewusste Ergänzung bliebe die neue Sperre
   unsichtbar („warum kam kein Alarm?" unbeantwortbar). Gegenläufig: #1800 sagt, diese Liste sei
   heute schon zu voll.
9. **#1467 S4 wird die Aufrufstellen zusammenlegen.** Die Sperre muss das überleben: eigene
   Funktion in `alert_gate.py`, dünne Aufrufer. #1777 wird zusätzlich die
   Ortsvergleich-Fälligkeit auf Fenster + Idempotenz umstellen — ein weiteres Argument, die
   Fälligkeit nicht selbst nachzubauen.
10. **Trip und Ortsvergleich sind hier strukturell ungleich:** Trip hat *einen* Schalter für beide
    Slots und ein Nachholfenster, der Ortsvergleich hat Morgen/Abend einzeln schaltbar, kein
    Nachholfenster, dafür `weekly`/`manual`-Zeitpläne. Ein 1:1 geteilter Fälligkeits-Rechner ist
    daraus nicht ableitbar; geteilt werden kann die **Sperr-Entscheidung**, nicht die
    Fälligkeits-Berechnung.

## Analysis (Phase 2)

### Type

**Bug** — nutzersichtbares Fehlverhalten (Meldungsrauschen), reproduzierbar am Produktivprotokoll.

### 🔴 Der gefährlichste Fund der Analyse: `skip_next` wird beim Lesen verbraucht

`src/services/trip_report_scheduler.py:783-788` — `_get_active_trips()` konsumiert
`report_config.skip_next` per Read-Modify-Write **mit `save_trip()`**, also einem persistenten
Schreibvorgang, bei **jedem** Aufruf:

```python
if rc.skip_next is True:
    new_rc = dataclasses.replace(rc, skip_next=False)
    new_trip = dataclasses.replace(trip, report_config=new_rc)
    save_trip(new_trip, user_id=self._user_id)
    continue
```

Bestätigt durch den Kommentar an `:428-431` („weil dort `skip_next` bei jedem Sammellauf
konsumiert wird (RMW auf `report_config`), unabhaengig von der Faelligkeit").

**Folge:** Würde die neue Sperre bequem `_get_active_trips()` bzw. `_collect_due_trips()`
mitbenutzen, verbrauchte sie im 15-Minuten-Alarm-Takt den Nutzerwunsch „nächstes Briefing
überspringen", bevor der Briefing-Scheduler ihn je sieht — das Briefing käme trotzdem. **Kein
bestehender Test fängt das**, weil die Scheduler-Tests den Versandpfad isoliert prüfen, nicht sein
Zusammenspiel mit einem fremden Takt. Ist Pflicht-Mutation der Adversary-Runde.

### Entscheidungen

| # | Frage | Entscheidung | Begründung |
|---|---|---|---|
| 1 | Einhängepunkte | **Drei**: `trip_alert._is_quiet_hours` (deckt `:231` **und** `:1447`), `compare_alert.py:183`, `compare_official_alert.py:126`. **Nicht** der Engine-Kern. | `AlertEvaluationConfig` (`src/services/point_weather.py:54-75`) ist ausdrücklich „kein Trip-Bezug" und trägt weder Versandzeiten noch Kennung — der Engine-Kern *kann* die Sperre nicht rechnen. Zudem läuft `evaluate()` bei beiden Aufrufern erst **nach** dem Wetterabruf (`trip_alert.py:250` vor `:283`; `compare_alert.py:387-394` vor `:401`). |
| 2 | Einsortierung | Als **zusätzliche letzte, rein lesende Stufe** direkt neben der jeweiligen Ruhezeit-Prüfung, vor dem Abruf. Bestehende Reihenfolgen bleiben unangetastet. | Die drei Ketten haben heute verschiedene Reihenfolgen; sie zu vereinheitlichen ist #1467 S4, nicht dieser Fix. Reines Anhängen = kleinstes Regressionsrisiko. |
| 3 | Heimat der Funktion | **`src/services/alert_gate.py`**, klar getrennt von `check_nowcast_gate()`. Kein neues Modul. | Ein eigenes Modul erkauft keine echte NowCast-Sicherheit (die kommt aus dem Verhaltenstest, Nr. 7) und zersplittert genau die Steuerung, die #1467 S4 zusammenlegen will. |
| 4 | „Briefing steht an?" | **Vorhandene Fälligkeitslogik fragen**, nicht neu rechnen. Ortsvergleich: `presets_due_for_hour()` direkt (rein, prüft `is_silenced`/`end_date`/`weekly`/Slot-Flags bereits). Trip: **reines Prädikat herauslösen** — mit allen Aktiv-Filtern, aber **ohne** den `skip_next`-Verbrauch. | Eine eigene Rechnung wäre die vierte Fassung (eine liegt im Frontend, `cockpitHelpers568.ts:247`). Beim Trip verbietet der Seiteneffekt oben die direkte Wiederverwendung. |
| 5 | Fensterbreite | **Vorlauf: PO-Entscheidung, Empfehlung 60 Minuten.** Nachlauf: über `alert_briefing_anchor.last_briefing_at()` (Tatsache „ist raus"), gedeckelt auf ~15 Min. | Gemessen: die Alarme lagen **60 und 15 Minuten** vor dem Briefing (04:00 und 04:45 UTC gegen 05:00). Ein 15-Minuten-Vorlauf hätte die 11 Alarme um 04:00 **nicht** gefangen. Der Nachlauf über den Anker statt über die Uhr löst zugleich Risiko 4: scheitert der Versand, wird der Anker gar nicht erst fortgeschrieben (`trip_report_scheduler.py:1341` vs. `:1366`) — die Sperre unterdrückt dann nicht. |
| 6 | Kein State-Verbrauch | Strukturell erfüllt, **wenn die Sperre nur liest**. | Alle Buchungen (`state_svc.save`, `throttle.record`, `daily_limit.increment`) liegen hinter dem Versand (`trip_alert.py:341-350`, `compare_alert.py:300-301,452-458`). Die Sperre sitzt weit davor. Disziplin, kein Automatismus ⇒ eigene Mutation. |
| 7 | Protokollierung | **Keine.** Status quo bleibt (`logger.debug`). | `rework_1467_s3_nowcast.md` AC-9 legt ausdrücklich fest, dass Δ/amtlich keine Unterdrückungs-Protokollierung bekommen. #1800 nennt die Liste bereits zu voll. Und fachlich wird die Meldung **ersetzt**, nicht verschluckt — eine „nicht zugestellt"-Zeile für etwas, das Minuten später vollständig ankommt, wäre irreführend. |
| 8 | NowCast-Ausnahme | **Verhaltenstest** als Hauptwächter, kein Struktur-/AST-Test. | Wirkort ist „kommt der NowCast trotzdem durch?", nicht „welche Datei importiert was". Ein Strukturtest würde bei #1467 S4 selbst zum Kollateralschaden. |
| 9 | Entitäten ohne Briefing | Ortsvergleich fällt automatisch ab (`presets_due_for_hour` prüft alles intern). **Trip nicht** — das herausgelöste Prädikat muss Etappe-am-Zieltag, `report_config.enabled`, `paused_at`, `paused_until` zwingend enthalten. | Sonst schweigt der Alarm bei einem pausierten Trip ohne Ersatz — Fehlerklasse #1555/#1584. |
| 10 | Schnitt | **Eine Scheibe**, alle vier Aufrufstellen. | LoC ist kein Engpass; der geteilte Baustein entsteht ohnehin entitätsunabhängig; die einzige echte Hürde (Trip-Extraktion) lässt sich durch Schneiden nicht umgehen. |

### Affected Files

| Datei | Art | ~LoC | Beschreibung |
|---|---|---|---|
| `src/services/alert_gate.py` | MODIFY | 50-70 | Neue Funktion `check_briefing_imminent(...)` — Vorlauf über die Fälligkeitslogik, Nachlauf über `last_briefing_at()`. Getrennt von `check_nowcast_gate()`. |
| `src/services/trip_report_scheduler.py` | MODIFY | 15-25 | Reines Fälligkeits-Prädikat herauslösen, **ohne** `skip_next`-Verbrauch. Bestandspfad verhaltensgleich. |
| `src/services/trip_alert.py` | MODIFY | ~15 | Zwei Aufrufstellen über den geteilten Adapter. |
| `src/services/compare_alert.py` | MODIFY | ~8 | Eine Aufrufstelle. |
| `src/services/compare_official_alert.py` | MODIFY | ~8 | Eine Aufrufstelle. |

**Produktivcode ~100-125 LoC** (Limit 250). Testcode wird deutlich umfangreicher — ein
`loc_limit_override` ist wahrscheinlich nötig.

### Bewusst NICHT in dieser Scheibe

- **Der amtliche Trip-Abruf wird nicht vorgezogen.** `check_official_alert_triggers()` läuft
  unbedingt bei `trip_alert.py:469`, also **vor** der Prüfung bei `:1447` — die bestehende
  Ruhezeit-Prüfung spart diesen Abruf schon heute nicht. Die Sperre verhindert die **Meldung**,
  nicht den Abruf. Das Vorziehen wäre ein Umbau am amtlichen Abrufpfad ohne Bezug zum gemeldeten
  Problem. Beobachtung für #1199.
- Vereinheitlichung der drei unterschiedlichen Prüf-Reihenfolgen (→ #1467 S4).
- Anzeige/Wortwahl unterdrückter Meldungen (→ #1750/#1800, siehe Abgrenzung).

### Mutations-Gegenproben (Pflicht in der Adversary-Runde)

1. Vorlauf auf 0 setzen → ein Alarm kurz vor dem Slot muss trotzdem gesperrt sein.
2. NowCast-Ausnahme entfernen → bei anstehendem Briefing **und** auslösendem Regenradar muss der
   NowCast durchgehen, der Änderungsalarm nicht.
3. `manual`-/pausiertes/archiviertes Preset nicht ausnehmen → Alarm muss durchgehen.
4. State-Verbrauch einbauen → `alert_state`, Sperrzeit-Speicher und Tageszähler müssen nach einer
   gesperrten Meldung unverändert sein (#1233-Analogie).
5. 🔴 `skip_next` durch die Sperre konsumieren → nach einem Sperr-Lauf muss `skip_next` weiterhin
   `True` sein.

### Open Questions (für die Spec-Freigabe)

- [ ] **Wie lange vor einem Briefing ist eine Meldung überflüssig?** Empfehlung 60 Minuten
      (deckt alle gemessenen Fälle). Kürzer = weniger Unterdrückung, aber der historische
      04:00-Fall bliebe ungefangen.

## Abgrenzung

- **Miterledigt:** #1800 erste Frage („Warum kurz vor dem Briefing noch ein Alert?").
- **Nicht hier:** #1750 und #1800 zweite Frage — Verständlichkeit der Wörter „Sperrzeit"/„Ruhezeit"
  und die Frage, ob unterdrückte Alarme überhaupt gelistet werden sollen
  (`src/output/renderers/email/undelivered_hint.py:39,85`). Eigener kleiner Durchlauf.
- **Nicht hier:** die Ruhezeiten selbst, der Fenster-Zuschnitt des Compare-Abweichungsalarms
  (#1584 C, erledigt), die Zusammenlegung der Ablaufsteuerungen (#1467 S4).
