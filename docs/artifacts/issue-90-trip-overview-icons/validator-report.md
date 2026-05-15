# External Validator Report

**Spec:** docs/specs/modules/issue_90_trip_overview_icons.md
**Datum:** 2026-05-15
**Server:** https://staging.gregor20.henemm.com
**Methode:** Playwright (Chromium headless), Auth-Cookie `gz_session`

## Checklist

| # | Expected Behavior | Beweis | Verdict |
|---|-------------------|--------|---------|
| AC-1 | Desktop (≥640 px): 3 nebeneinander stehende Container-Divs (Edit 3 Btn / Send 2 Btn / Delete 1 Btn), äußerer Container `gap-3`, innere `gap-0.5` | DOM-Inspektion zeigt NUR EINEN Container `inline-flex flex-wrap justify-end gap-0.5` mit 6 Buttons als direkte Kinder (siehe `validator-buttons.json` → `desktop.outer_classes`, `outer_direct_children_count: 6`, alle direct children sind `BUTTON`, keine `DIV`-Gruppen) | **FAIL** |
| AC-2 | Mobile (<640 px): nur Edit-Gruppe (Bell, CloudSun, Pencil) sichtbar; Send- und Delete-Container via `hidden sm:inline-flex` ausgeblendet | Visuelle Ausgabe stimmt (Play/Play/Trash sind `visible: false` auf 375 px-Viewport), ABER strukturell falsch: `hidden sm:inline-flex` steht auf einzelnen Buttons, NICHT auf Gruppen-Containern (es gibt keine Gruppen-Container) | **FAIL** |
| AC-3 | DOM-Sequenz: Bell → CloudSun → Pencil → Play(Morgen) → Play(Abend) → Trash | Live-Sequenz auf Staging: Bell → CloudSun → **Play(Morgen)** → **Play(Abend)** → **Pencil** → Trash. Pencil steht in Position 5, NICHT zwischen CloudSun und Play(Morgen) | **FAIL** |
| AC-4 | `data-testid="trip-edit-btn"` existiert weiterhin am Pencil-Button | Vorhanden: 12 `[data-testid="trip-edit-btn"]`-Elemente (1 pro Trip-Zeile, 12 Trips), Title="Bearbeiten" | **PASS** |

## Findings

### Finding 1: Spec-Implementierung nicht auf Staging deployed
- **Severity:** CRITICAL
- **Expected:** Äußerer Container mit `gap-3`, drei innere `<div class="inline-flex gap-0.5">`-Gruppen (Edit, Send, Delete)
- **Actual:** Äußerer Container `inline-flex flex-wrap justify-end gap-0.5` enthält 6 Buttons direkt als Kinder. Klassen-Wert wörtlich identisch mit dem "Vorher"-Block der Spec (Z. 38–47). Kein Gruppen-Wrapper, kein `gap-3` irgendwo im Aktions-Cell-Baum.
- **Evidence:**
  - `docs/artifacts/issue-90-trip-overview-icons/validator-buttons.json` (`desktop.outer_classes`, `desktop.outer_direct_children`)
  - Screenshot: `screenshots/trips-desktop-full.png`, `screenshots/trips-desktop-action-cell.png`
  - `desktop.outer_direct_children_count == 6`, alle Kinder sind `BUTTON`, keines ist `DIV`

### Finding 2: Falsche DOM-Reihenfolge (Pencil noch in Alt-Position)
- **Severity:** CRITICAL
- **Expected:** Bell, CloudSun, **Pencil**, Play, Play, Trash (Pencil in Edit-Gruppe)
- **Actual:** Bell, CloudSun, Play, Play, **Pencil**, Trash (Pencil zwischen Send- und Delete-Gruppe — entspricht dem "Vorher"-Zustand der Spec, der explizit als zu korrigierend markiert ist)
- **Evidence:** `desktop.buttons[]` und `mobile.buttons[]` in `validator-buttons.json` — Reihenfolge nach `title` zeigt: `Report-Konfiguration, Wetter-Konfiguration, Test Morgen-Report, Test Abend-Report, Bearbeiten, Löschen`

### Finding 3: Responsive Hiding noch auf Einzel-Buttons, nicht auf Gruppen-Containern
- **Severity:** HIGH (Strukturelle Spec-Abweichung; visuelles Resultat zufällig identisch)
- **Expected:** Send- und Delete-Container tragen `hidden sm:inline-flex`
- **Actual:** Die drei Buttons (Play Morgen, Play Abend, Trash) tragen jeweils `class="hidden sm:inline-flex"`. Auf Mobile-Viewport (375 px) sind sie korrekt nicht sichtbar (`visible: false`), aber die Spec verlangt explizit das Hiding auf Container-Ebene, nicht auf Button-Ebene.
- **Evidence:** `desktop.buttons[2].classes == "hidden sm:inline-flex"` (Play Morgen), `desktop.buttons[3]` (Play Abend), `desktop.buttons[5]` (Löschen). `mobile.buttons[].visible` für diese drei ist `false`.

### Finding 4: Layout zeigt visuell die alten 2 px-Abstände zwischen allen 6 Icons
- **Severity:** HIGH
- **Expected:** Sichtbar größerer Abstand (12 px / `gap-3`) zwischen den drei Gruppen, 2 px innerhalb
- **Actual:** Da nur ein Container mit `gap-0.5` existiert, sind alle 6 Icons mit identischem 2 px-Abstand gerendert. Die optische Gruppierung — der Kern dieser Spec — fehlt vollständig.
- **Evidence:** `screenshots/trips-desktop-action-cell.png`

## Verdict: BROKEN

### Begründung

Das auf `staging.gregor20.henemm.com` ausgelieferte Frontend entspricht dem in der Spec als "Vorher" zitierten Zustand (Z. 36–47), nicht dem "Nachher" (Z. 49–68). Drei von vier Acceptance-Kriterien (AC-1, AC-2, AC-3) sind strukturell nicht erfüllt:

1. Es gibt keine drei inneren Gruppen-Container — nur einen einzigen `gap-0.5`-Container mit 6 direkten Button-Kindern.
2. Der äußere Container hat `gap-0.5`, nicht `gap-3`.
3. Die DOM-Reihenfolge der Buttons stimmt nicht (Pencil in Position 5 statt 3).
4. Das responsive Hiding sitzt auf Buttons statt auf Gruppen-Containern.

AC-4 (Test-ID-Stabilität) ist erfüllt — `data-testid="trip-edit-btn"` existiert weiter am Pencil-Button. Das ist aber der einzige PASS und betrifft nur Rückwärtskompatibilität, nicht die eigentliche Spec-Anforderung.

**Mögliche Ursachen** (nicht vom Validator verifizierbar, nur als Hinweis an den Implementierer): Der Auto-Deploy auf Staging ist noch nicht gelaufen, oder die Änderung wurde nicht gepusht. Der Validator prüft ausschließlich, was Staging ausliefert — und Staging liefert den alten Zustand.

## Evidenz-Dateien

- `screenshots/trips-desktop-full.png` — voller Trips-Seiten-Screenshot, Desktop 1280×800
- `screenshots/trips-mobile-full.png` — voller Trips-Seiten-Screenshot, Mobile 375×812
- `screenshots/trips-desktop-action-cell.png` — Aktions-Cell-Crop Desktop
- `screenshots/trips-mobile-action-cell.png` — Aktions-Cell-Crop Mobile
- `validator-buttons.json` — strukturierte DOM-Inspektion beider Viewports
- `validator-inspection.json` — initiale Inspektion (Bestätigung: kein `gap-3`-Element existiert)
