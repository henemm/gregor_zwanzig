# Context: fix-2361-abruf-zeitlimit

## Request Summary
Issue #2361: Der zentrale Browser-Abruf `send()` in `frontend/src/lib/api.ts` läuft ohne Zeitlimit. Bei einer
praktisch toten Verbindung (EDGE-Funkloch) hängt er bis zum Browser-/OS-Default (Minuten), ohne Rückmeldung.
Gewünscht: Zeitlimit per `AbortSignal.timeout`, bei Ablauf derselbe Fehlerpfad wie ein Netzfehler; keine
automatischen Retries für schreibende Methoden.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/api.ts:73-83` | `send()` — Signatur, `extra?: RequestInit` |
| `frontend/src/lib/api.ts:96-104` | `opts = { method, ...extra, headers }` — Timeout-Signal muss NACH `...extra` gesetzt werden |
| `frontend/src/lib/api.ts:110-118` | `fetch(path, opts)` + catch → `meldeAbrufAusgang(false)`, Fehler unverändert weiter |
| `frontend/src/lib/api.ts:40-43` | `meldeAbrufAusgang` → DOM-Events `gz-abruf-gelungen` / `gz-abruf-fehlgeschlagen` |
| `frontend/src/lib/api.ts:58-71,175-181` | Schreibsperre (#2131 AC-10): schreibende Methoden werden vorab mit `Error{status:0}` abgewiesen |
| `frontend/src/lib/api.ts:174-198` | `request()`/`api.put` — nur `put` reicht `extra` durch; keepalive umgeht Warteschlange (:189-190) |
| `frontend/src/lib/api.ts:257,289` | direkte fetches: Datenexport (ZIP), GPX-Upload — lang laufend legitim |
| `frontend/src/lib/stores/verbindung.svelte.ts:46-51` | Verbindungs-Store: Fehlschlag ⇒ `offline=true`; nur ein gelungener Abruf entsperrt (online-Event bewusst nicht, :13-16) |
| `frontend/src/lib/components/shared/OfflineSperre.svelte:126-151` | sperrt Bedienelemente, sendet `gz-schreibsperre` |
| `frontend/src/lib/etagRegistry.ts:195-212` | `enqueueTripWrite`: Promise-Kette pro tripId; hängender fetch blockiert ALLE Folge-PUTs derselben Trip/desselben Vergleichs unbegrenzt |
| `frontend/src/lib/utils/sendOutcome.ts:5-6,119,127` | Versand-Trigger, rohes fetch, ausdrücklich OHNE Client-Timeout (bis 330 s, #2124) — nicht über `send()` |
| `frontend/src/service-worker.ts:447` | `/api/`-Anfragen werden NICHT abgefangen — SW irrelevant für den Abrufpfad |
| `frontend/src/routes/+page.server.ts` | einzige bestehende Nutzung von `AbortSignal.timeout` (SSR, #393) |

## Langläufer, die ÜBER `send()` laufen (Risiko Fehlabbruch)
- `CompareTabs.svelte:629-635` — `api.post('/api/preview/compare/{id}')` (Wetter-Vorschau, Go-Proxy-Timeout 60/120 s)
- `alerts-tab/AlertPreviewCard.svelte:34` — `api.post` Alarm-Vorschau
- `compare/steps/Step2Orte.svelte:122` — `/api/locations/resolve`

## Übrige direkte `fetch()`-Aufrufe im Browser (nicht über `send()`)
Passkey (`passkey.ts`), GPX-Upload (`TripNewEditor.svelte:321`, `gpx-upload/+page.svelte:54`), Vorschau-Iframes
(`EmailIframe`/`SmsPhoneFrame`, eigener AbortController), `StageList.svelte:31` (`/stages/weather`, Server bis 120 s),
`BriefingHistoryDialog.svelte:48`, Profil-GETs (AlarmeTab:188, WeatherMetricsTab:538, VTBriefingChannels:106),
Status-PUT/DELETE in `routes/archiv`, `routes/compare`, `routes/compare/[id]`, `routes/trips`, `routes/trips/[id]`,
`routes/locations/+page.svelte:26`. Diese melden auch heute NICHT an den Verbindungs-Store.

## Existing Patterns
- Test-Muster (`src/lib/__tests__/apiSchreibsperre.test.ts:24-53`): `globalThis.window = new EventTarget()` vor
  dynamischem `await import('../api.ts')`, `globalThis.fetch` ersetzen/wiederherstellen, auf
  `gz-abruf-fehlgeschlagen` lauschen. Runner: `node --test` (kein Vitest), `package.json:13`.
- Fake-Timer nutzt kein Test; `AbortSignal.timeout` wird von `mock.timers` vermutlich nicht erfasst ⇒ Zeitlimit
  konfigurierbar machen und mit ~20 ms testen; fetch-Mock rejectet auf `init.signal` 'abort'.
- Signal-Kombination: `extra?.signal ? AbortSignal.any([extra.signal, AbortSignal.timeout(ms)]) : AbortSignal.timeout(ms)`.
  `AbortSignal.any` bisher nirgends genutzt (Browser-Support: Safari ≥17.4).

## Dependencies
- Upstream: `fetch`, `AbortSignal`, `etagRegistry` (ETag/If-Match, Warteschlange), Verbindungs-Store-Events.
- Downstream: alle `api.get/post/put/patch/delete`-Aufrufer, Unload-Flush (keepalive: `tripSpeicherung.ts:150`,
  AlarmeTab:388, WeatherMetricsTab:1010/1037, CorridorEditor:267, `*VergleichSpeicherung.ts`).

## Existing Specs
- `docs/specs/modules/fix_2124_versand_nginx_timeout.md` — Versand 60–300 s, nginx 330 s; Z.162: kein Client-Timeout <330 s für den Versand (30 s Hard-Timeout verworfen)
- `docs/specs/modules/pwa_offline_ansicht_letzter_stand.md` (#2131, Abschnitt H, AC-10), `pwa_installierbar_offline_start.md`
- `docs/specs/modules/issue_1395_s2_etag_ifmatch.md`, `…s3_etag_registry.md`, `…s4_conflict_retry.md`, `…s6_ortsvergleich_etag.md`
- `docs/specs/modules/home_weather_fetch_timeout.md`, `fix_1912_scheduler_briefing_timeout.md` (Backend, nur Hintergrund)

## Risks & Considerations
1. **Zeitlimit ⇒ Offline-Sperre:** Ein Timeout feuert `gz-abruf-fehlgeschlagen` ⇒ `offline=true` ⇒ ganze UI gesperrt,
   bis ein Abruf gelingt. Ein langsamer, aber erreichbarer Server (z.B. Vorschau-Berechnung) sähe wie „offline" aus.
   Entsperren hängt an einem späteren gelungenen Abruf — gibt es keinen, bleibt die Sperre stehen. Zu klären: soll
   Timeout dieselbe Sperre auslösen (Issue sagt ja) und wie entsperrt es sich?
2. **Langläufer über `send()`:** Compare-/Alarm-Vorschau dürfen serverseitig bis 60/120 s brauchen. Ein pauschales
   20–30-s-Limit bricht sie fälschlich ab ⇒ Ausnahme pro Aufruf (längeres Budget) nötig, oder Budget daran messen.
3. **Schreibvorgang nach Timeout:** Request kann den Server erreicht haben. Kein Auto-Retry; nächster PUT trägt den
   alten ETag ⇒ 412-Konfliktpfad (#1395 S4) fängt das ab — muss geprüft, nicht angenommen werden.
4. **Warteschlange:** Heute blockiert ein hängender PUT alle Folge-PUTs unbegrenzt; das Zeitlimit löst das (Nebennutzen).
5. **keepalive-Flush beim Verlassen:** Timeout-Signal am keepalive-Request ist harmlos, Seite ist ohnehin weg; nicht
   verschlechtern.
6. **Versand bleibt ohne Limit** (#2124) — `sendOutcome.ts` darf nicht über `send()` laufen bzw. kein Limit bekommen.
7. **Scope der direkten fetches:** Sie umgehen `send()` und den Verbindungs-Store. Einbeziehen würde den Scope stark
   vergrößern; Analyse muss entscheiden, ob nur `send()` (Issue-Kern) oder auch kurze Status-PUT/DELETE-/GET-Aufrufe.

## Analysis

### Type
Bug (nutzersichtbar: App hängt bei toter Verbindung ohne Rückmeldung, Verbindungs-Store feuert nie)

### Verifizierte Befunde (Plan/Sonnet + Gegenprüfung)
- **Entsperren:** Kein Probe-/Polling-Abruf. Entsperrt wird ausschließlich durch `gz-abruf-gelungen`
  (`stores/verbindung.svelte.ts:49-51`); `online`-Event bewusst nicht (`:13-16`). `OfflineSperre.svelte:137` ist nur ein
  300-ms-Durchsetzungs-Intervall. Gesperrt werden nur `main button/input/select/textarea` (`:100-105`) — Links/Navigation
  bleiben frei, aber SSR-Loads laufen nicht über `send()` und entsperren nicht. ⇒ Mit Zeitlimit kann ein langsamer, aber
  erreichbarer Server die UI sperren, ohne dass sie sich selbst wieder entsperrt. **Diese Sackgasse verschärft der Fix
  selbst ⇒ im selben Ticket schließen** (Probe-GET `/api/health` solange `offline`, Seite sichtbar; `/api/health`
  existiert, `internal/router/router.go:224`).
- **Langläufer über `send()` (Go-Proxy-Timeouts):** Compare-Vorschau 60 s (`preview_proxy.go:52`, Aufrufer
  `CompareTabs.svelte:629-635`); Alarm-Vorschau ~30 s (`proxy.go:336`, `AlertPreviewCard.svelte:34`) — Kontext-Angabe
  60/120 s war falsch; `/api/notify/test` 120 s (`proxy.go:124`, `router.go:256`, Aufrufer `routes/account/+page.svelte:279`)
  — fehlte bisher; `/api/locations/resolve` Resolver 8–10 s je Client, gesamt bis ~20–30 s (`Step2Orte.svelte:122`,
  `LocationNewModal.svelte:44`). Alle übrigen `send()`-Aufrufe sind kurze CRUD-Vorgänge.
- **Budget-Durchreichung:** `api.get/post/patch/del` reichen `extra` heute NICHT durch, nur `put` (`api.ts:196-200`).
  `extra.signal` wird heute nirgends an `send()` übergeben.
- **Schreiben nach Timeout:** Warteschlange schluckt Fehler (`etagRegistry.ts:204-206`) ⇒ ein abgebrochener PUT gibt die
  Kette frei (heute blockiert ein hängender PUT alle Folge-PUTs unbegrenzt — Nebennutzen). ETag wird nur bei Erfolg
  gesetzt (`api.ts:158-169`) ⇒ hat der abgebrochene PUT den Server erreicht, endet der nächste PUT in 412 →
  `markiereKonflikt` (`api.ts:141`) = geprüfter Konfliktpfad, kein stilles Überschreiben. Muss per Test belegt werden.
- **AbortError-Schlucker:** `EmailIframe.svelte:25`, `SmsPhoneFrame.svelte:32` ignorieren `AbortError`, nutzen aber rohes
  fetch — nicht betroffen. Trotzdem Timeout als eigener Fehler (`name='TimeoutError'`, deutsche Meldung), **nicht**
  `status: 0` (0 = Schreibsperre).
- **keepalive:** Unload-Flush ohne Limit lassen (Abbruch bringt nichts, Browser begrenzen keepalive selbst).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/api.ts` | MODIFY | Zeitlimit in `send()` (AbortController+setTimeout, clearTimeout im finally, Aufrufer-Signal weiterleiten, Signal NACH `...extra`), Default-Konstante + Test-Setter, `zeitlimitMs` pro Aufruf, `get/post/patch/del` reichen Optionen durch, keepalive ausgenommen, Timeout ⇒ `meldeAbrufAusgang(false)` + `TimeoutError` (~40 LoC) |
| `frontend/src/lib/stores/verbindung.svelte.ts` | MODIFY | Probe-GET `/api/health` über `send()` in Intervall solange `offline` und Seite sichtbar (~25 LoC) |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | Vorschau-Budget ~70 s |
| `frontend/src/lib/components/**/alerts-tab/AlertPreviewCard.svelte` | MODIFY | Budget ~40 s |
| `frontend/src/lib/components/compare/steps/Step2Orte.svelte`, `LocationNewModal.svelte` | MODIFY | resolve-Budget ~40 s |
| `frontend/src/routes/account/+page.svelte` | MODIFY | `notify/test`-Budget ~130 s |
| `frontend/src/lib/__tests__/apiZeitlimit.test.ts` | CREATE | node --test, Muster `apiSchreibsperre.test.ts` (~90 LoC) |

