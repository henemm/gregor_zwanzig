---
entity_id: refactor_2990_kanal_ableitung_eine_quelle
type: module
created: 2026-11-26
updated: 2026-11-26
status: draft
version: "1.0"
workflow: feature-2990-kanal-ableitung
tags: [frontend, kanaele, ortsvergleich, trip, refactor, paritaet]
---

# Eine Kanal-Ableitung fuer Trip und Ortsvergleich (Issue #2990)

## Approval

- [ ] Approved

## Purpose

Welche Versandkanaele ein Trip oder ein Ortsvergleich aktiv hat, wird heute an drei Stellen getrennt abgeleitet (`reportChannels`, `heroKanaele`, `presetChannels`). Die Ortsvergleich-Kopie zeigt immer „Email", auch wenn der Nutzer die Orts-Mail abgeschaltet hat (`send_email:false`, PO-Entscheidung #2795). Dieser Umbau fuehrt alles auf EINEN Baustein zurueck; dadurch zeigen beide Kontexte bei gleichen Flags dieselben Kanaele in derselben Reihenfolge, und der Fehler beim Ortsvergleich verschwindet.

## Source

- **File:** `frontend/src/lib/components/shared/aktiveKanaele.ts` (neu)
- **Identifier:** `aktiveKanaele`, `aktiveKanalNamen`, `KANAL_ANZEIGENAME`

> **Schicht:** ausschliesslich Frontend (SvelteKit). Keine Aenderung an Go-API oder Python-Core, kein Schema-Eingriff; der Versand selbst entscheidet Python unveraendert.

> **Querschnitts-Pruefpunkte**
> - **Trip/Ortsvergleich-Teilung:** Der Baustein liegt unter `shared/` und bedient beide Kontexte aus einer Lese-Regel; das ist die Umsetzung der Code-Teilungs-Vorgabe, keine einseitige Neuanlage.
> - **Mandantentrennung:** Reine Funktionen auf uebergebenen Objekten, kein Endpoint, keine Nutzerdaten-Zugriffe, keine `user_id`-Logik; ein Zwei-Nutzer-Test entfaellt.
> - **Kanaele:** Alle vier Kanaele (E-Mail, Telegram, SMS, Premium-SMS) werden gleich behandelt und in fester Reihenfolge ausgegeben; Signal existiert nicht.

## Scope

### Affected Files

Pfade unter `frontend/src/`.

| File | Change Type | Description |
|------|-------------|-------------|
| `lib/components/shared/aktiveKanaele.ts` | CREATE | `KANAL_ANZEIGENAME`, `aktiveKanaele(quelle)` (Schluessel), `aktiveKanalNamen(quelle)` (Namen); Flags nur ueber `leseBriefingStartwerte` |
| `routes/_home/cockpitHelpers.ts` | MODIFY | `reportChannels` = `aktiveKanaele`; `heroKanaele` = Slot-Regel + `aktiveKanalNamen` |
| `lib/components/compare/subscriptionHelpers.ts` | MODIFY | `presetChannels` = `aktiveKanalNamen(preset)`; veralteten KL-6-Kommentar korrigieren |
| `routes/_home/SubscriptionKachel.svelte` | MODIFY | lokale `KANAL_NAME`-Tabelle entfaellt, Trip-Zweig nutzt `aktiveKanalNamen` |
| `lib/components/shared/__tests__/aktive_kanaele_2990.test.ts` | CREATE | Verhalten aus Nutzersicht, echte Funktionen ohne Mocks |

## Estimated Scope

