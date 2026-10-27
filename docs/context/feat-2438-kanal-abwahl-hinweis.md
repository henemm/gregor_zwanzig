# Context: feat-2438-kanal-abwahl-hinweis

## Request Summary
Issue #2438 (Scheibe S2b von #2422, im Epic #2507): Im Werte-Reiter kann ein Kanal-Reiter Metriken nur *abwählen*. Was global aus ist, erscheint in keinem Kanal (ADR-0050 Regel 1–3). Der Editor sagt das nicht. Gewünscht ist ein Hinweis im Editor (Befund B6 aus #2422). Geteilter Baustein Trip/Vergleich (`context`), UI-Änderung mit Fresh-Eyes-Blick und Abnahme des Wortlauts. B9 ist NICHT mehr Teil (S2a, erledigt).

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2Reihenfolge.svelte` | Rendert Reihenfolge-Liste und Gruppe „Aus in diesem Kanal“ (`wm2-aus-gruppe`, Z. 177–179) — natürlicher Ort für den Hinweis |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | Einbindung über `LayoutTab` (Z. ~1700); `onRestoreMetric` (Z. 832) wirkt nur im aktiven Kanal; Kanal-Sicht Z. 353–361 (global abgewählt erscheint in keiner Liste) |
| `frontend/src/lib/components/shared/layout-tab/LTCapNote.svelte` + `ltChannels.ts` (`ltCapNoteText`) | Bestehendes Muster für einen geteilten Hinweistext: Text als reine, testbare Funktion in `ltChannels.ts`, Darstellung in eigener Komponente |
| `frontend/src/lib/components/shared/layout-tab/LayoutTab.svelte` | Geteilter Rahmen mit `context="route"\|"vergleich"` |
| `docs/adr/0050-metrik-kaskade-verfeinerung-nicht-ersetzung.md` | Begründet die Regel (Grundauswahl = Maximum, Kanal nur abwählen) |
| `docs/specs/modules/fix_2422_einstellung_gleich_auslieferung.md` | Mutter-Spec; B6 Z. 43, Scheibe S2 Z. 60 |

## Existing Patterns
- Hinweistexte werden als reine Funktion in `ltChannels.ts` gehalten und separat gerendert (`ltCapNoteText` → `LTCapNote`), testbar ohne Svelte-Renderharness. Gleiches Muster für den neuen Text.
- Testanker per `data-testid` (`wm2-…`).
- Bestehende Tests rund um die Aus-Gruppe: `__tests__/channelOffGroupListBuilding.test.ts`; E2E: `e2e/kanal-grenzen-und-hinweise.staging.spec.ts`, `e2e/kanal-abwahl-bleibt-reversibel.staging.spec.ts`.

## Dependencies
- Upstream: `metricById`, `offColumns`, aktiver Kanal (`activeChannel`) aus `WeatherMetricsTab`.
- Downstream: Trip-Editor UND Ortsvergleich-Editor binden denselben Reiter ein (Teilungs-Invariante) — der Hinweis muss in beiden erscheinen, keine Compare-Sonderkomponente.

## Existing Specs
- `docs/specs/modules/layout_tab_route.md`, `layout_tab_vergleich.md`, `compare_weather_metrics_tab.md`, `fix_1719_s3_aus_ist_ein_zustand.md`

## Risks & Considerations
- Wortlaut ist PO-Abnahme (Spec-Freigabe).
- Nur Daten/Erklärung, keine Handlungsempfehlung (PO-Vorgabe) — Hinweis beschreibt, was gilt, nennt nicht „du solltest …“.
- Lesbarkeit/Kontrast (WCAG-AA, `--g-ink-4` nicht für Hilfetext); Handybreite 320/375 px.
- Offene Frage für Analyse: Hinweis dauerhaft sichtbar oder nur, wenn global etwas abgewählt ist? Und Position: unter der Aus-Gruppe vs. am Kopf der Reihenfolge-Karte.
- Gilt für alle Kanäle gleich (alle vier gleichrangig); Telegram-Kurzform folgt SMS — Hinweis darf dort nicht widersprechen.

## Analysis

### Type
Feature (reine UI-Erklärung, keine Verhaltens-/Datenänderung)

### Befund
`WeatherV2Reihenfolge.svelte` ist der EINE geteilte Baustein und wird viermal eingebunden:
Trip-Kanalsicht (`WeatherMetricsTab.svelte` ~1729, `offColumns={activeChannelSections.off}`),
Vergleich-Übersicht (~1538, `compareChannelSections.off`), Vergleich-Ausblick
(`CompareOutlookLayoutControls.svelte` 257) und globale Grundauswahl (~1690, ohne `offColumns`).
Die Gruppe „Aus in diesem Kanal" (`wm2-aus-gruppe`) wird nur gerendert, wenn `offColumns !== undefined`,
also exakt in den Kanal-Sichten. `splitChannelMetricsForDisplay(buckets.primary, kanal.primary)`
liefert „aus" = Grundauswahl MINUS aktiv; global Abgewähltes steht in keiner Liste (die Kanalsicht
kennt „global aus" nicht).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/layout-tab/ltChannels.ts` | MODIFY | Reine Funktion für den Hinweistext, analog `ltCapNoteText` |
| `frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2Reihenfolge.svelte` | MODIFY | Hinweis-Zeile (`data-testid="wm2-aus-hinweis"`) in `wm2-aus-gruppe` |
| `frontend/src/lib/components/shared/__tests__/kanal_abwahl_hinweis.test.ts` | CREATE | Textfunktion + Rendering in beiden `context`-Werten |
| `frontend/e2e/kanal-grenzen-und-hinweise.staging.spec.ts` | MODIFY | Hinweis sichtbar in Trip- UND Ortsvergleich-Editor, 375 px |

