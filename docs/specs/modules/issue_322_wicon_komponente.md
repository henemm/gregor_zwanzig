---
entity_id: issue_322_wicon_komponente
type: bugfix
created: 2026-05-22
updated: 2026-05-22
status: draft
version: "1.0"
tags: [bugfix, frontend, design-system, emoji, wicon, lucide, ap-009, issue-322]
---

<!-- Issue #322 — Bug AP-009: Wetter-Emojis in weatherEmoji.ts + StageDetailRow → WIcon ersetzen -->

# Issue #322 — Bug-Fix AP-009: Wetter-Emojis durch WIcon-Komponente ersetzen

## Approval

- [ ] Approved

## Zweck

AP-009 verletzt das Design-System-Verbot für Emojis im Produkt-UI: `weatherEmoji.ts` definiert ein vollständiges WMO→Emoji-Mapping, `StageDetailRow.svelte` enthält eine inline `stageWeatherEmoji()`-Funktion und ein hartcodiertes 💧-Emoji, und drei weitere Svelte-Routen importieren `weatherEmoji`. Der Fix führt eine neue `WIcon.svelte`-Komponente (Lucide-Wrapper, 8 Varianten) und `weatherUtils.ts` (WMO→WIconKind-Mapping + `degToCardinal()`) ein und stellt alle 4 betroffenen Konsumenten auf `<WIcon>` um, sodass das Produkt-UI emoji-frei ist und ausschließlich Design-System-konforme SVG-Icons verwendet werden.

## Quelle / Source

**Neue Dateien:**
- `frontend/src/lib/utils/weatherUtils.ts` — `WIconKind`-Typ + `wmoToWIconKind()` + `degToCardinal()`
- `frontend/src/lib/components/ui/wicon/WIcon.svelte` — Lucide-Wrapper-Komponente
- `frontend/src/lib/components/ui/wicon/index.ts` — Re-Export

**Geänderte Dateien:**
- `frontend/src/lib/components/trip-detail/StageDetailRow.svelte` — inline Emoji-Funktion + 💧 durch `<WIcon>` ersetzen
- `frontend/src/lib/components/compare/HourlyMatrix.svelte` — `weatherEmoji`-Import durch `weatherUtils`-Import ersetzen
- `frontend/src/routes/weather/+page.svelte` — `weatherEmoji`-Import + `degToCardinal`-Import auf `weatherUtils` umstellen
- `frontend/src/routes/compare/+page.svelte` — `weatherEmoji`-Import durch `weatherUtils`-Import ersetzen

> **Schicht-Hinweis:** Alle Änderungen liegen ausschließlich im Frontend-Layer (`frontend/src/`). Kein Go-API-Code, kein Python-Backend-Code betroffen. `weatherEmoji.ts` bleibt unberührt — kein Breaking-Change-Risiko für potenzielle externe Konsumenten.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `@lucide/svelte` | npm-Paket (bereits installiert) | Liefert die 8 SVG-Icon-Komponenten (sun, cloud, cloud-rain, cloud-lightning, cloud-snow, wind, moon, flashlight) |
| `frontend/src/lib/utils/weatherEmoji.ts` | TypeScript-Modul (bestehend, read-only) | Enthält das bisherige WMO→Emoji-Mapping; bleibt unverändert; `degToCardinal()` wird in `weatherUtils.ts` neu implementiert |
| `frontend/src/lib/components/trip-detail/StageDetailRow.svelte` | Svelte-Komponente (bestehend) | Konsument Nr. 1 — inline `stageWeatherEmoji()` + 💧-Literal werden ersetzt |
| `frontend/src/lib/components/compare/HourlyMatrix.svelte` | Svelte-Komponente (bestehend) | Konsument Nr. 2 — `weatherEmoji`-Import wird auf `weatherUtils` umgestellt |
| `frontend/src/routes/weather/+page.svelte` | SvelteKit-Route (bestehend) | Konsument Nr. 3 — `weatherEmoji` + `degToCardinal` werden aus `weatherUtils` bezogen |
| `frontend/src/routes/compare/+page.svelte` | SvelteKit-Route (bestehend) | Konsument Nr. 4 — `weatherEmoji`-Import wird auf `weatherUtils` umgestellt |
| `docs/design-system/COMPONENTS.md §3` | Design-System-Dokument | Normative Quelle für WIcon-API (kind, size, color, class) |

## Implementation Details

### 1. `weatherUtils.ts` — WIconKind-Typ + wmoToWIconKind() + degToCardinal()

Neue Datei `frontend/src/lib/utils/weatherUtils.ts`:

```typescript
export type WIconKind =
  | 'sun'
  | 'cloud'
  | 'rain'
  | 'thunder'
  | 'snow'
  | 'wind'
  | 'moon'
  | 'headlamp';

/**
 * Mappt einen WMO-Wettercode + optionale Tageszeit-/Strahlungs-/Bewölkungs-Parameter
 * auf einen WIconKind-Wert. Gibt 'cloud' als sicheren Fallback zurück.
 *
 * @param wmo      WMO-Wettercode (oder null wenn nicht vorhanden)
 * @param isDay    1 = Tag, 0 = Nacht (oder null)
 * @param dni      Direct Normal Irradiance in W/m² (oder null)
 * @param cloudPct Bewölkungsgrad 0–100 (oder null)
 */
export function wmoToWIconKind(
  wmo: number | null,
  isDay?: number | null,
  dni?: number | null,
  cloudPct?: number | null
): WIconKind {
  // WMO-codierte Phänomene haben Vorrang
  if (wmo !== null && wmo !== undefined) {
    if (wmo === 45 || wmo === 48) return 'cloud';           // Nebel
    if (wmo >= 51 && wmo <= 55) return 'rain';              // Nieselregen
    if (wmo >= 56 && wmo <= 67) return 'rain';              // Regen / gefrierender Regen
    if (wmo >= 71 && wmo <= 77) return 'snow';              // Schnee / Schneegestöber
    if (wmo >= 80 && wmo <= 82) return 'rain';              // Regenschauer
    if (wmo === 85 || wmo === 86) return 'snow';            // Schneeschauer
    if (wmo >= 95 && wmo <= 99) return 'thunder';           // Gewitter
  }

  // Tageszeit- und Strahlungsbasierte Entscheidung
  if (isDay === 0) {
    // Nacht
    return (cloudPct != null && cloudPct > 50) ? 'cloud' : 'moon';
  }

  // Tag (isDay === 1 oder unbekannt)
  if (dni != null) {
    if (dni > 500) return 'sun';
    if (dni >= 50) return 'cloud';
  }
  if (cloudPct != null && cloudPct >= 80) return 'cloud';

  return 'cloud'; // sicherer Fallback
}

/**
 * Konvertiert einen Windrichtungs-Grad-Wert (0–360) in eine 8-Punkte-Himmelsrichtung.
 * Identische Logik wie der bisherige Export aus weatherEmoji.ts.
 */
export function degToCardinal(deg: number): string {
  const dirs = ['N', 'NO', 'O', 'SO', 'S', 'SW', 'W', 'NW'];
  return dirs[Math.round(deg / 45) % 8];
}
```

### 2. `WIcon.svelte` — Lucide-Wrapper

Neue Datei `frontend/src/lib/components/ui/wicon/WIcon.svelte`:

```svelte
<script lang="ts">
  import Sun from '@lucide/svelte/icons/sun';
  import Cloud from '@lucide/svelte/icons/cloud';
  import CloudRain from '@lucide/svelte/icons/cloud-rain';
  import CloudLightning from '@lucide/svelte/icons/cloud-lightning';
  import CloudSnow from '@lucide/svelte/icons/cloud-snow';
  import Wind from '@lucide/svelte/icons/wind';
  import Moon from '@lucide/svelte/icons/moon';
  import Flashlight from '@lucide/svelte/icons/flashlight';
  import type { WIconKind } from '$lib/utils/weatherUtils';

  export let kind: WIconKind;
  export let size: number = 20;
  export let color: string = 'currentColor';
  let className: string = '';
  export { className as class };

  const iconMap = {
    sun: Sun,
    cloud: Cloud,
    rain: CloudRain,
    thunder: CloudLightning,
    snow: CloudSnow,
    wind: Wind,
    moon: Moon,
    headlamp: Flashlight,
  } as const;
</script>

<svelte:component
  this={iconMap[kind]}
  size={size}
  color={color}
  class={className}
  aria-hidden="true"
/>
```

### 3. `index.ts` — Re-Export

Neue Datei `frontend/src/lib/components/ui/wicon/index.ts`:

```typescript
export { default as WIcon } from './WIcon.svelte';
export type { WIconKind } from '$lib/utils/weatherUtils';
```

### 4. `StageDetailRow.svelte` — Emoji-Funktion + 💧 ersetzen

- Import `WIcon` aus `$lib/components/ui/wicon`
- Import `wmoToWIconKind` aus `$lib/utils/weatherUtils`
- Inline-Funktion `stageWeatherEmoji()` entfernen
- Alle Aufrufe von `stageWeatherEmoji(...)` durch `<WIcon kind={wmoToWIconKind(...)} size={16} />` ersetzen
- Das hartcodierte 💧-Emoji (Zeile 145) durch `<WIcon kind="rain" size={14} />` ersetzen

### 5. `HourlyMatrix.svelte` — Import tauschen

- `import { weatherEmoji } from '$lib/utils/weatherEmoji'` entfernen
- `import { wmoToWIconKind } from '$lib/utils/weatherUtils'` ergänzen
- Alle `weatherEmoji(wmo)`-Aufrufe durch `<WIcon kind={wmoToWIconKind(wmo)} />` ersetzen (inkl. WIcon-Import)

### 6. `weather/+page.svelte` + `compare/+page.svelte` — Imports umstellen

