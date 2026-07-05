# Architektur-Roadmap 2026-07

**Status:** Entscheidungsvorlage für den PO
**Grundlage:** `docs/analysis/architektur-drift-2026-07-05.md` (Rev. 2, gegengecheckt)
**Autor:** Claude (Tech Lead), 2026-07-05

Diese Roadmap ersetzt die Phasen A–E aus der Drift-Analyse Rev. 1. Umsetzung läuft
**ausschließlich über GitHub Issues** (Projektregel) — dieses Dokument ist die strategische
Klammer, keine Aufgabenliste. Jede Phase wird nach PO-Freigabe in Issues geschnitten, die einzeln
durch den OpenSpec-Workflow gehen (LoC-Limit 250 pro Workflow → kleine Schnitte sind Pflicht,
kein Big-Bang-Refactoring).

---

## E-0: Die vorgelagerte Entscheidung — Zielarchitektur

**Problem:** ADR-0001 (2026-04) beschreibt den heutigen Dual-Stack (Go-API + Python-Core) als
**Übergangszustand** — „bis das Python-Backend abgelöst ist". Die Ablösung ist nie erfolgt.
Seitdem ist die gesamte Produktlogik (Provider, Risk Engine, Renderer, Scheduler, Alerts,
Inbound-Handler) im Python-Core **weitergewachsen**. Jede größere Refactoring-Investition hängt
davon ab, ob diese Schicht Zukunft hat.

### Optionen

| | Option A: Go-Vollmigration abschließen | **Option B: Dual-Stack formalisieren (Empfehlung)** | Option C: Weiter wie bisher |
|---|---|---|---|
| **Was** | Wetter-Pipeline, Renderer, Scheduler nach Go portieren; Python stirbt | Neue ADR: Go = API/Auth/Store/Frontend-Serving, Python = Wetter-Domäne/Rendering/Scheduling — **dauerhaft**, mit klarer Vertragsgrenze (HTTP, `docs/reference/api_contract.md`) | Keine Entscheidung, Drift bleibt |
| **Aufwand** | Monate; komplette Pipeline-Neuschreibung inkl. aller Mail-/Telegram-/SMS-Renderer | 1 ADR + Doku-Fixes; danach gezieltes Refactoring | 0 |
| **Risiko** | Hoch: monatelang zwei Wahrheiten, Golden-Files decken den heutigen Funktionsumfang nicht mehr ab; kein Nutzer-Mehrwert währenddessen | Niedrig: legalisiert den Ist-Zustand, macht Investitionen in Python-Schichtung legitim | Doku bleibt falsch, jede Investitionsfrage bleibt unentscheidbar |
| **Nutzen** | Ein Stack, statische Typen überall | Klarheit; alle folgenden Phasen werden entscheidbar | — |

### Empfehlung: **Option B**

Begründung: Der Python-Core ist das Produkt — funktionierend, produktiv, über Staging-Gates
abgesichert. Eine Go-Portierung der gesamten Pipeline wäre eine monatelange Investition ohne
sichtbaren Nutzerwert, mit hohem Regressionsrisiko in genau dem Bereich (Mail-/Kanal-Rendering),
der die strengsten Validierungspflichten hat. Der Dual-Stack ist kein Makel, wenn die Grenze sauber
gezogen ist: Go macht das, worin es stark ist (API, Auth, Persistenz, Frontend-Serving), Python
das, worin der Bestand steckt (Wetter-Domäne, Rendering, Scheduling). ADR-0001 wird nicht
verworfen, sondern per Folge-ADR präzisiert: Die Migration von NiceGUI weg **ist abgeschlossen**
(UI ist SvelteKit), die Backend-Ablösung wird **aufgehoben**.

**PO-Aktion:** „go" für Option B (oder A/C mit Begründung). Danach schreibe ich die Folge-ADR.

---

## Phasen

### Phase 0 — Sofort, unabhängig von E-0 (Aufwand: 1–2 Tage)

Risikoarm, kein Code-Verhalten betroffen. Issues werden mit dieser Vorlage angelegt.

1. **Doku-Drift beheben:** `AGENTS.md` (`api/` = Python-Core), `docs/specs/_template.md`,
   `docs/features/architecture.md` (Signal raus, Produktivpfad statt CLI-Fluss).
