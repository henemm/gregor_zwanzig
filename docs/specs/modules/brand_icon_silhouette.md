---
entity_id: brand_icon_silhouette
type: module
created: 2026-09-16
updated: 2026-09-16
status: draft
version: "1.0"
tags: [brand, icon, pwa, favicon]
---

# Marken-Icon: Silhouette statt Kontur (Issue #2341)

## Approval

- [ ] Approved

## Purpose

Das Berg+Blitz-Bildmark von gregor.zwanzig wird von einer offenen Kontur-Linie (Stroke)
auf eine gefüllte Silhouette (Fill) umgestellt, mit einem 1,35× vergrößerten Blitz. Anlass
war ein PWA-Icon-Fehler (Issue #2341: Rand-Berührung, überflüssige Zusatzlinie unter dem
Berg, "wirkt nicht modern"). Der PO hat nach drei Vorschau-Runden (Variante E) entschieden,
die neue Geometrie **grundsätzlich** als kanonische Marken-Geometrie einzuführen — nicht nur
als punktuellen PWA-Fix. Diese Spec deckt alle Flächen ab, die die Geometrie referenzieren:
Sidebar-Glyph, Browser-Favicon, PWA-Icons (inkl. Schutzzonen), Apple-Touch-Icon, das
Design-System-Showcase, den zugehörigen e2e-Test und die abgelöste Vorgänger-Spec.

## Source

- **File:** `docs/design-requests/issue_15_atomic_design/spec/brand-kit.jsx`
- **Identifier:** `BrandIcon`, `BrandIconSquare` (kanonische Referenz-Komponenten)

Betroffene Schichten (reine Frontend-Änderung, keine Go-API/Python-Core-Berührung):

- **Frontend / User-UI** → `frontend/src/lib/brand/*.svelte`, `frontend/src/lib/assets/favicon.svg`,
  `frontend/static/*` (SvelteKit, produktive Oberfläche + statische PWA-Assets)
- **Test** → `tests/test_pwa_maskable_icon.py` (Python, aber reine Pixel-Prüfung generierter
  Assets — kein Backend-Code), `frontend/e2e/issue-370-brand.spec.ts` (Playwright)
- **Dokumentation** → `docs/specs/modules/favicon-einrichten.md` (Ablösung),
  `docs/design-requests/issue_15_atomic_design/spec/brand-kit.jsx` (Referenz-Update)

## Estimated Scope

- **LoC:** ~70 (meist wenige Zeilen je Svelte-/SVG-Datei, ein neuer Testblock, kein neuer
  Code für PNG-Erzeugung — die läuft über ein Wegwerf-Playwright-Skript, nicht Teil des Repos)
