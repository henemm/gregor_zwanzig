# Gregor Zwanzig · Mobile-Erweiterung v1

Mobile-Varianten (Primärziel 375 px, sekundär 414 / 768) für alle Hauptscreens des
Gregor-Zwanzig-Webapps. **Reine Erweiterung** des bestehenden Desktop-Designs —
keine neuen Patterns, keine neuen Tokens.

## Was hier drin ist

```
gregor-zwanzig-mobile/
├── README.md                       ← du bist hier
└── project/
    ├── tokens.css                  ← unverändert aus Desktop
    ├── mobile-shell.jsx            ← Primitives (TopBar, BottomNav, Drawer, Sheet, Toast, Inputs)
    ├── mobile-patterns.md          ← Mapping Mobile↔Desktop, Breakpoints, Entscheidungen
    │
    ├── screen-login-mobile.jsx           NEU (Desktop hatte noch keinen Login-Screen)
    ├── screen-design-system-mobile.jsx   Mobile-Token-Übersicht
    │
    ├── screen-home-mobile.jsx            ↔ screen-home
    ├── screen-trips-mobile.jsx           ↔ screen-trips
    ├── screen-trip-detail-mobile.jsx     ↔ screen-trip-detail
    ├── screen-trip-wizard-mobile.jsx     ↔ screen-trip-wizard (alle 4 Schritte)
    ├── screen-waypoint-editor-mobile.jsx ↔ screen-waypoint-editor
    ├── screen-metrics-editor-mobile.jsx  ↔ screen-metrics-editor
    ├── screen-alert-config-mobile.jsx    ↔ screen-alert-config
    ├── screen-compare-mobile.jsx         ↔ screen-compare
    ├── screen-location-new-mobile.jsx    ↔ screen-location-new
    ├── screen-output-preview-mobile.jsx  ↔ screen-output-preview (Email · SMS · Signal)
    │
    └── screen-patterns-mobile.jsx        App-Shell · Modal · Sheet · Toasts · States
```

Designs zu sehen im Repo-Root unter **`Gregor 20 - Mobile v1.html`** (alle Screens auf einem Design-Canvas).

## Regeln, die eingehalten wurden

1. **tokens.css ist die einzige Quelle** für Farben, Typo, Spacing, Radien.
   Keine Datei verändert tokens.css, keine Datei definiert eigene Hex-Werte.
2. **Komponenten-Namen identisch** zu bestehenden Atoms (`Card`, `Pill`, `Eyebrow`,
   `Btn`, `ElevSparkline`, `WIcon`, `Dot`). Mobile-Spezifika sind als `M*`-Suffix
   hinzugekommen (`MBtn`, `MInput`, `MField`, `MSwitch`, `MTab`, `MIcon`),
   damit Desktop-Atoms vom Mobile-Set klar trennbar bleiben.
3. **Touch-Targets ≥ 44 × 44 px** — `MBtn` Default `size="lg"` (48 px), `size="xl"`
   für 56-px-Fokus-CTAs. Switches 44 px Hit-Area. Bottom-Nav-Items 64 px hoch.
4. **Body-Schrift in Inputs ≥ 16 px** — fest in `MInput` verdrahtet
   (verhindert iOS-Auto-Zoom beim Focus).
5. **Safe-Areas** — `env(safe-area-inset-bottom)` in jeder Sticky-Bottom-Bar,
   `safeTop` 44 px in der Status-Bar-Region.
6. **Spacing-Skala konsistent** — Mobile verwendet `--g-s-3` (12 px) für Gaps,
   `--g-s-4` (16 px) für Außenrand statt 40 px Desktop, Card-Innenrand 16 px statt
   20/24 px. Skala selbst unverändert.
7. **Keine neue visuelle Sprache** — gleiche Farb-Logik (Accent burnt-orange, semantische
   Farben für Risk/Status), gleiche Schriften (Inter Tight + JetBrains Mono),
   gleiche Card-Anatomie (3-px-Accent-Left-Border für aktive Items),
   gleiche Eyebrow/Mono-Behandlung.

