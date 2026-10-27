# Context: feat-2316-pwa-update-erkennung

## Request Summary
Die installierte PWA soll neue Fassungen aktiv erkennen (`registration.update()` bei Sichtbarwerden/`pageshow`/Intervall), den Update-Hinweis zurückstellbar machen und ungespeicherte Eingaben vor dem Reload schützen. Bindende Vorgabe aus #2127: **Programmdateien werden erst nach dem Antippen geladen** (PO-Entscheid, nicht erneut vorlegen). Issue #2316, Nachfolger von #2128.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/service-worker.ts` | install 86-97: Update (`registration.active`) lädt nichts vor, nur die Erstinstallation ruft `programmdateienAblegen()` (79-84). message 509-529: erst `SKIP_WAITING` lädt herunter, dann `skipWaiting`; bei Fehlschlag `return` ohne Umschalten. activate 115-131: Sweep nur bei gefülltem eigenem Speicher; spart `gz-daten-*` aus; `clients.claim()`. Offline-Übersicht 433-438 sucht `/offline.html` über alle Speicher. Nachladen fehlender Programmdateien 414-424 |
| `frontend/src/lib/pwa/serviceWorkerUpdate.ts` | Kern des Client-Ablaufs (77 Z.): `updatefound`→installed→Hinweis, `applyUpdate`→`SKIP_WAITING`, `controllerchange`→einmal Reload. Kein `update()`, kein Rückfall-Timer, kein „Später" |
| `frontend/src/lib/pwa/serviceWorkerUpdate.test.ts` | `node:test`, echte `EventTarget`-Doppel (`FakeWorker/FakeRegistration/FakeContainer`), 6 Fälle AC-8/9/10. Hier docken Erkennungs-, Drossel-, Später- und Timer-Logik an |
| `frontend/src/routes/+layout.svelte` | 143-158 Einbindung über `navigator.serviceWorker.ready`; 213-223 Toast (z 60). iOS-Hinweis (229) und Passkey-Banner (255) sitzen ebenfalls auf `bottom:76px` → mögliche gegenseitige Überdeckung |
| `frontend/src/lib/components/mobile/Toast.svelte` | Props `kind, msg, action?, hint?, onaction?`, nur EINE Aktion, kein Schließen. Passkey-Banner baut zwei Knöpfe selbst (Layout 248-282) |
| `frontend/src/lib/stores/verbindung.svelte.ts` | Singleton `verbindung` (`offline`, `ausSpeicher`, `gesperrt`), wiederverwendbar für „Update offline angetippt" |
| `frontend/src/lib/stores/saveStatusStore.svelte.ts` | `SaveState idle/dirty/saving/error/conflict`, `hasPending` (162); **pro Seite** instanziiert, Singletons ausdrücklich verboten (2-3) |
| `frontend/src/routes/trips/[id]/+page.svelte` | 39-58 `beforeNavigate`: bei `willUnload` `flush({keepalive:true})` ohne Rückfrage (PO-Entscheid), sonst `flush` + `goto` |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | 155-175 flush beim Tab-Wechsel |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | 411-419 `beforeNavigate` bricht bei `!to` (Reload) ab; Anlege-Zustand lebt nur im Speicher → geht beim Reload verloren |
| `frontend/src/routes/compare/[id]/+page.svelte` | 50 `hubSaveCtl`, **kein** `beforeNavigate`; `CompareNewEditor` ohne Wächter (Context `compare-wizard-state`) |
| `frontend/e2e/pwa-update-und-abmelden.spec.ts` | AC-9 (62-106), AC-10 Null-Download-Zählung (112-173, `context.on('request')` + `r.serviceWorker()`), AC-17 (179-238), AC-18 alle Fenster zu + offline (244-336) |
| `frontend/e2e/pwaHelpers.ts` | `triggerServiceWorkerUpdate` 160-174 registriert **dieselbe Datei** mit `?gz-e2e=<ts>` neu → gleiche Version, kein echter Byte-Wechsel |
| `frontend/e2e/pwa-grundausstattung.spec.ts`, `pwa-offline-ansicht-mit-stand.spec.ts` (AC-16 459), `pwa-offline-sperre-und-mandant.spec.ts`, `pwa-nachweis.staging.spec.ts` + `e2e/playwright.2128.staging.config.ts` | übrige PWA-Strecke / Staging-Nachweis |
| `frontend/playwright.config.ts` | Projekt `pwa` 55-62 (`serviceWorkers:'allow'`), sonst `'block'` |
| `.github/workflows/ci.yml` | 236-278, 396-434: zweiter Aufruf `--project=pwa`, Mindestzahl `E2E_MIN_EXECUTED_PWA: 49` (nicht in `ci_e2e_specs.txt`) |
| `frontend/svelte.config.js` | kein `kit.version`/`serviceWorker`-Option; Registrierung durch SvelteKit (Default), `updateViaCache` Default `imports` |

