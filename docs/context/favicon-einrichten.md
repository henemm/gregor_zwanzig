# Context: Favicon einrichten

## Request Summary
Das bestehende Svelte-Standard-Favicon durch das kanonische BrandIcon (Bergkamm + Blitz) ersetzen und einen vollständigen, browser-kompatiblen Favicon-Stack nach 2026-Best-Practices aufbauen.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/assets/favicon.svg` | Aktuelle Svelte-Logo-SVG – wird ersetzt |
| `frontend/src/routes/+layout.svelte` | Importiert favicon.svg, setzt `<link rel="icon">` via svelte:head |
| `frontend/src/app.html` | HTML-Template – hier kommen alle `<link>`-Tags rein |
| `frontend/static/` | Statische Assets (aktuell nur robots.txt) |

## Existing Patterns
- Design-System-Quelle: `/tmp/gz-favicon-handoff/gregor-zwanzig/project/brand-kit.jsx` definiert `BrandIcon` und `BrandIconSquare`
- Token-Farben: `--g-ink: #1a1a18`, `--g-accent: #c45a2a`, `--g-paper: #f6f4ee`
- BrandIconSquare-Geometrie (64×64 viewBox):
  - Blitz: `M48 11 L41 23 L45 23 L43 29 L50 17 L46 17 Z` → fill accent
  - Hauptkamm: `M3 54 L18 22 L29 38 L38 26 L52 50 L61 54 Z` → stroke ink
  - Nebenkamm (optional): `M3 54 L18 22 L25 32` → stroke ink, opacity 0.45
  - Horizont (optional): `x1="3" y1="58" x2="61" y2="58"` → opacity 0.3

## Favicon-Stack (Best Practice 2026)
1. `favicon.svg` — transparent, für Chrome/Firefox/Edge/Safari modern
2. `favicon.ico` — 32×32 für IE/alte Browser
3. `apple-touch-icon.png` — 180×180 für iOS Safari Home Screen
4. `favicon-192.png` — 192×192 für Android Chrome
5. `favicon-512.png` — 512×512 für PWA-Splash
6. `site.webmanifest` — PWA-Deklaration

## Dependencies
- sharp-cli (bereits installiert, npx-Zugriff vorhanden, kann SVG→PNG)
- to-ico oder equivalentes Tool für ICO-Generierung

## Risks & Considerations
- `+layout.svelte` importiert favicon via Svelte-Import `$lib/assets/favicon.svg` → muss erhalten bleiben (oder wird auf `/favicon.svg` aus static/ umgestellt)
- Der SVG-Import in Svelte bundelt das Icon als Data-URL → bei großen SVGs ungünstig; für Favicon besser über static/ und `app.html`
- ICO-Generierung braucht extra npm-Tool
