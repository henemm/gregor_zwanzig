---
entity_id: fix_1434_dpc_zonen_drift
type: module
created: 2026-07-31
updated: 2026-07-31
status: draft
version: "1.0"
tags: [official-alerts, dpc, observability, unavailable, scheduler-status]
workflow: fix-1434-dpc-zonen-sichtbarkeit
---

<!-- Issue #1434 -->

# Zonen-Drift beim italienischen Zivilschutz: nicht zuordenbare Warngebiete werden sichtbar

## Approval

- [ ] Approved

## Purpose

Die DPC-Warnquelle ordnet einen Ort über eine **eingecheckte, statische** Geometrie
(`data/dpc_zones.json`, 187 Zonen) seiner Warnzone zu, während die Warnstufen **tagesaktuell**
aus dem Bulletin kommen. Schneidet der italienische Zivilschutz seine Warnzonen neu — was er
zwischen Januar und Juli 2026 in Venetien nachweislich getan hat (8 → 25 Zonen) —, driften
beide auseinander und amtliche Hochwasser-/Erdrutsch-/Gewitterwarnungen fallen still aus dem
Ergebnis. Diese Spec macht das Auseinanderdriften **sichtbar**: für den Wanderer über den
bestehenden „nicht abrufbar"-Hinweis (#1348), für den Betrieb über den login-freien
Status-Endpunkt und die daran anschließende Alarmierung in `check-gregor20.sh`.

Sie behebt den Drift **nicht** automatisch — Laufzeit-Geometrie bleibt bewusst ausgeschlossen
(s. Known Limitations).

## Source

- **File:** `src/services/official_alerts/dpc.py`
- **Identifier:** `DpcSource.fetch()`, `_records_by_zone()`

> **Schicht:** Erkennung und nutzersichtbare Wirkung liegen im **Python-Core**
> (`src/services/official_alerts/`). Die betriebliche Aggregation liegt in der **Go-API**
> (`internal/scheduler/warn_service_health.go`), die das Diagnose-Journal direkt vom
> gemeinsamen Datenverzeichnis liest — kein Python-HTTP-Aufruf, exakt wie `BriefingHealth()`.
> Die Alarmschwelle selbst liegt **außerhalb dieses Repos** in `henemm-infra`.

## Der Befund: zwei Drift-Richtungen, nur eine ist heute sichtbar

| # | Richtung | Ort im Code | Heute | Wirkung auf den Nutzer |
|---|---|---|---|---|
| **A** | Bulletin nennt eine Zone, die die Geometrie nicht kennt | `dpc.py:114-119` `_records_by_zone()` | `logger.warning`, Zeile verworfen | **keine** — kein Ort kann dieser Zone zugeordnet werden |
| **B** | Geometrie nennt eine Zone, die das Bulletin nicht mehr führt | `dpc.py:227-229` `fetch()`, `row is None → return []` | **nichts, keine Spur** | **stilles „keine Warnung"** trotz möglicherweise bestehender amtlicher Warnung |

Beim Neuschnitt treten beide gleichzeitig auf. Der Wanderer merkt nur **B** — und genau der
Pfad protokolliert heute nichts.

