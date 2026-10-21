---
entity_id: feat_2278_aktionsmodell
type: module
created: 2026-10-17
updated: 2026-10-17
status: implemented
version: "1.0"
tags: [trip, compare, aktionsmodell, liste, hub, mobil, sende-dialog, epic-2345, p3]
---

# Ein Aktionsmodell für Liste, Hub und Mobil bei Trip und Ortsvergleich (#2278)

## Approval

- [ ] Approved (PO)

## Purpose

Heute muss der Nutzer dieselbe Handlung bei Trip und Ortsvergleich an verschiedenen Orten suchen,
mit anderer Beschriftung und teils ohne Wirkung. Diese Spec führt EINE Aktionsquelle
`subscriptionActions(kind, status, surface)` für Liste, Hub und Mobil beider Arten ein
(Epic #2345, Etappe P3, DoD-2 und DoD-3). Mit demselben Umbau werden #1064 (Trip-Löschen im Hub
unerreichbar) vollständig und die Defekte „mobiles Trip-‚Briefing senden' sendet nicht" sowie
„Compare-Hub sendet ohne Rückfrage/Ziel" behoben. #2214 (Compare-Hub-Löschbestätigung) ist
bereits CLOSED; seine Test-IDs bleiben erhalten.

Alle Acceptance Criteria gehören in diesen einen Workflow. Die Scheiben unten sind nur die
Bau-Reihenfolge.

## Source

- **Neu:** `frontend/src/lib/components/shared/subscriptionActions.ts`, `shared/subscriptionExec.ts`,
  `lib/server/` (Profil-Loader), `molecules/SendConfirmDialog.svelte`, `molecules/StatusFilterPills.svelte`
- **Verallgemeinert:** `compare/CompareKebab.svelte` → `molecules/SubscriptionKebab.svelte`,
  `mobile/MCompareActionSheet.svelte` → `mobile/SubscriptionActionSheet.svelte`,
  `compare/CompareTile.svelte` → `organisms/SubscriptionCard.svelte`
- **Entfallen:** `molecules/ReportConfigDialog.svelte`, `molecules/TestReportDialog.svelte`
- **Umgebaut:** `routes/trips/+page.svelte`, `routes/trips/[id]/+page.svelte`, `routes/compare/+page.svelte`,
  `routes/compare/[id]/+page.svelte` (jeweils + `+page.server.ts`), `trip-new/TripNewEditor.svelte`,
  `routes/_home/CompareKachel.svelte`, `compare/subscriptionHelpers.ts`

## Estimated Scope

- **LoC:** ca. +900 / −700 (`loc_limit_override` nötig, je Scheibe messen)
- **Files:** ca. 16–20 produktiv + Tests
- **Effort:** high; Risiko MEDIUM (reines Frontend, Backend unberührt; Risiko liegt in vielen Beschriftungs-/testid-Tests, der Startseiten-Kachel und der Archiv-Ausblendung der Trip-Liste)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Go-API Trip `PATCH /api/trips/{id}/state`, `DELETE`, `POST /send` | Endpunkt | Pausieren/Archivieren, Löschen, Senden — unverändert |
| Go-API Compare `PUT /api/compare/presets/{id}`, `PATCH …/state`, `DELETE`, `POST …/send` | Endpunkt | Pausieren (Schedule), Archivieren, Löschen, Senden — unverändert |
| `lib/utils/sendOutcome.ts`, `compare/compareHubPersistenz.ts` | Util | Laufzustand Senden; Compare-Pause mit Read-Modify-Write |
| `lib/utils/tripStatus.ts` (`deriveTripStatus`, `tripStatus()`), `compare/subscriptionHelpers.ts` (`deriveStatusFromPreset`) | Util | Status-Verbraucher, bleiben UNVERÄNDERT |
| `shared/versand-tab/sendTargetLabel.ts` | Util | echtes Sende-Ziel, wertet alle vier Kanäle inkl. Premium-SMS aus |
| `molecules/ConfirmDialog`, `organisms/ListTable*`, `shared/subscriptionTabs.ts` | Bausteine | Basis für Dialog, Listen, Deep-Links `?tab=alarme` / `?tab=wetter-metriken` |
| `shared/VersandTab.svelte`, `MailInhaltCard.svelte` | Bausteine | Ersatz für die entfallende Alert-Konfiguration |

