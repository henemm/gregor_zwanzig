# Design-Request: Wizard-Screens auf aktuelle Implementierung aktualisieren

**Priorität:** Hoch — Handoff-Screens sind veraltet und blockieren korrekte SOLL-IST-Vergleiche

## Hintergrund

Der Trip-Wizard (`/trips/new`) wurde in Issue #300 bewusst umstrukturiert:

| | Altes Design (noch im Handoff) | Aktuelles Design (implementiert, korrekt) |
|-|-------------------------------|------------------------------------------|
| Step 1 | Profil & Eckdaten (Activity-Chips + Name + Kürzel) | Route (Name + Region + GPX-Upload) |
| Step 2 | GPX-Import (Drag-Drop) | Etappen (erkannte Etappen-Liste nach GPX) |
| Step 3 | Wegpunkte bestätigen (Vorschläge) | Wetter (Aktivitätsprofil-Dropdown + Metriken-Tabelle) |
| Step 4 | Briefings & Kanäle (Kanal-Toggles) | Reports (2×2 Cards: Abend/Morgen/Warnungen/Trend) |

Der Handoff zeigt noch das alte Design. Die Implementierung folgt dem neuen Design — das ist richtig.

## Was benötigt wird

**Aktualisierte SOLL-Screens für alle 4 Wizard-Schritte** — Desktop (1440px) + Mobile (390px):

### Step 1 — Route
- Trip-Name-Input (Pflicht) + Region-Input (optional, max 50 Zeichen)
- GPX-Upload-Dropzone (dashed accent border)
- "Aus Dateisystem wählen" + Drag-Drop
- Stepper: "SCHRITT 1 VON 4 · NEUE TOUR", H1 "Route — wie kennt das System deinen Weg?"
- Footer: Abbrechen | Weiter → (disabled bis Name + GPX)
- Referenz IST: `claude-code-handoff/soll-audit-2026-05-27/ist-screenshots/desktop-wizard-step1.png`

### Step 2 — Etappen
- Header: "N ETAPPEN ERKANNT AUS N GPX" + "Zusammenführen"-Link
- Etappen-Liste: Nummer · Name · Datum · km · ↑Höhe · WP-Zähler · "+N Vorschläge" (orange gestrichelte Pill)
- Rechte Spalte: Vorlagen-Panel (GR20, Karnischer Höhenweg, Stubaier Höhenweg)
- Footer: ← Zurück | "Pausentag einfügen" | Weiter →
- Referenz IST: `claude-code-handoff/soll-audit-2026-05-27/ist-screenshots/desktop-wizard-step2.png`

### Step 3 — Wetter
- Aktivitätsprofil-Dropdown (Alpen-Trekking Sommer, Skitouren, Küsten, …)
- Metriken-Tabelle: pro Zeile Checkbox + Metrik-Name + 3 Horizon-Pills (HEUTE/MORGEN/ÜBERMORGEN) + Format-Label
- Schwarze Oval-Pills für Horizons — aber: IST-Styling ist sehr dunkel/dominant, bitte polieren
- Footer: ← Zurück | Weiter →
- Referenz IST: `claude-code-handoff/soll-audit-2026-05-27/ist-screenshots/desktop-wizard-step3.png`

### Step 4 — Reports
- **2×2 Card-Grid:**
  1. Abend-Briefing: Aktiv-Checkbox + Uhrzeit **18:00** (24h!) + Kanal-Chips
  2. Morgen-Update: Aktiv-Checkbox + Uhrzeit 06:00 + Kanal-Chips
  3. Warnungen · AUTARK: kein Zeitfeld, Badge "AUTARK" + Beschreibungstext + Kanal-Chips
  4. Mehrtages-Trend: Hinweistext "Im Abend-Briefing enthalten"
- Abschluss-Button: "**Tour speichern**" (nicht "Speichern")
- Footer-Hinweis kursiv: "Unterwegs läuft alles autark. Kein Eingreifen nötig."
- Referenz IST: `claude-code-handoff/soll-audit-2026-05-27/ist-screenshots/desktop-wizard-step4.png`

