# Source Code – Gregor Zwanzig (Python-Core)

> Stand: 2026-07-21. Architektur-Gesamtbild: `docs/features/architecture.md`.

## Struktur

- `app/` — CLI (Debug-Werkzeug, nicht Produktivpfad), Loader, Modelle, Trip-/User-Handling
- `core/` — GPX, Segmentierung, Naismith
- `services/` — Wetter-Domäne: Forecast, Risk Engine, Aggregation, Alert-Engines, Scheduler-Dispatch, Inbound
- `output/` — Renderer (`renderers/`), Kanäle (`channels/`: email, telegram, sms, console), Tokens
- `providers/` — Wetter-Provider (Standard Open-Meteo; siehe `docs/reference/decision_matrix.md`)
- `validation/` — Validierungs-Helfer

## Leitplanken

- Keine Business-Logik in `app/cli.py`.
- Verträge/DTOs: `docs/reference/api_contract.md` ist die Single Source of Truth.
- Test-Politik (Zwei Schichten) und Pflicht-Gates: `CLAUDE.md`.