## Implementation Details

1. **Aktionsquelle:** `subscriptionActions(kind, status, surface: 'list'|'hub'|'mobile')` als reine Funktion.
   IDs: `pause|resume|send|preview|alarms|weather|edit|archive|unarchive|delete|continue-setup`.
   Labels kind-unabhängig. Reihenfolge Liste/Mobil: Pausieren/Fortsetzen · Senden · Vorschau · Alarme ·
   Wetter-Metriken · Bearbeiten · Löschen; Entwurf: Setup fortsetzen · Löschen. Hub-Kebab:
   Pausieren/Fortsetzen · Archivieren/Reaktivieren · Löschen (Senden ist Primärknopf). Archivieren
   steht nicht in der Liste (Liste blendet Archiviertes aus).
2. **Lebenszyklus-Schicht** `subscriptionLifecycle(kind, obj)` → draft/active/paused/archived als dünner
   Wrapper auf die bestehenden Ableitungen. `deriveTripStatus`, `tripStatus()` (Cockpit) und
   `deriveStatusFromPreset` bleiben unverändert.
3. **Ausführungs-Adapter** `subscriptionExec.ts` je kind: Trip über `PATCH /state`; Compare-Pause über `PUT`
   des ganzen Presets mit Read-Modify-Write (Test `list_toggle_read_modify_write` bleibt grün).
   **Kein Backend-Eingriff.** Die zwei Backend-Pausierwege (Trip `PATCH /state`, Compare `PUT schedule`)
   bleiben bis P4/P7 bestehen und sind nur durch den Adapter verdeckt.
4. **Alert-Konfiguration entfällt:** `ReportConfigDialog` (einziger Aufrufer `routes/trips/+page.svelte`)
   wird gelöscht. Grund (gemessen): `saveReportConfig` sendet `{...full, report_config: reportConfig}`
   und ersetzt `report_config` komplett; dabei gehen `send_premium_sms` und alle dem Dialog unbekannten
   Felder verloren (Verstoß gegen Read-Modify-Write und Kanal-Parität). Ersatz: Listen-Aktionen
   „Alarme" (`?tab=alarme`) und „Wetter-Metriken" (`?tab=wetter-metriken`) für beide Arten; Zeiten,
   Kanäle und Mail-Inhalt (`multi_day_trend_reports`, `show_compact_summary`,
   `wind_exposition_min_elevation_m`, `morning_time`) sind im geteilten Versand-Tab bearbeitbar.
5. **Sende-Dialog** `SendConfirmDialog` (auf `ConfirmDialog`, ersetzt `TestReportDialog`) für Liste, Hub und
   Mobil beider Arten: Ziel via `sendTargetLabel`, sperrt nur wenn kein Kanal liefern kann; Morgen/Abend-Wahl
   nur bei Trip, Default Morgen.
6. **Profil-Loader:** geteilter fail-soft Helfer in `lib/server/` (Muster `routes/compare/+page.server.ts`),
   eingebunden in `routes/trips/+page.server.ts`, `routes/trips/[id]/+page.server.ts`,
   `routes/compare/[id]/+page.server.ts`. Ohne Session `profile=null`, nie Rückfall auf einen Default-Nutzer.
7. **Bausteine verallgemeinern statt neu bauen** (Pendant-Sperre): Kebab, Aktionsblatt und Karte
   werden kind-neutral; die Trip-Inline-Karte und das Inline-Sheet im Route-File entfallen;
   Filter-Pillen werden geteilt (`StatusFilterPills`). Neue Dateien liegen in `molecules/`, `organisms/`,
   `mobile/`, `shared/` (außerhalb der Pendant-Sperre).
8. **Archiv-Parität:** Trip-Liste blendet Archiviertes aus wie die Compare-Liste.
9. **Trip-Hub:** Lebenszyklus-Kebab statt Breadcrumb-Aktionsleiste; Löschen mit Bestätigungsdialog
   (Compare-Test-IDs `compare-detail-delete-confirm-*` bleiben); tote „Trips"-Breadcrumbs
   (`routes/trips/[id]/+page.svelte` ~:259, `trip-new/TripNewEditor.svelte` ~:363) werden verlinkt;
   toter Code der Trip-Liste (`primaryLabel`, `handlePrimaryAction`, `handleArchive`, unerreichbarer
   Archiv-Dialog) entfällt.