## Existing Patterns
- **Gekapselte Browser-Logik mit hereingereichten Abhängigkeiten** (`registration`, `container`, `reload`) statt `navigator`-Griff → testbar mit echten `EventTarget`-Doppeln, ohne Mock-Theater. Neue Auslöser (`document`, `window`, Uhr/Timer) sollten genauso hereingereicht werden.
- **Mobile-Erkennung** `window.matchMedia('(max-width: 899px)')` in `$effect` mit Cleanup (`TripTabs.svelte:136-140`).
- **Zweiknopf-Banner** existiert im Layout (Passkey-Angebot 248-282) — Vorlage für „Aktualisieren / Später" statt neuer Komponente.
- **Speichern vor Verlassen** ist pro Seite über `saveStatusStore`-Instanzen + `beforeNavigate` gelöst, nicht zentral.

## Dependencies
- Upstream: Service-Worker-API (`updatefound`, `statechange`, `controllerchange`, `registration.update()`), SvelteKit-Registrierung, `$service-worker` (`build`, `files`, `version`), nginx liefert `/service-worker.js` mit `ETag`, ohne `Cache-Control` → Revalidierung 304/0 Byte (gemessen 13.09.).
- Downstream: alle installierten Nutzer; #2131-Offline-Ansicht (AC-16 „Inhalt bleibt nach angenommenem Update"), Abmelde-Räumen (ADR-0061 §4).

## Existing Specs
- `docs/specs/modules/pwa_installierbar_offline_start.md` — AC-8 (296), AC-9 (302), AC-10 (307), AC-13 (335), AC-17 (316), AC-18 (359); Abschnitt „Download erst auf Antippen" 77-95, Vorkehrungen 97-113. Nennt den Unit-Test fälschlich „Vitest" (222).
- `docs/specs/modules/pwa_offline_ansicht_letzter_stand.md` — AC-16 (286).
- `docs/adr/0061-pwa-service-worker-bauform.md` §3 (82-92) fortzuschreiben; Titel/§2 sprechen noch von „vier" Speicherregeln (heute fünf seit #2131).
- `docs/adr/0063-pwa-offline-inhalte-positivliste-und-mandanten-bucket.md` §6 (Sweep spart Datencaches aus).