- **Files:** 11 (siehe Dependencies-Tabelle)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/design-requests/issue_15_atomic_design/spec/brand-kit.jsx` | upstream (Referenz) | Kanonische Geometrie-Quelle — jede Änderung beginnt hier |
| `frontend/src/lib/brand/BrandIcon.svelte` | downstream | Sidebar-Glyph, randfüllend, von `issue-370-brand.spec.ts` byte-genau geprüft |
| `frontend/src/lib/brand/BrandIconSquare.svelte` | downstream | Square-Variante im Design-System-Showcase, Basis für App-Icon-Grafik |
| `frontend/src/lib/assets/favicon.svg`, `frontend/static/favicon.svg` | downstream (generiert aus Geometrie) | SVG-Quelle für Browser-Favicon, randfüllend |
| `frontend/static/favicon.ico`, `favicon-192.png`, `favicon-512.png` | downstream (generiert) | Browser/PWA-Icons ohne Schutzzone, randfüllend |
| `frontend/static/icon-maskable-512.png`, `apple-touch-icon.png` | downstream (generiert, MIT Schutzzone) | Android-Maskable + iOS-Homescreen, beide mit 80%-Schutzzone |
| `tests/test_pwa_maskable_icon.py` | downstream (Test, erweitert) | Schutzzonen-Pixelprüfung — muss neu auch `apple-touch-icon.png` abdecken |
| `frontend/e2e/issue-370-brand.spec.ts` | downstream (Test, bewusst umgeschrieben) | Byte-genaue DOM-Prüfung des Sidebar-Glyphs |
| `docs/specs/modules/favicon-einrichten.md` | downstream (abgelöst) | Alte Spec, deren AC-2 dem Ticket-Befund widerspricht |

## Implementation Details

```
Geometrie (ViewBox weiterhin 0 0 64 64, Farben unverändert:
Bergkamm #1a1a18 / --g-ink, Blitz #c45a2a / --g-accent, PNG-Hintergrund #f6f4ee / --g-paper):

1) Randfüllend (kein Einzug) — BrandIcon.svelte, favicon.svg (beide Kopien), favicon.ico,
   favicon-192.png, favicon-512.png:

   <path d="M3 54 L18 22 L29 38 L38 26 L52 50 L61 54 Z" fill="#1a1a18"/>
   <g transform="translate(45.5,20) scale(1.35) translate(-45.5,-20)">
     <path d="M48 11 L41 23 L45 23 L43 29 L50 17 L46 17 Z" fill="#c45a2a"/>
   </g>

   Bergkamm-Pfad ist GEOMETRISCH IDENTISCH zur bisherigen Kontur (nur fill statt
   stroke/fill:none). Blitz-Pfad ist ebenfalls unverändert, wird aber um seinen
   Schwerpunkt (45.5, 20) mit scale(1.35) vergrößert. Nebenkante
   (`M3 54 L18 22 L25 32`) und separate Horizontlinie (`<line y1="58" y2="58">`)
   entfallen ERSATZLOS — in BrandIconSquare.svelte damit auch die Bedingungen
   `showSubLine`/`showHorizon` und die zugehörigen Svelte-Props/Logik.

2) Mit Schutzzone (analog SAFE_FRACTION=0.8 aus tests/test_pwa_maskable_icon.py) —
   NUR icon-maskable-512.png und apple-touch-icon.png:
   Skalierung 0,87 statt des exakten Passungswerts 0,8828 — der hätte bei
   apple-touch-icon.png in 180 px keine Reserve (Motivkante genau auf der Randgrenze).

   <g transform="translate(6.9,6.9) scale(0.87) translate(-3,-7.85)">
     <path d="M3 54 L18 22 L29 38 L38 26 L52 50 L61 54 Z" fill="#1a1a18"/>
     <g transform="translate(45.5,20) scale(1.35) translate(-45.5,-20)">
       <path d="M48 11 L41 23 L45 23 L43 29 L50 17 L46 17 Z" fill="#c45a2a"/>
     </g>
   </g>

   apple-touch-icon.png bekommt damit ERSTMALS eine Schutzzone (bisher keine) —
   das ist die eigentliche Behebung des Ticket-Mangels "Rand-Berührung".

Erzeugungsweg SVG → PNG (kein Build-Tool im Repo, Playwright 1.63.0 als Rasterizer,
bereits Projekt-Abhängigkeit für e2e):

   a) Minimale HTML-Seite je Zielgröße schreiben, z.B.:
      <!doctype html><html><body style="margin:0">
        <svg xmlns="http://www.w3.org/2000/svg" width="512" height="512"
             viewBox="0 0 64 64">
          <rect width="64" height="64" fill="#f6f4ee"/>
          ...die jeweilige Pfad-Variante (randfüllend oder mit Schutzzone)...
        </svg>
      </body></html>

   b) Mit Playwright rendern und screenshotten, z.B.:
      npx playwright screenshot --viewport-size=512,512 <datei>.html <ziel>.png

   c) favicon.ico aus favicon-192.png (oder direkt aus der randfüllenden SVG-Variante
      bei 32×32) mit einem ICO-fähigen Konverter erzeugen (z.B. Pillow:
      `Image.open(...).save("favicon.ico", sizes=[(32,32)])`).

   Reihenfolge/Kommandos gehören als reproduzierbarer Schritt in den Implementierungs-PR
   (Wegwerf-Skript im Scratchpad, kein neues Repo-Tooling).
