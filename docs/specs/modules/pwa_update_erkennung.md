---
entity_id: pwa_update_erkennung
type: module
created: 2026-09-13
updated: 2026-09-13
status: implemented
version: "1.0"
tags: [pwa, frontend, offline, service-worker, issue-2316, epic-2127]
---

# PWA: aktive Update-Erkennung

Issue #2316 · Epic #2127 · Nachfolger von #2128 (`pwa_installierbar_offline_start.md`) und #2131
(`pwa_offline_ansicht_letzter_stand.md`) · Fortschreibung ADR-0061 §3

## Approval

- [x] Approved

## Purpose

Die installierte App erkennt neue Fassungen aktiv (nicht mehr nur beim zufälligen Neustart), bietet
das Update über einen zurückstellbaren Hinweis an und lädt dabei — bindend aus #2127 — Programmdateien
weiterhin erst NACH dem Antippen. Ungespeicherte Eingaben auf Trip- und Ortsvergleich-Detailseiten
gehen beim Update nicht verloren.

## Source

- **File:** `frontend/src/lib/pwa/serviceWorkerUpdate.ts` (bleibt einzige Quelle des Update-Ablaufs)
- **Weitere Dateien:** `frontend/src/routes/+layout.svelte`, `frontend/src/routes/compare/[id]/+page.svelte`,
  `frontend/src/routes/trips/[id]/+page.svelte`, `frontend/src/service-worker.ts`
- **Schicht:** Frontend (SvelteKit). Kein Go-Anteil, kein Python-Anwendungscode. `/api/*` bleibt vom
  Service Worker unberührt (ADR-0003).

## Estimated Scope

- **LoC:** Produktiv ~+110–140, Tests ~+300–400 (LoC-Limit ggf. per `set-field loc_limit_override`
  anheben)
- **Files:** ~9–11 (Modul + Test, Layout, zwei Detailseiten, Service-Worker-Message-Handler,
  E2E-Spezifikationen + `pwaHelpers.ts`, CI-Workflow, ADR-0061)
- **Effort:** high
- **Schnitt (zwei Scheiben, eine Spec, ACs unten markiert):**
  - **Scheibe A** — gemeinsamer Speicher-Wächter für `trips/[id]` und `compare/[id]`. Schließt die
    bestehende Verlustlücke bei `compare/[id]`, BEVOR aktives Prüfen sie durch häufigere Updates
    vervielfacht. Klein.
  - **Scheibe B** — Prüf-Auslöser/Drossel/„Später"/Rückfall in `serviceWorkerUpdate.ts`, Worker-
    Fehlschlagmeldung, Layout-Verdrahtung inkl. Vorrang am Bildschirmrand und Zurückhalten auf
    Anlege-Seiten, E2E + CI-Ratsche, ADR-0061 §3.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Service-Worker-API (`updatefound`, `statechange`, `controllerchange`, `registration.update()`) | Upstream | Grundlage der Erkennung |
| SvelteKit-Registrierung (Default, `updateViaCache: imports`) | Upstream | Registriert `/service-worker.js`, revalidiert per ETag (304/0 Byte gemessen 13.09.) |
| `frontend/src/lib/components/mobile/Toast.svelte` / Passkey-Zweiknopf-Muster (`+layout.svelte:248-282`) | Upstream (Vorlage) | Zweiknopf-Hinweis „Aktualisieren"/„Später", keine neue Komponente |
| `beforeNavigate` mit `willUnload:true` (SvelteKit-Client, `@sveltejs/kit/src/runtime/client/client.js:2662-2681`) | Upstream | `location.reload()` löst `beforeunload` → `beforeNavigate` aus; trägt den Speicher-Wächter |
| `trips/[id]/+page.svelte` (bestehender Wächter) | Upstream (Referenz) | Vorlage für die gemeinsame Hilfsfunktion |
| `#2131` Offline-Ansichten / `PROGRAMMPFADE` (`service-worker.ts:59-60`) | Downstream | Nicht Teil dieser Spec, siehe Known Limitations |
| `.github/workflows/ci.yml` (`E2E_MIN_EXECUTED_PWA`) | Downstream | Ratsche muss mit neuen E2E-Fällen angehoben werden |

