# Gregor Zwanzig – Backlog (PO-Ansicht)

## 0. Setup & Infrastruktur
- [x] Projekt-Skeleton (Tests, Mailer, Regeln)
- [ ] CLI-Entry-Point mit Optionen (`--report`, `--channel`, `--dry-run`, `--config`, `--debug`)
- [ ] Konfiguration: INI/TOML-Datei + ENV; Reihenfolge: CLI > ENV > Config-Datei
- [ ] Logging/Debug-Architektur (gemeinsame Debug-Struktur für Console+E-Mail)

## 1. Weather Data (Provider)
- [ ] Adapter MET Norway
- [ ] Adapter DWD/MOSMIX (optional)
- [ ] Normalisierung & Validierung
- [ ] Fehlerfälle: Timeouts, leere Felder, Rate Limits

## 2. Risk Logic
- [ ] Gewitter-Risiko (CAPE/Blitze/Proxy)
- [ ] Starkregen
- [ ] Wind/Hitze
- [ ] Schwellen/Heuristiken konfigurierbar

## 3. Reports & Versand
- [ ] Berichtstypen: `evening`, `morning`, `alert`
- [ ] Formatter (kurz, <160 Zeichen optional) + Debug-Anhang
- [ ] SMTP Live-Test (echte E-Mail), alternative Kanäle später

## 4. Ops
- [ ] Fehlerbehandlung & Retries
- [ ] Logging/Rotation
- [ ] GitHub Actions (Lint/Test)

## Definition of Done (jede Story)
- TDD: Tests zuerst, dann Implementierung, dann Refactor.
- README/Docs aktualisiert.
- Live-Verifikation: echter Versand/echter Abruf.
- Debug-Konsistenz: E-Mail-Debug == Console-Debug (Subset).
