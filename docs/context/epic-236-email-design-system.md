# Context: Epic #236 — Email-Templates ans Design-System angleichen

## Request Summary

Alle Backend-Mail-Templates auf die in Epic #133 etablierten Design-Tokens
umstellen und je `ActivityProfile` (Wintersport, Wandern, Summer-Trekking,
Allgemein) eine visuell erkennbare Signatur einführen. Aktuell hat
`src/output/renderers/email/html.py` sein eigenes, gewachsenes Inline-CSS und
empfängt das Aktivitätsprofil gar nicht — Wintersportler und Sommertrekker
bekommen visuell dieselbe Mail.

## Stand des Mail-Inventars (verifiziert 2026-05-16)

| # | Anlass | Code-Stelle | Render-Pfad | Profil-relevant | Status |
|---|--------|-------------|-------------|-----------------|--------|
| 1 | Trip-Briefing (Morgen/Abend) | `src/services/trip_report_scheduler.py:335` → `src/formatters/trip_report.py:111` → `src/output/renderers/email/html.py::render_html` | zentral | Ja | bestehend |
| 2 | Trip-Alert | `src/services/trip_alert.py:405` → `render_html` | zentral | Ja | bestehend |
| 3 | Service-Error-Mail | `src/services/trip_report_scheduler.py:785-811` (`_send_service_error_email`) | **Inline-HTML-String** | Nein | bestehend |
| 4 | Inbound-Email-Reply | `src/services/inbound_email_reader.py:148-159` (`_send_email_reply`) | **plain text only** | Nein | bestehend |
| 5 | Subscription/Compare-Mail | `src/app/cli.py:345-356` → `src/services/comparison_renderers.py::render_comparison_html` | **eigener Renderer** | Ja (Scoring) | bestehend |
| 6 | Password-Reset | — | — | nein | **nicht implementiert** |
| 7 | Welcome/Subscription-Confirmation | — | — | nein | **nicht implementiert** |

**Korrektur zum Epic-Body**: Tabelle dort listet 6 Anlässe, der Code hat 5
implementierte (1–5) plus 2 noch fehlende (Password-Reset, Welcome). Außerdem
existiert mit der Subscription-/Compare-Mail (Anlass 5) ein **eigener
HTML-Renderer**, der im Epic gar nicht auftaucht — der muss mit umgestellt
werden.

## Renderer-Detail: `src/output/renderers/email/html.py`

- 13 KB, eine große pure function `render_html(...)` (Zeile 95)
- Hartkodiert: Hex-Farben in mind. 18 Inline-`style=`-Statements
  (`#fffde7`/`#f9a825`/`#fff3e0`/`#e65100`/`#666`/`#999`/`#f5f5f5`/`#1976d2`/`#42a5f5`/`#e3f2fd`/`#90caf9`/`#fff8e1`/`#fbc02d`/`#f0f7ff`/`#fbc02d`)
- Hartkodiert: Schriften (`-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto`)
  → kein Inter Tight / JetBrains Mono
- Hartkodiert: Header-Farbe als Linear-Gradient `#1976d2 → #42a5f5` (alt)
- **Empfängt `ActivityProfile` NICHT** — nur `display_config` (Metrics)
- Tabellen-Layout ist bereits `<table>`-basiert (gut für Outlook)

## Design-System-Quellen (Single Source of Truth)

