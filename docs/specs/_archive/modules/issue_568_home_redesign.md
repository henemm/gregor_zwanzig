# Spec: Startseite-Redesign — Cockpit + Planungs-/Leerzustand (#568)

**Issue:** #568  
**Workflow:** issue-568-home-redesign  
**Typ:** feature · design-compliance  
**Areas:** area:home, area:components, area:compare, area:mobile

---

## Überblick

Die Startseite wandelt sich vom Briefing-Reader zum Steuer-Cockpit. Zwei klar
getrennte Zustände ersetzen die bisherige Hero-Kachel mit Etappen-Sparkline +
Pillstreifen.

Produktaussage: **90 % der Nutzung läuft ohne aktiven Trip** — Einrichten vor
dem Trip. Die App liefert Briefings autonom in die Kanäle. Die Webseite ist nur
für Konfiguration und schnelles Eingreifen da.

---

## Zustand A — Cockpit (aktiver Trip vorhanden)

### A1 · Trip-Status-Karte (ersetzt Hero)

- Trip-Name, Live-Pill „Tag X von Y" mit Fortschrittsbalken
  - `dayX`: `(heutigerIndex + 1)`, `dayY`: `heroStages.length`
  - Fortschrittsbalken: `dayX / dayY * 100 %`
- Kanal-Gesundheit: je ein `Dot` pro aktivem Kanal (Email, Signal, SMS etc.)
- **Kein** Etappen-Sparkline, **keine** Etappen-Prosa, **kein** Pillstreifen
- Link „Trip öffnen →" → `/trips/{id}?tab=overview`

### A2 · Schnellaktionen-Reihe (4 QuickAction-Molecules)

| Aktion | Tab-Ziel | glyph |
|---|---|---|
| Pausentag einplanen | `/trips/{id}?tab=stages` | `route` |
| Wetter-Metriken ändern | `/trips/{id}?tab=weather` | `metrics` |
| Briefing-Zeitplan | `/trips/{id}?tab=briefings` | `clock` |
| Vorschau prüfen | `/trips/{id}?tab=preview` | `eye` |

### A3 · Briefing-Zeitplan + Alerts (rechte Spalte, bleibt)

- „Was geht raus" — `BriefingTimelineRow` (unverändert)
- „Alarme · letzte 24 h" — `heroAlerts` (unverändert)

### A4 · Vergleiche + Archiv (unverändert)

- Aktive ComparePresets via `CompareKachel` (nutzt schon `CompareTile` + `CompareKebab`)
- Archiv-Kacheln (unverändert)

---

## Zustand B — Planungs-/Leerzustand (kein aktiver Trip)

### B1 · Ehrlicher Hinweis

Text: „Aktuell läuft kein Trip — Briefings kommen automatisch in die Kanäle,
sobald die nächste Reise startet."

### B2 · SetupResumeCard × 2 (nebeneinander)

Zwei Karten: nächster geplanter Trip + ältester unvollständiger Vergleich
(erster ComparePreset ohne ≥ 1 aktivem Kanal).

**Trip-Schritte** (in Reihenfolge):
1. Route — done wenn `stages.length >= 1`
2. Etappen — done wenn ≥ 1 Stage mit gesetztem `date`
3. Wetter — done wenn `report_config.metrics?.length > 0`
4. Layout — done wenn `report_config.layout_mode` gesetzt (≠ undefined)
5. Reports — done wenn `report_config.morning_enabled || report_config.evening_enabled`

**Vergleich-Schritte** (in Reihenfolge):
1. Vergleich — done immer (Entwurf existiert)
2. Orte — done wenn `locations.length >= 2`
3. Idealwerte — done wenn `ideal_values` nicht leer
4. Layout — done wenn `layout_mode` gesetzt
5. Versand — done wenn ≥ 1 aktiver Kanal

CTA „Setup fortsetzen" springt in den ersten Wizard-Schritt mit `done === false`.

**Trip-Wizard-Schritte → Tab-Query:**
- Step 1 (Route) → `/trips/new` oder `/trips/{id}?tab=stages`
- Step 2 (Etappen) → `/trips/{id}?tab=stages`
- Step 3 (Wetter) → `/trips/{id}?tab=weather`
- Step 4 (Layout) → `/trips/{id}?tab=briefings` (OutputLayoutEditor dort)
- Step 5 (Reports) → `/trips/{id}?tab=briefings`

**Vergleich-Wizard:**
- Step 1–5 → `/compare/{id}/edit?step={1..5}` (oder `/compare/new`)

### B3 · Schnell-anlegen-Zeile

- „+ Neuer Trip" → `/trips/new`
- „+ Neuer Orts-Vergleich" → `/compare` (create flow)

### B4 · Laufende Vergleiche + Archiv (unverändert)

Aktive Vergleiche und Archiv bleiben sichtbar (Vergleiche laufen
Trip-unabhängig weiter).

---

## Neue Molecules

