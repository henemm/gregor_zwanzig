# Context: fix-1661-anker-vom-falschen-tag

Issue: [#1661](https://github.com/henemm/gregor_zwanzig/issues/1661) — „Alarm-Anker vom falschen Tag wird still als gueltig behandelt (Leseseite)"
Erhoben: 2026-08-10 · Basis: `origin/main` @ `24882327` · Track: Full Process (Intake-Summe 5)

## Request Summary

Der Abweichungs-Alarm eines Trips kann gegen einen Wetter-Anker von einem **anderen Tag** vergleichen, ohne das zu bemerken: Fehlt der datierte Snapshot für heute, fällt `_get_cached_weather` auf die undatierte Datei zurück und gibt sie **ungeprüft** zurück. Der PO hat entschieden, alle drei im Issue genannten Teile in **einem** Workflow zu behandeln (Trip-Schutz, Compare-Datums-Schema, stilles Tor sichtbar machen).

## Gemessener Ist-Zustand in Produktion (2026-08-10)

Datenwurzel `/var/lib/gregor` (aus `systemd`: `Environment=GZ_DATA_DIR=/var/lib/gregor`), Nutzer `henning`.

**Der undatierte Trip-Rückfall trägt nachweislich Uraltdaten** — das Feld `target_date` steht in der Datei, wird beim Laden aber nie angesehen:

| `weather_snapshots/…` | `target_date` in der Datei | Alter am 10.08. |
|---|---|---|
| `5f534011.json` | `2026-08-10` | aktuell |
| `74de939c.json` | `2026-07-05` | 36 Tage |
| `14f1aafd.json` | `2026-06-14` | 57 Tage |

**Die datierte Reihe hat genau am Schadenstag eine Lücke:** `…_2026-08-07.json` → `…_2026-08-09.json`, der 08.08. fehlt.

### Der Schaden am 08.08. — kausal nachgemessen

Eine erste Fassung dieses Dokuments schloss aus einer Lücke im `alert_log.json` (kein `forecast_change` am 07.–09.08.) auf drei Ausfalltage. **Das war falsch** und wurde von der Gegenprobe zerlegt: am 07. und 09.08. existierte ein gültiger datierter Anker, der Rückfallpfad wurde dort gar nicht erreicht. Zudem gehörte der `forecast_change` vom 04.08. dem Ortsvergleich, nicht dem Trip. Nachgemessen gilt:

**Trip `5f534011` „KHW 403" läuft 2026-08-08 bis 2026-08-20** (`briefings/5f534011.json`), war also durchgehend aktiv — „Trip abgelaufen" scheidet als Alternativerklärung aus.

**Die Briefing-Historie (`briefing_log.json`) hat genau zwei Lücken:**

| | 06.08. | 07.08. | 08.08. | 09.08. |
|---|---|---|---|---|
| Morgen 05:00 | ✓ | ✓ | **fehlt** | ✓ |
| Abend 16:00 | ✓ | **fehlt** | ✓ (16:01) | ✓ |

Folge: am 08.08. gab es von Mitternacht bis 16:01 keinen datierten Anker für diesen Tag, und die undatierte Rückfall-Datei stammte vom Morgen des 07.08. (`target_date = 2026-08-07`).

**Journal-Beleg, nach Stunden getrennt** (`journalctl -u gregor-python.service`, Zähler für `WARNING trip_alert: No fresh weather data for trip 5f534011`):

| Fenster 04:00–10:59 | 06.08. | 07.08. | **08.08.** | 09.08. |
|---|---|---|---|---|
| blinde Läufe | 0 | 0 | **28** | 0 |

28 blinde Alarm-Läufe im Viertelstundentakt, ausschließlich am 08.08. Die Nachmittagstreffer (ab 11:00, an mehreren Tagen ~4/h) sind **anderes**, vorbestehendes Rauschen — die Warnzeile erscheint auch, wenn die Tagesetappe vorbei ist (#1584/#1199). Nur das Vormittagsfenster isoliert den hier behandelten Fehler.

**Präzisierte Schadensaussage:** der Abweichungs-Wächter war am 08.08. rund 16 Stunden lang **strukturell blind** — nicht „ein Alarm ging verloren" (das ist nicht beweisbar, weil unbekannt ist, ob sich die Vorhersage änderte), sondern „die Wache lief ins Leere und sagte es niemandem". Ob am 07./09.08. Alarme ausblieben, ist mangels Anlass nicht bewertbar und wird hier **nicht** mehr behauptet.

### Der Rückfall ist der Nachtpfad — nicht der Ausnahmefall

Daraus folgt eine Einsicht, die im Issue nicht steht: `load_dated(trip, today)` greift zwischen Mitternacht und dem ersten erfolgreichen Tageslauf **grundsätzlich** ins Leere. Der undatierte Rückfall ist damit kein seltener Notnagel, sondern der **reguläre Nachtpfad** — er ist nur deshalb üblicherweise korrekt, weil das Abend-Briefing `target_date = heute+1` schreibt (`trip_report_scheduler.py:653-667`). Fällt **ein** Abend-Briefing aus, ist der Anker die gesamte folgende Nacht und den Vormittag über vom falschen Tag. Genau das geschah am 07./08.08.

**Compare-Anker haben kein Datums-Schema:** Felder sind `id`, `name`, `lat`, `lon`, `fetched_at`, `provider`, `aggregated`, `hourly` — **kein** `target_date`. Alle acht Anker des aktiven Presets stammen vom 31.07. 16:00 (~234 h alt); der 26-h-Altersschutz greift, der Vergleichs-Alarm dieses Presets ist seit dem 01.08. faktisch stumm.

## PO-Entscheidungen (2026-08-10, vor der Analyse)

**E1 — Zuschnitt:** alle drei Teile in **einem** Workflow (nicht scheibenweise).

**E2 — Trip-Prüfung: Datum primär, Alter als zweites Netz.** Geprüft wird zuerst, ob der undatierte Rückfall den **heutigen** Tag beschreibt (`target_date`). Zusätzlich greift eine Höchstalter-Grenze als Auffangnetz, falls das Datumsfeld fehlt oder unplausibel ist. Begründung: das exakte Datum steht in der Datei, ein reiner Altersschutz über den Schreibzeitpunkt wäre das schwächere Werkzeug.

**E3 — Compare: NICHT `load_dated` nachrüsten.** Der im Issue vorgeschlagene Teil 2 zielt am eigentlichen Problem vorbei (siehe R3). Gebaut wird stattdessen: der beim **Abend-Versand** geschriebene Δ-Anker soll den Tag abbilden, über den das Briefing tatsächlich informiert hat (`target_date = heute+1`), statt konstruktionsbedingt den Schreibtag. Das Datei-Layout der Compare-Anker bleibt unverändert — **kein** neues Schema, kein Pruning, keine Bestandsdaten-Migration (R4 entfällt damit weitgehend). `#1584c` AC-5 wird dabei **ausdrücklich nachgezogen**, nicht still gebrochen: die Zusicherung „Anker und Frisch-Abruf bleiben am laufenden lokalen Tag" muss neu formuliert werden als „Anker und Frisch-Abruf beschreiben denselben Tag — nämlich den, über den zuletzt gebrieft wurde".

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/trip_alert.py:484-512` | `_get_cached_weather` — Kern des Bugs: `svc.load(trip.id)` in `:509` ohne jede Prüfung |
| `src/services/trip_alert.py:434-437` | „stilles Tor": `if not cached: continue`, **kein** Log |
| `src/services/trip_alert.py:1128-1130` | Zweite Aufrufstelle (`check_official_alert_triggers`), identisches Muster ohne Log |
| `src/services/trip_alert.py:1004-1010` | Zeitfilter über `cached.segment` — hier fallen die Segmente eines falschen Tages raus |
| `src/services/trip_alert.py:237` | `logger.warning("No fresh weather data for trip …")` — Ursache nicht unterscheidbar (Rauschbefund #1199, ~1350 Journal-Treffer) |
| `src/services/weather_snapshot.py:61-198` | `save`/`save_dated`/`load_dated`/`load`/`_prune_dated_snapshots` |
| `src/services/compare_weather_snapshot.py:42-100` | Nur `save`/`load`. Kein `save_dated`/`load_dated`, kein Pruning |
| `src/services/compare_alert.py:49,360,387-416` | `_MAX_ANCHOR_AGE = 26 h` und `_anchor_too_old` — der einzige existierende Anker-Frische-Baustein |
| `src/services/scheduler_dispatch_service.py:496-532` | `_write_compare_alert_snapshots` — Schreiber der Compare-Anker |
| `src/services/compare_location_weather_source.py:77-86` | Anker-Abruf ist an `local_today` gebunden |
| `src/services/trip_report_scheduler.py:653-667,1104-1111` | Schreiber der Trip-Anker; `_get_target_date`: morning → heute, evening → **heute+1** |
| `src/services/alert_briefing_anchor.py` | `record_briefing_dispatch_failure` (#1629) — Muster für die Diagnosespur |
| `internal/scheduler/briefing_health.go` | Go-Aggregation der Diagnosespur an `/api/scheduler/status` |

## Existing Patterns

**Datei-Layout.** Trip: `data/users/<uid>/weather_snapshots/{trip_id}.json` (undatiert) und `{trip_id}_{YYYY-MM-DD}.json` (datiert, Retention 7). Compare: `data/users/<uid>/compare_weather_snapshots/{preset_id}__{location_id}.json` — nur eine Form.

**Feldsemantik Trip.** Die JSON trägt `trip_id`, `target_date`, `snapshot_at`, `provider`, `segments`. `snapshot_at` ist der **Schreibzeitpunkt**, `target_date` der **beschriebene Tag**. `load_dated` liest `target_date` nicht (der Dateiname trägt das Datum); `load()` liest es ebenfalls nicht und gibt es auch nicht zurück — es fällt beim Laden vollständig auf den Boden.

**Anker-Frische (nur Compare).** `_anchor_too_old` normalisiert `fetched_at` auf UTC (Hausnorm #1345), vergleicht gegen 26 h, protokolliert eine WARNING und gibt `True` zurück — **ohne** den Anker neu zu schreiben und **ohne** `alert_state`/Cooldown anzufassen (sonst würde aus zeitweiliger Unterdrückung Dauerstille, #1584c AC-7).

**Ausfall sichtbar machen (#1629, frisch gemergt).** JSONL-Zeile nach `data/users/<uid>/diagnostics/briefing_dispatch_failures.jsonl` (fail-soft), Go liest per Glob, dekodiert **nur** `ts` (Privacy #252), bildet Streak + Zähler und hängt sie als Feldpaar an `/api/scheduler/status`. Eigene Lücken-Schwelle 26 h, weil Briefings nur 1–2×/Tag laufen.

## Dependencies

- **Upstream:** `get_data_dir()`/`get_snapshots_dir()` (`src/app/loader.py:1081-1156`), `SegmentWeatherData`, `resolve_compare_time_window()`, `DeviationAlertEngine`.
- **Downstream:** `TripAlertService.check_alerts` und `check_official_alert_triggers`; `CompareAlertService._evaluate_one_location`; die Go-Seite über `/api/scheduler/status`.

## Existing Specs

| Pfad | Bezug |
|---|---|
| `docs/specs/_archive/modules/bug_823_snapshot_date_guard.md` | Führte die Datums-**Priorität** ein (dated vor undated). Enthält **keine** Alters- oder Datumsprüfung des Rückfalls |
| `docs/specs/modules/fix_1584c_compare_alarm_zeitfenster.md` | Führte `_MAX_ANCHOR_AGE`/26 h ein. AC-6a (25 h 50 → Alarm), AC-6b (26 h 10 → kein Alarm + WARNING), AC-7 (nach frischem Anker wieder Meldung). **AC-5: Anker und Frisch-Abruf bleiben immer am laufenden lokalen Tag** |
| `docs/specs/modules/fix_1629_briefing_anker_versandfehler.md` | Schreibseite. Nennt #1661 wörtlich als Folgescheibe. AC-10 grenzt ab: scheitert der **Wetterabruf**, entsteht bewusst **kein** Anker |
| `docs/specs/modules/fix_1628_nowcast_datenluecke.md` | Muster „Ausfall ≠ nichts zu melden" |

## Testabdeckung — die Lücke ist belegt

`tests/tdd/test_issue_823_snapshot_date_guard.py` prüft drei Fälle, aber **immer** mit korrektem Datum oder vorhandenem datiertem Snapshot:
- `:109-139` dated vorhanden → dated gewinnt
- `:142-162` Rückfall auf undatiert — die Testdatei trägt dort `target_date=today` (`:155`)
- `:165-214` dated für heute vorhanden, morgen-datiertes Undatiert wird ignoriert

**Kein Test simuliert: kein datierter Snapshot für heute UND undatierter Rückfall mit falschem `target_date`.** Genau das ist die offene Lücke.

`tests/tdd/test_compare_alert_day_window.py:589-683` deckt AC-6a/6b/7 des Compare-Altersschutzes ab. `tests/tdd/test_briefing_anchor_survives_dispatch_failure.py:689-753` zeigt den Prod-Ausfall vom 08.08. als Ausgangslage der Schreibseite.

## Risks & Considerations

**R1 — Der Issue-Vorschlag „geteilter Baustein" widerspricht einer dokumentierten Entscheidung.** `compare_alert.py:399-401` begründet ausdrücklich, warum die Anker-Frische **nicht** in der geteilten `DeviationAlertEngine` sitzt: sie hänge am Versandrhythmus des jeweiligen Ortsvergleichs, sei also „Compare-eigene Politik (ADR-0021)". ADR-0021 listet in seinen Nachträgen die seither vereinheitlichten Bausteine — die Anker-Frische ist **nicht** darunter. Entweder die Begründung fällt (mit ADR-Nachtrag), oder die Teilung tut es. Das ist in `/20-analyse` zu entscheiden, nicht im Vorbeigehen. Zugleich gilt die PO-Vorgabe zur Trip/Vergleich-Code-Teilung und die Pendant-Sperre am Commit (`pendant_gate.py`).

**R2 — Trip und Compare haben unterschiedlich scharfe Information.** Der Trip kennt `target_date` (den beschriebenen Tag) — das ist ein **schärferes** Kriterium als ein Höchstalter über den Schreibzeitpunkt. Der Compare kennt nur `fetched_at`. Ein wörtlich „geteilter" Altersschutz würde auf der Trip-Seite das schwächere Werkzeug verwenden, obwohl das bessere in der Datei liegt.

**R3 — „`load_dated` für Compare" ist womöglich nicht das eigentliche Compare-Problem.** Der Compare-Anker beschreibt **konstruktionsbedingt** den laufenden lokalen Tag (`compare_location_weather_source.py:77-86`), und `#1584c` AC-5 hält als getestete Zusicherung fest, dass Anker und Frisch-Abruf genau dort bleiben sollen. Gleichzeitig läuft der Abend-Slot mit `target_date = heute+1` (`compare_slot_scheduler.py:111-112`), das aber an `_write_compare_alert_snapshots()` gar nicht übergeben wird. Ein Datums-Schema für Compare einzuführen heißt also, AC-5 neu zu verhandeln — nicht, eine vergessene Zeile nachzutragen. **Vor der Spec dem PO vorzulegen.**

**R4 — Persistenz-Schema-Änderung.** Teil 2 ändert das Datei-Layout der Compare-Anker. Es gilt Read-Modify-Write mit Merge, nie Replace; Altbestand (die acht Dateien vom 31.07.) darf nicht verwaisen. Edits an Schema-Dateien lösen den Pre-Snapshot-Hook aus.

**R5 — Ein Signal ohne Leser versandet.** Das Kontext-Dokument zu #1629 hält fest: `NowcastResult.throttled` hatte null Leser, `data_unavailable` (#1628) genau einen. Für Teil 3 heißt das: die Sichtbarkeit muss an einem Ort landen, den jemand tatsächlich liest — bevorzugt die bestehende Diagnosespur plus `/api/scheduler/status`, nicht eine neue Logzeile.

**R6 — Verschärfung kann Alarme abschalten.** Wird der Rückfall strenger, verschwinden Alarme, die heute (zufällig richtig) noch ausgelöst werden. Der Fall „Anker verworfen" muss unterscheidbar gemeldet werden und darf **nicht** `alert_state`/Cooldown anfassen — sonst wird aus zeitweiliger Unterdrückung Dauerstille (Lehre aus #1584c AC-7).

**R7 — Offene Nachbar-Issues im selben Codebereich.** #1584 (Alarme schalten 2 h nach Ankunft ab), #1594 (Ausbruch am Ruhezeit-Ende), #1599 (Stunde 19). Berührungen an `trip_alert.py` sind mit diesen Baustellen abzugleichen.

## Analysis

### Type
**Bug** — nutzersichtbares Fehlverhalten, in Produktion gemessen (siehe „Der Schaden am 08.08.").

### Ergebnis der Gegenprobe (analysis-challenger)

| Behauptung | Urteil | Konsequenz |
|---|---|---|
| Trip: `target_date` ist schärfer als ein Höchstalter (E2) | **hält** | Die befürchtete Gefahr „Anker enthält Segmente mehrerer Tage" besteht faktisch **nicht**: der Abgleich läuft über `segment_id`, und `_fetch_fresh_weather` filtert Frisch-Daten hart auf heute (`trip_alert.py:1006-1010`). Morgen-Segmente im Cache finden nie ein Gegenstück |
| Compare: Abend-Anker statt `load_dated` (E3) | **hält**, nachgemessen | Der Einwand „nutzt das Preset den Abend-Slot überhaupt?" ist beantwortet: `cp-eb6ba0b239d90e37` („Le Var") hat `evening_enabled: True` um 18:00. Die vier übrigen Ortsvergleiche haben nur einen Morgen-Slot |
| Drei Ausfalltage 07.–09.08. | **gefallen** | Korrigiert, siehe oben: nur der 08.08. ist zurechenbar. Die 234-h-Anker des Ortsvergleichs belegen einen **ausbleibenden Versand**, nicht die Tagessemantik — sie taugen nicht als Beleg für E3 (E3 steht auf dem `evening_enabled`-Befund) |
| Fix gehört auf die Leseseite | **hält, stark** | #1629 AC-10 sichert bewusst zu, dass bei Wetterabruf-Fehlern **kein** Anker entsteht. Der Zustand „kein datierter Anker für heute" bleibt also erreichbar — und ist zusätzlich jede Nacht der Regelfall |

**Zusätzlicher Fund der Gegenprobe:** `trip_command_processor.py:294-303` schreibt einen Snapshot **direkt** über `WeatherSnapshotService.save()` und umgeht damit `write_anchor_and_reset_memory()`, das bei `on_demand=True` bewusst aussteigt (`alert_briefing_anchor.py:233-234`, Invariante #1007 „On-Demand ist read-only"). Der On-Demand-Pfad überschreibt also den undatierten Anker, den der Alarm als Netz nutzt. **Nicht in dieser Scheibe**, aber als bekannte Abweichung zu vermerken.

### Affected Files

| Datei | Art | Beschreibung |
|---|---|---|
| `src/services/weather_snapshot.py` | MODIFY | Neue schlanke Methode `load_target_date(trip_id)` — liest nur den Kopf der undatierten Datei |
| `src/services/trip_alert.py` | MODIFY | Teil A: Prüfung im Rückfallpfad. Teil C: sichtbare Meldung an beiden Toren (`:434-437`, `:1128-1130`) |
| `src/services/point_weather.py` | MODIFY | Optionales Feld `target_date` |
| `src/services/compare_location_weather_source.py` | MODIFY | Optionaler `target_date`-Parameter, stempelt ihn auf das Ergebnis |
| `src/services/compare_weather_snapshot.py` | MODIFY | `target_date` additiv serialisieren/lesen |
| `src/services/scheduler_dispatch_service.py` | MODIFY | `target_date` an `_write_compare_alert_snapshots` durchreichen |
| `src/services/compare_alert.py` | MODIFY | Anker-`target_date` an den Frisch-Abruf weitergeben (konditional) |
| `src/services/alert_briefing_anchor.py` | MODIFY | `record_alert_anchor_rejected(...)`, fail-soft, nach Muster #1629 |
| `internal/scheduler/briefing_health.go` | MODIFY | Eigener Analyzer + Feldpaar an `/api/scheduler/status` |
| 3 Testdateien (Attrappen-Signaturen) | MODIFY | je ~3 LoC, zu Recht rot |

### Technical Approach — Entscheidungen

**A1 — `target_date` über eine eigene Methode, nicht über den Rückgabewert.** `load()` hat drei Aufrufer; zwei davon (`weather_extractor.py:84,127`) sind reine Anzeigepfade für `/heute`-/`/morgen`-Kommandos und sollen bewusst „was auch immer da ist" zeigen. Ein geänderter Rückgabetyp würde deren Semantik still mitverändern.

**A2 — Die Prüfung sitzt in `trip_alert.py`, nicht im Speicher-Layer.** Prüfort = Wirkort: dort wird verworfen, dort wird geloggt, dort ist die Alarm-Politik zuhause. Symmetrisch zur Begründung in `compare_alert.py:399-401`. **Damit entfällt der Konflikt mit ADR-0021 (R1):** es entsteht **kein** geteilter Baustein und **keine** zweite Kopie — die Trip-Seite bekommt ein **anderes**, schärferes Kriterium (Datum), der Ortsvergleich behält seinen Altersschutz. Geteilt wird nur der Zahlenwert 26 h, nicht der Code. Kein ADR-Nachtrag nötig.

**A3 — Das Altersnetz greift NUR, wenn `target_date` fehlt oder unlesbar ist.** Ein vorhandenes, aber falsches Datum wird vom Datumsabgleich erledigt; ein Altersnetz würde dort ein inhaltlich falsches Datum durchwinken, solange es frisch geschrieben ist. Grenze 26 h, analog zum Ortsvergleich und aus demselben Grund (Briefings laufen 1–2×/Tag).

**A4 — Verwerfen heißt genau: `None` zurückgeben.** Kein Anfassen von `alert_state`/Cooldown, kein Neuschreiben des Ankers (Lehre #1584c AC-7 — sonst wird aus zeitweiliger Unterdrückung Dauerstille).

**B1 — Additives Feld statt neues Schema.** `PointWeatherData` bekommt ein optionales `target_date`; die Anker-JSON trägt es zusätzlich. Dateiname und Ablageort bleiben unverändert. Altbestand ohne das Feld liefert `None` → Verhalten exakt wie heute. Keine Migration.

**B2 — Weitergabe an den 15-Minuten-Check konditional.** Nur wenn der Anker tatsächlich ein Datum trägt, wird es an den Frisch-Abruf durchgereicht. Grund: eine bedingungslose Übergabe bräche ~11 weitere Testdateien, deren Attrappen die Signatur nicht kennen — ohne fachlichen Gewinn, denn ohne datierten Anker gibt es nichts abzugleichen.

**B3 — `_anchor_too_old` bleibt unangetastet** und läuft weiterhin vor dem Abgleich. Alter und Tagesbezug sind zwei unabhängige Fragen.

**C1 — Eigene Diagnosespur, gleiches Muster.** Nicht `briefing_dispatch_failures.jsonl` erweitern: dort ist die Streak-Schwelle auf den Briefing-Takt (1–2×/Tag, 26 h) kalibriert, der Alarm-Check läuft alle 15 Minuten. Zwei Kadenzen in einem Zähler verfälschen beide Aussagen. Neue Datei `diagnostics/alert_anchor_rejected.jsonl`, eigener Go-Analyzer, Lücken-Schwelle 60 Minuten.

**C2 — Drei Fälle, zwei Behandlungen.** „Anker vom falschen Tag" und „Anker zu alt" gehören in die Eskalation. „Gar kein Anker" ist bei einem noch nicht gebrieften Trip der harmlose Normalfall — dort nur eine sichtbare Logzeile. **Abweichend vom Vorschlag des Agenten** eskaliert Fall (a) aber sehr wohl, wenn der Trip **gerade läuft** (`start_date <= heute <= end_date`): bei einem laufenden Trip ohne jeden Anker ist die Wache blind, und genau das soll auffallen. Ohne diese Unterscheidung wäre Fall (a) entweder Dauerrauschen (#1199-Muster) oder ein blinder Fleck.

### Scope Assessment

- Dateien: 9 Quell- + 3 Testdateien (Signatur-Anpassung)
- Geschätzte LoC Implementierung: **185–235**
- Neue rote Tests (Phase `/40-tdd-red`): **80–150** zusätzlich
- Risiko: **MEDIUM–HIGH** (kritischer Pfad, aber kein Schema-Bruch, keine Migration)

**Das Workflow-Limit von 250 LoC wird mit den nötigen Tests überschritten.** Entscheidung erforderlich (siehe „Open Questions").

### Reihenfolge

**A → C (Python/Trip) → B → C (Go).** Teil A ist unabhängig, kleinster Diff, schließt die belegte Lücke. Teil C/Python hängt am selben Code wie A. Teil B ist isoliert, trägt aber das höchste Testrisiko. Die Go-Seite zuletzt.

### Open Questions

- [ ] **LoC-Budget:** Limit für diesen Workflow anheben oder Teil C aufteilen? (PO-Entscheidung, siehe unten)

## Nicht in diesem Workflow

- #1199 — Rauschen der Warnzeile „No fresh weather data" (Sammel-Issue)
- Rückwirkendes Neuschreiben verworfener Anker (widerspräche ADR-0009 und #1584c)