## Umsetzungs-Reihenfolge (nur Bau-Reihenfolge, alle ACs gehören in diesen Workflow)

- **S1:** Aktionsquelle + Lebenszyklus-Schicht + Ausführungs-Adapter + Profil-Loader (rein, Tabellentest)
- **S2:** Bausteine kind-neutral + Compare-Seiten (Liste, Hub, Mobil mit Filtern/Blatt, Sende-Dialog)
- **S3:** Trip-Liste + Trip-Hub (Pausieren, Kebab, Dialoge, Archiv-Filter, #1064, toter Code, Entfall `ReportConfigDialog`)
- **S4:** Test- und Playwright-Bereinigung, Durchklick-Test beider Arten

## Expected Behavior

- **Input:** Nutzer öffnet Aktionen eines Trips oder Ortsvergleichs in Liste, Hub oder Mobil
- **Output:** dieselben Handlungen an derselben Stelle, gleich beschriftet, mit gleichem Ergebnis; jede angezeigte Aktion wirkt
- **Side effects:** Pausieren/Archivieren/Löschen/Senden wie bisher über die bestehenden Endpunkte

## Acceptance Criteria

- **AC-1:** Given ein aktiver Trip in der Desktop-Trip-Liste / When der Nutzer das Zeilenmenü öffnet / Then enthält es „Pausieren" an erster Stelle, in derselben Beschriftung und Reihenfolge wie beim Ortsvergleich, und die Wahl pausiert den Trip (Status „pausiert").
  - Test: `frontend/e2e/trips-list-aktionen.spec.ts` (Playwright, Desktop) + Unit `routes/trips/__tests__/trip_list_pause.test.ts`.

- **AC-2:** Given die mobile Vergleichs-Liste / When der Nutzer das Menü einer Karte öffnet / Then sind Pausieren/Fortsetzen · Senden · Vorschau · Alarme · Wetter-Metriken · Bearbeiten · Löschen erreichbar (Entwurf: Setup fortsetzen · Löschen), und die Liste bietet Filter-Pillen Alle/Aktiv/Geplant/Pausiert/Fertig wie beim Trip.
  - Test: `routes/compare/__tests__/compare_list_mobile_aktionen.test.ts` + `frontend/e2e/aktionsmodell-durchklick.spec.ts` (Mobil-Viewport).

- **AC-3:** Given „Senden" aus Trip-Liste, Trip-Hub, Compare-Liste oder Compare-Hub (Desktop und Mobil) / When der Dialog erscheint / Then nennt er das echte Versandziel (E-Mail-Adresse bzw. Chat, auch Premium-SMS) aus `sendTargetLabel`, der Bestätigen-Knopf ist gesperrt, wenn kein Kanal liefern kann, und es wird erst nach Bestätigung gesendet.
  - Test: `lib/components/molecules/__tests__/send_confirm_dialog.test.ts` (Ziel, Sperre, kein Request vor Bestätigung, beide Arten) + Playwright-Durchklick.

- **AC-4:** Given der Trip-Dialog „Senden" / When er geöffnet wird / Then bietet er die Wahl Morgen/Abend mit Vorauswahl Morgen, der Ortsvergleich-Dialog bietet keine solche Wahl, und der gesendete Bericht entspricht der gewählten Option.
  - Test: `send_confirm_dialog.test.ts` (kind=trip vs. kind=compare, `report_type` im Request).

- **AC-5:** Given der Trip-Hub oder der Compare-Hub / When der Nutzer im Lebenszyklus-Menü „Löschen" wählt / Then erscheint derselbe Bestätigungsdialog mit dem Namen (Compare-Test-IDs `compare-detail-delete-confirm-*` bleiben), es geht erst nach Bestätigung ein DELETE raus, und danach landet der Nutzer in der jeweiligen Liste (schließt #1064).
  - Test: `routes/trips/[id]/__tests__/trip_hub_loeschen.test.ts` + bestehender `routes/compare/__tests__/compare_hub_loeschen_bestaetigung`.