## Risks & Considerations
1. **Aktives Prüfen × Nicht-Vorladen (Hauptrisiko).** `update()` mit neuen Bytes installiert den Worker sofort; der Zustand „wartender Worker mit leerem Speicher" entsteht damit routinemäßig statt selten. Die Vorkehrungen (activate-Sweep nur bei gefülltem Speicher, Offline-Übersicht über alle Speicher, Nachladen bei Fehlgriff) müssen unter wiederholtem Prüfen tragen. Offene Frage für die Analyse: Nach Selbstaktivierung beim Schließen aller Fenster läuft der neue Worker mit leerem eigenem Speicher und dem alten `gz-<alt>`-Speicher daneben — beantwortet er Programmdatei-Anfragen der **neuen** Fassung offline? (Alte Dateien passen nicht zum neuen `build`-Manifest.) AC-18 prüft das heute nur mit künstlich umbenanntem Speicher derselben Version.
2. **E2E kann keinen echten Versionswechsel.** Der Helfer registriert dieselbe Datei neu; `update()` auf die unveränderte URL findet nichts. Für den Nachweis braucht es eine zweite Fassung mit anderen Bytes (z. B. Build-Variante oder vom Test ausgelieferter veränderter Worker unter derselben URL per `route`).
3. **Ungespeicherte Eingaben sind verstreut.** Keine app-weite Abfrage; Singleton-Store verboten. Varianten: (a) Hinweis nur außerhalb von Editor-Routen zeigen, (b) vor dem Reload über einen leichtgewichtigen Registrierungs-Mechanismus fragen, (c) vor dem Reload die seiteneigene `flush`-Logik anstoßen. `TripNewEditor`/`CompareNewEditor` haben Zustand nur im Speicher → dort hilft nur „nicht anbieten". Trip/Compare-Teilung beachten (gleiche Lösung für beide).
4. **Datenverbrauch des Prüfens:** heute 304/0 Byte dank ETag + `updateViaCache: imports`. Invariante festhalten, sonst frisst ein Intervall Volumen.
5. **Drossel/Intervall nur solange sichtbar**, sonst weckt ein Hintergrund-Timer das Gerät.
6. **Überdeckung am Bildschirmrand:** Update-Hinweis, iOS-Hinweis und Passkey-Banner teilen `bottom:76px`.
7. **CI-Ratsche:** `E2E_MIN_EXECUTED_PWA: 49` muss mit neuen Fällen angehoben werden; `waitForTimeout` vermeiden (Timer-Tests über hereingereichte Uhr).
8. **Staging braucht zwei Deploys** hintereinander (erst Mechanik, dann sichtbarer Wechsel).
9. **Rückfall-Timer vs. Fehlschlag-Pfad:** Ein Timer, der nach ~4 s blind neu lädt, darf den Fall „Download im Worker gescheitert → alte Fassung bleibt" nicht in einen Reload auf dieselbe alte Fassung verwandeln, ohne dem Nutzer zu sagen, dass das Update nicht geklappt hat.

## Analysis

### Type
Feature

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/pwa/serviceWorkerUpdate.ts` | MODIFY | Prüf-Auslöser (`visibilitychange` sichtbar, `pageshow`, Intervall nur solange sichtbar, Stopp sobald `waiting` existiert), Drossel über hereingereichte Uhr, „Später" als Modul-Zustand bis Kaltstart, Rückfall ohne blinden Reload |
| `frontend/src/lib/pwa/serviceWorkerUpdate.test.ts` | MODIFY | `node:test`, bestehende `EventTarget`-Doppel um `document`/`window`/Uhr erweitern |
| `frontend/src/routes/+layout.svelte` | MODIFY | Hinweis mit „Aktualisieren/Später" (Zweiknopf-Muster wie Passkey-Banner 248-282), auf Anlege-Routen zurückhalten, Vorrang gegenüber iOS-Hinweis/Passkey-Banner an `bottom:76px` |
| `frontend/src/routes/compare/[id]/+page.svelte` | MODIFY | Speicher-Wächter vor Verlassen/Reload wie `trips/[id]` (gemeinsame Hilfsfunktion, keine Compare-Sonderlösung) |
| `frontend/src/routes/trips/[id]/+page.svelte` | MODIFY (ggf.) | Wächter in gemeinsame Hilfsfunktion überführen |
| `frontend/src/service-worker.ts` | MODIFY (klein, ggf.) | Fehlschlag im `SKIP_WAITING`-Zweig an die Fenster melden (statt Zeitraten im Client) |
| `frontend/e2e/pwa-update-und-abmelden.spec.ts` / neue Spec, `frontend/e2e/pwaHelpers.ts` | MODIFY/CREATE | Nachweise im Projekt `pwa`; echter Byte-Wechsel des Workers nötig (heutiger Helfer registriert dieselbe Datei neu) |
| `.github/workflows/ci.yml` | MODIFY | `E2E_MIN_EXECUTED_PWA` anheben |
| `docs/specs/modules/<neue Spec #2316>.md` | CREATE | eigene Spec, verweist auf #2128/#2131-Specs |
| `docs/adr/0061-pwa-service-worker-bauform.md` | MODIFY | §3 fortschreiben; „vier" → „fünf" Speicherregeln |