## Implementation Details

```
serviceWorkerUpdate.ts (Scheibe B):
- Auslöser: document.addEventListener('visibilitychange', ...) bei sichtbar,
  window.addEventListener('pageshow', ...), setInterval alle 30 Min NUR wenn document.visibilityState
  === 'visible'; beim Verstecken Timer stoppen (clearInterval), beim erneuten Sichtbarwerden neu starten.
- Drossel: hereingereichte Uhr (z.B. { now(): number }) statt Date.now() direkt, wie registration/
  container/reload heute hereingereicht werden. Prüfaufruf nur wenn now() - letzterPruef >= 60_000.
- Sobald registration.waiting existiert: keine weitere registration.update()-Anfrage mehr auslösen.
- "Später": Modul-interner State (kein Store, keine Persistenz), setzt sich bei Kaltstart (Modul-
  Neuinitialisierung) zurück.
- Rückfall: auf 'controllerchange' warten; bleibt es nach erreichtem 'activated' aus, GENAU EINMAL nach
  4s reload() aufrufen (Timer hereingereicht). Bleibt der Worker in 'installed' hängen (Download im
  Worker gescheitert), KEIN Timer-Reload.
- Fehlschlag-Empfang: navigator.serviceWorker.addEventListener('message', ...) auf
  { type: 'UPDATE_FEHLGESCHLAGEN' } -> Zustand "Fehlschlag" exportieren, Hinweis zeigt Meldung,
  "Aktualisieren" bleibt/wird wieder antippbar, kein Reload.

service-worker.ts (Scheibe B, message-Handler ~509-529):
- catch-Zweig um den Download-Schritt vor skipWaiting(): bei Fehler an ALLE Fenster
  postMessage({ type: 'UPDATE_FEHLGESCHLAGEN' }) senden (self.clients.matchAll()), dann return ohne
  skipWaiting().

+layout.svelte (Scheibe B):
- Zweiknopf-Hinweis nach Vorlage Passkey-Banner (248-282): "Aktualisieren" ruft applyUpdate() aus dem
  Modul, "Später" setzt den Modul-internen Später-Zustand.
- Sichtbarkeits-Vorrang: Hinweis nur rendern wenn weder iOS-Installationshinweis noch Passkey-Angebot
  sichtbar sind (bestehende reaktive Zustände abfragen, keine neue globale Zustandsmaschine).
- Zurückhalten auf /trips/new und /compare/new: aktuelle Route über $page.url.pathname prüfen.

compare/[id]/+page.svelte + trips/[id]/+page.svelte (Scheibe A):
- Gemeinsame Hilfsfunktion (z.B. in frontend/src/lib/pwa/ oder frontend/src/lib/save/) die
  beforeNavigate({ willUnload }) auf den jeweiligen saveStatusStore anwendet und bei hasPending
  flush({ keepalive: true }) auslöst — exakt das Verhalten, das trips/[id] heute schon hat, aber
  einmal geschrieben und von beiden Detailseiten aufgerufen (Trip/Vergleich-Code-Teilung ist Pflicht).
- KORREKTUR nach RED-Messung (13.09.): Auf compare/[id] wird hubSaveCtl.hasPending heute NIE true —
  der Vergleichs-Hub nutzt kein schedule(): CorridorEditor.svelte:211-218 endet bei
  context==='vergleich' nach syncToWizard(); gespeichert wird nur bei focusout/click
  (CompareTabs.svelte:504, 1420-1424). Gemessen verloren: Zahl im Reiter Idealwerte eingetippt,
  Feld nicht verlassen, neu geladen (E2E: erwartet 45, erhalten 30). Getippt+verlassen,
  „Markieren" und beides hintereinander: 9/9 gespeichert.
  Daher: Der Vergleichs-Hub meldet eine eingetippte Änderung genauso wie der Trip
  (context==='route') über saveController.schedule() an, sodass hasPending true wird und der
  geteilte Wächter sie beim Neuladen mit keepalive überträgt. Keine Compare-Sonderlösung.
```