- **AC-6:** Given eine Tabelle mit beiden Arten (Trip, Ortsvergleich) × allen Status (Entwurf, aktiv, pausiert, archiviert) × allen Flächen (Liste, Hub, Mobil) / When `subscriptionActions` aufgerufen wird / Then entsprechen IDs, Beschriftungen und Reihenfolge je Zelle EINER Erwartungstabelle, und beide Arten liefern bei gleichem Status identische Ergebnisse.
  - Test: `lib/components/shared/__tests__/subscriptionActions.test.ts` (Tabellentest, `node --test`). Ersetzt die Ticket-Formulierung „genau eine Quelle im Code" durch diese Verhaltensprüfung; die Dateiinhalt-Prüfung AC-6c in `routes/trips/issue_477_486.test.ts` wird gelöscht, nicht umgeschrieben.

- **AC-7:** Given ein Nutzer pausiert bzw. setzt fort in Liste oder Hub / When die Aktion ausgeführt wird / Then werden bei Trip nur der Pausen-Zustand und bei Ortsvergleich der Zeitplan verändert, alle übrigen Felder des Objekts bleiben unverändert (Read-Modify-Write), und die Status-Anzeigen von Cockpit und Archiv-Seite zeigen weiterhin dasselbe wie vorher.
  - Test: `compare/__tests__/list_toggle_read_modify_write` (bleibt grün) + `lib/components/shared/__tests__/subscriptionExec.test.ts` (Trip PATCH `{paused}`, kein Verlust unbekannter Felder) + `lib/utils/tripStatus.test.ts` unverändert.

- **AC-8:** Given die Trip-Liste und die Compare-Liste / When der Nutzer „Alarme" oder „Wetter-Metriken" wählt / Then öffnet sich bei beiden Arten der jeweilige Hub direkt auf dem Reiter (`/trips/{id}?tab=alarme` bzw. `/compare/{id}?tab=alarme`, `?tab=wetter-metriken`); die Aktion „Alert-Konfiguration" und der Dialog `ReportConfigDialog` existieren nicht mehr.
  - Test: Playwright `aktionsmodell-durchklick.spec.ts` (URL und aktiver Reiter, beide Arten) + Unit `subscriptionActions.test.ts` (IDs `alarms`/`weather`, keine ID `alert-config`).

- **AC-9:** Given ein Trip mit `send_premium_sms` und weiteren Feldern in `report_config`, darunter den Alt-Schwellen `change_threshold_temp_c/_wind_kmh/_precip_mm` und `alert_on_changes` / When der Nutzer über den Versand-Tab speichert / Then bleiben diese Felder, `send_premium_sms` und alle dem Editor unbekannten Felder unverändert erhalten, und kein Weg in der Oberfläche ersetzt `report_config` mehr komplett.
  - Test: `shared/versand-tab/__tests__/versand_speichern_erhaelt_report_config.test.ts` (Roundtrip über `mergeReportConfig`, beide Arten) + Playwright-Speichern-Roundtrip gegen die API. **Bewusste Abweichung:** die drei Alt-Schwellen und `alert_on_changes` sind danach in KEINER Oberfläche mehr bearbeitbar; sie bleiben in den Daten und werden vom Python-Core (`src/services/weather_change_detection.py`) weiter gelesen.

- **AC-10:** Given zwei verschiedene angemeldete Nutzer A und B mit jeweils eigener Empfängeradresse und eigenem Chat / When B in Trip-Liste, Trip-Hub oder Compare-Hub „Senden" öffnet / Then zeigt der Dialog ausschließlich Ziele von B, nie `mail_to` oder Chat von A; ohne Session ist das Ziel „unbekannt" und der Versand gesperrt, nie ein Rückfall auf einen Default-Nutzer.
  - Test: `lib/server/__tests__/profileLoader.test.ts` (zwei Sessions, kein Default-Rückfall, fail-soft `profile=null`) + Playwright mit zwei Nutzern gegen Staging.

