# Klärung: Welche LocationNew-Modal-Variante ist die Wahrheit?

**Status:** offen, blockt Issue #588 (Sub-Issue Epic #575 Design-Fidelity)
**Datum:** 2026-06-05

## Problem

Bei der 1:1-Übernahme des LocationNew-Modals stellt sich heraus, dass die JSX-Vorlage `claude-code-handoff/current/jsx/screen-location-new.jsx` und das SOLL-Screenshot `claude-code-handoff/current/soll/M-location-new.png` **zwei fundamental verschiedene Modal-Designs** zeigen.

## Variante A — JSX-Vorlage (aktuell live, Implementation 1:1)

Datei: `claude-code-handoff/current/jsx/screen-location-new.jsx`
Implementation: `frontend/src/lib/components/compare/LocationNewModal.svelte`

- **Konzept:** Smart-Import-Modal für POI/Wegpunkte
- **Header:** „MODUL 1 · LOCATION ANLEGEN" / „Neuer Ort"
- **Beschreibung:** „Importiere aus Komoot, Google Maps, oder gib Koordinaten direkt ein."
- **Sektion 1: Verortung · Smart-Import**
  - Großes Eingabefeld für URLs/Koordinaten
  - 6 Format-Chips: **Komoot-URL · Google Maps · DMS-Koordinaten · Dezimal · UTM · GPX-Wegpunkt**
- **Erkannt-Vorschau Card:** Quelle, Koordinaten, Höhe (DEM), Zeitzone, Daten-Quelle, Land/Region
- **Mini-Map** (Vorschau-Anzeige des erkannten Ortes)

## Variante B — SOLL-PNG (`M-location-new.png`)

- **Konzept:** Karte+Formular-Modal für strukturierte Orts-Anlage
- **Header:** „ORTS-VERGLEICH · NEUER ORT" / „Ort auf Karte anklicken oder Adresse eingeben"
- **Layout:** **Karte links** (interaktiv, mit Pin) + **Formular rechts**
- **Formularfelder:**
  - Ortsname: „Hintertuxer Gletscher"
  - Gruppe: „Skigebiete Tirol"
  - Aktivitätsprofil: „Wintersport"
  - Wetter-Template: „Skitouren (Basis)"
- **Buttons unten:** „Abbrechen" + „Speichern & weiter" (primär)

## Auswirkungen

- **Diff-Tool** (`.claude/hooks/design_fidelity_diff.py`) zeigt **62,95 % Pixel-Diff** zwischen IST (Variante A) und SOLL-PNG (Variante B). Das ist kein Implementierungs-Drift, sondern Konflikt der Quellen.
- Pilot-Regel aus #575/#583: *„JSX gewinnt bei Konflikt."* Konsequent angewandt wäre Variante A korrekt — aber dann ist das SOLL-PNG falsch und sollte aktualisiert werden.
- Variante B würde **kompletten Neubau** des Modals bedeuten (Smart-Import fällt weg oder wird Sekundär-Tab).

## Bitte um Entscheidung

Welche Variante ist die Wahrheit?

- [ ] **A — Smart-Import-Modal bleibt** (JSX-konform). SOLL-PNG `M-location-new.png` aktualisieren, sodass es der JSX entspricht. → #588 kann als „1:1 erfüllt" geschlossen werden.
- [ ] **B — Karte+Formular-Modal** wird die neue Wahrheit. JSX `screen-location-new.jsx` aktualisieren, sodass es der SOLL-Variante entspricht. → #588 wird zur Implementierung der neuen Variante mit komplettem Modal-Neubau.
- [ ] **C — Beides nebeneinander** (Tabs/Sektionen): Smart-Import + Karte+Formular als zwei Modi. JSX müsste entsprechend erweitert werden.

## Bezug

- Issue #588 (Sub-Issue Epic #575)
- Diff-Tool-Befund: `docs/artifacts/issue-588-locationnew-1to1/design-diff-M-location-new.json`
- Pilot-Erkenntnis aus #583 zum Umgang mit SOLL ≠ JSX
