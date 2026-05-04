---
workflow: bug-106-mobile-waypoint-row
issue: 106
type: bug
priority: medium
phase: analyse
created: 2026-05-04
---

# Bug #106 — Wegpunkt-Zeile auf Mobile zu eng

## Symptom

Auf Mobile-Viewport (375×667, iPhone SE) ist die Wegpunkt-Eingabezeile in `WizardStep2Stages` zu eng. Werte werden abgeschnitten:
- Name-Feld: „Pun" statt „Punkt 1"
- Lat: „4" statt „47.0"
- Lon: „1" statt „11.0"
- Höhe: „2" statt „2000"

Bug erscheint sowohl im Trip-Wizard (`/trips/new`) als auch im Trip-Edit-Akkordeon (`TripEditView` → „Etappen").

## Root Cause

Datei: `frontend/src/lib/components/wizard/WizardStep2Stages.svelte`, Zeilen 79–111.

Wegpunkt-Zeile mit `flex items-center gap-2` und festen Pixel-Breiten:

| Element | Breite |
|---------|--------|
| Input Name | `w-32` (128px) |
| Input Lat | `w-24` (96px) |
| Input Lon | `w-24` (96px) |
| Input Höhe | `w-24` (96px) |
| Trash-Button | ~32px |
| 4× gap-2 | 32px |
| **Summe** | **~480px** |

Auf 375px Viewport mit Card `p-4` (32px) + `ml-2` (8px) bleiben nur **~335px verfügbar**. Kein Mobile-Breakpoint, kein `flex-wrap` → Werte werden abgeschnitten.

`TripEditView.svelte` Zeile 91 nutzt dieselbe Komponente — ein Fix repariert beide Stellen.

## Fix-Strategie

Mobile-First Layout, Konsistenz mit existierendem Projekt-Pattern (`grid grid-cols-1 sm:grid-cols-3` aus `WizardStep4ReportConfig.svelte:174`):

```
Mobile (< 640px):
+---------------------------+
| Name              [🗑]    |   ← Name + Trash in einer Zeile
+------+--------+-----------+
| Lat  | Lon    | Höhe (m)  |   ← 3 gleichgroße Spalten darunter
+------+--------+-----------+

Desktop (≥ 640px):
+---------+-----+-----+--------+----+
| Name    | Lat | Lon | Höhe   | 🗑 |   ← unverändert wie heute
+---------+-----+-----+--------+----+
```

**Implementierung:** Tailwind-Responsive-Klassen + zwei kleine HTML-Wrapper-Divs + doppelter Trash-Button (`hidden sm:inline-flex` / `sm:hidden`). Keine neue Komponente, kein Struktur-Refactoring.

**Touch-Target Mobile:** Trash-Button auf Mobile mind. 44×44px (Apple HIG).

## Affected Files

| Datei | Änderung |
|---|---|
| `frontend/src/lib/components/wizard/WizardStep2Stages.svelte` | Wegpunkt-Zeile (Zeilen 79–111): responsive Layout |
| `frontend/e2e/trip-wizard.spec.ts` | Neue Mobile-Viewport-Tests (Bug #106) |

**Scope:** 2 Dateien, ~15–18 LoC Komponente + ~30 LoC Test. Im Limit.

## Test-Strategie

**Playwright E2E mit Mobile-Viewport** (375×667, iPhone SE):
1. `/trips/new` → Trip-Name → „Manuell" → Weiter → „+ Wegpunkt"
2. Kein horizontales Page-Overflow (`scrollWidth ≤ clientWidth`)
3. Alle 4 Inputs sichtbar mit `boundingBox().width > 40` (nicht auf 0 gequetscht)
4. Trash-Button auf Mobile ≥ 44×44px (Touch-Target)

Plus manuelle Verifikation: Safari Mobile (Hard-Reload Cmd+Shift+R), Trip-Edit-Akkordeon „Etappen".

Kein Screenshot-Visual-Regression (kein CI-Baseline im Projekt, zu fragil).

## Risiken / Edge Cases

- **Number-Input-Spinner:** Browser-native Spinner in `<input type="number">` können in engen Containern überschießen → ggf. `[appearance:textfield]` ergänzen.
- **`sm:contents`:** Wird laut Plan-Agent nicht gebraucht — stattdessen Wrapper-Div-Ansatz.
- **Viewports < 320px:** Akzeptiert als Edge Case, „Höhe (m)"-Placeholder wird knapp.
- **`ml-2` auf Eltern-Div** (Zeile 76): bleibt unangetastet — 327px Restplatz reichen für 3 Spalten.

## Konsistenz-Check

Plan-Agent hat im Projekt geprüft:

- Mobile-Responsive-Pattern: `grid grid-cols-1 gap-2 sm:grid-cols-3` (verwendet in `WizardStep4ReportConfig`, `WizardStep3Weather`)
- Doppel-Button-Pattern Mobile/Desktop: `hidden sm:inline-flex` (verwendet in `locations/+page.svelte`, `trips/+page.svelte`)
- Kein `flex-wrap` für Formular-Inputs im Projekt — Pattern wird hier ebenfalls gemieden

→ Fix bleibt **konsistent mit etablierten Mustern**, kein neues Pattern.

## Nächster Schritt

`/3-write-spec` — Bugfix-Spec erstellen.
