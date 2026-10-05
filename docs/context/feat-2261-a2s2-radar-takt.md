# Context: feat-2261-a2s2-radar-takt

## Request Summary
#2261 A-2 S2: Die zwei Radar-Alarm-Prüfläufe (`radar_alert_checks`, `compare_radar_alert_checks`) sollen alle 5 statt 15 Min laufen; das Laufbudget wird je Alarmart an den eigenen Takt gebunden (Überlappungsinvariante). Ziel: Radar-Verzögerung ≈ 15 Min statt heute 32 Min (Takt 15 + Datenalter 5 + Verarbeitung 12). PO-Entscheid 03.10.: Verzögerung verkürzen.

## Related Files
| File | Relevance |
|------|-----------|
| `internal/scheduler/scheduler.go:153-155, 229-236` | Budget-Felder `alertWaitBudget` 300 s / `alertRunBudget` 720 s / `alertCallCap` 1800 s — heute EIN Satz für alle Alarmjobs („80 % des */15-Takts, Deckel = 2 Takte") |
| `internal/scheduler/scheduler.go:262-270` | Cron-Einträge; Radar `7,22,37,52 * * * *` (Offset aus #1628) |
| `internal/scheduler/scheduler.go:399-404` | `budgetsFor(jobID)` — Briefing-Jobs bekommen Briefing-Budget, alle anderen das Alarm-Budget. Natürliche Stelle für Budget je Alarmart |
| `internal/scheduler/scheduler.go:190-198` | `alertBudgetJobIDs` — deklariert, nirgends benutzt (toter Code) |
| `internal/scheduler/scheduler.go:306-393, 442, 467-491` | `runForAllUsers`, `runUserStep`, `callUserWithBudget` — Rotation, `not_reached`, `skipped_in_flight`, `budgetExceededError` |
| `internal/scheduler/scheduler.go:853-902` | `recordRun` — TryLock je jobID; belegt ⇒ Tick übersprungen, `overlap.SkippedSinceLastRun++` |
| `internal/scheduler/user_call_budget.go:54-63` | Deckel: Register-Eintrag wird nach `alertCallCap` freigegeben, neuer Aufruf möglich, während Python noch läuft |
| `internal/scheduler/user_run_state.go:27-28, 189-197, 320-328` | Schwellen zählen LÄUFE (`failureAlertThreshold=3`, `partialAlertThreshold=8`), nicht Minuten; `fanOutJobIDs` |
| `internal/scheduler/radar_cron_offset_test.go:38-56` | Verlangt erste Startminute nach :00 == 7 — bricht bei jedem 5-Min-Ausdruck; Gegenprobe `:75-100` bleibt |
| `internal/scheduler/user_call_wait_budget_test.go:391-414` | `TestBudgetDefaults_MatchSpec` 720/300/1800/1440/600 |
| `internal/scheduler/user_call_wait_budget_test.go`, `run_budget_rotation_test.go` | ~15 Tests setzen die drei Felder direkt (mit `alert_checks`) — Feld-Umbau bricht sie |
| `internal/scheduler/scheduler_unify_test.go:54,66` | 9 Einträge / 10 Jobs — bleibt bei reinem Cron-Wechsel grün |
| `api/routers/scheduler.py:97-114` | Radar-Endpunkte, immer `{"status":"ok"}` |
| `src/services/trip_alert.py:62-68, 1820ff` | `ALERT_RUN_DEADLINE_SECONDS=180` gilt NUR für `check_all_trips` (an `alertWaitBudget=300` gebunden ⇒ `alert_checks` muss ≥ 300 s behalten); `check_radar_alerts` hat keine Zeitgrenze |
| `src/services/compare_radar_alert.py:125` | Ortsvergleich-Radar |
| `src/services/radar_cache.py:68, 96-99, 127-131` | TTL 300 s, prozessweit; Treffer bei Alter ≤ TTL; Docstring nennt 15-Min-Takt |
| `src/services/radar_service.py:77,152,158,178,792-827` | A-1-Konstanten (180/27/30, nicht taktgebunden); Quellenkette BrightSky → INCA → AROME-FR → ARPAE → AROME-HD → ICON-D2 → Open-Meteo |
| `src/providers/geosphere.py:56-67` | INCA-Retries bis 180 s je Abruf |
| `src/services/forecast_budget.py:49-51,100-139` | Open-Meteo-Tagesbudget 9000; Radar (`polling`) gedrosselt ab 80 %, Abweichung ab 95 % |
| `tests/tdd/test_radar_onset_threshold_variance.py:173-182` | Kommentar nennt `7,22,37,52` |
| `/home/hem/henemm-infra/scripts/check-gregor20.sh:839-899` | `ALARM_JOB_MAX_AGE_MIN=20` für alle 5 Alarmjobs, Text „Takt 15 Min" (fremdes Repo, Arbeitsbaum ist sofort live) |

## Existing Patterns
- Budget je Jobfamilie über `budgetsFor(jobID)` (Briefing vs. Alarm, #2149 Scheibe B) — Erweiterung auf Alarmart ist derselbe Mechanismus.
- Überlappungsschutz = TryLock je jobID in `recordRun`; Invariante faktisch: Laufbudget + ~5–10 s Nacharbeit < Taktabstand.
- Python-Zeitgrenze < Go-Wartebudget (ADR-0038) — für `check_all_trips` umgesetzt (A-2 S1), für Radar nicht.
- #1628: Radar-Offset weicht Open-Meteo-Lastspitzen bei :00/:30 aus.

## Dependencies
- Upstream: Python-Core-Endpunkte, Radar-Quellenkette, `radar_cache`, `ForecastBudgetGate` (Open-Meteo 9000/Tag).
- Downstream: `/api/scheduler/status` (overlap, users-Felder), MQ-Alarme bei Schwellen (zählen Läufe), externes Monitoring `check-gregor20.sh`, Frontend-Statusanzeige (keine 15-Min-Annahme gefunden).

## Existing Specs / ADRs
- `docs/specs/modules/fix_2149_scheduler_budget_teilb.md:140-144, 286-304, 411-418` — Budget-Tabelle inkl. ausdrücklich der Radar-Jobs („Takt effektiv 15 Minuten"); wird teilweise abgelöst.
- `docs/adr/0070-aufruferseitige-wartegrenze-je-nutzeraufruf.md:22-37` — Alarm 300/720/1800 „= zwei Takte"; braucht Nachfolge-/Ergänzungs-ADR.
- `docs/adr/0038` — Python-Grenze < Wartebudget.
- `docs/reference/decision_matrix.md:285-302` — #1628-Abschnitt mit Cron-Ausdruck.
- `docs/features/architecture.md:393`; `fix_1628_nowcast_datenluecke.md:247`; `feat_2261_a1_radar_vorlauf.md:211-212`; `fix_2261_a2s1_alarmlauf_reihenfolge.md:182` (S2-Ankündigung).
- `alarm_latenz_zusage.md` existiert noch nicht (gehört zu S4).

## Messwerte (Prod-Journal, 7 Tage, 670 Ticks, 3 Nutzer)
- Trip-Radar letzte Antwort: p90 ≈ 1 s, p99 ≈ 10 s, max 33 s; Ortsvergleich-Radar ≈ 0 s.
- 30 Tage: keine Budget-/Überlappungsereignisse beim Radar.
- ~115 Radar-503 in ~10 Tagen, davon 112 auf hh:07 (Ursache unbelegt; widerspricht der #1628-Annahme „Spitze bei :00/:30").

## Risks & Considerations
1. **Startminute:** 5-Min-Raster liegt max. 2,5 Min von :00/:30 entfernt; Startminute 0 mod 5 stapelt sich mit */15-Jobs und Briefing. Kandidaten `2-57/5`, `3-58/5`. :07-Häufung der 503er berücksichtigen.
2. **Budget je Alarmart:** `alert_checks` muss Wartebudget ≥ 300 s behalten (Python-Grenze 180 s). Radar bei 300 s Takt z. B. Lauf ≤ 240 s, Warte ≤ Lauf, Deckel ≈ 600 s (2 Takte).
3. **Keine Python-Zeitgrenze im Radarpfad** — hängendes INCA (180 s je Abruf, bis 6 Punkte/Trip) kann das kleinere Budget sprengen; nach Deckel paralleler Python-Lauf für denselben Nutzer möglich.
4. **Laufzählende Schwellen** bedeuten bei 5-Min-Takt andere Echtzeit (hoher MQ-Alarm nach 15 statt 45 Min) — bewusst festlegen.
5. **Cache-TTL = Takt (300 s):** je nach Abfragezeitpunkt 5 oder 10 Min Datenalter — TTL senken (z. B. 240 s) oder bewusst festlegen.
6. **Open-Meteo-Budget:** Radar-Anteil ×3; Drossel 80 % früher erreicht, Abweichungsalarme rücken an 95 %.
7. **Nebenwirkungen ×3:** `alert_log._append` (ganze Datei, ohne Sperre), `alert_input_capture` (50 Dateien ⇒ Diagnosefenster ⅓), Sperrzeit-Überholung (#2065) und Tageslimit-Durchbruch bekommen mehr Gelegenheiten.
8. **Externes Monitoring** (`check-gregor20.sh`, eigenes Repo, sofort live) braucht Radar-eigene Schwelle (~10 Min).
9. Toter Code `alertBudgetJobIDs` — beim Umbau entweder nutzen oder entfernen.

## Analysis

### Type
Feature (Verkürzung der Radar-Alarm-Verzögerung, PO-Entscheid 03.10.)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `internal/scheduler/scheduler.go` | MODIFY | Cron beider Radar-Jobs `7,22,37,52` → `3-58/5`; neue Felder `radarWaitBudget`/`radarRunBudget`/`radarCallCap` + Defaults; `budgetsFor` dritter Zweig (Switch über Jobfamilie); toten `alertBudgetJobIDs` entfernen; Log-Text „9 cron entries" bleibt |
| `src/services/trip_alert.py` | MODIFY | `RADAR_RUN_DEADLINE_SECONDS` in `check_radar_alerts` (:1820ff), geprüft **vor jedem `get_nowcast`-Abruf** (nicht nur zwischen Trips) |
| `src/services/compare_radar_alert.py` | MODIFY | dieselbe Deadline, vor jedem Abruf |
| `src/services/radar_cache.py` | MODIFY | TTL 300 → 240 s (:68, :127-131), Docstring „15-Min-Takt" korrigieren |
| `internal/scheduler/radar_cron_offset_test.go` | MODIFY | statt „Startminute == 7": Startminute mod 5 ≠ 0, Abstand 5 Min; Gegenprobe :75-100 bleibt |
| `internal/scheduler/user_call_wait_budget_test.go` | MODIFY | `TestBudgetDefaults_MatchSpec` um Radar-Werte erweitern; Alarm-Werte 300/720/1800 bleiben |
| `internal/scheduler/` neuer Test | CREATE | Radar-Budgetzweig + Überlappungsinvariante aus dem echten Cron-Abstand abgeleitet (Laufbudget + Nacharbeit < Takt) |
| `tests/tdd/` neue Tests | CREATE | Python-Deadline im Radarpfad (Trip + Ortsvergleich); TTL < Takt; Drosselung: drei Läufe hintereinander auf identischen Daten ⇒ höchstens eine Meldung |
| `tests/tdd/test_radar_onset_threshold_variance.py` | MODIFY | Kommentar `7,22,37,52` |
| `/home/hem/henemm-infra/scripts/check-gregor20.sh` | MODIFY | eigene Radar-Schwelle 10–12 Min (Rest bleibt 20) — **strikt nach Prod-Selftest**, siehe unten |
| `docs/adr/` | CREATE | Nachfolge-/Ergänzungs-ADR zu 0070 (Budget je Alarmart, Ungleichungskette) |
| `docs/reference/decision_matrix.md`, `docs/specs/modules/fix_2149_scheduler_budget_teilb.md`, `docs/features/architecture.md` | MODIFY | Takt/Budget-Tabelle nachziehen |

Unberührt (keine 15-Min-Annahme gefunden): Frontend, `api/routers/scheduler.py` (Status liefert dynamisches `next_run`).

### Scope Assessment
- Dateien: ~6 produktiv (Go 1, Python 3, infra 1) + Tests + Doku/ADR
- Geschätzte produktive LoC: +90 bis +110 / −15 (Limit 250)
- Risk Level: MEDIUM — kleine Änderung, aber das Zeitverhalten zweier Prod-Alarmjobs ändert sich; Rückbau über Cron-Ausdruck trivial.

### Technical Approach

**Zielrechnung (dieselbe Formel wie die 32-Min-Ist-Rechnung: Takt + Cache-Datenalter + Laufbudget):**
5 Min + 4 Min (TTL 240 s) + 4,5 Min (Laufbudget 270 s) ≈ **13,5 Min** (Ziel ≈ 15 Min erfüllt). Wie oft die Quelle selbst neue Daten liefert (RADOLAN 5 Min; INCA, AROME-FR, Open-Meteo je 15 Min) ist ein **separater Term außerhalb dieser Rechnung** — für Gebiete mit 15-Min-Quellen sinkt der Gewinn entsprechend; nur Information, keine Entscheidungsfrage.

**Ungleichungskette (bindend, wird Test + ADR):**
- `Deadline + max. Einzelabruf ≤ Wartebudget ≤ Laufbudget`
- `Laufbudget + Nacharbeit (~10 s) < Takt (300 s)`
- `Cache-TTL < Takt − Start-Jitter` (sonst bedient der Lauf bei t=300 die Daten von t=0 ⇒ effektiv nur jeder zweite Lauf frisch, S2 wirkungslos)
- max. Einzelabruf = 180 s (INCA-Retries, `geosphere.py:56-67`, A-1/S3-Thema, nicht hier ändern)

**Werte:** Deadline 60 s · Wartebudget 240 s · Laufbudget 270 s · Deckel (`radarCallCap`) 600 s = 2 Takte · TTL 240 s.
Prüfung: 60+180 = 240 ≤ 240 ≤ 270; 270+10 = 280 < 300; 240 < 300. Messwerte Prod (p99 10 s, max 33 s) passen in 60 s Deadline. Keine Restlücke ⇒ keine Ausnahme zu ADR-0038 nötig. `alert_checks` und die */15-Compare-Jobs behalten 300/720/1800 (Python-Grenze 180 s < 300 s).

**Cron `3-58/5 * * * *`:** kollidiert nie mit den */5- und */15-Jobs (0 mod 5) und nicht mit `briefing_dispatch` (:00), 3 Min Abstand zu :00/:30, verlässt hh:07.

**Befund hh:07-Fehler (geprüft 05.10., Journal `gregor-python`, 10 Tage):** 109 × HTTP 503 von **Open-Meteo minutely_15** (letztes Glied der Radar-Quellenkette), davon 108 um hh:07, 1 um hh:37. Sie werden in `radar_service` als WARNING abgefangen; der Radar-Endpunkt antwortet trotzdem 200 ⇒ **kein Go-Failure, kein Einfluss auf `failureAlertThreshold`/MQ**. `gregor-api`-Journal: 0 Radar-503. Ursache liegt beim Anbieter (vermutlich stündliches Update-Fenster); ob es auch :03/:08/:13 trifft, ist unbekannt ⇒ nach Deploy beobachten (Zählung pro Minute), kein Blocker.

**Laufzählende Schwellen 3/8:** belassen (global in `user_run_state.go:27-28`). Folge: Radar-MQ-Alarm nach 15 statt 45 Min, Teilausfall nach 40 statt 120 Min — schnellere Störmeldung ist für einen Latenz-Ticket gewollt; da Open-Meteo-503 nicht als Failure zählt, kein stündlicher Fehlalarm zu erwarten. Bewusst in Spec/ADR festhalten.

**Open-Meteo-Tagesbudget:** Nur der Open-Meteo-Fallback am Kettenende zählt (`radar_service.py` ~967-990, `allow`/`record_call` unmittelbar vor echtem Fetch; Cache-Treffer zählen nicht). Anteil ×3 möglich; nicht gemessen ⇒ `forecast_budget.json` vor/nach Deploy vergleichen. Drossel 80 % / 95 % bleiben Sicherung.

**Mehrfachmeldungen:** Sperrzeit + Dringlichkeits-Überholung (`alert_gate.py:402-472`, #2065) und Tageslimit (`alert_daily_limit.py`) bekommen ×3 Gelegenheiten ⇒ Pflichttest auf Gate-Ebene (drei Läufe, identische Daten).

**Externes Monitoring — Reihenfolge PFLICHT:** `check-gregor20.sh`-Arbeitsbaum ist sofort live. Eine 10-Min-Schwelle vor dem Prod-Deploy schlägt beim alten 15-Min-Takt sofort falsch an ⇒ Umstellung **strikt nach `prod_selftest.py` Exit 0**, als eigener Schritt in `/70-deploy`; diese Session ändert und committet in `henemm-infra` selbst.

### Dependencies
- Upstream: Python-Radarendpunkte (`api/routers/scheduler.py:97-114`), Radar-Quellenkette, `radar_cache`, `ForecastBudgetGate`.
- Downstream: `/api/scheduler/status` (overlap/users), MQ-Schwellen, `check-gregor20.sh`, ADR-0070/0038, S4-Spec `alarm_latenz_zusage.md` (übernimmt später die Ungleichungskette als Wächter).

### Nicht in S2
A-1-Konstanten/INCA-Härtung (S3) · Feed-TTL amtliche Warnungen (S3) · Latenz-Zusage + Wächter (S4) · 5-Min-Takt für `alert_checks`/Compare-Abweichung · Je-Job-Schwellen · `alert_log`-Sperre / `alert_input_capture`-Rotation (nur bei Volumenproblem) · Ursachenklärung Open-Meteo-503.

### Open Questions
- [ ] (Beobachtung nach Deploy, kein Blocker) Trifft das Open-Meteo-503-Fenster auch :03/:08/:13? Zählung pro Minute 7 Tage nach Deploy.
- [ ] (Beobachtung nach Deploy) Open-Meteo-Tagesbudget-Verbrauch vor/nach.
