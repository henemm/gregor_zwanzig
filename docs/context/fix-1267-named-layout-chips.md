# Context: fix-1267-named-layout-chips

## Request Summary

Issue #1267 (Prod-Audit 2026-07-16, Befund 4, `[triage:po]`, Priorität 4a): Der Layout-Tab der Compare-Hub-Detailseite (`/compare/[id]` → Tab „Layout") zeigt pro Kanal (EMAIL/TELEGRAM) nummerierte Zahlen-Chips „1", „2", … statt benannter Spalten-Chips. Design-Soll (`claude-code-handoff/current/jsx/molecules.jsx:1236-1254`, Komponente `CompareLayoutRow`) zeigt echte Spaltennamen als Chips unter einem fett gesetzten Kanal-Namen + mono Constraint-Unterzeile. Laut PO-Memo „DER ursprüngliche Auslöser der Rest-Inventur — wurde in S8c nur neu gerahmt, nie ersetzt".

**Wichtige Klärung (aus Screenshot + bestehendem Hint-Text bestätigt):** Die Spalten im Compare-Kontext sind **Orte**, nicht Metriken. Der Section-Header im Layout-Tab sagt bereits wörtlich: „Metrik-Zeilen · Orte sind die Spalten — der Renderer kappt je Kanal" (`CompareTabs.svelte:1064`). Die im JSX-Vorbild verwendeten Beispielnamen „Neuschnee", „Wind" sind generische Platzhalter der Komponentenbibliothek (`molecules.jsx` ist keine Compare-spezifische Datei) — für Compare müssen die Chips echte **Ortsnamen** zeigen, gekappt auf das Kanal-Budget.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/molecules/CompareLayoutRow.svelte` | Ist-Zustand: Prop `cols: number`, rendert `chipIndices = [1..cols]` als reine Zahlen-Pills (Zeile 22-23, 57-59). Label nur `channel.toUpperCase()` mono, keine Bold-Name + Constraint-Unterzeile wie im Design. |
| `frontend/src/lib/components/compare/CompareTabs.svelte:1051,1067` | Zwei Call-Sites (Mobile `dense` + Desktop), übergeben `cols={channelChipCount(CHANNEL_COLS[ch], preset.location_ids.length)}` — eine reine Zahl, kein Namens-Array. |
| `frontend/src/lib/components/compare/CompareTabs.svelte:187-201` | `resolvedLocations = $derived(currentLocationIds.map((id, idx) => ({rank, loc: locationById.get(id)})))` — liefert bereits Ortsobjekte mit `.name` in der aktuellen Reihenfolge. Genau die Datenquelle, die für benannte Chips gebraucht wird. |
| `frontend/src/lib/components/compare/channelChipCount.ts` | `channelChipCount(budget, locationCount): number` — reine Zahlen-Kappungslogik (Issue #1097/#1232). Für benannte Chips muss die gleiche Kappung auf ein Namens-Array angewendet werden (z.B. `names.slice(0, count)`), nicht nur auf die Zahl. |
| `frontend/src/lib/components/compare/CompareTabs.svelte:576-583` | `CHANNEL_COLS` (aus `CHANNEL_COL_BUDGET`) + `LAYOUT_LIMIT_PILLS`/`LAYOUT_LIMIT_PILLS_MOBILE` — bereits vorhandene Konstanttexte „Email · alle Spalten" etc., die als Vorbild für eine evtl. neue `constraint`-Prop pro Kanal dienen können. |
| `claude-code-handoff/current/jsx/molecules.jsx:1004,1006,1236-1272` | Design-Soll: `COMPARE_CHANNEL_LABEL`/`COMPARE_CHANNEL_CONSTRAINT`-Maps + `CompareLayoutRow({channel, cols=[], dense})` mit fettem Namen + mono Constraint-Unterzeile (`head`) und `cols.map(c => <chip>{c}</chip>)` (`chips`). SMS-Sonderfall (`cols.length===0`) unverändert „flach · ohne Spalten". |
| `frontend/src/lib/components/molecules/issue_489_compare_rows.test.ts:128-163` | Bestehende Kern-Tests (AC-3a-e) für `CompareLayoutRow` — Source-Wächter, prüfen u.a. Regex `cols\s*===?\s*0` (Zeile 143-149). Muss beim Wechsel auf `cols.length === 0` mit angepasst werden, sonst falsch-rot. Keine anderen Tests hier hängen an der Zahlen-Semantik. |
| `frontend/src/lib/components/compare/__tests__/compare_hub_fidelity.test.ts:57-63` | Prüft nur, dass `CompareLayoutRow` mobil mit `dense`-Prop verwendet wird (Regex auf `<CompareLayoutRow[^>]*\bdense\b/s`) — bleibt unberührt, prüft nicht den Inhalt von `cols`. |
| `docs/specs/modules/issue_489_compare_row_molecules.md` | Ursprüngliche Spec zu #489 — dokumentiert `CompareLocationRow` und `CompareIdealRow` vollständig, der `CompareLayoutRow`-Abschnitt fehlt/ist unvollständig. Bestätigt: der numerische `cols`-Vertrag war nie vollständig gegen das JSX spezifiziert, seit Einführung ein Rest-Bug. |
| `frontend/src/lib/components/molecules/CompareLocationRow.svelte` | Referenzmuster für Ortsnamen-Rendering (Rang-Badge + Name + Höhe) — bereits vorhandenes, funktionierendes Ortsnamen-Pattern in derselben Komponentenfamilie. |
| `frontend/src/lib/components/ui/pill/Pill.svelte` | `Pill`-Atom, `tone`-Prop (`accent`/`default`/…) — unverändert weiter nutzbar, nur der Chip-Inhalt (Text) ändert sich von Zahl zu Ortsname. |

## Existing Patterns

- **Budget-Kappung:** `channelChipCount(budget, count)` kappt eine Zahl nach unten (Issue #1097/#1232). Für benannte Chips: dieselbe Kappungslogik, aber auf ein Array angewandt (`names.slice(0, channelChipCount(budget, names.length))` oder äquivalent) — kein neues Kappungskonzept nötig.
- **SMS-Sonderfall:** `channel==='sms' && cols===0` → Hint-Text „flach · ohne Spalten" statt Chips. Bleibt strukturell gleich, nur die Bedingung wechselt von `cols===0` (Zahl) zu `cols.length===0` (Array).
- **Trip/Compare-Teilung (CLAUDE.md-Pflicht):** `CompareLayoutRow` ist compare-eigen (Layout-Tab zeigt Kanal×Spalten-Matrix, ein Compare-spezifisches Konzept ohne 1:1-Trip-Pendant — Trips haben keine „Orte als Spalten"-Struktur). Kein Trip-Pendant vorhanden oder erwartet; keine Verletzung der Teilungs-Invariante zu prüfen.
- **Erstes Chip = accent-Tone:** Bestehende Konvention (`idx===0 ? 'accent' : 'default'`) bleibt unverändert erhalten, auch mit Namen statt Zahlen.

## Dependencies

- **Upstream:** `preset.location_ids` (Reihenfolge bestimmt Chip-Reihenfolge), `resolvedLocations`/`locationById` (liefert `.name`), `CHANNEL_COL_BUDGET` (Kanal-Budget), `channelChipCount` (Kappungslogik).
- **Downstream:** Keine — `CompareLayoutRow` wird ausschließlich in `CompareTabs.svelte` (2 Stellen: Mobile `dense`, Desktop) verwendet, keine weiteren Konsumenten.

## Existing Specs

- `docs/specs/modules/issue_489_compare_row_molecules.md` — Ursprungs-Spec der Komponente, `CompareLayoutRow`-Abschnitt unvollständig (kein vollständiger Vertrag für `cols`-Typ dokumentiert).
- `docs/specs/modules/feat_1256_s8c_hub_fidelity.md` — Spec zum Layout-Tab-Rahmen (Section-Header, Limit-Pillen), behandelt NICHT den Chip-Inhalt selbst (nur Rahmen/Bündel laut AC-1/AC-2).

## Analysis

### Type
Bug (GitHub-Label `bug`, PO-Audit-Befund — Ist-Zustand weicht sichtbar vom Design-Soll ab).

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/molecules/CompareLayoutRow.svelte` | MODIFY | Prop `cols: number` → `cols: string[]`; `isSmsFlat` von `cols===0` auf `cols.length===0`; Chips rendern `cols.map((name,i)=>...)` statt `chipIndices`; Kopfzeile auf JSX-Vorbild umgestellt: fetter Kanal-Name (interne Label-Map, z.B. `email→Email`) + mono Constraint-Unterzeile (interne Constraint-Map, z.B. `email→'alle Spalten'`) statt mono-uppercase Kanal-Kürzel — analog `COMPARE_CHANNEL_LABEL`/`COMPARE_CHANNEL_CONSTRAINT` in `molecules.jsx:1004,1006`, als interne Konstanten in der Komponente (kein neuer Prop, deckt sich mit JSX-Vorbild) |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | Neue `$derived`-Ableitung der Ortsnamen aus `resolvedLocations`, gekappt per bestehendem `channelChipCount`; beide `CompareLayoutRow`-Call-Sites (Zeile 1051, 1067) erhalten das Namens-Array statt der reinen Zahl |
| `frontend/src/lib/components/molecules/issue_489_compare_rows.test.ts` | MODIFY | AC-3c-Regex (`cols\s*===?\s*0`) an `cols.length === 0` anpassen; ggf. AC-3e-Assertion um Namensinhalt ergänzen |

**Bestätigt durch Explore-Agent (unabhängige Zweitprüfung):** Keine Playwright-E2E-Tests matchen die Zahlen-Chips „1"/„2" als Text — kein E2E bricht. Einzige weitere Testdatei mit Bezug (`compare_hub_fidelity.test.ts`) prüft nur die `dense`-Prop-Verwendung per Regex, nicht den Chip-Inhalt. `channelChipCount.ts` bleibt unverändert (reine Zahlen-Kappung wird weiterhin genutzt, nur auf die Array-Länge angewendet — kein neuer Helper nötig).

### Scope Assessment
- Files: 3 (keine neuen Dateien)
- Estimated LoC: ~40-50 (+/-)
- Risk Level: LOW (rein UI-intern, ein einziger Konsument, keine E2E-Kollision bestätigt)

### Technical Approach

1. `CompareLayoutRow.svelte`: Typ-Vertrag ändern auf `cols: string[]`. SMS-Sonderfall-Bedingung wird `channel.toLowerCase() === 'sms' && cols.length === 0`. Chips-Loop rendert `{#each cols as name, idx (idx)}<Pill tone={idx===0?'accent':'default'}>{name}</Pill>{/each}` — Tone-Konvention (erstes Chip accent) bleibt unverändert. Zusätzlich (PO-Entscheid, volle Design-Parität): Kopfzeile auf fetten Kanal-Namen + mono Constraint-Unterzeile umstellen, analog `COMPARE_CHANNEL_LABEL`/`COMPARE_CHANNEL_CONSTRAINT` aus `molecules.jsx` — als interne Konstanten in der Komponente (kein neuer Prop nötig, `channel` allein reicht als Lookup-Key).
2. `CompareTabs.svelte`: Ortsnamen aus der bereits vorhandenen `resolvedLocations`-Ableitung (Zeile 187-201, `{rank, loc}` in `currentLocationIds`-Reihenfolge) ziehen, `loc?.name` filtern, dann mit der bestehenden `channelChipCount(CHANNEL_COLS[ch], namesLength)`-Zahl kappen (`names.slice(0, count)`). Kein neuer Helper — reine Wiederverwendung der bestehenden Kappungslogik auf ein Array statt auf `preset.location_ids.length`.
3. Bestehenden Test `issue_489_compare_rows.test.ts` AC-3c auf den neuen Vertrag (`cols.length === 0`) ummünzen — keine neue Testdatei (Namensregel: Verhalten statt Issue-Nummer, Datei existiert bereits für dieselbe Komponente).

### Dependencies
- Upstream: `resolvedLocations`/`locationById` (liefert `.name`), `CHANNEL_COL_BUDGET`, `channelChipCount` (unverändert wiederverwendet).
- Downstream: keine (einziger Konsument ist `CompareTabs.svelte`).

### Open Questions
- [x] **GEKLÄRT (PO):** Zeilenkopf-Stil (fetter Kanal-Name + Constraint-Unterzeile) wird MIT umgesetzt, nicht nur der Chip-Inhalt. Begründung: `claude-code-handoff/current/jsx/screen-compare-detail.jsx:260` — die reale Bildschirm-Komposition (nicht nur die generische Molecule-Definition in `molecules.jsx`) verwendet `CompareLayoutRow` bereits mit einer Namens-Liste (`cols={sub.layout[ch] || []}`) inklusive Kopfzeilen-Stil. Das ist der verbindliche Design-Bauplan für diesen Tab — volle JSX-Parität, keine Design-Rückfrage nötig. Die Redundanz zur oberen Pillen-Leiste (`LAYOUT_LIMIT_PILLS`) wird bewusst in Kauf genommen (Design-Vorgabe).

## Risks & Considerations

- **Kein Trip-Pendant-Risiko:** Da `CompareLayoutRow` compare-eigen bleibt (keine Trip-Analogie), entfällt die sonst verpflichtende Prüfung „hätte das geteilt sein müssen".
- **Bestehender Test-Vertrag ändert sich:** `issue_489_compare_rows.test.ts` AC-3c prüft `cols===0`-Regex im Source — die Anpassung auf `cols.length===0` ist eine legitime Vertragsänderung im Rahmen des Bug-Fixes, keine neue Testdatei nötig (Namensregel: Verhalten, nicht Issue-Nummer — Datei bleibt, da sie schon existiert).
- **Kanal-Reihenfolge/Deckelung:** SMS bleibt bei `budget=0` weiterhin ohne Chips (Hint-Text) — unverändert vom aktuellen Verhalten, nur der Zahlen→Namen-Wechsel bei EMAIL/TELEGRAM ist neu.
- **Header-Umfang (Bold-Name + Constraint-Unterzeile):** Das JSX-Vorbild (Zeile 1236-1245) zeigt zusätzlich zum Chip-Fix auch einen anderen Head-Stil (fett statt mono-uppercase, + Constraint-Unterzeile pro Zeile). Der Screenshot-Ist-Zustand zeigt aktuell nur mono-uppercase Labels ohne Unterzeile — das ist zwar Teil der zitierten JSX-Zeilen, aber NICHT der Kern der Bug-Beschreibung im Issue-Titel („nummerierte Zahlen-Chips statt benannter Spalten"). Muss in der Spec-Phase geklärt werden: nur Chip-Inhalt fixen, oder auch Head-Stil parität herstellen (Redundanz zu den bereits vorhandenen `LAYOUT_LIMIT_PILLS` oben im Tab beachten).
