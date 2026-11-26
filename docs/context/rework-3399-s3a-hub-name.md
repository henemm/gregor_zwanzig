# Context: rework-3399-s3a-hub-name

Scheibe **S3a** von Issue #3399. Spec: `docs/specs/modules/rework_3399_vorlage_aufloesung.md` (Abschnitt „S3a – Name und Hub-Übersicht", AC-2, AC-9 Teil Hub). Gesamtanalyse: `docs/context/rework-3399-vorlage-aufloesung.md`. S1 (Lader + Alarme-Reiter, PR #3407) und S2 (Kopie beim Anlegen, PR #3409) sind live.

## Request Summary
Die Karte „Wetter" (Wertebereiche) in der Hub-Übersicht eines Ortsvergleichs zeigt als Titel den Vorlagennamen. Heute rechnet ihn `aboVorlagenName` mit der Frontend-Rangfolge `vorlageIdFuer` (ampel.template → profil → „allgemein", ignoriert `preset_name`). Künftig kommt die ID aus der Server-Auflösung (`POST /api/ampel/aufloesung` → `resolve_entwurf`); solange die Antwort aussteht und bei Fehler steht „—", nie „Allgemein".

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/shared/wetter-tab/vorlageName.ts:34-46` | `aboVorlagenName(lang, abo, vorlagen?)` mit `vorlageIdFuer`. Ziel laut Spec: `aboVorlagenName(lang, vorlageId \| null)` ⇒ Name oder „—" |
| `frontend/src/lib/components/shared/hub-uebersicht/hubUebersichtModell.ts:309-321` | `wertebereicheKarte(preset, vorlagen, alt)` setzt `titel: aboVorlagenName(get(locale), preset, vorlagen)`; `deriveVergleichKennzahlen(preset, status, briefing, orte, vorlagen?, alt?)` (Z. 323-354) |
| `frontend/src/lib/components/shared/hub-uebersicht/HubUebersicht.svelte:67-95` | lädt `/api/templates` und Katalog in `onMount`, baut `modell` per `$derived`. Neu: Vorlagen-ID per Lader |
| `frontend/src/lib/components/shared/alarme-tab/aboVorlageId.svelte.ts` | Runen-Verdrahtung „Abo → Lader → ID" aus S1 (`erstelleAboVorlageId(quelle, client)`, `extern`-Testhaken, Abo-Wechsel ⇒ null). Wiederverwendbar für den Hub (kontextfrei) |
| `frontend/src/lib/components/shared/wetter-tab/vorlagenIdLader.ts` | S1-Lader, modulweiter Cache je Eintrag (AC-6), Ticket, wirft nie |
| `frontend/src/lib/components/shared/AlarmeTab.svelte:193` | Vorbild der Einbindung: `erstelleAboVorlageId(() => ({ abo: trip ?? preset, extern }), api)` |

## Weitere Aufrufer von `aboVorlagenName` (gehören zu S3b, nicht S3a)
- `frontend/src/lib/components/organisms/SubscriptionCard.svelte:99`
- `frontend/src/routes/compare/+page.svelte:89` (Vergleichsliste)

## Existing Patterns
- Runen-Modul für Laufzeit-Verdrahtung mit Testhaken `extern` (S1 F001, `abo_vorlage_id_laufzeit_3399.test.ts`).
- Kern-Tests mit echtem Python `resolve_entwurf` per Subprozess (`wetter-tab/__tests__/wetterTabDaten.ts:107-130`, `aufgeloestVon`, `aufloesungPost`).
- Modell-Funktionen bleiben rein (Eingaben herein, kein Laden im Modell); Laden im Svelte-Baustein.

## Dependencies
- Upstream: `POST /api/ampel/aufloesung` (unverändert), `vorlagenIdLader.ts`, `aboVorlageId.svelte.ts`.
- Downstream: nur der Titel der Wetter-Karte im Vergleichs-Hub (Desktop-Karte und mobile Pfeil-Zeile, beide aus `modell.wertebereicheKarte`). Kein Speicher-Payload, keine Kanäle.

## Existing Specs
- `docs/specs/modules/rework_3399_vorlage_aufloesung.md` (S3a, AC-2, AC-9)
- `docs/specs/modules/feat_2682_hub_uebersicht_geteilt.md` (Hub-Übersicht geteilt)

## Betroffene Tests
- `shared/hub-uebersicht/__tests__/hub_uebersicht_vorlagenrang_2988.test.ts` (laut Spec Ort der AC-2/AC-9-Fälle)
- `compare/__tests__/compare_hub_fidelity.test.ts:86-90` (Quelltext-Check „aboVorlagenName( im Modell")
- `compare/__tests__/vergleich_hub_sprache.test.ts:294`, `compare/feat3298_vergleich_ohne_altfelder.test.ts:259` (Aufrufe nachziehen)
- weitere Treffer prüfen: `vorlage_statt_profil_2796.test.ts`, `wertebereiche_karte_2988.test.ts`, `s3a2794_teil4b_uebersicht.test.ts`, `hub_uebersicht_verdrahtung_laufzeit.test.ts`, `s3a2794_teil4b_befunde.test.ts`, `p5c_ableitung_hub_orte_ausgabe.test.ts`, `reiter_sprunglinks_nur_neue_kennungen.test.ts`

## Risks & Considerations
- **Signatur-Konflikt mit S3b:** Ändert S3a die Signatur von `aboVorlagenName`, brechen SubscriptionCard und Vergleichsliste (S3b-Dateien). Entweder die beiden Aufrufer in S3a minimal mitziehen (überschreitet den S3a-Rahmen, nimmt S3b vorweg) oder in S3a eine neue ID-basierte Namensfunktion ergänzen und die alte bis S3b stehen lassen. In der Analyse entscheiden.
- **Zustand „—":** Das Modell braucht die Unterscheidung laedt/fehler nicht, nur `vorlageId: string | null` (null ⇒ „—").
- **Doppelter POST:** Hub und Alarme-Reiter mounten nicht gleichzeitig; identische Einträge trifft der modulweite Cache (AC-6).
- **Trip-Kontext:** Die Wetter-Karte existiert nur im Vergleich; für den Trip keinen Abruf auslösen (nur mit `preset`).

## Analysis

**Type:** Refactor (Frontend), Scheibe S3a von #3399. Kombinierter Durchgang Kontext+Analyse (Intake-Summe 1).

### Affected Files (Change Type)
| File | Change | Begründung |
|------|--------|------------|
| `frontend/src/lib/components/shared/wetter-tab/vorlageName.ts` | MODIFY | neu `vorlagenNameAusId(lang, vorlageId: string \| null)`: Katalogname der ID über `vorlageAnzeigename`, `null` ⇒ „—". `aboVorlagenName` (alte Rangfolge) bleibt bis S3b unverändert für SubscriptionCard und Vergleichsliste |
| `frontend/src/lib/components/shared/hub-uebersicht/hubUebersichtModell.ts` | MODIFY | `deriveVergleichKennzahlen(…, vorlagen?, alt?, vorlageId?: string \| null)` (neuer letzter, optionaler Parameter, damit die ~20 Testaufrufe ohne ID kompilieren); `wertebereicheKarte` setzt `titel: vorlagenNameAusId(get(locale), vorlageId ?? null)`; Import von `aboVorlagenName` entfällt |
| `frontend/src/lib/components/shared/hub-uebersicht/HubUebersicht.svelte` | MODIFY | `const aboVorlage = erstelleAboVorlageId(() => ({ abo: preset, extern: preset ? undefined : null }), api)` (S1-Runen-Modul wiederverwendet, ohne Preset kein Abruf, Trip unberührt); `aboVorlage.id` als letztes Argument an `deriveVergleichKennzahlen` |

### Scope / Risk
- ca. 20–30 LoC Produktcode in 3 Dateien, deutlich unter 250. Risiko niedrig: nur der Titel einer Karte im Vergleichs-Hub; keine Speicherdaten, keine Kanäle, kein Trip.
- Sichtbare Änderung: Titel „—" bis zur Antwort (kurz) und bei Fehler; bei `preset_name` gesetzt jetzt die Server-Vorlage (AC-9).

### Technical Approach / Entscheidungen
1. **Abweichung von der Spec-Tabelle (Signatur):** Statt `aboVorlagenName` umzubauen, kommt eine neue ID-basierte Funktion `vorlagenNameAusId`. Grund: SubscriptionCard und Vergleichsliste (S3b-Dateien) rufen `aboVorlagenName(lang, preset)`; ein Signaturwechsel in S3a würde sie brechen oder S3b vorwegnehmen (Scheibenregel: einzeln auslieferbar). S3b stellt die beiden Aufrufer auf `vorlagenNameAusId` um und löscht `aboVorlagenName`. In der Spec als Changelog-Eintrag und S3a/S3b-Tabellen nachziehen.
2. **Verdrahtung:** `erstelleAboVorlageId` (S1, `shared/alarme-tab/aboVorlageId.svelte.ts`) ist kontextfrei; Wiederverwendung statt neuer Lader-Verdrahtung (Code-Teilung, kein Pendant). Cache (AC-6) wirkt dadurch auch zwischen Hub und Alarme-Reiter.
3. **Modell bleibt rein:** Modell bekommt nur `vorlageId: string | null`; „laedt" und „fehler" fallen beide auf „—" (AC-2 verlangt keine Unterscheidung in der Anzeige).

### Tests (RED zuerst: AC-2, AC-9)
- Kern-Modell mit echtem `resolve_entwurf` (`aufgeloestVon` aus `wetterTabDaten.ts`): Titel = Katalogname der Python-ID; `null`/fehlend ⇒ „—", nie „Allgemein"/„General"; Fall `preset_name` gesetzt (z. B. preset_name `wintersport`, profil `wandern`, ohne ampel.template) ⇒ Name der Python-Vorlage (AC-9). Ort: `hub_uebersicht_vorlagenrang_2988.test.ts` (laut Spec).
- Laufzeit-Verdrahtung (AC-2 „wo es wirkt"): `hub_uebersicht_verdrahtung_laufzeit.test.ts` hat einen Fetch-Ersatz am Ausgang; neuer Fall: Vergleich ⇒ genau ein POST `/api/ampel/aufloesung` mit dem Eintrag des Presets (inkl. `preset_name`), Antwort-ID ⇒ Kartentitel; Antwort 500 ⇒ „—"; Trip ⇒ kein POST. Bestehende Fälle dort prüfen, ob sie die Menge der Abrufe vollständig festschreiben (dann um den POST ergänzen).
- Nachziehen: `vorlage_statt_profil_2796.test.ts:51,88-103` (Titel-Regeltests der alten Rangfolge auf ID-Eingabe umstellen; `aboVorlagenName`-Unit-Fälle bleiben bis S3b), `compare_hub_fidelity.test.ts:86-90` (Quelltext-Check auf `vorlagenNameAusId(`), ggf. `vergleich_hub_sprache.test.ts:294`, `feat3298_vergleich_ohne_altfelder.test.ts:259`, Prüfstand-Ausgabe `f10Pruefstand.ts:354` (Titel ohne ID jetzt „—").

### Dependencies
- Keine neuen. Python, Go, `/api/templates` unverändert.

### Open Questions
- Keine PO-Frage; die Signatur-Abweichung ist technisch und in der Spec zu vermerken.

## TDD RED (Stand)
RED-Commit 9e7c19667: 7 neue Fälle rot in `hub_uebersicht_vorlagenrang_2988.test.ts` (AC-2, AC-9, Unit `vorlagenNameAusId`) und `hub_uebersicht_verdrahtung_laufzeit.test.ts` (POST, „—" beim Laden, 500 ⇒ „—"). Artefakt `docs/artifacts/rework-3399-s3a-hub-name/test-red-output.txt`.

Hinweise für `/50-implement`:
- `HubUebersicht.svelte` muss `erstelleAboVorlageId` genau so aus `../alarme-tab/aboVorlageId.svelte.ts` importieren (Prüfstand-Saat `LADER_SAAT` ersetzt diesen Namen).
- Laufzeittest alt: `netz().uebrigeAbrufe()` + `deepEqual(['/api/templates'])` in „genau EIN Abruf /api/templates" und „Vorlagen-Abruf scheitert" werden durch den neuen POST rot ⇒ `uebrigeAbrufe` nimmt `/api/ampel/aufloesung` aus (eigene Fälle prüfen ihn).
- Nachziehen: `vorlage_statt_profil_2796.test.ts:51-71` (Titel über ID aus `aufgeloestVon`; Listenkarte und `aboVorlagenName`-Unit bleiben bis S3b), `compare_hub_fidelity.test.ts:86-90` (auf `vorlagenNameAusId(`), prüfen: `vergleich_hub_sprache.test.ts:294`, `feat3298_vergleich_ohne_altfelder.test.ts:259`, `f10Pruefstand.ts:354`, `wertebereiche_karte_2988`, `s3a2794_teil4b_uebersicht`, `s3a2794_teil4b_befunde`, `p5c_ableitung_hub_orte_ausgabe`, `hub_uebersicht_modell`.
- Git: Commit-Hook verlangt einfachen `git commit` ohne `cd` davor.
