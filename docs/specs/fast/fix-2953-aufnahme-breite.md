# Mini-Spec: fix-2953-aufnahme-breite

Issue #2953 (Nebenbefund aus #2913). Messung 14.11.2026 gegen Staging (390×844, Trip + Vergleich,
langer und normaler Titel, Reiter Wetter + Übersicht): **im normalen Scrollen bleibt jede Seite exakt
390 px breit**, kein Element ragt über den rechten Rand. Nutzer sehen kein seitliches Scrollen.

Die zu breiten Bilder entstehen nur im Ganzseiten-Aufnahme-Helfer der Testskripte: er setzt
`overflow: visible` auf `<main>`. `<main>` ist Flex-Element; ohne `overflow:auto` wird seine
automatische Mindestbreite zur min-content-Breite des Inhalts, `<main>` wächst (Vergleich-Übersicht
526–537 px, **auch mit kurzem Titel** — der Titel ist nicht die Ursache). Gegenprobe mit zusätzlichem
`min-width: 0` auf den Aufnahme-Zielen: alle acht Aufnahmen 390 px.

## Was ändert sich
- Aufnahme-Helfer `ganzseite()` in `frontend/e2e/fix2913-metrikliste-mockup.staging.spec.ts` und
  `frontend/e2e/hub-kopf-c2-bildabgleich.staging.spec.ts`: zusätzlich `min-width: 0 !important`
  auf den Aufnahme-Zielen setzen (wird wie die übrigen Stile danach zurückgesetzt).
- Beide Helfer prüfen nach der Aufnahme, dass die PNG-Breite (IHDR Bytes 16–19) der
  Viewport-Breite entspricht; eine zu breite Aufnahme schlägt fehl statt ein verfälschtes Bild
  an den Bildprüfer zu geben.

## Was darf sich nicht ändern
- Kein Produktcode (Seitenkopf, Layout, `<main>`) wird geändert — es gibt keinen Nutzerfehler.
- Höhe der Ganzseitenaufnahme bleibt wie bisher (höher als der Viewport).
- Stile der Seite nach der Aufnahme exakt wie vorher (Zurücksetzen über `data-gz-aufnahme`).

## Manuelle Test-Schritte
1. Staging-Spec #2913 (`playwright.2913-metrikliste.staging.config.ts`) laufen lassen.
2. Aufnahmen `*-390.png` sind 390 px breit, die Breitenprüfung ist grün.

## Inline-Test (wird während Implementierung geschrieben)
- [ ] Breitenprüfung im Aufnahme-Helfer (PNG-Breite == Viewport-Breite), Gegenprobe: ohne
      `min-width: 0` schlägt sie bei Vergleich-Übersicht 390 px fehl.