```

## Expected Behavior

- **Input:** Keine Laufzeit-Eingabe — reine Geometrie-/Asset-Änderung. Betroffen sind
  statische SVG-Quellen, generierte PNG/ICO-Dateien und zwei Svelte-Komponenten.
- **Output:** Überall, wo das Marken-Icon erscheint (Sidebar, Browser-Tab, PWA-Homescreen
  Android/iOS, Design-System-Showcase), zeigt sich die gefüllte Silhouette mit vergrößertem
  Blitz statt der bisherigen Kontur-Linie mit Nebenkante/Horizont.
- **Side effects:** `favicon-einrichten.md` wird als abgelöst markiert (nicht gelöscht);
  `issue-370-brand.spec.ts` AC-2 prüft künftig Fill- statt Stroke-Geometrie;
  `test_pwa_maskable_icon.py` bekommt einen zusätzlichen Testblock für
  `apple-touch-icon.png`.

## Acceptance Criteria

- **AC-1:** Given die Design-System-Showcase-Route `/_design` ist geladen, When das
  gerenderte `[data-testid="brand-icon"]`-SVG (Sidebar-Glyph, `BrandIcon.svelte`)
  inspiziert wird, Then trägt der Bergkamm-Pfad (`d="M3 54 L18 22 L29 38 L38 26 L52 50
  L61 54 Z"`) das Attribut `fill="#1a1a18"` (oder den berechneten --g-ink-Wert) und
  KEIN `stroke`-Attribut mehr, und der Blitz-Pfad liegt in einer `<g>` mit
  `transform` äquivalent zu `scale(1.35)` um seinen Schwerpunkt (45.5, 20).
  - Test: `frontend/e2e/issue-370-brand.spec.ts` AC-2 (umgeschrieben) liest die
    DOM-Attribute des live gerenderten Glyphs aus — kein Dateiinhalt-Check, sondern
    Prüfung des tatsächlich ausgelieferten SVG.

- **AC-2:** Given `BrandIconSquare.svelte` wird im Design-System-Showcase in Größe ≥32px
  gerendert, When das SVG-DOM inspiziert wird, Then existiert weder ein Pfad mit
  `d="M3 54 L18 22 L25 32"` (Nebenkante) noch ein `<line>`-Element mit `y1="58"
  y2="58"` (Horizont) — beide Zusatzelemente samt der Svelte-Bedingungen
  `showSubLine`/`showHorizon` sind entfernt.
  - Test: Playwright-Assertion auf `/_design`, die die betroffenen Selektoren auf
    `toHaveCount(0)` prüft (neuer oder erweiterter Testfall neben `issue-370-brand.spec.ts`).

- **AC-3:** Given `frontend/static/favicon.svg` (und die identische Kopie unter
  `frontend/src/lib/assets/`) wird im Browser als Bild geladen und auf 64×64px
  gerastert, When die Pixelfarbe an einem Punkt INNERHALB der Bergkamm-Fläche
  (z.B. (30, 45)) gemessen wird, Then ist der Pixel durchgehend Ink-Farbe
  (`#1a1a18`) statt — wie bei einer Kontur — Hintergrundfarbe mit dünner Umrandung.
  - Test: Playwright-Screenshot der gerenderten SVG-Datei, Pixel-Sample per Pillow
    (analog zum Vorgehen in `tests/test_pwa_maskable_icon.py`) — echte
    Bildinhalts-Prüfung, kein String-Match auf den SVG-Quelltext.

- **AC-4:** Given `frontend/static/icon-maskable-512.png` wird mit der neuen
  Silhouetten-Geometrie UND der Schutzzonen-Transformation neu erzeugt, When
  `tests/test_pwa_maskable_icon.py::TestAC2MaskableIconSchutzzone` läuft, Then
  bleibt der Test grün (keine Motivpixel außerhalb der mittleren 80% der Kantenlänge)
  — die bestehende Schutzzonen-Prüfung bleibt unverändert wirksam.
  - Test: `uv run pytest tests/test_pwa_maskable_icon.py::TestAC2MaskableIconSchutzzone -v`