**Messung 2026-07-31** gegen das echte Bulletin `20260730_1511`: beide Datensätze
(`today`/`tomorrow`) tragen **je 187 Zeilen mit 187 eindeutigen Codes**, deckungsgleich mit der
eingecheckten Geometrie — Drift in beide Richtungen aktuell **0**. Das Bulletin führt also
*jede* Zone, auch die ohne Warnung (`NESSUNA ALLERTA`). Daraus folgt für die Auslegung:
**ein fehlender Bulletin-Eintrag ist eine Anomalie, nicht „normales Schweigen"** — Pfad B darf
deshalb ohne Rauschsorge laut sein.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/official_alerts/warn_egress.py` (`mark_fetch_incomplete()`, `warn_egress.py:69-81`) | module | **Fertiger Haken für Pfad B** (aus #1397 S1c): markiert einen Abruf als „nicht vollständig abrufbar", ohne dass `cached_fetch()` selbst fehlschlug — kein neuer Mechanismus nötig |
| `src/services/official_alerts/base.py` (`get_official_alerts_with_status()`, Zeile 135-146) | module | Wertet den `observe_fetch_failure()`-Kontext aus und leitet daraus `unavailable` ab — der Weg, über den Pfad B nutzersichtbar wird |
| `src/services/official_alerts/warn_egress.py` (`log_warn_service_call()`, Zeile 212-254) | module | Bestehender Diagnose-Kanal `data/diagnostics/warn_service_calls.jsonl`; additiv erweiterbar, Präzedenz #1422 S1 (`ok`, `self_throttled`) |
| `internal/scheduler/warn_service_health.go` (`aggregateWarnServiceCalls`, `WarnServiceHealth`) | module | Aggregiert das Journal je Dienst; überspringt Zeilen ohne `ok`-Feld bereits heute (`entry.Ok == nil → continue`) — neue Ereigniszeilen brechen bestehende Leser daher nicht |
| `internal/scheduler/scheduler.go:533` | module | Einhängepunkt `warn_service_health` in `/api/scheduler/status` |
| `docs/specs/modules/warn_unavailable_hint.md` (#1348) | spec | Definiert den nutzersichtbaren Hinweis „amtliche Warnungen aktuell nicht abrufbar", den Pfad B auslöst |
| `docs/specs/modules/fix_1422_warn_ausfall_alarm.md` | spec | Vertragsmuster Kern↔Infra („Schnittstelle für Teil B"); diese Spec folgt ihm |
| `henemm-infra/scripts/check-gregor20.sh` (Abschnitt 2, ab Zeile 57) | reference | Der einzige Konsument, der aus dem Status einen Alarm macht — wertet heute `briefing_health` aus, `warn_service_health` **nicht** |
| `src/services/official_alerts/data/dpc_zones.json` | data | Die statische Geometrie, deren Alterung das Risiko erzeugt |

## Estimated Scope

- **LoC:** ~230–280 gesamt inkl. Tests über Python **und** Go — an der 250er-Grenze, daher
  **zwei Scheiben** (s. Implementation Details). Je Scheibe deutlich unter dem Limit.
- **Files:** 6 (2× Python-Quelle, 1× Go-Quelle, 2× Test, 1× Doku) + 1 Nachricht an `infra`
- **Effort:** medium

## Implementation Details

### Scheibe S1 — Erkennung und nutzersichtbare Wirkung (Python-Core)

1. **Pfad B erkennen** (`DpcSource.fetch()`): Liefert die Zonen-Zuordnung einen Code, den der
   Bulletin-Datensatz des Bezugstags nicht führt, ist das **kein** „keine Warnung", sondern
   „für diesen Ort nicht abrufbar". Der Abruf wird über den vorhandenen
   `warn_egress.mark_fetch_incomplete()` als unvollständig markiert und mit Zonencode
   protokolliert. Rückgabe bleibt fail-soft `[]` (ADR-0018) — die Wirkung entsteht über
   `base.py`, nicht über eine Ausnahme.
2. **Pfad A schärfen** (`_records_by_zone()`): Ein unbekannter Zonencode wird danach getrennt,
   ob die Zeile eine **echte** Warnstufe trägt (`ALLERTA GIALLA/ARANCIONE/ROSSA`, erkannt über
   das bestehende `_level_from_text()`) oder nur `NESSUNA ALLERTA`. Nur ersterer bedeutet
   tatsächlichen Verlust und wird als solcher vermerkt; letzterer bleibt ein leiser Hinweis.
3. **Diagnose-Zeile:** additiv in derselben Datei `data/diagnostics/warn_service_calls.jsonl`,
   als **eigene Ereigniszeile** **ohne** das Feld `ok`. Damit überspringt die bestehende
   Go-Aggregation sie automatisch (`entry.Ok == nil → continue`) und meldet keinen falschen
   Ausfall — die neue Auswertung in S2 liest sie gezielt. Schreibfehler werden geschluckt wie
   bei `log_warn_service_call()`: Beobachtung darf den Abruf nie beeinträchtigen.

   **Feldnamen (festgelegt in der RED-Phase, verbindlich für S1 und S2):**

   | Feld | Wert |
   |---|---|
   | `ts` | Zeitstempel UTC, ISO-8601 (wie bestehende Zeilen) |
   | `service` | `"dpc"` |
   | `zone_code` | der betroffene Zonencode |
   | `has_warning` | Pfad A: `true`, wenn die verworfene Bulletin-Zeile eine echte Warnstufe trägt. Pfad B: **immer `true`** — ob der fehlende Eintrag eine Warnung getragen hätte, ist prinzipiell unbekannt; da ein fehlender Eintrag nachweislich eine Anomalie ist (Messung oben), wird er bewusst konservativ als relevant geführt. Folge für Teil B: **jeder** Pfad-B-Fall ist ein ERROR-Kandidat, die Unterscheidung „mit/ohne Warnung" trägt dort keine Information. |
   | `drift` | Richtung: `"bulletin_only"` (Pfad A) oder `"geometry_only"` (Pfad B) |
   | `ok` | **nicht vorhanden** — bewusst weggelassen |

   Die Tests der RED-Phase (`tests/tdd/test_dpc_zone_drift.py`) filtern auf
   `"ok" not in entry` und `zone_code`; die Implementierung muss genau diese Namen
   verwenden.

### Scheibe S2 — Betriebszustand und Alarm-Anschluss (Go-API + Infra-Auftrag)

4. **Aggregation** in `warn_service_health.go`: je Dienst die Zahl nicht zuordenbarer Gebiete
   seit dem letzten Scan, getrennt nach „trägt Warnung" und „ohne Warnung", plus Zeitstempel
   des jüngsten Vorkommens. Fail-soft je Zeile wie bisher.
5. **Ausgabe** unter dem bestehenden Schlüssel `warn_service_health` in
   `/api/scheduler/status` — additiv, bestehende Felder unverändert.
6. **Auftrag an `infra`** per Inter-Instanz-Nachricht nach S2-Deploy: Auswertung in
   `check-gregor20.sh`, Schwelle als **ERROR** bei mindestens einem nicht zuordenbaren Gebiet
   **mit** Warnung, als **WARN** bei Vorkommen ohne Warnung. Die Schwellenlogik gehört
   ausdrücklich dorthin, nicht in dieses Repo (Muster #1422 Teil B / henemm-infra#150).

## Expected Behavior

- **Input:** Koordinate eines beobachteten Orts in Italien + das tagesaktuelle DPC-Bulletin.
- **Output:** unverändert die Liste amtlicher Warnungen; zusätzlich der Status
  „nicht abrufbar" für Orte, deren Zone das Bulletin nicht mehr führt.
- **Side effects:** Ereigniszeilen im bestehenden Diagnose-Journal; ein zusätzliches
  Zustandsfeld im login-freien Status-Endpunkt. Kein zusätzlicher Netzzugriff, kein
  Kontingentverbrauch — die Erkennung fällt beim ohnehin stattfindenden Abruf ab.

## Acceptance Criteria

### Scheibe S1 (Python-Core)

- **AC-1:** Given ein beobachteter Ort in Italien liegt in einem Warngebiet, das im
  tagesaktuellen amtlichen Bulletin nicht mehr geführt wird / When die amtlichen Warnungen für
  diesen Ort ermittelt werden / Then meldet das Ergebnis für diesen Ort „amtliche Warnungen
  nicht abrufbar" statt stillschweigend „keine Warnung"
  - Test: `tests/tdd/test_dpc_zone_drift.py` — Bulletin ohne den Zonencode des Orts,
    geprüft wird der `unavailable`-Status des echten Ermittlungswegs, nicht ein Log-Text

- **AC-2:** Given ein beobachteter Ort in Italien liegt in einem Warngebiet, das im Bulletin
  geführt wird und dort keine Warnung trägt / When die amtlichen Warnungen für diesen Ort
  ermittelt werden / Then bleibt das Ergebnis unauffällig — keine Warnung und **kein**
  „nicht abrufbar"-Hinweis, damit der Normalfall kein Dauerrauschen erzeugt
  - Test: `tests/tdd/test_dpc_zone_drift.py` — Gegenprobe zu AC-1 mit demselben Aufbau

- **AC-3:** Given das Bulletin führt ein Warngebiet, das die hinterlegte Gebietskarte nicht
  kennt, und dieses Gebiet trägt eine echte Warnstufe / When das Bulletin verarbeitet wird /
  Then ist dieser Fall in den Betriebsdaten als tatsächlicher Warnungsverlust erkennbar und
  vom harmlosen Fall ohne Warnstufe unterscheidbar
  - Test: `tests/tdd/test_dpc_zone_drift.py` — zwei unbekannte Zonencodes im selben Bulletin,
    einer mit `ALLERTA GIALLA`, einer mit `NESSUNA ALLERTA`; geprüft wird die geschriebene
    Betriebsdatenzeile, nicht der Logger

- **AC-4:** Given das Schreiben der Betriebsdaten schlägt fehl (z.B. Zielverzeichnis nicht
  beschreibbar) / When ein Ort mit gültiger Zuordnung abgefragt wird / Then liefert die Quelle
  ihre amtlichen Warnungen unverändert vollständig aus — die Beobachtung darf den Abruf unter
  keinen Umständen beeinträchtigen
  - Test: `tests/tdd/test_dpc_zone_drift.py` — Journal-Pfad auf ein nicht beschreibbares Ziel
    gesetzt, geprüft wird die zurückgegebene Warnliste

- **AC-4b (Präzisierung von AC-4, ergänzt nach der RED-Phase):** Given das Schreiben der
  Betriebsdaten schlägt fehl **und** gleichzeitig liegt ein Drift-Fall vor / When die
  amtlichen Warnungen ermittelt werden / Then bricht nichts ab und die übrigen Orte werden
  unverändert versorgt — der Drift-Vermerk läuft ausgerechnet dann, wenn ohnehin etwas nicht
  stimmt, und darf die Lage nicht verschlimmern
  - Test: `tests/tdd/test_dpc_zone_drift.py` — nicht beschreibbarer Journal-Pfad **plus**
    unbekannter Zonencode im Bulletin bzw. Zone fehlt im Bulletin; geprüft wird, dass der
    Abruf durchläuft und der `unavailable`-Status trotzdem korrekt gesetzt wird
  - Begründung der Ergänzung: der ursprüngliche AC-4-Test durchläuft ausschließlich den
    **bestehenden** Schreibweg (`log_warn_service_call()`), nicht den neuen
    (`log_zone_drift()`) — vom Implementierer selbst offengelegt. Keine Scope-Erweiterung,
    sondern derselbe Satz „Beobachtung darf den Abruf nie beeinträchtigen", auf den neuen
    Weg angewandt.

### Scheibe S2 (Go-API + Infra-Anschluss)

- **AC-5:** Given im Beobachtungszeitraum traten nicht zuordenbare Warngebiete auf, davon
  mindestens eines mit echter Warnstufe / When der Systemzustand über den ohne Anmeldung
  erreichbaren Status-Endpunkt abgefragt wird / Then weist der Zustand diese Vorkommen
  getrennt nach „mit Warnung" und „ohne Warnung" samt jüngstem Zeitpunkt aus
  - Test: `internal/scheduler/warn_service_health_test.go` — Journal mit beiden Zeilenarten,
    geprüft wird die Rückgabe von `WarnServiceHealth()`

- **AC-6:** Given es trat im gesamten Beobachtungszeitraum kein einziges nicht zuordenbares
  Warngebiet auf / When der Systemzustand abgefragt wird / Then enthält der Zustand keinen
  erfundenen Befund und keine Nullwerte, die von einem echten Vorkommen nicht unterscheidbar
  wären — analog zur bestehenden Regel „keine Aktivität ist kein Ausfall"
  - Test: `internal/scheduler/warn_service_health_test.go` — Gegenprobe zu AC-5

- **AC-7:** Given das Diagnose-Journal enthält die neuen Ereigniszeilen / When der bestehende
  Ausfall-Zustand je Warndienst (letzter Erfolg / letzter Versuch) ermittelt wird / Then bleibt
  dieser unverändert korrekt — die neuen Zeilen werden dort weder als Erfolg noch als
  Fehlschlag gewertet
  - Test: `internal/scheduler/warn_service_health_test.go` — gemischtes Journal aus alten und
    neuen Zeilen, geprüft werden `last_success_at`/`last_attempt_at`

- **AC-8:** Given der Stand ist auf Staging ausgerollt und ein Scheduler-Zyklus ist
  abgeschlossen / When der Status-Endpunkt dort abgefragt wird / Then ist das neue Zustandsfeld
  vorhanden und plausibel (bei intakter Gebietskarte ohne Vorkommen), sodass die
  Infra-Auswertung dagegen bauen kann
  - Test: Staging-Abruf gegen `/api/scheduler/status` im Rahmen der E2E-Verifikation
    (kein pytest/Go-Test)

## Schnittstelle für Teil B (henemm-infra, NICHT Gegenstand dieser Spec)

Nach S2-Deploy per Inter-Instanz-Nachricht an `infra` zu beauftragen — analog #1422 Teil B
(henemm-infra#150):

- **Quelle:** `GET http://localhost:8090/api/scheduler/status`, Feld `warn_service_health`
  (ohne Anmeldung erreichbar, wird von `check-gregor20.sh` bereits abgefragt).
