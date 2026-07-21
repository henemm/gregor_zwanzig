---
entity_id: issue_680_compare_editor_slice3
type: module
created: 2026-06-09
updated: 2026-06-09
status: draft
version: "1.0"
tags: [frontend, compare, editor, design-compliance, epic-677]
---

# Compare-Editor Slice 3 — Fidelity-Tabs „Orte" + „Idealwerte" (CE_)

## Approval

- [ ] Approved

## Purpose

Bringt die Tab-Inhalte **„Orte"** und **„Idealwerte"** des Compare-Editors (Gerüst aus Slice 1/2,
Epic #677) vollständig auf CE_-Fidelity — **und** verdrahtet alle bisher angedeuteten Funktionen
tatsächlich: nummerierte Picked-Liste mit Entfernen, Region-Gruppierung in der Bibliothek,
Dual-Handle-Slider für Idealwert-Bereiche, freie Metrik-Auswahl (hinzufügen / entfernen) pro
Vergleich mit Persistenz.

> **PO-Direktive (2026-06-09):** „Optisch angedeutet aber nicht funktional" ist nicht akzeptiert.
> Jede sichtbare Funktion muss echt verdrahtet sein. Überschreibt die Issue-Vorgabe „Drag = V1.5".

## Source

- **Datei A (geändert):** `frontend/src/lib/components/compare/steps/Step2Orte.svelte`
- **Datei B (geändert):** `frontend/src/lib/components/compare/steps/Step3Idealwerte.svelte`
- **Datei C (neu):** `frontend/src/lib/components/compare/RangeSlider.svelte`
- **Datei D (geändert):** `frontend/src/lib/components/compare/compareMetricDefs.ts`
- **Datei E (geändert):** `frontend/src/lib/components/compare/compareWizardState.svelte.ts`
- **Datei F (geändert):** `frontend/src/lib/components/compare/compareEditorSave.ts`

> Schicht: **Frontend / User-UI** → `frontend/src/...` (SvelteKit, gregor20.henemm.com).

## Design-Quelle (bindend)

`claude-code-handoff/current/jsx/screen-compare-editor.jsx` —
`CE_OrteTab` (Z. 196–306), `CE_IdealwerteTab` (Z. 309–361), `CE_IDEALS` (Z. 28–60).

## Estimated Scope

- **LoC:** ~550–650
- **Files:** 6 (2 neu, 4 geändert)
- **Effort:** high
- **LoC-Override:** 700 (gesetzt)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `CompareWizardState` | geändert | Neues Feld `activeMetricKeys` + `metricsManuallyEdited`-Flag |
| `compareMetricDefs.ts` | geändert | `ALL_METRICS`-Katalog (alle anwählbaren Metriken) |
| `compareEditorSave.ts` | geändert | `display_config.active_metrics` in Save-Payload |
| `Location` (types.ts) | reuse | `region` als Gruppierungsfeld, Fallback-Bucket |
| atoms `Eyebrow/Btn/Pill/Field` | reuse | Bausteine |
| `Checkbox` (ui) | reuse | Bibliotheks-Auswahl |
| `RangeSlider.svelte` | neu | Dual-Handle-Slider (reine UI-Komponente, DOM-basiert) |
| `IDEAL_DEFAULTS`, `PROFILE_METRICS_WITH_SCALES` | reuse | Profil-Defaults beim Öffnen |

---

## Acceptance Criteria

**AC-1:** Picked-Liste nummeriert + Entfernen
Given: Im Orte-Tab sind ≥ 1 Orte in `pickedIds`.
When: Nutzer schaut auf den rechten Bereich („Im Vergleich").
Then: Jeder Ort erscheint als Karte mit einer fortlaufenden **Nummer** (1, 2, 3 …), Name + Region/Höhe als Untertitel, und einem **✕-Button**, der den Ort beim Klick aus `pickedIds` entfernt. Bei 0 ausgewählten Orten erscheint ein Leer-State „Noch keine Orte. ↲ links hinzufügen oder unten auswählen".

**AC-2:** Picked-Counter + Warn-Hinweis / Lock-Freischaltung
Given: Orte-Tab geöffnet.
When: Anzahl der `pickedIds` ändert sich.
Then: Rechts neben dem Eyebrow-Header „Im Vergleich · N" zeigt ein Mono-Hinweis:
- `< 2` → `min. 2 erforderlich` (Warn-Farbe `--g-warn`),
- `2–5` → `passt` (Muted),
- `> 5` → `viel — Empfehlung 3–5` (Muted).
Ab ≥ 2 Orten ist der Tab „Idealwerte" in der Editor-Tab-Bar freigeschaltet (bestehende Lock-Logik, bleibt unverändert).

**AC-3:** Bibliotheks-Grid nach Region gruppiert
Given: Mindestens eine `Location` mit gesetztem `region`-Feld und eine ohne.
When: Nutzer schaut auf den unteren Bibliotheks-Abschnitt.
Then: Orte sind in Spalten nach `location.region` gruppiert (bis 3 Spalten, je Region eine Spalte-Gruppe mit Mono-Überschrift `REGION · N`). Orte ohne `region` landen in einem Fallback-Bucket „Weitere". Jeder Ort ist ein Checkbox-Button: aktiv = Accent-Hintergrund + Haken, inaktiv = transparenter Hintergrund; Klick togglet den Ort in `pickedIds`.

**AC-4:** Profil-Defaults beim Öffnen von Idealwerten
Given: Im Tab „Vergleich" ist ein Aktivitätsprofil gewählt. Tab „Idealwerte" wird zum ersten Mal geöffnet.
When: Tab-Wechsel zu „Idealwerte".
Then: `activeMetricKeys` wird mit den Metriken des gewählten Profils aus `PROFILE_METRICS_WITH_SCALES[profileKey]` vorbelegt (sofern noch nicht manuell geändert). `idealRanges` erhält die Defaults aus `IDEAL_DEFAULTS[profileKey]` für Metriken, die noch keinen Wert haben. Bereits gesetzte Werte bleiben erhalten (Edit-Schutz).

**AC-5:** Profil-Wechsel aktualisiert Defaults (sofern nicht manuell überschrieben)
Given: Nutzer hat Profil A gewählt, Tab „Idealwerte" noch **nicht** geöffnet oder Metriken nicht manuell geändert (`metricsManuallyEdited === false`).
When: Nutzer wechselt im Tab „Vergleich" auf Profil B.
Then: `activeMetricKeys` wird auf die Metriken von Profil B zurückgesetzt; `idealRanges` wird für alle neuen Metrik-Keys mit Profil-B-Defaults vorbelegt (bestehende Keys bleiben). Bei `metricsManuallyEdited === true` ändert sich `activeMetricKeys` **nicht** — der Nutzer hat seine Auswahl manuell getroffen.

**AC-6:** Dual-Handle-Slider je Metrik
Given: Tab „Idealwerte" zeigt eine Metrik mit `kind === 'range'`.
When: Nutzer zieht den linken oder rechten Slider-Handle (Maus/Touch) oder bewegt ihn per Pfeiltaste.
Then: Der Handle bewegt sich innerhalb der Grenzen (`rangeMin/rangeMax`), der andere Handle blockiert (kein Überlappen). `idealRanges[key].min` und `idealRanges[key].max` werden laufend aktualisiert. Der **abgeleitete Ideal-Text** rechts (z.B. „30–200 cm") spiegelt die aktuellen Werte sofort wider. Die farbige Balken-Füllung zwischen den Handles aktualisiert sich synchron.

**AC-7:** Enum-Metriken (Gewitter) — Segmented-Control statt Slider
Given: Tab „Idealwerte" zeigt eine Metrik mit `kind === 'enum'` (z.B. `thunder_level_max`).
When: Nutzer klickt ein Enum-Segment.
Then: Genau dieses Segment ist hervorgehoben (`--g-accent-tint`/Border), `idealRanges[key].max` wird auf den gewählten String-Wert gesetzt. Kein Slider, kein Zahlenfeld.

**AC-8:** Metrik hinzufügen
Given: Im Tab „Idealwerte" gibt es Metriken im Gesamt-Katalog `ALL_METRICS`, die noch nicht in `activeMetricKeys` sind.
When: Nutzer klickt „＋ Metrik hinzufügen".
Then: Ein Auswahlbereich (Inline-Liste oder kleines Overlay) zeigt alle noch nicht aktiven Metriken. Klick auf eine Metrik fügt sie zu `activeMetricKeys` hinzu, setzt `metricsManuallyEdited = true`, und schließt die Auswahl. Die neue Metrik erscheint als letzte Zeile.

**AC-9:** Metrik entfernen
Given: Im Tab „Idealwerte" ist mindestens eine Metrik sichtbar.
When: Nutzer klickt das ✕ einer Metrik-Zeile.
Then: Die Metrik wird aus `activeMetricKeys` entfernt, `metricsManuallyEdited = true`. Die Zeile verschwindet sofort. Es gibt kein Minimum — alle Metriken können entfernt werden (leere Liste zeigt Leer-State + „＋ Metrik hinzufügen").

**AC-10:** Persistenz — active_metrics im Save-Payload
Given: Nutzer hat `activeMetricKeys` geändert und klickt im Edit-Modus „Speichern".
When: `saveComparePreset()` läuft durch.
Then: Der PATCH-Payload enthält `display_config.active_metrics` als Array der aktuellen `activeMetricKeys`. Beim Laden des Editors im Edit-Modus werden `activeMetricKeys` aus `preset.display_config.active_metrics` wiederhergestellt (Fallback: Profil-Defaults). Bestandsfelder in `display_config` bleiben per RMW erhalten.

**AC-11:** Funktions-Diff dokumentiert (AC-5 aus Issue)
Given: Implementierung abgeschlossen.
When: Spec-Review.
Then: Jede in `CE_OrteTab` / `CE_IdealwerteTab` vorhandene Funktion ist entweder implementiert oder im Abschnitt „Out-of-Scope / Folge-Issues" explizit aufgeführt.

---

## Implementation Details

### RangeSlider.svelte (neu)
Pure UI-Komponente, keine Store-Abhängigkeit.
```
Props: { min: number, max: number, step: number,
         valueMin: number, valueMax: number,
         onchange: (min: number, max: number) => void }
Intern: Pointer-Events auf zwei Thumb-divs + Track-div.
  mousedown/touchstart → setze actveHandle ('min'|'max')
  pointermove → clamp + gegenseitige Sperre (min ≤ max - step)
  pointerup → cleanup
Tastatur: ArrowLeft/ArrowRight ±step, Home/End
ARIA: role="slider", aria-valuemin/max/now, aria-label
Track-Fill: left = (valueMin-min)/(max-min)*100%, width = (valueMax-valueMin)/(max-min)*100%
```

### compareMetricDefs.ts — ALL_METRICS
```typescript
// Flaches Array aller anwählbaren Metriken (SNOW_DEPTH … THUNDER etc.)
export const ALL_METRICS: MetricDef[] = [SNOW_DEPTH, SNOW_NEW, SUNNY_HOURS, WIND_MAX,
  CLOUD_AVG, VISIBILITY, PRECIP_SUM, UV_INDEX, TEMP_MAX, THUNDER];
```

### compareWizardState.svelte.ts — neue Felder
```typescript
activeMetricKeys = $state<string[]>([]);        // Keys der aktiven Metriken
metricsManuallyEdited = $state(false);          // true sobald Nutzer add/remove tätigte
```
Initialisierung beim Laden aus `preset.display_config.active_metrics ?? profilDefaults`.

### compareEditorSave.ts — Payload-Erweiterung
```typescript
if (edits.activeMetricKeys.length > 0) {
  displayConfig.active_metrics = edits.activeMetricKeys;
}
```
RMW: bestehender `display_config`-Spread (Z. 35) bleibt erhalten — neues Feld ergänzt, nichts überschreibt unbekannte Keys.

### Ideal-Text-Ableitung (keine festen Mock-Texte)
```
range-Metrik: min und max vorhanden → "${min}–${max} ${unit}"
              nur min → "≥ ${min} ${unit}"
              nur max → "≤ ${max} ${unit}"
              weder noch → "–"
enum-Metrik: Enum-Wert direkt als Text
```

### Testid-Vertrag (MUSS erhalten bleiben)
Bestehende Testids aus `issue_452_step2_smart_import.test.ts` und `issue_441_step3_idealwerte.test.ts`:
`compare-wizard-step-2`, `compare-wizard-step-3`, `compare-step2-smart-import-input`,
`compare-step2-resolve-btn`, `compare-step2-fallback-{lat,lon,add-btn}`, `compare-step2-library`,
`compare-step2-counter`, `compare-step3-min-<key>`, `compare-step3-max-<key>`,
`compare-step3-scale-{min,max}-<key>`.

Neue Testids (additiv):
- `compare-step2-picked-list` — Picked-List-Container
- `compare-step2-picked-item-<id>` — einzelne Karte
- `compare-step2-picked-remove-<id>` — ✕-Button
- `compare-step3-slider-min-<key>`, `compare-step3-slider-max-<key>` — Slider-Handles
- `compare-step3-ideal-text-<key>` — abgeleiteter Ideal-Text
- `compare-step3-add-metric-btn` — „＋ Metrik hinzufügen"
- `compare-step3-add-metric-option-<key>` — Option in der Auswahl
- `compare-step3-remove-metric-<key>` — ✕ pro Metrik-Zeile

---

## Out-of-Scope / Folge-Issues

| CE_-Funktion | Status |
|---|---|
| Slider-Drag (war ursprünglich V1.5) | **In Scope** — PO-Entscheidung 2026-06-09 |
| ＋ Metrik hinzufügen | **In Scope** — PO-Entscheidung 2026-06-09 |
| Gewicht-Konfiguration pro Metrik | Out-of-Scope (Slice 4/5) |
| Smart-Import „Mock-Erkennung erkannt"-Pill | **In Scope** — CE_-Fidelity |
| Smart-Import — URL-Link-Icon in Input | In Scope — CE_-Optik |
| Bibliotheks-Suche / Filter | Out-of-Scope (kein CE_-Pendant, Folge-Issue) |

---

## Changelog

- 2026-06-09: Initiale Spec (Slice 3/6, Epic #677). Scope per PO erweitert: Slider-Drag + Add/Remove-Metrik vollständig verdrahtet (überschreibt ursprüngliches Issue „V1.5 OOS").
