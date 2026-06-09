# Context: Issue #680 — Compare-Editor Slice 3 (Fidelity Tabs „Orte" + „Idealwerte")

## Request Summary
Epic #677 · Slice 3/6. Die Tab-Inhalte **„Orte"** und **„Idealwerte"** im Compare-Editor-Gerüst
(aus Slice 1/2) 1:1 auf die neue `CE_`-Fidelity aus `screen-compare-editor.jsx` bringen —
**ohne** die bestehende funktionale Logik (Smart-Import, Picked-State, Idealwert-Persistenz) zu
ändern. Reiner Markup/Style-Rework.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/compare/CompareEditor.svelte` | Gerüst (Slice 1/2); rendert `<Step2Orte>` / `<Step3Idealwerte>` in den Tabs |
| `frontend/src/lib/components/compare/steps/Step2Orte.svelte` | **Ziel A** — Orte-Tab, aktuell Tailwind-Markup, muss auf CE_-Fidelity |
| `frontend/src/lib/components/compare/steps/Step3Idealwerte.svelte` | **Ziel B** — Idealwerte-Tab, aktuell Number-Input-Grid, muss auf CE_-Fidelity |
| `frontend/src/lib/components/compare/compareMetricDefs.ts` | `PROFILE_METRICS_WITH_SCALES` + `IDEAL_DEFAULTS` (echte Metrik-Keys, persistierte min/max) |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | `pickedIds`, `idealRanges`, `activityProfile` — geteilter State via Context |
| `frontend/src/lib/types.ts` | `Location` (region, elevation_m), `ActivityProfile` (4 Werte), `toCompareProfile()`, `ACTIVITY_PROFILE_OPTIONS` |
| `claude-code-handoff/.../jsx/screen-compare-editor.jsx` | **Design-Quelle** — `CE_OrteTab` (Z.196-306), `CE_IdealwerteTab` (Z.309-361), `CE_IDEALS` (Z.28-60) |

## Existing Patterns
- **Geteilter State:** Beide Steps konsumieren `getContext<CompareWizardState>('compare-wizard-state')`. `pickedIds: string[]`, `idealRanges: Record<string, IdealRange>`, `activityProfile`.
- **Idealwert-Defaults:** `Step3Idealwerte` schreibt via `$effect` die `IDEAL_DEFAULTS[profileKey]` in `state.idealRanges` — **nur** für noch nicht belegte Keys (Edit-Schutz). Angezeigte Metrik-Liste = `PROFILE_METRICS_WITH_SCALES[profileKey]`. → AC-3/AC-4 funktional **bereits abgedeckt**.
- **Persistenz:** `idealRanges` → `display_config.ideal_ranges` (RMW), Save-Flow aus #679 (`compareEditorSave.ts`) unverändert.
- **Profil-Mapping:** `toCompareProfile()` mappt 4 `ActivityProfile` → 4 `ProfileKey` (WINTERSPORT/ALPINE_TOURING/SUMMER_TREKKING/ALLGEMEIN).
- **Edit-Modus:** `CompareEditor` schaltet im Edit-Modus alle Tabs frei (`isEdit || unlocked`), kein Continue-Button.

## Dependencies
- **Upstream:** CompareWizardState (Context), compareMetricDefs (Defaults/Skalen), Location-API (`/api/locations`, `/api/locations/resolve`), Atoms (`Eyebrow`, `Btn`, `Pill`, `Field`), `Checkbox`.
- **Downstream:** Save-Flow #679 liest `idealRanges`/`pickedIds`. Bestehende Component-Tests (`issue_452_step2_smart_import.test.ts`, `issue_441_step3_idealwerte.test.ts`) referenzieren Testids.

## Testid-Vertrag (PFLICHT erhalten)
`compare-wizard-step-2`, `compare-wizard-step-3`, `compare-step2-smart-import-input`,
`compare-step2-resolve-btn`, `compare-step2-fallback-{lat,lon,add-btn}`, `compare-step2-library`,
`compare-step2-counter`, `compare-step3-min-<key>`, `compare-step3-max-<key>`,
`compare-step3-scale-{min,max}-<key>`. → Rework darf diese **nicht** brechen; neue Testids additiv.

## Profil-Daten-Divergenz (wichtige Designentscheidung)
`CE_IDEALS` (Design) hat **5** display-only Profile (`wintersport`, `wintersport-glacier`,
`alpine-touring`, `hiking`, `trail-running`) mit reinen Anzeige-Feldern (`ideal`-Text, `pos`
Slider-Position, `notes`, `scale`-Labels). Das echte Datenmodell hat **4** Profile mit echten
Metrik-Keys + numerischen min/max. → **Funktionales Modell bleibt Source of Truth.** Anzeige-Felder
(Slider-Bar-Füllung, Ideal-Text, Skalen-Labels, Notiz) werden aus dem echten Modell **abgeleitet**,
nicht aus den 5 Mock-Profilen kopiert.

## Risks & Considerations
- **R1 (Testid-Bruch):** Heavy-Markup-Rework darf bestehende Tests nicht rot machen → funktionale Testids erhalten.
- **R2 (Slider = nur Anzeige):** Drag ist explizit Out-of-Scope (V1.5). Slider-Bar read-only aus min/max ÷ rangeMin/rangeMax ableiten.
- **R3 (Ideal-Text-Ableitung):** CE-statische Texte („≥ 80 cm") passen nicht zu unseren numerischen Defaults → Ideal-Text aus min/max+unit generieren.
- **R4 (Region-Gruppierung):** `CE_OrteTab` gruppiert nach `l.group`; unser Modell hat `region` (+ `group_id`). Nach `region` gruppieren, Fallback-Bucket für Orte ohne Region.
- **R5 (LoC-Limit 250):** Zwei Komponenten + Doku; Frontend-Markup ist LoC-intensiv → ggf. `loc_limit_override`.
- **R6 (AC-5 Funktions-Diff):** Doku-Pflicht — jede CE_-Funktion abgedeckt oder Out-of-Scope vermerken.