- **AC-5:** Given `frontend/static/apple-touch-icon.png` wird ERSTMALS mit der
  Schutzzonen-Transformation neu erzeugt (bisher randfüllend ohne Schutzzone), When
  dieselbe Randprüf-Funktion (`border_pixels_other_than_background` aus
  `tests/test_pwa_maskable_icon.py`, wiederverwendet oder parametrisiert für
  `apple-touch-icon.png`) darauf angewendet wird, Then liefert sie eine leere Liste
  (keine Motivpixel im Rand) — das behebt den ursprünglichen Ticket-Mangel
  "Rand-Berührung auf iOS" programmatisch nachweisbar, nicht nur optisch.
  - Test: Neuer Testfall in `tests/test_pwa_maskable_icon.py` (oder Schwesterdatei),
    der `APPLE_TOUCH_ICON = STATIC_DIR / "apple-touch-icon.png"` derselben
    Randprüfung unterzieht wie `icon-maskable-512.png`.

- **AC-6:** Given `frontend/static/favicon-512.png` wird mit der neuen
  Silhouetten-Geometrie OHNE Schutzzonen-Einzug neu erzeugt (randfüllend wie bisher),
  When `tests/test_pwa_maskable_icon.py::TestRandpruefungMisstUeberhauptEtwas::
  test_randfuellendes_favicon_faellt_durch_dieselbe_pruefung` läuft, Then findet die
  Randprüfung weiterhin Motivpixel im Rand (Test bleibt wie bisher grün, weil er
  genau das Fehlschlagen der Randprüfung als Positivkontrolle erwartet) — kein
  Kollateralschaden an der bestehenden Positivkontrolle.
  - Test: `uv run pytest tests/test_pwa_maskable_icon.py::TestRandpruefungMisstUeberhauptEtwas -v`

- **AC-7:** Given `docs/design-requests/issue_15_atomic_design/spec/brand-kit.jsx`
  als kanonische Geometrie-Referenz, When die Datei nach der Umstellung gelesen wird,
  Then enthält `BrandIcon` und `BrandIconSquare` dieselbe Fill-Silhouette +
  1,35×-Blitz-Transformation wie die Svelte-Portierungen, und `BrandIconSquare`
  enthält keine Nebenkante-/Horizont-Logik mehr.
  - Test: `# doc-compliance-test` — reiner Konsistenz-Check zwischen kanonischer
    Referenzquelle und ihren Portierungen (keine eigene Laufzeit-Umgebung für
    `brand-kit.jsx` vorhanden, daher zulässige Ausnahme von der
    Dateiinhalt-Check-Regel).

- **AC-8:** Given `docs/specs/modules/favicon-einrichten.md` beschreibt in AC-2 ein
  Verhalten ("kein abgeschnittenes Icon"), das laut Issue #2341 nicht zutraf, When
  diese Spec (`brand_icon_silhouette.md`) freigegeben wird, Then trägt
  `favicon-einrichten.md` einen Status-Vermerk "Abgelöst durch
  `docs/specs/modules/brand_icon_silhouette.md`" statt stillschweigend widersprüchlich
  stehen zu bleiben.
  - Test: `# doc-compliance-test` — Status-Feld-Konsistenz zwischen alter und neuer Spec.

## Known Limitations

- Die PNG/ICO-Erzeugung bleibt Handarbeit (kein Build-Schritt in `package.json`/CI) —
  diese Spec dokumentiert den Erzeugungsweg reproduzierbar, automatisiert ihn aber nicht.
  Künftige Geometrie-Änderungen müssen den Playwright-Rasterisierungsschritt erneut manuell
  ausführen.
- `docs/specs/_archive/modules/issue_370_brand_library.md` wird nicht inhaltlich
  geändert (archiviert) — nur bei Bedarf auf Konsistenz geprüft, kein eigenes AC.
- Punkt 3 aus Issue #2341 ("wirkt nicht modern") ist keine technisch prüfbare
  Anforderung; sie gilt durch die PO-Auswahl (Variante E, Silhouette + großer Blitz)
  als erledigt und wird nicht in ein eigenes AC übersetzt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Icon-/Marken-Design ist keine der in `CLAUDE.md` gelisteten
  ADR-pflichtigen Entscheidungsflächen (Kanäle, Provider, Datenmodell/Persistenz, Auth,
  Editor-Paradigma, Test-/Deploy-Strategie). Die Entscheidung ist im PO-Artifact-Dialog
  vom 16.09.2026 dokumentiert und in `docs/context/fix-2341-pwa-logo.md` festgehalten.

## Changelog

- 2026-09-16: Initial spec created
