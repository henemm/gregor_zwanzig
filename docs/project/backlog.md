# Gregor Zwanzig – Backlog (PO-Ansicht)

## 0. Setup & Infrastruktur
- [x] `SETUP-01` Projekt-Skeleton (Tests, Mailer, Regeln)
- [ ] `SETUP-02` CLI-Entry-Point mit Optionen (`--report`, `--channel`, `--dry-run`, `--config`, `--debug`)
- [ ] `SETUP-03` Konfiguration: INI/TOML-Datei + ENV; Reihenfolge: CLI > ENV > Config-Datei
- [ ] `SETUP-04` Logging/Debug-Architektur (gemeinsame Debug-Struktur für Console+E-Mail)

## 1. Weather Data (Provider)
- [ ] `WEATHER-01` Adapter MET Norway
- [ ] `WEATHER-02` Adapter DWD/MOSMIX (optional)
- [ ] `WEATHER-03` Normalisierung & Validierung
- [ ] `WEATHER-04` Fehlerfälle: Timeouts, leere Felder, Rate Limits

## 2. Risk Logic
- [ ] `RISK-01` Gewitter-Risiko (CAPE/Blitze/Proxy)
- [ ] `RISK-02` Starkregen
- [ ] `RISK-03` Wind/Hitze
- [ ] `RISK-04` Schwellen/Heuristiken konfigurierbar

## 3. Reports & Versand
- [ ] `REPORT-01` Berichtstypen: `evening`, `morning`, `alert`
- [ ] `REPORT-02` Formatter (kurz, <160 Zeichen optional) + Debug-Anhang
- [ ] `REPORT-03` SMTP Live-Test (echte E-Mail), alternative Kanäle später

## 4. Ops
- [ ] `OPS-01` Fehlerbehandlung & Retries
- [ ] `OPS-02` Logging/Rotation
- [x] `OPS-03` GitHub Actions (Lint/Test)

## 5. WebUI
- [x] `UI-01` **Trip Edit** - Bestehende Trips bearbeiten
- [x] `UI-02` **Compare E-Mail** - Skigebiet-Vergleich per E-Mail mit Zeitfenster
- [x] `UI-03` **Cloud Layers** - Wolkenhöhen (Low/Mid/High) via Open-Meteo

## Definition of Done (jede Story)
- TDD: Tests zuerst, dann Implementierung, dann Refactor.
- README/Docs aktualisiert.
- Live-Verifikation: echter Versand/echter Abruf.
- Debug-Konsistenz: E-Mail-Debug == Console-Debug (Subset).
