# Context: fix-2341-pwa-logo

## Request Summary

Issue #2341: Das PWA-Homescreen-Icon (iOS-Screenshot im Ticket) hat drei Mängel —
(1) das Motiv berührt den Rand, (2) eine „komische zweite Linie" unter dem Berg,
(3) der Stil wirkt nicht wie ein modernes Logo.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/static/apple-touch-icon.png` | Datei, die iOS tatsächlich lädt (`app.html:16`) — das ist das im Screenshot gezeigte Icon |
| `frontend/static/favicon.svg` | Statische SVG-Quelle, randfüllend, enthält Hauptpfad + Nebenkante + Horizont |
| `frontend/static/favicon-192.png`, `favicon-512.png`, `icon-maskable-512.png`, `favicon.ico` | Weitere generierte Icon-Dateien, alle randfüllend (nicht maskable-sicher außer `icon-maskable-512.png`) |
| `frontend/src/lib/brand/BrandIconSquare.svelte` | Svelte-Quelle „1:1 portiert aus brand-kit.jsx" — Square-Variante mit Nebenkante + Horizont, Basis für die App-Icon-Grafik. Nur in `_design-system`-Showcase eingebunden, nicht live im Produkt |
| `frontend/src/lib/brand/BrandIcon.svelte` | Sidebar-Glyph — **nur** die zwei Hauptpfade (Blitz + Bergkamm), **keine** Nebenkante/Horizont |
| `frontend/src/app.html` | `<link>`-Tags für Favicon/Apple-Touch-Icon/Manifest |
| `frontend/static/site.webmanifest` | PWA-Manifest, deklariert `favicon-192.png`/`favicon-512.png` (`purpose: any`) und `icon-maskable-512.png` (`purpose: maskable`) |
| `tests/test_pwa_maskable_icon.py` | Pillow-Randprüfung für `icon-maskable-512.png` (AC-2 aus `pwa_installierbar_offline_start.md`) — inkl. Positivkontrolle, die verlangt, dass `favicon-512.png` **randfüllend bleibt** |
| `frontend/e2e/issue-370-brand.spec.ts` | Prüft **byte-genau** die SVG-`d`-Attribute von `BrandIcon.svelte` gegen `brand-kit.jsx` (Sidebar-Glyph) |
| `docs/specs/modules/favicon-einrichten.md` | Bestehende Spec zur Icon-Einrichtung (Draft, kein Issue) — legt Farben/Dateien/HTML-Tags fest |
| `docs/design-requests/issue_15_atomic_design/spec/brand-kit.jsx` | Kanonische Quelle der Brand-Icon-Geometrie |

## Existing Patterns

- Die Brand-Geometrie lebt kanonisch in `brand-kit.jsx` und wird 1:1 in Svelte-Komponenten portiert (`BrandIcon.svelte`, `BrandIconSquare.svelte`) sowie manuell in statische SVG/PNG-Dateien unter `frontend/static/` übertragen.
- **Kein automatisierter Build-Schritt** SVG → PNG: Die fünf Bilddateien unter `frontend/static/` sind Handarbeit (kein Skript in `package.json`, keine zugehörige CI-Aufgabe).
- Für Android existiert bereits ein maskable-sicheres Symbol mit 80 %-Schutzzone (`icon-maskable-512.png`), geprüft durch `tests/test_pwa_maskable_icon.py`. Für iOS (`apple-touch-icon.png`) gibt es **keine** äquivalente Schutzzone — iOS rundet das Icon selbst ab, ohne dass die App das Motiv einrücken müsste, aber „darf Rand nicht berühren" (PO-Wunsch) ist trotzdem ein optisches, nicht technisches Kriterium.

## Dependencies

- **Upstream (Geometrie-Quelle):** `docs/design-requests/issue_15_atomic_design/spec/brand-kit.jsx` — jede Geometrie-Änderung muss hier beginnen, damit Sidebar-Glyph, Design-System-Showcase und Icon-Dateien nicht auseinanderlaufen.
- **Downstream (was von der Geometrie abhängt):**
  - `frontend/e2e/issue-370-brand.spec.ts` — bricht, wenn die **Hauptpfade** (Blitz `D_BLITZ`, Bergkamm `D_BERGKAMM`) verändert werden. Nebenkante/Horizont sind davon **nicht** betroffen (kein Teil des geprüften Pfads).
  - `tests/test_pwa_maskable_icon.py` — die Positivkontrolle-Klasse `TestRandpruefungMisstUeberhauptEtwas` verlangt ausdrücklich, dass `favicon-512.png` randfüllend bleibt. Wird `favicon-512.png` selbst eingerückt, wird dieser Test rot — das ist dann kein Kollateralschaden, sondern der Test muss bewusst mitgezogen/neu begründet werden.
  - `frontend/src/routes/_design-system/+page.svelte` — zeigt `BrandIconSquare` in vier Größen; rein visuelle Regression, kein Test.

## Existing Specs

- `docs/specs/modules/favicon-einrichten.md` — regelt heutige Icon-Dateien, Farben, HTML-Tags (Draft-Status, kein Issue-Bezug)
- `docs/specs/modules/pwa_installierbar_offline_start.md` — AC-2 zur maskable-Schutzzone (Android), PO-Approved

## Risks & Considerations

- **Positivkontrolle bricht bei falscher Anpassung:** Wird `favicon-512.png` eingerückt statt weiterhin randfüllend gehalten, meldet `tests/test_pwa_maskable_icon.py::TestRandpruefungMisstUeberhauptEtwas` einen Fehlschlag, der wie ein Fremdbefund aussieht. Die Spec muss festlegen: `favicon-512.png` bleibt randfüllend (Browser-Tab-Kontext, kein Beschnitt), **nur** `apple-touch-icon.png` bekommt eine Schutzzone.
- **Byte-genauer e2e-Test:** Geometrie-Änderungen an den zwei Hauptpfaden von `BrandIcon.svelte` würden `issue-370-brand.spec.ts` (AC-2) brechen. Sofern die Spec nur Nebenkante/Horizont/Einrückung ändert, bleibt dieser Test unberührt.
- **Kein Build-Pipeline:** PNG-Erzeugung aus SVG ist manuell. Die Spec sollte den exakten Erzeugungsweg (Werkzeug/Kommando) dokumentieren, damit künftige Icon-Änderungen nicht erneut Handarbeit sind.
- **Punkt 3 („modernes Logo") ist keine prüfbare technische Anforderung.** Tragfähiges AC: „Icon entspricht der vom PO gewählten Variante" — Varianten werden in der Spec-Phase als gerenderte Optionen vorgelegt.

## Analyse (kombiniert mit Kontext, Standard-Track)

**Ursache der drei Mängel:**

1. **Rand-Berührung:** `apple-touch-icon.png` wird direkt aus dem randfüllenden `favicon.svg`/`BrandIconSquare`-Motiv erzeugt, ohne Einrückung. iOS wendet selbst KEINE automatische Schutzzone an (anders als Android bei `purpose: maskable`) — das Motiv liegt also 1:1 bis an die Kante.
2. **„Zweite Linie unter dem Berg":** In `BrandIconSquare.svelte`/`favicon.svg` gibt es zwei Zusatzelemente, die in `BrandIcon.svelte` (Sidebar) nicht vorkommen: die Horizont-Linie (`y=58`, Opacity 0.3) läuft waagerecht **unter** dem gesamten Bergmotiv — das deckt sich am ehesten mit „unter dem Berg". Die Nebenkante (`M3 54 L18 22 L25 32`, Opacity 0.45) liegt **auf** der linken Bergflanke, nicht darunter. Bei kleiner Darstellung (App-Icon-Größe) wirkt die Horizontlinie als optisch überflüssige zweite Linie.
3. **„Nicht modern":** Geschmacksfrage ohne technisches Kriterium — wird in der Spec-Phase über PO-Auswahl aus gerenderten Varianten gelöst.

## PO-Entscheidung (16.09., per Artifact-Vorschau)

Drei Runden Vorschau (`https://claude.ai/artifact/35jJqZV8NPatNRTDuParxZ`), PO wählte **Variante E** und erweiterte den Auftrag ausdrücklich: **„Dann aber auch grundsätzlich ändern"** — die Silhouette wird zur neuen kanonischen Marken-Geometrie, nicht nur ein PWA-Icon-Fix.

