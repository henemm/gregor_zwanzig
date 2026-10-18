# Adversary Dialog — feat-2278-aktionsmodell
Spec: docs/specs/modules/feat_2278_aktionsmodell.md
Datum: 2026-10-18 11:57

## Checkliste
- [x] **Input:** Nutzer öffnet Aktionen eines Trips oder Ortsvergleichs in Liste, Hub oder Mobil
- [x] **Output:** dieselben Handlungen an derselben Stelle, gleich beschriftet, mit gleichem Ergebnis; jede angezeigte Aktion wirkt
- [x] **Side effects:** Pausieren/Archivieren/Löschen/Senden wie bisher über die bestehenden Endpunkte
- [x] **AC-1:** Given ein aktiver Trip in der Desktop-Trip-Liste / When der Nutzer das Zeilenmenü öffnet / Then enthält es „Pausieren" an erster Stelle, in derselben Beschriftung und Reihenfolge wie beim Ortsvergleich, und die Wahl pausiert den Trip (Status „pausiert").
- [x] **AC-2:** Given die mobile Vergleichs-Liste / When der Nutzer das Menü einer Karte öffnet / Then sind Pausieren/Fortsetzen · Senden · Vorschau · Alarme · Wetter-Metriken · Bearbeiten · Löschen erreichbar (Entwurf: Setup fortsetzen · Löschen), und die Liste bietet Filter-Pillen Alle/Aktiv/Geplant/Pausiert/Fertig wie beim Trip.
- [x] **AC-3:** Given „Senden" aus Trip-Liste, Trip-Hub, Compare-Liste oder Compare-Hub (Desktop und Mobil) / When der Dialog erscheint / Then nennt er das echte Versandziel (E-Mail-Adresse bzw. Chat, auch Premium-SMS) aus `sendTargetLabel`, der Bestätigen-Knopf ist gesperrt, wenn kein Kanal liefern kann, und es wird erst nach Bestätigung gesendet.
- [x] **AC-4:** Given der Trip-Dialog „Senden" / When er geöffnet wird / Then bietet er die Wahl Morgen/Abend mit Vorauswahl Morgen, der Ortsvergleich-Dialog bietet keine solche Wahl, und der gesendete Bericht entspricht der gewählten Option.
- [x] **AC-5:** Given der Trip-Hub oder der Compare-Hub / When der Nutzer im Lebenszyklus-Menü „Löschen" wählt / Then erscheint derselbe Bestätigungsdialog mit dem Namen (Compare-Test-IDs `compare-detail-delete-confirm-*` bleiben), es geht erst nach Bestätigung ein DELETE raus, und danach landet der Nutzer in der jeweiligen Liste (schließt #1064).
- [x] **AC-6:** Given eine Tabelle mit beiden Arten (Trip, Ortsvergleich) × allen Status (Entwurf, aktiv, pausiert, archiviert) × allen Flächen (Liste, Hub, Mobil) / When `subscriptionActions` aufgerufen wird / Then entsprechen IDs, Beschriftungen und Reihenfolge je Zelle EINER Erwartungstabelle, und beide Arten liefern bei gleichem Status identische Ergebnisse.
- [x] **AC-7:** Given ein Nutzer pausiert bzw. setzt fort in Liste oder Hub / When die Aktion ausgeführt wird / Then werden bei Trip nur der Pausen-Zustand und bei Ortsvergleich der Zeitplan verändert, alle übrigen Felder des Objekts bleiben unverändert (Read-Modify-Write), und die Status-Anzeigen von Cockpit und Archiv-Seite zeigen weiterhin dasselbe wie vorher.
- [x] **AC-8:** Given die Trip-Liste und die Compare-Liste / When der Nutzer „Alarme" oder „Wetter-Metriken" wählt / Then öffnet sich bei beiden Arten der jeweilige Hub direkt auf dem Reiter (`/trips/{id}?tab=alarme` bzw. `/compare/{id}?tab=alarme`, `?tab=wetter-metriken`); die Aktion „Alert-Konfiguration" und der Dialog `ReportConfigDialog` existieren nicht mehr.
- [x] **AC-9:** Given ein Trip mit `send_premium_sms` und weiteren Feldern in `report_config`, darunter den Alt-Schwellen `change_threshold_temp_c/_wind_kmh/_precip_mm` und `alert_on_changes` / When der Nutzer über den Versand-Tab speichert / Then bleiben diese Felder, `send_premium_sms` und alle dem Editor unbekannten Felder unverändert erhalten, und kein Weg in der Oberfläche ersetzt `report_config` mehr komplett.
- [x] **AC-10:** Given zwei verschiedene angemeldete Nutzer A und B mit jeweils eigener Empfängeradresse und eigenem Chat / When B in Trip-Liste, Trip-Hub oder Compare-Hub „Senden" öffnet / Then zeigt der Dialog ausschließlich Ziele von B, nie `mail_to` oder Chat von A; ohne Session ist das Ziel „unbekannt" und der Versand gesperrt, nie ein Rückfall auf einen Default-Nutzer.
- [x] **AC-11:** Given ein Trip ist archiviert / When der Nutzer die Trip-Liste öffnet / Then erscheint er dort nicht (wie bei Ortsvergleichen), die Filter-Pille „Fertig" zeigt nur Trips mit vergangenem Datum, die nicht archiviert sind, der archivierte Trip bleibt auf der Archiv-Seite auffindbar, und das Cockpit zeigt unverändert dasselbe wie vorher.
- [x] **AC-12:** Given der Trip-Hub (Desktop und Mobil) / When der Nutzer das Lebenszyklus-Menü öffnet / Then enthält es Pausieren/Fortsetzen · Archivieren/Reaktivieren · Löschen anstelle der bisherigen Breadcrumb-Aktionsleiste, „Senden" ist der Primärknopf und öffnet den Sende-Dialog, und der Compare-Hub zeigt dieselbe Menü-Struktur.
- [x] **AC-13:** Given die Breadcrumbs „Trips" im Trip-Hub und im Trip-Anlegen-Editor / When der Nutzer darauf klickt / Then führt er zur Trip-Liste `/trips`.
- [x] **AC-14:** Given die mobile Trip-Liste und die mobile Vergleichs-Liste / When der Nutzer eine Karte öffnet / Then sieht er bei beiden Arten dieselbe Karte (`SubscriptionCard`) und dasselbe Aktionsblatt (`SubscriptionActionSheet`) mit denselben Filter-Pillen (`StatusFilterPills`); „Senden" im Blatt öffnet den Sende-Dialog und sendet nach Bestätigung wirklich (bisher öffnete mobiles Trip-„Briefing senden" nur die Vorschau).
- [x] **AC-15:** Given die Startseite mit Ortsvergleich-Kacheln / When sie angezeigt wird / Then verhält sie sich wie heute: Klick öffnet den Hub, das Kebab-Menü der Kachel bietet nur „Bearbeiten" (öffnet den Hub), und keine der neuen Listen-Aktionen erscheint dort ohne Wirkung. (Gemessen: die Kachel zeigt heute ein Kebab, behandelt aber nur `edit`; wirkungslose Einträge entfallen aus Konsistenz mit AC-16.)
- [x] **AC-16:** Given jede angezeigte Aktion in Liste, Hub und Mobil von Trip und Ortsvergleich (Desktop und Mobil-Viewport) / When der Nutzer sie auslöst / Then tritt die Handlung tatsächlich ein (Request bzw. Navigation bzw. Dialog); es gibt kein Aktions-Element ohne Wirkung.
- [x] **AC-17:** Given der tote Code der Trip-Liste (`primaryLabel`, `handlePrimaryAction`, `handleArchive`, unerreichbarer Archiv-Dialog) und die Trip-Inline-Karte/-Sheet / When der Umbau fertig ist / Then bleibt das Verhalten der Liste inklusive Zeilen-Primärknopf „Briefing senden" und Löschen mit Bestätigung erhalten und alle bestehenden Listen-Tests (angepasst auf neue Beschriftungen/IDs) sind grün.

