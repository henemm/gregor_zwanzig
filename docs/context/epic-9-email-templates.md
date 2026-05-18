# Context: Epic #9 — Email-Templates ans Design-System angleichen

## Request Summary

EPIC 9 (GitHub: Issue #236) bringt alle Backend-Mail-Templates auf das neue
Design-System (Epic #133). Sub-Issues #254 und #255 sind abgeschlossen —
Vorarbeit (Tokens-Drift, Inventar, Test-Tooling) und Profil-Signaturen stehen.
Der nächste Schritt ist Sub-Issue 3: **Trip-Briefing-Mail** final umbauen
(Dunkel-Footer, Tag-System, Mobile-Layout, Dark-Mode-Compat).

## Aktueller Stand (2026-05-18 nach #254 + #255)

### Was bereits umgesetzt ist

| Thema | Datei | Status |
|-------|-------|--------|
| Design-Tokens als Python-Modul | `src/output/renderers/email/design_tokens.py` | ✅ Vollständig, alle 13 Tokens |
| Profil-Signaturen (CAPS-Eyebrow + SVG-Icon) | `src/output/renderers/email/profile_signature.py` | ✅ 4 Profile, `icon_html` vorhanden |
| `render_html()` nutzt Tokens + Signaturen | `src/output/renderers/email/html.py` | ✅ Header, Tabellen, Sections |
| Web-Fonts (Inter Tight + JetBrains Mono) | `html.py` im `<head>` | ✅ `WEB_FONT_LINK`, Fallback-Stacks |
| Preview-Script | `scripts/preview_email.py` | ✅ CLI, kein API-Call nötig |
| Test-Tooling | `tests/tdd/test_email_profile_pipeline.py` | ✅ 4 Profile getestet |
| Verbindliche Token-Quelle dokumentiert | `docs/reference/design_system.md §12` | ✅ `app.css` = SoT |

### Was noch fehlt (Gaps für Sub-Issue 3)

| Lücke | Wo in html.py | AC aus Epic #236 |
|-------|--------------|------------------|
| **Dunkel-Footer** fehlt | Zeile 285: `.footer { background: G_PAPER }` — noch hellgrau | AC-8 |
| **Tag-/Pill-System** fehlt | Kein `ok`/`warn`/`risk`/`info`-Pill-Renderer | AC-7 |
| **Mobile-Layout** fehlt | Keine `@media (max-width: 480px)` Rules | AC-9 |
| **Dark-Mode-Compat** fehlt | Kein `<meta name="color-scheme">`, kein `@media (prefers-color-scheme: dark)` | AC-3 (implizit) |
| **CSS Custom Properties am Root** fehlt | Alle Farben inline-hex — kein `<style>:root{...}` | AC-1 |

## Betroffene Dateien

| Datei | Relevanz |
|-------|----------|
| `src/output/renderers/email/html.py` | Haupt-Renderer, 316 Zeilen, eine große pure function `render_html()` |
| `src/output/renderers/email/design_tokens.py` | Token-Konstanten (nicht ändern) |
| `src/output/renderers/email/profile_signature.py` | Profil-Daten (nicht ändern) |
| `src/output/renderers/email/helpers.py` | Hilfs-Funktionen (fmt_val, visible_cols, etc.) |
| `scripts/preview_email.py` | Preview-Tooling, ggf. für mobiles Preview erweitern |
| `tests/tdd/test_email_profile_pipeline.py` | Tests für Profile + render_html() |
| `tests/tdd/test_renderers_email.py` | Unit-Tests für den Renderer |

## Mail-Anlässe (vollständiges Inventar)

| # | Anlass | Code-Stelle | Profil | Status Epic 9 |
|---|--------|-------------|--------|---------------|
| 1 | **Trip-Briefing (Morgen/Abend)** | `trip_report_scheduler.py:335` → `html.py::render_html` | Ja | → Sub-Issue 3 |
| 2 | **Trip-Alert** | `trip_alert.py:405` → `render_html` | Ja | → Sub-Issue 4 |
| 3 | Service-Error-Mail | `trip_report_scheduler.py:785-811` (Inline-HTML-String) | Nein | → Sub-Issue 5 |
| 4 | Inbound-Email-Reply | `inbound_email_reader.py:148-159` (plain text only) | Nein | → Sub-Issue 6 |
| 5 | Subscription/Compare-Mail | `cli.py:345-356` → `comparison_renderers.py::render_comparison_html` | Ja | → Sub-Issue 9 |
| 6 | Password-Reset | `auth_service.py` (noch zu lokalisieren) | Nein | → Sub-Issue 7 |
| 7 | Welcome/Subscription-Confirmation | nicht implementiert | Nein | → Sub-Issue 8 |

## Design-Referenzen

| Quelle | Inhalt |
|--------|--------|
| `docs/reference/design_system.md` | Verbindliche v2-Doku; §12 = Mail-Token-Entscheidung |
| `frontend/src/app.css` | Live-Tokens — Single Source of Truth |
| `src/output/renderers/email/design_tokens.py` | Python-Kopie aller Tokens |
| `docs/reference/design_system.md §5-6` | Eyebrow-Komponente, Tag/Pill-System |

## Constraints für Sub-Issue 3 (Trip-Briefing)

1. **Inline-CSS-Only** — CSS Custom Properties am `<style>:root` für moderne Clients + Hex-Fallback in allen kritischen Rules
2. **Outlook** ignoriert `@media` und CSS-Variables — Hex-Fallback immer doppelt setzen
3. **Dunkel-Footer**: `background: var(--g-ink, #1a1a18)`, weißer Text `#ffffff`, Links in Akzentfarbe
4. **Tag-Farben**: `ok=#3a7d44`, `warn=#c8882a`, `risk=#b33a2a`, `info=#2a6cb3` — nicht hartkodieren, aus `G_SUCCESS/WARNING/DANGER/INFO`
5. **Mobile (380px)**: Header kondensiert (Eyebrow + Brand in 1 Zeile), 2-spaltige Stats, Tabellen → Karten
6. **Kein Struktur-Refactor** von `render_html()` — nur Styling und neue Layout-Layer; Funktion bleibt eine pure function

## Testansatz

- Test-Mails an `gregor-test@henemm.com` (Stalwart, IMAP: gregor-test / GregorTest-7xK9mQ2026!)
- Kein Mock — echte SMTP-Sendung via `tests/tdd/test_html_email.py::TestRealGmailE2E`
- Nach Implementierung: `scripts/preview_email.py` für visuellen Check im Browser
- `email_spec_validator.py` vor "E2E bestanden"

## Empfohlener Schnitt für nächste Sub-Issues

| Schritt | GitHub-Issue | Abhängigkeit |
|---------|-------------|--------------|
| **Aktuell** | Trip-Briefing-Mail (anlegen + umsetzen) | #254 ✅ + #255 ✅ |
| Dann | Trip-Alert-Mail | Trip-Briefing fertig |
| Dann | Service-Error-Mail | unabhängig |
| Dann | Inbound-Reply | unabhängig |
| Dann | Compare-Email | Epic #246 (Compare-Engine) |
| Final | Visueller Regressions-Check | alle Templates fertig |

## Verwandte Specs

- `docs/specs/modules/issue_254_email_template_vorarbeit.md`
- `docs/specs/modules/issue_255_email_profil_signaturen.md`
- `docs/specs/modules/output_channel_renderers.md`
- `docs/reference/design_system.md`
