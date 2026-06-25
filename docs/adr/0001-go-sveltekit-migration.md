# ADR-0001: Migration Python/NiceGUI → Go/SvelteKit

- **Status:** Akzeptiert
- **Datum:** 2026-04-12
- **Bezug:** `docs/project/migration-plan-go-sveltekit.md`

## Kontext

Das ursprüngliche MVP war vollständig in Python umgesetzt: Business-Logik, Formatter und das
Web-UI über NiceGUI (~18.600 LOC produktiv, ~20.400 LOC Tests, 67 Python-Dateien). Mit
wachsendem Funktionsumfang stieß diese Architektur an Grenzen — insbesondere das in Python/NiceGUI
gebaute Web-UI war für ein wachsendes, mandantenfähiges Produkt zunehmend schwer wartbar, und es
fehlte eine saubere Trennung zwischen Backend-Service und Frontend.

## Entscheidung

Das System wird auf **Go (Backend) + SvelteKit (Frontend)** migriert. Die Migration erfolgt
**inkrementell und phasenweise** (Meilensteine M1–M7), **nicht** als Big Bang:

- Das Python-System bleibt produktiv, bis Go+SvelteKit vollständig steht.
- Backend zuerst, Frontend danach.
- **Golden-File-Regression:** Python-Output wird als JSON eingefroren, der Go-Output dagegen
  verglichen, um Verhaltensgleichheit zu beweisen.

## Verworfene Alternativen

- **Big-Bang-Rewrite** — verworfen: zu hohes Risiko eines längeren Produktiv-Ausfalls; keine
  Möglichkeit, Alt- gegen Neu-Verhalten kontinuierlich zu vergleichen.
- **Bei Python/NiceGUI bleiben** — verworfen: NiceGUI skaliert für ein mandantenfähiges,
  mehrseitiges UI mit komplexen Wizards schlecht; Frontend und Backend bleiben verklebt.

## Konsequenzen

- **Positiv:** Klare Trennung Backend-Service / Frontend; performanteres, statisch typisiertes
  Go-Backend; modernes, wartbares SvelteKit-UI; Golden-Files sichern Verhaltensgleichheit ab.
- **Negativ / Preis:** Über die Migrationsdauer existieren **zwei** Stacks parallel; Logik muss
  doppelt vorgehalten/abgeglichen werden, bis das Python-Backend abgelöst ist.
- **Folgepflichten:** Die Architektur-Doku (`docs/features/architecture.md`) beschreibt heute den
  Ziel-Stack (Go-Backend + SvelteKit-Frontend + Wizards). Mandantentrennung wird im Go-Backend über
  `s.WithUser(...)` erzwungen — siehe [ADR-0003](0003-multi-tenant-isolation.md).