## Dialog

### Runde 1
**Adversary:** Eigenstaendiger Neulauf, das Vorprotokoll (adversary-dialog-vor-buildfix.md) wurde nur als Hinweisquelle benutzt, nichts uebernommen.

**Beweis 1 - Build (Pflichtpunkt 1):** `cd frontend && npx vite build; echo EXIT=$?` -> `Using @sveltejs/adapter-node ... done`, **EXIT=0** (Ausgabe: Scratchpad build.txt). Ohne den Fix (Mutation M1/M2 unten) bricht genau dieser Build ab, der Compile-Test faengt es.

**Beweis 2 - Gesamtsuite:** `npm test -- --test-reporter=spec` (frontend, node --test): tests 5025, pass 5020, fail 0, skipped 5, duration 155 s. Voller Bericht: docs/artifacts/feat-2278-aktionsmodell/adversary-test-output.txt. svelte-check: 27 Fehler, ausschliesslich in Alt-Dateien/Alt-Tests (forecast_hours, WeatherConfigDialog u.a.), keiner in einer #2278-Datei (Basislinie vorher 29-30).

**Code-Belege (Abdeckung, jede Pflichtdatei zitiert):**
Code reference: frontend/src/lib/components/shared/subscriptionActions.ts:53 - `subscriptionActions(_kind, status, surface)`; `_kind` wird nie gelesen, also identische Tabelle fuer beide Arten (AC-6); Zeilen 60-72: draft = continue-setup/delete, archived = unarchive/delete, paused/active = Liste/Mobil pause|resume, send, preview, alarms, weather, edit, delete, Hub = pause|resume, archive, delete (AC-1, AC-2, AC-12); keine ID `alert-config` (AC-8). Zeile 80-92 `subscriptionLifecycle` als Wrapper.
Code reference: frontend/src/lib/components/shared/subscriptionExec.ts:153 - `setPaused`: Trip nur `PATCH /state {paused}` (Zeile 159); Compare frischer GET (162), PUT nur `statusZielNutzlast` = {schedule, previous_schedule} (163-164) = Read-Modify-Write (AC-7). Zeile 186-195 `sendSubscription`: `opts.reportType ?? 'morning'` nur beim Trip (AC-4). Zeile 177-183 `deleteSubscription` mit `pruefe` (Fehler werden nicht verschluckt).
Code reference: frontend/src/lib/server/profileLoader.ts:203 - ohne `gz_session` sofort `null` (206), Fehler -> `null` (213); nie user_id, nie Default (AC-10).
Code reference: frontend/src/lib/components/shared/versand-tab/sendTargetLabel.ts:66 - Profil null/undefined -> "Versandziel unbekannt", gesperrt; einziger Aufrufer ist sendConfirmModel.ts:29 (grep), das alte `profile ?? {}`-Verhalten betrifft keinen anderen Nutzer (AC-3, AC-10).
Code reference: frontend/src/lib/components/molecules/sendConfirmModel.ts:23 - Ziel + Sperre aus `sendTargetLabel` (29), Morgen/Abend-Wahl nur bei `kind==='trip'` (34), Default `auswahl ?? 'morning'` (35) (AC-3, AC-4).
Code reference: frontend/src/lib/components/molecules/index.ts:27 - CompareTile/CompareKebab/ReportConfigDialog/TestReportDialog nicht mehr exportiert, nur CompareStatusPill/CompareLocationRow/CompareIdealRow (AC-8, AC-17).
Code reference: frontend/src/lib/components/mobile/index.ts:29 - der Export `MCompareActionSheet` ist entfernt, `SubscriptionActionSheet` wird direkt importiert, kein Alt-Export mehr (AC-14).
Code reference: frontend/src/lib/components/compare/subscriptionHelpers.ts:145 - `compareFilterStatus`: draft -> null (nur unter "Alle"), `end_date` vor heute -> 'fertig', Leerstring/fehlend = kein Enddatum (AC-2 Pillen).
Code reference: frontend/src/routes/_home/kachelActions.ts:4 - Kachel-Aktionen = genau `[edit]`; CompareKachel.svelte:17 benutzt es, +page.svelte:806 uebergibt jetzt `sub={preset}` (AC-15; vorher falsch benannte Prop `<CompareKachel {preset} />`).
Code reference: frontend/src/routes/trips/+page.server.ts:15 und :20 - Profil per `loadProfile(cookies)`, archivierte Trips serverseitig ausgefiltert (AC-10, AC-11); Client-Refetch trips/+page.svelte:30 filtert ebenfalls `archived_at == null`.
Code reference: frontend/src/routes/trips/[id]/+page.server.ts:24 - `loadProfile(cookies)` im Promise.all, `profile` im Rueckgabeobjekt (AC-10).
Code reference: frontend/src/routes/compare/[id]/+page.server.ts:18 - `loadProfile(cookies)`, `profile` im Return (AC-10).
Code reference: frontend/src/routes/trips/+page.svelte:147 - `confirmSend(berichtsart: 'morning' | 'evening' | undefined)` (der Build-Fix); :154 reicht `{ reportType: berichtsart }` weiter; Dispatch `onTripAction` (Zeilen 104-114): pause/resume -> togglePause, send -> sendTarget (Dialog), alarms/weather -> `?tab=alarme|wetter-metriken`, delete -> deleteTarget (Dialog) (AC-1, AC-3, AC-8, AC-14, AC-16, AC-17).
Code reference: frontend/src/routes/trips/[id]/+page.svelte:265 - `handleSendConfirm(berichtsart: ... | undefined)` (Build-Fix); :272 `sendSubscription('trip', trip.id, { reportType: berichtsart })`; :242-243 `deleteSubscription` dann `goto('/trips')`; :289-292 Hub-Kebab-Dispatch pause/resume/archive/unarchive/delete; :390-397 SendConfirmDialog mit `profile={data.profile}` (AC-3, AC-4, AC-5, AC-12).
Code reference: frontend/src/routes/__tests__/seiten_kompilieren_zu_gueltigem_js.test.ts:25-63 - neuer Test: 13 .svelte-Dateien x client+server -> Svelte-Preprocess -> compile -> acorn.parse (26 Tests, alle gruen). Die Dateiliste wurde gegen die Menge der neuen/geaenderten .svelte-Dateien seit der Merge-Base geprueft: alle 12 sowie das umbenannte SubscriptionKebab sind enthalten.
- Weitere gelesene Stellen: SendConfirmDialog.svelte:31 (`gesperrt = $derived(modell.gesperrt || running)`), :39 (`disabled={gesperrt}`), :43 (`onConfirm(modell.berichtsart)`); SubscriptionActionSheet.svelte (Klick -> `onAction(action.id); onClose()`); StatusFilterPills.svelte (fuenf Pillen); compare/+page.svelte:117-128 (Dispatch), :154 (Senden erst nach Bestaetigung), :164 (Loeschen); compare/[id]/+page.svelte:324 (Loeschen -> /compare), :455 (Dialog-Bestaetigung ruft handleTestSend).