### Testplan und Messbefunde (Messung 13.09., Playwright 1.59.1, Chromium)

- `context.route('**/sw.js')` fängt die **Update-Prüfung** des Worker-Skripts NICHT ab (nur die
  Erstregistrierung). Auch `context.on('request')` sieht die Prüfanfrage nicht. Ein Versionswechsel
  per Umleitung ist daher nicht baubar; ebenso ist „nur das Worker-Skript wurde angefragt" nicht über
  Browser-Anfrage-Ereignisse positiv messbar, sondern nur auf der ausliefernden Seite.
- **Trägt:** Der ausliefernde Server liefert unter derselben URL eine byte-veränderte Fassung B →
  `registration.update()` löst `updatefound` aus. Die E2E-Strecke braucht daher auf dem
  Auslieferungsweg (Preview-Server, Port 4173, `frontend/e2e/start-preview.sh`) eine zweite Fassung.
  Der heutige Helfer `triggerServiceWorkerUpdate` (`frontend/e2e/pwaHelpers.ts` 160-174) registriert
  nur dieselbe Datei neu und ist kein echter Wechsel. Den Mechanismus wählt die Implementierung;
  Anforderung: echter Byte-Wechsel, kein Übersteuern von `registration`.
- Headless-Chromium ändert `visibilityState` nicht selbst; der Sichtbarkeitswechsel darf im E2E per
  Ereignis am Dokument simuliert werden, `registration.update()` muss dabei echt laufen.
- Die Programmdatei-Zählung aus #2128 AC-10 (`context.on('request')` + `r.serviceWorker()`) bleibt
  gültig: Anfragen, die der Worker selbst stellt, sind sichtbar.
- Unit-Tests (`node:test`) nutzen echte `EventTarget`-Doppel und eine hereingereichte Uhr; kein
  `waitForTimeout`, kein Mock-Theater.
- CI: `speicherung-ueberlebt-neuladen.spec.ts` neu in `.github/ci_e2e_specs.txt` (Filter B im
  Zielverbund 3× gemessen); `E2E_MIN_SPECS: 47`, `E2E_MIN_EXECUTED_HAUPT: 229`,
  `E2E_MIN_EXECUTED_PWA: 60` in `.github/workflows/ci.yml`.

## Expected Behavior

- **Input:** Sichtbarwerden der Seite, `pageshow`-Ereignis, 30-Minuten-Intervall (nur sichtbar),
  Navigation; Antippen von „Aktualisieren"/„Später"; Worker-Fehlschlagmeldung.
- **Output:** Update-Hinweis erscheint/verschwindet regelgerecht; Reload nur nach angenommenem und
  erfolgreichem Update oder als einmaliger Rückfall bei ausbleibendem `controllerchange`.
- **Side effects:** `registration.update()`-Aufrufe (0 Byte dank ETag-Revalidierung, außer bei echter
  neuer Fassung); Speichern ungesicherter Änderungen auf `trips/[id]`/`compare/[id]` vor Reload;
  `postMessage` vom Worker an alle Fenster bei Fehlschlag.

## Acceptance Criteria

- **AC-1:** Given die App ist installiert und läuft im Hintergrund, eine neue Fassung wurde ausgeliefert / When der Nutzer die App wieder in den Vordergrund holt / Then erscheint der Update-Hinweis automatisch, ohne dass der Nutzer manuell neu laden muss. *(Scheibe B)*
  - Nachweis: E2E Projekt `pwa`

