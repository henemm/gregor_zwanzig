# Context: issue-373-mobile

## Request Summary
#373 (Epic #368): `frontend/src/lib/components/mobile/` mit 12 M*-Touch-Primitiven aus `mobile-shell.jsx`. Eigenständige Touch-Atome (44px Hit-Area), NICHT Mobile-Varianten der Molecules (C3). Bridge-Ansatz wie #371 (PO-bestätigt „schonend, nichts brechen").

## Stand: 10 neu, 2 bestehen
| Primitive | Status |
|-----------|--------|
| MBtn, MInput, MField, MSwitch, MTab, MIcon | **NEU** (aus mobile-shell.jsx) |
| Drawer, Sheet, Toast, MobileShell | **NEU** |
| TopAppBar | existiert `ui/sidebar/TopAppBar.svelte` (#267) → konsolidieren |
| BottomNav | existiert `ui/sidebar/BottomNav.svelte` (#267) → konsolidieren |

`lib/components/mobile/` existiert noch nicht. #312 (Toast/Sheet/Switch-Primitive) wurde NIE als Komponenten gebaut → #373 erfüllt #312 (danach #312 schließen).

## Props (body-15 §Mobile + mobile-shell.jsx)
- **MBtn**: variant, size md|lg|xl, block, icon (lg≥44px)
- **MInput**: value, type, placeholder, leftIcon (min font 16px gegen iOS-Zoom)
- **MField**: label, sub + slot (Touch-Padding)
- **MSwitch**: checked, label (44px Hit-Area)
- **MTab**: items, active, onChange, scrollable
- **MIcon**: kind (menu|back|close|plus|search|bell|…), size, color
- **TopAppBar**: title, eyebrow, onMenu, leftIcon, right, dense, scrolled
- **BottomNav**: active, onChange
- **Drawer**: open, onClose
- **Sheet**: open, onClose, title, eyebrow, snap full|half|peek, footer
- **Toast**: kind info|success|warn|error, msg, action, hint
- **MobileShell**: Template (TopAppBar + ScreenScroll + BottomNav + Drawer/Sheet/Toast-Slots)

Interne Helfer (in mobile/ mitbauen, nicht exportieren oder als Sub): IconBtn, NavIcon, DrawerGroup, DrawerItem, ScreenScroll. Demo-Rahmen (PhoneFrame, MobileStatusBar, HomeIndicator) gehören NICHT in die Bibliothek → Showcase #374.

## Token-Disziplin
mobile-shell.jsx: 78 `var(--g-*)`-Treffer, nur 2 Inline-Hex (#0e0e0c/#1a1a18 in Demo-Rahmen, nicht in M*-Primitiven). C1 erfüllbar.

## Architektur (Bridge-Ansatz)
- 10 neue M*-Komponenten in `mobile/` (Svelte 5, `<script lang="ts">`, Token-basiert, 44px Touch, SSR-fest).
- TopAppBar/BottomNav: `mobile/`-Re-Export-Wrapper auf `ui/sidebar/`-Pendants + additive Prop-Angleichung an mobile-shell.jsx falls Props fehlen (backward-compat, #267-Aufrufer unberührt).
- `mobile/index.ts` exportiert alle 12.

## Risiken
- MInput 16px + MSwitch/MBtn 44px Touch-Mindestmaß sind harte AC.
- Drawer/Sheet/Toast haben Overlay/Portal-Verhalten → SSR-Festigkeit (kein `window.*`/`document.*` ohne `browser`-Guard) kritisch.
- TopAppBar/BottomNav-Konsolidierung darf #267-Mobile-Navigation nicht brechen.
- Reines Frontend, kein Backend. Bibliothek inert bis Nutzung (visuelle Abnahme via Showcase #374).
