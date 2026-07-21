# Mini-Spec: fix-875-mobile-menu-zindex

## Was ändert sich
- `Sidebar.svelte` Zeile 208: Drawer-z-index von `z-40` auf `z-[55]` erhöhen
- Korrekte Z-Index-Hierarchie: Backdrop z-50 liegt hinter Drawer z-[55], aber TopAppBar z-[60] bleibt oben

## Was darf sich nicht ändern
- Desktop-Sidebar bleibt unverändert
- TopAppBar-z-index bleibt z-[60]
- Backdrop-z-index bleibt z-50
- Alle Navigationspfade und onclick-Handler bleiben identisch

## Manuelle Test-Schritte
1. Mobile-Viewport öffnen (< 1024px)
2. Hamburger-Icon antippen → Menü öffnet sich
3. Auf „Meine Trips" tippen → Navigation funktioniert, kein sofortiges Schließen
4. Backdrop antippen → Menü schließt sich korrekt
5. Hamburger erneut öffnen → X-Icon antippen → Menü schließt sich

## Inline-Test (wird während Implementierung geschrieben)
- [ ] Test: Drawer hat nach Öffnen z-index > Backdrop (numerisch höher als 50)