**Neue Geometrie (ersetzt die bisherige Linien-Kontur überall):**
- Bergkamm als **gefüllte Silhouette** (`fill="#1a1a18"`, kein Stroke) statt offener Kontur-Linie. Pfad bleibt geometrisch identisch (`M3 54 L18 22 L29 38 L38 26 L52 50 L61 54 Z`), nur `fill` statt `stroke`/`fill:none`.
- Blitz **1,35× vergrößert**, zentriert um seinen Schwerpunkt `(45.5, 20)`: `<g transform="translate(45.5,20) scale(1.35) translate(-45.5,-20)">` um den unveränderten Blitz-Pfad.
- Nebenkante (`M3 54 L18 22 L25 32`) und separate Horizontlinie (`<line y1="58" y2="58">`) entfallen ersatzlos — die Silhouette braucht sie nicht, sie waren nur Zusatzlinien der alten Kontur-Optik.

**Randbehandlung — zwei Klassen, nicht pauschal:**
- **Mit Sicherheitsabstand** (Schutzzone analog `SAFE_FRACTION = 0.8`, Transform `translate(6.4,6.4) scale(0.8828) translate(-3,-7.85)` um die neue Geometrie): `icon-maskable-512.png` (technisch nötig, Android-Beschnitt) und `apple-touch-icon.png` (PO-Wunsch aus dem Ticket — „darf Rand nicht berühren").
- **Randfüllend wie heute, kein Einzug:** `BrandIcon.svelte` (Sidebar), `favicon.svg`/`.ico`, `favicon-192.png`, `favicon-512.png` — dort schneidet nichts zu, ein Einzug wäre nur Leerraum. **Wichtig:** `favicon-512.png` bleibt damit die randfüllende Positivkontroll-Datei für `tests/test_pwa_maskable_icon.py` — unverändertes Verhalten dieses Tests bleibt intakt.

**Betroffene Dateien (vollständige Liste für die Spec):**
| Datei | Änderung |
|---|---|
| `docs/design-requests/issue_15_atomic_design/spec/brand-kit.jsx` | Kanonische Geometrie aktualisieren (Referenz-Quelle) |
| `frontend/src/lib/brand/BrandIcon.svelte` | Silhouette statt Kontur, größerer Blitz, kein Einzug |
| `frontend/src/lib/brand/BrandIconSquare.svelte` | Silhouette statt Kontur, größerer Blitz, kein Einzug (Nebenkante/Horizont-Logik entfällt komplett) |
| `frontend/src/lib/assets/favicon.svg` | Silhouette, größerer Blitz, kein Einzug |
| `frontend/static/favicon.svg` | dito |
| `frontend/static/favicon.ico` | neu erzeugen aus der neuen Geometrie |
| `frontend/static/favicon-192.png` | neu erzeugen, kein Einzug |
| `frontend/static/favicon-512.png` | neu erzeugen, kein Einzug (bleibt Positivkontroll-Referenz) |
| `frontend/static/icon-maskable-512.png` | neu erzeugen MIT Einzug |
| `frontend/static/apple-touch-icon.png` | neu erzeugen MIT Einzug |
| `frontend/e2e/issue-370-brand.spec.ts` | `D_BLITZ`/`D_BERGKAMM`-Konstanten und Prüf-Logik (Pfad statt Stroke-Kontur) bewusst auf neue Geometrie umschreiben |
| `docs/specs/modules/favicon-einrichten.md` | AC-2 widerspricht dem Ticket-Befund („kein abgeschnittenes Icon" traf nicht zu) — wird durch die neue Spec abgelöst/ergänzt |
| `docs/specs/_archive/modules/issue_370_brand_library.md` | ggf. Verweis/Status ergänzen (archiviert, nur zur Konsistenz prüfen) |

**Erzeugungsweg SVG → PNG:** Kein Build-Tool im Repo vorhanden. Playwright (bereits Projekt-Abhängigkeit für e2e, Version 1.63.0) wird als Rasterizer verwendet — Screenshot einer HTML-Seite mit dem Ziel-SVG in exakter Pixelgröße. Kommando gehört in die Spec als reproduzierbarer Schritt.

**Nicht mehr offen:** Punkt 3 „modern" ist durch die PO-Auswahl (Silhouette + großer Blitz) beantwortet — kein AC mehr nötig, das Ergebnis der Auswahl wird 1:1 in die ACs übersetzt.
