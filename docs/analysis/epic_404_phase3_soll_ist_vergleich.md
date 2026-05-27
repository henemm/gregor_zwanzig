# SOLL-IST-Vergleich — Epic #404 Phase 3
## Abschlussbericht

**Datum:** 2026-05-27  
**Grundlage:** 50 SOLL-Screenshots (Design-Handoff), 26 IST-Screenshots (Playwright/Staging, Commit 61575c8)  
**Methode:** Bottom-Up Atomic (Atoms → Molecules → Desktop-Screens → Mobile-Screens)  
**Vergleichs-Agents:** 5 unabhängige fresh-eyes-inspector Agenten

---

## Gesamtbild

| Ebene | BLOCKER | MEDIUM | LOW |
|-------|---------|--------|-----|
| Atoms + Molecules | 0 | 4 | 5 |
| Desktop (15 Screens) | 16 | 29 | 19 |
| Mobile (11 Screens) | 29 | 18 | 11 |
| **Gesamt roh** | **~45** | **~51** | **~35** |
| Nach Deduplizierung (Desktop+Mobile = 1 Issue) | **~18** | **~22** | **~15** |

**Screens ohne echtes Delta:** 1 (Compare: ausschließlich Datenzustand)

---

## Ebene 1 — Atoms

### Btn
- **SOLL:** `variant: primary | accent | ghost | quiet`
- **IST:** Zusätzliche Varianten `outline | secondary | destructive | link` — additive Erweiterung
- **Schwere:** LOW — kein Katalogbruch, nur Überschuss

### Eyebrow ⚠️
- **SOLL:** Default-Farbe `--g-ink-3`
- **IST:** Default-Farbe `--g-ink-faint` (2,85:1 Kontrast auf Weiß)
- **Delta:** WCAG-AA-Risiko bei 10px-Text (Grenze: 4,5:1)
- **Schwere:** MEDIUM
- **Code:** `frontend/src/lib/components/ui/eyebrow/Eyebrow.svelte:8`

### Pill
- **Delta:** ✓ Kein Delta

### Dot
- **SOLL:** `size` default = numerisch 8px; **IST:** `size` default = Token `sm`
- **Schwere:** LOW — funktional äquivalent, kein visuelles Delta

### KV
- **SOLL:** `value` als Snippet (Rich Content); **IST:** `value` nur `string | number`
- **Schwere:** LOW — Legacy-Komponente, bevorzugt DetailRow

### Card ⚠️
- **SOLL:** `padding: number` + `accent: boolean` steuerbar
- **IST:** Props existieren, aber `ui/card/card.svelte` kennt sie nicht → werden stillschweigend ignoriert
- **Schwere:** MEDIUM — Katalog-API-Vertrag gebrochen; Aufrufer mit `<Card padding={16}>` erhalten keine Wirkung
- **Code:** `frontend/src/lib/components/ui/card/card.svelte:9`

### Input
- **SOLL:** `mono: boolean` Prop; **IST:** fehlt
- **Schwere:** LOW — Workaround via `class`

### Switch
- **Delta:** ✓ Kein Delta (Zusatz-Props `tone` + `lg` sind additive Erweiterungen)

### Segmented ⚠️
- **SOLL-API:** `items[]` / `value` / `onChange` / `size: sm|md`
- **IST-API:** `options[]` / `selected` / `onselect` / kein `size`
- **Delta:** Alle öffentlichen Prop-Namen inkompatibel mit COMPONENTS.md; `size`-Prop komplett fehlend
- **Schwere:** MEDIUM — Neue Aufrufer, die sich auf den Katalog verlassen, übergeben falsche Props; keine Größenvarianten möglich
- **Code:** `frontend/src/lib/components/ui/segmented/Segmented.svelte:2`

### ElevSparkline
- **Delta:** ✓ Kein Delta

### WIcon
- **Delta:** ✓ Kein Delta

---

## Ebene 2 — Molecules

### Field
- **Delta:** ✓ Kein Delta

### Stat
- **Delta:** ✓ Kein Delta

### StagePill
- **Delta:** ✓ Kein Delta

