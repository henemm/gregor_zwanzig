---
entity: issue_583_archiv_1to1
type: feature
status: draft
created: 2026-06-04
issue: 583
epic: 575
---

# Spec: Issue #583 — Archiv-Screen 1:1 nach `screen-archive.jsx`

## Kontext

Issue #583 ist Sub-Issue des Epic #575 (Design-Fidelity Redo). Aktueller Baseline-Diff
gegen SOLL-Screenshot `H-archive.png`: **69,64 %**. Schwelle: **< 10 %** (#603-Gate).

Hauptursachen der Drift (aus Baseline-Screenshot-Vergleich):
1. **Suchfeld-Breite**: JSX `flex: "0 0 380px"` (380 px fix) → Svelte `flex: 1` (volle Breite)
2. **Mock-Daten fehlen**: Validator-Account hat keine Archiv-Trips
3. **`accuracy`-Feld** fehlt im Trip-Modell → AccuracyBar zeigt 0 % statt echter Werte
4. **`headline`-Feld** fehlt → "Was passiert ist"-Spalte zeigt generische Event-Summary

## Scope

Innerhalb Scope:
- Suchfeld-Breite-Fix (Inline-Style aus JSX 1:1)
- Demo-Archiv-Trips auf Validator-Account anlegen mit Mock-`accuracy` + `headline`
- Demo-Daten enthalten 8 Trips wie JSX-Mock `ARCHIVE_LIST`
- Backend-Datei-Schema-Erweiterung: `accuracy_pct` und `headline` optional in `Trip` (Go)
- Frontend liest und rendert die neuen Felder
- Diff < 10 %

Außerhalb Scope (eigene Folge-Issues):
- Echte Forecast-Accuracy-Berechnung (Briefings vs. tatsächliches Wetter) → **Sub-Issue A**
- User-Editor für Trip-Retrospektive (Headline) → **Sub-Issue B**
- Bis dahin: nur Demo-Daten zeigen die Felder.

## Acceptance Criteria

**AC-1:** Given ein Validator-Account ohne archivierte Trips, when ich Demo-Daten anlege,
then enthält das User-Datenverzeichnis 8 archivierte Trips mit `archived_at`,
`accuracy_pct` und `headline` aus dem JSX-Mock (`ARCHIVE_LIST`).

**AC-2:** Given das Trip-Go-Modell, when es ein archiviertes Trip mit `accuracy_pct=92`
und `headline="Gewitter Tag 2 wie prognostiziert"` serialisiert/deserialisiert,
then bleiben beide Felder als optionale JSON-Properties erhalten (Round-Trip).

**AC-3:** Given das Frontend rendert die Archiv-Tabelle mit einem Trip,
der `accuracy_pct=92` hat, when der AccuracyBar gerendert wird,
then zeigt er einen 92 %-breiten farbigen Balken (Ton `good`, weil `>=90`)
und die Zahl `92%` (nicht `—`).

**AC-4:** Given das Frontend rendert die Archiv-Tabelle mit einem Trip,
der `headline="Sonnig wie vorhergesagt"` hat, when die Spalte "Was passiert ist"
gerendert wird, then zeigt sie genau diesen Text (nicht `formatEventSummary(...)`).

**AC-5:** Given das Such-Eingabefeld in `/archiv`, when die Seite gerendert wird,
then hat das umschließende `<div>` `flex: 0 0 380px` (nicht `flex: 1`) — das
Suchfeld nimmt 380 px ein und überlässt den Rest der Sortier-Pill-Leiste.

**AC-6:** Given Validator-Login auf Staging mit Demo-Daten, when
`python3 .claude/hooks/design_fidelity_diff.py --screen H-archive` läuft,
then ist der `diff_pct` < 10 % und das Tool exit-0.

## Backend-Modell-Änderungen

### Go (`internal/model/trip.go`)
```go
type Trip struct {
    // ... bestehende Felder ...
    AccuracyPct  *int    `json:"accuracy_pct,omitempty"`
    Headline     string  `json:"headline,omitempty"`
}
```

Optional + omitempty → existierende Daten bleiben Round-Trip-stabil.

### Python (`src/app/models.py` / `src/app/trip.py`)
Falls Trip-Klasse die Felder nicht passthrough-serialisiert: erweitern um
`accuracy_pct: Optional[int]` und `headline: Optional[str]` mit Defaults `None`.

### Datenformat (Datei-Schema)
Pre-Snapshot via `data_schema_backup.py` (automatisch). Migration nicht nötig:
neue Felder optional, existierende Trips ohne diese Felder bleiben gültig.

## Demo-Daten

Datei: `data/users/<validator-id>/trips/*.json` mit 8 Trips entsprechend der JSX-`ARCHIVE_LIST`:
| ID | Name | Stages | from | to | accuracy_pct | alerts | headline |
|----|------|--------|------|------|--------------|--------|----------|
| ortler-2025 | Ortler-Überquerung | 4 | 2025-09-12 | 2025-09-15 | 92 | 1 | Gewitter Tag 2 wie prognostiziert — Aufstieg vorgezogen |
| zillertal-2025 | Zillertal mit Steffi | 1 | 2025-12-28 | 2025-12-30 | 88 | 0 | Sonnig wie vorhergesagt, leichter Föhn ab Mittag |
| rofan-2025 | Rofan Tageswanderung | 1 | 2025-08-23 | 2025-08-23 | 76 | 1 | Niederschlag 4 h früher als prognostiziert eingetroffen |
| venediger-2024 | Großvenediger Rundtour | 5 | 2024-07-18 | 2024-07-22 | 94 | 0 | Stabile Schönwetter-Phase, Briefings ohne Korrektur |
| stubai-2024 | Stubaier Höhenweg | 8 | 2024-08-30 | 2024-09-06 | 81 | 2 | Kaltlufteinbruch Tag 5 erkannt, Etappe 6 umgeplant |
| khw-402 | KHW 402 | 13 | 2024-05-05 | 2024-05-18 | 86 | 3 | Drei Gewitter-Tage, davon zwei Tage vorher avisiert |
| gardasee-2024 | Gardasee Klettersteige | 3 | 2024-04-19 | 2024-04-21 | 71 | 1 | Wind unterschätzt, Bocchette gesperrt — kurzfristig umgeplant |
| dachstein-2023 | Dachstein Überschreitung | 2 | 2023-09-08 | 2023-09-09 | 95 | 0 | Bilderbuch-Bedingungen — präzise getroffen |

`archived_at` = `to` + 1 Tag.

## Frontend-Änderungen

`frontend/src/routes/archiv/+page.svelte`:
- Such-`<div>`: `style="position:relative;flex:0 0 380px"` (statt `flex:1`)
- `accuracyBar`-Snippet: nimmt `value` + `color` als Parameter (statt fix 0 %)
- "Was passiert ist"-Spalte: rendert `trip.headline` (Fallback auf bestehende Logik wenn leer)
- AccuracyBar-Farblogik: `>=90 = #3d6b3a (good)`, `>=80 = var(--g-ink-2) (ok)`, sonst `#c08a1a (warn)`

## Non-Goals

- Echte Accuracy-Berechnung (kommt als Sub-Issue A)
- Headline-Editor (kommt als Sub-Issue B)
- Sidebar-Aktiv-Marker (ist schon korrekt im Layout)
- Demo-Daten für andere User als Validator