| Quelle | Inhalt |
|--------|--------|
| `docs/reference/design_system.md` (1–274) | Verbindliche v2-Doku, sync mit `app.css` 2026-05-16 |
| `frontend/src/app.css` (49–126) | Live-Tokens (`--g-accent #c45a2a`, `--g-paper #f6f4ee`, `--g-ink #1a1a18`, surface/ink-Stufen, semantic, wx-*) |
| `docs/reference/design_system_tokens.css` | Begleit-Referenz, kann driften (Issue #213 — Sync gerade gemacht in 53ae45e) |
| `frontend/src/routes/_design/+page.svelte` | Showroom (Btn, Card, Pill, Eyebrow, Dot, Sparkline, TopoBg) |
| `frontend/src/app.html` | Google-Fonts-Einbindung `Inter Tight` + `JetBrains Mono` |

Schlüssel-Tokens für Mail-Adaption:
- Farben: `--g-accent #c45a2a`, `--g-paper #f6f4ee`, `--g-ink #1a1a18`,
  `--g-success/warning/danger/info`, `--g-wx-rain/sun/wind/snow/thunder/fog`
- Schriften: `--g-font-ui: 'Inter Tight', system-ui, sans-serif`,
  `--g-font-data: 'JetBrains Mono', ui-monospace, monospace`
- Radien `--g-radius-*`, Elevation `--g-elev-1/2/3`

## ActivityProfile

- `src/app/profile.py`: Enum `WINTERSPORT | WANDERN | SUMMER_TREKKING | ALLGEMEIN`, Default `ALLGEMEIN`
- Heute im Render-Pfad nicht direkt: erreicht via `Trip.aggregation_config.profile`
  den Formatter/Scheduler, wird aber an `render_html()` nicht durchgereicht
- Profil-Signaturen pro Profil sind noch nicht im Design-System definiert
  → das ist Sub-Issue 2 dieses Epics

## Test-Mail-Tooling

| Datei | Zweck |
|-------|-------|
| `tests/tdd/test_html_email.py::TestRealGmailE2E` | **Echte** Gmail-SMTP-Sendungen, IMAP-Pull (memory-konform: keine Mocks) |
| `tests/tdd/test_html_email.py::TestSubscriptionEmailGeneration` | Pipeline ohne SMTP |
| `tests/tdd/test_bug_198_notify_test_resend.py:34-55` | Test-Resend-Routing (Gmail vs. Resend) |
| `src/app/config.py::Settings.for_testing()` | Routet Test-User automatisch auf Gmail (Pflicht!) |

## Constraints (aus Issue + Email-Welt)

1. **Inline-CSS-Only** für Mail-Body, aber CSS-Custom-Properties am Wurzel-Element
   sind in modernen Clients (Apple Mail, Gmail-Web, Apple-Webmail) erlaubt — mit
   Hex-Fallback in jeder kritischen Rule
2. **Web-Fonts** via Google-Fonts-Link im `<head>`, plus Fallback-Stack —
   Outlook ignoriert; Inter Tight/JetBrains Mono dort als sans-serif/monospace
3. **Tabellen-Layout** statt Flex/Grid (Outlook)
4. **Dark-Mode**: `meta name="color-scheme"` + `@media (prefers-color-scheme: dark)`
5. **Profil-Marker** sichtbar im Header (Eyebrow + Icon + Akzent-Subtoken pro Profil)
6. **Visueller Test** per echter Gmail-Sendung pro Template × Profil; Litmus
   nicht zwingend, ggf. später

## Risiken

- **Outlook-Renderer** ignoriert CSS-Custom-Properties → jeder Token braucht Hex-Fallback im Inline-Style
- **Skalierung**: 5 implementierte Anlässe × 4 Profile (zwei davon profil-neutral) = ca. 14 Mail-Varianten zum visuell Testen
- **Refactor-Verlockung**: `render_html()` ist groß und verdient eine Zerlegung, aber Out-of-Scope für dieses Epic
- **Subscription-Renderer** (Anlass 5) ist im Epic-Body nicht erwähnt — Scope-Lücke; muss ergänzt werden
- **Profil-Diff vs. Marken-Konsistenz**: Profile dürfen nicht so unterschiedlich werden, dass die Marke zerfasert → Sub-Issue 2 muss zuerst das visuelle Vokabular definieren

## Out of Scope

- Inhalt der Mails (welche Daten in welchem Block) — nur Look & Feel
- Email-Pipeline-Refactor (SMTP, Tracking, Bounce-Handling)
- SMS-Templates
- Profil-spezifische Datenlogik (β4-Thema, nicht Mail-Styling)
- Password-Reset- und Welcome-Mails (existieren nicht; bleiben außerhalb)

## Empfohlener Schnitt für die nächsten Schritte

Das Epic ist groß. Atomare Reihenfolge:

1. **Sub-Issue 1 (Inventar verifizieren)** ist durch dieses Context-Dokument
   de facto erledigt → kurz auf GitHub dokumentieren und schließen
2. **Sub-Issue 2 „Profil-Signaturen definieren"** — Token-Erweiterung pro Profil,
   Icon + Eyebrow-Variante, am Wurzel-Element gesetzt. Voraussetzung für alle
   trip-bezogenen Mail-Umstellungen
3. Dann **Sub-Issue 3 „Trip-Briefing-Mail"** als ersten echten Renderer-Umbau
4. Anschließend Alert, Service-Error, Inbound-Reply, Subscription
5. Final: visueller Regressions-Check über alle Anlässe × Profile

## Verwandte Specs

- `docs/specs/modules/output_channel_renderers.md` — β3-Spec der Mail-Renderer
- `docs/specs/modules/output_text_report_renderer.md` — β4, profil-bewusster Text-Renderer
- `docs/specs/modules/activity_profile.md` — Profil-Enum
- `docs/reference/design_system.md` — Design-System v2

## Verwandte Issues

- Epic #133 — Design System & Tokens (Fundament)
- Epic #140 — Output-Vorschau (zeigt die Mails, die wir hier umbauen)
- Issue #213 — Design-System-Doku-Drift (gerade gefixt in 53ae45e)
- Bug #125 — Safari-HTML-Cache (verwandt: HTML-Mail-Rendering)
