# Context: feat-2346-s2-kachel (#2346 Scheibe S2)

## Request Summary
Scheibe S2 von #2346: ein gemeinsamer Startseiten-Kachel-Baustein `SubscriptionKachel` für Trip und Ortsvergleich (Status, nächster Versand, letzter Versand, Kanäle in gleicher Anordnung); tote Bausteine löschen. S1 (Pendant-Sperre) ist in main (PR #2611). Spec und Grundkontext: `docs/specs/modules/feat_2346_cockpit_paritaet.md` (Abschnitt S2, AC-1 teilweise, AC-9) und `docs/context/feature-2346-cockpit-paritaet.md`.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/routes/_home/TripKachel.svelte` (103 Z.) | eigener `<a>` mit `data-testid="trip-card"`, zeigt Typ, Status, Name, Zeitraum, Etappenzahl, „Reports ✓" — wird ersetzt |
| `frontend/src/routes/_home/CompareKachel.svelte` (23 Z.) | Thin-Wrapper auf `SubscriptionCard kind="vergleich" compact` — wird ersetzt |
| `frontend/src/routes/_home/kachelActions.ts` | `compareKachelActions()` (nur „Bearbeiten") — von der neuen Kachel für beide kinds genutzt |
| `frontend/src/lib/components/organisms/SubscriptionCard.svelte` (266 Z.) | Kanäle (`!compact && vergleich`), Zeitplan und Fußzeile „zuletzt" nur `kind==='vergleich'` — kind-neutral machen; Props `nextSend?`, `lastSent?` |
| `frontend/src/routes/_home/cockpitHelpers.ts:128,141` | `reportChannels` / `heroKanaele` liefern Trip-Kanäle aus den Flags (#2422 S3) |
| `frontend/src/lib/components/compare/subscriptionHelpers.ts:211,232,269` | `presetTileScheduleLabel`, `relativeLastSent`, `presetChannels` (Vergleich) |
| `frontend/src/routes/+page.svelte:38-39,801,850` | Einbindung `CompareKachel` / `TripKachel` |
| `organisms/HomeHeroTrip.svelte`, `organisms/index.ts:29-30` | tot — löschen (`HomeHeroCompare.svelte` existiert im Ordner schon nicht mehr; nur noch Barrel-Eintrag/Verweise prüfen) |
| `molecules/CompareIdealRow.svelte`, `molecules/index.ts` | tot — löschen, Test `issue_491…:155` mitziehen |
| `.claude/hooks/pendant_gate.py` (`BEKANNTE_PAARE`) | Paar `CompareKachel`/`TripKachel` streichen, sobald die Dateien weg sind (Schrumpf-Test `tests/tdd/test_pendant_gate_bekannte_paare.py`) |

## Existing Patterns
- Thin-Wrapper auf `SubscriptionCard` (#2278), Aktionen über `actions`-Prop, `onclick`/`onAction` navigiert zum Hub.
- Trip-Kanäle immer aus `report_config`-Flags, nie aus `empfaenger` (#1452, AC-9).
- Keine eigene Fälligkeitsrechnung im Frontend (`deriveNextSend` bleibt unberührt); Props nullable, bis S4 liefert „—".
- `NextBriefing` (#1969) soll 1:1 in `nextSend` passen; bei `at===null` zeigt die Kachel `reason`.

## Dependencies
- Upstream: `tripStatus`, `reportSlotAktiv`, `subscriptionLifecycle`, `SubscriptionKebab`, `ladeReportZustand`.
- Downstream: Startseite (`+page.svelte`, `kachel-grid`-Klassen); e2e-Specs.

## Tests/Verwender (umhängen statt löschen)
Node-Tests: `compare_kachel_aktionen.test.ts`, `issue_578_molecules_organisms.test.ts:310-355`, `issue_489_compare_rows`, `issue_491_compare_detail`, `compare_channel_display_from_flags`, `issue_1273_s3_redirect_links`, `aktionsmodell_bausteine_ausloeser`, `report_slot_aktiv.test.ts:178-193`, `subscription_card.test.ts`.
**Playwright nutzt `data-testid="trip-card"` der Startseiten-Kachel:** `frontend/e2e/issue-294-home-kachel.spec.ts`, `startseite.spec.ts` (`trips/+page.svelte` und weitere e2e-Specs betreffen die `/trips`-Liste mit eigenem `trip-card` — in /20-analyse abgrenzen).

## Existing Specs
- `docs/specs/modules/feat_2346_cockpit_paritaet.md` (Status draft, Approval offen) — wird für S2 zugeschnitten und freigegeben.
- ADR-0097 Trip/Ortsvergleich-Code-Teilung.

## Risks & Considerations
- Sichtbare Änderung der Vergleichs-Kachel (bewusst, PO-bekannt).
- `trip-card`-testid in e2e-Specs: neuer Baustein muss die testid erhalten oder die Specs werden angepasst (Entscheidung in /20-analyse).
- Trip-Kachel war ein `<a href>` (Link, Mittelklick/Rechtsklick), `SubscriptionCard` ist `div role=button` — Rückschritt beim Link-Verhalten prüfen.
- Ohne S4 zeigen „nächster/letzter Versand" beim Trip „—"; Ticket bleibt bis S4 offen, keine Reste abspalten.
- LoC voraussichtlich > 250 ⇒ `loc_limit_override`.
- Lieferung per PR (`Refs #2346`, nicht `Closes`); `e2e_scope` nach jedem Commit im Worktree gegenlesen.

## Analysis

### Type
Feature (Rework, Frontend-only) — Scheibe S2 von #2346.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/organisms/SubscriptionCard.svelte` | MODIFY | Zweige `channels`/`scheduleText`/Fußzeile `kind==='vergleich'` (Z.~99-101, 207, 235) kind-neutral; Kanäle auch bei `compact`; Props `channels?`, `nextSend?`, `lastSent?` (nullable, „—") |
| `frontend/src/routes/_home/SubscriptionKachel.svelte` | CREATE | ein Baustein für beide kinds, wrappt `SubscriptionCard compact`, Aktion „Bearbeiten", Klick → Hub; Kanäle Trip aus `reportChannels(report_config)` |
| `frontend/src/routes/_home/TripKachel.svelte`, `CompareKachel.svelte` | DELETE | ersetzt |
| `frontend/src/routes/+page.svelte` (:38-39, :801, :850) | MODIFY | Einbindung; `nextBriefings` ist bereits geladen (:57-62, #1969) ⇒ `nextSend` kann schon jetzt gespeist werden |
| `frontend/src/routes/_home/kachelActions.ts` | MODIFY | Name `compareKachelActions` → kind-neutral |
| `organisms/HomeHeroTrip.svelte`, `organisms/index.ts:29-30` | DELETE/MODIFY | tot (`HomeHeroCompare.svelte` existiert nicht mehr) |
| `molecules/CompareIdealRow.svelte`, `molecules/index.ts` | DELETE/MODIFY | tot |
| `.claude/hooks/pendant_gate.py` (`BEKANNTE_PAARE`) + eingefrorene Menge in `tests/tdd/test_pendant_gate_bekannte_paare.py` / `test_pendant_gate.py` | MODIFY | Paare HomeHero* und Kachel streichen |
| Tests: `subscription_card.test.ts`, `compare_kachel_aktionen.test.ts`, `issue_578_molecules_organisms.test.ts:310-355`, `issue_489_compare_rows`, `issue_491_compare_detail:155`, `compare_channel_display_from_flags`, `report_slot_aktiv.test.ts:178-193`, `issue_1273_s3_redirect_links`, `aktionsmodell_bausteine_ausloeser` | MODIFY/DELETE | umhängen; neuer SSR-Test `SubscriptionKachel` (beide kinds gleiche Feldfolge, AC-9 Flags statt `empfaenger`) |

### Scope Assessment
- Files: ca. 15 (3 produktiv neu/geändert, 4 gelöscht, ~8 Tests)
- Estimated LoC: +250/-220 (ggf. `loc_limit_override 500`)
- Risk Level: MEDIUM — sichtbare Änderung der Vergleichs-Kachel (bewusst), Link-Verhalten der Trip-Kachel

### Technical Approach
1. `SubscriptionCard` kind-neutral: Kanäle-Zeile, Zeitplan-Zeile und Fußzeile für beide kinds, auch `compact`. Kanäle als Prop (`channels`) statt intern aus `presetChannels` — Trip-Kanäle liefert die Kachel via `reportChannels()` (Flags, nie `empfaenger`, #1452/AC-9).
2. `SubscriptionKachel` (routes/_home/) als einziger Wrapper; kind aus Aufruf (`activePresets` → vergleich, `otherTrips` → trip).
3. **Entscheidung `data-testid="trip-card"`:** wird NICHT übernommen. `startseite.spec.ts` und `issue-294-home-kachel.spec.ts` stehen nicht in `.github/ci_e2e_specs.txt` und gelten laut Spec als veraltet; der neue Baustein trägt `subscription-card-{id}` + `data-kind`. Die Specs werden minimal auf `[data-testid^="subscription-card-"][data-kind="trip"]` angepasst. Die `/trips`-Liste (`trips/+page.svelte`, eigenes `trip-card`) ist ein anderer Baustein und bleibt unberührt.
4. **Link-Verhalten:** Trip-Kachel war `<a href>`; `SubscriptionCard` ist `div role=button` mit `goto`. Lösung: Name optional als echter `<a href>` (Prop `href`), Karten-Klick bleibt `goto` — Mittel-/Rechtsklick bleibt erhalten, der Vergleich gewinnt den Link dazu.
5. **Nächster Versand:** `nextBriefings` (#1969) ist in `+page.svelte` schon geladen ⇒ `nextSend` per `formatNextBriefing` schon in S2 speisen (Trip und Vergleich); `lastSent` beim Vergleich `letzter_versand`, beim Trip „—" bis S4. Keine eigene Fälligkeitsrechnung.
6. Tote Bausteine löschen, `BEKANNTE_PAARE` + eingefrorene Test-Menge kürzen (Schrumpf-Test erzwingt das).

### Dependencies
Upstream: `tripStatus`, `reportSlotAktiv`, `subscriptionLifecycle`, `SubscriptionKebab`, `ladeReportZustand`, `formatNextBriefing`. Downstream: nur Startseite. Kein Backend, keine Persistenz, keine Schemaänderung.

### Open Questions
- [ ] Spec `feat_2346_cockpit_paritaet.md` ist `draft`; Freigabe der S2-ACs (AC-1 teilw., AC-9, AC-10, AC-16) steht aus — in /30-write-spec zuschneiden und um testid-Entscheidung, Link-Verhalten und `nextSend` schon in S2 ergänzen.
- [ ] Fresh-Eyes-Screenshot-Paar auf Staging nach Deploy.
