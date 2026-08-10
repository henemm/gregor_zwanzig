# Context: fix-1667-arrival-midnight-wrap

**Issue:** [#1667](https://github.com/henemm/gregor_zwanzig/issues/1667) — „Ankunftszeit-Berechnung ignoriert Mitternachts-Wrap"
**Workflow:** `fix-1667-arrival-midnight-wrap` (Full Process, Intake-Score 5)
**Erstellt:** 2026-08-10 · Basis-HEAD `5ea233a4`

## Request Summary

Rund 20 Tests schlagen reproduzierbar zwischen ~22:00 und 00:00 UTC fehl, weil Test-Fixtures ein Stage-Datum von `now.date()` mit Ankunftszeiten aus `(now + N h).strftime("%H:%M")` kombinieren. Zu klären ist, ob derselbe Musterfehler auch im Produktionscode existiert — dort wäre er sicherheitsrelevant, weil ein noch unterwegs befindlicher Wanderer Wetterwarnungen verlieren könnte.

## 🔴 Die Issue-Prämisse ist überholt — die wahre Ursache ist eine andere

Das Issue nennt als Ursachenkette: Ankunft nach Mitternacht → wird als Vergangenheit gelesen → löst die #1584-Unterdrückung („Alarme schalten 2h nach Ankunft ab") aus. **Beide Glieder dieser Kette treffen nicht zu.**

1. **Die 2h-Regel existiert nicht mehr.** Commit `dcabda4a` (PR #1590, gemerged als `e69017c8`, 2026-08-08) hat sie durch das ortszeit-aufgelöste Tagesfenster ersetzt. `grep -rn "arrival_time + timedelta" src/` findet nur noch den 1h-Mindestfenster-Fallback aus #1584 selbst (`src/services/trip_segments.py:288`). Die Fehlschläge wurden am 2026-08-10 beobachtet, also *nach* diesem Merge.

2. **`arrival_calculated` kann gar keine Zeit nach Mitternacht tragen.** `_format_hhmm()` klemmt auf `23:59` — dreifach identisch in `src/core/naismith.py:54-60`, `internal/model/naismith.go:88-96` und `frontend/src/lib/utils/naismith.ts:63-68`. Nur ein manuell gesetzter `arrival_override` trägt eine Zeit wie `"00:30"`.

### Die tatsächliche Ursache: `wp_days[0]` kann strukturell nie 1 werden

`src/services/trip_segments.py:149-158`:

```python
day = 0
prev = None
wp_days: List[int] = []
for t in wp_times:
    if t is not None and prev is not None and t < prev:  # strikt fallend = Tagesgrenze
        day += 1
    wp_days.append(day)
    if t is not None:
        prev = t
```

`prev` ist beim ersten Durchlauf `None` ⇒ **`wp_days[0]` ist immer 0.** Der Rollover aus #1098 erkennt eine Tagesgrenze nur *zwischen* zwei Wegpunkten. Eine Etappe, deren **erster** Wegpunkt bereits auf den Folgetag gehört, ist im Datenmodell nicht darstellbar.

Damit ist die Uhrzeit-Abhängigkeit exakt rechenbar (Beispiel `_save_radar_trip`, Versätze +1h/+4h):

| Laufzeit UTC | wp0 (+1h) | wp1 (+4h) | `wp_days` | Ergebnis |
|---|---|---|---|---|
| 12:00 | 13:00 | 16:00 | [0,0] | Segment heute 13–16 Uhr, aktiv → **grün** |
| 20:00–22:59 | 21:00 | 00:00 | [0,**1**] | strikt fallend ⇒ Rollover greift **korrekt** → **grün** |
| **ab 23:00** | **00:00** | **03:00** | **[0,0]** | steigend ⇒ kein Rollover ⇒ Segment liegt **23 h in der Vergangenheit** ⇒ „alle Segmente vorbei" ⇒ `check_radar_alerts()` liefert 0 → **rot** |

Bei den +2h/+4h-Fixtures verschiebt sich die Kippkante auf 22:00 UTC. Das erklärt die Feldbeobachtung „~20 Tests, 23:00–00:00 UTC" ohne Rest.

**Zweiter, seltenerer Mechanismus:** Baut die Fixture um 23:59:59 und läuft der Check um 00:00:01, ist `date_type.today()` (`src/services/trip_alert.py:739`) bereits der Folgetag, das Stage-Datum aber der Vortag ⇒ `get_stage_for_date()` findet nichts ⇒ leere Segmentliste.

## Related Files

### Produktionscode — Schreibpfad Ankunftszeit
| Datei:Zeile | Relevanz |
|---|---|
| `src/core/naismith.py:54-60` | `_format_hhmm()` — **die 23:59-Klemme**; einzige Erzeugungsstelle der Ankunftszeit |
| `src/core/naismith.py:75-114` | Naismith-Rechnung je Wegpunkt |
| `internal/model/naismith.go:88-121` | Go-Spiegel der Klemme (`ComputeStageArrivals`) |
| `frontend/src/lib/utils/naismith.ts:63-68` | TS-Spiegel der Klemme |
| `src/app/loader.py:1684-1688` | Compute-on-Save (Python) |
| `internal/store/trip.go:228-241` | Compute-on-Save (Go) |
| `src/app/trip.py:77` | Felddefinition: `Optional[str]`, `"HH:MM"` |

### Produktionscode — Lesepfad / Segmentbau
| Datei:Zeile | Relevanz |
|---|---|
| `src/services/trip_segments.py:149-158` | **`wp_days`-Offsetvektor — der Kern des Befunds** |
| `src/services/trip_segments.py:181-192` | Kombination `target_date + wp_days[i]` + `HH:MM` → `datetime` |
| `src/services/trip_segments.py:86-90` | Interpolation mit `+ timedelta(days=1)` (#1091) |
| `src/services/trip_segments.py:194-205` | Kollaps-Guard „Mitternachts-Klemme" |
| `src/services/trip_segments.py:239-292` | Ziel-Segment (#1584 nach PR #1590): Tagesfenster, `arrival_local_date` aus Ortszeit |
| `src/services/trip_forecast.py:185-198` | ⚠️ **Zweiter Befund** — kombiniert stur `stage.date` + `HH:MM`; Rollover wird vom `end <= start`-Guard stumm auf `start + 2h` eingeebnet, entgegen dem Kommentar direkt darüber |
| `src/services/segment_weather.py:453-457` | ⚠️ Nacht-Zeitreihe über **UTC**-Tag ⇒ bei Ankunft nach UTC-Mitternacht ~29 h lang |

### Produktionscode — die fünf „Segment ist vorbei"-Guards
| Datei:Zeile | Was unterdrückt wird |
|---|---|
| `src/services/trip_alert.py:749-763` | Radar-/NowCast-Alarm entfällt komplett |
| `src/services/trip_alert.py:1005-1010` | Kein Frisch-Abruf ⇒ keine Wetteränderungs-Erkennung |
| `src/services/trip_alert.py:1156-1158` | Segment fällt aus der Gruppierung amtlicher Warnungen |
| `src/services/trip_report_scheduler.py:1183-1191` | Kein Nowcast-Call im Briefing-Pfad |
| `src/services/corridor_threshold.py:86` | Korridor-/Schwellen-Treffer unterdrückt |

⚠️ `trip_alert.py:749-763` und `trip_report_scheduler.py:1183-1191` sind **getrennte Kopien derselben Auswahl-Logik** — ein Fix an einer Stelle greift nicht an der anderen.

### Testcode — betroffene Fixtures (12 Dateien, ~29–31 Testfunktionen)
| Datei:Zeile | Helfer | Versätze |
|---|---|---|
| `tests/tdd/test_alert_log_metrics.py:115` | `_save_radar_trip()` (Ursprung) | +1h/+4h |
| `tests/tdd/test_alert_urgency.py:175` | `_save_radar_trip()` (bitidentische Kopie) | +1h/+4h |
| `tests/tdd/test_issue_827_radar_throttle_recording.py:38` | `_make_trip()` | +2h/+4h |
| `tests/tdd/test_issue_1070_daily_alert_limit.py:227` | `_make_trip()` | +2h/+4h |
| `tests/tdd/test_alert_channel_threshold.py:214` | `_radar_trip()` | +2h/+4h |
| `tests/tdd/test_issue_883_acute_danger_override.py:76` | `_make_active_trip()` | −1h/+2h |
| `tests/tdd/test_alert_quiet_hours_robustness.py:224` | `_save_trip_direct()` | −1h/+2h |
| `tests/tdd/test_issue_822_radar_nowcast_segment.py:169,713,800` | inline (3×) | diverse |
| `tests/tdd/test_bundle_791_847_844_alerts.py:196` | inline | −1h/+3h |
| `tests/tdd/test_issue_995_scheduler_pause.py:183` | inline | −1h/+2h |
| `tests/tdd/test_issue_818_radar_briefing_integration.py:400` | **`pytest.skip` vor 04:00 UTC** | — |
| `tests/unit/test_alarm_zeitfenster_ziel.py:349` | **`pytest.skip` in den ersten 3 Min des UTC-Tages** | — |

Das Issue nennt 4 Dateien — es sind **mindestens 12**.

## Existing Patterns

### Vorbild für den Fixture-Fix (im Repo zweimal erprobt)
`tests/tdd/test_952_onset_alert_fidelity.py:135-147` und `tests/tdd/test_issue_1069_tier_channel_gating.py:438-450` klemmen das Ankunftsfenster auf **02:00–22:00 Ortszeit**. Das erfüllt genau die Bedingung aus der Ursachenanalyse: Wegpunkt-Zeiten steigen monoton innerhalb desselben Kalendertags, `wp_days` bleibt `[0,0]`, das Segment landet nie in der Vergangenheit.

⚠️ **Die scheinbar sauberere Alternative — Stage-Datum aus dem Ankunfts-`datetime` ableiten — löst das Problem nicht**, weil `wp_days[0]` trotzdem 0 bleibt.

### Wrap-Muster aus #399 — nur bedingt als Vorbild geeignet
`hour_in_window()` (`src/app/day_window.py:134-146`) ist der geteilte Baustein, hat aber nur **3 Aufrufer** gegen mindestens **4 wortgleiche Inline-Kopien** (`trip_report.py:422`, `email/helpers.py:149`, `renderers/day_window.py:127`, plus eigene Varianten in `comparison_engine.py`, `compare_official_alert.py`). In `docs/reference/` und `docs/adr/` kommt der Helfer **nicht ein einziges Mal** vor — keine dokumentierte Hauskonvention.

⚠️ **#1334 hat genau dieses Wrap-Muster an einer Aggregationsstelle als Bug-Ursache wieder ENTFERNT** (`src/services/segment_weather.py:226-262`): der reine Stunden-Wraparound „zog fälschlich gleiche Uhrzeiten von JEDEM Tag der Zeitreihe". Reine Stundenzahl-Wraps sind richtig beim Einordnen einer einzelnen Stunde (Anzeige/Filter) und falsch beim Aggregieren über eine mehrtägige Zeitreihe.

### Test-Uhr: existiert nicht als Werkzeug
- **`freezegun` ist nicht im Projekt** (`tests/tdd/test_compare_alert_day_window.py:48` sagt das ausdrücklich).
- Punktuelle DI-Uhren existieren: `src/services/radar_service.py:127` (`_now_fn`) — **der Radar-Dienst hat den Haken bereits, keine der betroffenen Fixtures nutzt ihn**; dazu `meteoalarm.py:75`, `dpc.py:53`, `warn_egress.py:185`.
- Der Workflow `fix-1656-testuhr` führt im Namen in die Irre: Commit `a0ae1d0d` (PR #1659) sagt wörtlich „KEIN Produktivcode angefasst"; es wurde **eine** Datei umgebaut, keine allgemeine Testuhr. Der Nachweis lief über ein **Wegwerf-pytest-Plugin zur Tageszeit-Verschiebung**, das **nicht eingecheckt** ist — für #1667 der naheliegende Nachweisweg.

## Dependencies

- **Upstream:** `naismith.py` (Ankunftsberechnung) → `loader.py`/`trip.go` (Compute-on-Save) → `trip_segments.py` (Segmentbau)
- **Downstream:** alle fünf „Segment vorbei"-Guards, Radar-/NowCast-Alarme, Wetteränderungs-Erkennung, amtliche Warnungen, Briefing-Nowcast, Korridor-Schwellen

## Existing Specs & ADRs

| Dokument | Kernaussage | Stand (nachgemessen) |
|---|---|---|
| `docs/adr/0044-kalendertage-folgen-der-ortszeit.md` | **Akzeptiert.** Kalendertage folgen der Ortszeit. „Ein Ortstag hat nicht immer 24 Stunden — jedes Tagesfenster muss seine Länge **berechnen** statt sie zu setzen." Rechenfalle: gleiches `tzinfo`-Objekt ⇒ Python rechnet auf Wanduhr-Werten. **Offene Restliste:** vier Stellen in `trip_command_processor.py` folgen der Regel noch nicht | gültig |
| `docs/adr/0035-ein-tagesfenster-fuer-trip-und-ortsvergleich.md` | **Akzeptiert.** Ein Auflöser `resolve_configured_window()`, Default 4–19 Uhr. Fenster über Mitternacht sind zulässig; am Zielsegment aber nicht abgebildet (PO 2026-08-08) | gültig |
| `docs/specs/modules/fix_1584_alarm_zeitfenster.md` | Ziel-Segment endet am Tagesfenster statt 2h nach Ankunft | **umgesetzt** (PR #1590) |
| `docs/specs/_archive/modules/issue_1098_midnight_rollover_segments.md` | `wp_days`-Vektor | **umgesetzt** (`trip_segments.py:151-157`) |
| `docs/specs/_archive/modules/issue_1004_startzeit_ssot.md:81,227` | Nennt die Klemme ausdrücklich: „**Ursache der Mitternachts-Klemme**" und „bleibt Grenzverhalten (nur abgesichert, nicht neu designt)" | **bewusste Altlast** |
| `docs/specs/modules/daywindow_gap_and_midnight_fix.md` | #1334 — Wrap-Muster in `segment_weather.py` ersatzlos entfernt | **umgesetzt** |
| `docs/specs/_archive/modules/bug_397_output_localtime.md` | Ursprung des Wrap-Musters (#397/#398/#399) | historisch |
| `docs/reference/api_contract.md:905,917,933` | `arrival_calculated` = reiner `HH:MM`-String ohne Datum; Prioritätskette `arrival_override` > `stage.start_time` > `arrival_calculated` > 08:00. **Zu Etappen über Mitternacht steht dort NICHTS** | Lücke |

### 🔴 Wichtige Abgrenzung zur PO-Entscheidung vom 2026-08-08
`fix_1584_alarm_zeitfenster.md:310-323` schließt **Mitternachts-Tagesfenster** (`start_hour > end_hour`, z. B. 22–2 Uhr) am Zielsegment bewusst aus — weil ein einzelnes Intervall das entstehende Loch nicht darstellen kann.

**Das ist NICHT derselbe Fall wie #1667.** Dort geht es um eine *Etappe mit Ankunft nach Mitternacht*, hier um ein *konfiguriertes Fenster über Mitternacht*. Beide laufen zufällig über denselben `window_end <= arrival_time`-Guard. Für Spätankünfte ist die Behandlung ausdrücklich **gewollt und per AC abgenommen** (AC-3: „der Trip fällt durch die Spätankunft NICHT stillschweigend aus der Überwachung"). Wer #1667 auf „ist doch schon entschieden" zuschneidet, verwechselt die beiden Fälle.

## Bestehende Wächter

- **`tests/test_output_timezone_guard.py`** (#1402) — AST-Ratsche mit `KNOWN_VIOLATIONS`, die nur schrumpfen darf. Flaggt rohes `.astimezone()` und stille Zonen-Rückfälle; bewacht zusätzlich die Aufrufseite in `src/`/`api/`.
- `tests/unit/test_alarm_zeitfenster_ziel.py` — AC-1…AC-6 aus #1584, inkl. `test_mitternachtsfenster_22_2_klemmt_auf_mindestfenster` und `test_ac4b_westzone_spaete_ankunft_fenster_endet_am_ortstag`
- `tests/tdd/test_issue_1004_startzeit_ssot.py:431,448,481` — Über-Mitternacht-Interpolation (#1091), Ziel-Ankunft am Folgetag (#1098)
- Weitere Wrap-Tests: `test_comparison_engine_midnight_window.py:87`, `test_thunder_forecast_day_window.py:226`, `test_drilldown_day_window_local_date.py:273,483`, `test_compare_local_time_basis.py:485`, `test_compare_outlook_day_boundary.py:116`

**Nicht bewacht:** kein Test prüft die 23:59-Klemme als Fehlverhalten; **keiner der drei Klemm-Orte (Python/Go/TS) hat einen Paritätstest** gegen die anderen beiden.

## Datenmodell — Ist-Stand nachgemessen

- `arrival_calculated`/`arrival_override` kommen in **keiner** JSON-Datei des Repos vor (`grep -rn "arrival_calculated" --include=*.json .` → 0 Treffer). Die Felder sind `omitempty`, die Ankunft wird bei jedem Lauf frisch gerechnet.
- `start_time` ist in **keiner** der 9 Trip-Fixtures gesetzt — überall greift der Default 08:00.
- **Keine einzige Etappe in den Bestandsdaten hat eine Ankunft nach Mitternacht.** Die einzigen Zeitangaben sind GPX-`time_window`-Artefakte (08:00–13:33), die seit #1004 keine Autorität mehr haben.

## Risks & Considerations

1. **🔴 Der Fixture-Fix beweist nichts über die Produktionsfrage — und entfernt zugleich den einzigen vorhandenen Frühwarn-Effekt** (abendlich rote Tests). Nach der Ursachenanalyse ist die Produktionsfrage jetzt präzise formulierbar: *Kann ein realer Trip eine Etappe haben, deren erster Wegpunkt erst nach Mitternacht erreicht wird — und was macht `wp_days[0] == 0` dann?*
2. **Der `trip_forecast.py`-Befund ist eigenständig** und vom Issue nicht erfasst: Kommentar und Verhalten widersprechen sich dort nachweislich. Zuschnitt-Entscheidung nötig — eigene Scheibe oder mitnehmen.
3. **Zwei Kopien der „Segment vorbei"-Logik** (`trip_alert.py` / `trip_report_scheduler.py`) — jeder Fix muss beide treffen oder die Teilung ausdrücklich begründen.
4. **Drei Kopien der 23:59-Klemme ohne Paritätstest** (Python/Go/TS) — wer eine ändert, hat kein Netz. Änderung an der Klemme berührt außerdem eine per #1004 bewusst stehen gelassene Entscheidung ⇒ PO-Rückfrage nötig, keine stille Korrektur.
5. **Das Wrap-Muster aus #399 ist kein Universalrezept** — #1334 hat es an einer Aggregationsstelle als Bug-Ursache entfernt.
6. **LoC-Limit 250:** `tests/` zählt mit. Ehrlicher Fixture-Scope ~80–120 LoC, Vollausbau mit Helfer + Skip-Rückbau ~140 LoC — im Rahmen, aber ohne Puffer für Produktionscode-Arbeit im selben Workflow.
7. **DST:** ADR-0044 verlangt, Fensterlängen zu *berechnen*. `trip_segments.py` nutzt `datetime.combine(...).replace(tzinfo=dest_tz)` — genau das Muster, vor dem ADR-0044 warnt. **Kein Test deckt die beiden Wechseltage hier ab.**
8. **Ruhezeiten:** `deviation_alert_engine.py:78-106` rechnet fest in `Europe/Vienna` statt in der Ortszeit des Ziels — von #1584 als offener Sonderfall benannt, Zusammenwirken mit Nacht-Ankunft ungeprüft.

## Analysis (Phase 2 — alles am laufenden Code gemessen)

### Type
**Bug** — mit einer realen, sicherheitsrelevanten Produktwirkung, die das Issue richtig befürchtet, aber falsch begründet.

### 🔴 Die Sicherheitslücke — gemessen, nicht hergeleitet

**Bedingung:** `stage.start_time + Naismith-Gehzeit > 24:00`. Erreichbar ohne Trick — ein Abendstart 18:00 mit 10 h Gehzeit genügt; die Startzeit ist im Editor frei eingebbar (`StageTimeField.svelte:34`, kein `min`/`max`).

Gemessene Kette (`start_time=22:00`, 4 Wegpunkte, Korsika):

| Messpunkt | Ergebnis |
|---|---|
| `arrival_calculated` | `['22:00','23:59','23:59','23:59']` — 3 von 4 auf die Klemme |
| Segmente | **2 statt 4** — Kollaps-Guard verwirft 15,6 km / 1800 Hm samt Überwachung |
| Ziel-Segment | 1h-Mindestfenster statt Tagesfenster (Log-Zeile wörtlich) |
| Überwachungsende | **immer 00:59 Ortszeit**, sobald die Bedingung zutrifft |
| Reale Restgehzeit | **11 h 50 min ohne Radar-/NowCast-Alarm** |
| Ab UTC-Mitternacht | `get_stage_for_date()` liefert nichts mehr — Etappe unauffindbar |

**Ursache ist die 23:59-Klemme** (`src/core/naismith.py:54-60`), nicht die 2h-Regel (seit PR #1590 weg) und nicht `wp_days` (dort nur Symptom). Die Klemme zerstört das Signal, an dem der `wp_days`-Rollover den Tageswechsel erkennt: `23:59 == 23:59` ist nicht *strikt fallend*.

### Testfehlschlag — andere Ursache, punktgenau reproduziert

`wp_days[0]` ist strukturell 0. Die Fixtures schreiben `arrival_calculated` direkt als `now + N h` und umgehen Naismith komplett. Mit einem Zeit-Verschiebungs-Plugin belegt: `test_alert_urgency.py::test_convective_radar_logs_high` grün bis 22:59 UTC, **rot ab exakt 23:00 UTC** (`check_radar_alerts() == 0`).

🔴 **Ein Fix an `wp_days` allein macht die ~30 Tests grün und ändert an der Sicherheitslücke nichts.**

### Zwei Messungen, die den Zuschnitt bestimmen

**M1 — Modulo-Wrap statt Klemme löst die Lücke und ist im Normalfall bit-identisch:**

| Start | Klemme (heute) | `total_min % (24*60)` |
|---|---|---|
| 08:00 | `['08:00','12:23','14:58','19:21']` → 4 Segmente | **bit-identisch** |
| 18:00 | `['18:00','22:23','23:59','23:59']` → **3** Segmente | `[…,'00:58','05:21']` → **4** Segmente |
| 22:00 | `['22:00','23:59','23:59','23:59']` → **2** Segmente | `['22:00','02:23','04:58','09:21']` → **4** Segmente |

**M2 — 🔴 Der Modulo allein schließt die Lücke NICHT.** `trip_alert.py:745` fragt nur `convert_trip_to_segments(trip, today)`. Um 02:00 UTC am Folgetag, Wanderer real unterwegs:
- **Ein-Etappen-Trip:** `[]` → `continue` → **null Alarme**, trotz korrekt gebauter Segmente.
- **Zwei-Etappen-Trip:** die Schleife greift das erste Segment der **nächsten** Etappe ⇒ **stille Falsch-Ortung** (Radar für `(42.42, 9.02)`, Wanderer bei `(42.34, 8.94)`). Besteht heute schon.

### Scheiben-Zuschnitt

| Scheibe | Inhalt | Wirkung | LoC |
|---|---|---|---|
| **S1** | Fixtures entschärfen (12 Dateien, Klemmen auf 02:00–22:00 Ortszeit nach `test_952_onset_alert_fidelity.py:135-147`) + 2 `pytest.skip` zurückbauen + `freezegun` als Dev-Dependency | keine Produktwirkung; räumt die abendliche Blockade weg | ~110–140 |
| **S2** | Klemme → Modulo in **drei** Sprachen (`naismith.py:59`, `naismith.go:91-97`, `naismith.ts:63-68`) + **Paritätstest**, den heute keiner der drei Orte hat | macht Nacht-Ankünfte *darstellbar* | ~95–115 |
| **S3** | Tagesübergreifende Segment-Auswahl als **additiver Fallback** + DI-Uhr `_now_fn` | macht sie *erreichbar*; behebt auch die Falsch-Ortung | ~120–130 |

**Grenzen begründet:** S1 teilt kein Codestück mit S2/S3 — zusammen hieße das, einen grünen Testlauf als Beleg für den Produktivfix auszugeben. S2 ist nachweislich inert (Normalfall bit-identisch, kein Bestands-Trip hat `start_time`); S3 greift in den heißen Alarmpfad und braucht eine eigene Adversary-Runde. S3 hängt an S2. **S2+S3 zusammen (~230 LoC) passten formal — das ist die Falle:** kein Puffer für Fix-Loops, und der Adversary müsste zwei verschiedene Wirkketten in einem Durchgang brechen.

🔴 **Auflage: S1 schließt #1667 nicht.** Der Issue bleibt bis S3 offen — sonst wird aus „Tests grün" stillschweigend „Lücke zu". Genau diese Verwechslung war der Ausgangspunkt des Tickets.

### Warum Modulo und nicht „Klemme heben"

Der Datenkontrakt bleibt **unangetastet**: Die Go-Begründung der Klemme (`naismith.go:86-88`) lautet, die Python-Gegenseite `_parse_hhmm` könne Stunden > 23 nicht konsumieren. Der Modulo liefert weiterhin nur `00:00`–`23:59` — die Bedingung ist **erfüllt, nicht umgangen**; `api_contract.md:917` bleibt wortgleich gültig. Ein echtes Anheben (`"25:30"`) bräche `time.fromisoformat`, ließe Go-`Sscanf` auf 08:00 zurückfallen und die TS-Regex auf den Default — drei stille, divergente Rückfälle ohne Paritätstest dazwischen.

### Tests, die heute das Gegenteil festschreiben (müssen mit S2 umgeschrieben werden)

- `tests/tdd/test_issue_802_fahrrad_segment_zeit.py:28` — erwartet `["08:00","23:59"]`
- `internal/model/naismith_802_test.go:77-82` — dieselbe Erwartung auf Go-Seite
- `internal/model/naismith_test.go:161-182` — expliziter Klemm-Test **mit der Begründung im Kommentar**; **umschreiben, nicht löschen**, sonst geht die einzige Dokumentation der ursprünglichen Überlegung verloren
- `tests/tdd/test_issue_1004_startzeit_ssot.py` — AC-5-Zusicherungen
- `frontend/src/lib/utils/naismith.test.ts`, `naismith_674.test.ts`

Der Kollaps-Guard `trip_segments.py:194-205` **bleibt** (fängt weiter `==`-Zeiten aus der Interpolation); nur sein Kommentar wird falsch.

### S3 — das eine ernste Risiko: Doppel-Aktivierung
Nach S2 läuft das Ziel-Segment von Etappe 08-12 bis 17:00 UTC am 08-13, während Etappe 08-13 ab 06:00 UTC läuft. Zwei Segmente gleichzeitig „aktiv"; heute entschiede allein Listenreihenfolge + `break`. **Deshalb reiner Fallback:** heute gewinnt immer, gestern kommt nur zum Zug, wenn heute nichts liefert. Gehört als eigenes AC in die Spec.

**Die PO-Entscheidung vom 2026-08-08 bleibt unberührt** — sie sitzt im `window_end <= arrival_time`-Guard; S3 fasst nur die Etappen*auswahl* an, S2 nur die Ankunfts*berechnung*. `test_mitternachtsfenster_22_2_klemmt_auf_mindestfenster` muss grün bleiben und gehört als Regressionsbeleg in beide Scheiben.

### Nachweisstrategie
- **Test-Uhr: `freezegun` als Dev-Dependency**, kein Eigenbau — Hauskonvention analog pytest-socket („das fertige Standardwerkzeug"). Erst damit ist S1 beweisbar: derselbe Test unter `freeze_time("…23:30Z")` heute rot, nach S1 grün. *Regel-Budget: an S1 gekoppelt, Prüfdatum +90 Tage.*
- **S2 Kern:** Paritäts-Fixture über alle drei Sprachen an 23:59/24:00/24:01/47:59 + Regression 22:00-Start → 4 statt 2 Segmente. **Staging:** Test-Trip `start_time=22:00`, Trip-Detail im echten Browser — vier verschiedene Uhrzeiten statt dreimal „23:59".
- **S3 Kern:** über `_now_fn` um 02:00 UTC prüfen, dass **die Koordinaten des tatsächlich begangenen Segments** abgefragt werden — nicht bloß, dass irgendein Alarm entsteht. Ein Test auf `count > 0` hätte die Falsch-Ortung nie gefunden.
- **Mutations-Gegenprobe (Pflicht):** Modulo → Klemme zurückdrehen ⇒ Segment-Zähltest muss rot werden. Fallback deaktivieren ⇒ Koordinaten-Test muss rot werden.

### Nebenbefunde — Triage-Entscheidung

| Befund | Entscheidung | Begründung |
|---|---|---|
| `trip_forecast.py:185-198` (24 h Versatz, Kommentar behauptet das Gegenteil) | **#1199-Sammeleintrag** | Nur über `src/app/cli.py:222` erreichbar (Legacy-Debug) ⇒ weder (a) noch (b) noch (c). Eintrag muss den **falschen Kommentar** nennen — er ist die Falle für den Nächsten |
| `segment_weather.py:453-457` (30 h Nachtfenster) | **#1199 + Pflicht-Nachmessung in der S2-Adversary-Runde** | Heute selten erreichbar, keine belegbare Falschzahl in zugestellter Mail. **Nach S2 ändert sich die Lage** — Nacht-Ankünfte werden erstmals real gebaut |
| `hour_in_window`-Inline-Kopien | **gar nichts** | Berührt #1667 nicht; #1334 hat das Muster andernorts als Bug-Ursache entfernt |
| `wp_days[0]` bei manuellem Override nach Mitternacht | **Known Limitation in der Spec** | Nach S2 kommt wp[0] garantiert aus `start_time`; konstruiert, nicht beobachtet |
| DST-Wechseltage (`.replace(tzinfo=...)`) | **#1199** | Echte ADR-0044-Abweichung, aber weder Ursache noch Folge von #1667 |

### PO-Entscheidungen — getroffen 2026-08-10

| Frage | Entscheidung |
|---|---|
| **Überwachungsdauer nach Mitternachts-Ankunft** | **Bis Tagesfenster-Ende** (wie bei Tagesankunft, Standard 19 Uhr). Keine zweite Zeitrechnung neben #1584. Mehr Wetterabrufe werden in Kauf genommen |
| **Editor-Anzeige bei Wegpunkt nach Mitternacht** | **Nur die korrekte Uhrzeit** („02:23"). Die Folgetags-Kennzeichnung „(+1)" kommt als **eigene kleine Arbeit danach** — nicht Teil von S2 |
| **Nacht-Etappen grundsätzlich** | **Erlaubt lassen.** Nachtstarts sind gängige Bergpraxis; keine Sperre, kein Warnhinweis |
| **Reihenfolge** | **S1 zuerst**, dann S2, dann S3. 🔴 **Auflage: #1667 bleibt bis S3 offen** — S1 schließt den Issue nicht |