- **Neue Teilstruktur:** je Warndienst die Zahl nicht zuordenbarer Gebiete, getrennt nach
  „mit Warnung" / „ohne Warnung", plus Zeitstempel des jüngsten Vorkommens.
- **Erwartete Auswertung:** mindestens ein Vorkommen **mit** Warnung → ERROR („amtliche
  Warnung nicht zuordenbar — Gebietskarte veraltet"); nur Vorkommen ohne Warnung → WARN.
  Fehlendes Feld → keine Evidenz, kein Alarm (nie als Fehler werten).
- **Behebung im Alarmfall:** Gebietskarte `dpc_zones.json` neu erzeugen und einchecken —
  ein bewusster, manueller Wartungsschritt in diesem Repo.

## Known Limitations

- **Kein Selbstheilen.** Die Geometrie wird nicht zur Laufzeit nachgezogen. Shapefile-Parsing
  zur Laufzeit wurde in #1427 bewusst verworfen (Präzedenz `rasterio`/#1162 legte Staging
  14 Minuten lahm). Diese Spec meldet den Drift, sie behebt ihn nicht.
- **Pfad A bleibt ortsunabhängig.** Ein unbekannter Bulletin-Zonencode betrifft keinen
  konkreten Nutzer; er ist ein reines Frühwarnsignal für den Betrieb.