## Bekannte IST-Probleme die das SOLL bereinigen sollte

- Step 3: Schwarze Oval-Buttons für HEUTE/MORGEN/ÜBERMORGEN sind optisch zu dominant → polieren
- Step 4: Uhrzeiten aktuell als 12h (06:00 PM) — SOLL muss 24h zeigen (18:00)
- Step 4: Button heißt "Speichern" — SOLL heißt "Tour speichern"
- Alle Steps: Stepper-Subtext unter den Schritten fehlt im IST — im SOLL zeigen (z.B. "Route · Etappen · Wetter · Reports")

## Mobile (390px)

Gleiche 4 Steps, aber:
- Step 1: Fortschrittsbalken (4 Segmente) statt nur Text-Stepper
- Step 4: Cards gestapelt (1-spaltig), nicht 2×2
- Kein Bottom-Nav während Wizard-Session

---

# 📐 Korrektur-Block · v2 · 2026-05-27 (PO-Review)

> **Status:** Diese Korrektur ersetzt die Specs für Step 3 und Step 4 oben. Step 1, Step 2 und die Mobile-Hinweise bleiben gültig.
>
> **Anlass:** Beim Review der v1-Mockups (alle 4 Steps gem. ursprünglicher Spec gebaut) hat der PO drei konzeptionelle Probleme erkannt, die nicht durch Detail-Polish lösbar sind, sondern eine Re-Strukturierung erfordern.

## Was sich ändert — Kurzfassung

| | v1 (oben) | v2 (gültig) |
|-|-|-|
| **Anzahl Steps** | 4 | **5** |
| Step 3 (Wetter) | Metriken × Horizon-Pills HEUTE/MORGEN/ÜBERMORGEN | Metriken × **Format-Variante** (Roh / Skala / Vereinfacht / Symbol) — scrollbar, gruppiert |
| Step 4 NEU | — | **Layout — Reihenfolge & Spalten-Auswahl pro Kanal** (Email/Telegram/Signal/SMS) mit Live-Preview |
| Step 4 alt → Step 5 | 2×2 Cards (Abend, Morgen, Warnungen+AUTARK, Mehrtages-Trend) | **3 Cards** (Abend mit Mehrtages-Toggle, Morgen, Warnungen) |
| AUTARK-Pill | Vollbreiter Banner | **Komplett entfernt** — autarker Betrieb ist Default, kein Feature-Highlight |

## Begründung (für Reviewer)

