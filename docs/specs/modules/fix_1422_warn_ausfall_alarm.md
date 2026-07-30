---
entity_id: fix_1422_warn_ausfall_alarm
type: module
created: 2026-07-30
updated: 2026-07-30
status: draft
version: "1.0"
tags: [official-alerts, observability, meteoalarm, geosphere-warn, scheduler-status]
workflow: fix_1422_warn_ausfall_alarm
---

<!-- Issue #1422 -->

# Warn-Ausfall wird sichtbar: Zustand der amtlichen Warndienste maschinenlesbar machen

## Approval

- [ ] Approved

## Purpose

MeteoAlarm konnte 24 Stunden lang keine einzige erfolgreiche Antwort liefern
(2026-07-29 09:30 UTC bis 2026-07-30 09:30 UTC gesperrt), ohne dass irgendwo
ein Alarm entstand — BetterStack blieb ruhig, der Scheduler-Status meldete
grün, und die bereits vorhandenen Beobachtungsdaten (`MeteoAlarmBudgetGate.
snapshot()`, `data/diagnostics/warn_service_calls.jsonl`) wurden von nichts
ausgewertet. Diese Spec macht den Zustand jedes amtlichen Warndienstes
(letzter Erfolg, letzter Versuch, eigener Rückzug vs. Anbieter-Ausfall)
maschinenlesbar über den bestehenden, login-freien Status-Endpunkt abrufbar —
die tatsächliche Alarmierung (3h-Schwelle) ist eine separate, in
henemm-infra beauftragte Folgearbeit (s. „Schnittstelle für Teil B" unten).

## Source

- **File:** `internal/scheduler/warn_service_health.go` (NEU)
- **Identifier:** `func (s *Scheduler) WarnServiceHealth() map[string]any`

> **Schicht:** Kern-Aggregation in Go-API (`internal/scheduler/`, liest
> Diagnose-Dateien direkt vom gemeinsamen Datenverzeichnis — analog
> `BriefingHealth()`, kein Python-HTTP-Aufruf). Die dafür nötige
> Journal-Schema-Erweiterung liegt in Python-Core
> (`src/services/official_alerts/warn_egress.py`,
> `src/services/official_alerts/meteoalarm.py`).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/scheduler/briefing_health.go` (`BriefingHealth()`) | module | Vorbild: liest `data/diagnostics/*.jsonl` direkt vom `Scheduler.store.DataDir`, fail-soft, ohne Login erreichbar über denselben Endpunkt |
| `internal/scheduler/scheduler.go` (`Status()`) | module | Einhängepunkt: neues Feld `warn_service_health` neben bestehendem `briefing_health` in der Rückgabe-Map |
| `src/services/official_alerts/warn_egress.py` (`cached_fetch()`, `log_warn_service_call()`) | module | Muss um `ok`/`self_throttled` erweitert werden — einzige Stelle, die den tatsächlichen Ausgang jedes Abrufs kennt |
| `src/services/official_alerts/meteoalarm.py` (`_MeteoAlarmBudgetExhausted`) | module | Muss als selbst auferlegter Rückzug markierbar sein (Unterscheidung von echtem Anbieter-Fehlschlag) |
| `src/services/official_alerts/meteoalarm_budget.py` (`MeteoAlarmBudgetGate.snapshot()`) | module | Zweite Rohdaten-Quelle (Datei `data/diagnostics/meteoalarm_budget.json`), direkt vom Go-Layer gelesen, analog zum Journal |
| `henemm-infra/scripts/check-gregor20.sh` (Abschnitt 2c, `provider_error_streak_since`) | reference | Etabliertes Muster: Kern liefert rohe Zeitstempel, die Schwellen-/Alarmlogik lebt in der Infra-Instanz, nicht hier |
| `docs/specs/modules/warn_service_consumption.md` | spec | Ursprung von `warn_egress.py`/Journal-Schema (Issue #1348) — diese Spec erweitert dessen Schema additiv |

## Estimated Scope

- **LoC:** ~350-450 gesamt über beide Scheiben — **überschreitet das
  250-LoC-Workflow-Limit**, siehe „Scheiben-Empfehlung" in den Implementation
  Details. S1 allein ~90-120 LoC, S2 allein ~180-220 LoC.
- **Files:** 6 (2 Python-Quelldateien geändert, 1 Python-Testdatei erweitert,
  1 Go-Datei neu, 1 Go-Datei geändert, 1 Go-Testdatei neu)
- **Effort:** medium (S1) + medium-high (S2)

## Implementation Details

### Scheiben-Empfehlung (LoC-Limit)

Diese Spec deckt zwei aufeinander aufbauende, aber unabhängig abschließbare
Scheiben ab. Wird das 250-LoC-Workflow-Limit ohne PO-Override erreicht: **S1
zuerst als eigener Workflow abschließen** (in sich geschlossen, additiv,
kein Verhaltensbruch für bestehende Leser des Journals), **S2 als
Folge-Workflow** auf derselben Spec.

- **S1 — Journal-Grundlage (Python-Core):** `warn_egress.py`/`meteoalarm.py`
  erweitern, sodass jede Journal-Zeile ihren tatsächlichen Ausgang trägt.
  Deckt AC-1 bis AC-3.
- **S2 — Statusendpunkt (Go-API):** `WarnServiceHealth()` aggregiert Journal
  + Budget-Datei zu einem neuen Feld im bestehenden
  `/api/scheduler/status`. Deckt AC-4 bis AC-8.

### S1 — Journal trägt den tatsächlichen Ausgang

Heute unterscheidet `log_warn_service_call()` nur `status`/`cache_hit`/
`retry_after` — zwei Fälle bleiben dabei von außen ununterscheidbar:

1. Ein Cache-Treffer während eines aktiven Fehlschlag-Backoff-Fensters
   (`entry["data"] is None`) protokolliert **denselben** `status=None,
   cache_hit=true` wie ein Cache-Treffer auf echte, gute Daten — von außen
   nicht als „weiterhin ausgefallen" erkennbar.
2. Ein selbst auferlegter Rückzug (`_MeteoAlarmBudgetExhausted`, eigenes
   Tageskontingent erschöpft) durchläuft denselben generischen
   Exception-Zweig wie ein echter Netzwerkfehler des Anbieters — von außen
   nicht unterscheidbar, obwohl die Gegenmaßnahme eine andere ist (eigenen
   Verbrauch senken vs. auf den Anbieter warten).
3. Ein „nicht zuständig"-Treffer (`not_covered_statuses`, z.B. GeoSphere-404
   außerhalb Österreichs) trägt heute keinen Marker, der ihn von einem
   echten Fehlschlag mit demselben Statuscode unterscheidet.

`log_warn_service_call()` bekommt zwei neue Parameter, additiv zum
bestehenden Schema (bestehende Leser/Tests bleiben unberührt, da JSON-Objekte
zusätzliche Keys ignorieren):

- `ok: bool` — trägt den tatsächlichen Ausgang dieser Zeile (Erfolg inkl.
  „nicht zuständig" = `true`; jeder Fehlschlag inkl. Cache-Treffer auf einen
  gecachten Fehlschlag = `false`). Wird an jeder der sechs bestehenden
  Aufrufstellen innerhalb `cached_fetch()` gesetzt.
- `self_throttled: bool = False` — `true` nur, wenn der Fehlschlag ein
  selbst auferlegter Rückzug war, erkannt über
  `getattr(exc, "self_throttled", False)` im bestehenden generischen
  Exception-Zweig (keine neue Exception-Hierarchie zwischen den Modulen
  nötig). `_MeteoAlarmBudgetExhausted` bekommt dafür ein
  Klassenattribut `self_throttled = True`.

Kein bestehender Aufrufer außerhalb `cached_fetch()` ist betroffen —
`log_warn_service_call()` wird ausschließlich intern aufgerufen.

### S2 — `WarnServiceHealth()` aggregiert Rohdaten, entscheidet nichts

Analog `BriefingHealth()`: liest `data/diagnostics/warn_service_calls.jsonl`
sowie `data/diagnostics/meteoalarm_budget.json` direkt vom
`s.store.DataDir` — kein Python-HTTP-Aufruf, kein App-Login nötig (derselbe
Grund, aus dem `check-gregor20.sh` heute schon `/api/scheduler/status` ohne
Auth abfragt).

**Bewusste Design-Entscheidung — nur Rohdaten, keine Schwelle:** Wie
`provider_error_streak_since` (Issue #1115/#1421) liefert dieser Endpunkt
ausschließlich Zeitstempel/Flags, **keine** fertige „ausgefallen"-Bewertung
und **keine** 3h-Schwelle. Die Schwellenlogik lebt bewusst in
`check-gregor20.sh` (Teil B) — genau wie beim bestehenden
Provider-Error-Streak. Das hält diese Scheibe klein und die Schwelle
änderbar, ohne Gregor neu deployen zu müssen.

Pro **kanonischem Dienstnamen** (Präfix vor dem ersten `:` im `service`-Feld
der Journal-Zeile — z.B. `meteoalarm:AT:p1` → `meteoalarm`; Dienste ohne `:`
bleiben unverändert) werden **nur** Zeilen mit `cache_hit=false`
berücksichtigt (ein Cache-Treffer ist keine neue Antwort vom Anbieter) UND
nur Zeilen, die das neue `ok`-Feld tragen (ältere Zeilen aus der Zeit vor
dieser Erweiterung werden übersprungen, s. Known Limitations):

- `last_success_at` — Zeitstempel der jüngsten Zeile mit `ok=true`.
- `last_attempt_at` — Zeitstempel der jüngsten Zeile überhaupt (Erfolg oder
  Fehlschlag) — die Grundlage für Teil B, um „gerade aktiv, aber
  fehlschlagend" von „aktuell gar nicht gebraucht" zu unterscheiden.
- `self_throttled` — `self_throttled`-Wert der jüngsten Zeile.

**Kein Eintrag, wenn nie aufgerufen:** Ein Dienst, für den in der gesamten
Journal-Historie keine passende Zeile existiert (z.B. weil aktuell kein
Trip seinen Zuständigkeitsbereich berührt), erscheint **gar nicht** als
Schlüssel in der Ergebnis-Map — kein erfundener Fehlschlag-Zustand. Teil B
muss ein fehlendes Feld als „keine Evidenz, kein Alarm" behandeln, nicht als
Fehlschlag.

**Datei fehlt vs. Datei kaputt:** Existiert `warn_service_calls.jsonl`
(noch) nicht, ist das Ergebnis eine leere Map (`{}`) — legitimer
Zustand direkt nach einer frischen Bereitstellung. Existiert die Datei,
lässt sich aber nicht öffnen/lesen (Rechteproblem, kaputtes Dateisystem),
setzt die Antwort zusätzlich `"journal_read_error": true` — **explizit
unterscheidbar** von „Datei fehlt noch nie geschrieben" bzw. von einem
gesunden leeren Zustand. Genau dieses stille „alles gut, weil nichts
gelesen werden konnte" ist der Fehler, den Issue #1422 behebt.

`meteoalarm_budget.json` wird als eigenständiger Block `meteoalarm_budget`
in dieselbe Antwort übernommen (Felder wie in
`MeteoAlarmBudgetGate.snapshot()`: `calls_today`, `daily_budget`,
`usage_ratio`, `observed_reset_ts`, `status`) — fail-soft nach demselben
Muster wie `snapshot()` selbst (`status: "unavailable"` statt Exception).

Einhängung: `scheduler.go`'s `Status()` bekommt eine zusätzliche Zeile
`"warn_service_health": s.WarnServiceHealth(),` neben dem bestehenden
`"briefing_health"`.

## Expected Behavior

- **Input:** Journal-Zeilen aus `data/diagnostics/warn_service_calls.jsonl`
  (geschrieben von `cached_fetch()` bei jedem Cache-Hit/-Miss aller fünf
  Warn-Dienste) sowie der Inhalt von `data/diagnostics/meteoalarm_budget.json`
- **Output:** neues Feld `warn_service_health` (pro tatsächlich aufgerufenem
  Dienst: `last_success_at`, `last_attempt_at`, `self_throttled`, optional
  `journal_read_error`) und `meteoalarm_budget` in der bestehenden,
  login-freien `/api/scheduler/status`-Antwort (Go-API, Port 8090)
- **Side effects:** keine — reine Leseoperation auf bereits bestehende
  Diagnose-Dateien, kein neuer Schreibpfad außer den additiven Feldern in
  der bereits bestehenden Journal-Zeile

## Test Plan

### Automated Tests (TDD RED)

- [ ] `tests/tdd/test_warn_service_egress.py::test_not_covered_treffer_zaehlt_als_erfolg` —
  AC-1: `not_covered_statuses`-Zweig schreibt `ok=true`.
- [ ] `tests/tdd/test_warn_service_egress.py::test_selbst_auferlegter_rueckzug_markiert_sich_selbst` —
  AC-2: eine Exception mit `self_throttled=True`-Attribut (Stellvertreter für
  `_MeteoAlarmBudgetExhausted`, kein echtes Netz) erzeugt eine Journal-Zeile
  mit `ok=false, self_throttled=true`; ein echter (konstruierter)
  Netzwerkfehler ohne dieses Attribut erzeugt `self_throttled=false`.
- [ ] `tests/tdd/test_warn_service_egress.py::test_cache_treffer_auf_fehlgeschlagenen_eintrag_ist_kein_erfolg` —
  AC-3: Cache mit `{"data": None, ...}` vorbelegt, Cache-Treffer-Zeile trägt
  `ok=false`.
- [ ] `internal/scheduler/warn_service_health_test.go::TestWarnServiceHealthReportsStaleSuccessAfterRepeatedFailures` —
  AC-4: Fixture-JSONL mit 24h ausschließlich `ok=false`-Zeilen für
  `meteoalarm:AT:p1`; `last_success_at` ist `null` bzw. älter als 24h,
  `last_attempt_at` aktuell.
- [ ] `internal/scheduler/warn_service_health_test.go::TestWarnServiceHealthOmitsServiceWithoutAnyCalls` —
  AC-5: Fixture ohne jede Zeile für `massif_closure`; der Schlüssel fehlt in
  der Ergebnis-Map komplett (kein erfundener Fehlschlag).
- [ ] `internal/scheduler/warn_service_health_test.go::TestWarnServiceHealthDistinguishesSelfThrottleFromBudgetFile` —
  AC-6: `meteoalarm_budget.json`-Fixture mit erschöpftem Kontingent
  (`observed_reset_ts` in der Zukunft) erscheint als eigener
  `meteoalarm_budget`-Block, unabhängig vom journalbasierten
  `self_throttled`-Flag.
- [ ] `internal/scheduler/warn_service_health_test.go::TestWarnServiceHealthFlagsUnreadableJournalDistinctFromMissing` —
  AC-7: Journal-Pfad zeigt auf ein Verzeichnis statt eine Datei (erzeugt
  einen echten, plattformunabhängigen Lesefehler ohne Rechte-Manipulation) →
  `journal_read_error=true`; fehlender Pfad (`os.IsNotExist`) → leere Map,
  kein Fehler-Flag.
- [ ] Staging-Nachweis (kein pytest, Teil der E2E-Verifikation): `curl
  https://staging.gregor20.henemm.com/api/scheduler/status` nach einem
  abgeschlossenen Scheduler-Zyklus — AC-8: da `api.meteoalarm.org` und
  `warnungen.zamg.at` auf Staging laut Egress-Guard `BLOCKED` sind (Issue
  #1348 2b), müssen `meteoalarm`/`geosphere_warn` `last_success_at: null`
  (bzw. deutlich veraltet) bei aktuellem `last_attempt_at` zeigen — ein
  echtes, reproduzierbares Dauerausfall-Szenario ohne Mock.

Kein Mock-Theater: Go-Tests schreiben echte JSONL-Fixture-Zeilen in
`t.TempDir()` und lesen `WarnServiceHealth()` real zurück; Python-Tests
konstruieren echte (kleine) Exception-Objekte statt `Mock()`. Keine reale
Uhr-Injektion nötig, da `WarnServiceHealth()` bewusst keine Alters-/
Schwellenberechnung selbst vornimmt (s. Implementation Details) — Fixtures
mit festen Zeitstempeln genügen für deterministische Assertions.

## Acceptance Criteria

- **AC-1:** Given eine Antwort fällt unter die „nicht zuständig"-Behandlung eines Dienstes (z.B. ein Ort außerhalb des Zuständigkeitsbereichs) / When die Journal-Zeile für diesen Abruf geschrieben wird / Then ist sie als erfolgreiche Antwort erkennbar, nicht als Fehlschlag
  - Test: `test_warn_service_egress.py::test_not_covered_treffer_zaehlt_als_erfolg`

- **AC-2:** Given ein Dienst weicht wegen des eigenen, selbst gesetzten Verbrauchslimits zurück, ohne dass ein echter Netzwerk-Call den Anbieter erreicht / When diese Zeile protokolliert wird / Then ist sie eindeutig als selbst auferlegter Rückzug erkennbar und von einem echten Antwortfehlschlag des Anbieters unterscheidbar
  - Test: `test_warn_service_egress.py::test_selbst_auferlegter_rueckzug_markiert_sich_selbst`

- **AC-3:** Given ein Cache-Treffer liefert Daten aus einem Zeitfenster zurück, in dem der letzte echte Abruf fehlgeschlagen war / When die Journal-Zeile für diesen Treffer geschrieben wird / Then ist auch dieser Treffer als nicht erfolgreich erkennbar, statt als stiller Erfolg durchzugehen
  - Test: `test_warn_service_egress.py::test_cache_treffer_auf_fehlgeschlagenen_eintrag_ist_kein_erfolg`

- **AC-4:** Given ein Warn-Dienst hatte über 24 Stunden hinweg wiederholte echte Abrufversuche, aber keine einzige erfolgreiche Antwort / When der Systemzustand über den bestehenden, ohne Anmeldung erreichbaren Status-Endpunkt abgefragt wird / Then zeigt der Zustand für diesen Dienst einen fehlenden oder mehr als 24 Stunden zurückliegenden letzten Erfolg bei gleichzeitig aktuellem letzten Versuch — nicht „alles in Ordnung"
  - Test: `warn_service_health_test.go::TestWarnServiceHealthReportsStaleSuccessAfterRepeatedFailures`

- **AC-5:** Given ein Warn-Dienst wurde im gesamten Beobachtungszeitraum kein einziges Mal aufgerufen, weil aktuell kein beobachteter Ort in seinem Zuständigkeitsbereich liegt / When der Systemzustand abgefragt wird / Then enthält der Zustand für diesen Dienst keinen erfundenen Fehlschlag-Hinweis, sondern ist erkennbar von einem tatsächlichen Ausfall unterscheidbar (keine Aktivität statt Ausfall)
  - Test: `warn_service_health_test.go::TestWarnServiceHealthOmitsServiceWithoutAnyCalls`

- **AC-6:** Given das eigene Tageskontingent für einen Warn-Dienst ist erschöpft (selbst auferlegter Rückzug, keine Störung beim Anbieter) / When der Systemzustand abgefragt wird / Then zeigt der Zustand diesen Rückzug getrennt vom journalbasierten Ausfallsignal an, sodass ein selbst verursachter Rückzug nicht mit einer echten Anbieter-Störung verwechselt wird
  - Test: `warn_service_health_test.go::TestWarnServiceHealthDistinguishesSelfThrottleFromBudgetFile`

- **AC-7:** Given die Journal-Datei existiert, ist aber nicht lesbar / When der Systemzustand abgefragt wird / Then meldet der Zustand diesen Lesefehler erkennbar, statt stillschweigend einen unauffälligen (leeren) Zustand zurückzugeben; fehlt die Datei hingegen komplett, bleibt der Zustand unauffällig leer ohne Fehler-Flag
  - Test: `warn_service_health_test.go::TestWarnServiceHealthFlagsUnreadableJournalDistinctFromMissing`

- **AC-8:** Given auf der Staging-Umgebung sind die Warn-API-Hosts grundsätzlich blockiert (dauerhaftes, reproduzierbares Ausfall-Szenario) / When der Status-Endpunkt auf Staging nach einem abgeschlossenen Scheduler-Zyklus abgefragt wird / Then zeigt der Zustand für die betroffenen Dienste den fehlenden Erfolg bei aktuellem letzten Versuch — kein grüner oder leerer Anschein trotz andauerndem Ausfall
  - Test: Staging-Curl-Nachweis gegen `/api/scheduler/status` (kein pytest/Go-Test, Teil der E2E-Verifikation)

## Known Limitations

- **Übergangsfenster nach Deploy:** Journal-Zeilen, die vor dieser Erweiterung
  geschrieben wurden, tragen kein `ok`-Feld und werden von
  `WarnServiceHealth()` vollständig übersprungen (weder Erfolg noch
  Fehlschlag) — bis genügend neue Zeilen nachgeschrieben sind (typischerweise
  binnen einer Stunde bei stündlicher Auffrischung), ist die Datenlage
  vorübergehend dünner als danach.
- **Unbegrenztes Wachstum des Journals:** `warn_service_calls.jsonl` hat
  keine Rotation/Retention (ererbtes Verhalten aus Issue #1348, nicht neu
  durch diese Spec) — `WarnServiceHealth()` scannt die komplette Datei bei
  jedem Aufruf, analog zu `BriefingHealth()`s Umgang mit
  `openmeteo_calls.jsonl`. Wird das zu einem Performance-Thema, ist eine
  eigene Housekeeping-Scheibe fällig.
- **„Nicht zuständig" wird nur über Abwesenheit erkannt:** Es gibt keinen
  aktiven Zuständigkeits-Katalog. Sollte ein Dienst aus einem eigenen Bug
  einfach nie aufgerufen werden (statt weil aktuell kein passender Ort
  beobachtet wird), sieht das für `WarnServiceHealth()` identisch aus wie
  „aktuell nicht gebraucht" — dieser Unterschied bleibt unsichtbar.
- **`meteoalarm_budget.json`-Lesefehler bleiben fail-soft ohne eigenes
  Fehler-Flag** (folgt der bestehenden `MeteoAlarmBudgetGate.snapshot()`-
  Konvention `status: "unavailable"`) — anders als beim Journal wird hier
  kein zusätzliches `*_read_error`-Flag eingeführt, da dieses Verhalten
  bereits bestehender, akzeptierter Vertrag ist.
- **Kanonische Dienstgruppierung per String-Split vor dem ersten `:`:** ein
  künftiger Dienstname, der selbst einen Doppelpunkt im eigentlichen Namen
  trägt, würde falsch gruppiert — aktuell betrifft das keinen der fünf
  bestehenden Dienste.
- **Teil B (3h-Schwelle, tatsächliche Alarmierung in
  `check-gregor20.sh`) ist NICHT Teil dieser Spec/Implementierung** — wird
  separat in `henemm-infra` beauftragt (per Inter-Instanz-Nachricht an
  `infra`, s. Abschnitt „Schnittstelle für Teil B"). Ohne diese Umsetzung
  bleibt der Ausfall über diese Spec allein sichtbar, aber noch nicht
  alarmiert.
- **`retry_after`/`status` bestehender Felder unverändert** — diese Spec
  fügt ausschließlich neue Felder hinzu, ändert keine bestehende Semantik.

## Schnittstelle für Teil B (henemm-infra, NICHT Gegenstand dieser Spec)

Wird nach Abschluss dieser Spec per Inter-Instanz-Nachricht an `infra`
beauftragt. Erwartete Schnittstelle, ohne Rückfragen umsetzbar:

- **Endpunkt:** `GET http://localhost:8090/api/scheduler/status` (bereits
  heute von `check-gregor20.sh` ohne Login abgefragt).
- **Neues Feld `warn_service_health`** (Objekt, Schlüssel = kanonischer
  Dienstname, z.B. `meteoalarm`, `geosphere_warn`, `vigilance`,
  `meteo_forets`, `massif_closure` — **nur vorhanden, wenn der Dienst
  mindestens einmal aufgerufen wurde**):
  - `last_success_at` (RFC3339-String oder `null`)
  - `last_attempt_at` (RFC3339-String oder `null`)
  - `self_throttled` (bool) — `true`, wenn der jüngste Fehlschlag ein
    selbst auferlegter Rückzug war (kein Anbieter-Problem)
  - `journal_read_error` (bool, nur vorhanden wenn `true`) — Journal-Datei
    existiert, ist aber nicht lesbar; **als eigener Fehlerfall behandeln**
    (Datei fehlt hingegen komplett → normaler, unauffälliger Zustand)
- **Neues Feld `meteoalarm_budget`** (Objekt, Passthrough von
  `MeteoAlarmBudgetGate.snapshot()`): `calls_today`, `daily_budget`,
  `usage_ratio`, `observed_reset_ts`, `status` (`"ok"`/`"unavailable"`).
- **Erwartete Auswertung in `check-gregor20.sh`:** analog Abschnitt 2c
  (`provider_error_streak_since`) — für jeden vorhandenen Schlüssel in
  `warn_service_health`: fehlt `last_success_at` ODER liegt er mehr als 3
  Stunden zurück, UND `last_attempt_at` liegt selbst nicht mehr als 3
  Stunden zurück (sonst: Dienst aktuell nicht in Gebrauch, kein Alarm) →
  ERROR. `self_throttled=true` bzw. `meteoalarm_budget.status` erschöpft →
  eigener, unterscheidbarer Hinweistext (andere Gegenmaßnahme: eigenen
  Verbrauch senken statt auf den Anbieter warten). `journal_read_error=true`
  → eigener ERROR, unabhängig vom Rest.
- Kein neuer BetterStack-Heartbeat — Einhängung in den bestehenden
  Gregor20-CORE- bzw. EXT-Heartbeat (Quote ist mit 10/10 voll).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** reine Observability-Erweiterung einer bestehenden
  Provider-Schicht (`official_alerts/`) und eines bestehenden,
  login-freien Status-Endpunkts (`internal/scheduler`) — berührt keine der
  ADR-relevanten Entscheidungsflächen (Kanäle, Provider-Auswahl,
  Datenmodell/Persistenz, Auth, Editor-Paradigma, Test-/Deploy-Strategie).
  Kein neuer Provider, kein neuer Kanal, keine Schema-Änderung an
  Kernentitäten (nur additive Diagnose-Felder).

## Changelog

- 2026-07-30: Initial spec erstellt — Issue #1422
