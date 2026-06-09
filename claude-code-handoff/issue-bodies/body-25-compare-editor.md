<!-- gregor-zwanzig-handoff: stable_id=compare-editor-progressive -->
# Issue #25 · Orts-Vergleich — Progressive Tab Editor (Anlegen + Bearbeiten, Desktop + Mobile)

**Type:** Design-Compliance · Frontend · UX-Re-Strukturierung  
**Priority:** High — ersetzt `screen-compare-wizard.jsx` (deprecated + gelöscht 2026-06-09)  
**Baut auf:** #10 (Ortsvergleich-Wizard original), #20 (Kanonische IA), #24 (Trip Progressive Editor)

**Design Reference:**
- Desktop: `screen-compare-editor.jsx` (Prefix `CE_`) — `ScreenCompareEditor`
- Mobile:  `screen-compare-editor-mobile.jsx` (Prefix `CEM_`) — `ScreenCompareEditorMobile`
- Canvas Desktop: `Gregor 20 - Desktop.html` → Sektion „04 · Ortsvergleich-Hub"
- Canvas Mobile:  `Gregor 20 - Mobile.html` → Sektion „05 · Ortsvergleich-Hub"

---

## Kern-Entscheidung: Kein separater Wizard

Der bisherige 5-Schritt-Wizard (`screen-compare-wizard.jsx`) ist **gelöscht**.
Anlegen und Bearbeiten nutzen jetzt dieselbe Tab-Struktur — identisch zum Trip-Muster
(`screen-trip-new-v2.jsx` / `screen-trip-edit-v2-main.jsx`).

| Wizard-Schritt (alt) | Tab (neu) |
|---|---|
| Schritt 1 · Vergleich benennen | → **Tab „Vergleich"** (Name + Region + Profil) |
| Schritt 2 · Orte sammeln | → **Tab „Orte"** (Bibliothek + Smart-Import) |
| Schritt 3 · Idealwerte | → **Tab „Idealwerte"** (Range-Slider je Metrik) |
| Schritt 4 · Layout | → **Tab „Layout"** (Spalten pro Kanal + Vorschau) |
| Schritt 5 · Versand | → **Tab „Versand"** (Kanäle + Aktivierung) |

---

## Tab-Struktur (5 Tabs, alle Pflicht)

| # | Tab-ID | Label | Lock-Bedingung | Freischalten auslöst |
|---|---|---|---|---|
| 1 | `vergleich` | Vergleich | – immer offen | Tab 2 wenn Name ≠ leer |
| 2 | `orte` | Orte | Name eingegeben | Tab 3 wenn ≥ 2 Orte |
| 3 | `idealwerte` | Idealwerte | ≥ 2 Orte gewählt | Tab 4 beim ersten Öffnen |
| 4 | `layout` | Layout | Idealwerte-Tab besucht | Tab 5 beim ersten Öffnen |
| 5 | `versand` | Versand | Layout-Tab besucht | „Briefing aktivieren" aktiv |

---

## Modi

### Create-Modus (`mode="create"`)
- Tabs schalten sequenziell frei (identisch `ScreenTripNewV2`)
- Fortschrittsbalken: 5 Segmente
- Breadcrumb: `Orts-Vergleiche / Neuer Vergleich`
- Aktions-Button: „Briefing aktivieren" — **disabled** bis Versand-Tab besucht
- Jeder Tab hat einen eigenen Weiter-Button (floating auf Mobile, Footer auf Desktop)

### Edit-Modus (`mode="edit"`)
- Alle Tabs sofort frei — kein Lock, kein Progress-Bar
- Breadcrumb: `Orts-Vergleiche / [Name]` + Status-Dot (aktiv · pausiert)
- Aktions-Buttons: „Speichern" + „Verwerfen"
- „Ungespeichert"-Pill erscheint bei Änderungen (Desktop) / Speichern-Button leuchtet orange (Mobile)

---

## Soll-Screenshots

### Desktop — Neu anlegen (Tab 1 · Leer-Zustand)
![Desktop Neu Tab 1](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-compare-new-tab1-empty.png)

### Desktop — Neu anlegen (Tab 2 · Orte)
![Desktop Neu Tab 2](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-compare-new-tab2-orte.png)

### Desktop — Bearbeiten (Tab 3 · Idealwerte, Direkt-Sprung)
![Desktop Edit Tab 3](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-compare-edit-tab3-idealwerte.png)

### Mobile — Neu anlegen (Tab 1 · Leer)
![Mobile Neu Tab 1](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-compare-mobile-new-tab1.png)

### Mobile — Neu anlegen (Tab 5 · Versand)
![Mobile Neu Tab 5](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-compare-mobile-new-tab5.png)

---

## Tab 1 — Vergleich

