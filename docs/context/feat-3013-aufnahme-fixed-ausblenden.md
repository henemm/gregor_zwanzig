# Context: feat-3013-aufnahme-fixed-ausblenden

## Request Summary
Issue #3013 (Epic #2913): Der gemeinsame Ganzseiten-Aufnahme-Helfer der Bildabgleich-Skripte soll fest positionierte Elemente (untere Handy-Navigation `bottom-shell`, Overlays/Toasts) vor dem Ganzseitenfoto ausblenden und danach exakt wiederherstellen. Befund aus der Bildprüfung #3003 (14.11.2026): die schwebende Navigationsleiste liegt im 390-px-Foto über Vorlage-Karte und Abschnittsköpfen.

## Related Files
| File | Relevance |
|------|-----------|
| frontend/e2e/ganzseitenaufnahme.ts | Gemeinsamer Helfer `ganzseite(page, datei)` (#2953): hebt `.h-screen`/`main`-Begrenzung zur Aufnahmezeit auf, prüft PNG-Breite = Viewport, setzt Stile per `data-gz-aufnahme` im finally zurück. Hier kommt das Ausblenden hinein. |
| frontend/e2e/ganzseitenaufnahme-selbsttest.spec.ts | Kern-Selbsttest des Helfers auf `page.setContent`-Seiten (echter Browser, kein Mock, ohne Login). Hier kommen die neuen Tests hinein (fixed-Element verdeckt Inhalt ohne Helfer; mit Helfer unverdeckt; danach wiederhergestellt, auch bei Fehlschlag). |
| frontend/e2e/hub-kopf-c2-bildabgleich.staging.spec.ts | Aufrufer (Mockup- und Staging-Aufnahmen, Trip/Orte × DE/EN × 1280/390). |
| frontend/e2e/s3b2795-zustellung-bilder.staging.spec.ts | Aufrufer (Zustellung-Bilder). |
| frontend/e2e/fix2913-metrikliste-mockup.staging.spec.ts | Aufrufer. |
| frontend/src/lib/components/ui/sidebar/BottomNav.svelte | Quelle der Störung: `div.bottom-shell.fixed.z-50` (nur < desktop). |
| frontend/src/routes/+layout.svelte:302/341/367 | Weitere `position: fixed`-Hinweisleisten (Toasts) über der Navigation. |

## Existing Patterns
- Stil-Änderung nur zur Aufnahmezeit mit Sicherung des alten `style`-Attributs in einem data-Attribut und exakter Wiederherstellung im `finally` (#2953). Das neue Ausblenden folgt demselben Muster, mit eigenem Marker, damit sich beide Rücksetzungen nicht überschreiben (ein Element kann beides betreffen: z. B. ein fixed `main` wäre denkbar).
- Selbsttest-Muster: Gegenprobe-Test beweist, dass der Aufbau den Fehler ohne Helfer nachbildet; danach Helfer-Test.

## Analyse (kurz, Summe 1)
- Welche Elemente: alle mit **berechnetem** `position: fixed` (getComputedStyle), nicht nur `.bottom-shell` — deckt Navigation, Toasts und künftige Overlays ab, ohne Selektor-Liste, die veraltet.
- `sticky`: im Hub/Einstellungen kommt keins vor (einziges sticky ist `EditorStickyFooter` im Anlegen-Rahmen). Sticky-Elemente bleiben im Fluss und gehören zum Seiteninhalt (sie im Foto zu verstecken, ließe Lücken bzw. entfernte Inhalt). Daher: nur `fixed` ausblenden; sticky bleibt bewusst sichtbar. Das ist eine Abweichung vom Issue-Wortlaut („fixed/sticky") und wird in der Spec begründet.
- Wie ausblenden: `visibility: hidden !important` (Layout unverändert, keine Verschiebung des Inhalts; `display:none` könnte Layout ändern, z. B. `--g-nav-clearance`-Polster bleibt ohnehin).
- Mockup-Seite (`mockup-hub-fassung4.html`) hat kein `position: fixed` → Helfer wirkt dort neutral, Mockup-Aufnahmen unverändert.
- Desktop 1280: `bottom-shell` ist `desktop:hidden` → keine Änderung.

## Dependencies
- Upstream: Playwright `page.evaluate`, `page.screenshot({fullPage:true})`.
- Downstream: drei Bildabgleich-Staging-Skripte und der `mockup-bildpruefer`-Ablauf (Abnahme #3009).

## Existing Specs
- docs/specs/fast/fix-2953-aufnahme-breite.md (Vorgänger-Helfer).

## Risks & Considerations
- Wiederherstellung muss auch bei Fehlschlag der Breitenprüfung greifen (finally), sonst bleibt die Navigation in nachfolgenden Testschritten unsichtbar und Klick-Tests auf ihr scheitern.
- Zwei Marker getrennt halten (Rahmen-Stile vs. Ausblenden), sonst überschreibt die eine Rücksetzung die andere.
- Reine Test-Infrastruktur, kein Produktcode, kein Deploy-Effekt auf Nutzer.

## Analysis

### Type
Feature (Test-Infrastruktur, kein Produktcode)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| frontend/e2e/ganzseitenaufnahme.ts | MODIFY | Vor `page.screenshot` alle Elemente mit berechnetem `position: fixed` per `visibility: hidden !important` ausblenden; alten `style` in eigenem Marker `data-gz-aufnahme-fixed` sichern; im selben `finally` exakt wiederherstellen, getrennt vom Marker `data-gz-aufnahme`, so dass ein Element mit beiden Markern am Ende genau seinen Ursprungs-`style` hat. |
| frontend/e2e/ganzseitenaufnahme-selbsttest.spec.ts | MODIFY | Neue Kern-Selbsttests auf `page.setContent`: (a) Gegenprobe: fixed-Leiste verdeckt Inhalt im Ganzseitenfoto ohne Ausblenden (Pixelprüfung an der Leistenfarbe), (b) mit Helfer keine Pixel der Leistenfarbe im Foto, (c) nach dem Helfer ist die Leiste wieder sichtbar und ihr `style`-Attribut identisch (inkl. vorher vorhandenem Inline-Style und Element mit beiden Markern), (d) Wiederherstellung auch, wenn die Breitenprüfung wirft. |

Aufrufer (`hub-kopf-c2-bildabgleich`, `s3b2795-zustellung-bilder`, `fix2913-metrikliste-mockup`) bleiben unverändert und profitieren automatisch.

### Scope Assessment
- Files: 2
- Estimated LoC: +25 (Helfer) / +70 (Selbsttest)
- Risk Level: LOW — nur Test-Werkzeug, Wiederherstellung im `finally`; Desktop-Aufnahmen und Mockup-Seiten (kein `fixed`) bleiben unverändert.

### Technical Approach
- Auswahl über `getComputedStyle(el).position === 'fixed'` über alle Elemente unter `body`, keine Selektor-Liste → erfasst `bottom-shell`, Toast-Leisten aus `+layout.svelte` und künftige Overlays.
- Ausblenden mit `visibility: hidden !important` (Layout bleibt, kein Verschieben des Inhalts); `display: none` verworfen.
- `sticky` bleibt sichtbar (Abweichung vom Issue-Wortlaut, in Spec begründen): sticky liegt im Fluss und gehört zum Inhalt (`EditorStickyFooter` nur im Anlegen-Rahmen, in Hub-/Einstellungs-Aufnahmen nicht vorhanden).
- Bewusste Grenze: geöffnete Dialoge (`dialog-content`/`dialog-overlay` sind `fixed`) würden ebenfalls ausgeblendet. Kein heutiger Aufrufer fotografiert einen offenen Dialog; Dialog-Aufnahmen gehören in ein Viewport-Foto, nicht in ein Ganzseitenfoto. In Spec und Kopfkommentar des Helfers festhalten.
- Kind-Element mit eigenem `visibility: visible` in einer ausgeblendeten fixed-Leiste würde durchscheinen; in der App nicht vorhanden (BottomNav/Toasts setzen kein `visibility`), daher kein Zusatzaufwand.

### Dependencies
- Upstream: Playwright `page.evaluate`, `page.screenshot({ fullPage: true })`.
- Downstream: drei Bildabgleich-Staging-Skripte, `mockup-bildpruefer`-Abnahme (#3009).

### Open Questions
- keine (keine Produktentscheidung berührt; sticky/Dialog-Grenze ist technische Abwägung)
