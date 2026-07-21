---
entity_id: issue_504_wachhund_to_alerts
type: module
created: 2026-06-02
updated: 2026-06-02
status: draft
version: "1.0"
tags: [terminology, ui-text, rename]
---

# Issue #504 — Begriff „Wachhund" → „Alarm-Schwellen"

## Approval

- [ ] Approved

## Purpose

Der Begriff „Wachhund-Schwellen" war nie vom Product Owner beabsichtigt — er wurde von einer KI erfunden. Der sichtbare UI-Text der Alert-Rules-Karte im Trip-Überblick wird auf das offizielle Design-System-Vokabular (`"Alarm-Schwellen"`) umgestellt. Kein Logic-Change.

## Source

- **File:** `frontend/src/lib/components/trip-detail/TripOverview.svelte`
- **File:** `frontend/src/lib/components/trip-detail/TripOverview.issue487.test.ts`
- **Docs:** `docs/specs/modules/issue_487_trip_detail_overview_cards.md`
- **Docs:** `docs/design-system/COPY.md`

## Estimated Scope

- **LoC:** ~8 (Source), ~10 (Docs)
- **Files:** 2 Source + 2 Docs
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `DetailCard` | Svelte-Atom | Empfängt `title`-Prop — kein Change dort |

## Implementation Details

### Änderungen in TripOverview.svelte

```svelte
<!-- VORHER -->
// Karte 2: Alert Rules — „Wachhund-Schwellen"
<DetailCard
  title="Wachhund-Schwellen"
  ...
/>

<!-- NACHHER -->
// Karte 2: Alert Rules — „Alarm-Schwellen"
<DetailCard
  title="Alarm-Schwellen"
  ...
/>
```

### Änderungen in TripOverview.issue487.test.ts

Test-Beschreibungen (keine Logik):
- `'Karte "Wachhund-Schwellen" braucht testid="card-alerts"'` → `'Karte "Alarm-Schwellen" braucht testid="card-alerts"'`
- `'Karte "Wachhund-Schwellen" muss einen Link zu "#alerts" haben'` → `'Karte "Alarm-Schwellen" muss einen Link zu "#alerts" haben'`
- `test('nutzt alert_rules für Wachhund-Schwellen-Karte', ...)` → `test('nutzt alert_rules für Alarm-Schwellen-Karte', ...)`

### Änderungen in Docs

- `docs/specs/modules/issue_487_trip_detail_overview_cards.md`: `"Wachhund-Schwellen"` → `"Alarm-Schwellen"` (Titel, AC-3, Code-Beispiel, Sektionsüberschrift)
- `docs/design-system/COPY.md`: Sektionsname `"Verbotene Worte (Drift-Wachhund)"` → `"Verbotene Worte (Terminologie-Drift)"`

### Begründung für „Alarm-Schwellen"

Design-System COPY.md definiert: **„Alarm"** = Schwellwert-Überschreitung, sofortiger Trigger.
Die Karte zeigt genau diese Schwellwerte. Eyebrow und ActionText nutzen bereits „Alarmregeln" — der Titel „Alarm-Schwellen" ist komplementär und nicht redundant.

## Expected Behavior

- **Input:** Trip mit `alert_rules`-Array
- **Output:** Karte im Trip-Überblick zeigt `title="Alarm-Schwellen"` (war: `"Wachhund-Schwellen"`)
- **Side effects:** keine — rein kosmetisch

## Acceptance Criteria

**AC-1:** Given Trip-Überblick-Tab wird geladen, When die Alert-Karte gerendert wird, Then ist der sichtbare Kartentitel `"Alarm-Schwellen"` und NICHT `"Wachhund-Schwellen"`.

**AC-2:** Given die Datei `TripOverview.svelte`, When nach dem String `"Wachhund"` gesucht wird, Then findet sich kein Treffer (weder im Kommentar noch im Template-Code).

**AC-3:** Given die Datei `TripOverview.issue487.test.ts`, When nach dem String `"Wachhund"` gesucht wird, Then findet sich kein Treffer in Test-Beschreibungen.

## Known Limitations

- Historische Context-Docs und Artefakte (`docs/context/`, `docs/artifacts/`) behalten `"Wachhund"` als historische Artefakte — kein Aufräumen nötig.
- `docs/specs/user_stories_foundation.md` nutzt „Wachhund" als **Metapher** in fließendem Text (nicht als UI-Label) — bleibt unverändert.

## Changelog

- 2026-06-02: Initial spec created (Issue #504)