### DetailRow
- **Delta:** ✓ Kein Delta

### ThresholdRow
- **Delta:** ✓ Kein Delta

### AlertRow ⚠️
- **SOLL:** Icon-Art passt zum Alert-Typ (Regen → Regen-Icon, Wind → Wind-Icon, etc.)
- **IST:** `iconKind`-Mapping ist unvollständig — nur `thunder` → Thunder-Icon, **alle anderen** Alert-Typen → Wind-Icon
- **Schwere:** MEDIUM — Nutzer sieht Wind-Icon bei Niederschlag-Alert
- **Code:** `frontend/src/lib/components/molecules/AlertRow.svelte:55`

### ChannelChip
- **SOLL:** SVG-Icons als Kanal-Glyphen
- **IST:** Unicode-Zeichen (✉ ▲ ✈ ✱) — `▲` für Signal semantisch schwach
- **Schwere:** LOW — technisch kein Emoji-Verstoß, aber `▲` (Dreieck) für Signal-Kanal ist unscharf

### ChannelRow
- **Delta:** ✓ Kein Delta

### BriefingScheduleRow
- **Delta:** ✓ Kein Delta

### BriefingTimelineRow
- **Delta:** ✓ Kein Delta

---

## Ebene 3 — Desktop-Screens

### Home / Startseite
| Finding | Schwere |
|---------|---------|
| Personalisiertes Greeting "Guten Morgen, Gregor" fehlt; IST: generischer Titel "Deine Trips & Vergleiche" | MEDIUM |
| Breadcrumb-Eyebrow im IST vorhanden, im SOLL nicht (IST-Konsistenz ok) | LOW |
| Wetterdaten im Trip-Hero fehlen (SOLL: eingebettet; IST: kein Live-Wetter per Design-Entscheidung) | ⚠️ OFFEN |

> **Hinweis Home-Wetter:** Design-Entscheidung "kein blockierender SSR-Wetter-Fetch" schließt Demo-Daten nicht aus. Klärung ob SOLL-Greeting + Demo-Wetter implementiert werden soll → PO-Frage, kein technischer Bug.

### Trips-Liste
| Finding | Schwere |
|---------|---------|
| H1 "Meine Trips" statt "Trips" | MEDIUM |
| Status-Kategorien: IST hat Pausiert/Archiviert statt Abgeschlossen/Drafts | BLOCKER |
| Status-Zähler: SOLL große orange Zahlen ohne Punkte; IST kleine Zahlen mit farbigen Status-Punkten | MEDIUM |
| Etappen-Spalte fehlt (IST: Unterzeile statt eigene Spalte) | MEDIUM |
| Aktions-Spalte: SOLL 6 Icon-Buttons; IST 1 "Briefing-Vorschau"-Button + Kebab | BLOCKER |
| Footer-Typografie: "2 VON 2 TRIPS" in Monospace-Caps statt Fließtext | MEDIUM |
| Sidebar-Nutzer: zeigt "D · default" statt "Gregor Henemm · henemm.com" | MEDIUM |

### Trip-Detail
| Finding | Schwere |
|---------|---------|
| Übersicht-Tab: SOLL = Höhenprofil + Etappen-Liste + Sidebar. IST = 2×2 Card-Grid | BLOCKER |
| Höhenprofil fehlt vollständig im Übersicht-Tab | BLOCKER |
| Rechte Sidebar mit Briefing-Zeiten/Alert-Vorschau fehlt | MEDIUM |
| Tab-Beschriftungen weichen ab; "Matches"-Tab fehlt | MEDIUM |
| Trip-Metadaten reduziert (weniger Eyebrow-Zeilen) | MEDIUM |
| Status-Badge "Aktiv" outlined orange statt gefüllt | LOW |

### Metriken (Wetter-Briefing-Tab)
| Finding | Schwere |
|---------|---------|
| "Pro Kanal"-Tabelle (Email/Telegram/Signal/SMS) möglicherweise fehlend oder nur per Scroll erreichbar | MEDIUM |
| "NUR ROHWERT"-Anzeige: 3 Metriken ohne Toggle (intentional wenn keine Skala vorhanden?) | MEDIUM |