**Confirmations:**
- Confirmation AC-1: Code reference: frontend/src/lib/components/shared/subscriptionActions.ts:69-71 - aktiv: 'pause' an erster Stelle; Dispatch trips/+page.svelte:106 -> setPaused('trip', id, true) = PATCH {paused:true}. Tests: subscriptionActions.test.ts, trip_list_pause.test.ts. Status: CONFIRMED
- Confirmation AC-2: Code reference: frontend/src/lib/components/shared/subscriptionActions.ts:69 + StatusFilterPills.svelte (5 Pillen) + compare/+page.svelte:117. Mutationen N6/N7 gefangen. Status: CONFIRMED
- Confirmation AC-3: Code reference: frontend/src/lib/components/molecules/sendConfirmModel.ts:29. Ziel und Sperre im Modell bewacht (M8, N16, N2, N3, N4, N5 gefangen). Einschraenkung siehe F001 (Verdrahtung Modell -> Knopf nicht bewacht). Status: CONFIRMED (Verhalten korrekt, Wachtest-Luecke als F001)
- Confirmation AC-4: Code reference: frontend/src/lib/components/molecules/sendConfirmModel.ts:34-35 + subscriptionExec.ts:192. Mutationen M3, M3b, M4, M6c, N10, N11, N12 gefangen. Status: CONFIRMED
- Confirmation AC-5: Code reference: frontend/src/routes/trips/[id]/+page.svelte:242-243 und compare/[id]/+page.svelte:324. M14, N1, N14 gefangen. Status: CONFIRMED
- Confirmation AC-6: Code reference: frontend/src/lib/components/shared/subscriptionActions.ts:53-73. M5, M5b, N13, M19 gefangen. Status: CONFIRMED
- Confirmation AC-7: Code reference: frontend/src/lib/components/shared/subscriptionExec.ts:159-164. M6, M6b gefangen (7 bzw. 13 rote Tests). Status: CONFIRMED
- Confirmation AC-8: Code reference: frontend/src/routes/trips/+page.svelte:109-110 und compare/+page.svelte:124-125. M17, N6 gefangen. Status: CONFIRMED
- Confirmation AC-9: Code reference: frontend/src/lib/components/shared/versand-tab/mergeReportConfig.ts (Roundtrip) + Go-Merge. versand_speichern_erhaelt_report_config.test.ts gruen. Status: CONFIRMED (siehe Nebenpunkt 1)
- Confirmation AC-10: Code reference: frontend/src/lib/server/profileLoader.ts:206. M7, M7b, M8, M10-M12, N17-N20 gefangen. Status: CONFIRMED
- Confirmation AC-11: Code reference: frontend/src/routes/trips/+page.server.ts:20. M9, M20 gefangen. Status: CONFIRMED
- Confirmation AC-12: Code reference: frontend/src/routes/trips/[id]/+page.svelte:289-292, :312. N16 gefangen. Status: CONFIRMED
- Confirmation AC-13: Code reference: frontend/src/routes/trips/[id]/+page.svelte:302 (`<a href="/trips">`) und frontend/src/lib/components/trip-new/TripNewEditor.svelte:528 (`back={{ href: '/trips' ...}}`); trips_breadcrumb_link.test.ts gruen. Status: CONFIRMED
- Confirmation AC-14: Code reference: frontend/src/routes/trips/+page.svelte:107 (send -> Dialog statt Vorschau). N4, N8 gefangen. Status: CONFIRMED
- Confirmation AC-15: Code reference: frontend/src/routes/_home/kachelActions.ts:4. M13, P4 gefangen. Status: CONFIRMED
- Confirmation AC-16: Code reference: frontend/src/routes/trips/+page.svelte:104-114, compare/+page.svelte:117-128 (jede ID hat einen Zweig; Hub: trips/[id]/+page.svelte:289-292, compare/[id]/+page.svelte:268-280). M16, N4, N5, N15, N8 gefangen. Status: CONFIRMED
- Confirmation AC-17: Code reference: frontend/src/routes/trips/+page.svelte:147-157 (Senden mit Bestaetigung), :134-146 (Loeschen); toter Code (primaryLabel, handleArchive) nicht mehr in trips/+page.svelte. Gesamtsuite 0 fail. Status: CONFIRMED
- Confirmation Input/Output/Side effects: gleiche Quelle subscriptionActions.ts:53, gleiche Endpunkte subscriptionExec.ts:144/164/182. Status: CONFIRMED