- **AC-11:** Given ein Trip ist archiviert / When der Nutzer die Trip-Liste öffnet / Then erscheint er dort nicht (wie bei Ortsvergleichen), die Filter-Pille „Fertig" zeigt nur Trips mit vergangenem Datum, die nicht archiviert sind, der archivierte Trip bleibt auf der Archiv-Seite auffindbar, und das Cockpit zeigt unverändert dasselbe wie vorher.
  - Test: `routes/trips/__tests__/tripPausiertFilter` (angepasst, Fall „archiviert") + `routes/archiv/archiveHelpers.test.ts` + `lib/utils/__tests__/tripStatusConsolidation.test.ts` unverändert.

- **AC-12:** Given der Trip-Hub (Desktop und Mobil) / When der Nutzer das Lebenszyklus-Menü öffnet / Then enthält es Pausieren/Fortsetzen · Archivieren/Reaktivieren · Löschen anstelle der bisherigen Breadcrumb-Aktionsleiste, „Senden" ist der Primärknopf und öffnet den Sende-Dialog, und der Compare-Hub zeigt dieselbe Menü-Struktur.
  - Test: Playwright `aktionsmodell-durchklick.spec.ts` (Hub, beide Arten, Desktop und Mobil) + Unit `subscriptionActions.test.ts` (Fläche `hub`).

- **AC-13:** Given die Breadcrumbs „Trips" im Trip-Hub und im Trip-Anlegen-Editor / When der Nutzer darauf klickt / Then führt er zur Trip-Liste `/trips`.
  - Test: Playwright `issue-592-593-trips-navigation` (angepasst) + Unit-Rendertest der beiden Breadcrumbs.

- **AC-14:** Given die mobile Trip-Liste und die mobile Vergleichs-Liste / When der Nutzer eine Karte öffnet / Then sieht er bei beiden Arten dieselbe Karte (`SubscriptionCard`) und dasselbe Aktionsblatt (`SubscriptionActionSheet`) mit denselben Filter-Pillen (`StatusFilterPills`); „Senden" im Blatt öffnet den Sende-Dialog und sendet nach Bestätigung wirklich (bisher öffnete mobiles Trip-„Briefing senden" nur die Vorschau).
  - Test: `organisms/__tests__/subscription_card.test.ts` + Playwright `aktionsmodell-durchklick.spec.ts` (Mobil-Viewport, prüft gesendeten Request).

- **AC-15:** Given die Startseite mit Ortsvergleich-Kacheln / When sie angezeigt wird / Then verhält sie sich wie heute: Klick öffnet den Hub, das Kebab-Menü der Kachel bietet nur „Bearbeiten" (öffnet den Hub), und keine der neuen Listen-Aktionen erscheint dort ohne Wirkung. (Gemessen: die Kachel zeigt heute ein Kebab, behandelt aber nur `edit`; wirkungslose Einträge entfallen aus Konsistenz mit AC-16.)
  - Test: `routes/_home/__tests__/compare_kachel_aktionen.test.ts` (Aktionsliste der Kachel = nur `edit`, Klick-Navigation).

- **AC-16:** Given jede angezeigte Aktion in Liste, Hub und Mobil von Trip und Ortsvergleich (Desktop und Mobil-Viewport) / When der Nutzer sie auslöst / Then tritt die Handlung tatsächlich ein (Request bzw. Navigation bzw. Dialog); es gibt kein Aktions-Element ohne Wirkung.
  - Test: Playwright `frontend/e2e/aktionsmodell-durchklick.spec.ts` (läuft für beide Arten, beide Viewports, alle Aktions-IDs).

- **AC-17:** Given der tote Code der Trip-Liste (`primaryLabel`, `handlePrimaryAction`, `handleArchive`, unerreichbarer Archiv-Dialog) und die Trip-Inline-Karte/-Sheet / When der Umbau fertig ist / Then bleibt das Verhalten der Liste inklusive Zeilen-Primärknopf „Briefing senden" und Löschen mit Bestätigung erhalten und alle bestehenden Listen-Tests (angepasst auf neue Beschriftungen/IDs) sind grün.
  - Test: `routes/trips/trips-list-send` (angepasst), `bug-282-295-trips-list-redesign`, `issue-268-trips-mobile-card-stack` (Playwright, angepasst).

## Test Plan

Bündelt die `Test:`-Zeilen der ACs. Frontend-Unit über `node --test`, Playwright unter `frontend/e2e/`.

