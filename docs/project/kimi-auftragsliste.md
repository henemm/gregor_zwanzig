# Kimi-Auftragsliste

**Stand:** 2026-07-05 · **Regeln:** `docs/project/ai-collaboration-kimi.md` (Abschnitte 3.3 + 4)
**Pflicht-Lektüre vor jedem Auftrag:** `AGENTS.md`, `docs/adr/0015-dual-stack-zielarchitektur.md`,
das jeweilige GitHub-Issue (Volltext unten referenziert; bei fehlendem GitHub-Zugriff steht der
Auftragskern hier).

## Arbeitsablauf (für jeden Auftrag identisch)

1. Workspace anlegen: `bash .claude/tools/gz-workspace new kimi-<issuenr>` (im Hauptrepo
   `/home/hem/gregor_zwanzig` aufrufen; erzeugt isolierten Klon auf Branch `ws/kimi-<issuenr>`).
2. Implementieren — **nur** im Workspace. Diff klein halten (≤ 250 geänderte Zeilen).
3. Lokal beweisen: alle ohne Secrets lauffähigen Tests ausführen
   (`go test ./...`, Frontend-Unit-Tests, `uv run pytest <lokal lauffähige Tests>`).
   Protokoll als `TESTLOG.md` im Workspace-Root ablegen — **nicht committen**.
4. Committen (aussagekräftige Message mit Issue-Nr.) und Branch pushen:
   `git push origin ws/kimi-<issuenr>` (origin = lokales Hauptrepo — das ist die Abgabe).
5. Fertig melden (an den PO/Claude): Branch-Name + 3-Satz-Zusammenfassung + warum
   verhaltensneutral.

**Harte Verbote (unverändert):** kein Push/Merge nach `main` · nichts unter `.claude/` ändern ·
keine Secrets lesen (`.env`, `validator.env*`, `/etc/henemm/secrets.env`) · keine Läufe gegen
Produktion oder Staging · keine Mail-/Telegram-/SMS-Sends (auch keine „Tests" dafür — Zustell-
Nachweise macht Claude) · kein `git stash`, kein `git add -A` · Schema-Dateien
(`internal/model/*.go`, `internal/store/store.go`-Persistenzformate, `src/app/models.py`,
`src/app/loader.py`) nur strukturell anfassen, nie Feldformate ändern.

## Warteschlange (Reihenfolge = Priorität)

| # | Issue | Auftrag | Abhängig von |
|---|-------|---------|--------------|
| 1 | #1017 | Doku-Drift beheben | — |
| 2 | #1028 | Go: Routing aus main.go nach internal/router/ | — |
| 3 | #1029 | Go: Telegram-Token-Store als Dependency | #1028 integriert (beide ändern main.go-Wiring) |
| 4 | #1027 | Router-Presentation-Imports + Duplikate | — |
| 5 | #1025 | comparison_renderers verschieben + Compare/Preview-Imports | — |
| 6 | #1022 | NotificationService + Scheduler-Pfad | — |
| 7 | #1023 | trip_alert über NotificationService | #1022 integriert |
| 8 | #1024 | Inbound-Reader über NotificationService | #1022 integriert |

~~#1018 (CI-Ausbau)~~ — entfallen: bereits umgesetzt durch parallele Claude-Session
(Commit a283a5ef, 2026-07-05). Nicht anfassen.

„Integriert" heißt: Claude hat den Vorgänger-Branch nach Review + Staging-Nachweis auf `main`
gebracht — vorher NICHT auf dem alten Stand weiterbauen, sondern neuen Workspace von frischem
`origin/main` ziehen.

## Auftragskerne (Kurzfassung; Details im jeweiligen Issue)

**#1017 — Doku-Drift:** `AGENTS.md` (Z. 8 + 127): `api/` gehört zum Python-Core, Go-API =
`cmd/server/` + `internal/`. Dasselbe in `docs/specs/_template.md`. In
`docs/features/architecture.md`: Signal-Erwähnungen entfernen (Z. 10, 535 — Signal ist seit
#610 raus), Produktivpfad = Python-Core-Pipeline statt CLI-Fluss. NUR Doku-Dateien anfassen.

**#1028 — Router-Auszug:** `cmd/server/main.go` → Routing-Aufbau nach `internal/router/`
(z. B. `router.New(deps) http.Handler`), Inline-Handler in benannte Funktionen unter
`internal/handler/`. Kein Pfad, keine Middleware-Reihenfolge ändern. Nachweis: Routen-Inventar
vorher/nachher identisch + `go test ./...` grün.

**#1029 — Token-Store-Injektion:** Package-Level-State für Telegram-Tokens in injizierte
Abhängigkeit überführen (Konstruktor-Wiring in main). `go test ./...` grün.

**#1027 — Router-Imports + Duplikate:** (A) `api/routers/{scheduler,validator,debug,notify}.py`:
outputs/renderers-Direktimporte hinter Service-Grenze ziehen; in `debug.py` den toten Import
`outputs.radar_alert` beheben (#977). (B) `degrees_to_compass` (5 Definitionen) und `haversine`
(3 Definitionen) auf je EINE Quelle zusammenführen, Alt-Aufrufer umstellen.

**#1025 — comparison_renderers:** Datei von `src/services/` nach `src/output/renderers/`
verschieben (reine Verschiebung + Import-Anpassungen). Zusätzlich `compare_subscription.py`
und `preview_service.py`: Render-Aufrufe an EINER Stelle bündeln. Lokal lauffähige Tests laufen
lassen; Compare-Mail-Zustellnachweis macht Claude.

**#1022 — NotificationService:** Neue Klasse (Vorschlag `src/services/notification_service.py`
oder `src/output/notification_service.py` — Begründung mitliefern): nimmt Report-DTOs, wählt
Renderer, ruft Transporte. `trip_report_scheduler.py` vollständig darauf umstellen (verliert
alle formatters/output/outputs-Importe). Lokal beweisen: `tests/tdd/test_issue_811_mode_matrix.py`
grün + bestehende Scheduler-Tests grün. Zustell-/Validator-Nachweis macht Claude.

**#1023 / #1024 — Folge-Entkopplungen:** wie im Issue beschrieben, erst nach #1022-Integration.

