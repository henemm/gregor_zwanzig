# Context: fix-3458-alarm-vorschau-entfernen (Issue #3458)

## Request Summary
S5b-2 (Scheibe S5 #2797, Epic #2791): Die Alarm-Vorschau-Oberfläche („Beispiel-Alarm“ im Reiter
Zustellung, „Beispiel-Warnung“ im Alarm-Reiter, Knopf „Vorschau laden“) wird entfernt. Ersatz ist der
Test-Alarm im Menü „Test schicken ▾“ (#3441, PO-Entscheidung A14). Server-Endpunkte `alert-preview`
bleiben als Prüfwerkzeug (Validatoren, Staging, `alarm_testeinspeisung.md`).

## Related Files (Produktivcode)
| Datei | Rolle | Maßnahme |
|---|---|---|
| `frontend/src/lib/components/organisms/zustellung-tab/BeispielAlarm.svelte` | Abschnitt „Beispiel-Alarm“ (letzter Abschnitt Zustellung, Trip+Orte) | löschen |
| `frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte:26,45,54,116` | bindet BeispielAlarm ein, Prop `beispielAlarmRegeln` | Einbindung + Prop entfernen |
| `frontend/src/lib/components/compare/CompareTabs.svelte:41,474-479,831` | berechnet `beispielAlarmRegeln` für Orte | Ableitung + Prop-Weitergabe entfernen |
| `frontend/src/lib/components/shared/AlarmeTab.svelte:36,42,607-613` | Abschnitt `sample` („Beispiel-Warnung“) im Alarm-Reiter | Abschnitt + Imports entfernen |
| `frontend/src/lib/components/shared/alarme-tab/alarmeTabSections.ts:31` | hängt `sample` an Abschnittsliste | Zeile entfernen |
| `frontend/src/lib/components/alerts-tab/AlertPreviewCard.svelte` | Vorschau-Karte (Betreff/Mail/Telegram/SMS, Zeichenzähler) | löschen |
| `frontend/src/lib/components/alerts-tab/alertPreviewHelpers.ts` | Payload-Bau, Fehlertext, `vergleichAlarmRegeln` | löschen (keine weiteren Nutzer nach Entfernen) |
| `frontend/src/lib/api.ts:308-319` | `langlaeufer.alarmVorschau`, `alarmVorschau()` | entfernen (einzige Nutzer: AlertPreviewCard + Zeitlimit-Tests) |
| `frontend/src/lib/i18n/messages/{de,en}/alarme.json` | `alarme.beispiel_warnung`, `alarme.vorschau.*` | Schlüssel entfernen, sofern ungenutzt |

## Betroffene Tests (Bestandstests, anpassen statt still löschen)
Unit (`node --test`): `alerts-tab/alertPreviewHelpers.test.ts`, `alertPreviewEmpty.test.ts`,
`issue_850_alert_metrics_stale.test.ts`, `__tests__/alertPreviewKind.test.ts`,
`alertPreviewBerechnetHinweis.test.ts`, `alertPreviewKeineEtappen.test.ts`, `alarme_tab_sprache.test.ts`,
`f7Pruefstand.ts`, `f7KatalogAnker.ts`; `shared/__tests__/previewVerdrahtungHubs.test.ts`,
`s3b2795_zustellung_struktur.test.ts`, `context_herkunft_zweige_eingefroren.test.ts`,
`reiter_sprunglinks_nur_neue_kennungen.test.ts`, `rework_3036_zustellung_ohne_uebergang.test.ts`,
`s3a2794_*`, `infobox_nur_beim_anlegen.test.ts`, `alarme_tab_ohne_zustellung_3332/3333.test.ts`;
`compare/__tests__/fix_3061_hub_hydrierer.test.ts`, `compare_layout_tab_dissolution.test.ts`;
`lib/__tests__/apiZeitlimit.test.ts`, `etagRegistryQueue.test.ts`, `bausteine_waechter_regeln.ts`;
`i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts`; `molecules/__tests__/test_alarm_3441.test.ts`.

E2E (Playwright): `versand-tab.spec.ts:133`, `rework-3036-bloecke-schalter.spec.ts:195-204`,
`s3b2795-zustellung-uebergang.spec.ts:35-50`, `s3b2795-zustellung-englisch.spec.ts:40`,
`hub-versand-aufbau.spec.ts:65`, `was-steht-wo-karte.spec.ts:731` (WS-16, WS-neu-5),
`langlaeufer-zeitbudget-wirkort.spec.ts:134-147`, `sicherheitsrichtlinie-ohne-verletzung.spec.ts:198`.
Unberührt (Server-Endpunkt bleibt): `kind-required-3444.staging.spec.ts`.

Regel: Zusicherungen „Beispiel-Alarm ist da“ werden zu „Beispiel-Alarm ist weg“ umgedreht; Tests, die
ausschließlich das Innenleben der entfernten Karte prüfen, entfallen mit ihr, je mit Vermerk im PR/Spec
(welcher Test, warum gegenstandslos). Zusicherungen über Server-Wege (CSP, Zeitbudget) entfallen nur,
wenn sie allein über die Karte erreichbar waren.

## Existing Patterns
- Abschnittsmarker `data-abschnitt="…"` im Reiter Zustellung; `beispiel-alarm` war der letzte.
- Kontext-Unterschied als Daten (Ratsche `context_herkunft_zweige_eingefroren`) — Einträge für den
  Beispiel-Alarm müssen dort mit entfernt werden.
- Test-Alarm (#3441) nutzt eigene Backend-Wege, NICHT `alertPreviewHelpers` (geprüft per grep).

## Dependencies / Dependents
- Spec `docs/specs/modules/feat_3441_test_alarm.md` verweist ausdrücklich auf dieses Issue als Folge.
- Specs `alert_preview_echte_segmente.md`, `fix_2219_alarm_vorschau_haerten.md` beschreiben die
  Vorschau-UI → als abgelöst kennzeichnen (Backend-Teile gelten weiter).
- Spec `rework_3036_uebergangsblock_aufloesen.md` (AC-7 Beispiel-Alarm) → Abschnitt abgelöst.

## Risks
- Viele Bestandstests: Gefahr, dass Zusicherungen still verschwinden ⇒ jede Entfernung begründen.
- i18n-Katalog-Ratschen (DE/EN-Parität, ungenutzte Schlüssel) müssen grün bleiben.
- Sprung-Links/Elementlisten (Mockup-Abgleich #3009) dürfen keinen Verweis auf `beispiel-alarm` behalten.
- Kein Backend-Eingriff: Endpunkte und Python-Tests unverändert.

## Analysis

**Type:** Feature-Änderung (Rückbau einer Oberfläche, abgelöst durch #3441). Score 2 ⇒ Kontext und
Analyse in einem Durchgang.

**Affected Files (Change Type):**
- DELETE `alerts-tab/AlertPreviewCard.svelte` (220), `alerts-tab/alertPreviewHelpers.ts` (145),
  `organisms/zustellung-tab/BeispielAlarm.svelte` (40)
- MODIFY `ZustellungTab.svelte`, `CompareTabs.svelte`, `AlarmeTab.svelte`, `alarmeTabSections.ts`, `api.ts`,
  `i18n/messages/{de,en}/alarme.json`
- DELETE Unit-Tests, die nur das Innenleben der Karte/Helfer prüfen: `alertPreviewHelpers.test.ts`,
  `alertPreviewEmpty.test.ts`, `issue_850_alert_metrics_stale.test.ts`, `__tests__/alertPreviewKind.test.ts`,
  `alertPreviewBerechnetHinweis.test.ts`, `alertPreviewKeineEtappen.test.ts`, `previewVerdrahtungHubs.test.ts`
- MODIFY Bestandstests mit Strukturzusicherungen (Abschnittsreihenfolge, Ratschen, Katalog-Anker,
  Prüfstand F7, Zeitlimit, Wächter-Regeln): Beispiel-Alarm/`sample` ⇒ Abwesenheit zusichern
- MODIFY E2E-Specs (siehe oben): Präsenz ⇒ Abwesenheit; reine Vorschau-Abläufe (WS-16, WS-neu-5,
  Zeitbudget Alarm-Vorschau, CSP-Iframe der Vorschau) entfallen mit Vermerk
- MODIFY Specs `alert_preview_echte_segmente.md`, `fix_2219_alarm_vorschau_haerten.md`,
  `rework_3036_uebergangsblock_aufloesen.md`: Vermerk „UI abgelöst durch #3458“ (Backend gilt weiter)

**Scope/Risk:** Produktivcode fast nur Löschungen; der LoC-Wächter zählt nur hinzugefügte Zeilen ⇒ kein
Override nötig. Risiko niedrig (reine Oberfläche, kein Backend, keine Daten). Hauptrisiko: still
verschwindende Zusicherungen ⇒ Spec führt eine Tabelle „entfernter Test → Grund“.

**Technical Approach:**
1. RED: neuer Unit-Test `zustellung_ohne_beispiel_alarm_3458.test.ts` (Render beider Kontexte des
   Reiters Zustellung und des Alarm-Reiters im Anlegen: kein `data-abschnitt="beispiel-alarm"`, kein
   `alert-preview-card`, kein „Vorschau laden“; `alarmeTabSections` ohne `sample`; Test-Alarm-Eintrag
   im Menü weiterhin vorhanden) + E2E-Umkehr in `versand-tab.spec.ts`/`rework-3036-bloecke-schalter.spec.ts`.
2. GREEN: Komponenten/Helfer löschen, Einbindungen und `api.ts`-Funktionen entfernen, Katalogschlüssel
   DE/EN entfernen, Bestandstests anpassen.
3. Server-Endpunkte und Python unberührt.

**Dependencies:** #3441 (Test-Alarm, ausgeliefert) ist Ersatzweg. Abnahme #3009 hängt daran.

**Open Questions:** keine (PO-Entscheidung A14 liegt vor; Endpunkte bleiben laut Issue).
