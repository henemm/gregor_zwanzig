<!-- gregor-zwanzig-handoff: stable_id=wizard-screens-update-407-422 -->
# Issue #407 + #422 · Trip-Wizard auf aktuelle Spec aktualisieren (5-stufig, Layout-Step neu)

**Type:** Design-Compliance · Frontend · UX-Re-Strukturierung
**Priority:** High — Wizard ist Onboarding-Pfad zur ersten Tour-Konfiguration

**Status auf GitHub:** Issue #407 (Schritte 1-3) und #422 (Schritte 4-5) sind bereits angelegt. Dieser Body **ersetzt** die ursprünglichen 4-Step-Bodies durch die neue 5-Step-Spec gemäß PO-Review vom 27. Mai 2026.

**Design Reference:**
- Volle Spec mit Begründungen: `docs/design-requests/issue_407_422_wizard_screens_update.md`
- Design-Canvas Desktop: `Gregor 20 - Desktop.html` → Section „04 · Trip-Wizard" (5 Artboards `wizard-step1` … `wizard-step5`)
- Design-Canvas Mobile: `Gregor 20 - Mobile.html` → Section „03 · Trip-Wizard" (5 Artboards `m-wiz-1` … `m-wiz-5`)

---

## Worum es geht (Kurz)

Der bestehende 4-stufige Wizard wird auf **5 Schritte** umgebaut. Drei konzeptionelle Probleme im aktuellen Design werden behoben:

1. **„Horizonte" als Trip-Setting sind falsch verortet.** HEUTE/MORGEN/ÜBERMORGEN gehören nicht zur Trip-weiten Metriken-Auswahl — die Zeit-Horizont-Auflösung ist kanal-spezifisch und passiert im Output-Renderer.
2. **Mehrtages-Trend ist kein eigener Report.** Er ist Teil des Abend-Briefings.
3. **Output-Layout (Reihenfolge & Spalten pro Kanal) fehlte im Wizard.** Nutzer bekamen einen konfigurierten Trip, ohne dass das Briefing inhaltlich festgelegt war.

---

## Neue Struktur · 5 Schritte

| # | Step | Zweck |
|-|-|-|
| 1 | **Route** | Trip-Name + Region + GPX-Upload |
| 2 | **Etappen** | Erkannte Etappen prüfen + Vorlagen |
| 3 | **Wetter** | Welche Metriken werden gesammelt + Format pro Metrik |
| 4 | **Layout** ✨ NEU | Reihenfolge & Spalten-Auswahl pro Kanal (Email/Telegram/Signal/SMS) mit Live-Preview |
| 5 | **Reports** | Zeitplan & Versand-Kanäle (3 Cards: Abend mit 3–7-Tage-Toggle, Morgen, Warnungen) |

Stepper-Sublabel:

| # | Label | Sublabel |
|-|-|-|
| 1 | Route | Name & GPX hochladen |
| 2 | Etappen | Etappen prüfen |
| 3 | Wetter | Metriken auswählen |
| 4 | Layout | Reihenfolge pro Kanal |
| 5 | Reports | Zeitplan & Versand |

---

## Schritt-für-Schritt-Specs

### Step 1 · Route

![Step 1 · Route](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-flow1B-wizard-step1-route.png)

- Trip-Name (Pflicht) · Region (optional, max 50 Zeichen)
- GPX-Upload: Dropzone mit accent dashed border, Hint „GPX-Upload empfohlen — manuelle Eingabe geht auch in Schritt 2"
- Footer: Abbrechen | Weiter → (disabled bis Name + GPX vorhanden)

### Step 2 · Etappen

![Step 2 · Etappen](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-flow1C-wizard-step2-etappen.png)

- 2-spaltig: links Etappen-Liste, rechts Vorlagen-Panel (GR20, Karnischer Höhenweg, Stubaier)
- Etappen-Zeile: Drag-Grip · T01-Pill (accent-tint) · Datum · Name · km · ↑Höhe · WP-Zähler · „+N Vorschläge" (orange gestrichelt) oder GEPRÜFT-Tag
- Footer: ← Zurück | „+ Pausentag einfügen" | Weiter →

### Step 3 · Wetter — keine Horizon-Pills mehr

