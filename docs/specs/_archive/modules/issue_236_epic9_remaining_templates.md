---
entity_id: issue_236_epic9_remaining_templates
type: module
created: 2026-05-18
updated: 2026-05-18
status: implemented
version: "1.0"
tags: [email, design-system, epic-236, issue-236, service-error-mail, comparison-mail, design-tokens, profile-signature]
parent: epic_236_email_design_system
---

<!-- Issue #236 EPIC 9 — Verbleibende Templates: Service-Error-Mail + Comparison-Mail ans Design-System angleichen -->

# Issue #236 EPIC 9 — Verbleibende E-Mail-Templates: Service-Error-Mail und Comparison-Mail

## Approval

- [x] Approved (2026-05-18)

## Zweck

Dieses Issue schließt die letzten beiden noch nicht migrierten E-Mail-Templates im Rahmen von EPIC 9 (Issue #236): Die Service-Error-Mail in `trip_report_scheduler.py` erhält ein vollständiges HTML-Dokument mit Design-Tokens statt rohem f-String-HTML ohne Styling, und der Comparison-Renderer (`comparison_renderers.py`) wird von Material-Design-Farben auf Gregor-Design-Token-Konstanten umgestellt und erhält als erster Renderer die `profile`-Parameter-Schnittstelle für die spätere Profil-Eyebrow-Anzeige.

Nach Abschluss dieses Issues sind alle E-Mail-Templates im Projekt vollständig auf das Design-System ausgerichtet — kein hardkodierter Material-Design-Farbwert (#1976d2, #42a5f5 etc.) verbleibt in produktivem Code. Sub-Issues #254 (Inventar + Tokens), #255 (Profil-Signaturen), #257 (Trip-Briefing-Polish) und das Trip-Alert-Mail sind Voraussetzungen und bereits abgeschlossen.

## Quelle / Source

**Geänderte Dateien:**
- `src/services/trip_report_scheduler.py` — `_send_service_error_email`: vollständiges HTML-Template (DOCTYPE, head, body) mit Design-Tokens statt f-String-Roh-HTML
- `src/services/comparison_renderers.py` — Imports + CSS-Token-Mappings + `profile`-Parameter in `render_comparison_html()` und `render_comparison_text()` + Eyebrow-Header-Block
- `src/services/compare_subscription.py` — Profil-Weitergabe an `render_comparison_html()` + Warning-Banner von `#fff3cd`/`#ffc107` auf G_BOX_WARNING_BG/G_WARNING

**Neue Test-Datei:**
- `tests/tdd/test_issue_236_remaining_templates.py`

**NICHT ändern:** `design_tokens.py`, `profile_signature.py`, `html.py`, `helpers.py`, `plain.py`

> **Schicht-Hinweis:** Alle Änderungen liegen im Python-Backend-Layer (`src/services/`). Die HTML-Mails werden serverseitig gerendert — kein SvelteKit-Code, kein Go-API-Code betroffen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/renderers/email/design_tokens.py::G_PAPER` | Python-Konstante | Body-Hintergrund beider Mails |
| `src/output/renderers/email/design_tokens.py::G_INK` | Python-Konstante | Footer-Hintergrund (dunkel) + Textfarbe |
| `src/output/renderers/email/design_tokens.py::G_ACCENT` | Python-Konstante | Heading-Border-Color (Service-Error) + Header-Text (Comparison) + rank-Badge-BG |
| `src/output/renderers/email/design_tokens.py::G_DANGER` | Python-Konstante | Error-Pre-Block-Border-Left in Service-Error-Mail |
| `src/output/renderers/email/design_tokens.py::G_SUCCESS` | Python-Konstante | Winner-Block-BG-Border + td.best-Farbe (Comparison) |
| `src/output/renderers/email/design_tokens.py::G_WARNING` | Python-Konstante | Warning-Banner-Border (Comparison) |
| `src/output/renderers/email/design_tokens.py::G_SURFACE_1` | Python-Konstante | Error-Pre-Block-BG (Service-Error) + Winner/td.best-BG (Comparison) |
| `src/output/renderers/email/design_tokens.py::FONT_UI` | Python-Konstante | Body-Schriftfamilie beider Mails |
| `src/output/renderers/email/design_tokens.py::FONT_DATA` | Python-Konstante | Error-Pre-Block-Schrift in Service-Error-Mail |
| `src/output/renderers/email/design_tokens.py::WEB_FONT_LINK` | Python-Konstante | `<link>`-Tag im `<head>` beider Mails |
| `src/output/renderers/email/design_tokens.py::G_BOX_WARNING_BG` | Python-Konstante | Warning-Banner-Hintergrund in compare_subscription.py |
| `src/output/renderers/email/profile_signature.py::profile_signature` | Python-Funktion | Liefert `ProfileSignature` mit `icon_html`, `eyebrow`, `accent_hex` für Comparison-Header |
| `src/app/profile.py::ActivityProfile` | Python-Enum | Typ für `profile`-Parameter in `render_comparison_html()` und `render_comparison_text()` |
| `src/services/compare_subscription.py` | Python-Modul | Übergibt `activity_profile` aus `sub` an `render_comparison_html()` |

## Implementation Details

### 1. Service-Error-Mail in `trip_report_scheduler.py` (Zeile 785–812)

**`_send_service_error_email`-Methode: f-String durch vollständiges HTML ersetzen**

Die Variable `body` wird von rohem f-String-HTML auf ein vollständiges HTML-Dokument umgestellt. Der `EmailOutput`-Aufruf am Ende der Methode bleibt unverändert.

Struktur des neuen Templates:

```
<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="color-scheme" content="light">
  {WEB_FONT_LINK}
  <style>
    body { margin:0; padding:16px; background:{G_PAPER}; font-family:{FONT_UI};
           color:{G_INK}; }
    .container { max-width:600px; margin:0 auto; background:{G_PAPER}; }
    h3 { color:{G_ACCENT}; border-bottom:2px solid {G_ACCENT};
         padding-bottom:6px; margin-top:0; }
    p { margin:8px 0; line-height:1.5; }
    pre { background:{G_SURFACE_1}; border-left:4px solid {G_DANGER};
          font-family:{FONT_DATA}; padding:10px 14px; white-space:pre-wrap;
          word-break:break-word; border-radius:4px; font-size:12px; }
    .footer { background:{G_INK}; color:#ffffff; padding:12px;
              text-align:center; font-size:11px; margin-top:24px; }
  </style>
</head>
<body>
  <div class="container">
    <h3>Service-Benachrichtigung</h3>
    <p><b>Trip:</b> {trip.name}<br>
       <b>Report:</b> {report_type.title()}<br>
       <b>Problem:</b> Wetterdaten konnten nicht abgerufen werden.</p>
    <p><b>Betroffene Segmente:</b></p>
    <pre>{error_lines}</pre>
    <p><small>Diese E-Mail wurde automatisch gesendet. ...</small></p>
  </div>
  <div class="footer">Gregor Zwanzig</div>
</body>
</html>
```

Kein Profil-Marker — Profil ist in dieser Methode nicht bekannt.

### 2. Comparison-Renderer: Imports in `comparison_renderers.py`

Am Anfang der Datei nach den bestehenden Imports ergänzen:

```python
from typing import Optional
from src.output.renderers.email.design_tokens import (
    G_PAPER, G_INK, G_ACCENT, G_SUCCESS, G_WARNING, G_DANGER,
    G_SURFACE_1, FONT_UI, WEB_FONT_LINK,
)
from src.output.renderers.email.profile_signature import profile_signature
from src.app.profile import ActivityProfile
```

### 3. Comparison-Renderer: Funktionssignaturen erweitern

`render_comparison_html()` und `render_comparison_text()` erhalten einen optionalen `profile`-Parameter:

```python
def render_comparison_html(
    ...,
    profile: Optional[ActivityProfile] = None,
) -> str:
    ...

def render_comparison_text(
    ...,
    profile: Optional[ActivityProfile] = None,
) -> str:
    # profile-Parameter wird akzeptiert, aber in dieser Version nicht ausgewertet
    ...
```

### 4. Comparison-Renderer: CSS-Token-Mappings ersetzen

Den bestehenden CSS-Block (inline f-String im HTML-Template) vollständig durch Token-Konstanten ersetzen. Konkrete Mappings:

| Alt (hardkodiert) | Neu (Token) | Konstante |
|-------------------|-------------|-----------|
| `linear-gradient(135deg, #1976d2, #42a5f5)` header-BG | `{G_PAPER}` flat | G_PAPER |
| `color: white` header | `color: {G_INK}` | G_INK |
| `background: #f5f5f5` body | `{G_PAPER}` | G_PAPER |
| `background: #e8f5e9` .winner | `{G_SURFACE_1}` | G_SURFACE_1 |
| `color: #2e7d32` .winner-text | `{G_SUCCESS}` | G_SUCCESS |
| `border-left: 4px solid #4caf50` .winner | `{G_SUCCESS}` | G_SUCCESS |
| `background: #e8f5e9; color: #2e7d32` td.best | `{G_SURFACE_1}; {G_SUCCESS}` | G_SURFACE_1, G_SUCCESS |
| `border-bottom: 2px solid #1976d2` .section h3 | `{G_ACCENT}` | G_ACCENT |
| `background: #1976d2` .rank | `{G_ACCENT}` | G_ACCENT |
| `background: #f5f5f5; color: #888` .footer | `{G_INK}; color: #ffffff` | G_INK |
| `font-family: -apple-system, ..., Roboto` | `{FONT_UI}` | FONT_UI |

Zusätzlich `{WEB_FONT_LINK}` im `<head>`-Block ergänzen (vor oder nach dem `<style>`-Block).

### 5. Comparison-Renderer: Profil-Eyebrow im Header

Nach dem `sig = profile_signature(profile)`-Aufruf eine Eyebrow-Zeile im Header-Block einfügen (analog `html.py` Zeile ~310):

```python
sig = profile_signature(profile)
eyebrow_html = (
    f'<div style="font-size:11px;font-weight:600;letter-spacing:.08em;'
    f'color:{sig.accent_hex};margin-bottom:4px;">'
    f'{sig.icon_html}&nbsp;{sig.eyebrow}</div>'
) if profile is not None else ""
```

Den `eyebrow_html`-String im Header-Template direkt über dem `<h1>`-Titel einbetten.

### 6. Warning-Banner in `compare_subscription.py` (Zeilen 118–126)

Imports ergänzen:

```python
from src.output.renderers.email.design_tokens import G_BOX_WARNING_BG, G_WARNING
```

CSS-Werte im Warning-Banner-HTML ersetzen:

```
background: #fff3cd  →  background: {G_BOX_WARNING_BG}
border-left: ... #ffc107  →  border-left: 4px solid {G_WARNING}
```

### 7. Profil-Weitergabe in `compare_subscription.py` (Zeile ~109)

Den `render_comparison_html()`-Aufruf um `profile=getattr(sub, 'activity_profile', None)` ergänzen:

```python
html = render_comparison_html(
    ...,
    profile=getattr(sub, 'activity_profile', None),
)
```

### 8. LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `src/services/trip_report_scheduler.py` | +35 | ja |
| `src/services/comparison_renderers.py` | +25 | ja |
| `src/services/compare_subscription.py` | +8 | ja |
| `tests/tdd/test_issue_236_remaining_templates.py` | +90 | ja |
| **Gesamt** | **~158** | **< 250 LoC-Limit** |

## Expected Behavior

- **Input (`_send_service_error_email`):** Unverändert — `trip`, `report_type`, `error_lines` aus der Methode
- **Output (`_send_service_error_email`):** Vollständiges HTML-Dokument mit G_PAPER-BG, G_ACCENT-Heading-Border, G_DANGER-Error-Block-Border, WEB_FONT_LINK im head und Dunkel-Footer (G_INK-BG, `#ffffff`-Text "Gregor Zwanzig")
- **Input (`render_comparison_html`):** Bestehende Parameter unverändert + neuer `profile: Optional[ActivityProfile] = None`
- **Output (`render_comparison_html`):** HTML-String mit (1) allen Material-Design-Farben durch Token ersetzt, (2) WEB_FONT_LINK im head, (3) Eyebrow-Block im Header wenn `profile` nicht None, (4) Dunkel-Footer mit G_INK-BG
- **Input (`render_comparison_text`):** Bestehende Parameter unverändert + neuer `profile: Optional[ActivityProfile] = None`
- **Output (`render_comparison_text`):** Unverändert — `profile`-Parameter wird akzeptiert aber nicht ausgewertet
- **Side effects:** Keine — alle geänderten Funktionen bleiben pure functions; kein Netzwerk-Call, keine DB-Zugriffe

## Acceptance Criteria

- **AC-1:** Given `_send_service_error_email` aufgerufen mit beliebigem Trip und Report-Type / When das generierte HTML geprüft wird / Then enthält der `<body>`-Hintergrund `G_PAPER`, das `<h3>`-Element eine `border-bottom` mit `G_ACCENT`, der `<pre>`-Block eine `border-left` mit `G_DANGER` und der Footer `background:{G_INK}` mit Text "Gregor Zwanzig" und Textfarbe `#ffffff`.
  - Tests: `test_ac1_service_error_mail_structure`

- **AC-2:** Given das von `_send_service_error_email` generierte HTML / When der gesamte HTML-String auf hardkodierte Farb-Hex-Werte durchsucht wird / Then enthält er weder `#f5f5f5` noch `#1976d2` noch `#42a5f5` — einzige erlaubte hardkodierte Ausnahme ist `#ffffff` im Footer.
  - Tests: `test_ac2_service_error_mail_no_hardcoded_colors`

- **AC-3:** Given `render_comparison_html()` mit `profile=ActivityProfile.WANDERN` aufgerufen / When der Header-Block im zurückgegebenen HTML analysiert wird / Then enthält dieser eine Eyebrow-Zeile mit dem Icon und dem `eyebrow`-Text aus `profile_signature(ActivityProfile.WANDERN)` sowie den `accent_hex`-Farbwert als `color`-Stil.
  - Tests: `test_ac3_comparison_html_profile_eyebrow`

- **AC-4:** Given `render_comparison_html()` aufgerufen (mit oder ohne `profile`) / When der CSS-Block des zurückgegebenen HTML auf Material-Design-Farben geprüft wird / Then enthält der HTML-String weder `#1976d2` noch `#42a5f5` noch `#4caf50` noch `#e8f5e9` noch `#2e7d32`.
  - Tests: `test_ac4_comparison_html_no_material_colors`

- **AC-5:** Given `render_comparison_text()` mit `profile=ActivityProfile.WINTERSPORT` aufgerufen / When die Rückgabe geprüft wird / Then liefert die Funktion einen String (keine Exception), und das Ergebnis ist identisch mit dem Ergebnis ohne `profile`-Argument (kein Auswerten des Profils in Text-Render).
  - Tests: `test_ac5_comparison_text_profile_param_ignored`

- **AC-6:** Given `compare_subscription.py` führt einen Comparison-Run durch und `sub.activity_profile` ist gesetzt / When `render_comparison_html()` aufgerufen wird / Then wird `profile=sub.activity_profile` übergeben, und der Warning-Banner-CSS enthält `G_BOX_WARNING_BG` statt `#fff3cd` und `G_WARNING` statt `#ffc107`.
  - Tests: `test_ac6_compare_subscription_profile_forwarding`, `test_ac6_warning_banner_tokens`

- **AC-7:** Given alle geänderten Dateien importiert werden / When `pytest tests/` ausgeführt wird / Then laufen alle bestehenden Tests ohne Fehler durch — keine Regressionen in `test_renderers_email.py`, `test_email_design_tokens.py` oder `test_issue255_profil_signaturen.py`.
  - Tests: Integrations-Smoke via `pytest tests/`

## Known Limitations

- **`render_comparison_text()` wertet `profile` noch nicht aus:** Der Parameter ist API-Konsistenz-Vorbereitung für Issue #253. In dieser Version bleibt der Text-Output unverändert.
- **Eyebrow immer sichtbar (ALLGEMEIN als Fallback):** `profile_signature(None)` gibt die ALLGEMEIN-Signatur zurück — Eyebrow erscheint immer, auch wenn `profile=None`. Konsistent mit `html.py`. Kein "leerer Eyebrow" — das wäre schlechtere UX. *(Adversary F001 korrigiert: ursprüngliche `else ""`-Notiz war zu restriktiv.)*
- **Schriftfarbe Footer `#ffffff` hardkodiert:** Analog Issue #257 — kein `G_WHITE`-Token vorhanden; `#ffffff` als einzige erlaubte hardkodierte Ausnahme auf dunklem Hintergrund (Konvention aus Issue #254).

## Out of Scope

- `design_tokens.py` bleibt unverändert
- `profile_signature.py` bleibt unverändert
- Auswertung von `profile` in `render_comparison_text()` (folgt in Issue #253)
- Weitere noch nicht migrierte Templates außerhalb der drei genannten Dateien
- Outlook-VML-Fallbacks für dunkle Footer-Bereiche

## Changelog

- 2026-05-18: Initial spec erstellt. Setzt Sub-Issues #254 (Inventar + Tokens), #255 (Profil-Signaturen), #257 (Trip-Briefing-Polish) und Trip-Alert-Mail voraus. Schließt EPIC 9 Issue #236 Design-System-Migration ab.
- 2026-05-18: Implementation abgeschlossen. Alle ACs verifiziert. `_send_service_error_email()` rendert vollständiges HTML mit Design-Tokens. `render_comparison_html()` + `render_comparison_text()` mit `profile`-Parameter + Eyebrow-Header. Warning-Banner in `compare_subscription.py` auf Design-Tokens umgestellt.