Felder:
- **Name des Vergleichs** (Pflicht) — Freitext, max 80 Zeichen; erscheint im Mail-Betreff
- **Region** (optional) — Freitext, max 60 Zeichen
- **Aktivitätsprofil** — Radio-Kacheln: `wintersport` · `wintersport-glacier` · `alpine-touring` · `hiking` · `trail-running`

Lock-Trigger für Tab 2: `name.trim().length > 0`

Desktop: „Orte hinzufügen →"-Button am Tab-Ende  
Mobile: Floating-CTA am Bildschirm-Boden

---

## Tab 2 — Orte

Ziel: 3–5 Kandidaten auswählen (min. 2 für Lock-Freigabe Tab 3).

**Desktop** — zweispaltig:
- Links: Smart-Import (URL aus Komoot/Google Maps oder Koordinaten → Name + Elev + Gruppe erkannt)
- Rechts: Picked-List (nummerierte Karten, ✕ zum Entfernen)
- Unten: Bibliotheks-Grid (Checkboxen, gruppiert nach Region)

**Mobile** — sequenziell:
- Picked-List oben
- „Ort aus Bibliothek wählen" → Bottom-Sheet mit vollständiger Bibliothek (Checkboxen)
- Smart-Import als separate Zeile (vereinfacht)

Lock-Trigger für Tab 3: `pickedIds.length >= 2`

---

## Tab 3 — Idealwerte

Was bedeutet „gut" für jede Metrik → bestimmt den täglichen Score.