2. **CI-Ausbau (secrets-frei):** Go-Tests (102 Dateien), Frontend-Unit-Tests (126 Dateien) und
   `svelte-check` in `ci.yml`. `tests/tdd/` bleibt bewusst draußen (braucht Staging/Creds).
   `mypy`: installieren **oder** `[tool.mypy]` entfernen (Empfehlung: erst entfernen, Einführung
   ist ein eigenes Projekt). Lint-Pflicht erst nach einmaliger Ruff-Bereinigung.
   *Hinweis:* `svelte-check` hat aktuell 40 Fehler — der CI-Schritt startet als Baseline-Gate
   („nicht schlechter werden") oder nach Fehlerbereinigung in Phase 3.
3. **Inbound-`"default"`-Fallback prüfen** (Sicherheit): Was erhält ein unbekannter
   Absender/Chat? Befund → Fix-Issue.
4. **Arbeitsverzeichnis-Hygiene:** untrackte Reste (`src/web/`-Leichen, `validator.env.bak*`,
   Test-Fixtures `data/users/tdd-*` im Prod-Datenverzeichnis) aufräumen bzw. Test-Fixtures in
   einen Test-Datenpfad verlagern (Anschluss an #1013/#1014).

### Phase 1 — Go-Refactoring (nach Phase 0; Aufwand: 1–2 Wochen, in ~5 Issues)

Unabhängig vom Ausgang von E-0 sinnvoll (Go bleibt in jeder Option die API-Schicht):

1. `internal/store/store.go` (831 Zeilen) in entitätsbezogene Dateien aufteilen (reine
   Dateiorganisation, gleiche Tests).
2. Router aus `cmd/server/main.go` nach `internal/router/` auslagern; Inline-Handler entfernen.
3. Domain-Logik aus Handlern in Service-Funktionen ziehen — **inkrementell beim Anfassen**, kein
   Sweep (die Handler sind gut getestet: 51 Testdateien auf 24 Handler; das Sicherheitsnetz
   existiert).
4. Telegram-Token-Store als Dependency injizieren statt Package-State.

### Phase 2 — Python-Schichtung (**nur nach E-0 = Option B**; Aufwand: 1–2 Wochen, in ~6 Issues)

1. Die 7 Service-Dateien mit Renderer-/Transport-Imports entkoppeln: Services liefern DTOs.
2. `NotificationService` als zentrale Verteilerschicht (Renderer wählen, Transport aufrufen).
3. `src/services/comparison_renderers.py` nach `src/output/renderers/` verschieben.
4. `src/output/` vs. `src/outputs/` vs. `src/formatters/` konsolidieren → **braucht ADR**
   (AGENTS.md-Pflicht) und Abstimmung mit `renderer_mail_gate` (Gate-Pfadmuster!).
5. Duplikate zentralisieren: `degrees_to_compass` (5×), `haversine` (3×).
6. Router-Verletzungen (`scheduler`, `validator`, `debug`, `notify`) auflösen; #977 (toter Import
   in `debug.py`) fällt hier mit.

**Wichtig:** Der Mail-Rendering-Pfad hat harte Gates (Modus-Matrix-Test + Briefing-Validator gegen
echte Staging-Mail). Jedes Issue in dieser Phase muss diese Nachweise erbringen — das ist der
Grund, warum die Phase in kleine Schnitte zerlegt wird.

### Phase 3 — Frontend-Stabilisierung (parallel möglich; Aufwand: 2–3 Wochen verteilt)

1. **API-Base zentralisieren** (20 Duplikate → 1 Modul) — schneller, risikoarmer Gewinn, zuerst.
2. `svelte-check`-Fehler 40 → 0, dann als CI-Gate scharf schalten (Reihenfolge mit Phase 0.2).
3. Große Komponenten (`TripNewEditor` 1061, `+page.svelte` 966, `WeatherMetricsTab` 845) beim
   nächsten fachlichen Anfassen splitten — **kein** eigenständiges Split-Projekt.
4. Atoms-/Wrapper-Layer: Entscheidung liegt bei Claude Design → Design-Request stellen, nicht
   selbst umbauen (Projektregel).

### Phase 4 — Test-Konsolidierung (parallel, andockend an #984; Aufwand: ~1 Woche)

1. Test-Drift-Audit #984 ausweiten: dauerhaft rote Tests auf `main` sind ein Gate-Erosionsrisiko
   (#971, #979, #1008, #1011 gehören in dieselbe Bereinigung).
2. Die 7 CI-ausgeschlossenen Unit-Dateien: **reparieren oder löschen** (sie sind rot, teils
   NiceGUI-Altlasten) — nicht „reaktivieren".
3. Staging-E2E-Blocker beheben (#987, #973: Basic-Auth) — Voraussetzung für verlässliche
   Playwright-Läufe.

---

## Reihenfolge und Investitionsrahmen

| Prio | Phase | Abhängigkeit | Aufwand |
|------|-------|--------------|---------|
| 1 | E-0 entscheiden | PO | 1 Gespräch + 1 ADR |
| 2 | Phase 0 | — | 1–2 Tage |
| 3 | Phase 1 (Go) | Phase 0 | 1–2 Wochen |
| 4 | Phase 2 (Python) | **E-0 = B** | 1–2 Wochen |
| 5 | Phase 3 (Frontend) | parallel | 2–3 Wochen verteilt |
| 6 | Phase 4 (Tests) | parallel | ~1 Woche |

Gesamtrahmen wie in der Analyse: **2–4 Wochen fokussierter Invest über die nächsten Quartale**,
verzahnt mit Feature-Arbeit (Phasen 3.3 und 1.3 laufen „beim Anfassen" mit, kosten also kaum
eigenes Budget).

**Mitarbeit von Kimi:** siehe `docs/project/ai-collaboration-kimi.md` — Phasen 1.1, 3.1 und Teile
von Phase 4 sind als Kimi-geeignete Pakete markierbar (mechanisch, testgesichert, ohne
Staging-Credential-Pflichten).
