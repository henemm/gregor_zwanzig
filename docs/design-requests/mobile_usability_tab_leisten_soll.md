# Mobile Usability · Paket 2 — Horizontal scrollbare Tab-Leisten auf Mobile

**Status:** Soll-Entwurf für PO-Abnahme · 2026-09-22 · **Mockup:** `docs/design-requests/mobile-usability-tabs-soll.html`
**Bezug:** Mobile-Usability-Audit (WebKit, iPhone 13, 390×844) · #1231 Slice 6 (Band + Fade-Muster) · AP-006 (keine lokalen Kopien katalogisierter Komponenten) · #585 (offener Badge-Stil)

---

## 1. Ausgangslage

Ist-Belege (lokale Audit-Artifacts, nicht im Repo versioniert):

- `frontend/test-results/mobile-usability/iphone13/trips_ma-alpen-x__stages.png` — Trip-Detail, aktiver Tab „Etappen & Wegpunkte": Band zeigt „Übersicht | Etappen & Wegpunkte 4 | Wet[ter…]" — „Wetter-Metriken" ist abgeschnitten.
- `frontend/test-results/mobile-usability/iphone13/compare_cp-eb6ba0b239d90e37.png` + `compare_cp-eb6ba0b239d90e37__*.png` — Compare-Detail, Übersicht-Tab.
- `frontend/test-results/mobile-usability/iphone13/trips_ma-alpen-x__alarme.png` u. a. für Deep-Link-Fälle.

| Befund | Messung (Audit) | Ursache im Code |
|---|---|---|
| `trip-detail-tab-list` horizontal scrollbar | 874 px Scrollbreite bei 356 px Sicht | 7 Tabs mit langen Labels („Etappen & Wegpunkte", „Wetter-Metriken"), Pill-Padding 0.375rem/0.875rem, kein Wrap (`TripTabs.svelte` Mobil-Muster :360-394) |
| `compare-detail-tab-list` horizontal scrollbar | 654 px bei 358 px Sicht | 6 Tabs, identisches Pattern |
| Aktiver Tab nicht initial sichtbar | Deep-Link `?tab=alarme` landet mit aktivem Tab außerhalb des sichtbaren Band-Ausschnitts | Kein `scrollIntoView` beim Mount/Wechsel in beiden Komponenten |
| CompareTabs ist eine Hand-Kopie | AP-006-Drift-Risiko | `CompareTabs.svelte:726-742` baut die Tab-Leiste als eigene Button-Row (`compare-tabs-bar`), Mobil-CSS 1:1 aus `TripTabs.svelte` kopiert (Kommentar :1244 selbst nennt das Muster) — zwei Dateien, zwei Wahrheiten, kein `<Segmented>`/`<MTab>` |