### Runde 2
**Adversary:** Mutations-Gegenprobe (Step 3b), ausschliesslich per String-Ersetzung, Sicherungskopie je Datei im Scratchpad, danach Rueckkopie und Byte-Vergleich (jede Zeile `restored identical: True`); nach der letzten Mutation zeigt die Diff-Statistik nur die beiden Build-Fix-Zeilen, kein Mutationsrest. Zielsuite je Mutation = 370 Testdateien (routes, lib/server, lib/components/{shared,molecules,organisms,mobile,compare}, lib/__tests__); Ueberlebende zusaetzlich gegen alle Testdateien (Gesamtsuite) wiederholt. Ergebnis: **49 Mutationen, 47 gefangen, 2 ueberleben (P2/N9, P3)**. Es zaehlt WELCHER Test rot wurde - jeweils der Test, der die Zusicherung benennt.

Pflichtmutationen aus dem Auftrag:
- (a) Fix rueckgaengig (`berichtsart?:`): M1 trips/+page.svelte -> rot: `trips/+page.svelte (client|server) kompiliert zu parsebarem JS`; M2 trips/[id]/+page.svelte -> rot: dieselben zwei Tests fuer [id]. GEFANGEN (seiten_kompilieren_zu_gueltigem_js.test.ts).
- (b) report_type-Durchreichung (AC-4): M3 Hub `{ reportType: berichtsart }` -> `{}` -> rot: "Trip-Liste und Trip-Hub: erster Parameter der Bestaetigung geht als reportType in sendSubscription", "F003 (AC-4): die gewaehlte Berichtsart erreicht den Request". M3b dasselbe in der Liste -> 4 rot (u.a. "F016 Trip-Liste"). M4 Dialog ruft `onConfirm()` -> rot "F003/F010: Radiowahl -> onConfirm -> Request". M6c Adapter ignoriert reportType -> rot "sendSubscription Trip: report_type im Request (AC-4), Default morning". GEFANGEN; Einschraenkung: der Hub-Pfad wird per AST-/Quelltextpruefung (aktionsmodellAst.ts) bewacht, nicht durch Mounten.
- (c) Kernlogik: M5/M5b/N13/M19 (subscriptionActions.ts: Reihenfolge, Hub ohne archive, Trip pausiert -> aktiv, archived ignoriert) -> rot in subscriptionActions.test.ts bzw. "Trip: paused_at = paused, archived_at gewinnt"; M6 (Trip pause invertiert) -> 7 rot; M6b (Compare-RMW ohne frischen Stand) -> 13 rot (u.a. "Datenerhalt: Korridore und unbekannte Felder ueberleben", "GET-Fehler: kein PUT"); M7 (profileLoader Default-Fallback ohne Session) -> 6 rot ("ohne Session: profile = null, nie ein Rueckfall..."); M7b (Loader wirft statt fail-soft) -> 6 rot; M8 (sendTargetLabel null-Guard weg) -> 4 rot. M10/M11/M12 (Profil im Server-Load auf null) -> "zwei Sessions: jeder Nutzer bekommt genau SEIN Profil". M9 Archivfilter weg -> "AC-11 ..." 3 rot. M20 compareFilterStatus 'fertig' weg -> rot. M13 Kachel +delete -> "compareKachelActions() liefert genau [edit]". M14/M15/N1/N14 (Loeschen: Navigation, Fehler verschluckt) rot. M16/M17/N4/N5/N6/N15 (Dispatch falsch/ohne Dialog) rot. N2/N3/N16 (Senden ohne Dialog bzw. Bestaetigung wirkungslos) rot "F001: Senden oeffnet nur den Dialog". N7 Pille vertauscht, N8 Blatt ohne onAction, N10 Reset auf Morgen, N11 Compare bekommt Wahl, N12 Default Abend rot. N17-N20 (Seite gibt dem Dialog kein Profil) rot "F002 (AC-10)". P1 (disabled nicht an ConfirmDialog) rot. P4 (Home `{preset}` statt `sub=`) rot "F012/AC-15".

