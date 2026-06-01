# #312 — Design: Fehlende UI-Primitive — Toast, DropdownMenu, Segmented Control, Switch, Sheet

**Labels:** `priority:high` `frontend` `foundation` `area:components` `for:claude-design`
**URL:** https://github.com/henemm/gregor_zwanzig/issues/312
**Erstellt:** 2026-05-21

---

## Was fehlt

Für saubere Svelte-Implementierungen fehlen **5 UI-Komponenten** im Design-System, die ich aktuell entweder gar nicht habe oder ad-hoc selbst zusammenbaue.

## Fehlende Komponenten

### 1. Toast / Notification
**Wo gebraucht:** Überall — nach Speichern, nach Test-Briefing, nach Fehler.
**Aktueller Zustand:** Keine gemeinsame Lösung. Jede Seite zeigt Erfolg/Fehler unterschiedlich (inline Text, Alert-Box, gar nichts).
**Was ich brauche:** Toast-Design mit 3 Tones: `success` (grün), `error` (rot), `info` (blau). Position: Bottom-Right Desktop, Bottom-Center Mobile. Auto-Dismiss nach 4s.

### 2. DropdownMenu (Kebab-Menü)
**Wo gebraucht:** Trips-Liste (Kebab `⋯`), Trip-Detail (Aktionen). Bereits in Issues #282/#295 als fehlend dokumentiert.
**Aktueller Zustand:** Improvisiert als `$state(showMenu)`-Boolean + absolut-positioniertes `<div>`. Kein einheitliches Verhalten bei Focusout/Escape.
**Was ich brauche:** Popover-Dropdown-Design: Trigger-Button, Listenpunkte mit Icon + Label, Trennlinie, Danger-Item (rot). Schatten: `--g-elev-3`.

### 3. Segmented Control
**Wo gebraucht:** EditWeatherSection — Umschalter „Roh / Indikator" (Issue #08 aus Handoff). Möglicherweise auch für Zeitraum-Auswahl in Compare.
**Aktueller Zustand:** Nicht vorhanden. Native Radio-Buttons oder nichts.
**Was ich brauche:** 2-3 Segmente nebeneinander, aktives Segment hat `--g-ink` Background + weißer Text, inaktiv `--g-surface-2` + `--g-ink-muted`.

### 4. Switch (On/Off Toggle)
**Wo gebraucht:** Subscriptions (Enable/Disable), Account (Kanal aktiv/inaktiv), Alert-Regeln (aktiv/inaktiv).
**Aktueller Zustand:** Natives HTML-Checkbox oder improviserter Toggle ohne Design-Token.
**Was ich brauche:** Pill-förmiger Toggle, 44×24 px, ON: `--g-accent`-Background, OFF: `--g-ink-faint`-Background. Touch-Target ≥ 44×44 px.

### 5. Bottom-Sheet (Mobile Drawer)
**Wo gebraucht:** Trips-Liste Mobile (Card-Aktionen), Compare Mobile (Ort-Auswahl).
**Aktueller Zustand:** Inline implementiert in Trips-Seite, nicht wiederverwendbar.
**Was ich brauche:** Generische Sheet-Komponente: Backdrop, Handle-Bar, Höhe 40–80 % Viewport, Drag-to-Close.

## Warum als Claude-Design-Issue

Diese Komponenten brauchen **visuelle Spezifikation** (Größen, Farben, Animationen, States) bevor ich sie sauber implementiere. Ohne Spec entstehen inkonsistente Eigenbauten auf jeder Seite.
