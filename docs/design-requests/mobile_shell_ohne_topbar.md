# Mobile-Shell: schwebende Tabbar, kein fixer Balken oben

**Status:** PO-Entscheide vom 2026-09-19 eingearbeitet (§8) · **Soll-Bild:** Design-Canvas „Gregor Mobile Shell" (claude.ai, Artboards *Übersicht*, *Unterseite*, *Konto-Sheet*, *TabBar*) · **Scheiben S1 (Tabbar), S2 (Konto-Kreis + Sheet + Balken weg) und S3 (Charter/Katalog) sind umgesetzt** (PR #2364). §1 beschreibt den Stand davor.

## 1. Ausgangslage

Die mobile Shell besteht heute aus zwei fixen Balken (`frontend/src/routes/+layout.svelte`):

| Element | Datei | Funktion heute |
|---|---|---|
| **TopAppBar** (56 px, `z-60`) | `ui/sidebar/TopAppBar.svelte` | Hamburger → Drawer · Wordmark (oder Seitentitel aus `topAppBarStore`) · Glocke (**deaktivierter Platzhalter, keine Funktion**) · Plus → `/trips/new` · optional `leftIcon: back` + Rechts-Slot |
| **Drawer** | `ui/sidebar/Sidebar.svelte` (mobiler Teil) | Wordmark · die 4 Workspace-Links (doppelt zur Tabbar) · Konto · System-Status · Dark-Mode · Abmelden |
| **BottomNav** (64 px, `z-50`) | `ui/sidebar/BottomNav.svelte` | 4 Ziele Übersicht / Trips / Vergleich / Archiv |

Den `topAppBarStore` füllen nur zwei Seiten: die Vergleichs-Liste (Titel + „Neuer Vergleich") und `CompareNewEditor` (Back + „Aktivieren"). Alle anderen Seiten zeigen im Balken nur die Wordmark. Der Balken kostet also 56 px auf jedem Screen und trägt fast nirgends Inhalt — und die Übersicht wiederholt seine Primäraktion (`+`) bereits im Page-Header („Neuer Trip" / „Neuer Vergleich").

## 2. Zielbild

1. **Kein fixer Balken oben.** Der Inhalt beginnt unter der Statusleiste (`env(safe-area-inset-top)`), die Papierfläche läuft bis an den Bildschirmrand.
2. **Schwebende Glas-Tabbar** (iOS-27-Stil): 16 px Rand, 6 px über der Home-Indicator-Zone, Kapsel mit Blur (86 % Deckung — Lesbarkeit vor Glas), vier gleich breite Ziele, Aktiv-Kapsel in Akzent-Tint. *(umgesetzt, S1)*
3. **Konto-Kreis** rechts neben der Tabbar (User-Badge mit Initialen). Tippen öffnet das **Konto-Sheet** von unten.
4. **Rücksprung im Inhalt**: Unterseiten zeigen oberhalb des `<PageHeader>` einen Rücksprung-Link (Mono-Caps, 36 px Touch-Ziel). Browser-Back und iOS-Swipe-Back funktionieren wie bisher.

## 2a. Leitplanken (PO, 2026-09-19)

1. **Die PWA auf iPhone/iPad dient vor allem dem schnellen Zugriff auf bestehende Trips und Orts-Vergleiche.** Folge für die Übersicht ohne Balken: Die erste Bildschirmhöhe gehört den bestehenden Objekten (laufender Trip, nächste Briefings, offene Entwürfe als Kachel-Grid); „Neuer Trip / Neuer Vergleich" bleiben Sekundäraktionen im Page-Header, nie ein eigener Block oben. Anlegen und Editieren sind Desktop-Fälle.
2. **Lesbarkeit und Erreichbarkeit bei schwierigem Licht haben Prio 1.** Deshalb ist das Glas mit 86 % Deckung bewusst weniger transparent als Apples Vorbild, inaktive Ziele stehen in `--g-ink-2` (8:1 auf Papier) statt in Grau, das aktive Ziel trägt Kapsel **und** Akzent-Icon **und** fettes Label (nie nur Farbe), und die Leiste sitzt so tief wie die Home-Indicator-Zone erlaubt (`--g-nav-gap` 6 px) — Daumenreichweite. Bei `prefers-reduced-transparency` wird die Leiste opak.
3. **Mockups zeigen keine Statusleiste und keinen Home-Indicator.** Auf dem Gerät kommen oben `env(safe-area-inset-top)` (≈ 54 px) und unten `env(safe-area-inset-bottom)` (34 px) dazu; die Artboards beginnen deshalb bewusst dicht am Rand.

