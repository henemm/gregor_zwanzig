---
entity_id: fix_3193_vorlage_abweichung_minimal
type: bugfix
created: 2026-11-20
updated: 2026-11-20
status: draft
version: "1.0"
workflow: fix-3193-vorlage-abweichung-minimal
tags: [wetter-tab, vorlage, abweichung, trip, vergleich, epic-2913]
---

# Fix #3193: Vorlagen-Abweichung im Reiter Wetter minimal und einheitlich

## Approval

- [ ] Approved

## Purpose

Nach „Übernehmen“ einer Vorlage oder „Auf Vorlage zurücksetzen“ soll der Reiter Wetter keine scheinbaren Abweichungen mehr speichern oder zählen: Zähler, Abweichungsmenge und Speicherweg messen künftig gegen dieselbe Basis „Vorlage im Kontext“. Heute zeigt der Orts-Vergleich „1 Abweichung“ mit dauerhaft stehendem, wirkungslosem Zurücksetzen-Knopf, und der Trip speichert abgeleitete Kinder als Abweichung.

## Source

- **File:** `frontend/src/lib/components/shared/wetter-tab/wetterZustand.ts`
- **Identifier:** `vorlageImKontext`, `mengeVon`, `abweichungenVon`, `mitVorlage`

Weitere Stellen: `wetterTabSpeicherung.ts` (`tripNutzlast`, `vergleichNutzlast`), `organisms/wetter-tab/WetterTabInhalt.svelte` (Aufrufe von `mengeVon`). Schicht: nur Frontend (SvelteKit); keine Go-/Python-Änderung.

Querschnitt: Teilung Trip/Vergleich bleibt erhalten (eine Kontext-Tabelle `Record<Kontext, …>` in der geteilten Datei, kein Pendant). Mandantentrennung: kein neuer datenbewegender Endpoint, bestehender Speicherweg unverändert. Kanäle: `ampel.metrics.<id>.enabled` steuert keine Ausgabe (Auswahl kommt aus `metrics[]`/`active_metrics`), kein Kanal betroffen.

## Scope

**Im Scope:**
- Eine einheitliche Basis „Vorlage im Kontext“ für Zähler, `mengeVon` und Speicher-Nutzlast.
- Trip: abgeleitete Kinder eines aktiven Elters gelten in der Basis als an.
- Orts-Vergleich: nicht ausgebbare Größen (nicht im Vergleichs-Katalog) gelten als neutral.
- Neuer Kern-Test und Angleichung der veralteten Auswahl-Erwartungen der Staging-E2E-Spec.

**Nicht im Scope:**
- `abweichungsMenge` in `ampelSchreiben.ts` (rechnet korrekt gegen die übergebene Basis).
- Systemvorlagen, Vergleichs-Katalog, Python/Go, Datenschema, Migration von Bestandsdaten.
- Anzeige von `deviation_count` (produktiv ungenutzt).

## Estimated Scope

- **LoC:** ca. 60 Produktcode, ca. 150 Test
- **Files:** 5 (3 Quelle, 1 Kern-Test neu, 1 E2E-Spec)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `AUSWAHL_ABLEITUNG` / `auswahlMitAbgeleiteten` (`ampelModell.ts`) | module | Trip-Ableitung der Kinder aus Elter-Metriken |
| `nurAusgebbar` / `ANGEBOTS_FILTER` / `vergleichsKatalogIds` | module | Kontext-Filter der ausgebbaren Größen (Vergleich) |
| `abweichungsMenge`, `zaehleAbweichungenGegen` | module | Minimale Menge bzw. Zählung gegen eine Basis |
| `/api/templates` (`AMPEL_TEMPLATES`) | API | Systemvorlagen (SSOT) |
| `/api/compare/metrics` | API | Vergleichs-Katalog, enthält `temperature_night` nicht |
| `frontend/e2e/s3a2794-teil3.helpers.ts` | test-helper | `aktiveDerVorlage`, `abgeleiteteKinder`, `auswahlImStand` |
| feat_2794 (Z. 144/149/208), feat_3047 E6/E7 | spec | Freigegebene Regeln „nur Abweichungen speichern“, Auswahl-Ableitung |

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Fehlerbehebung innerhalb bestehender, freigegebener Entscheidungen (feat_2794 „minimale Abweichung“, feat_3047 E6/E7); keine neue Entscheidungsfläche, kein Schema- oder Kanalwechsel.

## Implementation Details

