<!-- gregor-zwanzig-handoff: stable_id=trip-new-progressive-editor -->
# Issue #24 · Neue Tour anlegen — Progressive Tab Editor (kein separater Wizard)

**Type:** Design-Compliance · Frontend · UX-Re-Strukturierung  
**Priority:** High — ersetzt den bisherigen Wizard (`screen-trip-wizard.jsx`) als Onboarding-Pfad  
**Baut auf:** #20 (Kanonische Navigations-Architektur), #407/#422 (Wizard-Spec), #503 (Etappen & Wegpunkte)

**Design Reference:**
- Mockup: `Gregor 20 - Trip anlegen.html` (im Projekt-Root, Preset-Switcher unten rechts)
- Komponente: `screen-trip-new-v2.jsx`
- Wegpunkt-Editor eingebettet: `screen-waypoint-editor.jsx` (embedded=true)

---

## Kern-Entscheidung: Kein separater Wizard

Der bisherige 5-Schritt-Wizard (`screen-trip-wizard.jsx`) wird **nicht** als
eigenständiger Flow implementiert. Stattdessen nutzt „Neue Tour anlegen"
**dieselbe Tab-Struktur** wie Trip bearbeiten — mit sequenziellem Lock-State.

| Wizard Step (alt) | Was es wirklich ist |
|---|---|
| Step 1 Route | → neuer **Route-Tab** (Name + Region + **Startdatum**) |
| Step 2 Etappen | → **Etappen & GPX-Tab** (GPX je Etappe, editierbare Namen, Auto-Datum) |
| Step 2½ Wegpunkte | → **Wegpunkte-Tab** (optional, `ScreenWaypointEditor embedded`) |
| Step 3+4 Wetter+Layout | → **Wetter-Metriken-Tab** `WetterMetrikenTabV2` (bereits gebaut) |
| Step 5 Reports | → **Briefing-Zeitplan-Tab** `TE2_ZeitplanTab` (bereits gebaut) |

**Begründung:**
- Wizard-Stepper = Tab-Bar mit Lock-State (strukturell identisch, keine neue Metapher)
- Ein Flow für Anlegen + Bearbeiten = weniger Pflege, kein UI-Lern-Split
- `screen-trip-wizard.jsx` → **deprecated**, kann nach Implementierung gelöscht werden

---

## Tab-Struktur (6 Tabs, einer davon optional)

| # | Tab-ID | Label | Lock-Bedingung | Optional |
|---|---|---|---|---|
| 1 | `route` | Route | – immer offen | nein |
| 2 | `etappen` | Etappen & GPX | Name + Startdatum | nein |
| 3 | `wegpunkte` | Wegpunkte prüfen | alle GPX geladen | **ja** |
| 4 | `wetter` | Wetter-Metriken | alle GPX geladen | nein |
| 5 | `zeitplan` | Briefing-Zeitplan | Wetter-Tab besucht | nein |
| 6 | `alerts` | Alerts | Zeitplan-Tab besucht | nein |

Wegpunkte + Wetter schalten **gleichzeitig** frei (beide nach allen GPX geladen).
Der User kann Wegpunkte überspringen und direkt zu Wetter.

---

## Soll-Screenshots

### Route-Tab (Leer-Zustand)
![Route Tab](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-trip-new-route-tab.png)

### Etappen & GPX-Tab (halb ausgefüllt — 3/5 Namen, 2/5 GPX)
![Etappen Tab](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-trip-new-etappen-tab.png)

### Wegpunkte-Tab (optional, `ScreenWaypointEditor embedded`)
![Wegpunkte Tab](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-trip-new-wegpunkte-tab.png)

---

## Tab 1 — Route

Felder:
- **Tour-Name** (Pflicht) — freies Textfeld, max 100 Zeichen
- **Region** (optional) — freies Textfeld, max 50 Zeichen
- **Startdatum** (Pflicht) — `<input type="date">`, 24h-Format

