# ADR-0015: Dual-Stack (Go + Python) als dauerhafte Zielarchitektur

- **Status:** Akzeptiert (PO-Entscheidung E-0, „go" 2026-07-05)
- **Datum:** 2026-07-05
- **Bezug:** [ADR-0001](0001-go-sveltekit-migration.md) (präzisiert dessen Endzustand),
  `docs/project/architektur-roadmap-2026-07.md` (Entscheidung E-0),
  `docs/analysis/architektur-drift-2026-07-05.md` (Rev. 2, Abschnitt 5.1)

## Kontext

ADR-0001 (2026-04) beschloss die Migration Python/NiceGUI → Go/SvelteKit und beschrieb den
parallelen Betrieb zweier Stacks als **Übergangszustand** — „bis das Python-Backend abgelöst ist".

Die Realität drei Monate später: Das NiceGUI-UI ist vollständig abgelöst (SvelteKit, Issue #129),
aber das Python-Backend wurde nie ersetzt — im Gegenteil, die gesamte Produktlogik ist dort
**weitergewachsen**: Provider-Adapter, Risk Engine, alle Kanal-Renderer (E-Mail/Telegram/SMS),
Scheduler, Alert-System, Inbound-Handler. Das Go-Backend trägt API, Auth, Persistenz (Store)
und den Proxy zum Python-Core. Die Architektur-Drift-Analyse (2026-07-05) zeigte: Fast alle
Doku-/Struktur-Drifts sind Symptome dieses nie erreichten Endzustands, und jede größere
Refactoring-Investition war unentscheidbar, solange offen blieb, ob die Python-Schicht Zukunft hat.

## Entscheidung

Der Dual-Stack ist **nicht länger Übergangszustand, sondern Zielarchitektur**. Die in ADR-0001
vorgesehene Ablösung des Python-Backends wird **aufgehoben**. Es gilt eine dauerhafte,
verbindliche Zuständigkeitsgrenze:

| Schicht | Technologie | Zuständigkeit |
|---------|-------------|---------------|
| **Frontend** | SvelteKit (`frontend/`) | Web-UI (Desktop-Planungstool) |
| **API-Backend** | Go (`cmd/server/`, `internal/`) | REST-API (Port 8090), Auth/Sessions, Mandantentrennung (`s.WithUser`), Persistenz/Store, Rate-Limiting, Proxy zum Python-Core |
| **Domain-Core** | Python (`api/`, `src/`) | Wetter-Domäne: Provider, Normalisierung, Risk Engine, Aggregation, alle Kanal-Renderer und -Transporte, Scheduler, Alerts, Inbound-Handler (FastAPI, Port 8000) |

**Vertragsgrenze** zwischen den Backends ist HTTP mit den DTOs aus
`docs/reference/api_contract.md` (Single Source of Truth).

Daraus folgende Regeln:

1. **Neue Domain-/Wetter-/Rendering-Logik entsteht im Python-Core**, nicht im Go-Backend.
   Go-Handler bleiben API-Klebstoff + Persistenz (bestehende Domain-Logik in Handlern wird
   gemäß Roadmap Phase 1 inkrementell in Service-Funktionen gezogen, nicht nach Python portiert).
2. **Neue API-/Auth-/Persistenz-Belange entstehen im Go-Backend.** Der Python-Core bekommt
   keine eigene Auth und keine neuen direkt exponierten Endpoints; er bleibt hinter dem Go-Proxy
   (interne Ports nur für Betrieb/Validierung).
3. **Keine Logik-Duplizierung zwischen den Stacks.** Wo heute Doppel-Logik existiert
   (z. B. Schema-Migrationen im Go-Schreibpfad vs. Python-Loader, siehe Issue #1000), ist pro
   Fall genau EINE Seite als Owner zu bestimmen und die andere abzubauen.
4. Investitionen in die Python-Binnenstruktur (Roadmap Phase 2: Service-/Renderer-Entkopplung,
   `NotificationService`) sind damit legitimiert und erwünscht.

## Verworfene Alternativen

- **Go-Vollmigration abschließen (ADR-0001 wörtlich zu Ende führen)** — verworfen: Die
  Wetter-Pipeline inkl. aller Kanal-Renderer ist der funktionierende, staging-abgesicherte Kern
  des Produkts. Eine Portierung wäre eine monatelange Neuschreibung ohne Nutzerwert, mit dem
  höchsten Regressionsrisiko genau in dem Bereich (Mail-/Kanal-Rendering) mit den strengsten
  Validierungspflichten. Die Golden-File-Absicherung aus ADR-0001 deckt den heutigen
  Funktionsumfang nicht mehr ab.
- **Konsolidierung auf Python (Go abschaffen)** — verworfen: Auth, Store, Mandantentrennung und
  Frontend-Serving funktionieren in Go nachweislich gut (51 Handler-Testdateien auf 24 Handler);
  eine Rück-Portierung wäre Investition ohne Gegenwert und würde ADR-0001 vollständig umkehren.
- **Weiter ohne Entscheidung** — verworfen: Doku bleibt falsch, jede Investitionsfrage in die
  Python-Schicht bleibt unentscheidbar (konkret blockierte das Roadmap Phase 2).

## Konsequenzen

- **Positiv:** Refactoring-Investitionen sind entscheidbar; die Doku kann den Ist-Zustand als
  Soll-Zustand beschreiben (#1017); „welche Schicht besitzt diese Logik?" hat eine eindeutige
  Antwort für neue Features.
- **Preis:** Zwei Sprachen/Stacks dauerhaft — zwei Toolchains, zwei Test-Welten, die
  HTTP-Vertragsgrenze muss gepflegt werden (`api_contract.md` bei jeder DTO-Änderung).
- **Folgepflichten:** `AGENTS.md`/`docs/specs/_template.md`/`docs/features/architecture.md`
  korrigieren (#1017); Roadmap Phase 2 in Issues schneiden; bestehende Doppel-Logik-Fälle
  (z. B. #1000) mit klarem Owner auflösen.
