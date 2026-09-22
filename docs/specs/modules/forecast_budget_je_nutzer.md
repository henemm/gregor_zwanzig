---
entity_id: forecast_budget_je_nutzer
type: module
created: 2026-09-20
updated: 2026-09-20
status: draft
version: "1.0"
tags: [multi-user, forecast-budget, fairness, epic-2138]
---

# Forecast Budget je Nutzer

## Approval

- [ ] Approved

## Purpose

`ForecastBudgetGate` zählt ausgelöste Open-Meteo-Abrufe bisher ausschließlich in einem
einzigen, für alle Nutzer geteilten Tagestopf; ein Vielverbraucher drosselt damit auch die
Alarme aller anderen Nutzer. Diese Erweiterung führt zusätzlich einen Zähler je Nutzer ein,
der beim Erreichen einer globalen Schwelle entscheidet, **wen** die Drosselung trifft — den
Vielverbraucher, nicht alle —, während der globale Topf als Kontoschutz gegenüber Open-Meteo
unverändert bestehen bleibt (#2387, Scheibe S1 von #2150, Epic #2138).

## Source

- **File:** `src/services/forecast_budget.py`
- **Identifier:** `ForecastBudgetGate`

Betroffene Schichten:

- **Python-Core** (Hauptänderung): `src/services/forecast_budget.py` sowie vier Aufrufpfade,
  die bislang keine `user_id` bis zur Gate-Instanziierung durchreichen (s. Implementation
  Details).
- **Go-API** (nur Leseseite, keine Logikänderung): `internal/scheduler/forecast_budget_health.go`
  liest weiterhin ausschließlich die unverändert formatierte globale Datei
  `<data_root>/diagnostics/forecast_budget.json` für `/api/scheduler/status`.

## Estimated Scope

- **LoC:** ~320–370 (Kern-Gate ~100–120, vier Signaturänderungen samt Aufrufern ~50–60, Tests
  inkl. Umschreiben des bestehenden 12er-Tests und des Radar-Funnel-Tests sowie Update aller
  Konstruktor-Aufrufe ~160–200, Go optional 0–15 für einen reinen Schutztest ohne
  Strukturwechsel)
- **Files:** ~11 (Kern-Gate, 4 Aufruferdateien mit ihren jeweiligen Callern, 4 Testdateien,
  optional ein Go-Testfile)
- **Effort:** high — **`loc_limit_override` ist vor der Implementierung zu setzen**, das
  250-LoC-Limit wird strukturell gerissen (Kern + 5 Signaturen + Tests + ggf. Go).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| ADR-0003 (Mandantentrennung) | ADR | Bindend: echte `user_id` durchreichen, kein `"default"`-Rückfall; Zwei-Nutzer-Test mit Gegenlesung ist Pflicht |
| ADR-0031 (Dateibasierte Persistenz) | ADR | Bindend: Ablage unter `data/users/<user_id>/…`; Read-Modify-Write mit Merge, nie Replace; Schema-Änderungen brauchen idempotente Migration |
| ADR-0070 (Wartebudget je Nutzeraufruf) | ADR | Präzedenz für „Budget je Nutzer + Gesamtdeckel je Lauf" — dieselbe Fairness-Frage, hier auf das Open-Meteo-Kontingent übertragen |
| ADR-0029 (Open-Meteo als Standard) | ADR | Legt das Kontingent-Modell fest; Folgepflicht, neue Abrufpfade gegen das Kontingent zu denken |
| `src/services/throttle_store.py` (`ThrottleStore`) | Modul | Vorlage für Konstruktor mit Pflicht-`user_id`, Sidecar-Lock-Schreibmechanik, idempotente Migration |
| `src/app/loader.py` (`get_data_dir`, `VALID_USER_ID_RE`) | Modul | Zielverzeichnis je Nutzer und Kennungs-Validierung |
| `internal/scheduler/forecast_budget_health.go` | Modul | Liest die globale Datei für `/api/scheduler/status`; Format der vier bekannten Felder darf sich nicht ändern |
| `src/services/alert_daily_limit.py` | Modul | Muster „Pflicht-Parameter ohne Default = kein stiller Rückfall" |

## Was gezählt wird

Erfasst werden ausschließlich Aufrufe, die durch das Gate laufen: die zwei produktiven
Instanziierungsstellen `segment_weather.py:128-130` und `radar_service.py:509-510` sowie die
vier unten genannten, um `user_id` erweiterten Pfade und der unattributierte Fall #13
(Provider-Schicht).

**NICHT erfasst** (bewusster Scope-Schnitt, wie schon in
`fix_1329_forecast_cache_budget.md:415-422`): `comparison_engine.py`, `forecast.py`,
`trip_forecast.py` — sie umgehen Cache UND Gate vollständig und bleiben in S1 außerhalb.
`openmeteo_calls.jsonl` erfasst den Radar-Pfad ebenfalls nicht; das ist ein separates Log,
unverändert durch S1.

## Implementation Details

```
ForecastBudgetGate(user_id: str, data_dir: Optional[Path] = None)
  - user_id ist PFLICHT-Parameter ohne Default (Muster ThrottleStore.__init__).
  - Globaler Pfad bleibt unverändert: <data_root>/diagnostics/forecast_budget.json
    (E1 -- Kontoschutz bleibt bestehen, Go-Leser bleibt funktionsfähig).
  - Neuer Nutzer-Pfad: data/users/<user_id>/diagnostics/forecast_budget.json
    über loader.get_data_dir(user_id), Kennung gegen VALID_USER_ID_RE geprüft.
  - Format je Nutzer-Datei: {"date": "...", "calls": {"openmeteo": N}} -- schlanker
    als die globale Datei, da cache_hits/cache_misses für die Fairness-Berechnung
    nicht gebraucht werden.

E6 -- Konstanten bleiben unangetastet:
  - DAILY_BUDGET, POLLING_THRESHOLD, BRIEFING_ONLY_THRESHOLD bleiben WÖRTLICH an
    forecast_budget.py:40-42 stehen -- nicht umbenannt, nicht verschoben, nicht in
    eine andere Datei gezogen. Grund: TestForecastBudgetConstantsMatchPython
    (forecast_budget_health_test.go:256) liest den Python-Quelltext zur Laufzeit
    und wird rot, sobald eine Konstante wandert. Der neue Wert "fairer Anteil"
    (DAILY_BUDGET / N) wird zur LAUFZEIT aus den bestehenden Konstanten
    abgeleitet und lebt als eigene Methode/Property NEBEN ihnen, nie anstelle.

record_call():
  - Schreibt wie bisher gegen die globale Datei (_safe_update, Sidecar-Lock <datei>.lock).
  - Schreibt zusätzlich, mit EIGENEM Sidecar-Lock, gegen den Nutzer-Topf (weniger
    Contention als ein gemeinsames Lock, Muster throttle_store.py:197-245).
  - Trägt user_id zusätzlich in ein Set "aktiver Nutzer des Tages" in der globalen
    Datei ein (neues Feld "active_users": [...]). Das Feld unterliegt DEMSELBEN
    UTC-Tagesreset wie "calls" -- _load_for_today() muss es bei Datumswechsel auf
    eine leere Menge zurücksetzen, sonst trägt N fälschlich die Nutzer des
    Vortags in die Fairness-Berechnung des neuen Tages (AC-5 prüft das explizit
    mit). Das Feld wird vom Go-Struct forecastBudgetFile NICHT deklariert und
    daher beim Unmarshal ignoriert -- keine Strukturänderung für den
    bestehenden Go-Leser nötig (E1-Nebenwirkung, siehe AC-6/AC-9). Dieses Set
    liefert N für die Fairness-Berechnung, ohne bei jedem allow()-Aufruf das
    Nutzerverzeichnis scannen zu müssen.

allow(priority, now=None) -- dreistufig (E2):
  - user_briefing: IMMER True (unverändert, Produktgrundsatz, Stufe-2-fest).
  - Stufe 0: globaler ratio < Schwelle der Priorität (0.80 polling / 0.95
    alert_check) -> True, wie bisher.
  - Stufe 1: Schwelle erreicht, aber globaler ratio < 1.0 -> Nutzer wird NUR
    gedrosselt, wenn sein eigener heutiger Verbrauch (Nutzer-Topf) ÜBER seinem
    fairen Anteil liegt. Fairer Anteil = DAILY_BUDGET / max(N, 1), N = Größe
    des "aktive Nutzer"-Sets aus der globalen Datei. Liegt der Nutzer darunter,
    läuft er weiter -- das ist der Kern von #2387.
  - Stufe 2: globaler ratio >= 1.0 (100% von DAILY_BUDGET) -> jede Priorität
    ausser user_briefing wird gedrosselt, UNABHÄNGIG vom fairen Anteil. Harter
    Kontoschutz, übersteuert Stufe 1 (AC-8).
  - unbekannte Priorität: True (unverändert).

snapshot() -- Erweiterung für Beobachtbarkeit (WICHTIG für AC-2/AC-5/AC-9):
  - Die globale Ausgabe (date/calls_today/daily_budget/usage_ratio/cache_hits/
    cache_misses/status) bleibt UNVERÄNDERT -- das ist die Form, die der
    Go-Leser kennt (auch wenn er sie nicht über snapshot() bezieht, s.u.).
  - ZUSÄTZLICH liefert snapshot() auf einer user-gebundenen Instanz drei neue
    Felder: user_calls_today (Zählerstand des eigenen Nutzer-Topfs),
    fair_share (DAILY_BUDGET / max(N,1) zum Abfragezeitpunkt), und
    active_users_count (N). Das ist die einzige ÖFFENTLICHE Lesequelle für
    Nutzer-Topf-Zustand -- sie ersetzt das direkte Lesen der Nutzer-JSON-Datei
    in Tests, damit AC-2 (Gegenlesung/Positivkontrolle), AC-5 (Tageswechsel)
    und AC-9 (frischer Nutzer-Topf) beobachtbares Verhalten prüfen statt
    Dateiinhalt.
  - KEIN Konflikt mit E5: ForecastBudgetHealth() (forecast_budget_health.go:
    121-127) liest die globale JSON-Datei direkt vom Dateisystem und ruft
    niemals Python's snapshot() auf -- die drei neuen Felder erreichen
    /api/scheduler/status also strukturell nicht. tests/test_success_status_guard.py
    nutzt snapshot() als kanonisches Positivbeispiel und muss additive, neue
    Felder tolerieren (kein Schema-Whitelist-Fail).

Fail-open je Nutzer (E3, bisher nirgends entschieden):
  - Ist der Nutzer-Topf unlesbar (kaputtes JSON, IO-Fehler) oder läuft das
    Nutzer-Lock in den Timeout, gilt der Nutzer-Verbrauch als "0 / nicht
    überschritten" -> allow() bleibt True, WARNING wird geloggt. Ein Lesefehler
    darf nie zur Drosselung führen (konsistent zur bestehenden Fail-open-
    Semantik der Klasse).

Migration:
  - Gewählter Weg: "globalen Bestand stehen lassen, je Nutzer frisch beginnen"
    (Präzedenz track_resolution_health.py:24-28), NICHT die aufwendigere
    Merge-Migration wie bei ThrottleStore. Begründung in einem Satz: es ist ein
    Tageszähler -- ein rückwirkender Split des globalen Zählerstands auf
    einzelne Nutzer wäre ohnehin nur eine Schätzung und der Bestand läuft
    binnen 24h aus; ein sauberer Neubeginn je Nutzer-Topf ist die einfachere,
    gleich korrekte Lösung. Read-Modify-Write mit Merge bleibt trotzdem Pflicht
    für jeden EINZELNEN Schreibvorgang (globale Datei UND Nutzer-Topf je für
    sich), nur der initiale Rückwirkungs-Merge zwischen den beiden entfällt.

Vier Signaturänderungen (echte user_id bis zur Gate-Instanziierung durchreichen,
kein Rückfall auf einen Ersatzwert -- jede Stelle OHNE echte Kennung muss laut
brechen):

  1. trip_command_processor.py:2422 (_show_now, /jetzt-Kommando)
     - user_id liegt eine Ebene höher an msg.user_id (:920) vor; Signatur von
       _show_now (und ggf. der dazwischenliegenden Aufrufkette bis :2422) wird
       um user_id erweitert, statt es aus dem Kontext zu erraten.

  2. compare_location_weather_source.py:174
     - Aufrufer haben die Kennung bereits: compare_alert.py:500,
       scheduler_dispatch_service.py:776. Das berührte Protocol
       point_weather.py:67-84 wird um den Pflicht-Parameter erweitert.

  3. segment_weather.py:533 (fetch_night_weather)
     - Aufrufer haben die Kennung bereits: trip_report_scheduler.py:2293,
       preview_service.py:242.

  4. stage_weather.py:56 (_fetch_one)
     - Aufrufer api/routers/internal.py:77 führt user_id bereits als
       Pflicht-Query-Parameter -- wird nur bis zur Gate-Instanziierung
       durchgereicht.

Fall #13 -- Provider-Schicht (E4, KEINE Signaturänderung):
  - thunder_enrichment.py:255 über src/providers/openmeteo.py:1166/1289/1303
    bucht weiterhin unattributiert in den GLOBALEN Topf, OHNE Eintrag in einem
    Nutzer-Topf. Die Priorität dort ist immer user_briefing (nie gedrosselt),
    betroffen ist also nur die Zählung, nicht das Drosselungsverhalten. Eine
    Durchreichung von user_id durch die bewusst nutzerfreie Provider-Schicht
    wird NICHT gemacht -- sie würde die Schichtung brechen und keinen
    Drosselungs-Unterschied erzeugen. Die AST-Ratsche
    tests/test_user_id_default_guard.py:286 bleibt unverletzt, weil an dieser
    Stelle gar keine Nutzerkennung gesetzt wird (auch kein "default").

Test, der bricht (Test-Politik: fixen ODER löschen, nie liegenlassen):
  - tests/unit/test_radar_budget_and_priority.py:363
    test_openmeteo_funnel_records_against_shared_budget_counter instanziiert
    ForecastBudgetGate() OHNE Argument (Zeile 375) -- das bricht mechanisch,
    sobald user_id Pflicht-Parameter wird (TypeError beim Konstruktoraufruf).
  - Entscheidung: UMSCHREIBEN, nicht löschen. Der Test sichert eine echte,
    weiterhin gültige Zusicherung zu (ein open-meteo-Fetch über den
    gemeinsamen Funnel zählt gegen ein Budget) -- nur die Form der Zusicherung
    muss das neue Doppel-Buchungs-Verhalten abbilden: EIN Fetch erhöht sowohl
    den globalen Zähler ALS AUCH den Nutzer-Topf des aufrufenden Nutzers
    (RadarNowcastService.get_nowcast() erhält dafür user_id, s. oben). Nach
    dem Umschreiben bewacht der Test wieder etwas Reales statt nur durchzulaufen.

Go-Leseseite:
  - Keine Strukturänderung nötig. forecastBudgetFile (Go) deklariert nur die
    vier bekannten Felder (date/calls/cache_hits/cache_misses); ein zusätzliches
    Feld in der globalen JSON-Datei wird beim Unmarshal ignoriert. Der
    Fehlverweis im Python-Code auf "ADR-0032" (forecast_budget.py:38) wird in
    der Implementierungsphase auf ADR-0075 korrigiert (kein Code-Verweis in
    dieser Spec nötig, siehe ADR-Abschnitt unten).
```

## Expected Behavior

- **Input:** `ForecastBudgetGate(user_id, data_dir=None)` — `user_id` als verbindliche
  Aufrufer-Kennung (Pflicht, kein Default). `allow(priority, now=None)`,
  `record_call()`, `record_cache_hit()`, `record_cache_miss()` bleiben in ihrer äußeren
  Signatur unverändert, wirken aber zusätzlich auf den Nutzer-Topf. `snapshot()` bleibt in
  der Signatur unverändert, liefert aber auf einer user-gebundenen Instanz zusätzliche Felder.
- **Output:** `allow()` liefert weiterhin ein `bool`. `snapshot()` liefert weiterhin das
  globale Aggregat im bisherigen Format (Datum, Zähler, Nutzungsverhältnis, Cache-Zähler,
  Status) plus die drei neuen Nutzer-Felder (`user_calls_today`, `fair_share`,
  `active_users_count`).
- **Side effects:** Schreibt zusätzlich `data/users/<user_id>/diagnostics/forecast_budget.json`.
  Die globale Datei `<data_root>/diagnostics/forecast_budget.json` bekommt ein zusätzliches,
  UTC-tagesweise zurückgesetztes Feld für die am heutigen Tag aktiven Nutzer (vom Go-Leser
  ignoriert, siehe Implementation Details).

## Acceptance Criteria

- **AC-1:** Given zwei Nutzer A und B haben je einen eigenen Nutzer-Topf und der globale Zähler hat die Polling-Schwelle überschritten, wobei A allein deutlich über seinem fairen Anteil (DAILY_BUDGET/N) liegt und B klar darunter / When beide im selben Lauf `allow("polling")` aufrufen / Then liefert der Aufruf für A `False` und für B `True`.
  - Test: In einem gemeinsamen Testlauf werden für Nutzer A und B unterschiedlich viele `record_call()`-Aufrufe gebucht, bis der globale Zähler über `POLLING_THRESHOLD` liegt; anschließend wird für beide Nutzer `allow("polling")` im selben Prozesslauf aufgerufen und das jeweilige Boolean-Ergebnis verglichen.

- **AC-2:** Given Nutzer A und Nutzer B haben unterschiedliche `ForecastBudgetGate`-Instanzen mit je eigener `user_id` und B hat mindestens einen Aufruf gebucht / When mit der Kennung von A `snapshot()` abgefragt wird / Then zeigt `user_calls_today` unter A den Aufruf von B NICHT (Gegenlesung), während `snapshot()` unter der echten Kennung von B den gebuchten Aufruf tatsächlich zeigt (Positivkontrolle).
  - Test: Zwei `ForecastBudgetGate`-Instanzen mit `user_id="nutzer_a"` und `user_id="nutzer_b"` werden gegen denselben `data_dir` betrieben; nach `record_call()` unter B liefert `snapshot()["user_calls_today"]` unter A den Wert `0` (Abwesenheit), unter B den tatsächlich gebuchten Wert (Positivkontrolle).

- **AC-3:** Given der globale Zähler steht bei 100% oder mehr von `DAILY_BUDGET` / When `allow("user_briefing")` für einen beliebigen Nutzer aufgerufen wird / Then liefert der Aufruf weiterhin `True`.
  - Test: Globaler Zähler wird auf `DAILY_BUDGET` oder darüber gesetzt, danach wird `allow("user_briefing")` für einen Nutzer mit voll ausgeschöpftem eigenem Topf aufgerufen und das Ergebnis `True` geprüft.

- **AC-4:** Given der Nutzer-Topf einer `ForecastBudgetGate`-Instanz ist unlesbar (kaputtes JSON) oder das Sidecar-Lock läuft in den Timeout / When `allow("polling")` aufgerufen wird / Then liefert der Aufruf `True` und es wird keine Ausnahme geworfen.
  - Test: Die Nutzer-Zählerdatei wird mit ungültigem JSON präpariert bzw. das Lock künstlich blockiert (Vorlage `tests/tdd/test_file_lock_timeout.py`); Rückgabewert und WARNING-Logeintrag werden geprüft, keine Exception propagiert bis zum Aufrufer.

- **AC-5:** Given ein Nutzer hat gestern (UTC) Aufrufe gebucht und war Teil der „aktive Nutzer"-Menge des Vortags / When eine injizierte Uhr einen neuen UTC-Tag simuliert und `allow()`/`record_call()` erneut aufgerufen werden / Then zeigt `snapshot()["user_calls_today"]` für den neuen Tag einen zurückgesetzten Zähler UND `snapshot()["active_users_count"]` zählt den Vortags-Nutzer nicht mehr, solange er am neuen Tag noch keinen Aufruf gebucht hat.
  - Test: `allow(priority, now=<injizierte Uhr Tag 2>)` nach vorher gebuchtem Aufruf an Tag 1 (`now=<Tag 1>`); sowohl der zurückgesetzte Nutzer-Zählerstand als auch die zurückgesetzte `active_users`-Menge werden über `snapshot()` geprüft, ohne `date.today()` zu verwenden.

- **AC-6:** Given der Python-Core hat sowohl den globalen als auch mehrere Nutzer-Töpfe befüllt / When `/api/scheduler/status` abgefragt wird / Then enthält die Antwort weiterhin ein verwertbares `forecast_budget`-Aggregat (Datum, Zähler, Schwellenstufe) und keines der Felder oder Werte ist eine Nutzerkennung.
  - Test: HTTP-Aufruf gegen den laufenden Go-Server nach vorbereiteten Nutzer-Töpfen mit bekannten, unterscheidbaren `user_id`-Werten; die JSON-Antwort wird auf die erwarteten Aggregatfelder geprüft, und es wird zugesichert, dass keiner der bekannten `user_id`-Strings in der Antwort vorkommt.

- **AC-7:** Given ein Aufrufpfad, der bisher ohne `user_id` in die Budget-Prüfung lief (z.B. `compare_location_weather_source.py:174`) / When er ohne eine echte Nutzerkennung aufgerufen wird / Then bricht der Aufruf laut (Exception wegen fehlendem Pflicht-Parameter) statt auf einen Ersatzwert wie `"default"` zurückzufallen.
  - Test: Der betroffene Aufrufpfad wird ohne `user_id`-Argument aufgerufen; erwartet wird eine geworfene Ausnahme statt einer erfolgreichen Ausführung mit stillschweigend gesetztem Ersatzwert.

- **AC-8:** Given der globale Zähler erreicht 100% oder mehr von `DAILY_BUDGET` / When `allow("polling")` oder `allow("alert_check")` für einen Nutzer aufgerufen wird, dessen eigener Verbrauch noch UNTER seinem fairen Anteil liegt / Then liefert der Aufruf trotzdem `False`.
  - Test: Globaler Zähler wird auf 100%+ gesetzt, der Nutzer-Topf bleibt bei 0 (klar unter jedem fairen Anteil); `allow("polling")` und `allow("alert_check")` werden für diesen Nutzer aufgerufen und beide Ergebnisse als `False` geprüft.

- **AC-9:** Given eine bestehende globale `forecast_budget.json` mit einem Zählerstand aus der Zeit vor dieser Änderung existiert / When nach dem Update der erste Aufruf für einen beliebigen Nutzer erfolgt / Then bleibt der globale Zählerstand unverändert erhalten und der neue Nutzer-Topf beginnt unabhängig bei 0.
  - Test: Eine globale Zählerdatei wird mit einem festen `calls`-Wert im Bestandsformat vorbereitet; nach dem ersten `record_call()` eines Nutzers wird sowohl der globale Zählerstand über `snapshot()["calls_today"]` (um den neuen Aufruf erhöht, sonst unverändert) als auch der über `snapshot()["user_calls_today"]` beobachtete, unabhängig bei 0 gestartete Nutzer-Topf geprüft.

- **AC-10:** Given der globale Zähler liegt im Band zwischen `BRIEFING_ONLY_THRESHOLD` (95%) und 100% von `DAILY_BUDGET`, wobei Nutzer A mit seinem eigenen Tagesverbrauch ÜBER seinem fairen Anteil (`DAILY_BUDGET / N`) liegt und Nutzer B klar darunter / When beide im selben Lauf `allow("alert_check")` aufrufen / Then liefert der Aufruf für A `False` und für B `True` — die Alarm-Prüfung des unbeteiligten Nutzers läuft weiter.
  - Test: Der globale Zähler wird in das Band zwischen 95% und 100% von `DAILY_BUDGET` gesetzt (unter 1.0, damit Stufe 2 nicht greift), die Nutzer-Töpfe werden so vorbelegt, dass A über und B unter dem fairen Anteil liegt; anschließend wird `allow("alert_check")` für beide Nutzer im selben Prozesslauf aufgerufen und `False` für A sowie `True` für B geprüft.

## Known Limitations

- **UTC-Tagesschnitt bleibt bewusst UTC**, nicht die Zeitzone des Nutzers — das Kontingent
  hängt am Konto des Anbieters, nicht am Kalender des Nutzers. Die bestehende Begründung
  der Allowlist-Zeile `tests/test_output_timezone_guard.py:656` ("kein Nutzerdatum") ist durch
  die Nutzer-Partitionierung anfechtbar geworden und muss in der Implementierungsphase
  nachgezogen werden (neue Begründung: der Schnitt ist bewusst UTC, nicht nutzerlos).
- **Drei Pfade umgehen Cache und Gate vollständig** (`comparison_engine.py`, `forecast.py`,
  `trip_forecast.py`) und bleiben in S1 bewusst außerhalb — derselbe Scope-Schnitt wie in
  `fix_1329_forecast_cache_budget.md:415-422`. Ihr Verbrauch fließt weder in den globalen
  noch in einen Nutzer-Topf ein.
- **Der faire Anteil (`DAILY_BUDGET / N`) ändert sich im Tagesverlauf**, wenn weitere Nutzer
  aktiv werden — ein früh am Tag berechneter Anteil kann später sinken. Das ist gewollt: der
  faire Anteil ist ein Momentaufnahme-Wert, keine Reservierung.
- Fall #13 (Provider-Schicht, `thunder_enrichment.py`) bleibt unattributiert im globalen Topf
  ohne eigenen Nutzer-Topf-Eintrag (E4) — bewusster Schichtungs-Schnitt, keine Rückführbarkeit
  dieses Anteils auf einzelne Nutzer.
- Der Go-Status-Endpunkt bleibt bei den bestehenden Aggregatfeldern; eine anonyme Kennzahl der
  aktiven Nutzer-Töpfe (Anzahl statt Liste) ist NICHT Teil von S1 und kann Gegenstand einer
  Folge-Scheibe sein.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0075 (neu; Nummer geprüft und frei)
- **Rationale:** `forecast_budget.py:38` beruft sich bislang auf „ADR-0032" — das ist eine
  Nummernkollision, `docs/adr/0032-*.md` behandelt die Wizard-Abschaffung; ein ADR zum
  Budget-Gate wurde nie angelegt. ADR-0075 schließt diese Lücke UND hält die Entscheidungen
  dieser Spec fest:
  1. Der globale Topf bleibt der alleinige Kontoschutz gegenüber Open-Meteo; ein Zähler je
     Nutzer mit je vollem `DAILY_BUDGET` ist ausdrücklich verworfen (hätte N×Budget zur Folge).
  2. Das Drosselungsmodell ist dreistufig (Schwelle unterschritten → kein Drosseln / Schwelle
     erreicht → fairer Pro-Kopf-Anteil entscheidet / 100% erreicht → harter Kontoschutz
     unabhängig vom Anteil), `user_briefing` bleibt in allen drei Stufen ungedrosselt.
  3. Fail-open gilt auch je Nutzer: ein unlesbarer Nutzer-Topf oder ein Lock-Timeout gilt als
     „nicht überschritten", niemals als Drosselungsgrund.
  4. Die Provider-Schicht (Fall #13) bleibt bewusst nutzerfrei und bucht unattributiert in den
     globalen Topf — keine Durchreichung von `user_id` durch diese Schicht.
  5. Der Go-Status-Endpunkt bleibt auf Aggregate beschränkt; Nutzerkennungen dürfen dort nie
     erscheinen, da der Endpunkt ohne Anmeldung erreichbar ist.
  6. `DAILY_BUDGET`, `POLLING_THRESHOLD`, `BRIEFING_ONLY_THRESHOLD` bleiben wörtlich an ihrer
     bisherigen Stelle (`forecast_budget.py:40-42`) stehen, weil
     `TestForecastBudgetConstantsMatchPython` (`forecast_budget_health_test.go:256`) den
     Python-Quelltext zur Laufzeit liest; der faire Anteil wird als abgeleiteter Wert daneben
     ergänzt, nie an ihrer Stelle.
  Der Fehlverweis in `forecast_budget.py:38` wird im Zuge der Implementierung auf ADR-0075
  korrigiert. Das ADR selbst wird NICHT durch diese Spec angelegt, sondern in der
  Implementierungsphase.

## Changelog

- 2026-09-20: Initial spec created für #2387 (Scheibe S1 von #2150, Epic #2138)
- 2026-09-20: AC-10 ergänzt — die Kernzusicherung des Tickets (`alert_check` eines
  unbeteiligten Nutzers läuft im 95–99%-Band weiter) war in AC-1 (nur `polling`) und
  AC-8 (100%-Kontoschutz) nicht abgedeckt und hätte in `/40-tdd-red` keinen Test bekommen.
