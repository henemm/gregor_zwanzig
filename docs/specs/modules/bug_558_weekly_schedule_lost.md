---
entity_id: bug_558_weekly_schedule_lost
type: bugfix
created: 2026-06-02
updated: 2026-06-02
status: draft
version: "1.0"
tags: [bugfix, compare-hub, versand-tab, schedule, weekly, issue-558]
---

<!-- Issue #558 — Compare Hub · Versand-Tab: Wöchentlicher Rhythmus geht bei Pause/Aktivieren verloren -->

# Issue #558 — Bug-Fix: Wöchentlicher Versand-Rhythmus nach Pause/Aktivieren wiederherstellen

## Approval

- [ ] Approved

## Zweck

Im Compare Hub (Versand-Tab) kann ein Preset pausiert und wieder aktiviert werden. Beim Aktivieren wird der Versand-Rhythmus (`schedule`) immer auf `'daily'` gesetzt — auch wenn das Preset vorher `'weekly'` hatte. Dadurch geht der wöchentliche Rhythmus still und heimlich verloren. Fix: Vor dem Pausieren den aktuellen Schedule merken und beim Aktivieren genau diesen Wert wiederherstellen.

## Quelle / Source

**Geänderte Dateien:**
- `frontend/src/lib/components/compare/CompareTabs.svelte` (einzige Änderung)

**Root Cause:** Zeile 158 in `CompareTabs.svelte`:
```typescript
const next = localSchedule === 'manual' ? 'daily' : 'manual';
```
Diese Logik unterscheidet nur zwischen `'manual'` (pausiert) und `'daily'` (aktiv) — `'weekly'` wird beim Aktivieren niemals zurückgesetzt.

> **Schicht-Hinweis:** Ausschliesslich SvelteKit-Frontend-Layer (`frontend/src/lib/components/compare/`). Das Datenmodell im Go-Backend (`internal/model/compare_preset.go`) bleibt unverändert — `Schedule string` mit den erlaubten Werten `"daily"`, `"weekly"`, `"manual"` ist bereits korrekt.

## Estimated Scope

- **LoC:** ~15
- **Files:** 1
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/compare/CompareTabs.svelte` | Svelte-Komponente | Enthält `handleToggleActive()` und den fehlerhaften Toggle-State |
| `internal/model/compare_preset.go` | Go-Model | Definiert `Schedule string`; Werte `"daily"`, `"weekly"`, `"manual"` — kein Change nötig |

## Implementation Details

### Zustandsänderung in `CompareTabs.svelte`

Zwei neue/geänderte `$state`-Variablen und eine korrigierte `handleToggleActive`-Funktion:

```typescript
// Neu: merkt den letzten aktiven Schedule vor einer Pause
let previousSchedule = $state<string>(
    (preset.schedule && preset.schedule !== 'manual') ? preset.schedule : 'daily'
);

// Unverändert initialisiert, aber jetzt durch previousSchedule ergänzt
let localSchedule = $state<string>(preset.schedule ?? 'manual');

async function handleToggleActive() {
    const isPausing = localSchedule !== 'manual';
    if (isPausing) previousSchedule = localSchedule; // vor Pause merken
    const next = isPausing ? 'manual' : previousSchedule;
    try {
        await api.put(`/api/compare/presets/${preset.id}`, { ...preset, schedule: next });
        localSchedule = next;
    } catch {
        // State bleibt unverändert bei Fehler
    }
}
```

**Wichtig:** `previousSchedule` wird nur beim Pausieren überschrieben — nicht beim Aktivieren. Damit bleibt der Wert über mehrere Pause/Aktivieren-Zyklen stabil.

### LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `frontend/src/lib/components/compare/CompareTabs.svelte` | ~15 | ja (Frontend-Komponente) |
| **Gesamt (zählend)** | **~15** | **< 250 LoC-Limit** |

## Expected Behavior

- **Input:** Benutzer klickt "Pausieren" auf einem Preset mit `schedule='weekly'`, dann klickt er "Aktivieren"
- **Output:** Das Preset hat nach dem Aktivieren wieder `schedule='weekly'`; kein `'daily'`-Fallback
- **Side effects:** Kein Backend-Change. Der API-PUT-Call wird weiterhin mit dem korrekten `schedule`-Wert abgesetzt.

## Acceptance Criteria

- **AC-1:** Given ein Preset mit `schedule='daily'` / When der User pausiert und dann wieder aktiviert / Then ist `schedule` danach `'daily'` (bestehende Funktionalität unverändert)

- **AC-2:** Given ein Preset mit `schedule='weekly'` / When der User pausiert (→ `schedule='manual'`) und dann wieder aktiviert / Then ist `schedule` danach `'weekly'` und nicht `'daily'`

- **AC-3:** Given ein Preset im Entwurfs-Zustand mit `schedule='manual'` (noch nie aktiv gewesen) / When der User erstmals aktiviert / Then wird `schedule='daily'` gesetzt (sinnvoller Default für Erstaktivierung)

## Known Limitations

- `previousSchedule` ist ein rein lokaler Svelte-State und überlebt keinen Seiten-Reload. Falls der User die Seite nach dem Pausieren neu lädt und dann aktiviert, greift der aus dem gespeicherten Preset-Wert initialisierte `previousSchedule` (Fallback `'daily'`). Da das Preset zu diesem Zeitpunkt `schedule='manual'` hat, kann der ursprüngliche Wert serverseitig nicht mehr rekonstruiert werden — das ist eine akzeptable Einschränkung und kein Regression gegenüber dem aktuellen Verhalten.

## Out of Scope

- Backend-Änderungen am Schedule-Datenmodell
- Persistenz von `previousSchedule` über Page-Reloads hinaus
- Änderungen an anderen Teilen des Compare Hub

## Changelog

- 2026-06-02: Initial spec erstellt. Behebt stillen Datenverlust des wöchentlichen Versand-Rhythmus beim Pause/Aktivieren-Zyklus in `CompareTabs.svelte`.