Was der Audit **nicht** bemängelt: das Band + Fade-Muster selbst (#1231). Es signalisiert Scrollbarkeit, kostet keinen vertikalen Platz und ist seit #1231 Slice 6 etabliert. Das eigentliche Problem ist dreiteilig: (a) der aktive Tab ist per Deep-Link nicht sichtbar, (b) Tippen ist das einzige Orientierungsmittel, (c) zwei Kopien des gleichen Bausteins driften.

## 2. Optionen

### (a) Band bleibt + aktiver Tab sichtbar positionieren + A11y

- Beim Mount und bei jedem Tab-Wechsel: `activeItem.scrollIntoView({ inline: 'start', block: 'nearest' })` (mit `scroll-padding-inline: 12px` bereits vorhanden → aktiver Tab landet mit 12 px Rand am Anfang des sichtbaren Bereichs).
- Semantik: `role="tablist"` / `role="tab"` / `aria-selected` / roving `tabindex` (aktiver Tab `tabindex="0"`, Rest `-1`), Pfeiltasten ←/→ wechseln den Tab (WAI-ARIA Tabs). Heute: weder Rollen noch Tastatur.
- Fade-Maske, Scroll-Snap und Pill-Optik bleiben.
- Aufwand: klein, kein Layout-Wechsel, Desktop unberührt.

### (b) 2-zeiliger Wrap

- Tabs umbrechen lassen (`flex-wrap: wrap`), keine Scrollbarkeit mehr.
- Gegen: frisst auf 390 px bei 7 langen Labels zuverlässig 2 Zeilen (~88–96 px vertikal, das ist fast ein Hero); Zeilen ungleich lang („Etappen & Wegpunkte" + „Wetter-Metriken" dominieren Zeile 1); bricht die etablierte Band-Metapher und damit die Parität zu den JSX-Sollbildern (#1231, screen-compare-detail-mobile.jsx); vertikaler Platz ist auf Mobile das knappste Gut (siehe Paket 1).

### (c) Primär-Tabs sichtbar + Rest unter „Mehr"

- 3–4 Tabs sichtbar, Rest hinter Kebab-Menü.
- Gegen: Tabs sind **Navigation, keine Aktionen** — AP-004/005 verstecken *Aktionen* im Kebab, nicht Navigations-Ziele. Ein versteckter „Versand"-Tab ist nicht entdeckbar und bricht das „ein Tab = ein Aspekt"-Modell beider Detailseiten. Zusätzlich bräuchte es eine Primär-Definition pro Kontext (woher?).

## 3. Empfehlung: Option (a)

**Option (a), umgesetzt als EIN geteilter Katalog-Baustein**, der die Mobil-Regeln (Band, Fade, scrollIntoView, A11y) zentral trägt:

1. **`<Segmented>`/`<MTab>`-Angleichung (AP-006):** TripTabs und CompareTabs rendern denselben Baustein statt zweier Hand-Kopien. Konkret: ein `MTabBar`-Baustein (Katalog-Erweiterung nötig, §11-Prozess — Props analog `<MTab>`: `items`, `active`, `onChange`, `scrollable`), implementiert auf Basis des vorhandenen `<Segmented>`-Atoms. `TripTabs.svelte` nutzt ihn bereits implizit (es rendert `<Segmented>`), die Mobil-Overrides wandern von der Komponenten-`:global()`-CSS in den Baustein; `CompareTabs.svelte` ersetzt `compare-tabs-bar` durch denselben Import. Desktop-Underline-Optik (Trip) vs. Desktop-Button-Optik (Compare) bleiben als Varianten-Prop erhalten — geteilt ist nur der Scroll-/A11y-/Positionierungs-Kern.
2. **Aktiver Tab immer sichtbar:** `scrollIntoView({ inline: 'start' })` beim Mount (Deep-Link) und synchron zum State-Wechsel. Das ist der konkrete Audit-Befund „nicht initial sichtbar" und kostet 5 Zeilen.
3. **A11y-Nachrüstung:** `role="tablist"`/`tab`, `aria-selected`, roving Tabindex, ←/→-Tastatur. Heute sind beide Leisten für Screenreader und Tastatur schlecht erschlossen; bei einem Band, das man sonst nur durch Wischen erforscht, ist Tastatur die einzige Alternative.
4. **Touch-Ziele:** Pill-Trigger auf Mobile `min-height: 44 px` (heute 0.375rem/0.875rem-Padding ≈ 31 px Höhe — unter dem Charter-Minimum §7).

Nicht empfohlen: (b) und (c), Begründung §2. Falls PO (c) will, ist das eine IA-Entscheidung (Primär-Tab-Definition), kein Usability-Fix — eigener Request.

## 4. Konkrete Token- und Abstands-Angaben

| Element | Ist | Soll |
|---|---|---|
| Pill-Trigger Padding (Mobil) | `0.375rem 0.875rem` (≈31 px hoch) | `min-height: 44px`, Padding `var(--g-s-2) var(--g-s-3)` (8/12), Label `--g-text-sm` (13) |
| Aktiver Pill | Accent-Fill, Paper-Text | unverändert; **Badge** im aktiven Pill: Paper/Accent-Kontrast prüfen (s. F2) |
| Badge inaktiv | Accent-Fill 12px, White | neutral: `--g-paper-deep`-Hintergrund, `--g-ink-3`-Text, mono `--g-text-xs` (11 px) — Vorschlag, offen aus #585 |
| Fade-Maske | 16 px linear | unverändert (`mask-image` wie #1231) |
| Scroll-Padding | `scroll-padding-inline: 12px` | unverändert; `scrollIntoView` nutzt es implizit |
| Band-Höhe inkl. Trigger | variabel ~40 px | 44 px + 1 px Unterstrich-Reserve = 45 px; kein Layout-Sprung Desktop |
| Fokus-Ring | Browser-Default | sichtbarer Ring (`--g-accent`, 2 px, Offset 2) für Tastatur-Nutzung |

Keine neuen Tokens nötig; alles aus `--g-s-*`, `--g-text-*`, `--g-r-pill`, bestehenden Accent/Surface-Tokens.

## 5. Betroffene Komponenten (Katalog-Bezug)

| Komponente | Änderung | Katalog |
|---|---|---|
| **`MTabBar`** (neu bzw. gehoben) | Geteilter scrollbarer Tab-Baustein: Band + Fade + `scrollIntoView` + WAI-ARIA-Tabs + 44-px-Trigger; konsumiert `<Segmented>` | Erweiterung §7 (Mobile-Shell) — `<MTab>` existiert dort bereits als Bar-Konzept, wird konkretisiert |
| `TripTabs.svelte` | Mobil-`:global()`-CSS (Band/Fade/Pill) in `MTabBar` verschieben; eigene Regeln nur noch Desktop-Underline | §9, nutzt dann `<MTabBar>` |
| `CompareTabs.svelte` | `compare-tabs-bar`-Hand-Markup + kopiertes Mobil-CSS ersetzt durch `<MTabBar>` (AP-006-Fund geschlossen) | §9 |
| `Segmented.svelte` (Atom) | optional: `minHeight`-/A11y-Props, falls der Kern dort statt in `MTabBar` landet | §4 Forms |

## 6. Abnahmekriterien (Vorschlag)

- [ ] Deep-Link `?tab=alarme` (Trip) und `?tab=vorschau` (Compare) auf 390 px: aktiver Tab ist beim Laden ohne User-Geste vollständig sichtbar, mit 12 px Abstand zum linken Band-Rand.
- [ ] Tab-Wechsel per Tap und per ←/→ positioniert den neuen Aktiven gleich.
- [ ] Screenreader: Leiste als `tablist` mit `aria-selected`, aktiver Tab fokussierbar.
- [ ] Alle Trigger ≥ 44 px Höhe, sichtbarer Fokus-Ring.
- [ ] Kein horizontales Scrollen erforderlich, um irgendeinen Tab zu *sehen* (Band darf weiter scrollen; der Punkt ist, dass der aktive nie verdeckt ist).
- [ ] TripTabs und CompareTabs importieren denselben Baustein (AP-006); kein dupliziertes Mobil-CSS mehr.

## 7. Offene Fragen an PO

- **F1:** Tab-Reihenfolge bzw. Tab-Anzahl ändern wir nicht in diesem Paket — korrekt? (7 Trip-Tabs passen nie ohne Scroll auf 356 px; Wrap/„Mehr" war verworfen.)
- **F2:** Badge-Stil (offen aus #585): Vorschlag neutral statt Accent-Fill — Zustimmung? Betrifft nur inaktive Pill-Badges; der aktive Pill-Text bleibt Paper auf Accent.
- **F3:** Soll der Tab-Wechsel den vertikalen Scroll-Reset der Seite behalten (heute `noScroll`) — ja, unverändert? (Kein Audit-Befund, nur Absicherung.)
