# Context: rework-3399-s2-kopie

Scheibe **S2** von Issue #3399. Spec: `docs/specs/modules/rework_3399_vorlage_aufloesung.md` (Abschnitt „Kopie beim Anlegen (S2)", AC-5). Gesamtkontext und Analyse: `docs/context/rework-3399-vorlage-aufloesung.md`. S1 (Lader + Alarme-Reiter) ist live (PR #3407).

## Request Summary
„Vergleich als Kopie anlegen" (`/compare/new?from=<id>`) übernimmt die Vorlage der Quelle künftig aus der Server-Auflösung (`POST /api/ampel/aufloesung` → `resolve_entwurf`) statt aus der Frontend-Rangfolge `vorlageIdFuer`. Scheitert die Auflösung, startet der Editor ohne Vorlagen-ID (Anlege-Voreinstellung `STANDARD_VORLAGE`), alle übrigen Felder der Quelle bleiben übernommen, keine Fehlerseite.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/compare-new/compareNewVorlage.ts:30-66` | `feldsatzAusVorlage(preset, locations)`; `vorlageId` heute über `vorlageIdFuer(…, JEDE_VORLAGE)`. Neu: dritter Parameter `vorlageId: string \| null`; `null` ⇒ Feld weglassen (Standard bleibt). `JEDE_VORLAGE` und der Import von `vorlageIdFuer` entfallen |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte:111-131` | Prop `vorlage`; `untrack(() => feldsatzAusVorlage(vorlage, locations))` einmalig beim Start. Neu: Prop `vorlageId` und Weitergabe |
| `frontend/src/routes/compare/new/+page.server.ts` | lädt die Quelle (`ladeVorlage`, fail-soft) parallel zu Orten/Profil. Neu: nach dem Laden der Quelle `loeseAmpelnAuf(client, [eintragAusAbo(vorlage)])` gegen die Go-API mit dem Sitzungs-Cookie; jeder Fehler ⇒ `vorlageId: null` |
| `frontend/src/routes/compare/new/+page.svelte` | reicht `data.vorlageId` an den Editor |
| `frontend/src/lib/components/shared/wetter-tab/ampelAufloesung.ts` | `loeseAmpelnAuf(client: {post<T>(path, body)}, eintraege)`, `eintragAusAbo(abo)` (ampel, preset_name, profil). Wirft bei jedem Fehler. Kein Browser-Import ⇒ serverseitig nutzbar |
| `frontend/src/lib/server/apiBase.ts` | `apiBase()` für die Go-Basis-URL |
| `internal/handler/ampel_aufloesung.go` | Go prüft Anmeldung (Cookie) und reicht an Python durch; unverändert |

