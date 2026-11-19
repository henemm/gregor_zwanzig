---
entity_id: ganzseitenaufnahme_fixed_ausblenden
type: feature
created: 2026-11-19
updated: 2026-11-19
status: draft
version: "1.0"
workflow: feat-3013-aufnahme-fixed-ausblenden
tags: [test-infrastruktur, bildabgleich, e2e]
---

# Ganzseitenaufnahme blendet fest positionierte Elemente aus

## Approval

- [ ] Approved

## Purpose

Der gemeinsame Ganzseiten-Aufnahme-Helfer der Bildabgleich-Skripte blendet vor dem Foto alle fest positionierten Elemente (untere Handy-Navigation, Hinweisleisten) aus und stellt sie danach exakt wieder her. Ohne das schwebt die Navigationsleiste im 390-px-Ganzseitenfoto über Karten und Abschnittsköpfen und verfälscht den Bildabgleich (Befund aus #3003, Issue #3013, Epic #2913).

## Source

- **File:** `frontend/e2e/ganzseitenaufnahme.ts`
- **Identifier:** `ganzseite(page, datei)`

> Schicht: reine Test-Infrastruktur unter `frontend/e2e/`. Kein Produktcode (`frontend/src`, Go, Python) wird geändert, keine Nutzerdaten bewegt, kein Briefing- oder Alarm-Inhalt betroffen. Kein Trip/Vergleich-Pendant: der Helfer ist bereits für beide gemeinsam.

## Scope

**Im Scope:**
- Helfer `frontend/e2e/ganzseitenaufnahme.ts`: fest positionierte Elemente vor dem Ganzseitenfoto ausblenden und im `finally` exakt wiederherstellen
- Kern-Selbsttests in `frontend/e2e/ganzseitenaufnahme-selbsttest.spec.ts` (AC-1 bis AC-5)
- Kopfkommentar im Helfer mit den Grenzen (sticky, Dialoge)

**Außerhalb des Scopes:**
- Produktcode (`frontend/src`, Go, Python), insbesondere `BottomNav.svelte` und `+layout.svelte`
- Die drei aufrufenden Bildabgleich-Skripte (bleiben unverändert)
- sticky-Elemente und Viewport-Fotos offener Dialoge
- Erneute Bildprüfung der Hub-Seiten (gehört zur Abnahme #3009)

## Estimated Scope

- **LoC:** ca. +25 (Helfer) / +70 (Selbsttest)
- **Files:** 2
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/e2e/ganzseitenaufnahme.ts` | module | Helfer `ganzseite()` (#2953), wird erweitert |
| `frontend/e2e/ganzseitenaufnahme-selbsttest.spec.ts` | test | Kern-Selbsttest auf `page.setContent`, wird erweitert |
| `docs/specs/fast/fix-2953-aufnahme-breite.md` | spec | Vorgänger: Rahmen-Stile (`data-gz-aufnahme`) und Breitenprüfung |
| Playwright `page.evaluate`, `page.screenshot({ fullPage: true })` | library | Auswahl, Ausblenden und Foto |
| `hub-kopf-c2-bildabgleich.staging.spec.ts`, `s3b2795-zustellung-bilder.staging.spec.ts`, `fix2913-metrikliste-mockup.staging.spec.ts` | test | Aufrufer, bleiben unverändert und profitieren automatisch |
| `frontend/src/lib/components/ui/sidebar/BottomNav.svelte`, `frontend/src/routes/+layout.svelte` | component | Quelle der Störung (`div.bottom-shell.fixed.z-50`, fixed-Hinweisleisten), werden nicht geändert |

## Implementation Details

Im Helfer, vor `page.screenshot`, gleiche Stelle und gleiches `finally` wie die Rahmen-Aufhebung aus #2953:

1. **Auswahl nach berechnetem Stil:** alle Elemente unter `body`, deren `getComputedStyle(el).position === 'fixed'`. Keine Selektorliste, damit Navigation, Toasts und künftige Overlays ohne Pflege erfasst sind.
2. **Ausblenden mit `visibility: hidden !important`.** Das Layout bleibt unverändert, der Inhalt verschiebt sich nicht. `display: none` ist verworfen, weil es das Layout ändern könnte.
3. **Eigener Marker `data-gz-aufnahme-fixed`:** Der bisherige `style`-Attributwert (auch "nicht vorhanden") wird dort gesichert. Der Marker ist getrennt von `data-gz-aufnahme` (Rahmen-Stile), damit sich beide Rücksetzungen nicht überschreiben. Ein Element mit beiden Markern endet exakt mit seinem Ursprungs-`style`.
4. **Wiederherstellung im `finally`**, auch wenn die Breitenprüfung wirft oder das Foto scheitert. Sonst blieben Elemente in Folgeschritten unsichtbar und Klicktests darauf scheiterten. Ursprünglich fehlendes `style`-Attribut wird wieder entfernt, nicht leer gesetzt.
5. **Kopfkommentar im Helfer** hält die Entscheidungen und Grenzen unten fest.

Bewusste Entscheidungen und Grenzen:

- **sticky bleibt sichtbar** (begründete Abweichung vom Issue-Wortlaut "fixed/sticky"): sticky-Elemente liegen im Fluss und gehören zum Seiteninhalt; sie zu verstecken ließe Lücken oder entfernte Inhalt. In Hub und Einstellungen kommt keins vor (einziges sticky ist `EditorStickyFooter` im Anlegen-Rahmen).
- **Dialog-Grenze:** Geöffnete Dialoge (`dialog-content`, `dialog-overlay`) sind `fixed` und würden mit ausgeblendet. Kein Aufrufer fotografiert einen offenen Dialog; Dialog-Aufnahmen gehören in ein Viewport-Foto, nicht in ein Ganzseitenfoto.
- **Durchscheinende Kinder:** Ein Kind mit eigenem `visibility: visible` in einer ausgeblendeten Leiste bliebe sichtbar. In der App setzen BottomNav und Toasts kein `visibility`; kein Zusatzaufwand.
- **Neutral ohne fixed-Elemente:** Mockup-Seite (`mockup-hub-fassung4.html`) und Desktop 1280 (`bottom-shell` ist dort `desktop:hidden`) haben nichts Fixes; der Helfer ändert dort nichts.

## Expected Behavior

- **Input:** Playwright-Seite und Zieldatei für `ganzseite(page, datei)`.
- **Output:** Ganzseiten-PNG ohne fest positionierte Elemente, Breite gleich Viewport-Breite (Prüfung aus #2953 bleibt).
- **Side effects:** Keine bleibenden: nach dem Aufruf, auch bei Fehlschlag, haben alle Elemente exakt ihr ursprüngliches `style`-Attribut und sind wieder sichtbar.

## Test Plan

### Automated Tests (TDD RED)

Kern-Selbsttests in `frontend/e2e/ganzseitenaufnahme-selbsttest.spec.ts` auf `page.setContent` im echten Browser (Chromium), ohne Login, ohne Netz, kein Mock. Fotos werden per Pixelprüfung an der Leistenfarbe ausgewertet.

- [ ] Test 1 (Gegenprobe): GIVEN Seite mit langem Inhalt und fixed-Leiste in auffälliger Farbe WHEN Ganzseitenfoto ohne Helfer THEN Leistenfarbe ist im Foto vorhanden.
- [ ] Test 2: GIVEN dieselbe Seite WHEN `ganzseite()` THEN keine Leistenpixel im Foto, Inhalt unter der Leiste sichtbar.
- [ ] Test 3: GIVEN Leiste mit vorhandenem Inline-Style und ein Element mit beiden Markern WHEN `ganzseite()` THEN `style`-Attribute danach byte-identisch, Leiste sichtbar.
- [ ] Test 4: GIVEN Viewport, dessen Breitenprüfung wirft WHEN `ganzseite()` THEN Fehler kommt an, Leiste trotzdem wiederhergestellt.
- [ ] Test 5: GIVEN Seite ohne fixed-Elemente WHEN `ganzseite()` THEN Foto und Seitenstile unverändert gegenüber dem Stand vor der Änderung.

Der Selbsttest wird vor der Implementierung rot nachgewiesen (Test 2 scheitert, solange nichts ausgeblendet wird).

## Acceptance Criteria

- **AC-1:** Given eine Seite mit langem Inhalt und einer fest positionierten Leiste in auffälliger Farbe / When ein Ganzseitenfoto ohne Ausblenden gemacht wird / Then enthält das Foto Pixel in der Leistenfarbe (Gegenprobe: der Aufbau bildet den Fehler nach).
  - Test: Der Fehler aus #3003 wird im echten Browser nachgestellt; ohne diese Gegenprobe wäre AC-2 nicht aussagekräftig.

- **AC-2:** Given dieselbe Seite / When die Ganzseitenaufnahme mit dem Helfer gemacht wird / Then enthält das Foto keine Pixel in der Leistenfarbe und der Inhalt, den die Leiste sonst verdeckt hätte, ist sichtbar.
  - Test: Pixelprüfung im Foto auf Leistenfarbe sowie auf Inhaltsfarbe an der Stelle unter der Leiste.

- **AC-3:** Given eine fest positionierte Leiste mit bereits vorhandenem Inline-Style und ein Element, das beide Marker (`data-gz-aufnahme`, `data-gz-aufnahme-fixed`) betrifft / When die Aufnahme abgeschlossen ist / Then ist die Leiste wieder sichtbar und das `style`-Attribut aller Elemente ist byte-identisch zum Zustand vor der Aufnahme.
  - Test: `style`-Attribute vor und nach `ganzseite()` im Browser vergleichen; Sichtbarkeit der Leiste prüfen.

- **AC-4:** Given eine Aufnahme, bei der die Breitenprüfung einen Fehler wirft / When der Helfer den Fehler weitergibt / Then ist die fest positionierte Leiste trotzdem wiederhergestellt (sichtbar, ursprünglicher `style`).
  - Test: Aufruf mit erzwungener Breitenabweichung erwartet den Fehler; danach Zustand der Leiste prüfen, damit Folge-Klicktests nicht scheitern.

- **AC-5:** Given eine Seite ohne fest positionierte Elemente (Mockup-Seite oder Desktop-Breite 1280) / When die Ganzseitenaufnahme gemacht wird / Then ist das Foto unverändert gegenüber dem Stand vor dieser Änderung und alle Seitenstile bleiben unverändert.
  - Test: Seite ohne fixed-Element aufnehmen, Foto-Bytes bzw. Pixel gegen Aufnahme ohne Ausblende-Schritt vergleichen und `style`-Attribute prüfen.

## Definition of Done

- AC-1 bis AC-5 durch die Kern-Selbsttests im echten Browser belegt, Selbsttest grün
- Gegenprobe (AC-1) zeigt, dass der Testaufbau den Fehler ohne Helfer nachbildet
- Ein Bildabgleich-Lauf gegen Staging in 390 px (Trip und Orte) zeigt den Inhalt ohne schwebende Navigation; Ergebnis im Issue #3013 dokumentiert
- Adversary-Verdict VERIFIED, alle 6 CI-Checks grün, Änderung in `main`

## Known Limitations

- sticky-Elemente bleiben bewusst sichtbar (Abweichung vom Issue-Wortlaut, siehe Implementation Details).
- Offene Dialoge werden im Ganzseitenfoto ebenfalls ausgeblendet; dafür ist ein Viewport-Foto zu verwenden.
- Ein Kind mit eigenem `visibility: visible` in einer fixed-Leiste würde durchscheinen; in der App nicht vorhanden.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Erweiterung eines Test-Werkzeugs nach dem bestehenden Muster aus #2953; keine Entscheidungsfläche (Kanäle, Provider, Datenmodell, Auth, Deploy) berührt.

## Changelog

- 2026-11-19: Initial spec created (Issue #3013, Workflow feat-3013-aufnahme-fixed-ausblenden)