- **AC-2:** Given noch kein wartender Worker existiert / When die Seite über sichtbar, `pageshow`, Intervall oder Navigation wiederholt auf eine neue Fassung prüft / Then werden bis zum Antippen des Update-Hinweises null Programmdateien übertragen (gezählt wie #2128 AC-10 über `context.on('request')` und `r.serviceWorker()`). *(Scheibe B)*
  - Nachweis: E2E Projekt `pwa`

- **AC-3:** Given wiederholtes Prüfen hat einen wartenden Worker mit leerem eigenen Speicher erzeugt und alle Fenster wurden geschlossen / When die App danach ohne Netzverbindung erneut geöffnet wird / Then startet sie entweder mit einer lauffähigen Fassung oder zeigt die eigene Offline-Übersicht, nie die Browser-Fehlerseite. *(Scheibe B)*
  - Nachweis: E2E Projekt `pwa`

- **AC-4:** Given die Seite bleibt durchgehend sichtbar / When innerhalb von 60 Sekunden mehrere Prüf-Auslöser hintereinander feuern und danach die Uhr weiterläuft / Then wird höchstens einmal pro 60 Sekunden tatsächlich geprüft, und das 30-Minuten-Intervall läuft nur, solange die Seite sichtbar ist. *(Scheibe B)*
  - Nachweis: Unit `node:test`

- **AC-5:** Given ein wartender Worker existiert bereits / When ein weiterer Prüf-Auslöser feuert / Then wird keine weitere Prüfanfrage mehr ausgelöst, solange dieser Worker wartet. *(Scheibe B)*
  - Nachweis: Unit `node:test`

- **AC-6:** Given der Update-Hinweis wird gerade angezeigt / When der Nutzer auf „Später" tippt / Then verschwindet der Hinweis bis zum nächsten Kaltstart der App, auch wenn in der Zwischenzeit weitere Prüf-Auslöser feuern. *(Scheibe B)*
  - Nachweis: Unit `node:test` und E2E Projekt `pwa`

- **AC-7:** Given der iOS-Installationshinweis oder das Passkey-Angebot wird gerade am unteren Bildschirmrand angezeigt / When gleichzeitig ein Update verfügbar wird / Then bleibt der Update-Hinweis verborgen und erscheint erst, sobald der andere Hinweis geschlossen wurde — zwei Hinweise überlagern sich nie. *(Scheibe B)*
  - Nachweis: E2E Projekt `pwa`, Mobil-Viewport

- **AC-8:** Given der Nutzer bearbeitet gerade einen neuen Trip auf `/trips/new` oder einen neuen Ortsvergleich auf `/compare/new` / When währenddessen ein Update verfügbar wird / Then bleibt der Update-Hinweis zurückgehalten und erscheint erst nach dem Verlassen dieser Seite. *(Scheibe B)*
  - Nachweis: E2E Projekt `pwa`

- **AC-9:** Given der Nutzer hat auf der Detailseite eines bestehenden Ortsvergleichs (`/compare/[id]`) eine Zahl eingetippt und das Feld noch nicht verlassen, die Änderung ist also noch nicht übertragen / When die Seite neu geladen wird — so wie es ein angenommenes Update tut / Then ist die Änderung nach dem Neuladen gespeichert, nicht verloren, und es erscheint keine Verlassen-Rückfrage. *(Scheibe A)*
  - Nachweis: E2E (Reload mit ausstehender Änderung, danach Wert aus dem Server gelesen)

- **AC-10:** Given der Nutzer hat auf der Detailseite eines bestehenden Trips (`/trips/[id]`) eine Änderung gemacht, die noch nicht übertragen ist / When die Seite neu geladen wird — so wie es ein angenommenes Update tut / Then ist die Änderung nach dem Neuladen gespeichert, über denselben geteilten Speicher-Wächter wie beim Ortsvergleich. *(Scheibe A)*
  - Nachweis: E2E, beide Detailseiten mit gleichem Baustein; in Scheibe B zusätzlich einmal über den echten Update-Weg („Aktualisieren") im Projekt `pwa`

- **AC-11:** Given der Nutzer tippt „Aktualisieren" an, während das Gerät offline ist oder der Download im Worker fehlschlägt / When der Worker den Fehlschlag per Nachricht meldet / Then zeigt das Fenster eine verständliche Meldung, lädt NICHT neu, die alte Fassung bleibt aktiv, und „Aktualisieren" ist danach erneut antippbar. *(Scheibe B)*
  - Nachweis: Unit `node:test` und E2E Projekt `pwa`

- **AC-12:** Given der neue Worker erreicht den Zustand `activated`, aber `controllerchange` bleibt aus / When 4 Sekunden vergangen sind / Then lädt das Fenster genau einmal automatisch neu, kein zweites Mal. *(Scheibe B)*
  - Nachweis: Unit `node:test`

- **AC-13:** Given der wartende Worker bleibt im Zustand `installed` hängen (Download im Worker nicht abgeschlossen) / When Zeit vergeht / Then löst kein Timer einen blinden Reload aus. *(Scheibe B)*
  - Nachweis: Unit `node:test`

- **AC-14:** Given die ausgelieferte Fassung ist unverändert und die App läuft / When die Prüf-Auslöser (sichtbar, `pageshow`, Intervall) mehrfach feuern / Then kommen beim ausliefernden Server nur Abrufe des Worker-Skripts an, und im Browser entsteht dadurch keine einzige weitere Anfrage — weder an `/api/*` noch an Programmdateien. *(Scheibe B)*
  - Nachweis: E2E Projekt `pwa` (Worker-Skript-Abrufe serverseitig gezählt, übrige Anfragen über `context.on('request')`)

- **AC-15:** Given zwei aufeinanderfolgende Deploys liegen auf Staging vor und die erste Fassung ist als App installiert / When die installierte App danach erneut auf eine neue Fassung prüft / Then wird der zweite Deploy als Update erkannt und der Hinweis erscheint auf dem echten Auslieferungsweg (nicht nur simuliert). *(Scheibe B)*
  - Nachweis: Staging-Zweifach-Deploy

## Known Limitations

- **Unbestätigter Nebenbefund, NICHT Teil von #2316:** Aktiviert der Browser den wartenden Worker
  selbst (weil zwischenzeitlich alle Fenster geschlossen waren), hat der neue Worker einen leeren
  eigenen Speicher. Vorgehaltene #2131-Offline-Ansichten verweisen dann auf `/_app/immutable/*`-Pfade
  der ALTEN Fassung, die nicht in `PROGRAMMPFADE` (`service-worker.ts:59-60`) stehen und in Regel 5
  (nur Netz) landen — offline eventuell ohne Skript/Stil. Dieser Fall wird im Rahmen der E2E-Strecke
  (AC-3) am echten Ablauf mitbeobachtet; bestätigt er sich, folgt ein eigenes Issue.
- Speichern beim Entladen bleibt Best-Effort (`keepalive`), wie heute bei `trips/[id]`.
- Gemessen 13.09. (RED-Lauf): Nach dem Neuladen zeigte `/trips/[id]` noch den alten Wert, obwohl
  der neue schon gespeichert war — die Seite wurde geholt, bevor der `keepalive`-Speichervorgang
  ankam. AC-9/AC-10 sichern „gespeichert", nicht „sofort richtig angezeigt". **Behoben durch
  #2317** (`docs/specs/modules/speicherung_beim_neuladen.md`, Baustein 3,
  `stores/nachEntladenNachladen.ts`): die neu geladene Detailseite holt bei erkanntem
  Entladen-Speichern bis zu 6× im Abstand von 500 ms den Server-Stand nach. #2317 behebt außerdem,
  dass bei Wertebereichen, Alarmen und Wetter-Metriken „gespeichert" beim Entladen bis dahin nie
  verlässlich galt: die Speicherfunktionen der Reiter verschluckten den hier hereingereichten
  `init`-Parameter (Baustein 1) und „Aktualisieren" wartet seither eine ausstehende Speicherung
  regulär ab, bevor es die Fassung wechselt (Baustein 2, `stores/aktiveSpeicherung.ts`).
- Update-Notizen/Changelog für den Nutzer sind kein Ziel dieser Spec.
- Eine „Aktualisiert"-Meldung nach einer still (selbst) aktivierten Fassung ist kein Ziel dieser Spec.
- Keine nginx-Änderungen: Messung 13.09. zeigt `/service-worker.js` mit `ETag` → 304/0 Byte,
  Registrierung mit SvelteKit-Default `updateViaCache: imports`. Ändert sich künftig die Registrierung
  oder die Auslieferungs-Header, muss diese Invariante neu gemessen werden.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0061 (Fortschreibung §3, kein neues ADR)
- **Rationale:** Die aktive Update-Erkennung ändert nichts an der grundsätzlichen Bauform aus
  ADR-0061 (Service Worker, Speicherregeln, Nicht-Vorladen von Programmdateien) — sie ergänzt nur,
  WANN geprüft wird und wie der Nutzer den Wechsel bestätigt. §3 wird um die neuen Auslöser und die
  bei #2131 auf fünf gestiegene Zahl der Speicherregeln korrigiert (Titel/§2 sprechen dort noch
  fälschlich von „vier").

## Changelog

- 2026-09-13: Initial spec created (Issue #2316)
- 2026-09-13: Nach RED-Messung AC-9 präzisiert (nicht verlassenes Feld) und Umsetzungsweg Scheibe A
  korrigiert (Vergleichs-Hub meldet über `schedule()` an); Known Limitation „veraltete Anzeige nach
  Neuladen" ergänzt. Erneute PO-Freigabe nötig.
- 2026-09-13: Umsetzung Scheibe A + Scheibe B abgeschlossen. Adversary: 3 Runden, Verdict VERIFIED,
  15 Mutationen alle gefangen.
- 2026-09-13: F002 (Adversary MEDIUM, Mobil-Parität): Mobil-Pendant `CorridorEditorMobile.svelte`
  meldet beim Ortsvergleich ebenfalls über `saveController.schedule()` an — dieselbe
  `handleCorridorCommit`-Route (`CompareTabs.svelte`) wie am Desktop-Editor. Ergänzt um E2E-Fall
  „AC-9-Mobil" (laufende Ziehgeste am Band-Griff, Neuladen vor `pointerup`).
- 2026-09-13: Testkorrektur AC-10/AC-11 (PO freigegeben): `controller.scriptURL` bleibt beim
  Byte-Wechsel unter gleicher URL identisch (Sonde
  `docs/artifacts/feat-2316-pwa-update-erkennung/sonde-skripturl-bytewechsel.txt`); Fassungsnachweis
  daher über den Programm-Speichernamen `gz-<version>` (Helfer `fassungsKennung`) statt über die
  Skript-URL.
- 2026-09-13: CI-Ratsche angehoben: `speicherung-ueberlebt-neuladen.spec.ts` neu auf der
  Positivliste, `E2E_MIN_SPECS` 47, `E2E_MIN_EXECUTED_HAUPT` 229, `E2E_MIN_EXECUTED_PWA` 60
  (`pwa-update-erkennung.spec.ts` neu, 5 PWA-Dateien im Zweitlauf).
- 2026-09-13: AC-15 (Staging-Zweifach-Deploy, echter Auslieferungsweg) bleibt bis zum nächsten
  Zweifach-Deploy auf Staging offen — alle übrigen ACs sind über Unit-/E2E-Nachweis erfüllt, `status`
  wird trotzdem auf `implemented` gesetzt, da der Produktivcode vollständig steht.
- 2026-09-14: AC-15 auf Staging gemessen, **PASS** — möglich seit henemm-infra#229 (Zugriffe von der
  Server-IP ohne nginx-Basic-Auth; der Lauf nutzte bewusst keine Anmeldedaten für die Schranke).
  Zweiter Build desselben Commits `c3b42530` per `auto-deploy-gregor-staging.sh --force`:
  `service-worker.js` `f92fa465…` → `8455be42…`, Speichername `gz-1789330794578` → `gz-1789365451168`.
  Profil A (App blieb über den Deploy offen, App-eigene Prüfung per `visibilitychange`): wartender
  Worker + Hinweis „Neue Version verfügbar", nach „Aktualisieren" neuer Speichername, Hinweis weg.
  Profil B (App vor dem Deploy beendet, danach Kaltstart): Hinweis erscheint. Beide Profile vor dem
  Deploy nachweislich kontrolliert (`controller` gesetzt). Messprotokoll im Abschluss-Kommentar von
  Issue #2316.
