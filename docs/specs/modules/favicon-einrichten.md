# Spec: Favicon einrichten

**Issue:** (ohne Issue-Nr., direkter PO-Auftrag)
**Status:** Draft
**Created:** 2026-05-27

## Was wird gemacht

Das Svelte-Standard-Favicon wird durch das kanonische gregor.zwanzig-Brand-Icon (Bergkamm + Blitz-Glyph, Farben aus Design-System) ersetzt. Browser, iOS-Homescreen und Android/PWA erhalten je die passende Datei.

## Dateien & Artefakte

| Datei | Zweck |
|-------|-------|
| `frontend/src/lib/assets/favicon.svg` | Vektor-Icon (transparenter Hintergrund) – für moderne Browser |
| `frontend/static/favicon.ico` | 32×32 Fallback für IE / alte Browser |
| `frontend/static/apple-touch-icon.png` | 180×180 für iOS „Zum Startbildschirm" |
| `frontend/static/favicon-192.png` | 192×192 für Android Chrome |
| `frontend/static/favicon-512.png` | 512×512 für PWA-Splash |
| `frontend/static/site.webmanifest` | PWA-Deklaration |
| `frontend/src/app.html` | Alle `<link>`-Tags |
| `frontend/src/routes/+layout.svelte` | Import auf neues SVG zeigen |

## Brand-Icon-Geometrie (aus brand-kit.jsx)

ViewBox 64×64, konkrete Hex-Farben:
- Blitz: `#c45a2a` (--g-accent)
- Bergkamm: `#1a1a18` (--g-ink)
- Hintergrund (nur für PNG): `#f6f4ee` (--g-paper)

## HTML-Tags in app.html (Best Practice 2026)

```html
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
```

## Acceptance Criteria

**AC-1:** Given ein moderner Browser (Chrome/Firefox/Edge/Safari), When die App geöffnet wird, Then erscheint der Bergkamm+Blitz-Glyph (kein Svelte-Logo) im Browser-Tab.

**AC-2:** Given ein iOS-Gerät, When der User „Zum Startbildschirm" tippt, Then erscheint apple-touch-icon.png (180×180, Paper-Hintergrund, kein abgeschnittenes Icon).

**AC-3:** Given der Browser ruft `/favicon.ico` ab, Then antwortet der Server mit einer validen ICO-Datei (32×32).

**AC-4:** Given `/site.webmanifest`, Then sind `name`, `icons` (192+512) und `theme_color` (#f6f4ee) gesetzt.

**AC-5:** Given der +layout.svelte-Import, Then zeigt `<svelte:head>` auf die neue favicon.svg (kein Svelte-Logo mehr).
