---
entity_id: issue_520_organisms_barrel_completeness
type: module
created: 2026-06-01
updated: 2026-06-01
status: draft
version: "1.0"
tags: [frontend, atomic-design, organisms, issue-520, barrel]
---

<!-- Issue #520 — Organisms-Barrel vervollständigen: 5 trip-detail-Komponenten aufnehmen -->

# Issue #520 — Organisms-Barrel vervollständigen

## Approval

- [ ] Approved

## Purpose

Der Organisms-Barrel `frontend/src/lib/components/organisms/index.ts` exportiert nach Epic #471 vier Komponenten. Fünf weitere Svelte-Komponenten in `trip-detail/` sind bereits organismuswürdig (komplexe Zusammenbauten aus Atoms und Molecules), werden aber von Konsumenten noch direkt über `trip-detail/`-Pfade importiert. Diese Lücke verletzt das Barrel-Pattern: ein einheitlicher `$lib/components/organisms`-Importpfad ist die einzige erlaubte Quelle für Organisms. Mit diesem Issue werden die fünf Komponenten als Re-Exporte in den Barrel aufgenommen, ohne physische Dateibewegungen oder API-Änderungen.

## Source

- **File:** `frontend/src/lib/components/organisms/index.ts`
- **Identifier:** Barrel-Re-Exports (WeatherMetricsTab, ChannelPreviewBlock, ChannelPreviewCard, MetricGroup, MetricCheckbox)

> **Schicht-Hinweis:** Reine Frontend-Änderung (SvelteKit `frontend/src/lib/components/`). Keine Go/Python-Schicht betroffen.

## Estimated Scope

- **LoC:** ~20 netto (5 Export-Zeilen + 5 Test-Blöcke + 5 COMPONENTS.md-Zeilen)
- **Files:** 3
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `epic_471_organisms_layer.md` | Predecessor-Spec | Definiert Barrel-Pattern, Schicht-Regeln und Test-Struktur; dieses Issue baut direkt darauf auf |
| `frontend/src/lib/components/organisms/index.ts` | Zu ändernde Datei | Erhält 5 neue Re-Export-Zeilen |
| `frontend/src/lib/components/organisms/organisms.test.ts` | Zu ändernde Datei | Erhält 5 neue Export-Existence-Tests |
| `docs/design-system/COMPONENTS.md` | Zu ändernde Datei | Organisms-Tabelle (Zeilen 155–160) bekommt 5 neue Einträge |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | Organism-Quelle | Physische Quelle, wird per Re-Export aufgenommen (kein Move) |
| `frontend/src/lib/components/trip-detail/ChannelPreviewBlock.svelte` | Organism-Quelle (C2-Verstoß dokumentiert) | importiert `$lib/components/ui/card/index.js` — Verstoß bleibt unbehoben (Scope C3); nur Export-Existence getestet |
| `frontend/src/lib/components/trip-detail/ChannelPreviewCard.svelte` | Organism-Quelle | Physische Quelle, wird per Re-Export aufgenommen |
| `frontend/src/lib/components/trip-detail/MetricGroup.svelte` | Organism-Quelle | Physische Quelle, wird per Re-Export aufgenommen |
| `frontend/src/lib/components/trip-detail/MetricCheckbox.svelte` | Organism-Quelle (C2-Verstoß dokumentiert) | importiert `$lib/components/ui/horizon-chip/index.js` — Verstoß bleibt unbehoben (Scope C3); nur Export-Existence getestet |
| Issue #475 (pattern) | Referenz | ui/-Verstöße werden in separaten Folge-Issues behoben, nicht inline |

## Implementation Details

### Constraint-Übersicht

| Constraint | Beschreibung |
|---|---|
| C1 | Keine physischen Dateibewegungen — nur neue Re-Export-Zeilen in `organisms/index.ts` |
| C2 | Organisms sollen nur aus atoms/, molecules/ oder organisms/ importieren (kein ui/) |
| C3 | Keine API-Änderungen an den Svelte-Komponenten selbst |
| C2-Ausnahme | ChannelPreviewBlock und MetricCheckbox haben C2-Verstöße, werden aber gemäß C3 nicht angefasst; Verstöße sind dokumentiert, Fixes in Folge-Issues |