## 3. Was ersetzt was

| Heute im Balken | Neu | Begründung |
|---|---|---|
| Wordmark | Erste Zeile der **Übersicht** (nur dort), rechts daneben das Datum als Mono-Caption | Marke einmal pro Sitzung, nicht auf jedem Screen |
| Seitentitel / Eyebrow (Store) | `<PageHeader>` der Seite — den gibt es schon | Store und Doppelpflege entfallen (AP-011: Page-Header nur via `<PageHeader>`) |
| Hamburger → Drawer | **Konto-Kreis** → **Konto-Sheet**: Kanäle & Empfänger · Konto/Einstellungen · System-Status · Dunkles Design · Datenexport · Abmelden | Charter §2: Konto **nur** über User-Badge. Der Drawer duplizierte die Tabbar (E2E `mobile-bottom-nav` AC-4 verlangt das ohnehin nicht) |
| Glocke (disabled) | entfällt ersatzlos | Heute ohne Funktion. Sobald #1701-Alarme einen Posteingang bekommen, ist der Konto-Kreis (Punkt) + eine Sheet-Zeile der vorgesehene Ort |
| Plus → `/trips/new` | entfällt; Primäraktion steht im Page-Header | AP-004 (genau eine Primäraktion), AP-012 (kein zweiter Einstieg) |
| „Neuer Vergleich" (Compare-Liste, Rechts-Slot) | Rechts-Slot des `<PageHeader>` | dasselbe Muster wie Übersicht |
| „Aktivieren" (`CompareNewEditor`) | Sticky-Footer des Editors (wie Trip-Editor: geteilter Baustein, `context="vergleich"`) | Trip/Vergleich-Code-Teilung |
| `leftIcon: back` | `<PageHeader back={{ href, label }}>` — Rücksprung-Link über dem Eyebrow | ein Baustein statt Store-Magie |
| Offline-Band `#gz-stand` (heute per `body`-Padding unter den Balken geschoben) | Erste Zeile im Inhalt, unter der Safe-Area | die `app.css`-Sonderregel (#2131) entfällt |

**Nicht Teil des Konzepts:** ein einklappender Großtitel beim Scrollen (iOS Large Title). Kann später kommen, ändert nichts an der Struktur.

## 4. Ist der Konto-Kreis ein FAB?

Nein, aber die Charter muss das sagen. AP-012 verbietet den **Primäraktions**-FAB (Akzent-Kreis unten rechts, der eine Screen-Aktion aus dem Header löst). Der Konto-Kreis ist Navigation, nicht Aktion: neutral (Glas wie die Leiste, kein Akzent-Fill außer dem Avatar-Badge selbst), Teil der Tabbar-Gruppe, auf jedem Screen gleich. Vorschlag für Charter §2: *„Mobile Nav: schwebende Bottom-Nav mit denselben 4 Bereichen plus User-Badge als Konto-Kreis. Konto-Sheet enthält Konto + Benachrichtigungen + Logout. Kein Top-Balken."* und AP-012 um den Satz *„Der Konto-Kreis der Mobile-Nav ist kein FAB"* ergänzen.

## 5. Safe-Area oben

Heute konsumiert nichts `env(safe-area-inset-top)` — der 56-px-Balken hat das verdeckt. Ohne Balken:

- `main.mobile-scroll-pad`: `padding-top: calc(env(safe-area-inset-top) + var(--g-s-3))` statt `56px`.
- `app.html`: `apple-mobile-web-app-status-bar-style` bleibt `default` (PO-Entscheid): iOS zeichnet die Statusleiste selbst in `theme-color` `#f6f4ee` mit dunkler Schrift, die Seite beginnt direkt darunter. Kein Papier unter der Statusleiste, kein heller Statusleisten-Text.
- Sheet/Editor-Konstanten, die 56 px annehmen: `EditStagesPanelNew.svelte` (`TOP_APP_BAR_PX`), `mobile/Sheet.svelte` (`56px` collapsed), `ProfileSheetEmbedded.svelte` (`100dvh - 56px`), `compare/[id]/+page.svelte:406` (handgebaute Leiste „analog TopAppBar").

## 6. Betroffene Tests

| Test | Änderung |
|---|---|
| `e2e/mobile-bottom-nav.spec.ts` AC-1 (`top-app-bar` sichtbar), AC-4 (Hamburger → Drawer) | umschreiben auf Konto-Kreis → Konto-Sheet |
| `e2e/issue-293-wordmark.spec.ts` AC-2 (Wordmark im Balken) | Wordmark auf `/` im Inhalt |
| `e2e/compare-editor-fidelity-s8d.spec.ts` (`top-app-bar-title`, `top-app-bar-new-compare`) | auf `<PageHeader>`-TestIDs |
| `src/lib/issue_481_mobile_header_icons.test.ts` | löschen (prüft die Glocke im Balken) |
| `src/routes/compare/__tests__/compare_list_mobile_chrome.test.ts` | löschen/umschreiben (Store-Fill) |
| `src/lib/components/mobile/mobile.test.ts` | Barrel ohne `TopAppBar`; `MobileShell` (nur Showcase) ohne TopBar |
| `e2e/bug-274-safe-area-insets.spec.ts` | Kopfkommentar: neue Safe-Area-Stellen (oben) |
| `e2e/mobile-bottom-nav-floating.spec.ts` | **neu (S1)**: Geometrie + Glas der Tabbar |

## 7. Umsetzung in Scheiben

| Scheibe | Inhalt | LoC (grob) |
|---|---|---|
| **S1 — Tabbar** *(erledigt)* | `BottomNav.svelte` schwebend/Glas, `--g-nav-*` Tokens, `.mobile-scroll-pad`, Toast-/SaveIndicator-Anker auf `--g-nav-clearance`, `EditStagesPanelNew` 64→70, Doku, E2E | ~150 |
| **S2 — Konto-Kreis + Sheet + Balken weg** *(erledigt)* | Konto-Kreis neben der Tabbar, `KontoSheet` aus `mobile/Sheet.svelte` (Konto · System-Status · Dunkles Design · Datenexport · Abmelden — keine Benachrichtigungen-Zeile), Drawer + `TopAppBar` + `topAppBarStore` löschen, Wordmark + Datum in die Übersicht, `<PageHeader back>` in `CompareNewEditor`/Compare-Liste, Safe-Area oben, `#gz-stand`-Sonderregel raus, 56-px-Konstanten, Tests aus §6 | ~400 (→ `loc_limit_override 500`) |
| **S3 — Charter/Katalog** *(erledigt, mit S2)* | CHARTER §2, AP-012-Ergänzung, COMPONENTS.md (`TopAppBar`/`Drawer` raus, `BottomNav` + `KontoSheet` neu), `SCREENS.json` | Doku |

S2 ist bewusst ein Zug: Konto-Kreis und Balken-Abbau hängen am selben Layout, ein Zwischenstand mit beidem wäre doppelte Navigation.

## 8. PO-Entscheidungen (2026-09-19)

| Frage | Entscheidung |
|---|---|
| Konto-Kreis neben der Tabbar oder fünftes Ziel? | **Neben der Tabbar.** Charter §2 bleibt bei genau vier Bereichen. |
| Benachrichtigungen im Konto-Sheet? | **Weglassen.** Kein Platzhalter, bis ein echter Posteingang existiert (#1701). |
| Statusleiste (Systemzeile mit Uhrzeit, Empfang, Akku) | **Standard behalten.** Seite beginnt direkt unter der Statusleiste; kein Papier darunter, keine helle Systemschrift. |
| Dunkles Design | **Ins Konto-Sheet** (ein Tipp weniger als über die Konto-Seite). |
| Reihenfolge | **Konto-Kreis, Sheet und Balken-Abbau in einem Zug** (Scheibe S2). |