Ursache: Der Zähler misst gegen `vorlageImKontext` (Trip: Rohvorlage plus abgeleitete Kinder an), `mengeVon` und der Speicherweg (`tripNutzlast` Z. 70, `vergleichNutzlast` Z. 88) gegen die Rohvorlage. Die Auswahl wird dagegen kontextbezogen gebildet (`mitVorlage` = `nurAusgebbar(AUSWAHL_ABLEITUNG[context](enabled))`). Trip: abgeleitete Kinder erscheinen so als „hinzugefügt“. Vergleich: `temperature_night` ist in der Vorlage an, fehlt wegen E6 in der Auswahl und zählt als Abweichung `{enabled:false}`.

Vorgehen:
1. `vorlageImKontext` wird zur einzigen exportierten Basis, als Kontext-Tabelle `BASIS_IM_KONTEXT: Record<Kontext, …>` in `wetterZustand.ts`; Signatur um aktuelle Auswahl und Katalog-IDs erweitert.
2. route: Rohvorlage plus jedes abgeleitete Kind eines aktiven Elters `enabled:true`. Ein bewusstes „−“ am Kind bleibt Abweichung.
3. vergleich: Rohvorlage, aber für nicht ausgebbare Größen (`!katalogIds.has(id)`) folgt `enabled` der aktuellen Auswahl (neutral). Grenzen und `alarm_ab` dieser Zeilen werden weiter verglichen. Ohne bekannten Katalog bleibt die Basis die Rohvorlage (analog `nurAusgebbar`).
4. `mengeVon(s, vorlagen, context, alt)`, `abweichungenVon`, `tripNutzlast`, `vergleichNutzlast` nutzen ausschließlich diese Basis; der Zähler zählt die Menge, die auch gespeichert wird.
5. `WetterTabInhalt.svelte`: Aufrufe in `signatur`, `abweichungen`, `anzeigeMenge`, `aboAmpel` mit `context`/`altSchluessel`. `aboAmpel` nutzt dieselbe Basis; die Kinder leitet `mitEigenerVorlage` beim Anwenden wieder ab.

E2E-Angleichung `s3a2794-teil3-vorlage.spec.ts` Z. 103/151: Die Erwartung `ampel.metrics == {}` (Z. 101/150) bleibt. Die Auswahl-Erwartung wird an E6/E7 angepasst. Trip: `aktiveDerVorlage(v)` plus `abgeleiteteKinder(kind, aktiveDerVorlage(v))`, weil p5c Kinder ausdrücklich in `metrics[]` schreibt. Vergleich: Vorlagen-Aktive geschnitten mit den `metric_id`s aus `/api/compare/metrics`, weil `temperature_night` gewollt fehlt.

## Expected Behavior

- **Input:** Nutzer wechselt die Vorlage (Übernehmen), setzt auf Vorlage zurück, lädt einen Bestand oder ändert einzelne Metriken.
- **Output:** Gespeichertes `display_config.ampel` enthält nur echte Abweichungen (nach Wechsel/Zurücksetzen: keine `metrics`); Picker zeigt „unverändert“; Zurücksetzen-Knopf nur bei echter Abweichung.
- **Side effects:** Bestandsdaten mit Rausch-Einträgen (Trip: `temperature_day_*`/`wind_chill_*` mit `enabled:true`; Vergleich: `temperature_night: {enabled:false}`) zählen 0 und verschwinden beim nächsten Speichern. Laden löst kein Speichern aus; andere Felder bleiben erhalten (Read-Modify-Write).

## Test Plan

### Automated Tests (TDD RED)

Neuer Kern-Test in `frontend/src/lib/components/shared/wetter-tab/__tests__/` im echten Instanz-Prüfstand (`svelteInstanzPruefstand.ts`), Daten aus den echten Python-Funktionen, kein Mock. Er geht über `mitVorlage` plus `tripNutzlast`/`vergleichNutzlast` (dort, wo es wirkt), nicht nur über `abweichungsMenge` mit Rohauswahl (Lücke von `ampelSchreiben.test.ts:370`).

- [ ] Test 1 (je Kontext, alle Systemvorlagen): GIVEN beliebiger Stand WHEN `mitVorlage(v)` THEN Zähler 0 und Nutzlast `ampel` ohne `metrics`.
- [ ] Test 2: GIVEN Trip nach Vorlage WHEN „−“ an `temperature_day_low` THEN Zähler 1, Nutzlast `{temperature_day_low:{enabled:false}}`.
- [ ] Test 3: GIVEN Vergleich nach Vorlage WHEN „−“ an Böen THEN Zähler 1, Nutzlast `{gust:{enabled:false}}`.
- [ ] Test 4 (Bestandsdaten): GIVEN Bestand mit gesperrtem `temperature_night` in `active_metrics` WHEN Laden THEN Zähler 0, Menge leer.
- [ ] Test 5 (Bestandsdaten Rausch): GIVEN gespeichertes `ampel` mit Rausch-Einträgen WHEN Laden und Speichern einer Alarmstufe THEN Zähler 0, Rausch-Einträge weg, Alarmstufe und übrige Felder erhalten.
- [ ] Test 6: GIVEN Vergleichs-Katalog nicht geladen WHEN Basis gebildet THEN Rohvorlage (kein Absturz).
- [ ] Staging-E2E: `s3a2794-teil3-vorlage.spec.ts` AC-11/12/13/28 für route und vergleich grün.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit beliebiger Systemvorlage / When der Nutzer eine andere Vorlage übernimmt oder auf die Vorlage zurücksetzt / Then ist die gespeicherte Abweichung leer und der Picker zeigt „unverändert“.
  - Test: Kern-Test im Instanz-Prüfstand für alle Systemvorlagen (Trip), geprüft an der Speicher-Nutzlast und am Zähler.