Verhalten:
- „Etappen anlegen →"-Button disabled bis Name + Startdatum ausgefüllt
- Hinweis-Banner (accent-tint): „GPX lädst du im nächsten Schritt hoch — eine Datei pro Etappe."

---

## Tab 2 — Etappen & GPX

**GPX je Etappe** — kein Gesamt-Trip-GPX mehr. Jede Etappe braucht eine eigene `.gpx`-Datei.

Tabellen-Layout pro Etappen-Zeile:

| Spalte | Inhalt |
|---|---|
| T-Badge | T01, T02, … (accent-tint) |
| Etappenname | Inline-Input (ghost-Stil, Akzent-Rahmen bei Fokus) |
| Datum | Auto-berechnet: Startdatum + Index (read-only, Mono) |
| GPX-Slot | Leer: dashed Pill „GPX hochladen" · Geladen: grüner ✓-Badge + Dateiname + km/↑-Stats |
| Löschen | × |

**Datum-Kalkulation:**
```
etappeDate(i) = startDate + i Tage
```
Datum ist nicht editierbar in diesem Tab (Änderung → Tab Etappen & Wegpunkte im Edit-Flow).

**Footer-Buttons:**
- Alle GPX geladen: zwei Buttons: „Wetter direkt →" (ghost) + „Wegpunkte prüfen →" (accent)
- Noch GPX fehlend: nur ein disabled Button + Hinweis-Zeile

**Lock-Trigger für Wetter + Wegpunkte:** `alle Etappen haben GPX-Datei`

---

## Tab 3 — Wegpunkte prüfen (optional)

Rendert `<ScreenWaypointEditor embedded={true}/>` aus `screen-waypoint-editor.jsx`.

Wrapper-Aufbau:
1. **Info-Banner** (oben, card-bg):
   - Text: „Wegpunkte aus GPX berechnet — optional prüfen. Wegpunkte sind Wetterscheiden …"
   - Buttons: „Überspringen →" (ghost) + „Wegpunkte übernehmen →" (accent)
2. **Embedded Waypoint Editor** (volle Breite, alle Features des bestehenden Editors)
3. **Footer** (unten, card-bg): erneut „Überspringen" + „Wegpunkte übernehmen →"

Tab-Label: „Wegpunkte prüfen" + `OPTIONAL`-Pill (accent-tint, Mono, uppercase, 9px)

Beide Buttons führen zu Tab 4 (Wetter-Metriken) — kein Unterschied im Ergebnis für diesen Sprint.

---

## Tabs 4–6 — Wiederverwendete Komponenten

| Tab | Svelte-Pendant zu |
|---|---|
| Wetter-Metriken | `screen-trip-edit-v2-weather.jsx` → `WetterMetrikenTabV2` |
| Briefing-Zeitplan | `screen-trip-edit-v2-main.jsx` → `TE2_ZeitplanTab` |
| Alerts | `screen-trip-edit-v2-main.jsx` → `TE2_AlertsTab` |

Diese Tabs sind im Edit-Flow bereits implementiert — im Create-Flow werden **dieselben Komponenten** verwendet, nicht separate Kopien.

---

## Hero + Breadcrumb

