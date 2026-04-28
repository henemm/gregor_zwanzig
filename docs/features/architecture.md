# Architektur – Gregor Zwanzig

## Überblick
Gregor Zwanzig ist ein Headless-Dienst (kein UI), der in drei Ebenen strukturiert ist:

1. **CLI & Config**
   - Einstiegspunkt: `src/app/cli.py`
   - Optionen: `--report`, `--channel`, `--dry-run`, `--config`, `--debug`
   - Priorität: CLI > ENV > config.ini
   - Ausgabe: Console (immer) und optional Versand (E-Mail)

2. **Business-Logik**
   - **Provider-Adapter**: holen Rohdaten von Wetter-APIs (z. B. MET Norway, DWD)
   - **Normalizer**: wandelt Daten in ein gemeinsames DTO ([api_contract.md](./api_contract.md))
   - **Risk Engine**: bewertet Forecasts anhand Schwellen (Regen, Gewitter, Wind, Hitze)
   - **Report Formatter**: erzeugt kurze Texte + Debug-Anhang
   - **DebugBuffer**: gemeinsame Quelle für Console + E-Mail-Debug

3. **Render-Pipeline**
   - **Channel Renderers** (`src/output/renderers/`) – β3: Pure-Function Renderer für E-Mail + SMS
   - `render_email()` – HTML + Plain-Text Körper (aus Token-Zeilen)
   - `render_sms()` – Kompaktes Format ≤160 Zeichen (v2.0 Wire-Format)
   - Schnittstelle: TokenLine (aus Report Formatter) → Channel-spezifischer Output

4. **Channels**
   - **SMTP-Mailer** (`src/app/core.py`) – einziger aktiver Kanal im MVP
   - Weitere Kanäle (SMS, Push, Garmin-Mail) später möglich

## Datenfluss (MVP)
CLI  
  ↓  
Config / ENV  
  ↓  
Provider-Adapter  
  ↓  
Normalisierung  
  ↓  
Risk Engine  
  ↓  
Formatter → TokenLine  
  ↓  
Channel Renderers  
  ├─→ render_email() → (HTML, Plain)  
  ├─→ render_sms() → Wire-Format ≤160 Zeichen  
  └─→ DebugBuffer  
  ↓  
Channel (E-Mail / Console / SMS)

## Debug-Prinzip
- Alle Schritte schreiben standardisierte Debug-Zeilen in den DebugBuffer
- Console = vollständige Ausgabe
- E-Mail = 1:1 identisches Subset
- Kern-Debug-Zeilen (immer enthalten): `cfg.path`, `report`, `channel`, `debug`, `dry_run`