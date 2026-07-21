---
entity_id: issue_255_email_profil_signaturen
type: module
created: 2026-05-17
updated: 2026-05-17
status: draft
version: "1.0"
tags: [email, design-system, activity-profile, issue-255, epic-236]
parent: epic_236_email_design_system
phase: phase3_spec
---

<!-- Issue #255 — Profil-Signaturen: CAPS-Eyebrows, Inline-SVG-Icons, Paper-Header -->

# Issue #255 — E-Mail-Profil-Signaturen: CAPS-Eyebrows, Inline-SVG-Icons, Paper-Header

## Approval

- [x] Approved

## Zweck

Die visuellen Profil-Signaturen der vier Aktivitätsprofile (Wintersport, Wandern, Summer-Trekking,
Allgemein) werden für HTML-Mails aufgewertet: Emoji-Icons werden durch minimale inline SVGs
ersetzt, Eyebrow-Texte auf einheitliches CAPS-Format umgestellt, und der Mail-Header-Hintergrund
wechselt von der Profil-Akzentfarbe auf den Design-System-Token `G_PAPER` (#f6f4ee).

Dieses Sub-Issue baut direkt auf #241 (`issue_241_email_profile_pipeline`) auf: die Pipeline-
Verkabelung steht bereits, hier werden ausschließlich die Signaturwerte selbst sowie das
Header-CSS angepasst.

## Quelle / Source

**Geänderte Dateien:**
- `src/output/renderers/email/profile_signature.py` — Neues Feld `icon_html: str` (inline SVG) + neue Eyebrow-Texte
- `src/output/renderers/email/html.py` — Header-BG `sig.accent_hex` → `G_PAPER`; CSS `.header` anpassen; Eyebrow-Farbe `#ffffff` → `G_ACCENT`; `sig.icon` → `sig.icon_html` im Eyebrow-Div

**Angepasste Tests:**
- `tests/tdd/test_email_profile_pipeline.py` — `PROFILE_CASES`: neue Eyebrow-Werte + neue `icon_html`-Assertions

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/profile.py::ActivityProfile` | Python-Enum | Eingabe-Typ, 4 Werte (WINTERSPORT, WANDERN, SUMMER_TREKKING, ALLGEMEIN) |
| `src/output/renderers/email/profile_signature.py::ProfileSignature` | Dataclass | Wird um `icon_html: str` erweitert; alle 4 Einträge in `_SIGNATURES` werden aktualisiert |
| `src/output/renderers/email/design_tokens.py::G_PAPER` | Konstante | Neuer Header-Hintergrund (#f6f4ee) |
| `src/output/renderers/email/design_tokens.py::G_INK` | Konstante | Neue Textfarbe im Header (#1a1a18) |
| `src/output/renderers/email/design_tokens.py::G_INK_FAINT` | Konstante | Border-Farbe unter dem Header |
| `src/output/renderers/email/design_tokens.py::G_ACCENT` | Konstante | Eyebrow-Textfarbe (#c45a2a) statt bisherigem #ffffff |
| `tests/tdd/test_email_profile_pipeline.py` | Test-Modul | Bestehende Tests werden auf neue Eyebrow-Werte und `icon_html`-Assertions erweitert |

## Profil-Signaturen (neu)

### Eyebrow-Texte

| Profil | Eyebrow alt | Eyebrow neu |
|--------|------------|------------|
| `WINTERSPORT` | `Wintersport` | `WINTERSPORT · PISTE` |
| `WANDERN` | `Wandern` | `WANDERN` |
| `SUMMER_TREKKING` | `Sommer-Trekking` | `ALPINE TOUR` |
| `ALLGEMEIN` | `Allgemein` | `WETTER-BRIEFING` |

### Icons (inline SVG)

Jedes Icon ist ein minimales inline SVG: 14×14 px, `display:inline`, `vertical-align:middle`,
`xmlns="http://www.w3.org/2000/svg"` (Gmail-Pflicht). Fill-Farbe = Profil-Akzentfarbe.

| Profil | SVG-Motiv | accent_hex | Fill-Farbe |
|--------|----------|-----------|-----------|
| `WINTERSPORT` | Snowflake (6-armige Schneeflocke) | `#4a7fb5` | `#4a7fb5` |
| `WANDERN` | Mountain (einfaches Dreieck) | `#3a7d44` | `#3a7d44` |
| `SUMMER_TREKKING` | Peak (doppeltes Bergdreieck) | `#c45a2a` | `#c45a2a` |
| `ALLGEMEIN` | Compass (Kreis + Nadel) | `#6b675c` | `#6b675c` |

Das `icon`-Feld (Emoji) bleibt für Plain-Text-Kompatibilität erhalten. `icon_html` wird
ausschließlich im HTML-Renderer verwendet.

## Implementation Details

### 1. `ProfileSignature`-Dataclass erweitern

**`src/output/renderers/email/profile_signature.py`**

```python
@dataclass(frozen=True)
class ProfileSignature:
    accent_hex: str   # Inline-Hex fuer Outlook-kompatibles Inline-CSS
    icon: str         # Unicode-Glyph (Plain-Text-Fallback, bleibt erhalten)
    eyebrow: str      # Sichtbares CAPS-Label
    icon_html: str    # Inline SVG fuer HTML-Mails (neu)
```

Jeder der 4 Einträge in `_SIGNATURES` erhält einen `icon_html`-Wert. Alle SVG-Strings müssen:
- mit `<svg` beginnen und mit `</svg>` enden
- `xmlns="http://www.w3.org/2000/svg"` enthalten
- `width="14" height="14"` und `style="display:inline;vertical-align:middle"` tragen
- `fill="<accent_hex>"` oder `stroke="<accent_hex>"` als einzige Farbquelle nutzen
- Einfache Pfade ohne `<defs>`, `<use>` oder externe Referenzen sein

Beispiel (Wandern):
```python
icon_html=(
    '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" '
    'style="display:inline;vertical-align:middle" viewBox="0 0 14 14">'
    '<path fill="#3a7d44" d="M7 1 L13 13 H1 Z"/>'
    '</svg>'
),
```

### 2. Eyebrow-Texte aktualisieren

In `_SIGNATURES` die `eyebrow`-Felder auf die neuen CAPS-Werte setzen:
- `WINTERSPORT` → `'WINTERSPORT · PISTE'`
- `WANDERN` → `'WANDERN'`
- `SUMMER_TREKKING` → `'ALPINE TOUR'`
- `ALLGEMEIN` → `'WETTER-BRIEFING'`

### 3. Header-CSS in `html.py` anpassen

**CSS-Klasse `.header` (aktuell ca. Zeile 275):**

```css
/* Alt: */
.header { background: {profile_accent_hex}; color: white; padding: 20px; }

/* Neu: */
.header {
    background: {G_PAPER};
    color: {G_INK};
    padding: 20px;
    border-bottom: 1px solid {G_INK_FAINT};
}
```

Color-Overrides auf `<h1>`, `<h2>`, `<p>` innerhalb `.header` entfernen — sie erben `G_INK`
von der CSS-Klasse. Inline-Style am Header-`<div>` (ca. Zeile 292) von `background:{sig.accent_hex}`
auf `background:{G_PAPER}` umstellen (oder Inline-Override ganz entfernen, falls die CSS-Klasse
allein reicht).

### 4. Eyebrow-Div in `html.py` anpassen

**Eyebrow-Block (ca. Zeile 293):**

```html
<!-- Alt: -->
<div class="eyebrow" style="...;color:#ffffff;">{sig.icon} {sig.eyebrow}</div>

<!-- Neu: -->
<div class="eyebrow" style="...;color:{G_ACCENT};">{sig.icon_html} {sig.eyebrow}</div>
```

`sig.icon` (Emoji) wird durch `sig.icon_html` (SVG-String) ersetzt. Die Farbe wechselt von
`#ffffff` auf `G_ACCENT` (`#c45a2a`), da der Hintergrund nun hell (G_PAPER) statt dunkel ist.

### 5. Tests aktualisieren

**`tests/tdd/test_email_profile_pipeline.py`** — `PROFILE_CASES`-Tabelle:
- Eyebrow-Erwartungswerte auf neue CAPS-Strings aktualisieren
- Pro Profil: `assert sig.icon_html.startswith('<svg')` und `assert sig.icon_html.endswith('</svg>')`
- Pro Profil: `assert 'xmlns="http://www.w3.org/2000/svg"' in sig.icon_html`
- Pro Profil: `assert sig.accent_hex in sig.icon_html` (Fill-Farbe = Akzentfarbe)
- Für AC-2: `assert sig_summer.icon_html != sig_allgemein.icon_html` (unterschiedliche Pfade)

### 6. LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `src/output/renderers/email/profile_signature.py` | +30 | ja |
| `src/output/renderers/email/html.py` | +10 | ja |
| `tests/tdd/test_email_profile_pipeline.py` | +40 | ja |
| **Gesamt** | **~80** | **< 250 LoC-Limit** |

## Expected Behavior

- **Input** (`profile_signature`): `Optional[ActivityProfile]` — wie bisher
- **Output** (`profile_signature`): `ProfileSignature`-Dataclass mit jetzt 4 Feldern (`accent_hex`, `icon`, `eyebrow`, `icon_html`); Eyebrow-Werte sind nun CAPS; `icon_html` enthält validen SVG-String; bei `None` → ALLGEMEIN-Fallback mit `eyebrow='WETTER-BRIEFING'`
- **Input** (`render_html`): unverändert; `profile`-kwarg bereits aus #241
- **Output** (`render_html`): HTML-String mit hellem Header-Hintergrund (`G_PAPER` / `#f6f4ee`); Eyebrow in `G_ACCENT` (`#c45a2a`); SVG-Icon statt Emoji im Eyebrow-Div; Profil-Akzentfarbe erscheint NICHT mehr als Header-Hintergrund
- **Input** (`render_plain`): unverändert; nutzt weiterhin `sig.icon` (Emoji), nicht `sig.icon_html`
- **Output** (`render_plain`): unverändert bis auf neue CAPS-Eyebrow-Texte
- **Side effects:** Keine — alle Funktionen bleiben pure functions

## Acceptance Criteria

- **AC-1:** Given `profile_signature(ActivityProfile.WINTERSPORT)` aufgerufen wird / When das Ergebnis geprüft wird / Then enthält `sig.icon_html` einen validen inline-SVG-String (beginnt mit `<svg`, endet mit `</svg>`, enthält `xmlns="http://www.w3.org/2000/svg"` und `#4a7fb5` als Farbe) und `sig.eyebrow == "WINTERSPORT · PISTE"` — analog für WANDERN (`eyebrow="WANDERN"`, Farbe `#3a7d44`), SUMMER_TREKKING (`eyebrow="ALPINE TOUR"`, Farbe `#c45a2a`), ALLGEMEIN (`eyebrow="WETTER-BRIEFING"`, Farbe `#6b675c`).
  - Test: (populated after /tdd-red)

- **AC-2:** Given `profile_signature(ActivityProfile.SUMMER_TREKKING)` und `profile_signature(ActivityProfile.ALLGEMEIN)` aufgerufen werden / When beide `icon_html`-Strings verglichen werden / Then unterscheiden sich ihre SVG-Pfad-Inhalte UND ihre eingebetteten Farben (`#c45a2a` vs `#6b675c`) — die Icons sind visuell unterscheidbar.
  - Test: (populated after /tdd-red)

- **AC-3:** Given `render_html(profile=ActivityProfile.WINTERSPORT, ...)` aufgerufen wird / When der generierte HTML-String geprüft wird / Then enthält er `#f6f4ee` (G_PAPER) im Header-Hintergrund, `#c45a2a` (G_ACCENT) als Eyebrow-Textfarbe, und einen `<svg`-Start-Tag als Teil des Eyebrow-Div-Inhalts.
  - Test: (populated after /tdd-red)

- **AC-4:** Given `render_html(profile=ActivityProfile.ALLGEMEIN, ...)` aufgerufen wird / When der HTML-String auf den Header-Abschnitt geprüft wird / Then erscheint `#f6f4ee` als Header-Hintergrund — die Profil-Akzentfarbe `#6b675c` erscheint NICHT als `background`-Wert des Headers.
  - Test: (populated after /tdd-red)

- **AC-5:** Given `render_plain(profile=ActivityProfile.WANDERN, ...)` aufgerufen wird / When die Plain-Text-Ausgabe geprüft wird / Then enthält die Eyebrow-Zeile den Text `WANDERN` (neues CAPS-Format) und beginnt mit dem Emoji-Icon `🥾` — `sig.icon_html` (SVG) wird für Plain-Text nicht verwendet.
  - Test: (populated after /tdd-red)

- **AC-6:** Given `profile_signature(None)` aufgerufen wird / When das Ergebnis geprüft wird / Then wird die ALLGEMEIN-Signatur zurückgegeben mit `eyebrow == "WETTER-BRIEFING"` und einem validen SVG-String in `icon_html` — ohne Exception.
  - Test: (populated after /tdd-red)

## Known Limitations

- **Outlook-SVG-Support:** Outlook (Windows) ignoriert inline SVG vollständig. Die Icons erscheinen dort nicht. Mitigation: Eyebrow-Text und Akzentfarbe tragen die Profil-Information; das SVG ist Bonus für moderne Clients (Gmail, Apple Mail).
- **Plain-Text nutzt weiterhin Emoji:** `sig.icon` (Emoji-Feld) bleibt für Plain-Text und ältere Code-Pfade erhalten. Beide Felder müssen konsistent gepflegt werden.
- **CAPS-Eyebrows in Plain-Text:** `render_plain` übernimmt die neuen CAPS-Texte automatisch über `sig.eyebrow`. Das ist gewollt.

## Out of Scope

- **Footer-Gestaltung** — laut Design-Bundle dunkel geplant, aber separates Sub-Issue
- **Outlook-SVG-Fallback** — keine VML- oder `<!--[if mso]>`-Alternativen gefordert
- **`frontend/src/lib/utils/profileSignature.ts`** — Frontend-Pendant bleibt unverändert (eigenes Ticket bei Bedarf)
- **Pipeline-Verkabelung** — steht bereits durch #241; hier nur Signaturwerte und Header-CSS
- **Trip-Alert-Mail, Subscription-Mail, Service-Error-Mail** — andere Sub-Issues von Epic #236

## Risiken & Migration

1. **Bestehende Tests brechen:** `PROFILE_CASES` in `test_email_profile_pipeline.py` prüft aktuell die alten Eyebrow-Werte (`Wintersport`, `Sommer-Trekking` etc.). Diese Tests werden nach der Implementierung bewusst rot (TDD-RED-Phase) und dann grün gepatcht.

2. **Backward-Kompatibilität `ProfileSignature`:** Das neue Feld `icon_html` ist ein Pflichtfeld in der Dataclass. Alle 4 Einträge in `_SIGNATURES` müssen gleichzeitig aktualisiert werden — kein schrittweises Rollout.

3. **Visueller Kontrast:** Der Wechsel von farbigem Header-Hintergrund (Akzentfarbe) zu `G_PAPER` verändert den visuellen Eindruck erheblich. Manuelle Sichtprüfung im Preview-Iframe auf Staging ist Pflicht vor Prod-Deploy.

## Tests / Verifikation

Test-Datei: `tests/tdd/test_issue255_profil_signaturen.py`

- **AC-1 — SVG-Feld + CAPS-Eyebrows (`profile_signature()`):**
  - `ac1_icon_html_is_valid_svg` — icon_html beginnt mit `<svg`, endet `</svg>`, hat `xmlns`
  - `ac1_icon_html_uses_profile_accent_color` — accent_hex in icon_html
  - `ac1_eyebrow_is_caps_format` — eyebrow-Text ist neues CAPS-Label
  - `ac1_icon_html_has_correct_size` — width/height 14, inline/middle
- **AC-2 — Summer-Trekking vs. Allgemein unterscheidbar:**
  - `ac2_summer_trekking_and_allgemein_have_different_svg_paths`
- **AC-3 — render_html() Header-BG + Eyebrow-Farbe + SVG:**
  - `ac3_header_background_is_paper_not_accent`
  - `ac3_header_background_has_no_accent_as_bg`
  - `ac3_eyebrow_color_is_accent_not_white`
  - `ac3_eyebrow_contains_svg_not_emoji`
- **AC-4 — Allgemein-Spezialfall:**
  - `ac4_allgemein_header_is_paper_not_accent`
- **AC-5 — render_plain nutzt Emoji + CAPS-Eyebrow:**
  - `ac5_render_plain_has_caps_eyebrow`
  - `ac5_render_plain_uses_emoji_not_svg`
- **AC-6 — None-Fallback gibt WETTER-BRIEFING zurück:**
  - `ac6_none_fallback_returns_wetter_briefing`
- **Manuell-visuell:** Browser-Tab auf `https://staging.gregor20.henemm.com/trips/<id>` → Tab „Vorschau" → Mail-iframe für mind. 2 verschiedene Profile; Header muss hell (#f6f4ee) erscheinen

## Changelog

- 2026-05-17: Initial spec erstellt. Setzt #241 (profile_signature.py + Pipeline) voraus. Design-Bundle bestätigt Paper-Header.