### Alerts
| Finding | Schwere |
|---------|---------|
| Toggle-Switches: SOLL farbige iOS-Toggles; IST Text-Buttons "Aus" / "Δ Aus" | MEDIUM |
| Beispiel-Alert-Block (vollständig gerendert mit Inhalt) möglicherweise vorhanden aber nicht im Screenshot | MEDIUM |

### E-Mail-Vorschau
| Finding | Schwere |
|---------|---------|
| Fehlermeldung "HTTP 422 — Stage must have at least one waypoint" englisch/roh im UI | MEDIUM |
| E-Mail + SMS auf gleichem Tab (SOLL: getrennte Screens) — vermutlich intentionell | LOW |

### SMS-Vorschau
| Finding | Schwere |
|---------|---------|
| Gleicher Tab wie E-Mail (s.o.) | LOW |
| Legende: IST "Spec-Format SMS" statt SOLL-Legende; andere Terminologie | LOW |

### Wegpunkt-Editor ⛔
| Finding | Schwere |
|---------|---------|
| **Falscher Screen-Typ**: SOLL = dedizierter Editor mit Karte + Höhenprofil + WP-Sidebar. IST = generische Trip-Bearbeitungs-Maske mit Akkordeon | BLOCKER |
| Höhenprofil fehlt vollständig | BLOCKER |
| Wegpunkt-Sidebar (nummeriert, Edit/Delete) fehlt | BLOCKER |
| Etappen-Strip: SOLL Karten-Thumbnails; IST simple Kacheln ohne Thumbnails | MEDIUM |

### Wegpunkt-Wizard Step 1
| Finding | Schwere |
|---------|---------|
| Screen-Inhalt falsch: SOLL = Profil & Eckdaten; IST = Route (GPX-Upload in Step 1 statt Step 2) | BLOCKER |
| Aktivitätsprofil-Auswahl (5 Kacheln) fehlt | BLOCKER |
| Kürzel-Feld fehlt | BLOCKER |
| Eyebrow: "NEUER TRIP ·" Präfix fehlt | MEDIUM |
| Stepper-Labels weichen ab | MEDIUM |

### Trip-Wizard Step 2
| Finding | Schwere |
|---------|---------|
| Etappen-Badge Farbe: SOLL orange; IST blau | MEDIUM |
| Struktur grundsätzlich erkennbar vorhanden | — |

### Trip-Wizard Step 3
| Finding | Schwere |
|---------|---------|
| **Falscher Inhalt**: SOLL = Wegpunkt-Bestätigung; IST = Metriken-Konfiguration | BLOCKER |
| Höhenprofil + Wegpunkt-Bestätigungs-Interface fehlen | BLOCKER |

### Trip-Wizard Step 4
| Finding | Schwere |
|---------|---------|
| Layout-Konzept unterschiedlich (zweispaltig vs. 2×2 Cards) | MEDIUM |
| Kanal-Verwaltungsbereich mit Toggle pro Kanal fehlt | MEDIUM |
| Alert-Schwellen: SOLL konkrete Werte (50 km/h, 10 mm/h); IST "Autark"-Karte ohne Zahlen | MEDIUM |
| "Trip anlegen" vs. "Speichern" — Bezeichnung | LOW |
| Uhrzeit-Format: SOLL 24h (18:00); IST 12h (06:00 PM) | MEDIUM |

### Compare
| Finding | Schwere |
|---------|---------|
| IST ist Leerzustand (keine Orte konfiguriert) — ausschließlich Datenzustand, kein echtes Delta | — |

### Archiv ⛔
| Finding | Schwere |
|---------|---------|
| **Terminologie-Verstoß**: überall "Touren" statt "Trips" (Eyebrow, Tabellentext, Footer, Fehlermeldung) | BLOCKER |
| Suchfeld-Breite zu schmal (~40% statt volle Breite) | MEDIUM |
| Sortier-Tab Beschriftung: Title Case statt ALL CAPS | LOW |