![Step 3 · Wetter](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-flow1D-wizard-step3-wetter.png)

**Was sich ändert:**
- Statt HEUTE/MORGEN/ÜBERMORGEN-Pills pro Metrik gibt es ein **Format-Dropdown** pro Metrik (Roh / Skala / Vereinfacht / Symbol).
- 15+ Metriken in 5 Gruppen (Temperatur, Wind, Niederschlag, Sicht & Sonne, Atmosphäre), in scrollbarem Container mit Fade-Indikator am unteren Rand.
- Sticky Gruppen-Header beim Scrollen.
- Aktivitätsprofil-Dropdown links setzt Default-Auswahl.

**Begründung:** Die Frage „welcher Zeit-Horizont in welchem Kanal?" ist *kanal-spezifisch* (SMS = wenig, Email = viel) und gehört in den Output-Renderer (siehe body-14-output-layout-system.md), nicht in eine pauschale Trip-Spalte.

### Step 4 · Layout — NEU

![Step 4 · Layout](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-flow1E-wizard-step4-layout.png)

**Zweck:** Reihenfolge & Spalten-Auswahl pro Kanal. **Abend & Morgen nutzen denselben Aufbau** (PO-Entscheidung). Layout ist trip-spezifisch und bleibt nachträglich änderbar über die Trip-Detail-Seite — derselbe Component (`screen-metrics-editor.jsx`).

**Layout:**
- 4 Channel-Tabs oben: ✉ Email (∞ Spalten) · → Telegram (max 8) · ▲ Signal (max 6) · \* SMS (≤140 Zeichen)
- Body 2-spaltig (Desktop): linke Spalte Drag-sortierbare Metriken in zwei Sektionen („Spalten" + „Wandert in Detail-Zeile"), rechte Spalte sticky Live-Preview.
- SMS-Spezialfall: Priorisierungs-Listen-Mode (keine Tabelle).
- Mobile: Tabs als horizontal scrollbare Chips, Preview ZUERST (Kontext vor Aktion), dann Drag-Liste mit ▲▼-Buttons (mindestens 36 px hoch).

### Step 5 · Reports — 3 Cards (statt 4)

![Step 5 · Reports](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-flow1F-wizard-step5-reports.png)

