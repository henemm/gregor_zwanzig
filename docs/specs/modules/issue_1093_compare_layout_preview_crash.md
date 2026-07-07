---
entity_id: issue_1093_compare_layout_preview_crash
type: module
created: 2026-07-07
updated: 2026-07-07
status: draft
version: "1.0"
tags: [bug, frontend, compare, layout]
---

# Orts-Vergleich Layout-Tab: LayoutPreview-Crash bei echten Orten (#1093)

## Approval

- [ ] Approved

## Purpose

Der Layout-Tab im Orts-Vergleich-Editor (`/compare/new` → Tab „Layout") bleibt dauerhaft
bei „Lade Metriken-Katalog…" hängen, sobald echte Orte gewählt sind. Ursache ist ein
Render-Crash in der Beispiel-Vorschau `LayoutPreview.svelte`. Dieser Fix stellt sicher,
dass der Layout-Tab immer lädt und die Vorschau nie leer läuft.

## Source

- **File:** `frontend/src/lib/components/compare/LayoutPreview.svelte`
- **Identifier:** `rows` ($derived, Z. 20–24)

Schicht: **Frontend / User-UI** (SvelteKit).

## Estimated Scope

- **LoC:** ~5–10
- **Files:** 1 (`LayoutPreview.svelte`)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `Step4Layout.svelte` | Consumer | Mountet LayoutPreview; sein Lade-Zustand bleibt bei Crash stehen |
| `CompareEditor.svelte` | Consumer | Rendert Step4Layout im Tab `layout` (Desktop + Mobile) |

## Implementation Details

Ist-Zustand (fehlerhaft):

```js
const rows = $derived(
  pickedIds.length > 0
    ? DUMMY_LOCATIONS.filter(d => pickedIds.includes(d.id)).slice(0, 5)
    : DUMMY_LOCATIONS
);
```

`DUMMY_LOCATIONS` hat feste Fantasie-IDs (`loc-01/07/08`). Echte `pickedIds` sind echte
Location-UUIDs → der Filter matcht nie → `rows = []` → `rows[0].name` / `rows[0].feels`
(Z. 46–47, 57–59, 97) wirft `Cannot read properties of undefined (reading 'feels')` →
Render-Crash → Spinner bleibt stehen.

Soll-Zustand: Die Vorschau ist reine Illustration mit statischen Dummy-Daten. Der ID-Match
gegen echte Orte ist strukturell bedeutungslos. `rows` wird an die **Anzahl** der gewählten
Orte gekoppelt, immer aus `DUMMY_LOCATIONS` genommen, und ist nie leer:

```js
const rows = $derived(
  pickedIds.length > 0
    ? DUMMY_LOCATIONS.slice(0, Math.min(pickedIds.length, DUMMY_LOCATIONS.length))
    : DUMMY_LOCATIONS
);
```

(Untergrenze: mindestens 1 Zeile, da `pickedIds.length > 0` im Zweig gilt und
`DUMMY_LOCATIONS.length >= 1`.)

## Expected Behavior

- **Input:** `channel` ('email'|'telegram'|'sms'), `pickedIds` (echte Location-UUIDs)
- **Output:** Vorschau mit 1–3 illustrativen Dummy-Zeilen (gedeckelt auf `DUMMY_LOCATIONS.length`)
- **Side effects:** keine — kein API-Call, keine Persistenz

## Acceptance Criteria

- **AC-1:** Given ein eingeloggter Nutzer legt unter `/compare/new` einen neuen Orts-Vergleich
  an und wählt **zwei echte gespeicherte Orte** / When er den Tab **„Layout"** öffnet / Then
  verschwindet der Text „Lade Metriken-Katalog…" innerhalb von 5 Sekunden und der
  Metriken-Katalog samt Vorschau (`compare-step4-layout-preview`) wird sichtbar — **ohne**
  einen `pageerror` in der Browser-Konsole.
  - Test: Playwright-E2E gegen Staging — Wizard durchklicken (Name, 2 Library-Orte,
    Idealwerte öffnen, Layout-Tab), `page.on('pageerror')` sammeln, assert 0 pageerrors und
    `getByTestId('step4-loading')` nicht mehr sichtbar, `compare-step4-layout-preview` sichtbar.

- **AC-2:** Given der Layout-Tab ist offen mit ≥2 gewählten Orten / When die Vorschau rendert /
  Then zeigt die Vorschau-Tabelle mindestens eine Datenzeile mit Ort-Name und Temperatur-Wert
  (keine leere Tabelle, kein „undefined").
  - Test: Playwright — assert `compare-step4-layout-preview` enthält ≥1 `<tr>` mit
    nicht-leerem Ort-Namen; kein Text „undefined" im Vorschau-Container.

## Known Limitations

- Die Vorschau bleibt bewusst rein illustrativ (statische Dummy-Wetterwerte). Sie zeigt
  **nicht** echte Wetterdaten der gewählten Orte — das ist unverändert und nicht Teil dieses
  Fixes. Nur der Crash / das Nie-Laden wird behoben.
- Konfigurierbarkeit der Metriken/Elemente (#1094) und Alerts (#1095) sind separate Issues.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner lokaler Bugfix in einer Präsentationskomponente, keine
  Architektur- oder Schnittstellenänderung.

## Changelog

- 2026-07-07: Initial spec created (#1093, aus #1092 Punkt 1)
