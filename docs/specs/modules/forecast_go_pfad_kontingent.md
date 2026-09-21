---
entity_id: forecast_go_pfad_kontingent
type: module
created: 2026-09-21
updated: 2026-09-21
status: draft
version: "1.0"
tags: [multi-user, forecast-budget, go-python-grenze, epic-2138]
---

# Forecast Go-Pfad Kontingent

## Approval

- [ ] Approved

## Purpose

`GET /api/forecast` (Go) ruft Open-Meteo direkt über den Provider auf und umgeht dabei das
Tageskontingent-Gate (`ForecastBudgetGate`), das im Python-Core sitzt — ein Aufruf über diesen
Pfad zählt weder gegen den globalen Topf noch gegen den Nutzer-Topf aus #2387. Diese Änderung
verdrahtet den Go-Pfad durch dieselbe dreistufige Kontingent-Entscheidung wie alle anderen
Aufrufer, mit der echten Nutzerkennung, sodass ein einzelner Nutzer über diesen Weg nicht die
Kontingente der anderen aufbrauchen kann (#2391, Scheibe S3 von #2150, Epic #2138 Multi-User).

## Source

- **File:** `internal/handler/forecast.go`
- **Identifier:** `ForecastHandler`

Betroffene Schichten:

- **Go-API:** `internal/handler/forecast.go` (Auth-Prüfung, Reservierung vor dem Abruf, 429 bei
  Ablehnung), `internal/router/router.go` (Konfiguration der Core-URL an den Handler durchreichen)
- **Python-Core:** `api/routers/internal.py` (neuer Endpunkt `POST
  /api/_internal/forecast-budget/reserve`, prüft und bucht in einem Aufruf gegen
  `ForecastBudgetGate`)

## Estimated Scope

- **LoC:** ~100 (Go-Handler ~55, Router-Verdrahtung ~1, Python-Endpunkt ~35)
- **Files:** 3 produktiv (`internal/handler/forecast.go`, `internal/router/router.go`,
  `api/routers/internal.py`) + 2 Doku (`docs/adr/0076-*.md`, `docs/adr/README.md`) + 2 Test
  (`internal/handler/forecast_test.go`, `tests/tdd/test_internal_forecast_budget_reserve.py`)
- **Effort:** medium
- **`e2e_scope`:** **full-stack (Go + Python), kein Frontend** — die Änderung berührt
  `internal/` und `api/`, aber keine Datei unter `frontend/`. Die Staging-Validierung muss
  beide Prozesse abdecken (Go-Handler und Python-Core), ein Frontend-Browser-Gate ist nicht
  erforderlich.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| ADR-0075 (Forecast-Budget-Fairness je Nutzer) | ADR | Bindend, alle 6 Punkte: dreistufiges `allow(priority)`, `user_briefing` nie gedrosselt, Fail-open je Nutzer, kein `"default"`-Rückfall, Go-Status bleibt aggregatfrei, Konstanten bleiben an ihrer Python-Stelle |
| ADR-0015 (Dual-Stack-Zuständigkeit) | ADR | Regel 1: neue Domänenlogik entsteht im Python-Core, Go bleibt API-Klebstoff — löst die Spannung mit der Zuständigkeitstabelle, die „Rate-Limiting" als Go-Aufgabe nennt |
| ADR-0062 (Core authentifiziert Go) | ADR | `X-GZ-Core-Auth` mit `GZ_CORE_SHARED_SECRET`, fail-closed auf jedem Endpunkt außer `/health` — trägt den neuen internen Aufruf |
| ADR-0003 (Mandantentrennung) | ADR | Kein `"default"`-Rückfall für `user_id`; echte Kennung aus dem Auth-Kontext |
| `ForecastBudgetGate` (`src/services/forecast_budget.py`) | Modul | Enthält die dreistufige Entscheidung `allow(priority)` und die Buchung `record_call()`/`record_cache_miss()`, die der neue Endpunkt aufruft |
| `internal/handler/premium_sms_link_code.go:33-40` | Modul | Muster für die 401-Prüfung: `middleware.UserIDFromContext` liefert bei fehlender Session den leeren String, Handler prüft selbst |
| `internal/handler/proxy.go:151-163` (`appendUserID`) | Modul | Muster für Spoofing-Schutz: entfernt eine vom Client mitgeschickte `user_id`, setzt die authentifizierte |
| `internal/coreauth/transport.go:27` | Modul | Transport, der `X-GZ-Core-Auth` an ausgehende Core-Aufrufe anhängt |
| `api/routers/internal.py:29` | Modul | Bestehendes Muster für `user_id: str = Query(...)` als Pflicht-Parameter am Core-Endpunkt |
| `internal/scheduler/forecast_budget_health_test.go:256-286` (`TestForecastBudgetConstantsMatchPython`) | Test | Eingefrorener Boden aus ADR-0075 Punkt 6 — `polling` bleibt die einzig passende Bestandspriorität, keine neue Konstante |

## Implementation Details

```
POST /api/_internal/forecast-budget/reserve?user_id=<auth>&priority=polling
  (Python-Core, api/routers/internal.py, hinter enforce_core_auth)

  → 200 {"allowed": true}
       Ablauf im Handler: ForecastBudgetGate(user_id).allow("polling") == True
         → record_cache_miss()   (auf dem Go-Pfad gibt es keinen Antwort-Cache,
           jeder Abruf ist faktisch ein Miss -- ohne das lügt die Cache-Hit-Quote
           in /api/scheduler/status nach oben)
         → record_call() zweimal
           (2 Einheiten = garantierte Untergrenze des Regelfalls: doRequest
           (Forecast) + fetchUVData laufen unbedingt; tryFallback und Retries
           können mehr kosten -- bewusste Unterbuchung, siehe Known Limitations.
           Der zweite record_call()-Aufruf ist KEIN Kopierfehler: record_call()
           trägt zusätzlich user_id in die Menge "active_users" der globalen
           Datei ein, die aber mengengeprüft und damit idempotent ist -- der
           zweite Aufruf erhöht ausschließlich "calls", active_users bleibt
           unverändert. Diese Wiederholung ist Absicht, kein Bug.)

  → 200 {"allowed": false, "retry_after_s": <Sekunden bis UTC-Mitternacht>}
       Ablauf im Handler: allow("polling") == False -- NICHTS wird gebucht,
       weder record_cache_miss() noch record_call() laufen. Der abgelehnte
       Pfad und der gebuchte Pfad sind im Endpunkt zwei disjunkte Zweige, nicht
       ein "allow, dann record egal was".

  Auf der Leitung reisen NUR user_id und priority. Die Zahl der gebuchten
  Einheiten (2) ist KEINE Schnittstellen-Größe, sondern eine Konstante im
  Python-Endpunkt -- ein Query-Parameter "units" ließe Handler und Gate
  auseinanderdriften, weil der Core dann jede vom Aufrufer geschickte Zahl
  annähme, statt selbst zu wissen, was ein Forecast-Abruf kostet.

Go-Handler (internal/handler/forecast.go, ForecastHandler):

  Reihenfolge im Handler (PFLICHT, in dieser Abfolge):
    1. Auth-Prüfung ZUERST:
       userID := middleware.UserIDFromContext(r.Context())
       if userID == "" { 401 unauthorized; return }
       (Muster: internal/handler/premium_sms_link_code.go:33-40)
    2. Parametervalidierung DANACH (lat/lon/hours wie bisher, unverändert
       in Form und Fehlertext) -- 400 bei fehlendem/ungültigem lat/lon.
    3. Reservierung: POST an /api/_internal/forecast-budget/reserve mit der
       authentifizierten user_id (NIE eine vom Client mitgeschickte, Muster
       appendUserID) und priority=polling, über den mit X-GZ-Core-Auth
       versehenen Transport (internal/coreauth/transport.go).
       - Core antwortet allowed:true  -> weiter zu Schritt 4 (Abruf).
       - Core antwortet allowed:false -> 429, Retry-After-Header (Sekunden
         bis UTC-Mitternacht aus retry_after_s), Fehlerobjekt im Stil
         {"error": "budget_exceeded", "detail": "..."}. KEIN Abruf.
       - Core nicht erreichbar / Timeout / Antwort != 200 -> fail-open:
         WARNING loggen, weiter zu Schritt 4 wie bisher (Verhalten wie vor
         dieser Änderung).
    4. p.FetchForecast(lat, lon, hours) wie bisher, Antwort unverändert.

  Bestandstest internal/handler/forecast_test.go:16-102 prüft heute
  Parametervalidierung OHNE Auth-Kontext im Request. Mit der neuen Reihenfolge
  liefen diese Fälle sonst 401 statt 400. FESTLEGUNG: diese Testfälle bekommen
  einen gültigen Auth-Kontext gesetzt (Session/Context wie im Muster anderer
  Handler-Tests mit Auth), die bestehende 400-Erwartung bleibt UNVERÄNDERT.
  Kein stilles Umschreiben der Erwartung auf 401.

Router (internal/router/router.go):
  ForecastHandler bekommt zusätzlich die Core-Basis-URL aus der bestehenden
  Konfiguration (deps.Config.PythonCoreURL) durchgereicht -- eine Zeile,
  keine neue Konfigurationsquelle.
```

## Expected Behavior

- **Input:** `GET /api/forecast?lat=<f>&lon=<f>&hours=<n>` mit Session-Cookie/Auth-Kontext wie
  bisher. Kein neuer Client-Parameter.
- **Output:** Bei erlaubtem Kontingent unverändert `200` mit der Vorhersage (`meta`/`data`/
  `timezone`). Bei ausgeschöpftem Kontingent `429` mit `Retry-After`-Header (Sekunden bis UTC-
  Mitternacht) und Fehlerobjekt `{"error": ..., "detail": ...}`. Ohne Session `401`. Bei
  Parameterfehlern weiterhin `400` (Form unverändert). Bei unerreichbarem Core weiterhin `200`
  mit der Vorhersage (fail-open) plus `WARNING`-Logeintrag.
- **Side effects:** Bei jedem durchgelassenen Aufruf erhöht der Python-Core den globalen
  Tageszähler um 2 Einheiten, den Nutzer-Topf der aufrufenden `user_id` um 2 Einheiten, bucht
  einmal `record_cache_miss()` und trägt `user_id` in `active_users` ein (idempotent). Bei
  abgelehnter Reservierung und bei unerreichbarem Core bleibt der Zähler unverändert.

## Acceptance Criteria

- **AC-1:** Given ein angemeldeter Nutzer ruft `GET /api/forecast` auf und der Python-Core
  erlaubt die Reservierung / When die Antwort `200` mit der Vorhersage zurückkommt / Then hat
  sich der Tageszähler des Python-Core für die echte `user_id` dieses Nutzers um 2 Einheiten
  erhöht.
  - Test: Ein Aufruf gegen `ForecastHandler` mit gesetztem Auth-Kontext und einem echten
    Python-Core (Testserver gegen eine `tmp_path`-Zählerdatei) wird ausgeführt; vor und nach dem
    Aufruf wird der Zählerstand der Nutzer-Zählerdatei für genau diese `user_id` gelesen und die
    Differenz von 2 geprüft.

- **AC-2:** Given zwei Nutzer A und B rufen `GET /api/forecast` auf, wobei der (gestubte)
  Python-Core für A `allowed: false` und für B `allowed: true` liefert / When beide Anfragen im
  selben Testlauf gegen `ForecastHandler` laufen / Then antwortet der Handler für A mit `429`
  und für B mit `200`.
  - Test: `httptest`-Server als Core-Stub, der je nach mitgeschicktem `user_id`-Query-Wert
    unterschiedlich antwortet; zwei `httptest.NewRequest`-Aufrufe mit unterschiedlichem
    Auth-Kontext (Nutzer A, Nutzer B) gegen denselben `ForecastHandler`, Statuscode wird je
    Nutzer geprüft. Das beweist die Verdrahtung im Handler, nicht das Kontingent selbst.

- **AC-3:** Given zwei Nutzer A und B haben unterschiedliche Nutzer-Töpfe in derselben, echten
  Zählerdatei-Struktur (`tmp_path`), wobei A über seinem fairen Anteil (`DAILY_BUDGET/N`) liegt
  und B klar darunter, und der globale Zähler hat die `polling`-Schwelle erreicht / When beide
  `POST /api/_internal/forecast-budget/reserve?user_id=...&priority=polling` aufrufen / Then
  liefert der Endpunkt für A `{"allowed": false, ...}` und für B `{"allowed": true}`.
  - Test: Gegen den echten FastAPI-Endpunkt mit `data_dir` auf `tmp_path` wird der globale
    Zähler über die `polling`-Schwelle gebracht, die Nutzer-Töpfe von A und B werden über den
    Endpunkt selbst (nicht über eine Fixture, die die Felder vorab anlegt) so vorbelegt, dass A
    über und B unter dem fairen Anteil liegt; anschließend werden beide Antworten geprüft.
    **Pflicht:** der Test lässt das Produkt (den Endpunkt) den Zähler schreiben und liest `calls`
    sowie `active_users` danach aus der real geschriebenen Datei zurück — eine Fixture, die diese
    Felder selbst anlegt, macht die Zusicherung vakuum-grün (so geschehen in #2387 RED).

- **AC-4:** Given der Python-Core-Endpunkt bekommt einen Aufruf mit einer bestimmten `user_id`
  und `priority=polling` / When der Endpunkt die Anfrage verarbeitet / Then liest ein Test die
  am Endpunkt tatsächlich angekommenen Werte von `user_id` und `priority` aus und prüft sie
  gegen die erwarteten Werte, statt nur das zurückgelieferte Urteil zu befolgen.
  - Test: Der Core-Endpunkt (oder im Go-Test der Stub) protokolliert die empfangene Query
    (`user_id`, `priority`) in eine für den Test lesbare Stelle; der Test vergleicht diese
    protokollierten Werte mit der erwarteten `user_id` des Handler-Aufrufers und mit
    `priority=polling` explizit. Hintergrund: `allow()` lässt unbekannte Prioritäten immer durch
    (`forecast_budget.py:133-134`, fail-open) — ein Test, der nur die Stub-Antwort prüft, bliebe
    bei einem Tippfehler in `priority` grün.

- **AC-5:** Given der Python-Core ist für den Handler nicht erreichbar (Verbindungsfehler,
  Timeout, oder Antwortstatus ungleich `200`) / When ein angemeldeter Nutzer `GET /api/forecast`
  aufruft / Then antwortet der Handler mit `200` und der Vorhersage (fail-open) und es wird ein
  `WARNING`-Logeintrag erzeugt.
  - Test: `ForecastHandler` wird mit einer Core-URL konfiguriert, die verbindungsunfähig ist
    bzw. gegen einen Stub, der Timeout oder `500` liefert; Statuscode und Response-Body werden
    als reguläre Vorhersage geprüft, zusätzlich der WARNING-Logeintrag (z. B. über einen
    injizierten Logger/Log-Capture).

- **AC-6:** Given kein Auth-Kontext ist gesetzt (`UserIDFromContext` liefert den leeren String)
  / When `GET /api/forecast` aufgerufen wird, auch mit gültigen `lat`/`lon`-Parametern / Then
  antwortet der Handler mit `401`, und zwar bevor die Reservierung beim Core angefragt wird.
  - Test: `httptest.NewRequest` ohne gesetzten Auth-Kontext gegen `ForecastHandler` mit gültigen
    `lat`/`lon`; Statuscode `401` wird geprüft, und es wird zugesichert, dass der Core-Stub in
    diesem Testfall keinen Aufruf erhalten hat (Aufrufzähler des Stubs bleibt bei 0).

- **AC-7:** Given ein Request ohne Auth-Kontext trägt zusätzlich fehlerhafte Parameter (z. B.
  fehlendes `lat`) / When `GET /api/forecast` aufgerufen wird / Then antwortet der Handler mit
  `401`, nicht mit `400` — die Auth-Prüfung greift vor der Parametervalidierung.
  - Test: Request ohne Auth-Kontext und ohne `lat`-Parameter gegen `ForecastHandler`;
    Statuscode `401` (nicht `400`) wird geprüft. Ergänzend: die drei Bestandstestfälle in
    `internal/handler/forecast_test.go:16-102` (fehlendes `lat`, ungültiges `lat`, ungültiges
    `hours`) bekommen einen gültigen Auth-Kontext gesetzt und behalten ihre bestehende
    `400`-Erwartung unverändert.

- **AC-8:** Given der Python-Core lehnt eine Reservierungsanfrage ab (`allowed: false`) / When
  danach derselbe Zählerstand (globaler Zähler und Nutzer-Topf) der Zählerdatei erneut gelesen
  wird / Then ist der Zählerstand identisch mit dem Stand unmittelbar vor der abgelehnten
  Anfrage — die Ablehnung hat nichts gebucht.
  - Test: Gegen den echten Endpunkt mit `tmp_path`-Zählerdatei wird der Zustand herbeigeführt, in
    dem eine Reservierung für eine `user_id` sicher abgelehnt wird (globaler Zähler über der
    Schwelle, Nutzer-Topf über dem fairen Anteil); `calls` und `active_users` werden aus der
    Datei gelesen, die Reservierung wird ausgeführt und mit `allowed: false` bestätigt,
    anschließend werden `calls` und `active_users` erneut gelesen und auf Gleichheit mit dem
    Stand vorher geprüft.

- **AC-9:** Given ein durchgelassener Aufruf über `/api/forecast` erreicht den Python-Core /
  When die Reservierung mit `allowed: true` beantwortet wird / Then hat der Endpunkt zusätzlich
  genau einmal `record_cache_miss()` gebucht (die Cache-Miss-Zahl in der Zählerdatei ist um
  genau 1 höher als vor der Anfrage).
  - Test: Zählerstand `cache_misses` wird vor und nach einer erlaubten Reservierung aus der
    `tmp_path`-Zählerdatei gelesen und die Differenz von genau 1 geprüft.

## Known Limitations

- **Unterbuchung im Fehlerfall:** 2 Einheiten je Abruf sind die garantierte Untergrenze des
  Regelfalls (`doRequest` + `fetchUVData`). Läuft zusätzlich `tryFallback` oder eine der
  Anfragen durch die Retry-Schleife des Providers, kostet der reale Abruf mehr Kontingent, als
  gebucht wird. Die echten Zahlen bleiben über `internal/provider/openmeteo/calllog.go`
  nachmessbar; diese Scheibe bucht bewusst die Untergrenze, keine Schätzung mit Aufschlag.
- **Der Python-Router `GET /forecast` (`api/routers/forecast.py:42`) bleibt ungegatet.** Er ist
  von außen nicht erreichbar (Core lauscht auf `localhost:8000`, `enforce_core_auth` fail-closed
  seit #2142) und damit kein Umgehungsweg für diesen Deckel — derselbe Scope-Schnitt wie in
  `fix_1329_forecast_cache_budget.md` und in ADR-0075.
- **Zusätzliche Latenz im HTTP-Pfad:** jeder `/api/forecast`-Aufruf löst jetzt zusätzlich einen
  lokalen RPC zum Python-Core aus, der seinerseits unter der `fcntl`-Sperre der Zählerdatei
  schreibt — im ungünstigen Fall (parallele Schreiber) entsteht eine kurze Sperrwartezeit
  innerhalb des Go-Request-Handlings, bevor der eigentliche Open-Meteo-Abruf überhaupt beginnt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0076 (neu; Nummer geprüft und frei)
- **Rationale:** ADR-0015 Regel 1 nennt neue Domänenlogik als Python-Aufgabe, dieselbe ADR nennt
  in ihrer Zuständigkeitstabelle „Rate-Limiting" aber ausdrücklich als Go-Aufgabe — genau diese
  Spannung entsteht an diesem Endpunkt. ADR-0076 löst sie auf: die Kontingent-*Entscheidung*
  bleibt ausschließlich in `ForecastBudgetGate` (Python, ein Schreiber, unter `fcntl`); Go fragt
  sie über `/api/_internal/*` hinter `X-GZ-Core-Auth` (ADR-0062) ab und übersetzt das Ergebnis in
  einen HTTP-Status (`200`/`429`/fail-open `200`). Es entsteht kein Go-seitiger Schreiber auf
  `forecast_budget.json` und kein Nachbau von `allow()` in Go — beides wäre ein zweites Exemplar
  derselben Regel, das mit der Zeit vom Original abweichen kann (Präzedenz-Verstoß gegen die
  bereits getroffene Trennung der Schreibwege in `internal/provider/openmeteo/calllog.go:11-14`).
  ADR-0076 **ergänzt** ADR-0075, löst es nicht ab: ADR-0075 legt das Kontingent-Modell fest,
  ADR-0076 legt fest, wie ein zweiter Sprachraum (Go) an dieses Modell andockt, ohne es zu
  duplizieren.

  Die ADR-Datei selbst (`docs/adr/0076-*.md`) und der Indexeintrag in `docs/adr/README.md`
  gehören zur Implementierung (Phase 5) und werden von dieser Spec nicht angelegt.

## Changelog

- 2026-09-21: Initial spec created für #2391 (Scheibe S3 von #2150, Epic #2138)