### Scope Assessment
- Files: 8 (7 MODIFY, 1 CREATE)
- Estimated LoC: +~85 produktiv / +~90 Test
- Risk Level: MEDIUM — zentrale Abruffunktion aller Frontend-Aufrufe; Fehlabbruch von Langläufern bzw. Fehl-Sperre bei falsch bemessenem Budget

### Technical Approach
- Scope **nur `send()`** (Issue-Kern). Direkte `fetch()`-Aufrufe (Uploads, ZIP-Export, Versand `sendOutcome.ts` bis 330 s #2124,
  Vorschau-Iframes, Status-PUT/DELETE in Routen) bleiben unverändert; sie melden auch heute nicht an den Verbindungs-Store.
- `AbortController` + `setTimeout` statt `AbortSignal.timeout`/`AbortSignal.any` — keine Browser-Abhängigkeit (Safari <17.4),
  ohne Fake-Timer testbar (Default per Setter auf ~20 ms senken).
- **Default-Budget 25 s** (EDGE-tauglich: deutlich über 8–10 s Broadband-Empfehlung, Funkloch nach ~½ Min gemeldet).
  Ausnahmen pro Aufruf: Compare-Vorschau 70 s, `notify/test` 130 s, Alarm-Vorschau 40 s, resolve 40 s (jeweils Go-Proxy-
  Timeout + Puffer).