### Scope Assessment
- Files: ~9–11
- Estimated LoC: Produktiv +105…135 (unter 250), Test +300…400 (nahe 500)
- Risk Level: HIGH (Service Worker entscheidet über Offline-Start aller installierten Nutzer)

### Technical Approach
Empfehlung Plan-Agent, gegengelesen:
- **Ein Modul** `serviceWorkerUpdate.ts` bleibt die einzige Quelle für den Update-Ablauf; neue Abhängigkeiten (`document`, `window`, Uhr) hereinreichen wie heute `registration`/`container`/`reload`.
- **„Später"** ohne Persistenz: Flag im Modul-Zustand; jeder echte Neustart setzt es zurück.
- **Ungespeicherte Eingaben:** `location.reload()` löst `beforeunload` aus, SvelteKit ruft darüber `beforeNavigate` mit `willUnload:true` (laut Plan-Agent in `@sveltejs/kit` client.js; in der Spec-Phase per Test belegen, nicht annehmen). Damit ist `trips/[id]` bereits geschützt (flush mit `keepalive`). Lücken: `compare/[id]` ohne Wächter → gleichen Wächter geteilt einbauen; Anlege-Editoren (`TripNewEditor`, `CompareNewEditor`) halten Zustand nur im Speicher → Hinweis dort zurückhalten. Kein zentraler Registrierungsmechanismus nötig.
- **Rückfall:** nicht blind nach fester Zeit neu laden. Auf `activated` warten; bleibt der wartende Worker `installed` (Download im Worker gescheitert, `service-worker.ts:509-529`), eine verständliche Meldung statt Reload. Eindeutiger per Rückmeldung aus dem `catch`-Zweig des Workers.
- **Leerer-Speicher-Fall für #2131-Offline-Ansichten** (siehe Risiko 1): Anfragen auf **alte** `/_app/immutable/*`-Pfade stehen nicht in `PROGRAMMPFADE` (`service-worker.ts:59-60`) und landen in Regel 5 (nur Netz). Ein Rückgriff in `ausSpeicherSonstNetz` würde nie erreicht; ein Fix müsste die Fetch-Weiche für alle Programmdateien ändern. **Nicht Teil von #2316**, separat zu klären (Befund noch am echten Ablauf zu bestätigen; #2131 AC-16 „Inhalt bleibt nach angenommenem Update" deckt den angenommenen, nicht den selbst aktivierten Fall ab).

### Dependencies
- Upstream: Service-Worker-API, SvelteKit-Registrierung (Default, `updateViaCache: imports`), `$service-worker` (`build`, `files`, `version`), `beforeNavigate`, nginx-Revalidierung (ETag → 304).
- Downstream: `+layout.svelte` ist einziger Importeur von `serviceWorkerUpdate`; `Toast.svelte` auch in `TripNewEditor`/`CompareNewEditor`; `createSaveStatus` in `trips/[id]` und `compare/[id]`; `verbindung.svelte.ts` in `OfflineSperre`, `offlineStand.ts`.

### Reihenfolge
1. Machbarkeit echter Byte-Wechsel im E2E klären (Preview-Server `e2e/start-preview.sh`, Port 4173; greift `context.route` für das Worker-Skript?). Fällt das weg: Nachweis auf Unit-Ebene + zweistufiger Staging-Nachweis.
2. Speicher-Wächter `compare/[id]` **vor/mit** den Prüf-Auslösern (sonst vervielfacht aktives Prüfen die bestehende Verlust-Lücke).
3. Auslöser/Drossel/Später/Rückfall in `serviceWorkerUpdate.ts`, Layout-Verdrahtung.
4. E2E + CI-Ratsche, ADR-0061 §3.

### Open Questions
- [ ] Leerer-Speicher-Fall der #2131-Offline-Ansichten: eigenes Ticket, das vor dem Rollout von #2316 geliefert wird? (Produktfrage an PO: Reihenfolge)
- [ ] Vorrang am unteren Rand, wenn Update-Hinweis, iOS-Installationshinweis und Passkey-Angebot gleichzeitig fällig sind → Tech-Entscheid in der Spec (Vorschlag: Update-Hinweis zuletzt, nie über einem anderen)
