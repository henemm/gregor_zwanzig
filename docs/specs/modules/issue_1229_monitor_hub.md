---
entity_id: issue_1229_monitor_hub
type: feature
created: 2026-07-13
updated: 2026-07-13
status: draft
version: "1.0"
tags: [compare, hub, briefings, neutralisierung, frontend]
workflow: feat-1229-monitor-hub
---

# Compare-Hub — Briefing-Zeiten + Neutralisierung (#1229-Rest, Phase 2 von Epic #1230)

- **Issue:** #1229 (Phase 2 von Epic #1230) — Rest-Umfang nach der Ist-Vermessung vom 2026-07-13
- **Vorgänger:** #1231 (Korridor-Editor, Wertebereiche-Tab, live), #1232 (VersandTab-Organism im Editor, live — `docs/specs/modules/versand_tab_vergleich.md`)
- **Design-Quelle (1:1):** `claude-code-handoff/current/jsx/screen-compare-detail.jsx` (`CHub_`-Präfix), Mock-Werte `claude-code-handoff/current/jsx/mock-locations.jsx:123/148/173/197`
- **Typ:** Frontend-only (SvelteKit-Route `/compare/[id]`), KEINE Backend-Änderung

## Approval

- [ ] Approved

## Purpose

Der Compare-Hub (`/compare/[id]`) zeigt heute im Versand-Tab und im
Monitoring-Streifen noch die alte Rhythmus-/Zeitfenster-Sprache
(`presetScheduleLabel` → „Täglich HH–HH Uhr") und im Idealwerte-Bereich eine
Ranking-Formulierung („…Metriken bestimmen das Ranking"), obwohl das Preset
seit #1232 slot-basierte Briefing-Zeiten (Morgen/Abend, je an/aus + Uhrzeit)
trägt und das Produkt als stehender Monitor ohne Score/Ranking positioniert
ist (PO 2026-07-11). Diese Spec bringt den Hub auf die kanonische
Design-Wahrheit (`screen-compare-detail.jsx`): eine neue Stat „Briefings" mit
lesbaren Uhrzeiten, einen read-only Versand-Tab mit Edit-Absprung in den
Editor statt Inline-Rhythmus-Anzeige, neutralisierte Idealwerte-Copy und einen
aufgeräumten Vorschau-Dispatcher ohne erreichbaren Rang/Score-Pfad.

## Source

- **Files:**
  - `frontend/src/lib/components/compare/subscriptionHelpers.ts` — neue Funktion `presetBriefingTimesLabel()`
  - `frontend/src/lib/components/compare/CompareTabs.svelte` (800 Z.) — Stat, Versand-Tab, Idealwerte-Copy
  - `frontend/src/routes/compare/[id]/+page.svelte` — Mobile-Stat-Grid (Z.162-232)
  - `frontend/src/lib/components/compare/CompareEditor.svelte` — `?tab=`-Deep-Link für den Edit-Modus
  - `frontend/src/lib/components/molecules/CompareBriefingPreview.svelte` (34 Z.) — Dispatcher, telegram/sms-Zweige
  - `frontend/src/lib/components/compare/RecommendationBanner.svelte` (46 Z.) — DELETE (toter Code)
  - `frontend/src/lib/types.ts` (Z.387-410) — `RankingEntry`, `CompareResult.ranking` entfernen
- **Identifier:** `function presetBriefingTimesLabel`, `CompareTabs` (Svelte-Component), `switchTab` (CompareEditor.svelte:202), `CompareBriefingPreview`

## Estimated Scope

- **LoC:** S1 (Kern) ~185–210 · S2 (Neutralisierung Vorschau + Aufräumen) ~50–90 (beide innerhalb des 250-LoC-Standardlimits, kein Override nötig)
- **Files:** S1: 7 · S2: 5 (`CompareBriefingPreview.svelte`, `RecommendationBanner.svelte` DELETE, `issue_462.test.ts`, `issue_390_atomic_migration.test.ts`, `types.ts`)
- **Effort:** medium (S1), low (S2)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/specs/modules/versand_tab_vergleich.md` (#1232, live) | module | Liefert die 5 Slot-Felder (`morning_enabled/morning_time/evening_enabled/evening_time/end_date`) am `ComparePreset`, auf denen `presetBriefingTimesLabel()` aufbaut |
| `docs/specs/modules/issue_1231_korridor_editor.md` (#1231, live) | module | Editor-Tab-Struktur inkl. `?tab=`-Konvention (`compare/[id]/+page.svelte:32`), Vorbild für den Deep-Link-Fix in `CompareEditor.svelte` |
| `docs/specs/modules/issue_517_compare_hub.md` | module | Grundlagen-Spec des 6-Tab-Hubs (Tab-Testids `compare-detail-tab-*`) |
| `src/services/compare_slot_scheduler.py` | module | Backend-Versand ist bereits slot-basiert — keine Änderung nötig, aber Datenquelle der Zeiten |
| Epic #1230 (Konvergenz Trips/Compare) | workflow | Phase 2 dieses Epics; Phase 3 (#1250, Datenmodell/`briefings[]`) folgt separat |

## Implementation Details

### S1 — Kern

**1. Versand-Tab: Anzeige + Absprung, kein Inline-Edit.**
`CompareTabs.svelte:363-368` (`Card`-Sektion „Rhythmus & Vorausschau" mit
`DetailRow`n „Zeitplan"/„Zeitfenster"/„Nächster Versand") wird ersetzt durch
eine Sektion „Briefing-Zeiten" mit genau zwei read-only `DetailRow`s:

```
<Card padding={20}>
  <Eyebrow>Briefing-Zeiten</Eyebrow>
  <DetailRow label="Briefings" value={presetBriefingTimesLabel(preset)} right={<EditIcon onclick={goToEditVersand} />} />
  <DetailRow label="Nächster Versand" value={formatNextSend(nextSend)} divider="none" />
  <!-- Fix-Loop 1: formatNextSend/deriveNextSend statt presetScheduleLabel (F001, s. Changelog) -->
</Card>
```

Der Edit-Stift (`CHub_EditIcon`, JSX Z.428-434) hat im Design bewusst keinen
Inline-Edit-Handler — er navigiert zu `/compare/{preset.id}/edit?tab=versand`.
Kein neuer Hub-Save-Pfad entsteht (Full-Replace-PUT-Risiko von
`handleToggleActive` bleibt unberührt, wird NICHT kopiert/erweitert).

**2. Editor-Deep-Link `?tab=` nachrüsten.**
`CompareEditor.svelte:93` initialisiert `activeTab` aktuell fix mit
`$state<EditorTabId>('vergleich')`. Analog zum bestehenden Muster in
`compare/[id]/+page.svelte:32` (`page.url.searchParams.get('tab')`) liest die
Editor-Route beim Mount einen `?tab=`-Query-Parameter und initialisiert
`activeTab` damit, WENN der Wert einer bekannten `EditorTabId` entspricht
(`vergleich`/`orte`/`idealwerte`/`layout`/`versand`/`alarme`); bei fehlendem
oder unbekanntem Wert bleibt der bisherige Default `'vergleich'`. Dies gilt
NUR im Edit-Modus (Create-Wizard hat keine Preset-ID, `switchTab` bleibt dort
ungegated wie heute).

**3. Stat „Briefings" (Desktop + Mobile).**
Neue Helper-Funktion in `subscriptionHelpers.ts`:

```ts
/** ComparePreset → lesbares Briefing-Zeiten-Label ("Morgen 06:30 · Abend 18:00"). */
export function presetBriefingTimesLabel(preset: ComparePreset): string {
  const toHHMM = (t?: string) => (t ?? '').slice(0, 5);
  const parts: string[] = [];
  if (preset.morning_enabled) parts.push(`Morgen ${toHHMM(preset.morning_time)}`);
  if (preset.evening_enabled) parts.push(`Abend ${toHHMM(preset.evening_time)}`);
  return parts.length > 0 ? parts.join(' · ') : '—';
}
```

Format-Vorbild `mock-locations.jsx:123/148/173/197`: `"Morgen 06:30 · Abend 18:00"`
(beide aktiv), nur eine aktive Zeile bei nur-Morgen/nur-Abend, `"—"` wenn
beide aus. Backend liefert `HH:MM:SS` — Slice auf `HH:MM`.

Eingebaut als fünfte Stat im Monitoring-Streifen
(`CompareTabs.svelte:214-257`, zwischen „Nächster Versand" und „Zuletzt raus",
JSX-Reihenfolge Z.145) UND im Mobile-Stat-Grid
(`compare/[id]/+page.svelte:162-232`, eigenes 2×2-Grid — wird zu einem Grid
mit fünf Kacheln erweitert bzw. die bestehende `grid-cols-2`-Struktur nimmt
eine fünfte Card auf, Testid `compare-detail-stat-briefings` analog zu den
bestehenden Kacheln).

**4. Copy-Swap Idealwerte-SummaryCard.**
`CompareTabs.svelte:277` ersetzt `"{n} Metriken bestimmen das Ranking"` durch
den JSX-Zieltext (Z.165, 1:1):
`"{n} Metriken mit Idealbereich — im Briefing pro Wert markiert. Kein Score, kein Ranking."`

### S2 — Neutralisierung Vorschau + Aufräumen

**5. `CompareBriefingPreview.svelte` — dead branches entfernen.**
Der Dispatcher routet aktuell `channel === 'telegram'` auf `CompareChatBubble`
und `channel === 'sms'` auf `CompareSmsPreview` (V1-Molecule mit
`rank`+`score`, Z.15-20/48 dort) — diese Zweige werden aber im Hub NIE mit den
nötigen Props `profile`/`data` gemountet (`CompareTabs.svelte:514-519`
übergibt nur `profileId`/`channel`/`subscriptionName`/`emailView`), sodass die
oberste Bedingung `!profile || !data` faktisch immer greift und bereits heute
`ComparePreviewMissing` rendert. Die telegram/sms-Branches sind also toter
Code mit trügerischem Anschein von Funktionalität. Sie werden auf
`ComparePreviewMissing` umgelenkt (Branches entfernt bzw. zusammengeführt);
`CompareChatBubble.svelte`/`CompareSmsPreview.svelte` selbst bleiben als
Dateien unangetastet (siehe Known Limitations).

**6. `RecommendationBanner.svelte` löschen.**
46-Zeilen-Datei, nirgends importiert (verifiziert: kein Treffer in
`CompareTabs.svelte`, `CompareDetail.svelte`, `CompareEditor.svelte`). Zwei
Struktur-Tests referenzieren sie als Existenz-Prüfung und müssen mitgehen:
- `frontend/src/lib/components/compare/issue_462.test.ts:34` (Eintrag in
  `MIGRATED_FILES`, prüft Atomic-Design-Imports der Datei) — Zeile entfernen.
- `frontend/src/lib/components/compare/__tests__/issue_390_atomic_migration.test.ts:117`
  (Eintrag in `PAGE_LOCAL_COMPOSITES`, prüft nur Datei-Existenz) — Zeile
  entfernen.

**7. `RankingEntry`/`ranking`-Types entfernen.**
`frontend/src/lib/types.ts:387-393` (`interface RankingEntry`) und das
`ranking: RankingEntry[]`-Feld in `interface CompareResult` (Z.410) werden
gelöscht — kein Produktionscode liest diese Typen mehr, nachdem
`CompareSmsPreview`/`CompareChatBubble` im Hub unerreichbar sind (S2 Punkt 5).

## Expected Behavior

- **Input:** Aufruf von `/compare/{id}` (Übersicht/Versand/Vorschau-Tab) mit
  einem `ComparePreset`, das die 5 Slot-Felder aus #1232 trägt (ggf. `undefined`
  bei Alt-Presets vor der Migration); Klick auf den Edit-Stift im Versand-Tab;
  Navigation zu `/compare/{id}/edit?tab=versand`.
- **Output:** Monitoring-Streifen und Versand-Tab zeigen „Morgen HH:MM · Abend
  HH:MM" (bzw. Teilmenge/„—") statt Rhythmus-/Zeitfenster-Sprache; Idealwerte-
  Card zeigt die neutrale Copy ohne „Ranking"-Wort in Bezug auf
  Metrik-Bestimmung; die Editor-Route mit `?tab=versand` öffnet direkt den
  Versand-Tab; Vorschau-Tab zeigt bei telegram/sms-Kanal-Auswahl
  `ComparePreviewMissing` statt eines (unerreichbaren) Rang/Score-Renders.
- **Side effects:** Keine Persistenz-Änderung im Hub selbst (reine Anzeige +
  Absprung). `RecommendationBanner.svelte` verschwindet aus dem Repo,
  `RankingEntry`/`ranking`-Type verschwinden aus `types.ts` — beides ohne
  Laufzeitwirkung, da unreferenziert.

## Scope

### Affected Files (S1)

| File | Change | ~LoC |
|------|--------|------|
| `frontend/src/lib/components/compare/subscriptionHelpers.ts` | MODIFY: `presetBriefingTimesLabel()` | +15 |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY: Stat, Versand-Tab-Sektion, Copy-Swap | +35/-15 |
| `frontend/src/routes/compare/[id]/+page.svelte` | MODIFY: Mobile-Stat-Grid um „Briefings"-Kachel erweitert | +10 |
| `frontend/src/lib/components/compare/CompareEditor.svelte` | MODIFY: `?tab=`-Deep-Link-Init | +12 |
| `frontend/src/lib/components/molecules/CompareBriefingPreview.svelte` | MODIFY (S2, siehe unten) | — |
| `frontend/src/lib/components/compare/__tests__/issue_582_list_helpers.test.ts` | MODIFY: 4 Vitest-Fälle für `presetBriefingTimesLabel` | +30 |
| `frontend/e2e/compare-hub-briefing-times.spec.ts` | CREATE: erste Hub-Playwright-Spec | +70 |

### Affected Files (S2)

| File | Change | ~LoC |
|------|--------|------|
| `frontend/src/lib/components/molecules/CompareBriefingPreview.svelte` | MODIFY: telegram/sms-Zweige → `ComparePreviewMissing` | +2/-8 |
| `frontend/src/lib/components/compare/RecommendationBanner.svelte` | DELETE | -46 |
| `frontend/src/lib/components/compare/issue_462.test.ts` | MODIFY: Zeile 34 entfernen | -1 |
| `frontend/src/lib/components/compare/__tests__/issue_390_atomic_migration.test.ts` | MODIFY: Zeile 117 entfernen | -1 |
| `frontend/src/lib/types.ts` | MODIFY: `RankingEntry`/`ranking`-Feld entfernen | -8 |

### Slices

- **S1 (Kern):** Versand-Tab „Briefing-Zeiten" + Edit-Deep-Link, Stat „Briefings" Desktop+Mobile, Copy-Swap Idealwerte, Helper+Vitest+erste Hub-E2E.
- **S2 (Neutralisierung + Aufräumen):** `CompareBriefingPreview`-Dispatcher entschärfen, `RecommendationBanner`+`RankingEntry` entfernen.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Vitest (`issue_582_list_helpers.test.ts`): GIVEN ein Preset mit `morning_enabled=true, morning_time='06:30:00', evening_enabled=true, evening_time='18:00:00'` WHEN `presetBriefingTimesLabel(preset)` aufgerufen wird THEN ist das Ergebnis `"Morgen 06:30 · Abend 18:00"`.
- [ ] Vitest: GIVEN nur `morning_enabled=true` (evening aus) WHEN aufgerufen THEN ist das Ergebnis `"Morgen 06:30"` (kein „Abend"-Teil, kein Trenn-`·` ohne zweiten Teil).
- [ ] Vitest: GIVEN nur `evening_enabled=true` (morning aus) WHEN aufgerufen THEN ist das Ergebnis `"Abend 18:00"`.
- [ ] Vitest: GIVEN beide Slots aus (`morning_enabled=false, evening_enabled=false`) WHEN aufgerufen THEN ist das Ergebnis `"—"`.
- [ ] Playwright (`compare-hub-briefing-times.spec.ts`): GIVEN ein per API angelegtes Preset mit gesetzten Slot-Feldern WHEN die Hub-Übersicht besucht wird THEN zeigt die Stat `compare-detail-stat-briefings` den erwarteten Zeiten-String, sichtbar auf Desktop UND Mobile (`:visible`).
- [ ] Playwright: GIVEN der Versand-Tab ist offen WHEN die Sektion betrachtet wird THEN existieren KEINE DetailRows mit den Labels „Rhythmus & Vorausschau"/„Zeitplan"/„Zeitfenster" und der Text enthält NICHT das Muster `hour_from`-`hour_to` als Rohwert.
- [ ] Playwright: GIVEN der Versand-Tab ist offen WHEN der Edit-Stift bei „Briefings" geklickt wird THEN navigiert die Seite zu `/compare/{id}/edit?tab=versand` UND der Versand-Tab ist dort direkt aktiv (kein Zwischenklick nötig).
- [ ] Playwright: GIVEN die Editor-Route wird mit einem unbekannten Wert aufgerufen (`/compare/{id}/edit?tab=nonsense`) WHEN die Seite lädt THEN ist der Default-Tab (`vergleich`) aktiv, kein Fehler/leerer Bildschirm.
- [ ] Playwright: GIVEN die Übersicht ist offen WHEN die Idealwerte-SummaryCard betrachtet wird THEN enthält ihr Text „Kein Score, kein Ranking" UND NICHT mehr „bestimmen das Ranking".
- [ ] Playwright: GIVEN der Vorschau-Tab ist offen und Kanal „SMS" oder „Telegram" gewählt WHEN die Render-Fläche geprüft wird THEN erscheint `ComparePreviewMissing`-Markup, KEIN Rang- oder Score-Text (Negativ-Assertion auf Ziffer+Punkt-Präfix-Pattern).
- [ ] Playwright: GIVEN die Hub-Seite ist offen WHEN alle 6 Tabs durchgeklickt werden THEN existieren alle bestehenden `compare-detail-tab-{uebersicht,orte,idealwerte,layout,versand,vorschau}`-Testids unverändert.

### Fixtures

- Kern-Schicht: Vitest ohne Netz/Browser (reine Funktions-Assertions auf `presetBriefingTimesLabel`).
- Playwright: Staging, echte Preset-Anlage via `POST /api/compare/presets` (kein Mock), echter Klick-Pfad (Muster `versand-tab-vergleich.spec.ts`), `:visible`-Filter wegen Desktop+Mobile-Doppel-Mount.

## Acceptance Criteria

**AC-1:** Given ein Compare-Preset mit `morning_enabled=true/morning_time='06:30:00'` und `evening_enabled=true/evening_time='18:00:00'` / When die Hub-Übersicht (Desktop) besucht wird / Then zeigt die Stat „Briefings" im Monitoring-Streifen den Text „Morgen 06:30 · Abend 18:00".
  - Test: Playwright liest `compare-detail-stat-briefings` auf Desktop-Viewport.

**AC-2:** Given dasselbe Preset / When die Hub-Übersicht im mobilen Viewport besucht wird / Then zeigt die entsprechende Kachel im Mobile-Stat-Grid (`compare/[id]/+page.svelte`) denselben Zeiten-Text wie Desktop.
  - Test: Playwright, Viewport ≤899px, `:visible`-Filter auf dieselbe Testid.

**AC-3:** Given ein Preset mit nur `morning_enabled=true` (evening aus) bzw. nur `evening_enabled=true` (morning aus) bzw. beiden aus / When `presetBriefingTimesLabel()` aufgerufen wird / Then liefert die Funktion „Morgen HH:MM" bzw. „Abend HH:MM" bzw. „—", nie einen führenden/verwaisten Trennpunkt.
  - Test: Vitest, 3 Fälle in `issue_582_list_helpers.test.ts`.

**AC-4:** Given der Versand-Tab des Hubs ist geöffnet / When die Sektion oberhalb der Kanal-Karte betrachtet wird / Then heißt sie „Briefing-Zeiten" mit den zwei DetailRows „Briefings" und „Nächster Versand"; die Begriffe „Rhythmus & Vorausschau", „Zeitplan", „Zeitfenster" sowie ein roher `hour_from`–`hour_to`-Wert kommen dort NICHT mehr vor.
  - Test: Playwright, Text-Assertions auf Vorhandensein/Abwesenheit im Sektions-Container.

**AC-5:** Given der Versand-Tab zeigt die Sektion „Briefing-Zeiten" / When der Edit-Stift neben „Briefings" geklickt wird / Then navigiert die Anwendung zu `/compare/{id}/edit?tab=versand` und der Editor öffnet sich dort direkt mit aktivem Versand-Tab (kein zusätzlicher Klick nötig).
  - Test: Playwright prüft URL nach Klick + Sichtbarkeit des Versand-Tab-Panels ohne weitere Interaktion.

**AC-6:** Given die Editor-Route wird mit einem unbekannten oder fehlenden `?tab=`-Wert aufgerufen / When die Seite lädt / Then ist der bisherige Default-Tab (`vergleich`) aktiv, keine Fehlermeldung, kein leerer Tab-Inhalt.
  - Test: Playwright ruft `/compare/{id}/edit?tab=doesnotexist` und `/compare/{id}/edit` (ohne Parameter) auf, prüft aktiven Tab.

**AC-7:** Given die Idealwerte-SummaryCard in der Hub-Übersicht / When sie gerendert wird / Then lautet der Beschreibungstext „{n} Metriken mit Idealbereich — im Briefing pro Wert markiert. Kein Score, kein Ranking." — die vorherige Formulierung „…Metriken bestimmen das Ranking" erscheint nicht mehr.
  - Test: Playwright Text-Assertion auf die neue Formulierung, Negativ-Assertion auf die alte.

**AC-8:** Given der Vorschau-Tab ist offen und Kanal Telegram oder SMS ausgewählt / When die Render-Fläche geprüft wird / Then zeigt `CompareBriefingPreview` den `ComparePreviewMissing`-Zustand statt eines Rang/Score-Renders (der V1-Pfad in `CompareSmsPreview`/`CompareChatBubble` ist über den Hub nicht mehr erreichbar).
  - Test: Playwright wählt beide Kanäle nacheinander, prüft Abwesenheit von Rang-/Score-Markup und Anwesenheit des Missing-Hinweises.

**AC-9:** Given der Hub ist vollständig neutralisiert und aufgeräumt / When das Repository durchsucht wird / Then existiert `RecommendationBanner.svelte` nicht mehr, `RankingEntry`/das `ranking`-Feld an `CompareResult` sind aus `types.ts` entfernt, und die beiden Struktur-Tests (`issue_462.test.ts`, `issue_390_atomic_migration.test.ts`) referenzieren die Datei nicht mehr.
  - Test: Vitest/node:test-Lauf beider Struktur-Testdateien bleibt grün nach der Löschung (keine toten Referenzen mehr).

**AC-10:** Given die bestehenden sechs `compare-detail-tab-{uebersicht,orte,idealwerte,layout,versand,vorschau}`-Testids / When alle Tabs nacheinander angeklickt werden / Then sind alle sechs weiterhin vorhanden und funktionsfähig, unverändert gegenüber dem Stand vor dieser Änderung.
  - Test: Playwright klickt alle sechs Tabs, prüft je Panel-Sichtbarkeit.

## Known Limitations

- **KL-1 · Kurz-Labels außerhalb dieser Route bleiben unverändert:** `presetScheduleLabel`/`presetTileScheduleLabel`-Konsumenten außerhalb von `/compare/[id]` — insbesondere die Vergleichs-Liste/`CompareTile.svelte` („tägl. HH") und `AutoReportCard.svelte` — behalten vorerst die alte Rhythmus-Sprache. Diese Kurz-Copy ist nicht Teil des `screen-compare-detail.jsx`-Screens und daher nicht Gegenstand dieser Spec. Folge-Aufnahme in Sammel-Issue #1199, kein eigenes Issue.
- **KL-2 · Kein `briefings[]`-Array im Datenmodell:** Diese Scheibe führt KEIN neues Datenfeld ein — die flachen Slot-Felder (`morning_enabled/morning_time/evening_enabled/evening_time`) aus #1232 bleiben der Stand. Die Frage eines strukturierten `BriefingSubscription`-Modells gehört zu Phase 3 von Epic #1230 (#1250), nicht hierher.
- **KL-3 · `CompareSmsPreview.svelte`/`CompareChatBubble.svelte` bleiben als Dateien bestehen:** Design-Fidelity-Struktur-Tests (analog `issue_462.test.ts`) lesen ihren Dateiinhalt zur Atomic-Design-Prüfung. Nach S2 sind beide Komponenten über den Hub-Dispatcher (`CompareBriefingPreview.svelte`) nicht mehr erreichbar (toter, aber vorhandener Code) — kein Löschauftrag in dieser Spec.
- **KL-4 · E-Mail-Vorschau im Hub bleibt der Validator-iframe:** `CompareTabs.svelte:131-136` (`/api/_validator/compare-email-preview`) ist unverändert die Quelle der E-Mail-Vorschau; diese Spec berührt ausschließlich den telegram/sms-Zweig des Dispatchers.

## Edge Cases

| Fall | Verhalten |
|---|---|
| Alt-Preset ohne die 5 Slot-Felder (vor #1232-Migration, Felder `undefined`) | `presetBriefingTimesLabel` behandelt `morning_enabled`/`evening_enabled` als falsy → Ergebnis `"—"`, kein Crash bei fehlendem `morning_time`. |
| `morning_time`/`evening_time` im Backend-Format `HH:MM:SS` | Helper schneidet auf `HH:MM` (`.slice(0,5)`), kein Sekundenanteil in der Anzeige. |
| Doppel-Mount Desktop/Mobile derselben Route | Beide Zweige rufen denselben Helper mit demselben `preset`-Objekt auf → identischer Text; Playwright nutzt `:visible` zur Unterscheidung. |
| `?tab=` mit Groß-/Kleinschreibungs-Abweichung (`Versand` statt `versand`) | Zählt als unbekannter Wert (exakter String-Vergleich gegen `EditorTabId`-Werte) → Default-Tab, kein Crash. |
| Preset ohne aktiven Kanal, Vorschau-Tab auf „sms"/„telegram" | `ComparePreviewMissing` erscheint unabhängig vom Kanal-Status — Verhalten bereits heute so (kein neuer Zustand). |

## Out of Scope

- Backend-/API-Änderung jeglicher Art — Slot-Felder und Scheduler sind aus #1232 bereits live.
- Neuer Hub-Save-Pfad oder Inline-Edit der Briefing-Zeiten im Hub selbst (bleibt Editor-Aufgabe).
- Kurz-Copy in Vergleichs-Liste/`CompareTile`/`AutoReportCard` (KL-1, → #1199).
- `briefings[]`-Datenmodell-Reshape (KL-2, → #1250, Phase 3 von Epic #1230).
- LTComparePreview-Umbau des Vorschau-Tabs — JSX behält `CompareBriefingPreview`, kein Organism-Ersatz.
- Löschung von `CompareSmsPreview.svelte`/`CompareChatBubble.svelte` (KL-3).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Anzeige-/Copy-Anpassung und Dead-Code-Entfernung entlang einer bereits etablierten Datenquelle (#1232-Slot-Felder); kein neues Architekturmuster, kein neuer Save-Pfad, keine Schema-Änderung.

## Changelog

- 2026-07-13: Initial spec created
- 2026-07-13: Fix-Loop 1 nach Adversary-BROKEN (transparent, keine AC-Änderung):
  F001 (CRITICAL) — „Nächster Versand" im Versand-Tab nutzte `presetScheduleLabel`
  („Täglich 7–16 Uhr", roher Stundenwert, AC-4-Verstoß) → jetzt `formatNextSend`.
  F002 (MEDIUM, gleicher Screen, JSX Z.175-178) — Übersicht-Card „Versand" zeigte
  roh `hour_from–hour_to` (vorbestehend) → jetzt „Briefings … · nächster Versand …".
  Übersicht-Stat und Mobile-Stat „Nächster Versand" ebenfalls auf `formatNextSend`.
  E2E-Spec um Übersicht-Panel-Negativ-Assertions erweitert. Bewusste Ausnahme:
  `time_window`-API-Parameter im Validator-Preview-Request (nicht sichtbar, KL-4-Pfad).