**(1) „Horizonte HEUTE/MORGEN/ÜBERMORGEN" gehören nicht in die Trip-weite Metriken-Konfiguration.**
- Die zugrundeliegende Frage ist *kanal-spezifisch*: SMS hat 140 Zeichen → nur „Heute". Email hat keine Begrenzung → bis 7 Tage. Diese Constraint-Auflösung gehört in den Output-Layout-Renderer (body-14), nicht in eine pauschale Wizard-Spalte.
- Das ursprünglich anvisierte Use-Case („Gewitter von Übermorgen soll im SMS-Briefing landen") wird elegant über die Metrik-Priorisierung im Output-Layout-System (SMS-Renderer) gelöst.

**(2) Mehrtages-Trend ist Teil des Abend-Briefings, nicht ein eigenständiger Report.**
- Eine eigene Card suggeriert eigenständigen Zeitplan, eigene Kanäle — das ist nicht der Fall.
- Lösung: Mehrtages-Trend wird als Toggle „**3–7-Tage-Ausblick enthalten**" innerhalb der Abend-Briefing-Card verankert.
- Das Grid schrumpft von 4 auf 3 Cards (Desktop: 3-spaltig; Mobile: 1-spaltig gestapelt).

**(3) Output-Layout (Reihenfolge & Spalten pro Kanal) gehört zum Trip-Setup.**
- Bisher: Wizard endet, der User landet auf einem konfigurierten Trip — aber die *Inhalte* der Briefings sind nicht festgelegt (Reihenfolge zufällig, kein SMS-Priorisierung, keine Kanal-spezifische Reduktion). Nutzer hat einen „leeren" Trip ohne zu wissen, wie die Briefings aussehen.
- Lösung: Output-Layout wird **Step 4 des Wizards** — derselbe `screen-metrics-editor`-Component, der auch von Trip-Detail aus erreichbar bleibt (1 Component, 2 Einbettungen).
- **Wichtig:** Abend & Morgen nutzen **denselben Layout-Aufbau pro Kanal** (PO-Entscheidung). Spätere Per-Report-Overrides können in einer Folge-Issue ergänzt werden.

**(4) AUTARK ist Default, kein Feature.**
- Der vorherige große AUTARK-Pill auf der Warnungen-Card hat den autarken Betrieb als hervorhebbares Feature inszeniert. Tatsächlich ist autarker Betrieb der Grundzustand der gesamten App.
- Lösung: Pill entfernt. Beschreibungstext „Alert, sobald eine Alarmregel überschritten wird" reicht. Footer-Hinweis (kursiv, am Ende von Step 5) „Unterwegs läuft alles autark. Kein Eingreifen nötig." bleibt als Reassurance bestehen.

## Step 3 — Wetter (v2)

**Zweck:** Festlegen, *welche* Metriken überhaupt gesammelt werden, in welchem *Format*.

- Aktivitätsprofil-Dropdown (links, ~260 px breit) — Profil setzt die Default-Auswahl (Trekking → ohne UV, MTB → mit Wind & Niederschlag, Skitour → mit Schneefallgrenze & Lawinensituation).
- Metriken-Liste **scrollbar** (max-height ~540 px), gruppiert nach: Temperatur · Wind · Niederschlag · Sicht & Sonne · Atmosphäre (15+ Metriken sichtbar, Scroll deutlich erkennbar — Fade-Gradient am unteren Rand).
- Pro Zeile: Checkbox · Metrik-Name · **Format-Select (Dropdown)** mit Optionen:
  - `Roh` — z.B. „11,6 °C", „45 km/h"
  - `Skala` — z.B. „5 Bft", „mäßig"
  - `Vereinfacht` — z.B. „warm", „böig"
  - `Symbol` — z.B. ☀ ☁ ⛈ (für sehr kompakte Kanäle)
- **Keine Horizon-Pills.** Welcher Zeit-Horizont in welchem Kanal landet, regelt der Renderer pro Kanal (siehe body-14-output-layout-system).
- Footer-Hinweis am unteren Listen-Rand (mono, klein): „Reihenfolge & Kanal-Zuordnung kommen in Schritt 4."
- Hinweis: Exakte Format-Auswahl pro Metrik (welche Optionen sind für „Wind" sinnvoll, welche für „Gewitter"?) wird im Backend entschieden. Mockup zeigt den UX-Pattern, nicht die finale Optionsliste.

## Step 4 — Layout (NEU)

**Zweck:** Festlegen, *wie* das Briefing pro Kanal aussieht — Reihenfolge der Metriken, was in die Tabelle passt, was in „Detail" wandert, was wegfällt.

**Layout:**
- Eyebrow + H1 + Hilfstext: „Abend & Morgen nutzen denselben Aufbau."
- **Channel-Tab-Strip oben** (Desktop: 4 Spalten gleich breit; Mobile: horizontal scrollbare Chips):
  - ✉ Email · ∞ Spalten
  - → Telegram · max 8 Spalten
  - ▲ Signal · max 6 Spalten
  - \* SMS · ≤140 Zeichen, keine Tabelle
- **Body 2-spaltig (Desktop):**
  - **Linke Spalte (1fr):** Drag-sortierbare Metriken-Liste in zwei Sektionen:
    - „**Spalten · N / max**" — Metriken, die als eigene Tabellen-Spalten erscheinen.
    - „**Wandert in „Detail"-Zeile · N**" — überzählige Metriken (warn-toned Badge), kommen als Detail-Zeile unter die Tabelle.
    - Pro Zeile: Drag-Grip · Positions-Nr · Metrik-Name + Format · Spalten/Detail-Tag · ▲▼ Move-Buttons.
  - **Rechte Spalte (380 px sticky):** Live-Vorschau für aktiven Kanal:
    - Email: vereinfachte Tabelle (6 Spalten × 3 Zeilen Sample-Daten)
    - Telegram/Signal: Mock-Bubble (max 272 px Content-Breite für Signal, getreu Renderer-Constraint) mit Mono-Tabelle + Detail-Zeile
    - SMS: Text-Block mit Zeichen-Counter „N / 140"
- **SMS-Spezialfall** (statt 2-spaltig): Priorisierungs-Liste — Drag-Reihenfolge bestimmt, welche Metriken zuerst in die Zeichen-Budget rutschen.
- **Mobile:** Tab-Chips horizontal scrollbar, dann Preview ZUERST (Kontext vor Aktion), dann darunter die Drag-Liste mit ▲▼-Buttons (mindestens 36 px hoch, Touch-Target).

**Wichtig:** Die Layout-Konfiguration ist trip-spezifisch und wird in Trip-Detail über denselben Component nachträglich änderbar (`screen-metrics-editor.jsx` ist das geteilte Asset).

## Step 5 — Reports (statt v1 Step 4)

**Zweck:** Zeitplan & Versand-Kanäle pro Report.

**3 Cards** (Desktop: 3-spaltig; Mobile: 1-spaltig gestapelt):

1. **Abend-Briefing**
   - Aktiv-Switch · Eyebrow „ABEND-BRIEFING" · Titel „Vor dem Schlafen" · Sub „Plan & Vorhersage für morgen."
   - Mono Uhrzeit `18:00` (24h-Format) + Button „Ändern"
   - **NEU:** kleine eingelassene Card mit Switch + Label „3–7-Tage-Ausblick enthalten" + Hint „Mehrtages-Trend wird mitgeschickt"
   - Versand-Kanäle: Kanal-Chips (Email/Signal/Telegram/SMS — aktive in accent-tint)
   - Link „Inhalt im Output-Editor anpassen →"

2. **Morgen-Update**
   - Aktiv-Switch · Eyebrow „MORGEN-UPDATE" · Titel „Vor Etappenstart" · Sub „Aktuelle Bedingungen für heute."
   - Mono Uhrzeit `06:00` (24h-Format) + Button „Ändern"
   - Versand-Kanäle
   - Link „Inhalt im Output-Editor anpassen →"

3. **Warnungen**
   - Kein Switch im Header (Warnungen sind immer aktiv, ihre Aktivität wird durch Alarmregeln gesteuert).
   - Eyebrow „WARNUNGEN" · Titel „Sofort, wenn nötig" · Sub „Alert, sobald eine Alarmregel überschritten wird."
   - Kein Zeitfeld
   - Versand-Kanäle
   - Link „Alarmregeln verwalten →"

**Kein AUTARK-Pill mehr.** Footer-Hinweis kursiv am unteren Rand: „Unterwegs läuft alles autark. Kein Eingreifen nötig."

Abschluss-Button (Footer rechts): **„Tour speichern"**.

## Stepper-Anpassung

5-Circle-Stepper mit Verbinder-Linien zwischen den Circles. Sublabel unter jedem Step:

| # | Label | Sublabel |
|-|-|-|
| 1 | Route | Name & GPX hochladen |
| 2 | Etappen | Etappen prüfen |
| 3 | Wetter | Metriken auswählen |
| 4 | Layout | Reihenfolge pro Kanal |
| 5 | Reports | Zeitplan & Versand |

States:
- **Done** — paper bg, ink-3 1.5px border, ink-2 ✓ (KEIN grünes Mint — entsättigtes Ink-Done)
- **Current** — paper bg, accent 2px border, accent number
- **Upcoming** — paper bg, rule 1.5px border, ink-4 number (nicht klickbar)

Mobile-Stepper: 5-Segment-Fortschrittsbalken (3 px hoch, var(--g-accent) für aktiv/done, var(--g-rule) für upcoming).

## Mobile-Spezifika (unverändert gültig, ergänzt um Step 4)

- 5-Segment-Fortschrittsbalken statt Text-Stepper
- Step 4 Layout: Kanal-Chips horizontal scrollbar, Preview zuerst, dann Drag-Liste mit ▲▼-Buttons
- Step 5 Reports: 3 Cards 1-spaltig gestapelt
- Kein Bottom-Nav während Wizard

## Referenz-SOLL-Screens (Design-Canvas)

- Desktop: `Gregor 20 - Desktop.html` → Section „04 · Trip-Wizard" → 5 Artboards `wizard-step1` … `wizard-step5`
- Mobile: `Gregor 20 - Mobile.html` → Section „03 · Trip-Wizard" → 5 Artboards `m-wiz-1` … `m-wiz-5`

## Acceptance Criteria

- [ ] Wizard ist 5-stufig, nicht 4-stufig
- [ ] Step 3 hat keine Horizon-Pills, sondern Format-Dropdown pro Metrik
- [ ] Step 3 zeigt 15+ Metriken in gruppiertem, scrollbarem Container
- [ ] Step 4 (Layout) ist als eigener Wizard-Schritt vorhanden mit 4 Kanal-Tabs
- [ ] Step 4 zeigt pro Kanal eine Live-Preview rechts (Desktop) / oben (Mobile)
- [ ] Step 4 nutzt `screen-metrics-editor.jsx` als zugrundeliegenden Component (geteilt mit Trip-Detail)
- [ ] Step 5 hat 3 Cards, nicht 4
- [ ] Mehrtages-Trend ist ein Toggle innerhalb der Abend-Briefing-Card
- [ ] Kein AUTARK-Pill auf der Warnungen-Card
- [ ] Uhrzeiten im 24h-Format (`18:00`, `06:00`)
- [ ] Abschluss-Button heißt „Tour speichern"
- [ ] Footer-Hinweis kursiv „Unterwegs läuft alles autark. Kein Eingreifen nötig." nur auf Step 5 sichtbar

## Out of Scope (Folge-Issues)

Bewusst NICHT Teil dieses Issues — Klärung in eigenen Tickets, damit der
Wizard-Umbau nicht blockiert wird:

1. **Finale Format-Optionen pro Metrik-Typ.** Das Mockup zeigt vier
   generische Optionen (Roh / Skala / Vereinfacht / Symbol). Welcher Satz
   für jede einzelne Metrik (z. B. „Wind", „Gewitter", „Schneefallgrenze")
   tatsächlich sinnvoll ist, entscheidet Backend + Daten-Logik. Folge-Issue
   pflegt eine Mapping-Tabelle `metric_id → allowed_formats[]` und einen
   Default pro Metrik.

2. **Per-Report-Layout-Overrides.** Abend und Morgen nutzen aktuell PER
   PO-ENTSCHEIDUNG dasselbe Layout pro Kanal. Wenn sich aus dem Betrieb
   ergibt, dass z. B. der Morgen-Report eine andere Spalten-Reihenfolge
   braucht („Wind zuerst, weil das den Tag bestimmt"), kommt das als
   Folge-Issue zurück. Daten-Schema sollte dies erlauben (Layout-Set pro
   `(trip, report_type)` statt nur pro `(trip)`), aber das UI exposed es
   noch nicht.

3. **Echtes Drag-and-Drop in Step 4.** Mockup nutzt ▲▼-Move-Buttons als
   Reihenfolge-Steuerung — Implementation-Detail. Wenn Drag-and-Drop
   gewünscht ist (Library-Wahl, Touch-Handling, Keyboard-Accessibility),
   bitte als separates UX-Issue, das auch das mobile Reorder-Pattern
   einschließt.

4. **„Inhalt im Output-Editor anpassen →"-Link von Step 5 Cards** soll
   sinnvollerweise auf die Trip-Detail-Seite verlinken (dort steckt
   derselbe Component). Routing wird Teil der Implementation, nicht des
   Mockups.

