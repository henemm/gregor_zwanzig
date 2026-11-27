---
entity_id: fix_3458_alarm_vorschau_entfernen
type: module
created: 2026-11-27
updated: 2026-11-27
status: draft
version: "1.0"
workflow: fix-3458-alarm-vorschau-entfernen
tags: [frontend, zustellung, alarme, rueckbau, s5b-2]
---

# S5b-2: Alarm-Vorschau-Oberfläche entfernen (Issue #3458)

## Approval

- [ ] Approved

## Purpose

Die Alarm-Vorschau in der Oberfläche (Abschnitt „Beispiel-Alarm“ am Ende des Reiters Zustellung, Abschnitt „Beispiel-Warnung“ im Alarm-Reiter, Knopf „Vorschau laden“) wird entfernt. Sie ist laut PO-Entscheidung A14 durch den Test-Alarm im Menü „Test schicken ▾“ (#3441) ersetzt, der einen echten Beispiel-Alarm an die Alarm-Kanäle schickt. Die Server-Endpunkte `alert-preview` bleiben als Prüfwerkzeug bestehen.

## Source

- **File:** `frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte` (Einbindung), `frontend/src/lib/components/shared/AlarmeTab.svelte` (Abschnitt `sample`)
- **Identifier:** `BeispielAlarm`, `AlertPreviewCard`, `alertPreviewHelpers`, `langlaeufer.alarmVorschau`, Abschnitt `sample`

> **Schicht-Hinweis:** Ausschließlich Frontend (`frontend/src/...`, SvelteKit). Go-API und Python-Core bleiben unverändert; `POST /api/briefings/{id}/alert-preview` und `POST /api/trips/{id}/alert-preview` antworten wie bisher.
>
> **Trip/Ortsvergleich-Teilung:** Der Rückbau trifft die geteilten Bausteine unter `shared/` (`context="route"|"vergleich"`) in beiden Kontexten gleich; keine einseitige Änderung. Der Kontext-Unterschied (Ratsche `context_herkunft_zweige_eingefroren`) verliert dabei seine Einträge zum Beispiel-Alarm.
>
> **Mandantentrennung:** Es werden keine Nutzerdaten bewegt, kein neuer Datenweg.
>
> **Kanäle:** Alle vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS) bekommen den Beispiel-Alarm weiterhin über den Test-Alarm (#3441); der Inhalt ist nicht Teil dieser Änderung.

## Estimated Scope

- **LoC:** Produktivcode überwiegend Löschungen (ca. -420 Zeilen aus 3 gelöschten Dateien plus Streichungen); hinzugefügt werden nur der neue Test (ca. +90) und Umkehrungen in Bestandstests. Der LoC-Wächter zählt nur hinzugefügte Zeilen, kein Override nötig.
- **Files:** 3 Produktivdateien gelöscht, 7 geändert, rund 8 Unit-Test-Dateien gelöscht, rund 20 Unit-Tests und 8 E2E-Specs angepasst, 1 neuer Test, 3 Specs mit Vermerk
- **Effort:** medium (viele Bestandstests, kein Backend)

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/organisms/zustellung-tab/BeispielAlarm.svelte` | DELETE | Abschnitt „Beispiel-Alarm“ |
| `frontend/src/lib/components/alerts-tab/AlertPreviewCard.svelte` | DELETE | Vorschau-Karte |
| `frontend/src/lib/components/alerts-tab/alertPreviewHelpers.ts` | DELETE | Payload-Bau, Fehlertext, `vergleichAlarmRegeln` (keine weiteren Nutzer) |
| `frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte` | MODIFY | Einbindung und Prop `beispielAlarmRegeln` entfernen |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | Ableitung und Weitergabe von `beispielAlarmRegeln` entfernen |
| `frontend/src/lib/components/shared/AlarmeTab.svelte` | MODIFY | Abschnitt `sample` samt Imports entfernen |
| `frontend/src/lib/components/shared/alarme-tab/alarmeTabSections.ts` | MODIFY | `sample` nicht mehr anhängen |
| `frontend/src/lib/api.ts` | MODIFY | `langlaeufer.alarmVorschau` und `alarmVorschau()` entfernen |
| `frontend/src/lib/i18n/messages/de/alarme.json`, `.../en/alarme.json` | MODIFY | `alarme.beispiel_warnung`, `alarme.vorschau.*` entfernen (nur ungenutzte) |
| `frontend/src/lib/components/shared/__tests__/zustellung_ohne_beispiel_alarm_3458.test.ts` | CREATE | Neuer Render-Test (RED) |
| Bestandstests Unit/E2E | MODIFY / DELETE | siehe Tabelle unten |
| `docs/specs/modules/alert_preview_echte_segmente.md`, `fix_2219_alarm_vorschau_haerten.md`, `rework_3036_uebergangsblock_aufloesen.md` | MODIFY | Vermerk „UI abgelöst durch #3458“ |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `feat_3441_test_alarm` | spec | Ersatzweg „Test schicken ▾“ → Test-Alarm; nennt dieses Issue unter „Nicht im Umfang“ |
| `POST /api/briefings/{id}/alert-preview`, `POST /api/trips/{id}/alert-preview` | Server-Endpunkte | bleiben als Prüfwerkzeug (Validatoren, Staging, `alarm_testeinspeisung.md`) |
| `frontend/src/lib/i18n/messages/{de,en}` | Katalog | Schlüssel entfernen, Paritäts-Ratschen müssen grün bleiben |
| Ratsche `context_herkunft_zweige_eingefroren` | Test | Einträge zum Beispiel-Alarm müssen mit entfernt werden |
| Epic #2791 / Scheibe S5 #2797 | Issue | Einordnung; Abnahme #3009 hängt daran |

## Implementation Details

1. RED: neuer Test `zustellung_ohne_beispiel_alarm_3458.test.ts` (`node --test`, kein Vitest) nach dem Muster von `rework_3036_zustellung_ohne_uebergang.test.ts` (Render über `lade`/`renderKomponente`/`renderVergleichNeu` aus `infoboxSsr.ts`). Er rendert den Reiter Zustellung (Trip und Orte) und den Alarm-Reiter im Anlegen (beide Kontexte) und sichert die Abwesenheit von Beispiel-Alarm, Vorschau-Karte und „Vorschau laden“ zu; zusätzlich: `alarmeTabSections` ohne `sample`, `de`/`en`-Katalog ohne Vorschau-Schlüssel, `api.ts` ohne `alarmVorschau`. E2E-Umkehr in `versand-tab.spec.ts` und `rework-3036-bloecke-schalter.spec.ts`.
2. GREEN: Komponenten und Helfer löschen, Einbindungen und `api.ts`-Funktionen entfernen, Katalogschlüssel DE/EN entfernen (nur wenn nirgends mehr genutzt; Treffer in `test_schicken.json` sind der Test-Alarm-Untertitel und bleiben), Bestandstests anpassen.
3. Server-Endpunkte und Python bleiben unberührt.

Regel für Bestandstests: Zusicherungen „Beispiel-Alarm ist da“ werden zu „ist weg“ umgedreht. Tests, die ausschließlich das Innenleben der entfernten Karte prüfen, entfallen mit ihr (Begründung in der Tabelle). Zusicherungen über Server-Wege (CSP, Zeitbudget) entfallen nur, wenn sie allein über die Karte erreichbar waren.

### Entfallende/angepasste Bestandstests → Grund

Unit (`node --test`, unter `frontend/src/lib/…`):

| Test | Maßnahme | Grund |
|------|----------|-------|
| `components/alerts-tab/alertPreviewHelpers.test.ts` | entfällt | prüft nur den gelöschten Helfer `alertPreviewHelpers.ts` |
| `components/alerts-tab/alertPreviewEmpty.test.ts` | entfällt | prüft nur den Leerzustand der gelöschten Karte |
| `components/alerts-tab/issue_850_alert_metrics_stale.test.ts` | entfällt | Veraltungs-Verhalten der Karte (Metrik-Änderung macht Vorschau stale); ohne Karte gegenstandslos |
| `components/alerts-tab/__tests__/alertPreviewKind.test.ts` | entfällt | prüft das `kind`-Verhalten der Karte; Server-Seite deckt `kind-required-3444.staging.spec.ts` weiter ab |
| `components/alerts-tab/__tests__/alertPreviewBerechnetHinweis.test.ts` | entfällt | Hinweistext der Karte |
| `components/alerts-tab/__tests__/alertPreviewKeineEtappen.test.ts` | entfällt | Hinweis „keine Etappen“ der Karte |
| `components/shared/__tests__/previewVerdrahtungHubs.test.ts` | entfällt | Verdrahtung Hub → Karte → abgeschickter Körper; Karte und Verdrahtung existieren nicht mehr (Abwesenheit sichert der neue Test zu) |
| `components/alerts-tab/__tests__/alarme_tab_sprache.test.ts` | angepasst | Vorschau-bezogene Sprachzusicherungen entfallen; übrige Sprach-Zusicherungen bleiben |
| `components/alerts-tab/__tests__/f7Pruefstand.ts`, `f7KatalogAnker.ts` | angepasst | Anker auf entfernte `alarme.vorschau.*`-Schlüssel und Karte entfernen; übrige Anker bleiben |
| `components/shared/__tests__/s3b2795_zustellung_struktur.test.ts` | angepasst | `MARKER` ohne `beispiel-alarm`; AC-30-Block (Karte je Kanal) wird zu „Abschnitt Beispiel-Alarm fehlt“ |
| `components/shared/__tests__/rework_3036_zustellung_ohne_uebergang.test.ts` | angepasst | AC-7: „Beispiel-Alarm letzter Abschnitt“ wird zu „letzter Abschnitt ist `stille-stunden`, kein `zustellung-beispiel-alarm`“ |
| `components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts` | angepasst | Einträge `AlertPreviewCard kind="vergleich"/"route"` der Zweig-Ratsche entfernen |
| `components/shared/__tests__/reiter_sprunglinks_nur_neue_kennungen.test.ts` | angepasst | Datei-Einträge der Karte entfernen |
| `components/shared/__tests__/s3a2794_eine_wmt_instanz.test.ts`, `s3b2795_zustellung_profil_einmal.test.ts`, `s3a2794_zustellung_ziel_und_bereich.test.ts`, `zustellung_tab_laedt_keine_compare_klebeschicht.test.ts` | angepasst | Zeile `BeispielAlarm` aus den Dateilisten/Einbettungszählungen entfernen; „genau einmal eingebettet“ wird zu „nicht eingebettet“ |
| `components/shared/__tests__/infobox_nur_beim_anlegen.test.ts` | angepasst | Kettenende statt `BeispielAlarm` neuer letzter Abschnitt |
| `components/shared/__tests__/alarme_tab_ohne_zustellung_3332.test.ts`, `…3333.test.ts` | angepasst | Verweis auf den Beispiel-Alarm als „bleibt“ umdrehen: Abschnitt `sample` fehlt |
| `components/compare/__tests__/fix_3061_hub_hydrierer.test.ts` | angepasst | Fall „Beispiel-Alarm hat für Altbestand Regeln“ (`beispielAlarmRegeln`) entfällt mit der Prop; Hydrierer-Fälle bleiben |
| `components/compare/__tests__/compare_layout_tab_dissolution.test.ts` | angepasst | „ZustellungTab mountet genau einen Beispiel-Alarm“ wird zu „keinen“ |
| `components/molecules/__tests__/test_alarm_3441.test.ts` | geprüft | Treffer ist nur der Untertitel des Test-Alarm-Eintrags; bleibt unverändert, sichert den Ersatzweg |
| `lib/__tests__/apiZeitlimit.test.ts` | angepasst | Zeitlimit-Fälle zu `alarmVorschau` entfallen mit der Funktion; übrige Zeitlimits bleiben |
| `lib/__tests__/etagRegistryQueue.test.ts`, `lib/__tests__/bausteine_waechter_regeln.ts` | angepasst | Verweise auf entfernte Karte/Helfer streichen |
| `i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts` | angepasst | Dateiliste ohne `AlertPreviewCard.svelte`, `alertPreviewHelpers.ts` |

E2E (Playwright, `frontend/e2e/`):

| Spec | Maßnahme | Grund |
|------|----------|-------|
| `versand-tab.spec.ts:133` | umgedreht | `alert-preview-card` im Reiter Zustellung wird zu `toHaveCount(0)` |
| `rework-3036-bloecke-schalter.spec.ts` B-5 (Zeilen ~195-206) | umgedreht | statt Karte sichtbar und letzter Abschnitt `beispiel-alarm`: Abschnitt fehlt, letzter Abschnitt ist `stille-stunden` |
| `s3b2795-zustellung-uebergang.spec.ts:35-52`, `s3b2795-zustellung.helpers.ts` | umgedreht | Abschnittsreihenfolge ohne `beispiel-alarm`; Text „Beispiel-Warnung“ darf nicht vorkommen |
| `s3b2795-zustellung-englisch.spec.ts:40` | umgedreht | englischer Reiter ohne „Example warning“ |
| `hub-versand-aufbau.spec.ts:65` (VA-1) | angepasst | Reihenfolge endet bei „Stille Stunden“, kein Beispiel-Alarm |
| `was-steht-wo-karte.spec.ts` WS-16 (Z. 731) | entfällt | prüft allein „Vorschau laden“ und Abo-Trennung der Vorschau; Mandantentrennung des Server-Wegs bleibt über Staging-/Python-Tests abgedeckt |
| `was-steht-wo-karte.spec.ts` WS-neu-5 | entfällt | Hinweis „keine Etappe“ in der Vorschau-Karte; ohne Karte gegenstandslos |
| `langlaeufer-zeitbudget-wirkort.spec.ts` Fall „Alarm-Vorschau (40 s)“ (Z. 103-155) | entfällt | Zeitbudget war nur über den Knopf „Vorschau laden“ erreichbar; andere Zeitbudget-Fälle bleiben |
| `sicherheitsrichtlinie-ohne-verletzung.spec.ts` Fall „Alarm-Vorschau (srcdoc-iframe)“ (Z. 166-201) | entfällt | der srcdoc-iframe existierte nur in der Vorschau-Karte; übrige Seiten-Fälle der Richtlinie bleiben |
| `kind-required-3444.staging.spec.ts` | unberührt | prüft den Server-Endpunkt `alert-preview`, der bleibt |
| `hub-test-alarm.staging.spec.ts`, `trip-outlook-metric-selection.staging.spec.ts` | geprüft | Treffer nur Test-Alarm-Untertitel bzw. Text; nur anpassen, falls sie die Vorschau-Karte erwarten |

Die genaue Zeilen- und Fallzählung ergibt sich in der Umsetzung per `grep`; jeder entfallende Fall wird im Pull-Request-Text einzeln mit dem Grund aus dieser Tabelle vermerkt.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Neuer Unit-Test `zustellung_ohne_beispiel_alarm_3458.test.ts`: GIVEN Reiter Zustellung (Trip und Orte) gerendert / WHEN Abschnitte gelesen / THEN kein `data-abschnitt="beispiel-alarm"`, kein `zustellung-beispiel-alarm`, kein `alert-preview-card`, kein „Vorschau laden“ (RED heute: Abschnitt vorhanden).
- [ ] Gleicher Test: GIVEN Alarm-Reiter im Anlegen (Trip und Orte) / WHEN gerendert / THEN kein Abschnitt „Beispiel-Warnung“; `alarmeTabSections` enthält `sample` nicht.
- [ ] Gleicher Test: GIVEN Katalog DE und EN / WHEN Schlüssel geprüft / THEN weder `alarme.beispiel_warnung` noch `alarme.vorschau.*`; `api.ts` exportiert kein `alarmVorschau`.
- [ ] Gleicher Test: GIVEN Test-Schicken-Menü / WHEN gerendert / THEN Eintrag Test-Alarm weiter vorhanden.
- [ ] Umgekehrte E2E-Zusicherungen (`versand-tab.spec.ts`, `rework-3036-bloecke-schalter.spec.ts`, `s3b2795-zustellung-uebergang.spec.ts`, `s3b2795-zustellung-englisch.spec.ts`, `hub-versand-aufbau.spec.ts`) gegen Staging in `/e2e-verify`.
- [ ] Kern-Schicht: Katalog-Paritäts-Ratschen und `keine_hartkodierten_nutzertexte.test.ts` grün; Python- und Go-Tests unverändert.

## Acceptance Criteria

- **AC-1:** Given ein Trip oder ein Orts-Vergleich im Hub / When der Reiter Zustellung angezeigt wird / Then endet der Reiter bei „Stille Stunden“ und zeigt weder einen Abschnitt „Beispiel-Alarm“ noch eine Vorschau-Karte noch den Knopf „Vorschau laden“.
  - Test: Render-Test beider Kontexte plus E2E im Hub (Trip und Orte): die Abschnittsliste enthält kein `beispiel-alarm`, kein Vorschau-Knopf ist auffindbar.

- **AC-2:** Given das Anlegen eines neuen Trips oder Orts-Vergleichs / When der Reiter Zustellung angezeigt wird / Then fehlt dort ebenfalls der Abschnitt „Beispiel-Alarm“ samt Vorschau-Karte und „Vorschau laden“.
  - Test: Render des Anlege-Editors (Trip und Orts-Vergleich) sowie E2E im Anlegen: keine Vorschau-Karte, Reihenfolge der übrigen Abschnitte unverändert.

- **AC-3:** Given das Anlegen eines Trips oder Orts-Vergleichs / When der Alarm-Reiter angezeigt wird / Then gibt es keinen Abschnitt „Beispiel-Warnung“, und die übrigen Abschnitte des Alarm-Reiters sind unverändert da.
  - Test: Render des Alarm-Reiters in beiden Kontexten; `alarmeTabSections` enthält `sample` nicht, die übrigen Abschnitte bleiben in ihrer Reihenfolge.

- **AC-4:** Given ein Trip oder Orts-Vergleich im Hub / When das Menü „Test schicken ▾“ geöffnet wird / Then ist der Eintrag Test-Alarm weiterhin vorhanden und der einzige Weg, einen Beispiel-Alarm auszulösen.
  - Test: bestehender Test-Alarm-Test (`test_alarm_3441`) bleibt grün; E2E öffnet das Menü und findet den Eintrag, während kein Vorschau-Knopf mehr existiert.

- **AC-5:** Given die Oberfläche in englischer Sprache / When die Reiter Zustellung und Alarm angezeigt werden / Then erscheinen weder „Example warning“ noch „Load preview“ noch ein Beispiel-Alarm-Abschnitt.
  - Test: E2E `s3b2795-zustellung-englisch.spec.ts` mit englischer Oberfläche: die Texte „Example warning“ und „Load preview“ kommen nicht vor.

- **AC-6:** Given der Server läuft unverändert / When `POST /api/briefings/{id}/alert-preview` oder `POST /api/trips/{id}/alert-preview` aufgerufen wird / Then antwortet er wie bisher, einschließlich der Ablehnung ohne gültige Briefing-Art.
  - Test: `kind-required-3444.staging.spec.ts` und die bestehenden Python-Tests zu `alert-preview` laufen ohne Änderung grün.

- **AC-7:** Given der Übersetzungskatalog Deutsch und Englisch / When die Katalog-Wächter laufen / Then enthalten beide Sprachen keine verwaisten Vorschau-Schlüssel (`alarme.beispiel_warnung`, `alarme.vorschau.*`) und die Katalog-Paritäts-Ratschen sowie die Prüfung auf hartkodierte Nutzertexte sind grün.
  - Test: Katalog-Paritäts-Test und `keine_hartkodierten_nutzertexte.test.ts` laufen grün; der neue Test sichert die Abwesenheit der Schlüssel in beiden Sprachen zu.

- **AC-8:** Given die geänderten und gelöschten Bestandstests / When die Kern-Schicht des Frontends läuft / Then ist sie vollständig grün, und jeder entfallene Test oder E2E-Fall ist in dieser Spec mit Grund aufgeführt (keine still verschwundene Zusicherung).
  - Test: `node --test` über die in der Tabelle genannten Testdateien grün; Abgleich der gelöschten Testdateien (`git diff --name-status`) gegen die Tabelle in dieser Spec.

## Definition of Done

- [ ] Beispiel-Alarm, Vorschau-Karte und „Vorschau laden“ in Zustellung (Hub und Anlegen, Trip und Orte) entfernt (AC-1, AC-2)
- [ ] „Beispiel-Warnung“ im Alarm-Reiter entfernt, Test-Alarm in „Test schicken ▾“ unverändert (AC-3, AC-4)
- [ ] Englische Oberfläche und Katalog DE/EN ohne Vorschau-Texte, Ratschen grün (AC-5, AC-7)
- [ ] Server-Endpunkte `alert-preview` unverändert (AC-6)
- [ ] Jeder entfallene oder umgedrehte Test steht mit Grund in der Tabelle; Kern-Schicht grün, alle 6 CI-Checks grün, Adversary-Verdict VERIFIED (AC-8)

## Known Limitations

- Die Server-Endpunkte `alert-preview` haben nach dem Rückbau keinen Nutzer in der Oberfläche mehr; sie dienen nur Validatoren, Staging-Prüfungen und `alarm_testeinspeisung.md`. Ein späteres Entfernen wäre ein eigenes Issue.
- Die Spezifikationen `alert_preview_echte_segmente.md` und `fix_2219_alarm_vorschau_haerten.md` bleiben im Backend-Teil gültig; ihr UI-Teil (Vorschau-Karte, Knopf „Vorschau laden“, Zeichenzähler) ist durch #3458 abgelöst. Ebenso ist `rework_3036_uebergangsblock_aufloesen.md` AC-7 (Beispiel-Alarm als letzter Abschnitt) abgelöst; der Rest dieser Spec gilt weiter. Die drei Specs erhalten dazu einen Vermerk im Changelog.
- Der Test-Alarm (#3441) zeigt keine Vorschau im Browser, sondern verschickt an die Alarm-Kanäle; das ist die bewusste PO-Entscheidung A14.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Rückbau einer Oberfläche gemäß PO-Entscheidung A14 (ersetzt durch Test-Alarm #3441); keine neue Architekturentscheidung, kein Backend- oder Datenmodell-Eingriff, keine Abweichung von bestehenden ADRs.

## Changelog

- 2026-11-27: Initial spec created (Issue #3458, Scheibe S5b-2)
