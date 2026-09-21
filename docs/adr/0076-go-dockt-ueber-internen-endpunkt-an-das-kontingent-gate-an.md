# ADR-0076: Go dockt über einen internen Core-Endpunkt an das Kontingent-Gate an, statt die Entscheidung nachzubauen

- **Status:** Akzeptiert
- **Datum:** 2026-09-21
- **Bezug:** GitHub-Issue #2391 (Scheibe S3 von #2150, Epic #2138 Multi-User), Spec
  `docs/specs/modules/forecast_go_pfad_kontingent.md`, **ergänzt ADR-0075** (Forecast-Budget-
  Fairness je Nutzer), löst die Spannung in ADR-0015 (Dual-Stack-Zuständigkeit) auf, trägt auf
  ADR-0062 (`X-GZ-Core-Auth`) und ADR-0003 (Mandantentrennung)

## Kontext

`GET /api/forecast` wird vom Go-Prozess beantwortet (`internal/handler/forecast.go`) und ruft
Open-Meteo über den Go-Provider direkt ab. Damit umgeht dieser Weg das Tageskontingent-Gate
`ForecastBudgetGate` (`src/services/forecast_budget.py`) vollständig: ein Abruf über
`/api/forecast` zählt weder gegen den globalen Topf noch gegen den Nutzer-Topf aus ADR-0075.
Ein einzelner Nutzer kann über diesen Weg das Kontingent aller anderen aufbrauchen — genau der
Effekt, den ADR-0075 für die Python-Pfade abgestellt hat.

Die Zuständigkeitsfrage ist dabei nicht eindeutig vorgezeichnet: ADR-0015 Regel 1 weist neue
Domänenlogik dem Python-Core zu und lässt Go „API-Klebstoff" sein, nennt in seiner
Zuständigkeitstabelle „Rate-Limiting" aber ausdrücklich als Go-Aufgabe. An diesem Endpunkt
treffen beide Sätze aufeinander.

## Entscheidung

1. **Die Kontingent-Entscheidung bleibt ausschließlich in `ForecastBudgetGate` (Python).** Es
   gibt genau einen Schreiber auf `forecast_budget.json`, unter `fcntl`-Sperre, mit genau einer
   Fassung der dreistufigen Regel aus ADR-0075. Ein Nachbau von `allow()` in Go ist verworfen:
   das wäre ein zweites Exemplar derselben Regel, das mit der Zeit vom Original abweicht.
   Präzedenz ist die bereits getroffene Trennung der Schreibwege in
   `internal/provider/openmeteo/calllog.go:11-14`.

2. **Go fragt die Entscheidung über einen internen Core-Endpunkt ab.**
   `POST /api/_internal/forecast-budget/reserve?user_id=<auth>&priority=polling` prüft **und**
   bucht in einem Aufruf und antwortet mit `{"allowed": true}` bzw.
   `{"allowed": false, "retry_after_s": <Sekunden bis UTC-Mitternacht>}`. Der Endpunkt liegt wie
   alle `/api/_internal/*`-Routen hinter `X-GZ-Core-Auth` (ADR-0062, fail-closed).

3. **Auf der Leitung reisen nur `user_id` und `priority`.** Die Zahl der gebuchten Einheiten (2:
   `doRequest` + `fetchUVData` laufen im Regelfall unbedingt) ist eine Konstante **im
   Python-Endpunkt**, kein Schnittstellen-Parameter — sonst nähme der Core jede vom Aufrufer
   geschickte Zahl an, statt selbst zu wissen, was ein Forecast-Abruf kostet.

4. **Die `user_id` kommt ausschließlich aus dem Auth-Kontext** (`middleware.UserIDFromContext`),
   nie aus einem Client-Parameter (ADR-0003, Muster `proxy.go:appendUserID`). Ohne Kennung
   antwortet der Handler `401` — **bevor** die Reservierung angefragt wird, damit der Core nie auf
   eine leere oder fremde Kennung bucht. Ein `"default"`-Rückfall ist ausgeschlossen (ADR-0075
   Punkt 4).

5. **Go übersetzt das Urteil nur in einen HTTP-Status:** `allowed:true` → Abruf und `200`,
   `allowed:false` → `429` mit `Retry-After` und `{"error": "budget_exceeded", "detail": ...}`
   ohne Abruf.

6. **Fail-open bleibt die Regel.** Ist der Core nicht erreichbar, läuft die Anfrage in einen
   Timeout oder antwortet er mit einem Status ungleich `200`, ruft der Handler die Vorhersage
   trotzdem ab (`200`, Verhalten wie vor dieser Änderung) und macht den verschluckten Fehler als
   `WARNING` im Log sichtbar. Ein kaputter Zähler darf nie einen Abruf blockieren — dieselbe
   Semantik, die `ForecastBudgetGate` seit #1329 trägt.

ADR-0076 **ergänzt** ADR-0075 und löst es nicht ab: ADR-0075 legt das Kontingent-Modell fest,
ADR-0076 legt fest, wie ein zweiter Sprachraum (Go) an dieses Modell andockt, ohne es zu
duplizieren.

## Konsequenzen

- Jeder `/api/forecast`-Aufruf löst zusätzlich einen lokalen RPC zum Python-Core aus, der unter
  der `fcntl`-Sperre der Zählerdatei schreibt. Im ungünstigen Fall (parallele Schreiber) entsteht
  eine kurze Sperrwartezeit im Go-Request-Handling, bevor der Open-Meteo-Abruf überhaupt beginnt.
- Gebucht wird die **Untergrenze** des Regelfalls (2 Einheiten). Läuft zusätzlich `tryFallback`
  oder eine Retry-Schleife des Providers, kostet der reale Abruf mehr Kontingent, als gebucht
  wird — bewusste Unterbuchung statt Schätzung mit Aufschlag; die echten Zahlen bleiben über
  `internal/provider/openmeteo/calllog.go` nachmessbar.
- Der Python-Router `GET /forecast` (`api/routers/forecast.py`) bleibt ungegatet. Er ist von außen
  nicht erreichbar (Core lauscht auf `localhost:8000`, `enforce_core_auth` fail-closed seit #2142)
  und damit kein Umgehungsweg — derselbe Scope-Schnitt wie in ADR-0075.
- Jeder weitere Go-Pfad, der Open-Meteo anzapft, geht denselben Weg über diesen Endpunkt. Ein
  Go-seitiger Schreiber auf `forecast_budget.json` bleibt ausgeschlossen.

## Verworfene Alternativen

1. **`allow()` in Go nachbauen und die Zählerdatei aus beiden Prozessen schreiben.** Zwei
   Schreiber auf derselben Datei unter zwei Sperr-Implementierungen, zwei Fassungen der
   dreistufigen Regel — verworfen aus genau dem Grund, aus dem `calllog.go` die Schreibwege
   bereits trennt.
2. **Die Buchung dem Provider-Aufruf nachschalten (erst abrufen, dann melden).** Der Deckel
   griffe dann immer einen Abruf zu spät und schützte das Kontingent nicht, das er bewachen soll.
3. **Die Zahl der Einheiten als Query-Parameter `units`.** Ließe Handler und Gate
   auseinanderdriften; der Core kennt die Kosten eines Forecast-Abrufs selbst.
4. **Fail-closed bei unerreichbarem Core (`503`).** Ein Ausfall des Zählers legte damit die
   Vorhersage-Fläche lahm — die Fail-open-Semantik aus ADR-0075 Punkt 3 gilt auch hier.