**Was sich ändert vs. v1-Spec:**
- Nur **3 Cards** (Abend, Morgen, Warnungen) — der frühere „Mehrtages-Trend" als 4. Card entfällt.
- **Mehrtages-Trend wird Toggle** innerhalb der Abend-Briefing-Card („3–7-Tage-Ausblick enthalten").
- **Kein AUTARK-Pill mehr.** Autarker Betrieb ist Default der App, kein Feature-Highlight.

**Cards:**
1. **Abend-Briefing**: Aktiv-Switch · Uhrzeit `18:00` (24h) · eingelassene Card mit Toggle „3–7-Tage-Ausblick enthalten" · Kanal-Chips · Link „Inhalt im Output-Editor anpassen →"
2. **Morgen-Update**: Aktiv-Switch · Uhrzeit `06:00` (24h) · Kanal-Chips · Link „Inhalt im Output-Editor anpassen →"
3. **Warnungen**: kein Switch (immer aktiv, gesteuert durch Alarmregeln) · keine Uhrzeit · Kanal-Chips · Link „Alarmregeln verwalten →"

Abschluss-Button: **„Tour speichern"**.
Footer-Hinweis kursiv unten: *„Unterwegs läuft alles autark. Kein Eingreifen nötig."*

---

## Mobile-Spezifika (390 px)

![Mobile Step 1](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-flow1B-mobile-step1-route.png)
![Mobile Step 4 · Layout](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-flow1E-mobile-step4-layout.png)
![Mobile Step 5 · Reports](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-flow1F-mobile-step5-reports.png)

- 5-Segment-Fortschrittsbalken oben (statt Circle-Stepper)
- Step 4 Layout: Channel-Chips horizontal scrollbar, Preview ZUERST, dann Drag-Liste mit ▲▼-Buttons
- Step 5 Reports: 3 Cards 1-spaltig gestapelt
- Bottom-Nav während Wizard ausgeblendet
- Step 5 Button „Tour speichern" über die volle Breite (Primary)

Alle Mobile-SOLL-Screens:
- [Step 1 · Route](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-flow1B-mobile-step1-route.png)
- [Step 2 · Etappen](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-flow1C-mobile-step2-etappen.png)
- [Step 3 · Wetter](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-flow1D-mobile-step3-wetter.png)
- [Step 4 · Layout](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-flow1E-mobile-step4-layout.png)
- [Step 5 · Reports](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-flow1F-mobile-step5-reports.png)

---

## Constraints

| ID | Constraint |
|-|-|
| C1 | Wizard hat exakt 5 Schritte, nicht 4. Step 4 = „Layout" ist neu. |
| C2 | Step 4 nutzt **denselben Component** wie der Output-Editor in Trip-Detail (`screen-metrics-editor.jsx`-Pendant). Zwei separate Editoren wären Drift-anfällig. |
| C3 | Abend & Morgen-Briefing teilen sich **eine** Layout-Konfiguration pro Kanal. Keine Per-Report-Overrides in dieser Iteration. |
| C4 | Step 3 zeigt **kein** Horizon-Pill-Layout mehr. Zeit-Horizont wird im Output-Renderer pro Kanal aufgelöst. |
| C5 | Step 5 zeigt **3** Cards, nicht 4. Mehrtages-Trend ist Toggle in der Abend-Card. |
| C6 | Kein AUTARK-Pill auf der Warnungen-Card. Footer-Hinweis kursiv reicht. |
| C7 | Uhrzeiten im 24h-Format (`18:00`, `06:00`). Niemals 12h. |
| C8 | Abschluss-Button heißt „Tour speichern", nicht nur „Speichern". |
| C9 | Mobile: Bottom-Nav während Wizard-Session ausgeblendet. |

---

## Acceptance Criteria

- [ ] Wizard ist 5-stufig (Route · Etappen · Wetter · Layout · Reports)
- [ ] Stepper zeigt 5 Circles mit Verbinder-Linien + Sublabel
- [ ] Mobile: 5-Segment-Fortschrittsbalken
- [ ] Step 3 hat keine Horizon-Pills, sondern Format-Dropdown pro Metrik
- [ ] Step 3 zeigt 15+ Metriken in gruppiertem, scrollbarem Container
- [ ] Step 4 (Layout) ist als eigener Schritt vorhanden
- [ ] Step 4 hat 4 Channel-Tabs mit Constraint-Info pro Kanal
- [ ] Step 4 zeigt pro Kanal eine Live-Preview
- [ ] Step 4 nutzt geteilten Component mit Trip-Detail-Output-Editor
- [ ] Step 5 hat 3 Cards, nicht 4
- [ ] Mehrtages-Trend ist Toggle innerhalb der Abend-Briefing-Card
- [ ] Kein AUTARK-Pill auf Warnungen-Card
- [ ] Uhrzeiten im 24h-Format
- [ ] Abschluss-Button heißt „Tour speichern"
- [ ] Footer-Hinweis „Unterwegs läuft alles autark." nur auf Step 5

---

## Out of Scope (Folge-Issues)

Bewusst NICHT Teil dieses Issues — siehe Spec-Datei für Details:

1. **Finale Format-Optionen pro Metrik-Typ.** Mockup zeigt vier generische Optionen. Welcher Satz für jede Metrik sinnvoll ist, regelt Backend.
2. **Per-Report-Layout-Overrides.** Aktuell PO-Entscheidung: Abend = Morgen. Daten-Schema sollte später Override-Layer erlauben.
3. **Echtes Drag-and-Drop in Step 4.** Mockup nutzt ▲▼-Buttons. Real DnD ist Implementation-Detail (Library-Wahl, Touch, A11y).
4. **Routing für „Inhalt im Output-Editor anpassen →"-Link** in Step 5: soll zur Trip-Detail-Seite navigieren — Routing-Detail.

---

## Migration

- Bestehende 4-Step-Wizard-Implementierung wird ersetzt. Bereits gespeicherte Trips bekommen ein Default-Layout pro Kanal (Spalten-Reihenfolge = Metriken-Default-Sort + alle aktiven Metriken).
- Migration-Pseudocode für `trip.output_layout`-Feld pro Kanal: siehe body-14-output-layout-system.md.
