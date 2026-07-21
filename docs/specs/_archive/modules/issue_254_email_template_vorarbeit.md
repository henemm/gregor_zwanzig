---
entity_id: issue_254_email_template_vorarbeit
type: module
created: 2026-05-17
updated: 2026-05-17
status: draft
version: "1.0"
tags: [email, design-tokens, html, tooling, epic9]
---

# Email-Template-Vorarbeiten für EPIC 9 (Issue #254)

## Approval

- [x] Approved

## Purpose

Dieses Modul umfasst vier Vorarbeiten, die EPIC 9 (Email-Templates, Issue #236) vorbereiten: Tokens-Drift zwischen `design_tokens.py` und `app.css` dokumentieren und eine verbindliche Single Source of Truth festlegen, ein vollständiges Inventar der bestehenden `html.py`-Bausteine erstellen, alle aktiven Mail-Anlässe im Projekt erfassen und ein lokales Preview-Script (`scripts/preview_email.py`) anlegen, das `render_html()` direkt aufruft und eine Browser-prüfbare HTML-Datei erzeugt. Die Vorarbeiten erzeugen keine Runtime-Änderungen am Produktionscode — sie schaffen die Informationsbasis, auf der EPIC 9 ohne Überraschungen gebaut werden kann.

## Source

- **File:** `scripts/preview_email.py` (NEU, ~50 LoC — einziger Code-Deliverable)
- **Identifier:** `main()` — CLI-Einstiegspunkt des Preview-Scripts

Dokumentationsänderungen betreffen:
- `docs/reference/design_system.md` (Ergänzung §12)
- `docs/reference/design_system_tokens.css` (Kommentar-Header präzisieren)

`src/output/renderers/email/html.py` wird **nicht** verändert — nur referenziert.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/renderers/email/html.py` | intern | `render_html()` — wird im Preview-Script direkt aufgerufen |
| `src/app/models.SegmentWeatherData` | intern | Dummy-Fixture als Eingabe für `render_html()` |
| `docs/reference/design_system.md` | Doku | Empfängt §12 über app.css als verbindliche Mail-Quelle |
| `docs/reference/design_system_tokens.css` | Doku | Kommentar-Header wird auf die dokumentierte Entscheidung angepasst |
| `tests/unit/test_renderers_email.py` | Referenz | Fixture-Muster (Inline-Daten, kein Import) für das Preview-Script |
| `scripts/backfill_display_config_issue111.py` | Referenz | Bewährtes `sys.path`-Setup-Muster für Scripts außerhalb `src/` |

## Implementation Details

### Teil A — Tokens-Drift dokumentieren

1. `docs/reference/design_system.md`: Neuer Abschnitt §12 „Mail-Tokens: Single Source of Truth"
   - Feststellung: `design_tokens.py` ist bereits 100 % konsistent mit `app.css` für alle 11 Kern-Tokens (Hex-Werte identisch)
   - Entscheidung: `app.css` ist die verbindliche Quelle; `design_tokens.py` ist abgeleitete Kopie
   - Bekannte Namens-Abweichungen explizit auflisten:
     - `--g-good/bad` → `--g-success/danger`
     - `--g-ink-2/3/4` → `--g-ink-muted/faint`
     - `--g-card` → `--g-surface-1`
   - Verweis auf Bug-Issue für `--g-weather-thunder` (violett in `app.css` vs. rot in alter Tokens-Datei)

2. `docs/reference/design_system_tokens.css`: Kommentar-Header von Hinweis auf verbindliche Entscheidung umformulieren — „Im Zweifel gilt app.css" → expliziter Verweis auf §12 in design_system.md

### Teil B — html.py Inventar

Befund in `docs/reference/design_system.md` §12 oder eigenem Abschnitt dokumentieren:

| Baustein | Status | Details |
|----------|--------|---------|
| Dunkel-Footer | FEHLT | Footer nutzt `G_PAPER` (#f6f4ee), kein dunkles `#1a1a18` |
| Daylight-Bar (SVG) | FEHLT | `_format_daylight_html()` rendert `<div>` mit Border-Left-Box, kein SVG |
| Tag-System ok/warn/risk/info | FEHLT | Box-Tints (`G_BOX_*`) vorhanden, kein Pill/Tag-System |
| ActivityProfile-Parameter | VORHANDEN | `profile: Optional[ActivityProfile]`, `profile_signature()`, `sig.accent_hex` im Header |
| Inline-CSS-Only | VORHANDEN | `<style>`-Block + Inline-Styles; Google Fonts dekorativ |
| Inter Tight + JetBrains Mono | VORHANDEN | `FONT_UI`, `FONT_DATA`, `WEB_FONT_LINK` aus `design_tokens.py` vollständig eingebunden |

### Teil C — Mail-Anlässe erfassen

7 Anlässe im Dokument festhalten:

| Nr | Datei | Zeile | Anlass |
|----|-------|-------|--------|
| 1 | `src/app/trip_report_scheduler.py` | 356 | Trip-Report Morning/Evening |
| 2 | `src/app/trip_report_scheduler.py` | 809 | Service-Error-Mail |
| 3 | `src/app/trip_alert.py` | 418 | Alert-Mail |
| 4 | `src/app/inbound_email_reader.py` | 152 | Inbound-Reply |
| 5 | `src/app/cli.py` | 354 | Compare-Subscription-Email |
| 6 | `src/app/cli.py` | 299 | CLI manueller Report (indirekt) |
| 7 | `src/app/core.py` | 5 | Alter SMTP-Direktpfad (toter Code, nicht mehr referenziert) |

### Teil D — Preview-Script `scripts/preview_email.py`

```python
#!/usr/bin/env python3
"""
Lokales Email-Preview-Script.
Erzeugt eine HTML-Datei aus render_html() — keine API-Calls, keine externen Deps.

Verwendung:
    python scripts/preview_email.py
    python scripts/preview_email.py --out /tmp/mein_preview.html
    python scripts/preview_email.py --report-type morning --open
"""
import sys
import argparse
from pathlib import Path

# sys.path-Setup: bewährtes Muster aus scripts/backfill_display_config_issue111.py
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.output.renderers.email.html import render_html
from src.app.models import SegmentWeatherData  # Dummy-Fixture-Typ

def build_fixture() -> list[SegmentWeatherData]:
    """Inline-Dummy-Daten — keine externen Abhängigkeiten."""
    # Fixture analog zu tests/unit/test_renderers_email.py
    # Mindestens 2 Segmente mit allen Pflichtfeldern befüllen
    ...

def main():
    parser = argparse.ArgumentParser(description="Email-HTML lokal rendern")
    parser.add_argument("--out", default="/tmp/email_preview.html")
    parser.add_argument("--report-type", default="morning", choices=["morning", "evening"])
    parser.add_argument("--open", action="store_true", dest="open_browser")
    args = parser.parse_args()

    segments = build_fixture()
    html = render_html(segments, report_type=args.report_type)

    out_path = Path(args.out)
    out_path.write_text(html, encoding="utf-8")
    print(f"Preview geschrieben: {out_path}")

    if args.open_browser:
        import subprocess
        subprocess.run(["xdg-open", str(out_path)], check=False)

if __name__ == "__main__":
    main()
```

Signatur von `render_html()` vor Implementierung final prüfen — die Fixture muss zur tatsächlichen Parameterliste passen.

## Expected Behavior

- **Input (Script):** Keine Pflicht-Argumente; optional `--out PATH`, `--report-type morning|evening` (kein `--open` — headless Server, kein Display)
- **Output (Script):** Valides HTML-Dokument unter `--out` (Default `/tmp/email_preview.html`), Exit 0 bei Erfolg
- **Side effects (Script):** Keine Netzwerkkommunikation, keine Datenbankzugriffe, keine Änderung an Produktionsdateien
- **Dokumentation:** `design_system.md` erhält §12 mit Tokens-Entscheidung und html.py-Inventar; `design_system_tokens.css` erhält präzisierten Kommentar-Header

## Acceptance Criteria

**AC-1:** Given `design_system.md` ohne §12-Abschnitt und `design_system_tokens.css` mit vagem Kommentar / When die Dokumentationsänderungen eingespielt sind / Then enthält `design_system.md` einen §12-Abschnitt, der `app.css` explizit als verbindliche Mail-Token-Quelle benennt, alle bekannten Namens-Abweichungen auflistet und auf das `--g-weather-thunder`-Bug-Issue verweist.
- Test: (populated after /tdd-red)

**AC-2:** Given das html.py-Inventar noch nicht dokumentiert ist / When §12 eingespielt ist / Then sind alle 6 Bausteine (Dunkel-Footer, Daylight-Bar, Tag-System, ActivityProfile, Inline-CSS, Fonts) mit Status VORHANDEN oder FEHLT bewertet und im Dokument nachlesbar.
- Test: (populated after /tdd-red)

**AC-3:** Given `scripts/preview_email.py` noch nicht existiert / When `python scripts/preview_email.py` ausgeführt wird / Then wird `/tmp/email_preview.html` mit valider HTML-Struktur erzeugt, der Prozess beendet mit Exit 0, und die Datei ist ohne Build-Schritt oder externe API direkt im Browser öffenbar.
- Test: (populated after /tdd-red)

## Known Limitations

- `scripts/preview_email.py` nutzt Inline-Fixture-Daten — das Preview entspricht nicht zwingend einem echten Trip-Datensatz, sondern dient ausschließlich der visuellen Überprüfung der Template-Struktur.
- Der `--g-weather-thunder`-Farbkonflikt (violett vs. rot) wird als separates Bug-Issue gemeldet und ist kein Deliverable dieses Issues.
- Anlass Nr. 7 (`core.py` SMTP-Direktpfad) ist toter Code; kein Handlungsbedarf im Rahmen dieses Issues, aber dokumentiert für EPIC 9.

## Changelog

- 2026-05-17: Initial spec created (Issue #254)