**Neue Unit-Tests (Kern-Schicht):**
- [ ] `lib/components/shared/__tests__/subscriptionActions.test.ts` — Tabellentest beide Arten × Status × Flächen (AC-1, AC-6, AC-8, AC-12)
- [ ] `lib/components/shared/__tests__/subscriptionExec.test.ts` — Ausführungs-Adapter, Read-Modify-Write (AC-7)
- [ ] `lib/components/molecules/__tests__/send_confirm_dialog.test.ts` — Ziel, Sperre, Bestätigung, Morgen/Abend (AC-3, AC-4)
- [ ] `lib/server/__tests__/profileLoader.test.ts` — zwei Nutzer, kein Default-Rückfall (AC-10)
- [ ] `shared/versand-tab/__tests__/versand_speichern_erhaelt_report_config.test.ts` — `send_premium_sms` und Alt-Schwellen bleiben (AC-9)
- [ ] `routes/trips/__tests__/trip_list_pause.test.ts` (AC-1), `routes/trips/[id]/__tests__/trip_hub_loeschen.test.ts` (AC-5)
- [ ] `routes/compare/__tests__/compare_list_mobile_aktionen.test.ts` (AC-2), `organisms/__tests__/subscription_card.test.ts` (AC-14), `routes/_home/__tests__/compare_kachel_aktionen.test.ts` (AC-15)

**Neue Playwright-Tests (Live-Schicht):**
- [ ] `frontend/e2e/aktionsmodell-durchklick.spec.ts` — jede angezeigte Aktion beider Arten, Desktop + Mobil (AC-2, AC-3, AC-8, AC-12, AC-14, AC-16)
- [ ] `frontend/e2e/trips-list-aktionen.spec.ts` (AC-1); Zwei-Nutzer-Prüfung gegen Staging (AC-10)

**Angepasste Bestandstests:** siehe „Bewusst zu ändernde Tests" (AC-11, AC-13, AC-17).

## Bewusst zu ändernde Tests

- `lib/components/compare/__tests__/`: compare_list_kebab_actions, compare_hub_lifecycle_actions, compareDetailEditActions, bug_626_compare_menu_actions, bug_591_pausieren_button, issue_627_send_action, issue_493_compare_mobile, compare_mobile_shared_hub, issue_488_compare_tile_atoms
- `routes/compare/__tests__/`: compare_send_dialog_target, compare_hub_test_send_meldung (Hub sendet jetzt mit Rückfrage), compare_hub_loeschen_bestaetigung (testids bleiben), compare_list_mobile_chrome (Link-only wird abgelöst)
- `routes/trips/`: trips-list-send, issue_477_486 (AC-6c gelöscht), issue_402, `__tests__/tripPausiertFilter`
- Playwright: bug-626-compare-menu-actions, compare-mobile-vervollstaendigung, trips-list-send, issue-268-trips-mobile-card-stack, bug-282-295-trips-list-redesign, issue-616-trip-one-surface, send-in-flight-guard
- Je Test pro Beschriftung/testid bewusst entscheiden, nicht pauschal anpassen.

## Known Limitations

- Vom Ticket-Text abweichend, bewusst:
  1. AC-4 des Tickets betrifft nur den Trip-Hub (#2214 zu).
  2. Ticket-AC-5 ist als Verhaltens-AC (AC-6) umformuliert.
  3. Die Alt-Schwellen `change_threshold_*` und `alert_on_changes` sind nicht mehr bearbeitbar, bleiben aber in den Daten und im Core aktiv (AC-9).
  4. Compare-Hub-Senden fragt jetzt nach und sperrt bei fehlendem Kanal (Verhaltensänderung).
  5. **Ablösung** der früheren Entscheidung #1256 S8 AC-21 („Compare-Mobil-Liste nur Link", Archiv `docs/specs/_archive/modules/issue_1256_compare_ui_rewire.md`, Kommentar in `routes/compare/+page.svelte` :197-199) durch die Paritätsvorgabe des Epics #2345 (DoD-3). Kein ADR hängt daran.
  6. Das Compare-Menü wird um „Alarme" und „Wetter-Metriken" länger (Folge der einen Tabelle); die Trip-Liste bekommt „Pausieren".
- Zwei Backend-Pausierwege (Trip `PATCH /state`, Compare `PUT schedule`) bleiben bis P4/P7.

## Out of Scope

- Backend-Angleichung (ein Pausier-Endpunkt, Datenmodell-Konvergenz) — P4/P7
- kind-neutraler Handversand-Endpunkt (`/api/briefings` hat kein send/state)
- Änderung der Status-Ableitung für Cockpit/Archiv

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Frontend-Vereinheitlichung auf Basis vorhandener Bausteine; keine Entscheidungsfläche aus `docs/adr/` berührt.

## Changelog

- 2026-10-17: Initial spec created (#2278)
