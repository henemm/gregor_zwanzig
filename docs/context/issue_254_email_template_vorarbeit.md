# Context: Issue #254 — Email-Templates Vorarbeit

## Request Summary
Vorarbeiten für EPIC 9 (#236, Email-Templates ans Design-System angleichen): Token-Drift zwischen zwei CSS-Dateien auflösen, Inventar von `html.py` aufnehmen, weitere Mail-Anlässe prüfen, Test-HTML-Tooling einrichten.

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/renderers/email/html.py` | HTML-Mail-Renderer (β3) — Kern-Datei für Teil B |
| `src/output/renderers/email/design_tokens.py` | Python-Spiegel der CSS-Tokens für Inline-CSS |
| `src/output/renderers/email/profile_signature.py` | Profil-Signaturen (Akzentfarbe, Icon, Eyebrow) |
| `docs/reference/design_system_tokens.css` | Referenz-Fassung der Tokens (126 Zeilen, kein Tailwind) |
| `frontend/src/app.css` | Lebende Tokens im Frontend (332 Zeilen, Tailwind) |
| `src/services/trip_report_scheduler.py` | 2 Mail-Anlässe: Trip-Report (Z.356) + Service-Error (Z.809) |
| `src/services/trip_alert.py` | 1 Mail-Anlass: Alert (Z.418) |
| `src/services/inbound_email_reader.py` | 1 Mail-Anlass: Inbound-Reply (Z.152) |
| `src/app/cli.py` | CLI mit `--dry-run` Flag, EmailOutput-Nutzung (Z.299) |
| `src/app/core.py` | Alter `send_mail()` Pfad via SMTP_* ENV — nicht via EmailOutput |
| `tests/tdd/test_html_email.py` | Referenz: TestRealGmailE2E (echter E2E-Test) |

## Teil A: Tokens-Drift — Ist-Stand

Die zwei Dateien haben **vollständig unterschiedliche Struktur und Namenskonventionen**:

| Aspekt | `design_system_tokens.css` | `frontend/src/app.css` |
|--------|---------------------------|------------------------|
| Größe | 126 Zeilen | 332 Zeilen |
| Framework | Kein Framework, reines `:root {}` | Tailwind (`@import`, `@theme`, `@layer base`) |
| Surface-Namen | `--g-paper`, `--g-paper-deep`, `--g-card`, `--g-card-alt`, `--g-rule`, `--g-rule-soft` | `--g-surface-0/1/2`, `--g-ink-muted/faint/strong` |
| Semantic | `--g-good`, `--g-warn`, `--g-bad` | `--g-success`, `--g-warning`, `--g-danger` |
| Wetter | `--g-weather-rain/snow/thunder/sun/cloud` | `--g-wx-rain/sun/wind/snow/thunder/fog` |
| Spezialvariablen | `--g-ink-2/3/4`, Elevation (`--g-shadow-*`), Spacing (`--g-s-*`), Radii (`--g-r-*`), Topo-Pattern `.g-topo` | `@property` Farbdeklarationen für Tailwind-Kompatibilität, kein Spacing/Radii |

**Entscheidend:** `design_tokens.py` (Mail-Renderer) **verwendet bereits die `app.css`-Namenskonvention** (G_SURFACE_1, G_INK_MUTED etc.), nicht die Tokens-CSS-Datei. De facto ist `app.css` die verbindliche Quelle für den Mail-Renderer.

Die Tokens-Datei enthält auch einen Hinweis im Kommentar: *"Im Zweifel gilt app.css"*.

**Empfehlung:** `app.css` als Single Source of Truth festlegen. `design_system_tokens.css` kann als Dokumentations-Referenz bleiben, aber Mail-Templates verweisen auf `design_tokens.py`, das `app.css` spiegelt.

## Teil B: html.py Inventar — Ist-Stand

| Baustein | Vorhanden? | Details |
|----------|-----------|---------|
| Dunkel-Footer (`background: #1a1a18`) | **NEIN** | Footer hat `background: {G_PAPER}` (#f6f4ee) — hellgrau, nicht dunkel |
| Daylight-Bar (SVG Tageslicht-Visualisierung) | **NEIN** | `_format_daylight_html()` rendert ein `<div>` mit Border-Left-Box — kein SVG |
| Tag-System ok/warn/risk/info | **NEIN** | Es gibt Box-Tints (G_BOX_WARNING_BG etc.) aber kein Pill/Tag-System |
| ActivityProfile-Parameter | **JA** | `profile: Optional[ActivityProfile] = None` übergeben, `profile_signature()` aufgerufen; Akzentfarbe im Header bereits per Profil |
| Inline-CSS-Only | **JA** | Alles Inline-CSS + `<style>` Block; externe Stylesheets: nur Google Fonts (dekorativ, von Mail-Clients ignorierbar) |
| Inter Tight + JetBrains Mono Fallback-Stacks | **JA** | FONT_UI = Inter Tight + System-Fallbacks; FONT_DATA = JetBrains Mono + Monospace-Fallbacks; WEB_FONT_LINK lädt beide via Google Fonts |

## Teil C: Mail-Anlässe — vollständige Liste

| # | Datei | Zeile | Beschreibung |
|---|-------|-------|-------------|
| 1 | `trip_report_scheduler.py` | 356 | **Trip-Report** (Morning/Evening) — Haupt-Anlass |
| 2 | `trip_report_scheduler.py` | 809 | **Service-Error-Mail** — wenn SMS-only Trip keine Wetterdaten bekommt |
| 3 | `trip_alert.py` | 418 | **Alert-Mail** — Schwellwert-Überschreitung |
| 4 | `inbound_email_reader.py` | 152 | **Inbound-Reply** — Antwort auf Kommando-Mails |
| 5 | `app/cli.py` | 354 | **CLI-Mail** — manueller Report via CLI |
| 6 | `app/core.py` | 20 | **Alter send_mail()-Pfad** — via SMTP_* ENV, nicht via EmailOutput |

**Befund für Teil C:** `app/core.py:send_mail()` ist ein **alter, separater Mail-Pfad** ohne `EmailOutput` — dieser war in den 6 bekannten Anlässen möglicherweise nicht erfasst. Er verwendet direkte SMTP-Umgebungsvariablen (SMTP_HOST/PORT/USER/PASS), nicht die GZ_-Variablen von `Settings`. Unklar ob dieser Code aktiv genutzt wird.

## Teil D: Test-Tooling — Ist-Stand

- CLI hat `--dry-run` Flag (`cli.py:302`), aber dieser unterbindet nur den Versand — kein HTML-Datei-Output
- `render_html()` in `html.py` ist eine Pure Function — direkter Aufruf ist möglich
- Kein bestehendes Test-Script das HTML nach `/tmp/` schreibt
- `tests/tdd/test_html_email.py::TestRealGmailE2E` als Referenz für echte E2E-Tests

**Was benötigt wird:** Ein einfaches Script `scripts/preview_email.py` das `render_html()` mit Dummy-Daten aufruft und `/tmp/email_preview.html` schreibt.

## Existing Patterns

- Mail-Tokens werden als Python-Konstanten gespiegelt (`design_tokens.py`) — Outlook-kompatibel, kein `var()`
- Profil-Signaturen folgen dem gleichen Muster: Python-Klasse spiegelt Frontend-Logik
- Test-Mails gehen an `gregor-test@henemm.com` via Stalwart IMAP

## Dependencies

- **Upstream:** `app.css` → `design_tokens.py` → `html.py`
- **Downstream:** `render_html()` wird aus `src/output/renderers/email/__init__.py` aufgerufen

## Existing Specs

- `docs/specs/modules/issue_240_email_design_tokens.md` — Tokens für Mail
- `docs/specs/modules/issue_241_email_profile_pipeline.md` — Profil-Pipeline
- `docs/reference/design_system.md` — Design-System-Referenz

## Risks & Considerations

- **Keine Code-Änderungen** in diesem Issue — rein dokumentarische Vorarbeit + Test-Tooling
- `app/core.py:send_mail()` ist potenziell toter Code — sollte als Befund gemeldet, aber nicht jetzt gelöscht werden
- Teil D (Test-Script) ist der einzige Code-Anteil — minimal, kein Risiko
