---
entity_id: fix_2361_abruf_zeitlimit
type: bugfix
created: 2026-10-17
updated: 2026-10-17
status: implemented
version: "1.0"
workflow: fix-2361-abruf-zeitlimit
issue: 2361
tags: [frontend, api-client, timeout, offline, etag]
---

# Zeitlimit fuer den zentralen Browser-Abruf send()

## Approval

- [ ] Approved

## Purpose

Der zentrale Abruf `send()` im Browser wartet bei einer praktisch toten Verbindung (z.B. EDGE-Funkloch) minutenlang, ohne dass die App irgendeine Rueckmeldung gibt. Diese Aenderung gibt jedem Abruf ein Zeitlimit, behandelt Ablauf wie einen Netzfehler (Verbindungs-Anzeige reagiert) und stellt sicher, dass die dadurch ausgeloeste Offline-Sperre sich von selbst wieder loesen kann.

## Source

- **File:** `frontend/src/lib/api.ts`
- **Identifier:** `send()` (plus `api.get/post/patch/del` fuer die Durchreichung von Optionen)

> Schicht: ausschliesslich Frontend (SvelteKit, `frontend/src/...`). Kein Go- oder Python-Code betroffen.

## Estimated Scope

- **LoC:** ca. +85 produktiv / +90 Test
- **Files:** 9 (7 MODIFY, 2 CREATE)
- **Effort:** medium (zentrale Funktion, aber kleine Aenderung)

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/api.ts` | MODIFY | Zeitlimit in `send()`, Default-Konstante + Test-Setter, Option `zeitlimitMs`, `get/post/patch/del` reichen Optionen durch, keepalive ausgenommen |
| `frontend/src/lib/stores/verbindung.svelte.ts` | MODIFY | Probe-Abruf `/api/health`, solange offline und Seite sichtbar |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | Budget 70 s fuer Compare-Vorschau |
| `frontend/src/lib/components/alerts-tab/AlertPreviewCard.svelte` | MODIFY | Budget 40 s fuer Alarm-Vorschau |
| `frontend/src/lib/components/compare/steps/Step2Orte.svelte` | MODIFY | Budget 40 s fuer `locations/resolve` |
| `frontend/src/lib/components/compare/LocationNewModal.svelte` | MODIFY | Budget 40 s fuer `locations/resolve` |
| `frontend/src/routes/account/+page.svelte` | MODIFY | Budget 130 s fuer `notify/test` |
| `frontend/src/lib/__tests__/apiZeitlimit.test.ts` | CREATE | Kern-Tests (node --test) |
| `frontend/src/lib/__tests__/verbindungProbe.test.ts` | CREATE | Kern-Tests Probe-Abruf (node --test) |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `fetch`, `AbortController`, `setTimeout` | Browser-API | Abbruch nach Zeitlimit, ohne `AbortSignal.timeout/any` (Safari < 17.4) |
| `frontend/src/lib/etagRegistry.ts` | module | Warteschlange `enqueueTripWrite`, ETag/If-Match, 412-Konfliktpfad `markiereKonflikt` |
| `frontend/src/lib/stores/verbindung.svelte.ts` | module | Reagiert auf `gz-abruf-fehlgeschlagen` / `gz-abruf-gelungen` |
| `frontend/src/lib/components/shared/OfflineSperre.svelte` | component | Sperrt Bedienelemente, solange offline |
| `GET /api/health` (Go-API, `internal/router/router.go`) | endpoint | Ziel des Probe-Abrufs, existiert bereits |
| `docs/specs/modules/fix_2124_versand_nginx_timeout.md` | Spec | Versand bleibt ohne Client-Limit (rohes fetch in `frontend/src/lib/utils/sendOutcome.ts`) |
| `docs/specs/modules/pwa_offline_ansicht_letzter_stand.md` | Spec | #2131 Abschnitt H / AC-10: Schreibsperre (`Error{status:0}`), Verbindungs-Store |
| `docs/specs/modules/issue_1395_s3_etag_registry.md`, `issue_1395_s4_conflict_retry.md` | Spec | ETag-Registry, 412-Konfliktbehandlung |

## Implementation Details

1. **Zeitlimit in `send()`:** pro Abruf ein `AbortController` plus `setTimeout`; nach Ablauf `abort()`. `clearTimeout` im `finally`, damit nach jedem Ausgang kein Timer uebrig bleibt. Das eigene Signal wird in den Fetch-Optionen NACH `...extra` gesetzt. Ein vom Aufrufer mitgegebenes `extra.signal` wird weiter beachtet: bricht der Aufrufer ab, wird der interne Controller mit abgebrochen.
2. **Budgets:** Default 25 s (EDGE-tauglich, ein Funkloch wird nach rund einer halben Minute gemeldet). Pro Aufruf ueberschreibbar ueber Option `zeitlimitMs`. Langlaeufer: Compare-Vorschau 70 s (Go-Proxy 60 s), `notify/test` 130 s (Go-Proxy 120 s), Alarm-Vorschau 40 s (Go-Proxy ca. 30 s), `locations/resolve` 40 s (Resolver gesamt bis ca. 30 s). Jeweils Server-Limit plus Puffer, damit der Server zuerst antwortet. `api.get/post/patch/del` reichen die Optionen kuenftig durch (bisher nur `put`).
3. **Test-Setter:** Der Default ist ueber eine exportierte Setter-Funktion senkbar (ca. 20 ms), damit Tests ohne Fake-Timer auskommen.
4. **keepalive:** Requests mit `keepalive: true` (Unload-Flush) erhalten kein Zeitlimit; die Seite ist ohnehin im Verlassen, der Browser begrenzt keepalive selbst.
5. **Fehlerpfad bei Ablauf:** wie bei einem Netzfehler `meldeAbrufAusgang(false)` (Event `gz-abruf-fehlgeschlagen`), danach Fehler weiterwerfen: eigener Fehler mit `name = 'TimeoutError'` und deutscher Meldung (Verbindung zu langsam bzw. keine Antwort). NICHT `status: 0` (das ist die Schreibsperre). Der Aufrufer-Abbruch bleibt ein `AbortError` und meldet weiterhin nichts als Fehlschlag.
6. **Keine automatischen Retries**, auch nicht fuer GET. Ein Wiederholen waere eine eigene Produktentscheidung.
7. **Schreibwege:** Ein abgebrochener PUT beendet seinen Eintrag in der Warteschlange (`enqueueTripWrite` schluckt Fehler), Folge-PUTs laufen wieder. Der ETag wird nur bei Erfolg aktualisiert; hat der abgebrochene PUT den Server doch erreicht, traegt der naechste PUT den alten ETag und endet in 412, also im bestehenden Konfliktpfad (`markiereKonflikt`) statt in stillem Ueberschreiben.
8. **Probe gegen die Sperr-Sackgasse:** Ein langsamer, aber erreichbarer Server kann durch das Zeitlimit die UI sperren; entsperrt wird bisher nur durch einen spaeteren gelungenen Abruf, den eine gesperrte UI nicht ausloest. Daher sendet `verbindung.svelte.ts` ueber `send()` einen `GET /api/health`, solange `offline` UND die Seite sichtbar ist (`document.visibilityState`), im Abstand von 15 s. 15 s ist kurz genug, dass die Sperre nach Rueckkehr der Verbindung zuegig faellt, und selten genug, dass im Funkloch weder Akku noch Datenvolumen merklich belastet werden (ein Probe-Abruf ist winzig). Erfolg loest `gz-abruf-gelungen` aus und entsperrt. Online ⇒ kein Intervall, keine Probe. Das Intervall wird beim Wechsel auf online oder bei unsichtbarer Seite beendet.

## Expected Behavior

- **Input:** Ein Abruf ueber `send()`, den der Server nicht innerhalb des Budgets beantwortet.
- **Output:** `TimeoutError` mit deutscher Meldung; Event `gz-abruf-fehlgeschlagen`; Verbindungs-Store wird offline.
- **Side effects:** Warteschlange des betroffenen Trips/Vergleichs ist wieder frei; im Offline-Zustand laeuft alle 15 s ein Probe-Abruf, der bei Erfolg entsperrt.

## Acceptance Criteria

- **AC-1:** Given die Verbindung ist praktisch tot und der Server antwortet nie / When die App einen normalen Abruf startet / Then meldet die App nach Ablauf des Zeitlimits einen Fehler (`TimeoutError` mit deutscher Meldung) und die Verbindungs-Anzeige wechselt auf "offline", statt endlos zu warten.
  - Test: fetch-Mock loest nie auf, Default-Limit per Setter auf ca. 20 ms; `send()` wirft `TimeoutError`, `gz-abruf-fehlgeschlagen` feuert genau einmal, der Fehler hat kein `status: 0`.

- **AC-2:** Given der Server antwortet langsam, aber noch innerhalb des Zeitlimits / When die App einen Abruf startet / Then wird der Abruf nicht abgebrochen, das Ergebnis kommt an und die Verbindung gilt als gut.
  - Test: fetch-Mock antwortet nach der Haelfte des Limits; `send()` liefert die Antwort, `gz-abruf-gelungen` feuert, kein Fehlschlag-Event; danach bleibt kein offener Timer zurueck.

- **AC-3:** Given eine bewusst lange Aktion wie die Compare-Vorschau, der Test-Versand der Benachrichtigung, die Alarm-Vorschau oder die Orts-Suche / When die Aktion laenger als das Standard-Limit, aber kuerzer als ihr eigenes Budget dauert / Then wird sie nicht vorzeitig abgebrochen.
  - Test: Aufruf mit `zeitlimitMs` groesser als der (gesenkte) Default; fetch-Mock antwortet nach Ablauf des Defaults, aber vor dem eigenen Budget; Abruf gelingt. Zusatz: die fuenf Aufrufstellen uebergeben 70 s / 130 s / 40 s / 40 s / 40 s (Verhaltenstest ueber den Pfad `api.post(..., { zeitlimitMs })`, kein Quelltext-Check).

- **AC-4:** Given die App speichert beim Verlassen der Seite Aenderungen mit dem Sofort-Versand (keepalive) / When dieser Abruf gesendet wird / Then bekommt er kein Zeitlimit und wird nicht von der App abgebrochen.
  - Test: Request mit `keepalive: true` und gesenktem Default; das an fetch uebergebene Signal wird durch das Zeitlimit nicht ausgeloest, der spaet antwortende Mock liefert ein Ergebnis.

- **AC-5:** Given ein Abruf, den der Aufrufer selbst abbrechen kann / When der Aufrufer ihn abbricht, bevor das Zeitlimit ablaeuft / Then wird der Abruf sofort abgebrochen wie bisher und es wird keine Verbindungsstoerung gemeldet.
  - Test: `extra.signal` wird abgebrochen; `send()` wirft `AbortError` (nicht `TimeoutError`), kein `gz-abruf-fehlgeschlagen`; ein Aufrufer-Signal geht auch dann nicht verloren, wenn es nach `...extra` mit dem eigenen zusammengefuehrt wird.

- **AC-6:** Given ein Abruf laeuft in das Zeitlimit / When der Fehler gemeldet wird / Then startet die App den Abruf nicht von selbst erneut (weder Lesen noch Schreiben), sodass nichts doppelt gespeichert oder gesendet wird.
  - Test: fetch-Mock zaehlt Aufrufe; nach Timeout (GET und PUT) bleibt der Zaehler bei 1, auch nach einer Wartezeit von mehreren Limits.

- **AC-7:** Given ein Speichern (PUT) eines Trips ist ins Zeitlimit gelaufen, der Server hat die Aenderung aber moeglicherweise schon angenommen / When der Nutzer danach erneut speichert / Then wird das zweite Speichern nicht blockiert, und hat sich der Stand auf dem Server geaendert, erscheint der bekannte Konflikt-Hinweis (412) statt eines stillen Ueberschreibens.
  - Test: Erster PUT haengt bis Timeout, Folge-PUT startet danach (Warteschlange frei, kein Dauer-Haengen), traegt den alten `If-Match`-ETag; Mock antwortet 412 ⇒ `markiereKonflikt` wird aufgerufen, der Server-Stand wird nicht ueberschrieben.

- **AC-8:** Given die App ist wegen eines Zeitlimits oder Netzfehlers gesperrt (offline) und die Seite ist sichtbar / When die Verbindung wieder funktioniert / Then entsperrt sich die App spätestens nach etwa 15 Sekunden (Probe-Intervall) von selbst, ohne dass der Nutzer etwas tun muss; ist die App online, laeuft kein solcher Hintergrund-Abruf.
  - Test: Store offline setzen ⇒ nach dem Probe-Intervall (im Test verkuerzt) geht ein `GET /api/health` raus; Mock antwortet 200 ⇒ Store ist online und die Probe stoppt. Store online ⇒ kein `/api/health`-Abruf. Seite unsichtbar ⇒ kein Probe-Abruf.

- **AC-9:** Given die App ist offline (Schreibsperre aus #2131) / When der Nutzer eine schreibende Aktion versucht / Then wird sie weiterhin sofort mit der Sperr-Meldung (`status: 0`) abgewiesen, und alle bestehenden ETag- und Konflikt-Ablaeufe verhalten sich unveraendert.
  - Test: `apiSchreibsperre.test.ts` und die vorhandenen ETag-Tests (`etagRegistry`, Konflikt-Retry, Vergleichs-ETag) laufen unveraendert gruen.

## Test-Plan

Kern-Schicht, ohne Netz, Runner `node --test` (kein Vitest). Muster: `frontend/src/lib/__tests__/apiSchreibsperre.test.ts` (`globalThis.window = new EventTarget()` vor dem dynamischen `await import('../api.ts')`, `globalThis.fetch` ersetzen und wiederherstellen, auf `gz-abruf-fehlgeschlagen` / `gz-abruf-gelungen` lauschen). Der fetch-Mock lehnt auf das Abbruch-Signal ab (`init.signal` 'abort'), damit echtes Abbruchverhalten geprueft wird.

| Datei | Neu/Bestand | Deckt ab |
|-------|-------------|----------|
| `frontend/src/lib/__tests__/apiZeitlimit.test.ts` | neu | AC-1 bis AC-7 (Timeout, fristgerechte Antwort, eigenes Budget, keepalive, Aufrufer-Abbruch, keine Retries, PUT-Warteschlange + 412) |
| `frontend/src/lib/__tests__/verbindungProbe.test.ts` | neu (eigene Datei, weil der Store Svelte-Runes nutzt und eigene Test-Vorbereitung braucht) | AC-8 |
| `frontend/src/lib/__tests__/apiSchreibsperre.test.ts` und vorhandene ETag-Tests | Bestand | AC-9 (Regression) |

Mutations-Gegenproben fuer den Adversary: Timer nicht aufraeumen, Signal VOR `...extra` setzen, keepalive nicht ausnehmen, Retry einbauen, Probe ohne Sichtbarkeits-/Offline-Pruefung, `status: 0` am Timeout-Fehler; jede Verfaelschung muss einen benannten Test rot machen.

## Nicht im Scope

- **Direkte `fetch()`-Aufrufe** ausserhalb von `send()` bleiben unveraendert: Datenexport (ZIP) und GPX-Upload (lang laufend legitim), Versand-Ausloeser `sendOutcome.ts` (bewusst ohne Client-Limit, bis 330 s, siehe `fix_2124_versand_nginx_timeout.md`), Vorschau-Iframes (`EmailIframe`, `SmsPhoneFrame`, haben eigenen Abbruch), Passkey, `StageList` (`/stages/weather`), Historien-Dialog, Profil-GETs sowie Status-PUT/DELETE in den Routen. Sie melden schon heute nicht an den Verbindungs-Store; sie einzubeziehen wuerde den Umfang stark vergroessern und das Risiko fehlerhafter Abbrueche erhoehen.
- **Automatische Wiederholung (Retry)** von Abrufen, auch fuer reine Lesezugriffe: eigene Produktentscheidung.
- **Aenderungen an Server (Go/Python), Service Worker oder Offline-Anzeige**: unveraendert. Der Service Worker faengt `/api/`-Anfragen nicht ab.
- Die `online`-Browser-Meldung als Entsperr-Ausloeser bleibt bewusst ausgeschlossen (siehe `verbindung.svelte.ts`).

## Risiken

1. **Fehl-Sperre durch zu knappes Budget:** Ein erreichbarer, aber langsamer Server loest "offline" aus. Gegenmassnahmen: Langlaeufer erhalten eigene Budgets (Go-Proxy-Limit plus Puffer); die Probe entsperrt die UI wieder.
2. **Zentrale Funktion:** `send()` wird von allen Frontend-Aufrufen genutzt. Gegenmassnahmen: kleine Aenderung, bestehende Regressionstests (AC-9), Staging-Verifikation.
3. **Schreiben nach Timeout:** Die Anfrage kann den Server erreicht haben. Es gibt keinen Retry, und der naechste PUT laeuft in den 412-Konfliktpfad (AC-7). Muss per Test belegt sein, nicht nur angenommen.
4. **Probe-Last:** Im dauerhaften Funkloch ein kleiner Abruf alle 15 s, nur bei sichtbarer Seite. Vernachlaessigbar.
5. **Neu zu pflegende Budgets:** Aendert sich ein Go-Proxy-Timeout, muss das Frontend-Budget mitwandern; deshalb steht das jeweilige Server-Limit im Kommentar an der Aufrufstelle.

## Known Limitations

- Ein Zeitlimit ist kein Beweis, dass der Server die Anfrage nicht verarbeitet hat; bei Schreibvorgaengen faengt nur der ETag-Mechanismus das ab.
- Direkte `fetch()`-Aufrufe (siehe Nicht im Scope) haben weiterhin kein App-seitiges Zeitlimit.
- Das Zeitlimit deckt nur den Zeitraum bis zum Eintreffen der Antwort-Kopfzeilen ab; haengt der Server danach beim Ausliefern des Antwortkoerpers, wartet `res.json()` ohne Limit (unwahrscheinlich bei kleinen JSON-Antworten, Nebenbefund #1199).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Keine Grundsatzentscheidung: Kanaele, Provider, Datenmodell, Auth und Editor-Paradigma bleiben unberuehrt. Der Versand ohne Client-Limit (#2124) und die Schreibsperre (#2131) bleiben bestehen.

## Changelog

- 2026-10-17: Initial spec created (Issue #2361)
- 2026-10-17: Umsetzung (Issue #2361) - Abweichungen von der Affected-Files-Tabelle:
  - `frontend/src/routes/_home/onboardingAktionen.ts` setzt das 130-s-Budget fuer den Testnachricht-Aufruf (notify/test) im Onboarding (fachlich noetig, gleicher Endpoint wie in account); dazu Test `onboarding_aktionen.test.ts`.
  - Zusaetzliche Tests: `verbindungProbeStartOffline.test.ts` und E2E `langlaeufer-zeitbudget-wirkort.spec.ts` (Wirkort-Nachweis der Komponenten-Verdrahtung, Fix-Loop 2).
  - CI-Ratsche als Folge der neuen E2E-Datei: `E2E_MIN_SPECS` 62 -> 63 und `E2E_MIN_EXECUTED_HAUPT` 363 -> 368 in `.github/workflows/ci.yml`, Eintrag in `.github/ci_e2e_specs.txt`.