UEBERLEBEN (kein Test wird rot, auch nicht in der Gesamtsuite):
- N9/P2: SendConfirmDialog.svelte:31 `const gesperrt = $derived(modell.gesperrt || running)` -> `$derived(false)`. Der Bestaetigen-Knopf waere nie gesperrt, obwohl kein Kanal liefern kann (AC-3). Grund: send_confirm_dialog.test.ts:159-166 prueft nur per AST, dass das `disabled`-Attribut den NAMEN `gesperrt` traegt, nicht woraus `gesperrt` abgeleitet wird; `modell.gesperrt` selbst ist nur im Modelltest (Zeilen 70-101) bewacht; kein Playwright-Spec (`send-confirm-yes` in 4 Specs) prueft `disabled`. -> F001.
- P3: Entfernen von `|| running` (gleiche Zeile) -> ueberlebt. Der Doppelklick-Schutz im Dialog ist ungeprueft; der Request selbst ist durch den In-Flight-Schutz in sendOutcome (#2124) gedeckt. -> F002 (LOW).

Weitere Pruefpunkte:
- Leitfrage "an der Stelle geprueft, an der es WIRKT": Bei Senden/Loeschen/Pausieren wurde je an der Nutzerstelle mutiert (Seiten-Dispatch, Hub-Primaerknopf, Dialog-Bestaetigung, Server-Load, Home-Seite), nicht nur im Modell. Nur die Sperre (F001) zeigt die typische Luecke "Modell geprueft, Verdrahtung nicht".
- Pruefen die Tests, was sie behaupten? Stichprobe: der Test "bindet disabled an gesperrt des Modells" prueft nur den Namen (F001). Sonst keine Vakuum-Tests gefunden: alle gefangenen Mutationen fielen im jeweils benannten Test, keine Zufallstreffer.
- Nebenpunkt 1 (WeatherMetricsTab.svelte:958, AC-9): `buildTripReportBody` sendet `report_config: reportConfig` (lokale Kopie), gefiltert durch `pickEigenfelder(..., WETTER_REPORT_KEYS)` (pickEigenfelder.ts:64) - also nur eine Teilmenge der Schluessel, kein Voll-Ersatz. Der Go-Handler merged ein Teil-`report_config` (internal/handler/fix_go_rmw_merge_1082_1103_test.go:75-131: `send_premium_sms` bleibt erhalten). Vorbestehend, kein Voll-Ersatz -> kein Finding; Restrisiko nur ein veralteter Wert der EIGENEN Schluessel (bestehende Race-Klasse, ausserhalb dieser Spec).
- Nebenpunkt 2 (AST-/Quelltextpruefungen): ein Teil der Seiten-Verdrahtungsnachweise ist AST-Pruefung (aktionsmodellAst.ts, aktionsmodell_seiten_bindung.test.ts). Sie fingen alle 49 Mutationen ausser F001/F002; Grenze: strukturell, nicht gerendert (Live-Schicht Playwright nicht lauffaehig in dieser Pruefung). F001 ist das Beispiel dieser Grenze.
- Nebenpunkt 3 (Compile-Test mit fester Dateiliste): heute vollstaendig, aber eine kuenftig neue .svelte-Datei wird nicht automatisch erfasst -> F003 (LOW, Sammelpunkt #1199).
- svelte-check: 27 Fehler nur in Alt-Dateien; der `CompareKachel {preset}`-Typfehler aus der Vorrunde ist behoben (+page.svelte:806).
- Regression: Aufrufer von `sendTargetLabel` = nur sendConfirmModel (grep); `confirmSend`/`handleSendConfirm` mit Pflichtparameter haben als einzigen Aufrufer SendConfirmDialog (Zeile 43), der immer mit Argument ruft.
**Implementierer:** (nicht anwesend, Isolation). Erwartete Rueckmeldung auf F001: ein Test, der `gesperrt` mit `modell.gesperrt || running` bindet (SSR-Render des Dialogs mit leerem Profil und `disabled`-Attribut, oder AST-Pruefung der Ableitung) plus Gegenbeispiel `running=true`.

### Runde 3
**Adversary:** Nachpruefung der Fix-Loop (nur Tests geaendert, Produktcode unveraendert). Selbst bestaetigt: `npx vite build` **EXIT=0**; Gesamtsuite `npm test` (Spec-Reporter, voller Bericht in adversary-test-output.txt): tests 5550, pass 5545, fail 0, skipped 5. `npx playwright test --list e2e/aktionsmodell-durchklick.spec.ts` parst (24 Tests in 2 Dateien, der neue Test "AC-3: Sende-Dialog sperrt Bestaetigen ..." bei Zeile 314); er wurde NICHT ausgefuehrt (laeuft in /e2e-verify).

Neue/geaenderte Tests, gelesen:
Code reference: frontend/src/lib/components/molecules/__tests__/send_confirm_dialog_sperre.test.ts:42-52 - wertet das ECHTE Instanz-Skript von SendConfirmDialog.svelte (Pruefstand umgebungFuer, echtes sendConfirmModel) aus und berechnet den Ausdruck, den die Komponente WIRKLICH als `disabled` an `<ConfirmDialog>` uebergibt (Zeile 47-51), also die Sperr-Herleitung selbst, nicht den Namen. Zeilen 55-70: je Art gueltig -> frei; ohne Adresse / unbestaetigt / Profil null -> gesperrt; Zeilen 73-85: running=true -> gesperrt, Default frei. Gegenprobe `typeof u.sendConfirmModel === 'function'` verhindert eine leere Messung.
Code reference: frontend/src/routes/__tests__/seiten_kompilieren_zu_gueltigem_js.test.ts:27-36 - Dateiliste jetzt per `readdirSync(src, {recursive})` ueber alle .svelte, Schutz `> 100` Dateien und Enthaltensein von SendConfirmDialog.svelte; ausgefuehrt client+server je Datei.
Code reference: frontend/e2e/aktionsmodell-durchklick.spec.ts:308-314 - Live-Test: Zweitnutzer ohne mail_to, Hub -> Senden, `send-confirm-yes` disabled, erzwungener Klick sendet nichts (nur --list geprueft).

Mutations-Nachfahrt (String-Ersetzung, Sicherungskopie, Rueckkopie, Byte-Vergleich `restored identical: True` je Lauf; Zielmenge = alle 511 Testdateien unter frontend ausser e2e):
- Q1 (= F001) `gesperrt = $derived(false)` -> 10 rot, u.a. "trip|vergleich: Profil ohne Adresse -> Knopf gesperrt", "... kein Profil (null) -> Knopf gesperrt". GEFANGEN, im richtigen Test.
- Q2 (= F002) ohne `|| running` -> 3 rot: "trip|vergleich: gueltiges Ziel + running=true -> gesperrt", "AC-3 (F002) ...". GEFANGEN.
- Q3 `disabled={false}` am ConfirmDialog -> 12 rot (Strukturtest + Sperr-Test). GEFANGEN.
- Q6 `!modell.gesperrt || running` (invertiert) -> 12 rot. GEFANGEN.
- Q5 (= F003) `function zzMutation(x?: number)` in LocationForm.svelte (nicht in der frueheren 13er-Liste) -> rot: "LocationForm.svelte (client|server) kompiliert zu parsebarem JS". GEFANGEN; der Glob wirkt.
- Q4 (neu) ConfirmDialog.svelte:65 `{disabled}` am Bestaetigen-Knopf entfernt (Weiterreichung ConfirmDialog -> Knopf `send-confirm-yes`) -> **UEBERLEBT** (0 rot, alle 511 Testdateien). Bewertung: Genau diese letzte Strecke ist laut Test-Header nur per Live-Test bewacht; in der Kernschicht gibt es keinen Test, der das Dialog-Markup mountet (bits-ui Dialog liefert unter SSR keinen Inhalt, gemessen). Das ist die Zwei-Schichten-Politik des Projekts, kein Versaeumnis der Fix-Loop; der Live-Test existiert und parst. Als F004 (LOW) gefuehrt, bis /e2e-verify ihn ausgefuehrt gruen zeigt.

Antwort auf die Leitfrage: Die Zusicherung "gesperrt" ist jetzt an der Herleitung (Modell -> Komponente) geprueft, die den Knopf steuert; offen bleibt nur die generische Weiterreichung im geteilten ConfirmDialog (F004).
**Implementierer:** (nicht anwesend) Findings-Status: F001 behoben (Q1/Q3/Q6 gefangen), F002 behoben (Q2 gefangen), F003 behoben (Q5 gefangen), F004 neu, LOW, offen bis E2E-Lauf.

### Runde 4
**Adversary:** Nachpruefung des CI-Fix (CSS-Regel Trip-Hub-Kopf, Fixture `testMitZustellbaremZiel`, Loeschung der Dateiinhalt-Testklasse). Selbst gemessen: `cd frontend && npm test` -> tests 5550, pass 5545, fail 0, skipped 5 (voller Bericht adversary-test-output.txt); `uv run pytest tests/tdd/test_bug_716_test_briefing_silent_fail.py -v -rA` -> 2 passed, 2 deselected (die zwei Deselected sind live/email-markiert). Der lokale E2E-Stack lief nicht (Port 5173 nicht erreichbar): **kein Playwright-Test ausgefuehrt, AC-13-Messwert 455,5 px NICHT selbst gemessen**, nur statisch begruendet.

Code reference: frontend/src/routes/trips/[id]/+page.svelte:429-436 - Regel nur in `@media (max-width: 899px)`: Desktop unveraendert (`.breadcrumb-bar` Zeile 411-419 und `.hub-actions` bleiben). `flex: 1 1 0` + `min-width: 0` + nowrap/overflow/ellipsis: der Pfad schrumpft, `.hub-actions` behaelt seine Breite, `flex-wrap: wrap` greift nicht mehr (Basis 0). Tippflaechen: die 44-px-Regel fuer `.hub-actions > [data-slot=btn]` darunter bleibt unberuehrt; Kebab hat festes 44x44 (Zeile 322-326). Kein Querscroll durch die Regel (sie verengt nur). Angezeigt wird `trip.shortcode ?? trip.name` (Zeile 304); der volle Name steht weiterhin in der Hub-Kopfzeile (`name={trip.name}`, Zeile 406) und im Seitentitel (Zeile 296), also bleibt er erreichbar; ein `title`-Attribut am Pfad fehlt (kein AC verlangt es; AC-13 dieser Spec ist der Breadcrumb-Link `/trips`, der Link bleibt sichtbar, weil nur der Namensteil gekuerzt wird). Die Mobil-Messung gehoert zur Spec #2284 S2 (trip-hub-kopf-region-aktivitaet.spec.ts, AC-13, Grenze 474 px).
Code reference: frontend/e2e/helpers.ts:251-307 - Fixture: eigener Zweitnutzer mit echter, frischer Kennung (`e2ezustellbar<ts>w<worker>`), kein "default"; Konto-Sitzung nur als In-Memory-`storageState` (kein Token nach /tmp); Admin-Kontext wird im `finally` geschlossen; Vorbedingung `mail_to` per `expect`; Seed-Trip gehoert dem Zweitnutzer (Admin-Daten unberuehrt); Loeschung des Kontos am Ende mit `account/delete`. Zwei verschiedene Nutzer sind damit Teil des Aufbaus (Admin legt Token an, Gast agiert). Schwaeche: siehe F005.
Code reference: frontend/e2e/send-in-flight-guard.spec.ts:33-37 - Import `testMitZustellbaremZiel as test`; Zeile 219-245 der Compare-Fall nutzt `page` als zustellbaren Nutzer, Aufraeumen von Preset/Orten im `finally` (`cleanup(page, ...)`); der bisherige Inline-Zweitnutzer entfaellt ersatzlos, Wirkung unveraendert (Sperre greift nicht, Versand wird per `page.route` gehalten).
Code reference: frontend/e2e/issue-767-768-test-briefing.spec.ts:15-18 - gleiche Umstellung, Seed-Trip-ID `e2e-cockpit-test` bleibt, daher laufen die Specs unveraendert; `login(page)` kehrt bei vorhandener Sitzung sofort zurueck (helpers.ts:180-190), meldet also NICHT als Admin neu an.
Code reference: tests/tdd/test_bug_716_test_briefing_silent_fail.py:19-22 - geloescht wurden nur die zwei `# doc-compliance-test`-Quelltext-Tests (AC-4). Ersatz-Waechter gelesen: frontend/src/lib/utils/sendOutcome.test.ts:81-92 ("AC-2: 422 ... zeigt die Backend-detail-Meldung", "500 ... generisch ohne Rohtext") - das ist ein Verhaltensnachweis auf der Logik, die frueher im Svelte-Text stand, und er ist stricter als die gestrichene Textsuche; die UI-Strecke (test-briefing-error im Browser) steckt in issue-767-768-test-briefing.spec.ts. Keine Zusicherung geht verloren.

Mutations-Gegenprobe (String-/Zeilen-Ersetzung, Sicherung im Scratchpad `page.bak`, Rueckkopie, `cmp` -> IDENTICAL):
- M1 komplette Regel `.breadcrumb-path { ... }` aus `@media (max-width: 899px)` entfernt (+page.svelte:429-435): Kernschicht `npm test` -> **0 rot** (5550 / 5545 pass / 0 fail). UEBERLEBT in der Kernschicht; `grep breadcrumb-path` findet die Klasse in keiner Testdatei. Faengt nur der Live-Test trip-hub-kopf-region-aktivitaet.spec.ts (AC-13, Etappen-Liste <= 474 px, 375x667 langer Name und 390x844) - NICHT ausgefuehrt (kein E2E-Stack), daher "nicht gemessen". Statisch: ohne die Regel bricht `flex-wrap: wrap` den Kopf um (+33 px, das war der CI-Befund 488 px), der Test wuerde also rot. -> F005.
- Gegenfrage Fixture: ein Entfernen der Konto-Loeschung oder des `mail_to`-Expects ist in der Kernschicht nicht messbar (reiner Live-Aufbau); ehrlich nicht gemessen. -> F006.

### Findings
Finding:
  ID: F001
  Severity: MEDIUM
  Category: edge_case
  Code reference: frontend/src/lib/components/molecules/SendConfirmDialog.svelte:31
  Description: `const gesperrt = $derived(modell.gesperrt || running)` ist die einzige Stelle, die die Sperre aus dem Modell an den Bestaetigen-Knopf bindet. Die Mutation `$derived(false)` laesst die gesamte Suite gruen. send_confirm_dialog.test.ts:159-166 prueft nur den Attributnamen `gesperrt`.
  Spec requirement: AC-3 - der Bestaetigen-Knopf ist gesperrt, wenn kein Kanal liefern kann
  Conflict: Das Produktverhalten ist heute korrekt, aber die Zusicherung ist nur am Modell (sendConfirmModel.ts:29), nicht dort bewacht, wo sie den Nutzer erreicht; eine Regression bliebe unbemerkt (auch kein Playwright prueft `disabled`).
  Remediation: Test fuer die Ableitung (AST-Ausdruck `modell.gesperrt || running` am `gesperrt`-Deklarator) oder SSR-Render des Dialogs mit Profil ohne Adresse und `disabled`-Attribut am Senden-Knopf; zusaetzlich e2e-Assertion, dass `send-confirm-yes` disabled ist.
  Status Runde 3: BEHOBEN (Q1, Q3, Q6 gefangen; send_confirm_dialog_sperre.test.ts, E2E-Test vorhanden).

Finding:
  ID: F002
  Severity: LOW
  Category: edge_case
  Code reference: frontend/src/lib/components/molecules/SendConfirmDialog.svelte:31
  Description: Das Entfernen von `|| running` laesst alle Tests gruen; der Dialog-eigene Doppelklick-Schutz ist ungeprueft.
  Spec requirement: AC-3 (sendet erst nach Bestaetigung, genau einmal) / #2124 In-Flight-Schutz
  Conflict: Der Request-Schutz in sendOutcome bleibt aktiv, daher nur LOW.
  Remediation: im selben Test wie F001 mit `running=true` abdecken.
  Status Runde 3: BEHOBEN (Q2 gefangen).

Finding:
  ID: F003
  Severity: LOW
  Category: anti_pattern
  Code reference: frontend/src/routes/__tests__/seiten_kompilieren_zu_gueltigem_js.test.ts:25
  Description: feste Dateiliste von 13 .svelte-Dateien; neue Svelte-Dateien mit derselben `x?: T`-Falle wuerden nur vom Build, nicht vom Test erfasst.
  Spec requirement: AC-17 (alle Tests gruen) / der Build muss laufen
  Conflict: heute vollstaendig, aber nicht selbstpflegend.
  Remediation: Liste per Glob ueber src/**/*.svelte (mindestens routes/ und lib/components/{molecules,organisms,mobile}) erzeugen; Sammelpunkt #1199.
  Status Runde 3: BEHOBEN (Glob ueber alle .svelte, Q5 gefangen).

Finding:
  ID: F004
  Severity: LOW
  Category: edge_case
  Code reference: frontend/src/lib/components/molecules/ConfirmDialog.svelte:65
  Description: Die Weiterreichung `{disabled}` an den Bestaetigen-Knopf (und damit an `send-confirm-yes`) ist in der Kernschicht ungeprueft; Entfernen laesst alle 511 Testdateien gruen.
  Spec requirement: AC-3 - Bestaetigen-Knopf ist gesperrt
  Conflict: Nur der Live-Test (aktionsmodell-durchklick.spec.ts:314) bewacht die letzte Strecke; er wurde nur per --list geprueft.
  Remediation: /e2e-verify muss den Test gruen ausfuehren; optional ein Rendertest von ConfirmDialog mit echtem DOM.

Finding:
  ID: F005
  Severity: LOW
  Category: edge_case
  Code reference: frontend/src/routes/trips/[id]/+page.svelte:429
  Description: Die neue Mobil-Regel `.breadcrumb-path` wird von keinem Test der Kernschicht bewacht; Entfernen laesst alle 5550 Tests gruen (gemessen).
  Spec requirement: AC-13 (#2284 S2, Spec v1.3) - Etappen-Liste beginnt bei 390 px hoechstens bei 474 px
  Conflict: Nur der Live-Test trip-hub-kopf-region-aktivitaet.spec.ts bewacht die Wirkung; er lief in dieser Runde nicht. Zwei-Schichten-Politik, kein Versaeumnis, aber /e2e-verify bzw. die CI-e2e muss ihn gruen zeigen.
  Remediation: e2e-Lauf von trip-hub-kopf-region-aktivitaet.spec.ts (AC-13, alle drei Faelle) abwarten; optional title-Attribut am Namens-Span.

Finding:
  ID: F006
  Severity: LOW
  Category: anti_pattern
  Code reference: frontend/e2e/helpers.ts:274
  Description: Schlaegt in der Worker-Fixture etwas NACH der Registrierung fehl (`expect(profil.mail_to)` Zeile 281 oder Seed-Trip Zeile 301), laeuft das Aufraeumen (Konto-Loeschung Zeile 303, Kontext schliessen) nicht, weil nur der Admin-Teil in `try/finally` steht; es bleibt ein Testkonto auf Staging/CI zurueck. Ausserdem: ein Konto je Worker belastet die Registrierungsbremse (5/h je IP).
  Spec requirement: AC-3 / AC-10 - Sende-Specs laufen mit zustellbarem Ziel, ohne Bestandsdaten zu verschmutzen
  Conflict: Nur Aufraeum-Hygiene im Fehlerfall; CI-Stack wird pro Lauf neu aufgesetzt, Staging hat Karteileichen-Reinigung.
  Remediation: gesamten Aufbau nach der Registrierung in `try/finally` mit Loeschung im finally; Sammelpunkt #1199.

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Verdict
**VERIFIED**

Begruendung (Runde 4): Gesamtsuite 5550 tests / 5545 pass / 0 fail / 5 skipped, Python-Datei 2 passed. CSS-Regel nur mobil, Desktop unveraendert, Tippflaechen/Querscroll nicht beruehrt, voller Name bleibt erreichbar. Fixture isoliert (echter Zweitnutzer, kein "default", In-Memory-Sitzung, Loeschung am Ende). Geloeschte Python-Tests hatten Ersatz-Waechter (sendOutcome.test.ts) und verlieren keine Zusicherung. Mutation M1 (CSS-Regel entfernt) ueberlebt die Kernschicht und wird nur vom nicht ausgefuehrten Live-Test AC-13 gefangen (F005, LOW); F006 LOW (Aufraeumen im Fehlerfall). Offen bleiben F004-F006, alle LOW. Playwright wurde in dieser Runde nicht ausgefuehrt.

AC-Uebersicht: AC-1 bis AC-17 belegt (Runde 4 beruehrt AC-3, AC-10, AC-13, AC-17).

## Geprüfte Dateien

- sha256:ed7389d34b5a2e8e96ca898ce9eb5f36c68ea296b6b5111b948048e322d29c38  frontend/e2e/aktionsmodell-durchklick.spec.ts
- sha256:8b28ef8410958b4ae3b689f1b22fc1c9c713f10d4707329a9f2805dd41e0d125  frontend/e2e/helpers.ts
- sha256:298419a75a8a6322de9a3f57701c290cd67d1b3866db05424d2ee326a7d4d6d7  frontend/e2e/issue-767-768-test-briefing.spec.ts
- sha256:64ef96c0b8842f6ae1295e2d1f27f5122a084219f3f5518be96b55e8f98c0899  frontend/e2e/send-in-flight-guard.spec.ts
- sha256:469e51bbd22340a74e368a6bf0f88f34b54b3cc7c8dd6fcd4d5412923b6a7196  frontend/src/lib/components/compare/subscriptionHelpers.ts
- sha256:43f657004843439e0b9a2b504d08e4818c9d3f2958d0083516dab2c6f6bdbea3  frontend/src/lib/components/mobile/index.ts
- sha256:c73e69663a628b4c5540319f05079c45b7ceabecb02884224fc0bce10b754ffd  frontend/src/lib/components/molecules/ConfirmDialog.svelte
- sha256:84c370050591737401938eecea06137314293987b1165df7a759f9d3acfded54  frontend/src/lib/components/molecules/SendConfirmDialog.svelte
- sha256:e884bed1c80b17311968d653cf5ec247977c73cd9aa4668794976da101a30f6b  frontend/src/lib/components/molecules/__tests__/send_confirm_dialog_sperre.test.ts
- sha256:a208da2cb7f724de191a89c6b9c06de7e659dcdfa385a882b32eef10d4870a47  frontend/src/lib/components/molecules/index.ts
- sha256:dba1374d2916f45183842c1e89be8bce6bc53a163e0b59c14c0e0f876486ebcf  frontend/src/lib/components/molecules/sendConfirmModel.ts
- sha256:691065bafb0bd13257823164a4bff7bf48f3e896ce82d116bb1b0da4a2dbb613  frontend/src/lib/components/shared/subscriptionActions.ts
- sha256:41d2da8877e2e5695571488422addb33d3087eefa0ad7e4a478c71e58db3b5c0  frontend/src/lib/components/shared/subscriptionExec.ts
- sha256:d7ffc0924894b233512fe62aea11ca83f321ab6e8f18539e9b7b0acee9e8fe6b  frontend/src/lib/components/shared/versand-tab/sendTargetLabel.ts
- sha256:5e620f0c0297dadc431be6da4292dd1ab164465668ecf15f059f946e1a2deffc  frontend/src/lib/server/profileLoader.ts
- sha256:9e06ffedfa1f8fd701140d66fec7e2ea40a4ec0764ebae71f32fcc17cd518651  frontend/src/routes/__tests__/seiten_kompilieren_zu_gueltigem_js.test.ts
- sha256:1accd3c5ecbf0c7bd80d38edcd34b38895253cc0b1ef99397540a7eb87372346  frontend/src/routes/_home/kachelActions.ts
- sha256:4f7dca6b51d51c1c987205484448f0e4a64a6ed30dd46b2031aa8972fe695b93  frontend/src/routes/compare/[id]/+page.server.ts
- sha256:9b2615fbf90c8f69096aab3db82ed0b3fc486715be88d0d06eed2e04ca8fbd1e  frontend/src/routes/trips/+page.server.ts
- sha256:15ef7daf8d6c533454c4a8a3e15306f93d6285cca23d4305702dcc7dee4cfdbd  frontend/src/routes/trips/+page.svelte
- sha256:b23fcc3b0b504a16deb995051279bf299fc48e40b7d626ebbbf1200c94c04776  frontend/src/routes/trips/[id]/+page.server.ts
- sha256:3eae1553d48ae14f125572307a1157a14d830cc0b587d7fc8f038901278b9813  frontend/src/routes/trips/[id]/+page.svelte
- sha256:eb47fd35e51439b19c67be93fe6a43f6227dfdaee5b9b8ab30006c448dbae4b6  tests/tdd/test_bug_716_test_briefing_silent_fail.py

## Prüfbasis

- base: 302131e31733fa2f542b3cd1b3047b29c1faac93
- blob:22a8ffe51e8ae13b74331704024edad506717680  frontend/e2e/aktionsmodell-durchklick.spec.ts
- blob:dd5b44f8ec519ef2022c255805e0d70b13462ba4  frontend/e2e/helpers.ts
- blob:178d3da97825a39eea85530e1d3d325de5156101  frontend/e2e/issue-767-768-test-briefing.spec.ts
- blob:adc847d3e1eb509fdffac08f9bcd1250cc2c9ec6  frontend/e2e/send-in-flight-guard.spec.ts
- blob:0344d9f04bb6ec09c7a57f15f6a9037cc2e1af0d  frontend/src/lib/components/compare/subscriptionHelpers.ts
- blob:d2131a96976f5ed663bf6cdc5aa749dc17130c2e  frontend/src/lib/components/mobile/index.ts
- blob:291f6372e795db93b9d624a0a6ea13a5276e1d62  frontend/src/lib/components/molecules/ConfirmDialog.svelte
- blob:d013338b35f1ede383336c5d579db0fe48200ecd  frontend/src/lib/components/molecules/SendConfirmDialog.svelte
- blob:fb72e3e25069e716fe5ae346fe88565ca8f18390  frontend/src/lib/components/molecules/__tests__/send_confirm_dialog_sperre.test.ts
- blob:6d64e640a86c58c277ff2f586bfd8807978a833c  frontend/src/lib/components/molecules/index.ts
- blob:b98126bb5e3db7eef8bed8d1ece1bf555bcc0906  frontend/src/lib/components/molecules/sendConfirmModel.ts
- blob:5e00b5e180f6daefd4aab4a24300f242aeca9b1e  frontend/src/lib/components/shared/subscriptionActions.ts
- blob:0a1c633d0d25bf8ba976f70f9e8869ccd1eca00b  frontend/src/lib/components/shared/subscriptionExec.ts
- blob:8f8bb89e8f7474c066850f8a589cb3f3821ddd63  frontend/src/lib/components/shared/versand-tab/sendTargetLabel.ts
- blob:35d2d8521fa5cdf7988879cca4a8e94f7c0867e5  frontend/src/lib/server/profileLoader.ts
- blob:0554bf1730a21865e3ebadf59be347cb8a56ac1f  frontend/src/routes/__tests__/seiten_kompilieren_zu_gueltigem_js.test.ts
- blob:14dd57da2d02a6d9cac191da64704c8807c6d0cc  frontend/src/routes/_home/kachelActions.ts
- blob:a5bda77704a14d17da8027169d47b13a733d256d  frontend/src/routes/compare/[id]/+page.server.ts
- blob:df631580646e6d79794cd83ee150ed6aff60e8b9  frontend/src/routes/trips/+page.server.ts
- blob:0a1ec77694c2d7caa9ce76703ff71823d57ad67f  frontend/src/routes/trips/+page.svelte
- blob:ebe2129e6748f4e9194df506e122503680e72e1f  frontend/src/routes/trips/[id]/+page.server.ts
- blob:751b8bccdf5f4f62af11859e4e5caab3bd75d194  frontend/src/routes/trips/[id]/+page.svelte
- blob:e702583dcf865b4a4d4dcc6cd8159d04dd5f2645  tests/tdd/test_bug_716_test_briefing_silent_fail.py
