# Context: Issue #714 — Paket Trip-Editor UI-Kleinigkeiten

## Request Summary
Sammel-Issue für drei kleine, rein frontendseitige UI-Korrekturen in Trip-Übersicht/-Editor.
#699 (Doppelter Pfad im Header) ist bereits live (43fb624f). Verbleibend: **#706, #713, #719**.

## Verbleibende Teilaufgaben
| # | Titel | Datei | Stelle |
|---|-------|-------|--------|
| #706 | […]-Menü in Trip-Übersicht abgeschnitten | `frontend/src/routes/trips/+page.svelte` | Dropdown Z.440 in `<Card overflow:hidden>` Z.373 |
| #713 | Trip-Titel nur über Stift-Icon editierbar | `frontend/src/lib/components/trip-detail/TripHeader.svelte` | `name-edit-row` Z.115–130 (dauerhaft sichtbar) |
| #719 | Mobile /trips/new: Etappen-Lösch-Button fehlt | `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | Mobile Stage-Card Z.817–860 (nur GPX-×, keine Etappen-Löschung) |

## Root-Cause je Punkt
- **#706:** Das Overflow-Menü (`position: absolute`, Z.440) liegt in einer `<Card style="overflow: hidden;">` (Z.373). `position:absolute` wird vom `overflow:hidden`-Vorfahren beschnitten → das ~6-Einträge-Menü (~280px) wird bei unteren Zeilen unten abgeschnitten. Analoges Pattern wie #682 (Sheet `position:fixed` statt `absolute`).
- **#713:** `name-edit-row` (Input + „Umbenennen", Z.115–130) ist permanent unter der H1 sichtbar. Soll: nur Titel + Stift-Icon; Klick auf Stift → Inline-Edit (Input + Speichern) erscheint.
- **#719:** Mobile Stage-Card hat nur einen `×` für GPX-Entfernung (`makeGpxRemoveHandler`, Z.845), keinen Etappen-Lösch-Button. Desktop hat ihn (`makeRemoveStageHandler(s.id)`, Z.627, testid `tn-stage-remove-{idx}`) inkl. #708-Bestätigungsdialog.

## Existing Patterns (wiederverwendbar)
- **Stift-Icon:** `import PencilIcon from '@lucide/svelte/icons/pencil'` (genutzt in `account/+page.svelte`, `trips/+page.svelte`).
- **Etappen-Löschung mit Dialog:** `makeRemoveStageHandler(id)` → `pendingRemoveStageId` → bits-ui Dialog (Z.980–992, Abbrechen/Löschen), `confirmRemoveStage()` (Z.263). Bereits da seit #708 — Mobile muss nur denselben Handler nutzen.
- **position:fixed-Escape aus overflow:hidden:** #682 (Sheet.svelte), commit cfe45df8.

## Dependencies
- Upstream: lucide-Icons, bits-ui Dialog (bereits importiert in TripNewEditor), `api.put` (TripHeader Save).
- Downstream: Playwright-Tests `e2e/`, Vitest `TripHeader.issue699.test.ts`, `issue_581_trip_detail_jsx.test.ts`.

## Risks & Considerations
- **#713:** testid `trip-name-edit` / `trip-name-save` bestehen — prüfen ob bestehende Tests das permanent sichtbare Feld erwarten (dann anpassen). Datenerhalt: nur `name` wird via PUT geändert (RMW im Backend, vgl. #707).
- **#706 position:fixed:** Menü muss bei Scroll geschlossen werden (sonst Position veraltet). Koordinaten aus `getBoundingClientRect()` des Buttons.
- **#719:** Lösch-Button im IMMER sichtbaren Card-Header platzieren (nicht im GPX-Slot) — Mobile-Parität wie #675/#661.
- Alles frontend-only, gleiche Komponentenfamilie, ein Staging-Lauf, ein Deploy. Geschätzt ~65 LoC (< 250-Limit).