- **Wirkung erst mit Teil B vollständig.** Bis `check-gregor20.sh` das Feld auswertet, ist der
  betriebliche Teil ein Zustandswert ohne Konsument — genau die Lücke, die #1422 hinterlassen
  hat. Deshalb ist der Auftrag an `infra` Teil der Definition of Done dieses Issues.
- **Kein Nachweis über einen echten Neuschnitt möglich.** Der Fall lässt sich nur mit einem
  konstruierten Bulletin nachstellen; ein echter DPC-Neuschnitt ist nicht herbeiführbar. Die
  Fixtures bilden den real gemessenen Aufbau des Bulletins nach (187 Zeilen, Felder
  `Zona_all`/`Nome_zona`/`Criticita`/`Idrogeo`/`Temporali`/`Idraulico`).
- **Andere statische Geo-Dateien tragen dasselbe Risiko** (`massif_polygons.json`,
  `department_polygons.json`) — bewusst nicht mitbehandelt, Zuschnitt bleibt auf DPC. Als
  Sammel-Eintrag für #1199 vorgesehen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine — kein neues ADR nötig.
- **Rationale:** Die Spec bewegt sich vollständig innerhalb bestehender Entscheidungen:
  ADR-0018 (Fail-soft in Warnquellen — die Quelle wirft weiterhin nicht und erfindet keine
  Warnung), ADR-0016 (additive Quellen — die Registrierung bleibt unberührt) sowie dem in
  #1422 etablierten, nicht als ADR geführten Vertragsmuster „Kern liefert Rohwerte, Infra
  entscheidet über Alarmschwellen". Keine Entscheidungsfläche wird verschoben.

## Changelog

- 2026-07-31: Initial spec created (Issue #1434, Scheiben S1/S2, PO-Entscheide V2 +
  nutzersichtbarer Hinweis)