### Location-New ⛔
| Finding | Schwere |
|---------|---------|
| **Falscher Screen-Typ**: SOLL = 3-Schritt-Wizard. IST = einfacher modaler Dialog | BLOCKER |
| Smart-Import (URL-Parsing) fehlt | BLOCKER |
| Minimap-Vorschau (LocationPreviewMap) fehlt | BLOCKER |
| Aktivitätsprofil: SOLL Kacheln; IST Dropdown | MEDIUM |
| Schritt-Indikatoren fehlen | MEDIUM |

---

## Ebene 3 — Mobile-Screens

### Mobile Home
| Finding | Schwere |
|---------|---------|
| Personalisiertes Greeting fehlt | MEDIUM |
| Heutiger Etappen-Block mit Höhenprofil fehlt | BLOCKER |
| "Was geht raus"-Briefing-Liste fehlt | BLOCKER |
| Bottom-Nav Icons: SOLL Haus; IST Raster (4 Quadrate) | LOW |
| Header: SOLL Hamburger + Glocke + Plus; IST Hamburger + Wordmark + Mond-Icon | MEDIUM |

### Mobile Trips-Liste
| Finding | Schwere |
|---------|---------|
| Filter-Pills (Alle/Aktiv/Geplant/Fertig mit Zählern) fehlen | BLOCKER |
| Schnellaktionen-Leiste (aufklappbar: Briefing senden/Vorschau/Alerts) fehlt; IST: nur Kebab | MEDIUM |
| Status-Dot: SOLL orange für aktiv; IST grün | MEDIUM |

### Mobile Trip-Detail
| Finding | Schwere |
|---------|---------|
| Kennzahlen-Kacheln (Etappe X/Y, nächstes Briefing, Start in N Tagen) fehlen | BLOCKER |
| Höhenprofil fehlt im Übersicht-Tab | BLOCKER |
| Dritter Tab abgeschnitten — horizontales Overflow | MEDIUM |
| 3 Aktionsbuttons sehr prominent direkt unter Header; dritter überläuft die Breite | MEDIUM |

### Mobile Alerts
| Finding | Schwere |
|---------|---------|
| Auslöse-Modus-Selektor (Δ-Änderung / Schwellwert / Beides·EMPFOHLEN) fehlt | BLOCKER |
| Kein eigenständiger Screen-Kontext/H1 | BLOCKER |
| Fixierter Footer (Test-Alert + Speichern) fehlt | BLOCKER |

### Mobile Metriken
| Finding | Schwere |
|---------|---------|
| Preset-Navigation: SOLL horizontale Pill-Tabs; IST vertikale Button-Liste | MEDIUM |
| Metriken-Akkordeon fehlt | BLOCKER |
| Toggle-Steuerelemente pro Metrik fehlen | BLOCKER |
| Fixierter Footer (Reset / Übernehmen) fehlt | BLOCKER |

### Mobile Wizard Step 1
| Finding | Schwere |
|---------|---------|
| Kürzel-Feld fehlt | BLOCKER |
| Aktivitätsprofil-Auswahl fehlt | BLOCKER |
| Fortschrittsbalken: SOLL visueller Balken; IST nur Text "1/4 · Route" | MEDIUM |
| Terminologie: "NEUE TOUR" statt "NEUER TRIP" | MEDIUM |
| Enddatum fehlt (IST: nur Startdatum + Hinweis) | MEDIUM |

### Mobile Wizard Step 2
| Finding | Schwere |
|---------|---------|
| Badge-Farbe Etappe: orange (SOLL) vs. blau (IST) | MEDIUM |
| Kursiver Hinweistext nach Footer unstrukturiert | LOW |

### Mobile Wizard Step 3
| Finding | Schwere |
|---------|---------|
| **Falscher Inhalt**: SOLL = Wegpunkt-KI-Vorschläge; IST = Metriken | BLOCKER |
| Schwarze Datums-Buttons überdecken Footer beim Scrollen | BLOCKER |
| Etappen-Strip-Navigation fehlt | BLOCKER |

### Mobile Wizard Step 4
| Finding | Schwere |
|---------|---------|
| Kanal-Toggles mit Kontaktdaten fehlen | BLOCKER |
| Abend-Briefing-Default: SOLL 18:00; IST 06:00 — falscher Wert | BLOCKER |
| Kontaktdaten (E-Mail, Telefon) nicht sichtbar | MEDIUM |

