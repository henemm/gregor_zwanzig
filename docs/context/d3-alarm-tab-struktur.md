# Context: D3 — Alarm-Tab Struktur/Beschriftung

## Request Summary
Der geteilte Alarm-Tab (`AlarmeTab.svelte`, `context="route"|"vergleich"`) hat irreführende Beschriftungen und eine verstreute Anordnung der Auslöser-Schalter. D3 sortiert die Blöcke um und benennt sie ehrlich — Scheibe D3 von Epic #1301, beantwortet #1292 P2/P3/P5/P6.

## Request-Herkunft (#1292)
- **P2:** Eyebrow „Wann Warnungen rausgehen" suggeriert Schwellwerte, steht aber über einem An/Aus-Schalter.
- **P3:** Die „ersten beiden Boxen" seien falsch platziert (Formuliert **vor** D2 — damals zwei Amtliche-Warnungen-Boxen; D2 hat den Inhalt-Schalter bereits ausgelagert, es bleibt nur der Trigger).
- **P5:** „Amtliche Warnungen lösen Alert aus" braucht eine ehrliche eigene Überschrift.
- **P6:** „Radar-Alarm" steht verwaist ganz unten; soll zu den auslösenden Schaltern hoch. Der „überladene Text" ist laut Epic der Eyebrow davor, nicht der Radar-Schalter selbst → beim Neu-Texten erledigt.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/shared/AlarmeTab.svelte` | Render-Organism; Eyebrow „Wann Warnungen rausgehen" (Z. 236), official-warnings-Block (234–244), radar-Block (287–296) |
| `frontend/src/lib/components/shared/alarme-tab/alarmeTabSections.ts` | Reine Reihenfolge-Funktion `alarmeTabSections(context)` (Z. 12–26) — hier die Umsortierung |
| `frontend/src/lib/components/shared/__tests__/alarme_tab_sections.test.ts` | Testet die **aktuelle** Reihenfolge hart (AC-9/#1258) → muss mit der neuen Reihenfolge mitgezogen werden |
| `docs/specs/modules/issue_1258_alarme_tab_official_warnings.md` | Ursprungs-Spec des geteilten Tabs (AC-9 Reihenfolge, AC-10 Korridor-Summary) |

## Mount-Punkte (beide Kontexte betroffen — geteilter Baustein)
- **vergleich:** `compare/CompareEditor.svelte:1304,1466`, `compare/CompareTabs.svelte:1389`
- **route:** `trip-detail/AlarmeScheduleTab.svelte:51`

## Ist-Reihenfolge (nach D2)
1. `korridor-summary` — Eyebrow „Korridor-Auslöser" + Sprung-Link Wertebereiche
2. `official-warnings` — Eyebrow **„Wann Warnungen rausgehen"** → Toggle „Amtliche Warnungen lösen Alert aus"
3. `metric-levels` — Alarm-Schwellen-Tabelle
4. `channels` — Kanäle (+ Telegram-Kurzstil im vergleich)
5. `cooldown` — Cooldown-Karte
6. `quiet-hours` — Stille-Stunden-Karte
7. `radar` — **nur vergleich**, Toggle „Radar-Alarm", ohne Überschrift, verwaist
8. `sample` — Beispiel-Warnung

## Ziel-Reihenfolge (D3)
Trigger-Schalter (official + radar) zu **einem Block mit ehrlicher Überschrift** zusammenziehen; Radar rückt direkt neben den Amtliche-Warnungen-Trigger. Eyebrow „Wann Warnungen rausgehen" entfällt/wird ersetzt.

```
korridor-summary → [Auslöser-Block: official-warnings (+ radar bei vergleich)]
→ metric-levels → channels → cooldown → quiet-hours → sample
```

## Existing Patterns
- Reihenfolge ausschließlich über die Pure-Function `alarmeTabSections(context)` — Component-Test prüft die Testid-Reihenfolge (kein DOM-Snapshot nötig).
- Überschriften via `<Eyebrow>`-Atom.
- Kontext-Weiche `context === 'vergleich'` nur für radar/Telegram-Kurzstil.

## Dependencies
- **Upstream:** `alarmeTabSections.ts` (Reihenfolge), `atoms/Eyebrow`, `ChannelToggle`.
- **Downstream:** `alarme_tab_sections.test.ts` (hart kodierte Reihenfolge, AC-9), Playwright-E2E über die drei Mount-Punkte.

## Risks & Considerations
- **Geteilter Baustein:** Änderung wirkt auf Trip **und** Vergleich. Trip-Kontext hat keinen Radar — der Auslöser-Block enthält dort nur den Amtliche-Warnungen-Trigger; Überschrift muss für ein **und** zwei Schalter passen.
- **Bestandstest AC-9** kodiert die alte Reihenfolge → muss synchron aktualisiert werden (nicht löschen; er schützt die Kontext-Invariante Radar-nur-vergleich).
- **Wortlaut der neuen Überschrift** ist eine Design-/PO-Entscheidung → in die ACs zur Freigabe.
- Rein strukturell/beschriftend — **keine Fachlogik-Änderung** an Alarm-Auslösung, Persistenz oder Feldern (Out of Scope). `official_warnings.enabled`/`radarAlertEnabled` bleiben unverändert verdrahtet.
- Frontend-only, voraussichtlich < 250 LoC.