**Breadcrumb:** `Trips / Neue Tour`  
**Hero-Titel:** live aktualisiert aus Tour-Name-Feld (grau = „Noch kein Name" bis Eingabe)  
**Fortschrittsbalken:** 4 Segmente (Route · Etappen · Wetter · Zeitplan) — Wegpunkte zählt als optional nicht mit  
**„Tour speichern"-Button:** disabled bis Zeitplan-Tab besucht

---

## Progressiver Lock-State

```
Zustand A (Leer):
  Route ← aktiv
  Etappen ⊘ | Wegpunkte ⊘ | Wetter ⊘ | Zeitplan ⊘ | Alerts ⊘

Zustand B (Name + Datum eingetragen):
  Route ✓ | Etappen ← aktiv
  Wegpunkte ⊘ | Wetter ⊘ | Zeitplan ⊘ | Alerts ⊘

Zustand C (alle GPX geladen):
  Route ✓ | Etappen ✓
  Wegpunkte [OPTIONAL] ← aktiv ODER Wetter ← aktiv (beide offen)
  Zeitplan ⊘ | Alerts ⊘

Zustand D (Wetter-Tab besucht):
  Route ✓ | Etappen ✓ | Wetter ✓ | Zeitplan ← aktiv
  Alerts ⊘

Zustand E (Zeitplan-Tab besucht):
  Alle Pflicht-Tabs ✓ | „Tour speichern" aktiv
```

---

## Kanal-Weitergabe

`WetterMetrikenTabV2` gibt aktive Kanäle via `onChannelsChange` zurück.  
`TE2_ZeitplanTab` empfängt `channels`-Prop.  
`TE2_AlertsTab` empfängt `defaultChannels`-Prop.  
→ Identisch zum Edit-Flow.

---

## Constraints

| ID | Constraint |
|---|---|
| C1 | Kein separater Wizard-Flow. `screen-trip-wizard.jsx` deprecated nach Implementierung. |
| C2 | GPX ist **je Etappe** — kein Gesamt-Trip-GPX mehr. |
| C3 | Startdatum im Route-Tab gesetzt → Etappen-Daten auto-berechnet, nicht editierbar im Create-Flow. |
| C4 | Wegpunkte-Tab ist optional — Wetter schaltet auch ohne Wegpunkte-Besuch frei. |
| C5 | Wegpunkte-Tab nutzt `ScreenWaypointEditor` mit `embedded=true` — kein eigener Karten-Code. |
| C6 | Tabs 4–6 (Wetter, Zeitplan, Alerts) sind **dieselben** Svelte-Komponenten wie im Edit-Flow. |
| C7 | Fortschrittsbalken zeigt nur Pflicht-Schritte (4 Segmente, Wegpunkte fehlt). |
| C8 | Tab-Label Wegpunkte trägt `OPTIONAL`-Pill (9px Mono, uppercase, accent-tint). |

---

## Acceptance Criteria

- [ ] Route-Tab: Name (Pflicht), Region (optional), Startdatum (Pflicht, `<input type="date">`)
- [ ] Etappen-Tab: Zeile pro Etappe mit editierbarem Namen, auto-berechnetem Datum, GPX-Slot
- [ ] Etappen-Tab: alle GPX geladen → Bestätigungshinweis + zwei Footer-Buttons
- [ ] Wegpunkte-Tab: Info-Banner + `ScreenWaypointEditor embedded` + Footer
- [ ] Wegpunkte-Tab hat `OPTIONAL`-Pill im Tab-Label
- [ ] Wegpunkte + Wetter schalten gleichzeitig frei (nach allen GPX)
- [ ] Fortschrittsbalken: 4 Segmente (kein Wegpunkte-Segment)
- [ ] Wetter/Zeitplan/Alerts: selbe Svelte-Komponenten wie im Edit-Flow
- [ ] „Tour speichern" erst aktiv nach Zeitplan-Tab-Besuch
- [ ] `screen-trip-wizard.jsx` gelöscht oder als deprecated markiert

---

## Migration / Abgrenzung

- **`screen-trip-wizard.jsx`** → deprecated, nach Go-live löschen
- **#407 / #422** (5-Step-Wizard-Spec) → überholt durch dieses Issue; Close oder als „Won't implement as separate wizard" markieren
- Die 5-Schritt-Logik aus #407/#422 lebt weiter — aber **als Tab-Editor**, nicht als modaler Wizard-Flow

---

## Out of Scope

1. **Mobile-Adaption** des Create-Flows — kommt in V1.5 (analog zu Edit-Flow)
2. **Echtes GPX-Parsen** im Frontend — Backend-Aufgabe; Etappen-Namen aus GPX ableiten
3. **Wegpunkte-Bearbeitung persistieren** — der embedded Editor zeigt den berechneten Stand; Speichern erfolgt über den normalen Trip-Save-Endpunkt
4. **Datum-Kaskaden-Dialog** im Create-Flow — nur im Edit-Flow nötig (StageDateField / StageCascadeNotice)