## Wie das in die SvelteKit-App übersetzt wird

Die JSX-Dateien sind **Spec-Layer**, nicht Produktion. Workflow für Übersetzung:

1. **Pattern-Komponenten** aus `mobile-shell.jsx` als Svelte-Komponenten anlegen:
   `TopAppBar.svelte`, `BottomNav.svelte`, `Drawer.svelte`, `BottomSheet.svelte`,
   `Toast.svelte`, `MInput.svelte`, `MBtn.svelte`, `MField.svelte`, `MSwitch.svelte`,
   `MTab.svelte`. Tokens via CSS-Variablen aus `app.css`.
2. **Breakpoint-Logik** in `app.css`:
   ```css
   /* Mobile-first */
   .gz-screen-padding { padding: var(--g-s-4); }       /* 16px */
   @media (min-width: 900px) {                          /* Desktop */
     .gz-screen-padding { padding: var(--g-s-10); }    /* 40px */
   }
   ```
3. **Routes** spiegeln die Mobile-Screens 1:1 — gleiche URLs, andere Layouts.
   Mobile-Layout aktiv bei `viewport ≤ 899 px`, Desktop sonst. Wizard und
   Location-New laufen auf Mobile als **Vollbild-Route** ohne BottomNav.
4. **Sheet vs. Modal Convention** — siehe `mobile-patterns.md` §F. Verwende
   `BottomSheet` für kontextuelle Aktionen / Multi-Select / Quick-Edit,
   `Modal` (Vollbild-Route) für lineare Flows und destruktive Bestätigung.

## Touch-Test

Vor dem Merge bitte auf echtem Gerät prüfen:

- iPhone SE (375 × 667) — engster Primärfall
- iPhone 14 / 15 (390 × 844) — Standard
- iPhone 14 Plus (430 × 932) — sekundär 414+
- iPad mini (768 × 1024) — Tablet-Breakpoint
- Android Pixel 7 (412 × 915) — Material-Verhalten der Sheets

Insbesondere checken:
- Hat die Bottom-Nav auf Geräten mit Home-Indikator den richtigen Safe-Area-Abstand?
- Lässt sich die Compare-Matrix horizontal scrollen ohne den vertikalen Scroll zu hijacken? `overscroll-behavior: contain` setzen.
- Sheet-Snap-Drag funktioniert auf Touch, Backdrop-Tap schließt sicher.
- Bei Focus auf Input nicht zoomen (iOS) — Test mit `font-size: 16px`.

## Offene Punkte zur Klärung mit Design

*(Stand v1: alle ursprünglichen Open-Items adressiert.)*

- **Etappen-Switcher im Wegpunkt-Editor** → ersetzt durch Dropdown-Trigger + Sheet (`StageSelectSheet`); skaliert auch bei 13+ Etappen, zeigt Risiko + Distanz + WP-Count pro Etappe.
- **Wizard-Abbruch** → Sheet-Pattern `PatternWizardCancel` mit 3 Optionen *Entwurf speichern / Weiter editieren / Verwerfen*. Verbindlich für alle mehrstufigen Flows wenn User schon Daten eingegeben hat. Siehe `mobile-patterns.md` §F.
- **Push-Permission** → eigener Pre-Prompt-Screen `PatternPushPermission`. Erscheint einmalig nach erster Alert-Konfig. Tappt User „Aktivieren" → erst dann triggern wir den nativen Permission-Dialog. Schutz davor, die Single-Shot-Permission auf iOS/Android zu verbrennen.
- Push-Settings müssen in Settings auch nachträglich änderbar sein, mit Deep-Link in die OS-Settings, falls der User initial „Nein" gewählt hat.

## Kontakt

Pattern-Entscheidungen + Begründungen siehe `mobile-patterns.md` im selben Ordner.