Pro Metrik eine Zeile:
| Spalte | Inhalt |
|---|---|
| Label | Metrik-Name + Notiz (kursiv, klein) |
| Range-Slider | Doppel-Knob auf Skala (Start + End) — interaktiv |
| Ideal-Text | kompakte Beschreibung rechts (z. B. „≥ 80 cm") |
| Löschen | × |

Header: Profil-Label + Anzahl Metriken + „＋ Metrik hinzufügen"-Button

**Defaults per Profil** (aus `CE_IDEALS` / `CEM_IDEALS` — im Mockup-Code vollständig):

| Profil-ID | Metriken |
|---|---|
| `wintersport` | Schneehöhe · Neuschnee 24h · Wind · Temperatur gef. · Niederschlag · Sichtweite |
| `alpine-touring` | Wind · Lawinenstufe · Sichtweite · Sonnenstunden |
| `hiking` | Niederschlag · Wind · Gewitter-Risiko · Temperatur |
| `trail-running` | Temperatur · UV-Index · Niederschlag |
| `wintersport-glacier` | Schneehöhe · Wind · Temperatur gef. · 0°-Linie |

Lock-Trigger für Tab 4: Tab wurde geöffnet (`idealsVis = true`)

---

## Tab 4 — Layout

Welche Spalten landen im täglichen Briefing, **pro Kanal unterschiedlich**.

Struktur:
- Kanal-Wahl: drei Buttons Email / Telegram / SMS (Constraint-Hinweis je Button)
- Spalten-Liste: Drag-Sort + Toggle-Switch + Pinned-Marker für Score
- Überfluss-Spalten: Orange-Pill `↳ Detail` wenn Kanal-Limit überschritten
- Desktop-Rechts: Live-Vorschau der Tabelle (Empfehlung + Vergleichs-Tabelle oder SMS-Fließtext)

**Kanal-Constraints:**

| Kanal | Max Spalten | Tabellen-Format |
|---|---|---|
| Email | ∞ | Vollständige Tabelle + Detail-Block je Ort |
| Telegram | 8 | Monospace-Tabelle (engster Kanal — bestimmt Spalten-Reihenfolge) |
| SMS | 0 | Kein Tabellen-Layout — Fließtext ≤ 140 Zeichen |

Lock-Trigger für Tab 5: Tab wurde geöffnet (`layoutVis = true`)

---

## Tab 5 — Versand

Einstellungen:
- **Versandzeit** (klickbare Kacheln): Uhrzeit · Bewertungs-Zeitfenster · Forecast-Horizont
- **Kanal-Zeilen** mit Switch je Kanal (Email · Telegram · SMS)

Create-Abschluss-Banner (wenn `versandVis = true`):
- Dunkel-Banner (desktop) / Grün-Banner (nach Aktivierung)
- Text: „Die Webseite musst du im Urlaub nicht öffnen — alles kommt automatisch in dein Postfach."

Desktop: „Briefing aktivieren"-Button in Breadcrumb-Zeile aktiv  
Mobile: TopAppBar-„Aktivieren"-Button aktiv

---

## Progressive Lock-State

```
Zustand A (Leer):
  vergleich ← aktiv
  orte ⊘ | idealwerte ⊘ | layout ⊘ | versand ⊘

Zustand B (Name eingegeben):
  vergleich ✓ | orte ← aktiv
  idealwerte ⊘ | layout ⊘ | versand ⊘

Zustand C (≥ 2 Orte gewählt):
  vergleich ✓ | orte ✓ | idealwerte ← aktiv
  layout ⊘ | versand ⊘

Zustand D (Idealwerte-Tab besucht):
  vergleich ✓ | orte ✓ | idealwerte ✓ | layout ← aktiv
  versand ⊘

Zustand E (Layout-Tab besucht):
  Alle Tabs ✓ | „Briefing aktivieren" aktiv
```

Edit-Modus: Alle Tabs immer offen, kein Progress-Bar, kein Lock.

---

## Kanal-Constraints (Referenz CLAUDE.md)

- **Email**: ∞ Spalten
- **Telegram**: max 8 — engster Tabellen-Kanal, Spalten-Reihenfolge entscheidend
- **SMS**: 0 Spalten — Fließtext, ≤ 140 Zeichen

Signal ist **kein Kanal mehr** (entfernt 2026-06-05).

---

## Constraints

| ID | Constraint |
|---|---|
| C1 | Kein separater Wizard. `screen-compare-wizard.jsx` ist gelöscht (2026-06-09). |
| C2 | Create + Edit nutzen dieselbe Tab-Struktur — nur Lock-State und Footer unterscheiden sich. |
| C3 | Edit-Modus: alle Tabs immer frei, kein Fortschrittsbalken. |
| C4 | Tab 3 (Idealwerte) öffnet mit Defaults für das gewählte Aktivitätsprofil aus Tab 1. |
| C5 | Layout-Tab: Spalten-Reihenfolge gilt pro Kanal separat. |
| C6 | Telegram ist der engste Kanal (max 8) — seine Spalten-Reihenfolge muss zuerst optimiert werden. |
| C7 | SMS hat kein Tabellen-Layout — alle Spalten-Einstellungen werden zu Fließtext-Tokens. |
| C8 | Mobile: Floating-CTA am Boden bei jedem Tab (Create-Modus). |
| C9 | Mobile: Bibliothek als Bottom-Sheet (`snap="full"`), nicht Inline. |
| C10 | Fortschrittsbalken: 5 Segmente (alle Tabs sind Pflicht — kein optionaler Tab). |

---

## Acceptance Criteria

- [ ] Create-Modus: Tab 2 gesperrt bis Name eingegeben
- [ ] Create-Modus: Tab 3 gesperrt bis ≥ 2 Orte gewählt
- [ ] Create-Modus: Tab 4 gesperrt bis Idealwerte-Tab geöffnet
- [ ] Create-Modus: Tab 5 gesperrt bis Layout-Tab geöffnet
- [ ] Create-Modus: „Briefing aktivieren" disabled bis Versand-Tab besucht
- [ ] Edit-Modus: alle Tabs sofort frei, kein Progress-Bar
- [ ] Edit-Modus: „Speichern" + „Verwerfen" in Breadcrumb (Desktop) / TopAppBar (Mobile)
- [ ] Edit-Modus: „Ungespeichert"-Indikator bei Änderungen
- [ ] Tab Orte: min. 2 Orte → Tab 3 freischalten; Warnung wenn < 2
- [ ] Tab Layout: Telegram-Überschuss-Spalten mit `↳ Detail`-Pill markiert
- [ ] Desktop: Live-Vorschau im Layout-Tab (Email-Tabelle / Telegram-Tabelle / SMS-Fließtext)
- [ ] Mobile: Orte-Bibliothek als Bottom-Sheet
- [ ] Mobile: Lock-Hint als Toast (2 s, dann ausblenden)
- [ ] `screen-compare-wizard.jsx` existiert nicht mehr im Repo

---

## Migration / Abgrenzung

- **`screen-compare-wizard.jsx`** → gelöscht (Design-Side 2026-06-09); Backend muss keine separate Wizard-Route mehr bedienen
- **#10** (Ortsvergleich-Wizard) → Tab-Editor-Spec ersetzt die Wizard-Spec; #10 auf „won't implement as separate wizard" setzen
- **`ScreenCompareDetail`** bleibt der read-only Hub nach dem Setup (6 Tabs: Übersicht · Orte · Idealwerte · Layout · Versand · Vorschau) — der Editor ist der Bearbeitungs-Einstieg

---

## Out of Scope

1. **Echtes Smart-Import-Backend** — URL-Parsing + Koordinaten-Auflösung (Backend-Aufgabe; UI zeigt Mock-Erkennung)
2. **Drag-Sort persistieren** — Spalten-Reihenfolge in DB speichern; UI zeigt Reihenfolge, Backend implementiert die Persistenz
3. **Range-Slider-Interaktivität** — Frontend rendert Default-Werte; Drag-Handler kommt in V1.5
4. **Orts-Vergleich-Analyse/History** — kein Analytics-Tab im Editor (bleibt in ScreenCompareDetail · Vorschau)