### `QuickAction.svelte`

```
Props:
  glyph: 'pause' | 'metrics' | 'clock' | 'bell' | 'send' | 'eye' | 'route'
  label: string
  sub: string          — Ziel-Sublabel (z.B. "Etappen & Wegpunkte")
  tone?: 'default' | 'accent'
  size?: 'md' | 'lg'   — md = Desktop, lg = Mobile (Touch-Target ≥ 44 px)
  href: string         — Navigations-Ziel (kein onClick, direkter Link)
```

Aufbau: Glyph-Tile (Lucide-Icon oder Emoji-Fallback) + Label + Sub + Chevron.
Kein Lese-Surface. Hover: border-color → `--g-accent`.
Mobile Touch-Target: `min-height: 44px`.

### `SetupResumeCard.svelte`

```
Props:
  eyebrow: string
  title: string
  subtitle?: string
  steps: Array<{ label: string; done: boolean }>
  ctaLabel: string
  ctaHref: string      — springt in ersten offenen Schritt
  secondary?: { label: string; href: string }
  tone?: 'accent' | 'default'
```

Aufbau: Eyebrow + Titel + Schritt-Checkliste (✓ done / ○ offen) +
Fortschrittsbalken (`done / steps.length * 100 %`) + CTA-Button.
`tone='accent'` → Trip (Akzent-Farbe), `tone='default'` → Vergleich.

---

## Betroffene Dateien

| Datei | Änderung |
|---|---|
| `frontend/src/routes/+page.svelte` | Vollständige Überarbeitung (Cockpit A + Planungs-B) |
| `frontend/src/lib/components/molecules/QuickAction.svelte` | NEU |
| `frontend/src/lib/components/molecules/SetupResumeCard.svelte` | NEU |
| `frontend/src/lib/components/molecules/index.ts` | 2 neue Exports |
| `frontend/src/routes/_home/cockpitHelpers.ts` | Neue Helper: `dayProgress`, `setupStepTrip`, `setupStepCompare`, `nextPlannedTrip`, `firstIncompleteCompare` |

**Entfernt aus `+page.svelte`:** `heroStage`, `heroWeatherResult`, `nextStage`,
`nextWeatherResult`, `heroProfile`, `heroRisk`, `heroSummary`, `nextStats`,
`nextProfile`, `nextRisk`, `nextSummary`, `stageProfile`, `stageWindow`,
`stageStats`, `riskTone`, `weatherSummary`, `stageStripState` — und alle
zugehörigen Importe aus `cockpitHelpers.ts`.

**LOC-Override:** 500 (ca. 350–450 LoC netto).

---

## Acceptance Criteria

**AC-1:** Given die Startseite hat einen aktiven Trip, When ich die Seite lade,
Then sehe ich keinen Etappen-Pillstreifen, keine Sparkline und keine
Etappen-Prosa — stattdessen einen Fortschrittsbalken „Tag X von Y" und eine
Schnellaktionen-Reihe mit 4 QuickAction-Links.

**AC-2:** Given ein aktiver Trip mit 12 Etappen läuft seit Tag 3, When ich die
Startseite lade, Then zeigt der Fortschrittsbalken „Tag 3 von 12" und die
Breite entspricht 25 %.

**AC-3:** Given kein aktiver Trip, When ich die Startseite lade, Then sehe ich
den Planungs-/Leerzustand mit einem ehrlichen Hinweis-Text und (falls Daten
vorhanden) zwei SetupResumeCards nebeneinander.

**AC-4:** Given ein geplanter Trip mit 3 von 5 erledigten Setup-Schritten, When
ich auf „Setup fortsetzen" klicke, Then navigiere ich zum ersten nicht-erledigten
Schritt (Schritt 4).

**AC-5:** Given `QuickAction` „Wetter-Metriken ändern" im Cockpit, When ich
darauf klicke, Then navigiere ich zu `/trips/{id}?tab=weather`.

**AC-6:** Given `QuickAction` und `SetupResumeCard`, When ich die
Molecules-Barrel `$lib/components/molecules` importiere, Then sind beide
Komponenten dort verfügbar (kein direkter Pfad-Import nötig).

**AC-7:** Given ein mobiles Viewport (≤ 640 px), When ich die Startseite lade,
Then haben alle QuickAction-Kacheln und SetupResumeCard-CTAs ein
Touch-Target ≥ 44 px.

**AC-8:** Given WCAG-AA-Kontrastanforderung, When Text auf Kacheln gerendert
wird, Then hat fließender Text mindestens 4,5:1 Kontrast (kein `--g-ink-4`
für Fließtext).

---

## Out of Scope

- Reale Wizard-Schritt-Persistenz / Resume-Routing (nur Link-Sprung in Tab)
- „Nächste 48 h Versand-Plan"-Widget
- Kanal-Gesundheits-Endpoint (Dots zeigen aktivierte Kanäle, kein Live-Status)