## Existing Patterns
- Serverseitiger Abruf mit Cookie-Header und fail-soft (`ladeVorlage` in derselben Datei, `profileLoader.ts`).
- Startwert-Muster: Editor übernimmt Vorlage einmalig per `untrack`, kein `$effect` (#2277 S2c AC-10).
- Tests mit echtem Python `resolve_entwurf` per Subprozess (`shared/wetter-tab/__tests__/wetterTabDaten.ts:107-130`, genutzt in `vorlagen_id_lader_3399.test.ts`).

## Dependencies
- Upstream: `POST /api/ampel/aufloesung` (Go → Python), `ampelAufloesung.ts`.
- Downstream: nur der Anlege-Editor des Ortsvergleichs (Startwert `vorlageId` → Reiter Wetter, Speicher-Payload `display_config.ampel.template`).

## Existing Specs
- `docs/specs/modules/rework_3399_vorlage_aufloesung.md` (S2, AC-5)
- `docs/specs/modules/feat_2277_s2c_compare_from_vorlage.md` (Kopie aus Vorlage, AC-10 Startwert einmalig)

## Betroffene Tests
- `frontend/src/lib/components/compare-new/__tests__/compareNewVorlage.test.ts` (Signatur, Fälle mit ID und mit `null`)
- `frontend/src/lib/components/compare-new/__tests__/anlegen_ohne_profil_3198.test.ts:220-245` (AC-5 aus #3198: heute Regeltest „profil wintersport ⇒ wintersport"; künftig Referenz echtes `resolve_entwurf`)
- `frontend/src/lib/components/compare/feat3298_vergleich_ohne_altfelder.test.ts:292-295` (Aufrufe `feldsatzAusVorlage(mit, orte)` nachziehen)
- ggf. `src/routes/compare/__tests__/compare_new_mounts_progressive_editor.test.ts`, `shared/__tests__/compare_new_editor_postet_einmal.test.ts` (Props)

## Risks & Considerations
- **Load-Funktion testbar machen:** der Auflösungsschritt sollte als reine Hilfsfunktion (Client injizierbar) aus `+page.server.ts` herausgezogen werden, damit der Kern-Test echtes Python als Client nutzt und den Fehlerfall (Client wirft) prüft — ohne Mock-Theater.
- **Kein Request ohne Quelle:** ohne `?from=` oder bei ungültiger Quelle kein Auflösungsaufruf, `vorlageId: null`.
- **Reihenfolge:** Auflösung braucht die Quelle ⇒ sequentiell nach `ladeVorlage`, Orte/Profil bleiben parallel.
- **Parität:** `eintragAusAbo` übergibt `preset_name`, wie bisher `vorlageIdFuer` in `feldsatzAusVorlage` — kein Verhaltenswechsel bei gültigen Daten. Unbekannte Vorlage fällt im Server auf „allgemein" (früher `JEDE_VORLAGE` ⇒ unbekannte ID wurde übernommen): kleine, gewollte Änderung.
- **Mandantentrennung:** Endpunkt liest keinen Nutzerbestand; Cookie des Nutzers wird durchgereicht, kein `"default"`.
- Scope: 4 Produktdateien, ~60–100 LoC — innerhalb der Grenzen.

## Analysis

### Type
Feature (Rework-Scheibe S2, ADR-0127 Nr. 3). Sichtbar: Kopie übernimmt die Server-Vorlage der Quelle; bei Auflösungsfehler Anlege-Voreinstellung statt geratener Rangfolge.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/compare-new/compareNewVorlage.ts` | MODIFY | `feldsatzAusVorlage(preset, locations, vorlageId: string \| null)`: ID gesetzt ⇒ übernehmen, `null` ⇒ Feld weglassen (Standard `STANDARD_VORLAGE` greift). Neu `vorlageIdDerQuelle(client, preset): Promise<string \| null>` = `loeseAmpelnAuf(client, [eintragAusAbo(preset)])[0].vorlage_id`, jeder Fehler ⇒ `null` (wirft nie). `JEDE_VORLAGE` + `vorlageIdFuer`-Import entfallen |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | MODIFY | Prop `vorlageId?: string \| null` (Default `null`), an `feldsatzAusVorlage` im bestehenden `untrack` |
| `frontend/src/routes/compare/new/+page.server.ts` | MODIFY | nach `Promise.all`: Quelle vorhanden ⇒ `vorlageIdDerQuelle(fetchClient, vorlage)`; `fetchClient.post` = `fetch(API()+path, {method:'POST', headers (Cookie), body})`, nicht-OK ⇒ throw. Rückgabe `vorlageId` (ohne Quelle `null`, kein Aufruf) |
| `frontend/src/routes/compare/new/+page.svelte` | MODIFY | `vorlageId={data.vorlageId}` |
| Tests | MODIFY | `compareNewVorlage.test.ts`, `anlegen_ohne_profil_3198.test.ts:220-255`, `feat3298_vergleich_ohne_altfelder.test.ts:292-295`, `compare_new_editor_postet_einmal.test.ts:148` (Signatur/Props) |

### Scope Assessment
- 4 Produktdateien, ca. 50–80 LoC netto; Tests ca. 80 LoC.
- Risk Level: LOW (nur Anlege-Startwert eines Ortsvergleichs, keine Speicher-Payload-Form ändert sich, Go/Python unverändert).

### Technical Approach
Auflösungs-Helfer als reine, injizierbare Funktion in `compareNewVorlage.ts` (kein Browser-/SvelteKit-Import, node-testbar). Kern-Tests (RED) mit echtem `resolve_entwurf` über `aufloesungPost` aus `shared/wetter-tab/__tests__/wetterTabDaten.ts`:
1. `vorlageIdDerQuelle` mit Quelle `profil: wintersport` ⇒ Ergebnis gleich Python-Referenz; Quelle `ampel.template: wassersport` ⇒ `wassersport`; Client wirft ⇒ `null`.
2. `feldsatzAusVorlage(…, 'wassersport').vorlageId === 'wassersport'`; mit `null` ⇒ `vorlageId` nicht gesetzt, übrige Felder (Name, Orte, Region, Versand) unverändert übernommen.
3. Editor mit `vorlage` + `vorlageId` aus Python ⇒ POST `ampel.template` = Server-Vorlage; mit `vorlageId: null` ⇒ POST `ampel.template` = `allgemein`, Name/Orte der Quelle übernommen.
Live-Test `frontend/e2e/rework-3399-kopie.spec.ts` (AC-5) gegen Staging: Kopie eines Vergleichs mit Vorlage ≠ allgemein zeigt im Reiter Wetter dieselbe Vorlage.
Kein Zwei-Nutzer-Test (Endpunkt liest keine Nutzerdaten, siehe Spec), Cookie wird durchgereicht.

### Dependencies
`loeseAmpelnAuf`/`eintragAusAbo` (`ampelAufloesung.ts`), `POST /api/ampel/aufloesung`, `STANDARD_VORLAGE`-Default in `compareFeldsatzStandard`.

### Befunde gegen den Plan
- Spec nennt für S2 keinen Helfer; er gehört in die ohnehin geänderte `compareNewVorlage.ts` (keine 5. Datei), damit die Load-Funktion schlank und der Fehlerpfad ohne SvelteKit testbar bleibt.
- Unbekannte Vorlagen-ID der Quelle wurde bisher wörtlich übernommen (`JEDE_VORLAGE`); künftig fällt sie im Server auf „allgemein" — gewollt (AC-9-Logik).

### Open Questions
Keine (AC-5 steht in der Spec, Freigabe über diesen Workflow; technische Details entschieden).