- **AC-2:** Given ein Orts-Vergleich mit beliebiger Systemvorlage / When der Nutzer übernimmt oder zurücksetzt / Then ist die gespeicherte Abweichung leer, der Picker zeigt „unverändert“ und der Zurücksetzen-Knopf verschwindet.
  - Test: Kern-Test (Vergleich, alle Vorlagen, Katalog ohne `temperature_night`); Staging-E2E AC-12/28 prüft das Verschwinden des Knopfes.

- **AC-3:** Given ein Trip oder Vergleich nach Vorlage / When der Nutzer bewusst eine Metrik ausschaltet („−“) / Then zählt genau diese eine Abweichung weiter und wird als `{enabled:false}` gespeichert.
  - Test: Kern-Test Tests 2 und 3 (Trip `temperature_day_low`, Vergleich Böen).

- **AC-4:** Given Bestandsdaten mit Rausch-Einträgen (Trip: abgeleitete Kinder `enabled:true`; Vergleich: `temperature_night` aus) / When der Reiter lädt / Then zeigt er 0 Abweichungen und schreibt nichts ohne Nutzeraktion.
  - Test: Kern-Test Tests 4 und 5, Ladepfad ohne Speichern.

- **AC-5:** Given dieselben Bestandsdaten / When der Nutzer danach etwas speichert (z. B. eine Alarmstufe) / Then sind die Rausch-Einträge weg und alle anderen Felder (Alarmstufen, Auswahl, Layout) unverändert erhalten.
  - Test: Kern-Test Test 5 vergleicht Nutzlast vor und nach dem Speichern feldweise (Read-Modify-Write).

- **AC-6:** Given ein Vergleichs-Bestand mit `temperature_night` in `active_metrics` / When er geladen wird / Then bleibt die Metrik gesperrt erhalten und zählt nicht als Abweichung.
  - Test: Kern-Test Test 4 sowie bestehende E6-Tests in `ac26_einstellung_gleich_ausgabe.test.ts` bleiben grün.

- **AC-7:** Given die Staging-Umgebung / When `s3a2794-teil3-vorlage.spec.ts` AC-11/12/13/28 für route und vergleich läuft / Then ist sie grün, mit begründet angeglichenen Auswahl-Erwartungen (Trip mit abgeleiteten Kindern, Vergleich ohne nicht ausgebbare Größen) und unveränderter Erwartung `ampel.metrics == {}`.
  - Test: Live-E2E auf Staging im Schritt `/e2e-verify`.

## Definition of Done

- Kern-Test rot vor, grün nach dem Fix; bestehende Tests `p15_abweichung_abgeleitete_kinder`, `ac26_einstellung_gleich_ausgabe`, `ampelSchreiben` grün.
- Staging-E2E `s3a2794-teil3-vorlage.spec.ts` AC-11/12/13/28 route und vergleich grün.
- Adversary mit Mutations-Gegenprobe (Basis in `tripNutzlast` bzw. `vergleichNutzlast` zurück auf Rohvorlage verfälscht muss einen Test rot machen).
- Pendant-Sperre und Kontext-Herkunft-Ratsche grün (Tabelle statt Weiche, keine Pendant-Funktion).
- Svelte-Check, Lint und alle 6 CI-Checks grün; Issue #3193 per Selftest-Exit 0 schließen; Epic #2913 bleibt offen.

## Known Limitations

- `zaehleAbweichungen` und `deviation_count` bleiben produktiv ungenutzt (nur Paritätstests).
- Bestandsrauschen wird nicht migriert, sondern verschwindet beim nächsten Speichern.
- Ist der Vergleichs-Katalog nicht ladbar, gilt die Rohvorlage als Basis und `temperature_night` kann wieder als Abweichung erscheinen.

## Changelog

- 2026-11-20: Initial spec created (Issue #3193, Epic #2913)
