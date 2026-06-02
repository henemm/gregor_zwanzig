# Context: Bug #558 — Weekly-Schedule geht bei Pause/Aktivieren verloren

## Request Summary

Wer ein Compare-Preset mit wöchentlichem Versandrhythmus pausiert und danach wieder aktiviert, bekommt anschließend einen täglichen Rhythmus. Die ursprüngliche `weekly`-Einstellung wird beim Aktivieren fest auf `'daily'` gesetzt.

## Root Cause

`frontend/src/lib/components/compare/CompareTabs.svelte`, Zeile 158:

```ts
const next = localSchedule === 'manual' ? 'daily' : 'manual';
```

Beim Aktivieren wird immer `'daily'` gesetzt, egal welchen Schedule das Preset vorher hatte (`'weekly'`). Der vorherige Schedule wird nicht gespeichert.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/compare/CompareTabs.svelte` | **Primärer Fix-Ort**: `handleToggleActive()` (Zeile 155–165) |
| `internal/handler/compare_preset.go` | PUT-Handler (Zeile 143–202): verarbeitet vollständige Presets korrekt |
| `internal/model/compare_preset.go` | Datenmodell: `Schedule string // "daily"|"weekly"|"manual"` |
| `internal/handler/compare_preset_test.go` | Bestehende Tests für PUT-Handler |
| `frontend/src/lib/components/compare/compare_detail.test.ts` | Frontend-Tests für Compare Detail |

## Bestehende Muster

- `localSchedule` ist ein reaktiver `$state`-Wert, der als lokale Kopie von `preset.schedule` dient (Zeile 155)
- `PUT /api/compare/presets/{id}` akzeptiert das vollständige Preset-Objekt — der Backend-Handler überschreibt `schedule` direkt aus dem Request-Body
- Kein dedizierter Pause/Aktivieren-Endpunkt vorhanden

## Lösungsansatz (rein Frontend)

Ein zusätzlicher State `previousSchedule` speichert den Schedule-Wert vor dem Pausieren. Beim Aktivieren wird dieser Wert wiederhergestellt statt immer `'daily'` zu setzen:

```ts
let previousSchedule = $state<string>(preset.schedule ?? 'daily');
let localSchedule = $state<string>(preset.schedule ?? 'manual');

async function handleToggleActive() {
    const isPausing = localSchedule !== 'manual';
    const next = isPausing ? 'manual' : previousSchedule;
    if (isPausing) previousSchedule = localSchedule; // vor Pause merken
    try {
        await api.put(`/api/compare/presets/${preset.id}`, { ...preset, schedule: next });
        localSchedule = next;
    } catch {
        // State bleibt unverändert
    }
}
```

## Dependencies

- **Upstream:** `preset`-Prop (wird von übergeordneter Komponente übergeben)
- **Downstream:** Backend-PUT-Handler (empfängt vollständiges Preset, kein Break)
- **Kein Backend-Change nötig**: Der PUT-Handler kann schon `weekly` korrekt speichern

## Risiken & Überlegungen

- **Einfachster Fix**: Rein im Frontend, kein Backend-Change, keine API-Erweiterung
- **Edge Case**: Wenn `preset.schedule` beim ersten Laden schon `'manual'` ist → `previousSchedule` auf `'daily'` initialisieren (sinnvoller Default)
- **Kein Datenverlust-Risiko**: PUT mit `weekly` hat schon immer funktioniert (bestehende Tests beweisen das)