### Mobile Compare
| Finding | Schwere |
|---------|---------|
| Leerzustand — ausschließlich Datenzustand, kein echtes Delta | — |

### Mobile Wegpunkt-Editor ⛔
| Finding | Schwere |
|---------|---------|
| **Falscher Screen-Typ**: SOLL = dedizierter Karten-Editor. IST = generisches Bearbeitungsformular | BLOCKER |
| Topographie-Karte fehlt | BLOCKER |
| Höhenprofil-Panel fehlt | BLOCKER |
| KI-Vorschlag-Interface fehlt | BLOCKER |
| Etappen-Navigator fehlt | BLOCKER |

---

## Priorisierter Issue-Backlog

### Prio 1 — BLOCKER, strukturell (Feature fehlt komplett)

| Nr | Thema | Betroffene Screens | Schwere |
|----|-------|-------------------|---------|
| B-01 | Wegpunkt-Editor: dedizierter Editor-Screen mit Karte, Höhenprofil, WP-Liste, KI-Vorschläge | Desktop WP-Editor, Mobile WP-Editor | BLOCKER |
| B-02 | Location-New: 3-Schritt-Wizard mit Smart-Import + Minimap | Desktop Location-New | BLOCKER |
| B-03 | Wizard Schritt 1: Aktivitätsprofil-Auswahl + Kürzel-Feld fehlen | Desktop + Mobile Wiz-1 | BLOCKER |
| B-04 | Wizard Schritt 3: falscher Inhalt — Metriken statt Wegpunkt-Bestätigung | Desktop + Mobile Wiz-3 | BLOCKER |
| B-05 | Trip-Detail Übersicht-Tab: Höhenprofil + Etappen-Layout ersetzen das Card-Grid | Desktop + Mobile | BLOCKER |

### Prio 2 — BLOCKER, Terminologie + Daten

| Nr | Thema | Betroffene Screens | Schwere |
|----|-------|-------------------|---------|
| B-06 | Archiv: "Touren" → "Trips" app-weit korrigieren | Archiv Desktop | BLOCKER |
| B-07 | Trips-Liste: Status-Kategorien falsch (Pausiert/Archiviert statt Abgeschlossen/Drafts) | Desktop Trips-Liste | BLOCKER |
| B-08 | Trips-Liste: Aktions-Spalte (6 Icon-Buttons fehlen; Kebab reicht nicht) | Desktop Trips-Liste | BLOCKER |
| B-09 | Mobile Alerts: Auslöse-Modus-Picker + fixierter Footer fehlen | Mobile Alerts | BLOCKER |
| B-10 | Mobile Metriken: Akkordeon + Toggle-Controls + fixierter Footer fehlen | Mobile Metriken | BLOCKER |
| B-11 | Mobile Wizard Step 4: Kanal-Toggles fehlen; Abend-Default 06:00 statt 18:00 | Mobile Wiz-4 | BLOCKER |
| B-12 | Mobile Trip-Detail: Kennzahlen-Kacheln fehlen | Mobile Trip-Detail | BLOCKER |
| B-13 | Mobile Trips-Liste: Filter-Pills (Alle/Aktiv/Geplant/Fertig) fehlen | Mobile Trips-Liste | BLOCKER |

### Prio 3 — MEDIUM, Design-System-Komponenten

| Nr | Thema | Betroffene Dateien | Schwere |
|----|-------|-------------------|---------|
| M-01 | Segmented: Prop-API inkompatibel mit Katalog (`items`→`options`, `value`→`selected`, kein `size`) | Segmented.svelte | MEDIUM |
| M-02 | AlertRow: Icon-Mapping unvollständig (alle außer Gewitter → Wind-Icon) | AlertRow.svelte | MEDIUM |
| M-03 | Eyebrow: Default-Farbe `--g-ink-faint` (2,85:1) statt `--g-ink-3`; WCAG-Risiko | Eyebrow.svelte | MEDIUM |
| M-04 | Card: `padding` + `accent` Props funktionslos (werden stillschweigend ignoriert) | card.svelte | MEDIUM |