### Schritt 1: 5 Re-Exporte in `organisms/index.ts` ergänzen

```typescript
// Ergänzung am Ende von frontend/src/lib/components/organisms/index.ts
// Issue #520 — trip-detail Organisms aufnehmen
export { default as WeatherMetricsTab }  from '../trip-detail/WeatherMetricsTab.svelte';
export { default as ChannelPreviewBlock } from '../trip-detail/ChannelPreviewBlock.svelte';
export { default as ChannelPreviewCard }  from '../trip-detail/ChannelPreviewCard.svelte';
export { default as MetricGroup }         from '../trip-detail/MetricGroup.svelte';
export { default as MetricCheckbox }      from '../trip-detail/MetricCheckbox.svelte';
```

Kein physischer Move. Die `.svelte`-Dateien verbleiben in `trip-detail/`. Konsumenten werden nicht umgestellt (AC-2).

### Schritt 2: 5 Export-Existence-Tests in `organisms.test.ts` ergänzen

Für ChannelPreviewBlock und MetricCheckbox wird KEIN ui/-Import-Check durchgeführt (bekannte C2-Verstöße, Scope C3). Nur Export-Existence:

```typescript
// Ergänzung in frontend/src/lib/components/organisms/organisms.test.ts
// Issue #520 — neue Organisms
const issue520Organisms = [
  { name: 'WeatherMetricsTab',   path: '../trip-detail/WeatherMetricsTab.svelte' },
  { name: 'ChannelPreviewBlock', path: '../trip-detail/ChannelPreviewBlock.svelte' },
  { name: 'ChannelPreviewCard',  path: '../trip-detail/ChannelPreviewCard.svelte' },
  { name: 'MetricGroup',         path: '../trip-detail/MetricGroup.svelte' },
  { name: 'MetricCheckbox',      path: '../trip-detail/MetricCheckbox.svelte' },
];

describe('organisms — Issue #520: 5 neue Exports im Barrel', () => {
  it('index.ts re-exportiert alle 5 neuen Organisms', () => {
    const barrel = readFileSync(join(__dirname, 'index.ts'), 'utf-8');
    for (const o of issue520Organisms) {
      assert.ok(barrel.includes(o.name), `${o.name} fehlt im Barrel`);
    }
  });
});
```

