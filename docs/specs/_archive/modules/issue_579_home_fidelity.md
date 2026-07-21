# Spec: #579 Home-Screen Design-Fidelity — Drift-Korrektur (Epic #575)

- **created:** 2026-06-07
- **issue:** #579 (wiedereröffnet, Epic #575)
- **scope:** frontend-only + Gate-Dokumentation (`.claude/hooks/design_fidelity_diff.py`)
- **bindende Quelle:** `claude-code-handoff/current/jsx/screen-home.jsx`

## Kontext

Die Home-Seite ist strukturell migriert (live d586dd56). Die Wiedereröffnung verlangt
Pixel-Diff < 10 % gegen die SOLL-Bilder. Baseline 2026-06-07: trip 13,82 % / compare
14,40 % / planning 13,29 %.

Zwei Anteile sind zu trennen:

- **Echte, datenunabhängige Drift gegen die JSX** → wird in dieser Spec gefixt.
- **Nicht auf < 10 % bringbarer Rest** (veraltetes SOLL zeigt den per #610 entfernten
  Signal-Kanal; Staging-Konto ist Single-State/dünn; 3 Modi teilen die URL `/`) → wird
  **dokumentiert** im Threshold-Map hinterlegt, nicht maskiert. PO-Entscheidung
  2026-06-07: Vorgehen „wie Schwester-Issues" (#486/#582/#583).

### Bewusste Ausschlüsse (dokumentierte Divergenz, kein Fix)

- **Hero-Untertitel „· Vorhersage {horizon}":** `ComparePreset` hat **kein** Horizont-Feld;
  `sub.horizon` ist reine Mock-Angabe ohne Datenquelle. Kein Erfinden von Fake-Daten
  (Projekt-Regel), kein Backend-Aufbau für ein nicht existierendes Produktkonzept.
- **Planning-Modus 1:1** (`screen-home-planning.jsx`): eigener, reicher Screen, live nicht
  messbar (Konto ist Compare-Modus). Eigene Migration → Folge-Issue, falls Drift bestätigt.

## Acceptance Criteria

**AC-1:** Given die Home-Seite im **Compare-Modus** (aktiver Vergleich, kein Live-Trip),
When der Nutzer zum unteren Seitenbereich scrollt, Then erscheint die „Einrichten"-Sektion
mit Eyebrow „Einrichten", Titel „Kein Trip geplant", Kicker „Sobald ein Mehrtages-Trip
ansteht, übernimmt er das Cockpit" und rechts einem **primary** Button „Neuer Trip"
(href `/trips/new`) — exakt wie `screen-home.jsx` Zeilen 340–347. Die bisherige generische
„Archiv / Frühere Trips"-Sektion erscheint im Compare-Modus **nicht**.

**AC-2:** Given die Home-Seite im **Trip-Modus**, When die Archiv-/Einrichten-Sektion
rendert, Then trägt sie den Eyebrow „Einrichten" (nicht „Archiv") und den Titel „Frühere
Trips" mit rechts einem **quiet** Button „Alle anzeigen" — wie `screen-home.jsx` Zeile 326.

**AC-3:** Given vorhandene abgeschlossene Trips, When die „Einrichten"-Sektion (Trip- oder
Compare-Modus) rendert, Then zeigt sie bis zu 4 Archiv-Karten im 4-Spalten-Grid mit
Datum (mono, uppercase), Name (15 px, fett) und „{N} Etappen" — Aufbau wie
`screen-home.jsx` Zeilen 327–337. Sind keine abgeschlossenen Trips vorhanden, bleibt im
Compare-Modus der Sektions-Kopf (AC-1) trotzdem sichtbar (Empty-Trip-Hinweis).

**AC-4:** Given die gefixte Home-Seite auf Staging, When der `staging-validator` den
Compare-Modus (Apfel-mit-Apfel) gegen `screen-home.jsx mode="compare"` prüft, Then ist das
Layout 1:1 bestätigt: Hero-Karte (Pill+Profil, Titel, Region·Orte, Zeitplan/Nächster-
Versand-Grid, Kanäle-Footer + „Vergleich öffnen →"), Outbox-Card, Alerts-Card,
Schnellaktionen-Strecke (5 Compare-Aktionen) und die „Einrichten/Kein Trip geplant"-Sektion
stehen in Reihenfolge und Struktur wie in der JSX.

**AC-5:** Given das Gate-Tool `design_fidelity_diff.py`, When es nach dem Fix für
`D-home-trip`, `D-home-compare`, `D-home-planning` läuft, Then enthält
`SCREEN_THRESHOLD_MAP` für alle drei einen **dokumentierten** Override (mit Kommentar:
veraltetes SOLL durch Signal-Entfernung #610 + Daten-/Single-State-Divergenz + Layout 1:1
via staging-validator bestätigt). Der Override liegt knapp über dem real gemessenen
Post-Fix-Diff (Ziel-Korridor ≤ 30 %, konsistent mit #486/#582/#583); der temporäre
#578-Override 20 % auf `D-home-trip` wird durch diesen dokumentierten Wert ersetzt.

## Betroffene Dateien

- `frontend/src/routes/+page.svelte` — Compare-Empty-State, Eyebrow-Naming, Sektions-Routing
- `.claude/hooks/design_fidelity_diff.py` — `SCREEN_THRESHOLD_MAP` Doku-Override

## Verifikation

- frontend-only → `staging-validator` prüft Compare-Modus-Layout 1:1 (AC-1…AC-4)
- Gate: `design_fidelity_diff.py --screen D-home-{trip,compare,planning}` → `passed:true`
  gegen dokumentierten Override (AC-5)
- LoC-Erwartung: < 80 (klein, presentational)
