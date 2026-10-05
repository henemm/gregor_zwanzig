---
entity_id: feat_2261_a2s2_radar_takt
type: module
created: 2026-10-05
updated: 2026-10-05
status: draft
version: "1.0"
tags: [alerts, scheduler, radar, latency, epic-2261, go-api, python-core]
---

# Radar-Alarm-Prüfläufe im 5-Minuten-Takt mit je Alarmart gebundenem Laufbudget (Epic #2261, A-2 S2)

## Approval

- [ ] Approved

## Purpose

Die zwei Radar-Alarm-Prüfläufe (Trip-Radar `radar_alert_checks`, Ortsvergleich-Radar `compare_radar_alert_checks`) laufen heute alle 15 Minuten; ein Regenbeginn wird dadurch im Schnitt erst rund 32 Minuten nach der Quelle gemeldet (Takt 15 + Datenalter bis 5 + Verarbeitung/Laufbudget 12). PO-Entscheid 03.10.: Radar-Verzögerung verkürzen, Ziel rund 15 Minuten. Diese Spec stellt beide Radar-Jobs auf einen 5-Minuten-Takt, bindet Warte-/Lauf-Budget und Zeitgrenze je Alarmart an den eigenen Takt (ADR-0038: Python-Grenze unter Go-Wartezeit, dazu Überlappungsinvariante) und stellt sicher, dass bei einer greifenden Zeitgrenze kein Trip und kein Ortsvergleich dauerhaft verhungert (Wiederverwendung des Mechanismus aus A-2 S1).

Beleg: Issue #2261 (Scheibe A-2 S2), Analyse `docs/context/feat-2261-a2s2-radar-takt.md`; Prod-Journal 7 Tage, 670 Ticks, 3 Nutzer: Trip-Radar-Antwort p90 ca. 1 s, p99 ca. 10 s, Maximum 33 s; Ortsvergleich-Radar ca. 0 s; 30 Tage ohne Budget-/Überlappungsereignis beim Radar.

## Source

- **Go:** `internal/scheduler/scheduler.go` — Cron-Einträge Z. 267/270, Budget-Felder Z. 153-155/232-234, `budgetsFor` Z. 399-404, toter `alertBudgetJobIDs` Z. 190-198
- **Python:** `src/services/radar_service.py` (`RadarService.get_nowcast`, `_fetch_frames_with_fallback`, neu `RadarDeadlineExceeded`), `src/services/trip_alert.py` (`check_radar_alerts`, neu `RADAR_RUN_DEADLINE_SECONDS`), `src/services/compare_radar_alert.py` (`check_all_compare_presets`, `_detect_triggered_locations`), `src/services/radar_cache.py` (TTL), `src/services/alert_check_state.py` (Stempel-Store, Dateiname parametrierbar, gemeinsamer Sortier-Helfer), `api/routers/scheduler.py` (zwei Radar-Endpunkte)
- **Extern (eigenes Repo, sofort live):** `/home/hem/henemm-infra/scripts/check-gregor20.sh` Z. 855-902

Schichten: Go-API **und** Python-Core. Frontend unberührt (Statusanzeige liest dynamisches `next_run`, keine 15-Min-Annahme gefunden).

## Estimated Scope