Hinweis: WeatherMetricsTab, ChannelPreviewCard, MetricGroup erhalten zusätzlich den Standard-ui/-Import-Check (analog zu den 4 Epic-#471-Organisms). ChannelPreviewBlock und MetricCheckbox erhalten nur den Barrel-Existence-Check.

### Schritt 3: COMPONENTS.md Organisms-Tabelle um 5 Zeilen erweitern

In `docs/design-system/COMPONENTS.md`, Abschnitt `## 8 · Organisms`, die bestehende Tabelle (aktuell 4 Einträge) um 5 Zeilen ergänzen:

| Komponente | Import | Props (bekannt) | Was sie tut |
|---|---|---|---|
| `<WeatherMetricsTab>` | `$lib/components/organisms` | `trip`, `stage?` | Tab-Inhalt mit Wetter-Metrik-Auswahl für Trip-Detail-Ansicht. Physisch in `trip-detail/WeatherMetricsTab.svelte`. |
| `<ChannelPreviewBlock>` | `$lib/components/organisms` | `channel`, `layout` | Vorschau-Block für einen einzelnen Briefing-Kanal (E-Mail/SMS). Physisch in `trip-detail/ChannelPreviewBlock.svelte`. ⚠ C2-Verstoß (ui/card) — Folge-Issue offen. |
| `<ChannelPreviewCard>` | `$lib/components/organisms` | `channel`, `content` | Card-Wrapper für Kanal-Vorschau. Physisch in `trip-detail/ChannelPreviewCard.svelte`. |
| `<MetricGroup>` | `$lib/components/organisms` | `group`, `metrics`, `onChange` | Gruppen-Sektion in der Metrik-Auswahl (z.B. Temperatur, Niederschlag). Physisch in `trip-detail/MetricGroup.svelte`. |
| `<MetricCheckbox>` | `$lib/components/organisms` | `metric`, `checked`, `onChange` | Einzelne Metrik-Checkbox mit Horizon-Chip-Darstellung. Physisch in `trip-detail/MetricCheckbox.svelte`. ⚠ C2-Verstoß (ui/horizon-chip) — Folge-Issue offen. |

### Schritt 4: Build-Verifikation

```bash
cd frontend && npm run build
```

Muss ohne Fehler durchlaufen. Anschließend organisms.test.ts via `node --test` ausführen.

### Nicht in diesem Issue (explizite Ausschlüsse)

- **C2-Auflösung für ChannelPreviewBlock** (`ui/card`): eigenes Folge-Issue nötig (Atom für Card-Primitive fehlt noch).
- **C2-Auflösung für MetricCheckbox** (`ui/horizon-chip`): eigenes Folge-Issue nötig (HorizonChip existiert nur in `ui/`, kein Atom vorhanden).
- **Konsumenten-Migration** auf `$lib/components/organisms`: kein erzwungenes Umstellen bestehender Imports (AC-2).
- **PresetRail**: keine `PresetRail.svelte` im Repo — kein Scope.

## Expected Behavior

- **Input:** keiner zur Laufzeit (reine Barrel-Erweiterung).
- **Output:** `import { WeatherMetricsTab, ChannelPreviewBlock, ChannelPreviewCard, MetricGroup, MetricCheckbox } from '$lib/components/organisms'` liefert alle 5 neuen Organisms; `npm run build` ist grün; alle 5 neuen Organisms erscheinen in der COMPONENTS.md-Tabelle; organisms.test.ts meldet 0 Fehler.
- **Side effects:** Bestehende Konsumenten mit direkten `trip-detail/`-Imports funktionieren weiterhin unverändert. Keine Laufzeit-Änderung an den Svelte-Komponenten selbst.

## Acceptance Criteria

**AC-1:** Given die Datei `frontend/src/lib/components/organisms/index.ts` / When man ihren Inhalt prüft / Then sind WeatherMetricsTab, ChannelPreviewBlock, ChannelPreviewCard, MetricGroup und MetricCheckbox als Re-Exporte enthalten (min. 5 neue Export-Zeilen gegenüber Epic-#471-Stand).
  - Test: (populated after /tdd-red)

**AC-2:** Given bestehende Konsumenten-Dateien, die `trip-detail/`-Pfade direkt importieren / When man ihre Import-Zeilen prüft / Then sind keine dieser Dateien verändert worden — alle direkten `trip-detail/`-Imports bleiben unberührt.
  - Test: (populated after /tdd-red)

**AC-3:** Given `docs/design-system/COMPONENTS.md`, Abschnitt `## 8 · Organisms` / When man die Tabelle liest / Then sind alle 9 Organisms aufgelistet (4 aus Epic #471 + 5 neue aus Issue #520).
  - Test: (populated after /tdd-red)

**AC-4:** Given `frontend/src/lib/components/organisms/organisms.test.ts` / When man alle Tests via `node --test` ausführt / Then laufen alle Tests grün — inklusive 5 neuer Export-Existence-Tests für die Issue-#520-Organisms.
  - Test: (populated after /tdd-red)

## Known Limitations

- ChannelPreviewBlock (`trip-detail/ChannelPreviewBlock.svelte`) importiert `$lib/components/ui/card/index.js` — verletzt die Schicht-Regel C2. Der Verstoß ist bekannt und dokumentiert; er wird nicht in diesem Issue behoben (C3-Constraint). Ein separates Folge-Issue ist nötig, sobald ein Card-Atom in `atoms/` verfügbar ist.
- MetricCheckbox (`trip-detail/MetricCheckbox.svelte`) importiert `$lib/components/ui/horizon-chip/index.js` — gleiches Muster wie ChannelPreviewBlock. HorizonChip existiert derzeit nur in `ui/`; Folge-Issue abhängig von HorizonChip-Atom-Migration.
- Der physische Speicherort der `.svelte`-Dateien bleibt in `trip-detail/` — `organisms/` ist kein eigenständiger Ordner mit allen Quellen (gewolltes Barrel-Pattern).
- Konsumenten importieren nach diesem Issue weiterhin aus `trip-detail/` — eine einheitliche Migrations-Kampagne ist ein separates Folge-Issue.

## Changelog

- 2026-06-01: Initial spec created (Issue #520, Organisms-Barrel vervollständigen, 5 trip-detail-Komponenten)
