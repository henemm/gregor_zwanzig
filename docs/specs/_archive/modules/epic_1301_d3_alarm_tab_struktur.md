---
entity_id: epic_1301_d3_alarm_tab_struktur
type: module
created: 2026-07-19
updated: 2026-07-19
status: draft
version: "1.0"
tags: [frontend, alarme-tab, epic-1301, issue-1292]
---

# D3 — Alarm-Tab Struktur/Beschriftung

## Approval

- [ ] Approved

## Purpose

Der geteilte Alarm-Tab benennt seine Auslöser-Schalter irreführend („Wann Warnungen rausgehen" über einem An/Aus-Schalter) und lässt den Radar-Schalter verwaist am Tab-Ende stehen. D3 fasst die Auslöser-Schalter unter einer ehrlichen Überschrift zusammen und ordnet die Blöcke neu — rein strukturell/beschriftend, ohne Fachlogik-Änderung. Scheibe D3 von Epic #1301, beantwortet #1292 P2/P3/P5/P6.

## Source

- **File:** `frontend/src/lib/components/shared/AlarmeTab.svelte` (Render-Organism)
- **File:** `frontend/src/lib/components/shared/alarme-tab/alarmeTabSections.ts` (Reihenfolge)
- **Identifier:** `alarmeTabSections(context)`, Render-Block `official-warnings` / `radar`

## Estimated Scope

- **LoC:** ~40–80
- **Files:** 2 Produktiv (`AlarmeTab.svelte`, `alarmeTabSections.ts`) + 1 Test (`alarme_tab_sections.test.ts`)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `atoms/Eyebrow` | UI-Atom | Überschriften |
| `ChannelToggle` | UI-Baustein | die beiden Auslöser-Schalter |
| `alarme_tab_sections.test.ts` | Test (#1258 AC-9) | kodiert die Reihenfolge hart → mitziehen |

## Implementation Details

**Ist-Reihenfolge** (`alarmeTabSections`): `korridor-summary → official-warnings → metric-levels → channels → cooldown → quiet-hours → [radar (nur vergleich)] → sample`.

**Ziel-Reihenfolge:** `radar` rückt direkt hinter `official-warnings` (weiterhin nur bei `context="vergleich"`):
`korridor-summary → official-warnings → [radar (nur vergleich)] → metric-levels → channels → cooldown → quiet-hours → sample`.

**Beschriftung:**
- Eyebrow „Wann Warnungen rausgehen" entfällt.
- Neue Überschrift über der Auslöser-Gruppe, kontextabhängig:
  - `context="vergleich"` → **„Amtliche & Radar-Warnungen"**
  - `context="route"` → **„Amtliche Warnungen"** (kein Radar-Schalter vorhanden — ehrlich)
- Der Radar-Block behält keinen eigenen Eyebrow (hatte auch vorher keinen); er sitzt sichtbar als zweiter Schalter unter derselben Überschrift.

**Schalter-Labels bleiben unverändert:** „Amtliche Warnungen lösen Alert aus" (Testid `alerts-tab-official-alert-triggers-toggle`) und „Radar-Alarm" (Testid `alarme-radar-toggle`).

## Expected Behavior

- **Input:** derselbe `context`/`trip`/`wiz`-State wie heute.
- **Output:** neue Blockreihenfolge + neue Überschrift; identische Schalter-Verdrahtung.
- **Side effects:** keine — keine geänderten Felder, keine Persistenz-/Auslöse-Logik.

## Acceptance Criteria

- **AC-1:** Given der Alarm-Tab mit `context="vergleich"` / When er gerendert wird / Then erscheint der Radar-Schalter (`alarme-radar-toggle`) **direkt nach** dem Amtliche-Warnungen-Schalter (`alerts-tab-official-alert-triggers-toggle`) und **vor** dem Alarm-Schwellen-Block (`alarme-section-metric-levels`) — nicht mehr am Tab-Ende.
  - Test: Component-/Reihenfolge-Test prüft die Testid-Reihenfolge `official-warnings` → `radar` → `metric-levels`.

- **AC-2:** Given der Alarm-Tab / When er mit `context="vergleich"` gerendert wird / Then trägt die Auslöser-Gruppe die Überschrift „Amtliche & Radar-Warnungen"; When er mit `context="route"` gerendert wird / Then lautet sie „Amtliche Warnungen"; in beiden Fällen existiert der Text „Wann Warnungen rausgehen" nirgends mehr.
  - Test: Playwright rendert beide Kontexte, prüft sichtbaren Überschriftentext je Kontext und Abwesenheit von „Wann Warnungen rausgehen".

- **AC-3:** Given der Amtliche-Warnungen-Schalter und der Radar-Schalter / When ich sie im umgebauten Tab betätige / Then schalten sie exakt dieselben Felder wie vor D3 (`official_warnings.enabled` bzw. `wiz.radarAlertEnabled`), ohne Änderung an Persistenz oder Auslöse-Logik.
  - Test: Toggle betätigen, gebundenen State/PUT-Payload prüfen — gleiches Feld, gleicher Effekt wie Baseline.

- **AC-4:** Given der Bestands-Reihenfolge-Test `alarme_tab_sections.test.ts` (#1258 AC-9) / When D3 die Reihenfolge ändert / Then wird der Test auf die neue Reihenfolge gezogen und prüft weiterhin die Invariante „Radar erscheint ausschließlich bei `context='vergleich'`" sowie „route- und vergleich-Reihenfolge identisch bis auf `radar`".
  - Test: `alarmeTabSections('route')` ohne `radar`, `alarmeTabSections('vergleich')` mit `radar` an Position hinter `official-warnings`; Differenz genau `{radar}`.

- **AC-5:** Given der Trip-Kontext (`context="route"`) / When der Alarm-Tab gerendert wird / Then bleibt die Reihenfolge der übrigen Blöcke (Korridor-Auslöser, Alarm-Schwellen, Kanäle, Cooldown, Stille Stunden, Beispiel) unverändert und es erscheint kein Radar-Schalter.
  - Test: Reihenfolge-Test route liefert `korridor-summary, official-warnings, metric-levels, channels, cooldown, quiet-hours, sample`.

## Out of Scope

- Keine Änderung an Alarm-Auslöse-Fachlogik, Schwellwerten, Radar-Nachlieferung oder stillen Stunden (D1 erledigt).
- Kein Umbau der Korridor-Summary, der Kanal-Auswahl, Cooldown- oder Stille-Stunden-Karten.
- Keine neuen Felder, keine Persistenz-Migration.

## Known Limitations

- Die Überschrift „Amtliche & Radar-Warnungen" gilt nur im Vergleich; im Trip fehlt Radar bauartbedingt (kein Radar-Alarm für Touren) → dort „Amtliche Warnungen". Das ist gewollt, keine Inkonsistenz.
- `official-warnings` und `radar` bleiben zwei getrennte `.alarme-section`-Blöcke (Testid-Invariante bleibt erhalten); sie werden visuell unter eine Überschrift gruppiert, nicht technisch zu einem Feld verschmolzen.
