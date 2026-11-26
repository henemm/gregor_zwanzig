# Context: rework-3399-vorlage-aufloesung

## Request Summary
Issue #3399 (Folge aus #2988 S4): Die letzte Frontend-Nachbildung der Vorlagen-Rangfolge (`vorlageIdFuer`: `ampel.template` → `preset_name` → `profil` → „allgemein") soll verschwinden. Alle Nutzer übernehmen `vorlage_id` aus der Server-Auflösung (`POST /api/ampel/aufloesung` → `app.ampel.resolve_entwurf`). Grundlage: ADR-0127 Nr. 3 (Frontend hält kein Metrik-Wissen).

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/alerts-tab/alarmAbAnzeige.ts:62-80` | `vorlageIdFuer` + `PROFIL_ZU_VORLAGE`, zu entfernen. `ladeVorlagenAmpeln`, `STANDARD_VORLAGE`, `alarmAbAus` bleiben |
| `frontend/src/lib/components/shared/AlarmeTab.svelte:188-190` | `vorlageAmpel = vorlagenAmpeln[vorlageIdFuer(aboAmpel, trip.preset_name, preset.profil, …)]` → „Alarm ab"-Vorgabe der Vorlage (Prop `vorlage` an Zeile 541). Synchron/derived |
| `frontend/src/lib/components/shared/wetter-tab/vorlageName.ts:39-48` | `aboVorlagenName(lang, abo, vorlagen?)` synchron, ruft `vorlageIdFuer` |
| `frontend/src/lib/components/compare-new/compareNewVorlage.ts:55-66` | `feldsatzAusVorlage` (synchron) setzt `vorlageId` der Kopie über `vorlageIdFuer` mit `JEDE_VORLAGE`; Nutzer `CompareNewEditor.svelte:31` |
| `frontend/src/lib/components/shared/wetter-tab/ampelAufloesung.ts` | Client: `loeseAmpelnAuf` (Pakete à 32), `eintragAusAbo`, `Aufgeloest = {vorlage_id, ampel}`; wirft bei jedem Fehler |
| `frontend/src/lib/components/shared/hub-uebersicht/tripAufloesung.ts` | Vorbild: Lademodul mit Ticket + Cache je Eintrag, Zustand `laedt/geladen/fehler`, scheitert nie |
| `frontend/src/lib/components/shared/hub-uebersicht/hubUebersichtModell.ts:309-321` | `wertebereicheKarte` → `aboVorlagenName(…, preset, vorlagen)` (Hub-Übersicht Vergleich) |
| `frontend/src/lib/components/organisms/SubscriptionCard.svelte:99` | Meta-Zeile Vergleich „Orte · Vorlagenname", ohne Vorlagenliste. Eingebunden in `HubKopf.svelte`, `routes/_home/SubscriptionKachel.svelte`, `routes/compare/+page.svelte`, `routes/trips/+page.svelte` |
| `frontend/src/routes/compare/+page.svelte:89` | Listen-Spalte „Vorlage" je Zeile über `aboVorlagenName` |
| `src/app/ampel.py:149-193, 254-268` | Python-Wahrheit: `_aufloesen`, `_bekannte_vorlage` (nur `AMPEL_TEMPLATES`), `template_for_profil`, `resolve_entwurf` |
| `frontend/src/lib/components/alerts-tab/__tests__/alertMetricLevelRowTitleRender.test.ts:35,96-100` | Unit-Test von `vorlageIdFuer`, fällt mit weg |

## Existing Patterns
- Server-Auflösung laden: `tripAufloesung.ts` (Cache per JSON-Schlüssel des Eintrags, Ticket gegen veraltete Antworten), `WetterTabInhalt.svelte:118-125` (derived Schlüssel + `loeseAmpelnAuf(api, [eintragAusAbo(abo())])`).
- Tests nutzen echtes Python (`wetterTabDaten.ts:107-130`: `resolve_entwurf` per Subprozess), kein Mock-Theater.
- Fehler/fehlende Vorlagenliste ⇒ „—" statt geratener Werte (`ladeVorlagenAmpeln`, `wertebereicheKarte`).

## Dependencies
- Upstream: `POST /api/ampel/aufloesung` (Go `internal/handler/ampel_aufloesung.go` → `api/routers/ampel_aufloesung.py`), `GET /api/templates`.
- Downstream: Alarme-Reiter (Trip + Vergleich, inkl. Compare-Anlege-Masken), Hub-Übersicht Vergleich, Abo-Karte (Home, Hub-Kopf, Listen Trips/Vergleiche), Vergleichsliste Spalte „Vorlage", Anlegen „Kopie aus Vorlage" im Compare-New-Editor.

## Existing Specs
- `docs/specs/modules/rework_2988_ampel_ableitung.md` (Known Limitations nennt dieses Folge-Issue; `auswahlLesen`/`aktiveMetriken`/`DERIVED_METRIC_RULES` bleiben)
- `docs/adr/0127-ein-katalog-eine-verarbeitung.md`

## Risks & Considerations
- **Mehr Nutzer als im Issue genannt:** `aboVorlagenName` wird außer in `hubUebersichtModell.ts` auch in `SubscriptionCard.svelte` (4 Einbindungen) und `routes/compare/+page.svelte` (Listenspalte) synchron gerufen. Alles umzustellen heißt: synchron → asynchron mit Ladezustand, in Listen gebündelt (ein Aufruf für alle Zeilen). Wahrscheinlich > 5 Dateien / > 250 LoC ⇒ Scheiben schneiden.
- **Ladezustand und Fehler:** heute zeigt die Anzeige sofort einen Namen; künftig erst nach der Antwort. Fehler ⇒ „—" (Muster), nie „Allgemein" geraten.
- **AlarmeTab** braucht weiterhin die *Vorlagen*-Ampel (`/api/templates`) für „Alarm ab", nur die ID kommt vom Server. Die aufgelöste Ampel enthält Abo-Abweichungen und taugt nicht als Vorgabewert.
- **compareNewVorlage** ist synchron und wird beim Anlegen aus einer Quelle aufgerufen; die Vorlagen-ID muss vorher aufgelöst oder nachgereicht werden.
- **Parität:** Python kennt nur Systemvorlagen (`AMPEL_TEMPLATES`); Frontend-`bekannt` aus `/api/templates` ist dieselbe Menge. Kein Verhaltenswechsel bei gültigen Daten erwartet.
- **Mandantentrennung:** Endpunkt liest keinen Nutzerbestand; kein neues Risiko.
- Trip/Vergleich-Code-Teilung: neue Lade-Logik kontextfrei in `shared/`, kein Pendant.

## Analysis

### Type
Feature (Rework, ADR-0127 Nr. 3) — kein Nutzerfehler; sichtbare Wirkung nur: Vorlagenname erscheint nach der Server-Antwort, bis dahin und bei Fehler „—".

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/wetter-tab/vorlagenIdLader.ts` | CREATE | Gebündelter, modulweit gecachter Lader `Abo → vorlage_id` über `loeseAmpelnAuf` (Ticket, scheitert nie, Fehler-Zustand) |
| `frontend/src/lib/components/shared/AlarmeTab.svelte` | MODIFY | `vorlageAmpel = vorlagenAmpeln[vorlageId]`, ID aus Lader; fehlt ⇒ null („—") |
| `frontend/src/lib/components/compare-new/compareNewVorlage.ts` | MODIFY | `feldsatzAusVorlage(…, vorlageId)`; Auflösung in der aufrufenden Seite vor dem Mount (Startwert-Muster `untrack` bleibt) |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` bzw. aufrufende Route | MODIFY | Quelle vor Mount auflösen |
| `frontend/src/lib/components/shared/wetter-tab/vorlageName.ts` | MODIFY | `aboVorlagenName(lang, vorlageId \| null)` → Anzeigename oder „—" |
| `frontend/src/lib/components/shared/hub-uebersicht/hubUebersichtModell.ts`, `HubUebersicht.svelte` | MODIFY | `vorlageId` als Parameter, Hub lädt per Lader |
| `frontend/src/lib/components/organisms/SubscriptionCard.svelte` + Einbinder (`HubKopf.svelte`, `routes/_home/SubscriptionKachel.svelte`, `routes/trips/+page.svelte`, `routes/compare/+page.svelte`) | MODIFY | Karte bekommt ID/Name als Prop; Listen laden gebündelt |
| `frontend/src/lib/components/alerts-tab/alarmAbAnzeige.ts` | MODIFY | `vorlageIdFuer`, `PROFIL_ZU_VORLAGE` entfernen (letzte Scheibe) |
| Tests: `alertMetricLevelRowTitleRender.test.ts:35,96-100`, `vorlage_statt_profil_2796.test.ts:82-103`, `compare_hub_fidelity.test.ts:86-90`, `compareNewVorlage.test.ts`, `feat3298_vergleich_ohne_altfelder.test.ts:259`, `vergleich_hub_sprache.test.ts:294`, `anlegen_ohne_profil_3198.test.ts:223`, `hub_uebersicht_vorlagenrang_2988.test.ts`, `reaktivitaet_waechter.test.ts:107` | MODIFY | Signaturen nachziehen; Regeltests durch Tests mit echtem `resolve_entwurf` ersetzen |

### Scope Assessment
- Files: ~12–15 Produktdateien + ~8 Tests
- Estimated LoC: ~450–550 netto ⇒ über 250/5 ⇒ **Scheiben** (ein Issue, Schluss erst nach letzter Scheibe, Vorbild #2988)
- Risk Level: MEDIUM (nur Anzeige, kein Datenschreiben; viele Einbindungen)

### Technical Approach (Empfehlung)
Scheiben in Reihenfolge, jede für sich auslieferbar (`vorlageIdFuer` bleibt bis S4):
- **S1** Lader `vorlagenIdLader.ts` (kontextfrei, Cache je `JSON.stringify(eintragAusAbo(abo))`, ein Paket für ungecachte Einträge) + AlarmeTab umstellen + Tests mit echtem Python. ~120 LoC.
- **S2** Compare-New: Quelle vor dem Mount auflösen, `feldsatzAusVorlage` bekommt `vorlageId`; Tests nachziehen. ~100 LoC.
- **S3a** `aboVorlagenName(lang, id|null)` + Hub-Übersicht (Modell + Komponente) + Tests.
- **S3b** `SubscriptionCard` mit ID-Prop, Einbinder (Home-Kachel, Hub-Kopf, Trip-Liste, Vergleichsliste gebündelt).
- **S4** `vorlageIdFuer`/`PROFIL_ZU_VORLAGE` löschen, Rest-Tests, Grep-Nachweis.
Ladezustand und Fehler ⇒ „—", nie „Allgemein" geraten. Die aufgelöste Ampel wird NICHT als „Alarm ab"-Vorgabe benutzt (enthält Abo-Abweichungen) — nur die ID.

### Dependencies
`POST /api/ampel/aufloesung` (unverändert), `GET /api/templates` (bleibt für Vorlagen-Ampeln in AlarmeTab), `tripAufloesung.ts` als Vorbild.

### Befunde gegen den Plan
- Issue nennt die `aboVorlagenName`-Nutzer unvollständig (SubscriptionCard ×4, Vergleichsliste).
- Paritätsunterschied: `aboVorlagenName` übergab kein `preset_name`, `eintragAusAbo` schon; bei Vergleichen meist leer, per Test absichern.
- Quelltext-Wächtertests (`reaktivitaet_waechter`, `compare_hub_fidelity`) müssen mitgezogen werden.

### Open Questions
- keine (kein Produkt-Zielkonflikt; „—" bei Laden/Fehler folgt dem bestehenden Muster)