- **LoC (produktiv, Limit 250):** ca. +165 bis +195 / −15. Aufteilung: Go ca. +30/−15; `radar_service.py` ca. +25; `trip_alert.py` ca. +45; `compare_radar_alert.py` ca. +35; `alert_check_state.py` ca. +20; `scheduler.py` (Router) ca. +15; `radar_cache.py` ±4; `check-gregor20.sh` ca. +10. Tests, Spec, ADR, Doku zählen nicht. Bleibt die Umsetzung über 230 produktive Zeilen, ist die Zeitgrenze im Ortsvergleich-Radar der erste Kandidat zum Vereinfachen (gemeinsamer Helfer statt eigener Schleife), nicht Scope-Streichung.
- **Files produktiv:** 9 (Go 1, Python 6, Shell 1, plus ADR/Doku-Dateien)
- **Effort:** medium; Risiko MEDIUM (Zeitverhalten zweier Prod-Alarmjobs ändert sich; Rückbau über Cron-Ausdruck trivial)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `AlertCheckStateStore` / `alert_check_state.py` (A-2 S1) | Modul | Persistierte „zuletzt erreicht"-Stempel; hier mit eigenem Dateinamen je Radar-Art wiederverwendet, nicht neu gebaut |
| `AlertCheckRunResult` (`trip_alert.py:168-183`) | Dataclass | Rückgabe mit `checked`/`skipped`/`skipped_ids`/`hit_deadline` — für beide Radar-Läufe wiederverwendet |
| `check_nowcast_gate` / `alert_gate.py`, `alert_daily_limit.py` | Module | Sperrzeit, Dringlichkeits-Überholung (#2065), Tageslimit — Wächter gegen Mehrfachmeldungen bei ×3 Läufen |
| `ForecastBudgetGate` (`forecast_budget.py`) | Modul | Open-Meteo-Tagesbudget 9000; Radar (`polling`) gedrosselt ab 80 %, Abweichung ab 95 % |
| `internal/scheduler/user_run_state.go` | Go-Modul | Laufzählende Schwellen `failureAlertThreshold=3`, `partialAlertThreshold=8` (unverändert, Echtzeit ändert sich) |
| `internal/scheduler/user_call_budget.go` | Go-Modul | Deckel je Nutzeraufruf (`callCap`) |
| `providers/geosphere.py:67` `FETCH_DEADLINE_SECONDS=180` | Konstante | Obergrenze des längsten Einzelquellenschritts (INCA) |
| ADR-0038, ADR-0070 | Entscheidungen | Python-Grenze strikt unter Go-Wartezeit; Go wartet nicht weiter, Python läuft fertig |
| ADR-0082 (neu, durch diese Scheibe) | Entscheidung | Budget und Ungleichungskette je Alarmart (Ergänzung zu 0070) |
| `/home/hem/henemm-infra/scripts/check-gregor20.sh` | Skript | Externes Monitoring, braucht Radar-eigene Altersschwelle |

## Implementation Details

### 1. Verifizierte Ausgangslage Quellenkette (Code geprüft 05.10.)

`RadarService.get_nowcast` (`radar_service.py:509`) ruft bei Cache-Fehltreffer `_fetch_frames_with_fallback` (`:792-827`): BrightSky → INCA → AROME-FR (Korsika) → ARPAE → AROME-HD → ICON-D2 → Open-Meteo minutely_15. Die Kette hat **keine Gesamtgrenze**. Zeitverbrauch je Quellenschritt:

- BrightSky: Provider-httpx 8 s + Konvektions-Sidecar (Open-Meteo, `HTTPX_TIMEOUT=8` s, `radar_service.py:178/991`) = ca. 16 s
- **INCA: `GeoSphereProvider.fetch_nowcast` bis `FETCH_DEADLINE_SECONDS=180 s` (`geosphere.py:67`) + Sidecar 8 s = 188 s — der längste Einzelschritt**
- Korsika: zwei Open-Meteo-Aufrufe = 16 s; ARPAE/AROME-HD/ICON-D2/minutely_15: je 8 s

Das Radar-Open-Meteo läuft über den eigenen `httpx`-Client in `_fetch_openmeteo_15` (8 s), **nicht** über `providers/openmeteo.py` (60 s); die Provider `meteofrance.py`/`dwd.py` (180 s) liegen nicht in der Radar-Kette. Die Analyse-Annahme „ein `get_nowcast` ist ein Einzelabruf ≤ 180 s" war falsch: ein `get_nowcast` kann bis zur Summe der durchlaufenen Quellen dauern (Worst Case alle Schritte hintereinander mehrere hundert Sekunden). Deshalb reicht die Zeitgrenze **in** die Kette hinein.

### 2. Zeitgrenze in der Quellenkette (minimal-invasiv)

- `get_nowcast(..., deadline_at: Optional[float] = None)` — absolute `time.monotonic()`-Marke; **Default `None` = Verhalten byte-identisch unverändert** für alle anderen Aufrufer (Briefing, `/jetzt`, Compare-Briefing).
- `_fetch_frames_with_fallback(..., deadline_at)` prüft **vor jeder Quelle**, auch vor der ersten: `time.monotonic() >= deadline_at` ⇒ `RadarDeadlineExceeded` (neue Exception in `radar_service.py`), keine weitere Quelle wird begonnen. Eine bereits laufende Quelle wird nicht abgebrochen (kein Thread-Kill). Worst Case ist damit **Deadline + ein Einzelschritt** (188 s).
- Cache-Treffer kosten nichts und werden nicht geprüft; ein bei Ablauf der Grenze bereits begonnener Cache-Miss-Pfad schreibt nur verwertbare Frames (`if frames:`), eine abgebrochene Kette schreibt nichts in den Cache.
- Eine nach dem **letzten** Quellenschritt abgelaufene Grenze löst keine Exception aus (kein Schritt mehr offen); das normale `data_unavailable`-Ergebnis bleibt.

### 3. Zeitgrenze und Übersprungene im Trip-Radar und Ortsvergleich-Radar (Teilungs-Invariante)

Beide Pfade nutzen **denselben** Baustein, kein Compare-Eigenbau:

- `RADAR_RUN_DEADLINE_SECONDS = 45.0` einmal in `trip_alert.py` definiert, `compare_radar_alert.py` importiert sie (Dokumentierte Invariante am Konstantenort: Ungleichungskette aus Abschnitt 5).
- Je Lauf `deadline_at = monotonic() + 45`. Geprüft **vor jeder Einheit** (Trip bzw. Ortsvergleich-Preset) **und** über den `deadline_at`-Parameter in der Quellenkette (Abschnitt 2), also vor jedem Nowcast-Abruf eines Zonenpunkts bzw. Orts.
- Reihenfolge je Lauf: „zuletzt erreicht" aufsteigend, fehlender Stempel = ältester, ID als Tie-Break — **derselbe Mechanismus wie S1** (`AlertCheckStateStore`, Max-Merge, Prune, fail-open). Dazu erhält der Store einen optionalen Parameter `filename` (Default `alert_last_checked.json` = S1 unverändert) und der Sortier-Helfer wird einmal in `alert_check_state.py` abgelegt. **Eigene Dateien je Alarmart** (`alert_last_checked_radar.json` je Trip, `alert_last_checked_compare_radar.json` je Preset), weil sich die Läufe sonst gegenseitig die Reihenfolge verschieben würden (ein Radar-Lauf alle 5 Min würde den 15-Min-Abweichungslauf als „frisch erreicht" stempeln).
- Stempel wie in S1 für jede **erreichte** Einheit (auch bei `continue`/Exception), geschrieben einmal im `finally`. Eine Einheit, deren Kette mit `RadarDeadlineExceeded` abbricht, gilt als **nicht erreicht**: kein Stempel, ID in `skipped_ids`.
- Abbruch einer Einheit durch `RadarDeadlineExceeded` (auch mitten in den Zonenpunkten eines Trips): **keine** Auswertung mit Teildaten (kein falsches „trocken"), **kein** `data_unavailable`-/Quellenausfall-Protokolleintrag, **kein** Throttle-/Tageslimit-Verbrauch, kein Alarm. Die Ausnahme wird vor dem bestehenden breiten `except Exception` abgefangen.
- Rückgabe: `check_radar_alerts()` und `check_all_compare_presets()` behalten ihren Rückgabetyp `int` (Bestandstests/-aufrufer). Neu je eine Methode `check_radar_alerts_run()` bzw. `check_all_compare_presets_run()` mit `AlertCheckRunResult`; der `int`-Aufruf ist ein Einzeiler darüber.
- Endpunkte `/api/scheduler/radar-alert-checks` und `/compare-radar-alert-checks` antworten wie S1: bisherige Felder (`status`, `count`) bleiben, zusätzlich `checked`, `skipped`, `skipped_ids`, `duration_s`; bei Grenzabbruch `status: "partial"` + `reason: "deadline"`, sonst `"ok"`. Go dekodiert additiv (kein `DisallowUnknownFields`).
- Beobachtbare Spur: WARNING mit den übersprungenen IDs (Muster `trip_alert.py:1170-1172`) plus Antwortfeld `skipped_ids`.

### 4. Go-Scheduler: Cron, Budget je Alarmart

- Cron beider Radar-Jobs `3-58/5 * * * *` (Startminuten 3, 8, 13 … 58). Kollidiert nie mit den `*/5`-Jobs (Minute ≡ 0 mod 5) und `*/15`-Jobs, nicht mit `briefing_dispatch` (:00); verlässt die Minute :07, auf der 108 von 109 Open-Meteo-503 in 10 Tagen lagen. Die #1628-Offset-Begründung (Lastspitze :00/:30) gilt weiter: 3 Minuten Abstand. Jobnamen/Anzeigetexte: „Radar Alert Checks (every 5 min, offset 3)".
- Neue Felder `radarWaitBudget = 240 s`, `radarRunBudget = 270 s`, `radarCallCap = 600 s` im Scheduler; `budgetsFor` erhält einen Zweig für die Radar-Job-IDs (`radar_alert_checks`, `compare_radar_alert_checks`). Alle anderen Alarm-Jobs behalten **300/720/1800** (ihre Python-Grenze `ALERT_RUN_DEADLINE_SECONDS=180` braucht Wartebudget ≥ 300), Briefing 600/1440/0.
- Der bisher ungenutzte `alertBudgetJobIDs` (Z. 190-198, nirgends gelesen) wird ersatzlos entfernt; die neue Radar-ID-Menge ist **benutzt** (von `budgetsFor`).
- Laufzählende Schwellen (3/8) bleiben unverändert (Abschnitt 6).

### 5. Zahlenwerte und Ungleichungskette (bindend; Test + ADR-0082)

Takt T = 300 s. Zeitgrenze D = 45 s. Max. Einzelquellenschritt E = 188 s (INCA 180 + Sidecar 8). Wartebudget W = 240 s, Laufbudget R = 270 s, Deckel C = 600 s, Nacharbeit N = 10 s, Cache-TTL = 240 s.

1. D + E = 45 + 188 = **233 < 240 = W** (Puffer 7 s; ADR-0038: Python-Grenze strikt unter Go-Wartezeit, kein Null-Puffer)
2. W = 240 ≤ **270 = R**
3. R + N = 270 + 10 = **280 < 300 = T** (Puffer 20 s; Überlappungsinvariante, sonst überspringt `recordRun` per TryLock den Folgetick)
4. C = **600 = 2 × T** (Deckel wie bei den Alarmjobs „zwei Takte")
5. TTL = **240 ≤ T − D = 255**, damit ein im Lauf N geholter Eintrag im Lauf N+1 nicht älter als TTL ausgeliefert wird und jeder Lauf frische Daten bekommt (sonst bedient jeder zweite Lauf Altdaten und S2 ist wirkungslos)

Prod-Messwerte (p99 10 s, Maximum 33 s) liegen unter der Zeitgrenze von 45 s: im Normalbetrieb greift sie nie, sie schützt nur im Störfall. Keine Ausnahme zu ADR-0038 nötig (keine Restlücke).

Erwartete Verzögerung (Formel Takt + Datenalter + Laufbudget): schlechtester Fall 5 + 4 + 4,5 = **13,5 Min** (Ziel ≈ 15 Min erfüllt; Ist 32 Min); typisch (p99-Laufzeit 10 s) 5 + 4 + 0,2 ≈ 9-10 Min. Wie oft die Quelle selbst neue Daten liefert (RADOLAN 5 Min; INCA, AROME-FR, Open-Meteo je 15 Min) ist ein separater Term außerhalb dieser Rechnung; für 15-Min-Quellen sinkt der Gewinn entsprechend (Information, keine Entscheidungsfrage).

### 6. Laufzählende Schwellen — Echtzeit ändert sich (PO-sichtbar)

`failureAlertThreshold = 3` und `partialAlertThreshold = 8` zählen **Läufe** (`user_run_state.go:27-28`, `:185-204`; `partial` und `not_reached` zählen auf den Teilerfolgs-Zähler, `budget`/`skipped_in_flight` auf den Fehler-Zähler). Bei 5 statt 15 Minuten Takt bedeutet das: Radar-Störmeldung per MQ nach **3 × 5 = 15 statt 45 Minuten**, Teilausfall-Meldung nach **8 × 5 = 40 statt 120 Minuten**. Bewusst belassen: schnellere Störmeldung passt zu einem Latenz-Ticket; Open-Meteo-503 im Radar-Endpunkt werden als WARNING abgefangen, der Endpunkt antwortet 200, zählt also nicht als Failure (Journal 05.10.: 0 Radar-503 im `gregor-api`-Log) — kein stündlicher Fehlalarm zu erwarten. Je-Job-Schwellen sind nicht Teil dieser Scheibe.

### 7. Cache-TTL

`radar_cache.py`: Default-TTL 300 → 240 s (Konstruktor `:68` und `get_shared_radar_cache` `:127`); Docstring „15-Minuten-Alarmtakt" auf 5 Min korrigiert.

### 8. Externes Monitoring (Deploy-Schritt, strikte Reihenfolge)

`check-gregor20.sh` Abschnitt 2e: neue Radar-eigene Altersschwelle `RADAR_JOB_MAX_AGE_MIN=12` für `radar_alert_checks` und `compare_radar_alert_checks` (Herleitung: Takt 5 Min + größter Abstand zweier Läufe durch Laufbudget 4,5 Min = 9,5 Min + Reserve ≈ 12), die drei übrigen Alarmjobs bleiben bei 20; Textausgabe „Takt 15 Min" wird je Job korrekt (5 bzw. 15). Der Arbeitsbaum ist **sofort live**: eine 12-Min-Schwelle vor dem Prod-Deploy würde beim alten 15-Min-Takt sofort falsch anschlagen. **Umstellung deshalb strikt nach `python3 .claude/hooks/prod_selftest.py` Exit 0**, als eigener Schritt in `/70-deploy`; diese Session ändert und committet in `henemm-infra` selbst (Infrastruktur-Änderung gehört dorthin).

### 9. Nebenwirkungen ×3 (nur beobachtet, nicht geändert)

`alert_log._append` (ganze Datei, ohne Sperre), `alert_input_capture` (50 Dateien ⇒ Diagnosefenster ⅓), Sperrzeit-Überholung (#2065), Tageslimit-Durchbruch und Open-Meteo-Tagesbudget (Radar-Anteil ×3 möglich; Drossel 80 %/95 % bleiben Sicherung) bekommen mehr Gelegenheiten. Schutz gegen Mehrfachmeldung ist Pflichttest AC-11.

## Expected Behavior

- **Input:** Go-Scheduler ruft alle 5 Minuten (Minute 3 mod 5) je Nutzer `POST /api/scheduler/radar-alert-checks?user_id=…` und `…/compare-radar-alert-checks?user_id=…` mit Wartebudget 240 s, Laufbudget 270 s über alle Nutzer, Deckel 600 s.
- **Output:** Antwort `{status, count, checked, skipped, skipped_ids, duration_s[, reason]}`; Alarme wie bisher über die geteilte Kanal-Auflösung (alle vier Kanäle, ADR/CLAUDE.md), nur früher.
- **Side effects:** Schreibt je Nutzer `alert_last_checked_radar.json` und `alert_last_checked_compare_radar.json` (nur diesen Nutzer); WARNING mit übersprungenen IDs bei Grenzabbruch; Radar-MQ-Störmeldungen nach 15/40 Minuten statt 45/120.

## Acceptance Criteria

- **AC-1:** Given der Scheduler mit seinen echten Cron-Einträgen / When die nächsten Auslösezeiten von `radar_alert_checks` und `compare_radar_alert_checks` aus dem Cron-Ausdruck berechnet werden / Then liegen je zwei aufeinanderfolgende Auslösungen genau 5 Minuten auseinander, die Startminute ist nicht durch 5 teilbar (kein Zusammenfallen mit den `*/5`-, `*/15`-Jobs und `briefing_dispatch`) und die Zahl der Cron-Einträge (9) sowie der Jobs (10) bleibt unverändert.
  - Test (Go, `radar_cron_offset_test.go` angepasst): echter Cron-Parser statt Textvergleich; Rückmutation auf `7,22,37,52` oder `*/5` wird rot; die Gegenprobe „andere Jobs bleiben `*/15`" bleibt.

- **AC-2:** Given ein neu erzeugter Scheduler / When `budgetsFor` für `radar_alert_checks` und `compare_radar_alert_checks` gefragt wird / Then liefert es Wartebudget 240 s, Laufbudget 270 s, Deckel 600 s, und für `alert_checks`, `compare_alert_checks`, `compare_official_alert_checks` weiterhin 300/720/1800 sowie für die Briefing-Teiljobs 600/1440/0.
  - Test (Go, `TestBudgetDefaults_MatchSpec` erweitert + neuer Test `radar_budget_per_alarmart_test.go`): jede Vermischung (Radar bekommt Alarm-Werte oder umgekehrt) wird rot.

- **AC-3:** Given die Zahlenwerte aus Abschnitt 5 / When die Ungleichungskette aus den **echten** Konstanten ausgewertet wird / Then gilt: Zeitgrenze + längster Einzelschritt < Wartebudget ≤ Laufbudget; Laufbudget + 10 s Nacharbeit < Takt (Takt aus dem echten Cron-Abstand abgeleitet); Deckel = 2 × Takt; Cache-TTL ≤ Takt − Zeitgrenze.
  - Test (zweiseitig verankert): Go-Test prüft Wait ≤ Run, Run + 10 s < Cron-Abstand, Cap = 2 × Abstand; Python-Test `test_radar_zeitgrenze_unter_go_wartebudget` prüft `RADAR_RUN_DEADLINE_SECONDS + (geosphere.FETCH_DEADLINE_SECONDS + radar_service.HTTPX_TIMEOUT) < 240` und `get_shared_radar_cache`-TTL `<= 300 - Deadline`; eine Änderung einer Seite ohne die andere wird rot.

- **AC-4:** Given eine echte `RadarService`-Instanz, deren Quellenschritte real Zeit verbrauchen (gemessene Schlafzeit je Schritt, Zeitgrenze klein gesetzt), die Koordinate liegt in mehreren Quellenbereichen und die erste Quelle liefert nichts / When `get_nowcast` mit `deadline_at` aufgerufen wird und die Grenze nach der ersten Quelle abgelaufen ist / Then beginnt keine weitere Quelle (Aufrufzähler der Folgequellen bleibt 0), `RadarDeadlineExceeded` wird ausgelöst und es wird nichts in den Cache geschrieben; ohne `deadline_at` werden dieselben Quellen wie bisher der Reihe nach versucht.
  - Test: `test_radar_kette_prueft_grenze_vor_jeder_quelle`; Prüfung nur vor `get_nowcast` (statt vor jeder Quelle) lässt die Folgequellen laufen ⇒ rot; Default-Gegenprobe verhindert eine geänderte Kette für Briefing & Co.

- **AC-5:** Given ein Nutzer mit N Trips, deren Radar-Prüfung je real Zeit braucht, und eine Zeitgrenze, die je Lauf nur k < N zulässt / When zwei Läufe von `check_radar_alerts_run` nacheinander laufen / Then beginnt der zweite Lauf mit genau den vom ersten übersprungenen Trips, die Vereinigung der erreichten Trips ist gleich allen N, `skipped_ids` des ersten Laufs nennt die nicht erreichten Trips in Prüfreihenfolge (`len == skipped`), und ein nicht erreichter Trip erhält keinen neuen Stempel.
  - Test: `test_trip_radar_zwei_laeufe_decken_alle_trips_ab`; Rückmutation auf ID-Reihenfolge lässt dieselben Trips erneut verhungern ⇒ rot.

- **AC-6:** Given einen Nutzer mit mehreren Ortsvergleichen mit eingeschaltetem Radar-Alarm unter derselben knappen Zeitgrenze / When zwei Läufe von `check_all_compare_presets_run` nacheinander laufen / Then gilt für Ortsvergleiche dasselbe wie in AC-5 (faire Reihenfolge, `skipped_ids`, Stempel nur für Erreichte), und beide Pfade benutzen denselben Sortier-Helfer und denselben Store (Teilungs-Invariante), ohne eigene Compare-Kopie.
  - Test: `test_compare_radar_zwei_laeufe_decken_alle_presets_ab`; zusätzlich ein Test, dass `alert_last_checked.json` (Abweichungslauf, S1) durch Radar-Läufe weder angelegt noch verändert wird.

- **AC-7:** Given ein Radar-Lauf, der wegen der Zeitgrenze Einheiten auslässt, und ein Lauf, der alle schafft / When Rückgabe, WARNING und Endpunkt-Antworten beider Radar-Endpunkte betrachtet werden / Then enthalten Rückgabe, WARNING-Zeile und Antwort genau die nicht erreichten IDs; beim Grenzabbruch ist `status` „partial" mit `reason` „deadline", beim vollen Lauf „ok" mit leerem `skipped_ids`; `check_radar_alerts()` und `check_all_compare_presets()` liefern weiterhin einen `int`.
  - Test: `test_radar_endpunkte_melden_skipped_ids` über den echten FastAPI-Router mit Log-Capture; fehlendes Feld, fehlende IDs oder geänderter Rückgabetyp werden rot.

- **AC-8:** Given einen Trip, dessen Quellenkette mitten in den Messpunkten der Reststrecke an der Zeitgrenze abbricht / When der Lauf endet / Then entstehen für diesen Trip kein Alarm, kein Eintrag im Alarmprotokoll (weder „Quellenausfall" noch „Daten nicht verfügbar"), keine Buchung auf Sperrzeit oder Tageslimit und kein Stempel; ein Quellenausfall **ohne** Grenzabbruch bleibt wie bisher protokolliert.
  - Test: `test_deadline_abbruch_ist_keine_entwarnung_und_kein_ausfall`; Behandlung als normaler Fehler (`except Exception`) oder Auswertung mit Teildaten wird rot.

- **AC-9:** Given der gemeinsame Radar-Cache / When ein Eintrag 239 s und einer 241 s alt abgefragt wird / Then ist der erste ein Treffer und der zweite ein Fehltreffer (TTL 240 s), und die Standard-TTL des geteilten Caches ist kleiner als der 5-Minuten-Takt.
  - Test: `test_radar_cache_ttl_240_unter_takt` mit injizierter Uhr; Rückmutation auf 300 wird rot.

- **AC-10:** Given die unveränderten Schwellen 3 (Ausfall) und 8 (Teilausfall) und der 5-Minuten-Takt / When die Echtzeit bis zur MQ-Störmeldung aus Schwelle × echtem Cron-Abstand berechnet wird / Then beträgt sie 15 Minuten (Ausfall) bzw. 40 Minuten (Teilausfall), und die Schwellenkonstanten selbst bleiben 3 und 8. **PO-Freigabe: Radar-Störmeldungen kommen damit nach 15 statt 45 bzw. 40 statt 120 Minuten.**
  - Test (Go): `TestRadarSchwellen_EchtzeitAusTaktUndSchwelle`; Änderung einer Schwelle oder des Taktes ohne bewusste Anpassung wird rot und macht die Echtzeitfolge sichtbar.

- **AC-11:** Given identische Wetterdaten mit auslösendem Regenbeginn für einen Trip bzw. einen Ortsvergleich / When drei Radar-Läufe hintereinander laufen (echte Gate-Kette Sperrzeit/Tageslimit, echtes `tmp_path`-Datenverzeichnis) / Then wird insgesamt höchstens eine Meldung versendet, für Trip-Radar und Ortsvergleich-Radar jeweils getrennt geprüft.
  - Test: `test_drei_radar_laeufe_gleiche_daten_hoechstens_eine_meldung`; ein Gate-Durchbruch bei der Sperrzeit (#2065) wird nur mit Zusatzbedingung (Dringlichkeits-Eskalation) erlaubt und ist in der Gegenprobe abgedeckt.

- **AC-12:** Given zwei Nutzer A und B mit je eigenen Trips und Ortsvergleichen (auch gleiche IDs) / When ein Radar-Lauf für A läuft / Then werden nur `data/users/A/alert_last_checked_radar.json` und `…_compare_radar.json` geschrieben, die Dateien von B bleiben byte-identisch oder nicht vorhanden, und unter `data/users/default/` entsteht nichts.
  - Test: `test_radar_zustand_zwei_nutzer_nie_default` (Pflicht-Zwei-Nutzer-Test); Fallback auf `"default"` oder gemeinsamer Pfad wird rot.

- **AC-13:** Given eine kaputte Radar-Zustandsdatei bzw. ein nicht erhältlicher Lock / When ein Radar-Lauf startet / Then werden alle Trips bzw. Ortsvergleiche normal geprüft und Alarme versendet, die Reihenfolge fällt auf die ID-Reihenfolge zurück, eine Warnung steht im Log und keine Exception erreicht den Endpunkt.
  - Test: `test_radar_zustand_fail_open`; Raise oder ausgebliebener Versand wird rot.

- **AC-14:** Given das Deploy dieser Scheibe auf Produktion / When `prod_selftest.py` mit Exit 0 endet und erst danach `check-gregor20.sh` umgestellt wird / Then prüft das Monitoring die beiden Radar-Jobs gegen 12 Minuten und die drei anderen Alarmjobs gegen 20 Minuten: ein vorbereiteter Status mit Radar-Lauf vor 13 Minuten meldet FAIL, ein `alert_checks`-Lauf vor 13 Minuten meldet OK, ein frischer Status meldet OK, und die Textausgabe nennt den richtigen Takt je Job.
  - Test: Skriptabschnitt gegen vorbereitete Status-JSONs (Eingabe über `SCHED_RESPONSE`); vor dem Selftest-Exit 0 wird die Datei in `henemm-infra` **nicht** geändert (Deploy-Reihenfolge, protokolliert im Execution-Log).

- **AC-15:** Given die Spec-/Doku-Fläche / When `tests/test_adr_index_drift.py` und die Doku-Prüfungen laufen / Then existiert `docs/adr/0082-*.md` (Ergänzung zu ADR-0070: Budget je Alarmart, Ungleichungskette aus Abschnitt 5) mit passendem Eintrag in `docs/adr/README.md`, und die Fundstellen `decision_matrix.md` (#1628-Abschnitt), `fix_2149_scheduler_budget_teilb.md` (Budget-Tabelle Radar) und `docs/features/architecture.md` nennen Takt 5 Min und die neuen Budgets.
  - Test: `uv run pytest tests/test_adr_index_drift.py` grün (Index↔Datei-Konsistenz).

## Tests

Neue Testdateien nach Verhalten benannt, kein Mock-Theater (echte Schlafzeiten, echte `tmp_path`-Datenverzeichnisse, echter Router, echter Cron-Parser):

| AC | Datei / Test |
|----|--------------|
| AC-1 | `internal/scheduler/radar_cron_offset_test.go` (angepasst) |
| AC-2 | `internal/scheduler/user_call_wait_budget_test.go` (`TestBudgetDefaults_MatchSpec` erweitert), `internal/scheduler/radar_budget_per_alarmart_test.go` (neu) |
| AC-3 | Go `radar_budget_per_alarmart_test.go` + `tests/tdd/test_radar_alarmlauf_zeitgrenze.py` |
| AC-4 | `tests/tdd/test_radar_alarmlauf_zeitgrenze.py` |
| AC-5, AC-8, AC-13 | `tests/tdd/test_radar_alarmlauf_fairness.py` (Trip) |
| AC-6, AC-12 | `tests/tdd/test_radar_alarmlauf_fairness.py` (Ortsvergleich, Zwei-Nutzer) |
| AC-7 | `tests/tdd/test_radar_alarmlauf_fairness.py` (Router) |
| AC-9 | `tests/tdd/test_radar_cache_ttl_unter_takt.py` |
| AC-10 | `internal/scheduler/radar_schwellen_echtzeit_test.go` (neu) |
| AC-11 | `tests/tdd/test_radar_mehrfachmeldung_gate.py` |
| AC-14 | Deploy-Schritt + Skriptlauf gegen vorbereitete JSONs |
| AC-15 | `tests/test_adr_index_drift.py` |

Anpassung Bestand: `tests/tdd/test_radar_onset_threshold_variance.py` (Kommentar `7,22,37,52`), `user_call_wait_budget_test.go`/`run_budget_rotation_test.go` (~15 Tests setzen die drei Alarm-Felder direkt mit `alert_checks` — bleiben unverändert grün, weil die Radar-Felder getrennt sind), `scheduler_unify_test.go` (9 Einträge / 10 Jobs bleibt). Mutations-Gegenprobe im Adversary: Deadline-Prüfung nur vor `get_nowcast`, TTL 300, Radar-Budget = Alarm-Budget, ID-Sortierung statt Stempel, gemeinsame Stempeldatei mit dem Abweichungslauf, Behandlung von `RadarDeadlineExceeded` als Quellenausfall.

## E2E- und Staging-Plan

- **Messbar auf Staging:** Cron/Takt und Laufzeit über `/api/scheduler/status` (`next_run`/`last_run`, zwei Läufe im Abstand von 5 Minuten); Radar-Endpunkt-Antwort mit `skipped_ids`/`checked` direkt über den Staging-Kern (Port 8001, Header `X-GZ-Core-Auth`; Go-Trigger ist auf Staging Admin-only und Staging hat keinen Admin, 403) mit Wegwerf-Testnutzer, **kein** Sammelversand; HTTP-Smoke `/` 200/302 und `/api/health` 200.
- **Nicht messbar auf Staging (`NOT_MEASURABLE_ON_STAGING`):** Inhalt der Zustandsdateien (Staging-Datenbestand für `hem` nicht lesbar) — im Kern bewiesen (AC-5/6/12/13), nicht als PASS behauptet.
- **Prod-Nachweis nach Deploy (`prod_selftest.py` Exit 0, danach Monitoring-Umstellung):** `last_run` beider Radar-Jobs alle 5 Minuten; kein `overlap.skipped_since_last_run` im Radar; danach beobachtend 7 Tage (siehe Known Limitations).

## Known Limitations

- Ein bei Ablauf der Zeitgrenze bereits laufender Quellenschritt wird nicht abgebrochen: Worst Case Zeitgrenze + 188 s = 233 s (unter Wartebudget 240 s, Puffer 7 s). Hängt INCA länger als seine eigenen 180 s, ist das ein Thema von A-2 S3 (INCA-Härtung), nicht dieser Scheibe.
- Nach Ablauf des 600-s-Deckels ist ein paralleler Python-Lauf desselben Nutzers möglich (ADR-0070); der Max-Merge der Stempel ist dafür harmlos.
- Beobachtung nach Deploy (kein Blocker): trifft das Open-Meteo-503-Fenster (bisher hh:07) auch :03/:08/:13? Zählung pro Minute 7 Tage nach Deploy; Open-Meteo-Tagesbudget (`forecast_budget.json`) vor/nach Deploy vergleichen, Radar-Anteil ×3 möglich, nicht gemessen.
- Wie oft die Quelle selbst neue Daten liefert (RADOLAN 5, INCA/AROME-FR/Open-Meteo 15 Min), begrenzt den Gewinn für Gebiete mit 15-Min-Quellen.
- Hart abgebrochener Prozess (Kill/OOM) verliert den Stempel-Fortschritt dieses Laufs (nur Fairness betroffen).

## Nicht in S2

- A-1-Konstanten und INCA-Härtung (Provider-Retry/Circuit-Breaker) — Scheibe S3
- Feed-TTL amtlicher Warnungen — Scheibe S3
- Latenz-Zusage und Wächter (`alarm_latenz_zusage.md`) — Scheibe S4 (übernimmt die Ungleichungskette als Wächter)
- 5-Minuten-Takt für `alert_checks`, `compare_alert_checks`, `compare_official_alert_checks`
- Je-Job-Schwellen für die laufzählenden MQ-Meldungen
- `alert_log`-Sperre und `alert_input_capture`-Rotation (nur bei nachgewiesenem Volumenproblem)
- Ursachenklärung der Open-Meteo-503 (Anbieterseite)
- Frontend (unberührt), Änderung der Alarmlogik je Trip/Ortsvergleich

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0082 (neu, wird in `/50-implement` geschrieben; Ergänzung zu ADR-0070, bezieht sich auf ADR-0038) mit Eintrag in `docs/adr/README.md` (sonst `tests/test_adr_index_drift.py` rot)
- **Rationale:** ADR-0070 legt Alarm-Budget 300/720/1800 „zwei Takte" für alle Alarmjobs fest. Mit einem 5-Minuten-Takt für die Radar-Jobs braucht jede Alarmart ein eigenes Budget, das an den eigenen Takt gebunden ist. Das ADR hält fest: Budget je Alarmart, die Ungleichungskette (Abschnitt 5) mit ausdrücklichem Puffer (kein Null-Puffer), dass die Zeitgrenze **in** die Quellenkette hineinreicht (nicht nur zwischen Einheiten) und die Wiederverwendung des Fairness-Mechanismus aus A-2 S1. Verworfene Alternativen: ein Budget für alle Jobs (zwingt `alert_checks` auf ≤ 240 s und verletzt dessen Python-Grenze 180 s + Überhang), Takt 3 Minuten (Cache-TTL und Open-Meteo-Budget ohne Gewinn gegenüber Datenquellen-Rhythmus), Zeitgrenze nur vor `get_nowcast` (Worst Case nicht begrenzbar, siehe Abschnitt 1).

## Changelog

- 2026-10-05: Initial spec created (Epic #2261, Scheibe A-2 S2)