- Timeout ⇒ derselbe Fehlerpfad wie Netzfehler: `meldeAbrufAusgang(false)`, Fehler weiterwerfen. **Keine Retries.**
- Probe in `verbindung.svelte.ts` schließt die Sperr-Sackgasse.

### Tests (Kern, node --test)
1. fetch-Mock löst nie auf ⇒ `send()` wirft nach Zeitlimit `TimeoutError`, `gz-abruf-fehlgeschlagen` feuert.
2. Langsamer, aber fristgerechter Abruf ⇒ läuft durch, `gz-abruf-gelungen`.
3. Pro-Aufruf-Budget überschreibt Default (Langläufer nicht abgebrochen).
4. keepalive-Request erhält kein Zeitlimit.
5. Aufrufer-Signal bricht weiterhin ab.
6. Abgebrochener PUT gibt Warteschlange frei; Folge-PUT trägt alten ETag ⇒ 412-Konfliktpfad.
7. Probe: offline ⇒ Probe-GET, Erfolg entsperrt; online ⇒ keine Probe.
8. Regression: `apiSchreibsperre.test.ts` und ETag-Tests grün.

### Dependencies
`fetch`, `AbortController`, `etagRegistry` (ETag/If-Match, Warteschlange), Verbindungs-Store-Events, `OfflineSperre`.

### Open Questions
- Keine PO-Frage offen (Default 25 s, Probe-Mitnahme und Scope sind technische Entscheidungen, oben begründet).
- Nebenbefund: Workflow-Register kennt einen Eintrag `fix-2361-fetch-timeout` (phase8_complete, Spec
  `api_client_fetch_timeout.md`), zu dem weder Spec noch Commit im Repo existiert — Karteileiche, ohne Einfluss.