### Scope Assessment
- Dateien: 3–4, ca. +60 LoC (unter 250-Limit)
- Risiko: NIEDRIG — kein Datenmodell-/Persistenzeingriff, keine Kanal-Logik

### Technical Approach
- Hinweis im geteilten Baustein → erscheint automatisch in Trip UND Vergleich, kein Compare-Eigenbau.
- Text als reine Funktion in `ltChannels.ts` (Muster `ltCapNoteText`/`LTCapNote`).
- **Sichtbarkeit dauerhaft** in jeder Kanal-Sicht, nicht bedingt: die Kanalsicht kennt die global abgewählten Metriken nicht; ein bedingter Hinweis bräuchte neue Datenführung. Die Regel gilt unabhängig davon, ob gerade etwas fehlt.
- **Position:** direkt unter der Gruppe „Aus in diesem Kanal", auch bei leerer Gruppe sichtbar.
- **Darstellung:** Kontrast ≥ 4.5:1 (nicht `--g-ink-4`), umbrechend bis 320 px; reine Beschreibung, keine Handlungsempfehlung.
- **Wortlaut-Vorschlag (PO-Abnahme in /30):** „Ein Kanal zeigt höchstens, was in der Grundauswahl gewählt ist. Was dort fehlt, erscheint in keinem Kanal." Begriff „Grundauswahl" in /30 an die UI-Beschriftung angleichen.
- Kein Widerspruch zu Telegram-Kurzform (folgt SMS): Text nennt keine Kanal-Zuordnung, gilt für alle vier gleich.

### Dependencies
- Upstream: `offColumns`-Prop (vorhanden), ADR-0050 Regel 1–3
- Downstream: Trip- und Ortsvergleich-Editor; bestehende Tests `channelOffGroupListBuilding.test.ts`, `kanal-abwahl-bleibt-reversibel.staging.spec.ts` dürfen nicht brechen
- Wächter: Fresh-Eyes-Inspector (UI-Änderung)

### Open Questions
- [ ] PO: Wortlaut des Hinweises (Freigabe in /30)