- `weatherEmoji`-Import aus `weatherEmoji.ts` entfernen
- `degToCardinal`-Import (falls vorhanden) aus `weatherEmoji.ts` entfernen
- Stattdessen aus `$lib/utils/weatherUtils` importieren
- Alle Emoji-String-Ausgaben durch `<WIcon>`-Renderings ersetzen

### 7. LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `frontend/src/lib/utils/weatherUtils.ts` | +55 (neu) | nein (Frontend-Asset) |
| `frontend/src/lib/components/ui/wicon/WIcon.svelte` | +35 (neu) | nein (Frontend-Asset) |
| `frontend/src/lib/components/ui/wicon/index.ts` | +3 (neu) | nein (Frontend-Asset) |
| `frontend/src/lib/components/trip-detail/StageDetailRow.svelte` | ~+5 / -10 | nein (Frontend-Asset) |
| `frontend/src/lib/components/compare/HourlyMatrix.svelte` | ~+5 / -5 | nein (Frontend-Asset) |
| `frontend/src/routes/weather/+page.svelte` | ~+5 / -5 | nein (Frontend-Asset) |
| `frontend/src/routes/compare/+page.svelte` | ~+3 / -3 | nein (Frontend-Asset) |
| **Gesamt (zählend)** | **0** | **< 250 LoC-Limit** |

## Expected Behavior

- **Input:** WMO-Wettercode (Ganzzahl 0–99), optional Tageszeit (isDay 0/1), DNI-Wert (W/m²), Bewölkungsgrad (0–100)
- **Output:** `WIconKind`-String, der in `<WIcon kind={...} />` eingesetzt wird und ein Lucide-SVG rendert. Kein Emoji-Zeichen im DOM.
- **Side effects:** `weatherEmoji.ts` bleibt unberührt und kann weiterhin importiert werden — keine Breaking Changes. Beim nächsten Build wird das resultierende JS-Bundle keine Emoji-Zeichenketten mehr in produktiven Pfaden enthalten (außer `weatherEmoji.ts` selbst, die niemand mehr importiert).

## Acceptance Criteria

- **AC-1:** Given ein WMO-Code für Gewitter (z.B. 95), When `wmoToWIconKind(95)` aufgerufen wird, Then gibt die Funktion `"thunder"` zurück.
  - Test: (populated after /tdd-red)

- **AC-2:** Given ein WMO-Code für Schnee (z.B. 71), When `wmoToWIconKind(71)` aufgerufen wird, Then gibt die Funktion `"snow"` zurück.
  - Test: (populated after /tdd-red)

- **AC-3:** Given `isDay=0` und `cloudPct=20` (klare Nacht), When `wmoToWIconKind(null, 0, null, 20)` aufgerufen wird, Then gibt die Funktion `"moon"` zurück.
  - Test: (populated after /tdd-red)

- **AC-4:** Given `<WIcon kind="rain" />` wird gerendert, Then ist ein cloud-rain SVG-Element im DOM sichtbar und kein Emoji-Zeichen im gerenderten HTML enthalten.
  - Test: (populated after /tdd-red)

- **AC-5:** Given der Grep-Befehl `grep -rnP '[\x{1F300}-\x{1F9FF}]' frontend/src/` ausgeführt wird, Then liefert dieser keine Treffer in produktiven Svelte/TS-Dateien außerhalb von `weatherEmoji.ts`.
  - Test: (populated after /tdd-red)

## Known Limitations

- **`weatherEmoji.ts` bleibt im Codebase:** Die Datei wird nicht gelöscht, um Breaking-Change-Risiken zu vermeiden. Sie wird von keinem produktiven Konsumenten mehr importiert, ist aber weiterhin im Repository vorhanden. Eine spätere Bereinigung kann in einem separaten Cleanup-Issue erfolgen.
- **`wmoToWIconKind()` kennt keine WMO-Codes 1–3 (leicht/teils bewölkt):** Diese WMO-Werte werden über den DNI/cloud-basierten Zweig aufgelöst. Wenn weder `dni` noch `cloudPct` übergeben werden, gibt die Funktion `'cloud'` als konservativen Fallback zurück.
- **`headlamp`-Icon:** Das `kind="headlamp"` wird in diesem Issue nicht aktiv verwendet (kein bestehender Konsument), aber als vollständige Implementierung des Design-System-Vertrags mitgeliefert.

## Out of Scope

- Löschen von `weatherEmoji.ts`
- Änderungen an der Go-API oder am Python-Backend
- Neue WMO-Code-Bereiche jenseits der in der Analyse dokumentierten Tabelle
- Animations- oder Farbthematisierung der WIcon-Komponente
- Dark-Mode-spezifische Icon-Varianten

## Changelog

- 2026-05-22: Initial spec erstellt. Behebt Design-System-Verstoß AP-009 durch neue WIcon.svelte-Komponente (Lucide-Wrapper, 8 kinds) + weatherUtils.ts (wmoToWIconKind + degToCardinal). 3 neue Dateien, 4 geänderte Dateien, ~130 LoC.