### Prio 4 — MEDIUM, Screen-Korrekturen

| Nr | Thema | Schwere |
|----|-------|---------|
| M-05 | Trip-Detail: Tab-Beschriftungen angleichen + "Matches"-Tab prüfen | MEDIUM |
| M-06 | Wizard Step 4: Uhrzeit-Format 12h → 24h (06:00 PM → 18:00) | MEDIUM |
| M-07 | E-Mail/SMS-Vorschau: Fehlermeldung auf Deutsch + benutzerfreundlich | MEDIUM |
| M-08 | Archiv: Suchfeld-Breite auf volle Breite setzen | MEDIUM |
| M-09 | Mobile Home: Header-Struktur (Glocke + Plus statt Mond-Icon) | MEDIUM |
| M-10 | Mobile Wizard Step 2: Badge-Farbe Etappe orange statt blau | MEDIUM |

### Offen / Klärung PO erforderlich

| Nr | Thema | Frage |
|----|-------|-------|
| PO-01 | Home: Personalisiertes Greeting "Guten Morgen, Gregor" | Soll implementiert werden (Name aus Auth)? |
| PO-02 | Home: Demo-Wetter im Trip-Hero | Design zeigt Wetterdaten; gilt "kein Live-Wetter" auch für Demo/Cache-Anzeige? |
| PO-03 | Trips-Liste: 6 Icon-Buttons in Aktions-Spalte | SOLL-Design oder intentionell durch Kebab ersetzt? |

---

## Nicht-Delta-Befunde (ausschließlich Datenzustand)

Diese Abweichungen sind **kein** UI-Bug — sie entstehen durch die Testdaten des E2E-Trips:

- **Compare-Screen** (Desktop + Mobile): Leerzustand weil keine Orte konfiguriert
- **E-Mail/SMS-Vorschau-Inhalt**: HTTP-422 weil Test-Trip keine Wegpunkte hat
- **Archiv-Tabelleninhalt**: 0 Einträge weil keine archivierten Trips vorhanden
- **Home Trip-Daten**: Nullwerte für km/Höhe weil Test-Trip minimale Daten hat

---

## Erkenntnisse zur Implementierungsreife

**Gut implementiert (kein oder minimales Delta):**
- Alle 10 Molecules (DetailRow, ThresholdRow, Field, Stat, StagePill, ChannelRow, BriefingScheduleRow, BriefingTimelineRow): vollständig
- WIcon, ElevSparkline, Pill: vollständig
- Archiv-Screen (bis auf Terminologie und Suchfeld-Breite)
- Wordmark, Bottom-Nav (Grundstruktur), Trip-Detail (Tab-Grundstruktur)

**Kritische Lücken — Features designed aber nicht implementiert:**
- Wegpunkt-Editor (eigenständiger Screen mit Karte + Profil)
- Location-New-Wizard (3-Schritte + Smart-Import)
- Wizard-Schritt-Reihenfolge und -Inhalte weichen erheblich vom Design ab
- Mobile-spezifische UI-Muster (Akkordeon, Modus-Picker, Kennzahlen-Kacheln)

---

## Methodik-Hinweise

1. **Phase 4-Validierung empfohlen für:** B-03, B-07, B-08, M-05 — es ist möglich, dass diese Abweichungen intentionelle Designentscheidungen nach dem Handoff sind.
2. **Wizard-Schritt-Struktur:** Die Reihenfolge der Wizard-Schritte (Route → Etappen → Wetter → Reports im IST vs. Profil → GPX → Wegpunkte → Briefings im SOLL) ist eine fundamentale Architekturabweichung. Klärung ob dies ein Redesign-Entscheid ist oder implementiert werden soll.
3. **Desktop WP-Editor vs. `/trips/[id]/edit`:** Der IST-Screenshot trifft die Route `/trips/[id]/edit` — die dedizierte WP-Editor-Route existiert eventuell unter einer anderen URL. Vor Issue-Erstellung prüfen ob ein separater WP-Editor-Screen existiert.