- **LoC:** ca. 80-110 inklusive Test (Grenze 250), Funktionen <=50 LoC
- **Files:** 5 (4 Produktion, davon 1 neu; 1 Test neu)
- **Effort:** low (Risiko niedrig: nur Anzeige)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `shared/briefingStartwerte.ts` (`leseBriefingStartwerte`) | Modul | bereits geteilte Lese-Regel der vier Kanal-Flags (#2987), einzige Flag-Quelle |
| `utils/reportSlotAktiv` | Modul | Slot-Regel fuer Hero (kein aktiver Slot, keine Kanaele) |
| `ChannelChip` | Komponente | normalisiert Schluessel und Anzeigenamen, bleibt unveraendert |
| Konsumenten `presetChannels` | Funktion | `CompareStatusRow`, `SubscriptionCard`, `routes/compare/+page.svelte`, `SubscriptionKachel`; bleiben unangetastet, da der Name bleibt |
| PO-Entscheidung #2795 | Issue | `send_email` am Ortsvergleich, fehlend = an |
| #1986 (NEU-9) | Issue | Paritaets-Bestandsaufnahme, Ursprung dieser Folge |

## Implementation Details

1. `shared/aktiveKanaele.ts` anlegen: pure Funktionen, importiert nur `briefingStartwerte.ts`. Reihenfolge fest Email, Telegram, SMS, Premium-SMS. E-Mail ist an, solange `send_email !== false`; Telegram, SMS und Premium-SMS nur bei Opt-in `=== true`. Quelle ist ausschliesslich der Flag-Satz des uebergebenen Objekts (Trip `report_config` oder Preset top-level), nie `empfaenger` oder `channel_layouts`.
2. `reportChannels(rc)` ruft `aktiveKanaele(rc)`; `heroKanaele(rc)` behaelt die Slot-Regel (ohne aktiven Slot leere Liste) und liefert sonst `aktiveKanalNamen(rc)`. `plannedBriefings` und die Trip-Timeline-Chips bleiben unveraendert.
3. `presetChannels(preset)` wird duenner Wrapper um `aktiveKanalNamen(preset)`; `channelNamesLabel` bleibt Wrapper darueber. Der Funktionsname bleibt (Konsumenten, Quelltext-Waechter #578).
4. In `SubscriptionKachel.svelte` die lokale Namenstabelle entfernen.

Reihenfolge TDD: Test zuerst (rot: Modul fehlt, `send_email:false` zeigt noch „Email"), dann Umsetzung.

## Expected Behavior

- **Input:** Objekt mit den Kanal-Flags (Trip-`report_config` oder Ortsvergleich-Preset), auch leer oder `undefined`.
- **Output:** Liste der aktiven Kanaele in fester Reihenfolge; leeres Objekt ergibt nur Email.
- **Side effects:** keine. Keine neuen Permissions, keine Speicher-Keys, keine Schema-Aenderung.

## Acceptance Criteria

- **AC-1:** Given ein Trip-`report_config` und ein Ortsvergleich-Preset mit denselben Kanal-Flags (Email an, Telegram, SMS und Premium-SMS an) / When die aktiven Kanaele abgeleitet werden / Then zeigen beide dieselben Kanaele in der Reihenfolge Email, Telegram, SMS, Premium-SMS.
  - Test: Beide Quellen mit gleichen Flags durch die echten Funktionen, Ergebnis gegen feste Liste; weitere Flag-Kombinationen mit abweichender Aufzaehl-Reihenfolge der Felder ergeben dieselbe Reihenfolge.

- **AC-2:** Given Trip und Ortsvergleich mit gleichen Flags / When Vergleichs-Liste, Detail-Hub „Kanaele", Startseiten-Kachel, Status-Zeile und Hero ihre Kanaele anzeigen / Then stimmt die Anzeige an jeder dieser Stellen mit der gemeinsamen Ableitung ueberein (Trip und Vergleich identisch).
  - Test: bestehende Paritaetswaechter `subscription_kachel_paritaet` und `home_hero_paritaet` sowie `channelNamesLabel` und `presetChannels` gegen feste Erwartung bleiben gruen.

- **AC-3:** Given ein Ortsvergleich-Preset mit `send_email:false` und Telegram an / When die aktiven Kanaele abgeleitet werden / Then enthaelt die Liste kein „Email", sondern nur Telegram.
  - Test: rot vor der Umsetzung (heute immer „Email"), gruen danach; gilt in Liste, Detail-Hub, Kachel und Status-Zeile ueber die gemeinsame Funktion.

- **AC-4:** Given ein Alt-Preset ohne Feld `send_email` und ein leeres Preset / When die aktiven Kanaele abgeleitet werden / Then ist „Email" an (fehlend gleich an) und es erscheint kein Telegram, SMS oder Premium-SMS.
  - Test: Bestandstests `issue_582_list_helpers`, `compare_preset_channels*` bleiben unveraendert gruen; neuer Test fuer fehlendes Feld.

- **AC-5:** Given Flags mit `true`, `false`, fehlend, `"true"` oder `1` fuer Telegram, SMS und Premium-SMS sowie vorhandene `empfaenger`, `channel_layouts` oder ein Signal-Feld / When die Kanaele abgeleitet werden / Then erscheint ein Kanal nur bei genau `true`, Signal erscheint nie, und `empfaenger` oder `channel_layouts` aendern nichts am Ergebnis.
  - Test: Tabellentest ueber Opt-in-Werte; gleiche Eingabe mit und ohne `empfaenger`/`channel_layouts` ergibt dasselbe Ergebnis.

- **AC-6:** Given ein Trip ohne aktiven Slot (Morgen und Abend aus) / When der Hero seine Kanaele anzeigt / Then bleibt die Kanal-Liste leer, waehrend die Trip-Timeline-Chips der geplanten Briefings unveraendert bleiben.
  - Test: `heroKanaele` mit Slots aus gegen leere Liste; bestehende Tests `home_hero_paritaet` und `report_slot_aktiv` (Defaults von `reportChannels`) bleiben gruen.

- **AC-7:** Given die Kanal-Anzeigen von Startseite, Hero, Vergleichs-Liste, Detail-Hub-Stat und Status-Zeile / When dort Kanal-Flags ausgewertet werden / Then geschieht das nur noch im Baustein `shared/aktiveKanaele.ts` (Hub-Uebersicht `tripBriefingKanaele` und Zustellungs-Reiter `standAusPreset` sind ausserhalb des Scopes, Folge-Issue #3413); `reportChannels`, `heroKanaele` und `presetChannels` liefern genau dessen Ergebnis, und die lokale `KANAL_NAME`-Tabelle der Kachel ist entfernt.
  - Test: Verhaltenstest: die drei alten Funktionen liefern fuer dieselbe Eingabe dasselbe wie `aktiveKanaele`/`aktiveKanalNamen`; eine Mutation der Flag-Regel im Baustein (z.B. E-Mail immer an) macht Tests rot, und zwar fuer Trip UND Vergleich.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1 (AC-1, AC-5): GIVEN gleiche Flags in `report_config` und Preset WHEN `aktiveKanaele`/`aktiveKanalNamen` THEN gleiche Liste in fester Reihenfolge; Opt-in nur bei `=== true`, nie Signal, `empfaenger`/`channel_layouts` ohne Einfluss
- [ ] Test 2 (AC-3): GIVEN Preset `send_email:false` WHEN `presetChannels` THEN kein „Email" (rot vor Umsetzung)
- [ ] Test 3 (AC-4): GIVEN Preset ohne `send_email` und leeres Preset WHEN `presetChannels` THEN Email an
- [ ] Test 4 (AC-6, AC-7): GIVEN Trip-`report_config` WHEN `reportChannels` und `heroKanaele` THEN gleiche Kanaele wie der Baustein; ohne aktiven Slot leerer Hero
- [ ] Regression (AC-2, AC-4, AC-6): `subscription_kachel_paritaet`, `home_hero_paritaet`, `issue_582_list_helpers`, `compare_preset_channels`, `compare_preset_channels_premium_sms`, `report_slot_aktiv` bleiben gruen

Ausfuehrung je Datei: `cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test <datei>`. Neuer Test: `frontend/src/lib/components/shared/__tests__/aktive_kanaele_2990.test.ts`, node:test ohne Mocks, echte Funktionen, kein Dateiinhalt-Check. Test 2 ist vor der Umsetzung rot, Test 1 rot (Modul fehlt); die uebrigen sichern Bestandsverhalten.

## Definition of Done

- AC-1 bis AC-7 durch Kern-Tests gruen, genannte Bestandswaechter unveraendert gruen.
- Mutationsgegenprobe im `implementation-validator` faengt: E-Mail-Regel vertauscht, Opt-in `=== true` aufgeweicht, Reihenfolge geaendert, Hero-Slot-Regel entfernt.
- Alle 6 CI-Checks gruen; Staging- und Prod-Ablauf gemaess Liefer-Workflow, Selftest Exit 0.

## Known Limitations

- Nur Anzeige: Versand und Backend sind nicht beruehrt; ob eine Orts-Mail tatsaechlich versandt wird, entscheidet weiter Python.
- `ChannelChip` bleibt unveraendert; er akzeptiert Schluessel wie Anzeigenamen.
- Der Quelltext-Waechter in `issue_578_molecules_organisms.test.ts` (Regex `presetChannels(preset)`) bleibt nur erfuellt, weil der Funktionsname bleibt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner Umbau auf eine Quelle nach dem Muster #2987/#2989; die Verhaltenskorrektur folgt der bestehenden PO-Entscheidung #2795 und ADR-0095 (Kanal-Paritaet). Kein neuer Kanal, Provider, Datenmodell- oder Auth-Eingriff.

## Changelog

- 2026-11-26: Initial spec created
- 2026-11-26: AC-7 auf die Affected Files begrenzt (Adversary F002), Rest nach #3413; Kachel-Test fuer Vergleich ergaenzt (F001)
