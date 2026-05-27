---
entity_id: bug_417_alertrow_icon_mapping
type: bugfix
created: 2026-05-27
updated: 2026-05-27
status: draft
version: "1.0"
tags: [bugfix, frontend, alert-row, icon-mapping, molecules, issue-417]
---

<!-- Issue #417 — Bug: AlertRow zeigt falsches Icon für alle Alert-Typen außer Gewitter -->

# Issue #417 — Bug-Fix: AlertRow — KIND_MAP + TONE_MAP für vollständiges Icon/Tone-Mapping

## Approval

- [ ] Approved

## Zweck

`AlertRow.svelte` zeigt für alle Alert-Arten außer `thunder` das Wind-Icon, weil Zeile 55 eine einfache ternäre Bedingung (`alert.kind === 'thunder' ? 'thunder' : 'wind'`) statt einer vollständigen Lookup-Tabelle verwendet. Regen-, Schnee-, Sonnen- und Temperatur-Alerts werden damit visuell falsch als Wind dargestellt. Derselbe Defekt steckt in der Tone-Berechnung (Zeile 53): `thunder_level` wird als `'warn'` statt als `'bad'` eingestuft, obwohl Gewittergefahr dieselbe Kritikalitätsstufe verdient. Der Fix ersetzt beide ternären Ausdrücke durch typisierte Lookup-Maps (`KIND_MAP`, `TONE_MAP`) mit explizitem `?? Fallback`, sodass alle bekannten Backend-Metrik-Namen korrekt auf ein Icon und eine Farbe abgebildet werden.

## Quelle / Source

**Geänderte Dateien:**
- `frontend/src/lib/components/molecules/AlertRow.svelte` — Zeilen 53–55: `tone`- und `iconKind`-Berechnung durch `TONE_MAP` + `KIND_MAP` ersetzen
- `frontend/src/lib/components/molecules/molecules.test.ts` — neuen Test für Icon-Mapping aller Kind-Werte ergänzen

> **Schicht-Hinweis:** Alle Änderungen liegen ausschließlich im Frontend-Layer (`frontend/src/`). Kein Go-API-Code, kein Python-Backend-Code betroffen. Der Bug ist rein visuell — Daten und Logik sind korrekt.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/utils/weatherUtils.ts` | TypeScript-Modul | Definiert `WIconKind` (`'sun' \| 'cloud' \| 'rain' \| 'thunder' \| 'snow' \| 'wind' \| 'moon' \| 'headlamp'`); unveränderlich, wird als Typ für `KIND_MAP` verwendet |
| `frontend/src/lib/components/atoms/WIcon.svelte` | Svelte-Atom | Empfängt `kind: WIconKind` und rendert das passende SVG-Icon; ist bereits in `AlertRow` importiert |
| `frontend/src/lib/components/molecules/molecules.test.ts` | TypeScript-Testdatei | Bestehende Source-Inspection-Tests für die Molecules-Schicht; erhält neue Testfälle für das Kind-Mapping |

## Implementation Details

### 1. `AlertRow.svelte` — KIND_MAP + TONE_MAP

Die zwei ternären Ausdrücke auf den Zeilen 53–55 werden durch zwei typisierte Record-Konstanten und entsprechende `$derived`-Ausdrücke ersetzt.

**Vorher (Zeilen 53–55):**

```typescript
const tone = $derived(alert.kind === 'thunder' ? 'bad' : 'warn');
const toneColor = $derived(tone === 'bad' ? 'var(--g-bad)' : 'var(--g-warn)');
const iconKind = $derived<WIconKind>(alert.kind === 'thunder' ? 'thunder' : 'wind');
```

**Nachher:**

```typescript
const TONE_MAP: Record<string, 'bad' | 'warn'> = {
  thunder: 'bad',
  thunder_level: 'bad',
};
const tone = $derived<'bad' | 'warn'>(TONE_MAP[alert.kind] ?? 'warn');
const toneColor = $derived(tone === 'bad' ? 'var(--g-bad)' : 'var(--g-warn)');

const KIND_MAP: Record<string, WIconKind> = {
  thunder: 'thunder',
  thunder_level: 'thunder',
  wind: 'wind',
  wind_gust: 'wind',
  wind_change: 'wind',
  rain: 'rain',
  precipitation_sum: 'rain',
  precipitation_change: 'rain',
  snow: 'snow',
  snow_line: 'snow',
  sun: 'sun',
  temperature: 'sun',
  temperature_min: 'sun',
  temperature_max: 'sun',
  temperature_change: 'sun',
};
const iconKind = $derived<WIconKind>(KIND_MAP[alert.kind] ?? 'wind');
```

`toneColor` und alle Template-Stellen (`<WIcon kind={iconKind} ...>`) bleiben unverändert — sie binden bereits reaktiv an die geänderten `$derived`-Werte.

### 2. `molecules.test.ts` — Neuer Testfall

Den bestehenden `#372 AC-4`-Test um ein `KIND_MAP`-Mapping-Szenario erweitern oder einen eigenen `#417`-Test ergänzen, der per Source-Inspection prüft, dass `KIND_MAP` die relevanten Schlüssel enthält:

```typescript
test('#417: AlertRow KIND_MAP enthält alle erwarteten kind-Werte', () => {
  const ar = read('AlertRow.svelte');
  const expectedKinds = [
    'thunder', 'thunder_level',
    'wind', 'wind_gust', 'wind_change',
    'rain', 'precipitation_sum', 'precipitation_change',
    'snow', 'snow_line',
    'sun', 'temperature', 'temperature_min', 'temperature_max', 'temperature_change',
  ];
  for (const kind of expectedKinds) {
    assert.ok(ar.includes(`'${kind}'`), `KIND_MAP-Schlüssel '${kind}' fehlt in AlertRow.svelte`);
  }
});
```

### 3. LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `frontend/src/lib/components/molecules/AlertRow.svelte` | +18 / -2 | nein (Frontend-Asset) |
| `frontend/src/lib/components/molecules/molecules.test.ts` | +10 | nein (Frontend-Asset) |
| **Gesamt (zählend)** | **0** | **< 250 LoC-Limit** |

## Expected Behavior

- **Input:** `AlertRow`-Komponente mit `alert.kind` gesetzt auf einen beliebigen Backend-Metrik-Namen (z.B. `'rain'`, `'snow_line'`, `'wind_gust'`, `'temperature_min'`, `'thunder_level'`, oder unbekannte Werte)
- **Output:** `WIcon` rendert das semantisch passende Wetter-Symbol (`rain`→Regen-Icon, `snow`→Schnee-Icon, `sun`/`temperature*`→Sonne-Icon, `wind*`→Wind-Icon, `thunder*`→Gewitter-Icon). Tone-Farbe ist `--g-bad` für Gewitter-Arten, `--g-warn` für alle anderen.
- **Side effects:** Keine. Der Fix ist rein visuell. Keine Daten werden gelesen oder geschrieben. Kein Backend-Code betroffen.

## Acceptance Criteria

- **AC-1:** Given AlertRow mit `alert.kind = 'thunder'` / When variant='icon' gerendert / Then WIcon erhält kind='thunder' und nicht kind='wind'
  - Test: `molecules.test.ts` → Test `#417 AC-1/2/3/4/5` (KIND_MAP-Schlüsselprüfung)

- **AC-2:** Given AlertRow mit `alert.kind = 'rain'` / When variant='icon' gerendert / Then WIcon erhält kind='rain' und nicht kind='wind'
  - Test: `molecules.test.ts` → Test `#417 AC-1/2/3/4/5` (precipitation_sum-Schlüssel)

- **AC-3:** Given AlertRow mit `alert.kind = 'snow'` / When variant='icon' gerendert / Then WIcon erhält kind='snow' und nicht kind='wind'
  - Test: `molecules.test.ts` → Test `#417 AC-1/2/3/4/5` (snow_line-Schlüssel)

- **AC-4:** Given AlertRow mit `alert.kind = 'wind_gust'` (Backend-Metrik-Name) / When variant='icon' gerendert / Then WIcon erhält kind='wind' (korrektes Mapping via KIND_MAP)
  - Test: `molecules.test.ts` → Test `#417 AC-1/2/3/4/5` (wind_gust-Schlüssel)

- **AC-5:** Given AlertRow mit `alert.kind = 'temperature_min'` / When variant='icon' gerendert / Then WIcon erhält kind='sun' und nicht kind='wind'
  - Test: `molecules.test.ts` → Test `#417 AC-1/2/3/4/5` (temperature_min-Schlüssel)

- **AC-6:** Given AlertRow mit unbekanntem kind (z.B. `'foobar'`) / When variant='icon' gerendert / Then Fallback: WIcon erhält kind='wind', kein Crash
  - Test: `molecules.test.ts` → Test `#417 AC-1/2/3/4/5` (`?? 'wind'`-Fallback via KIND_MAP-Struktur)

- **AC-7:** Given AlertRow mit `alert.kind = 'thunder'` oder `'thunder_level'` / When gerendert / Then tone='bad' und toneColor='var(--g-bad)' (Gewitter-Kritikalität korrekt)
  - Test: `molecules.test.ts` → Test `#417 AC-7/8` (TONE_MAP + thunder_level-Schlüssel)

- **AC-8:** Given AlertRow mit allen anderen bekannten kinds (rain, snow, wind, temperature*) / When gerendert / Then tone='warn' und toneColor='var(--g-warn)' (Warn-Stufe korrekt)
  - Test: `molecules.test.ts` → Test `#417 AC-7/8` (TONE_MAP-Fallback)

## Known Limitations

- **KIND_MAP deckt nur bekannte Metrik-Namen ab:** Wenn das Backend neue Alert-Arten einführt, muss KIND_MAP manuell erweitert werden. Der `?? 'wind'`-Fallback verhindert Crashes, zeigt aber semantisch falsches Icon.
- **Keine Laufzeit-Warnung bei unbekanntem kind:** Die Komponente schweigt bei unbekannten Werten. Für Debugging könnte ein `console.warn`-Aufruf im Fallback-Pfad hilfreich sein — ist aber nicht Teil dieses Scopes.

## Out of Scope

- Änderungen an `WIconKind` oder `weatherUtils.ts`
- Neue Icon-Arten (z.B. `'pressure'`, `'humidity'`)
- Backend-seitige Alert-Kind-Normalisierung
- Änderungen an der `dot`- oder `plain`-Variante von AlertRow

## Changelog

- 2026-05-27: Initial spec erstellt. Behebt falsches Wind-Icon für Regen/Schnee/Sonne/Temperatur-Alerts und falschen `warn`-Tone für `thunder_level` durch Einführung von `KIND_MAP` + `TONE_MAP` in `AlertRow.svelte`. 2 Dateien, ~20 LoC, rein visuell.
